"""A/B of a specific change: the same cases against two versions of the agent and the bundle, side by side.

    uv run python -m evals.ab <A> <B> <case>|--topic=<topic> ... [--repeats=N] [--yes] [--cap=USD]
                              [--threshold=k/n] [--lever=<name> [--note=<text>]]

Each side is `agro+okf`, two git refs, and `.` is the working tree as it
stands, uncommitted. `4bba8c2+3812cf1 .+.` is "what is on main against what
I have open"; `HEAD+3812cf1 HEAD+3dacbd2` is "the same agent with the bundle
from before and the one from now". The ids and flags pass as they are to `python -m evals`.

The use is the probe case: each change comes with a one-turn case that touches exactly
what changed, and the A/B runs that case with repeats. The whole suite is not
run: a broad change takes one probe for each edge it touches.

How:
- A ref that is not `.` is built as a worktree in a temporary directory, with the
  repo's `.venv` linked and the `.env` copied, and deleted at the end. Never
  `uv run` inside: it would resync the shared environment.
- Both sides sit the same exam: the `evals/` of this tree goes on top
  of the one in each agro worktree, and the `evals/` of the working okf on top of the one in
  each okf worktree. What changes between A and B is `src/` and the bundle, not
  who grades or which cases exist; that way the new probe case exists on both
  sides. A very old side, from before a rename in `src/`, may not
  run with today's `evals/`.
- Before spending it says how much it will cost. The cap is USD 0.10 (`CAP`); if the estimate goes over, it asks for
  `--yes`, which raises the cutoff up to USD 1 and no further: no run goes over USD 1 adding both sides
  (`allowed`).
- While it runs it adds up what each side is spending, model and judges, and if it passes the cutoff it kills both
  and records what was spent in `spend.txt` (`watch`). At the end, what was spent goes in `spend.txt` all the same.
- Before running it says what that n can claim: with n=3 nothing reaches p < 0.05.
- Below the table, one line per case with the `met` of each side (always,
  never or sometimes, and its Wilson interval), the Fisher p, Bayesian P(B>A) and
  "inconclusive" if p ≥ 0.05. Per case and not in TOTAL, because the turns of a
  conversation are not independent. `--threshold=9/10` is the bar written before
  running: B has to meet at least that fraction in each case. It works the same for
  an improvement and for "it did not get worse".
- At the end it says whether the sample works as a gate: with n < 10 it is smoke; with n ≥ 10, n and the real USD
  (`sample`). `--lever` does not record with n < 10.
- The transcripts stay in `evals/runs/ab-<date>/A` and `.../B`.
- With `--lever` it records the two rows in `logbook.tsv`, `A` as `baseline` and
  `B` as `new`, with the case, the `met` of each side and `--note` in the
  note (`evals/logbook.py`). Without the flag it records nothing.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.logbook import append, fill, flag, without_flags

ROOT = Path(__file__).resolve().parents[1]
OKF = Path(os.environ.get("OKF_DIR", ROOT / "okf")).resolve()

PER_TURN = 0.0035
"""Dollars per turn, rounded up: gpt-6-luna with the searcher, measured on Sep 24, 2026.

0.0024 to 0.0068 was measured with the gpt-5.6-luna table (0.20/0.02/1.20); with the real price of
gpt-6-luna (0.10/0.01/0.50) it is 0.0010 to 0.0034, corrected on Oct 14, 2026.
"""

CAP = 0.10
"""Above this it does not run without `--yes`."""

CEILING = 1.00
"""The ceiling of any run, adding both sides: `--yes` raises up to here, and no flag goes past it.

As in agro since Oct 18, 2026 (3.6-01, «Choque 0.1» with D2); in demo since 3.6-04.
Until that day `--yes` skipped it with no ceiling and nothing cut live.
"""

GATE_N = 10
"""The minimum n for a run to work as a gate and be recorded with `--lever`: below it is smoke."""

SPENT = "[spend] USD "
"""The line the suite prints after each attempt with what its side has spent so far (`evals/suite.py`)."""


class Cut(Exception):
    """The run passed the cutoff and was killed: `spent` is what was spent."""

    def __init__(self, spent: float) -> None:
        super().__init__(f"USD {spent:.4f}")
        self.spent = spent


@dataclass(frozen=True, slots=True)
class Side:
    name: str
    agro: str
    okf: str

    @classmethod
    def parse(cls, name: str, spec: str) -> Side:
        agro, sep, okf = spec.partition("+")
        if not sep or not agro or not okf:
            raise SystemExit(f"{name}: {spec!r} is not agro+okf (for example HEAD+3dacbd2, or .+. for the working tree)")
        return cls(name, agro, okf)

    @property
    def label(self) -> str:
        return f"{self.name} = agro {describe(ROOT, self.agro)} + okf {describe(OKF, self.okf)}"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def describe(repo: Path, ref: str) -> str:
    if ref == ".":
        dirty = "-dirty" if git(repo, "status", "--porcelain", "--untracked-files=no") else ""
        return f"{git(repo, 'rev-parse', '--short', 'HEAD')}{dirty} (tree)"
    return git(repo, "rev-parse", "--short", ref)


def checkout(repo: Path, ref: str, where: Path) -> Path:
    """The tree of `ref`: the repo itself if it is `.`, or a new worktree at `where`."""
    if ref == ".":
        return repo
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", "-q", str(where), ref], check=True)
    return where


def prepare(side: Side, tmp: Path) -> tuple[Path, Path]:
    """The agro and the okf of a side, ready to run with the `evals/` of this tree."""
    agro = checkout(ROOT, side.agro, tmp / f"agro-{side.name}")
    okf = checkout(OKF, side.okf, tmp / f"okf-{side.name}")
    if agro != ROOT:
        (agro / ".venv").symlink_to(ROOT / ".venv")
        if (ROOT / ".env").exists():
            shutil.copy(ROOT / ".env", agro / ".env")
        shutil.rmtree(agro / "evals")
        shutil.copytree(ROOT / "evals", agro / "evals", ignore=shutil.ignore_patterns("runs", "__pycache__"))
    if okf != OKF:
        shutil.rmtree(okf / "evals")
        shutil.copytree(OKF / "evals", okf / "evals")
    return agro, okf


def cleanup(tmp: Path) -> None:
    for repo in (ROOT, OKF):
        for wt in tmp.glob("*"):
            subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)], capture_output=True, check=False)
    shutil.rmtree(tmp, ignore_errors=True)
    for repo in (ROOT, OKF):
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], capture_output=True, check=False)


def turns(argv: Sequence[str], okf: Path) -> int:
    """How many turns a side runs, with the TSVs of its bundle."""
    code = "import sys; from evals import suite; print(sum(len(e.turns) for e in suite.select(sys.argv[1:]) or ()))"
    env = {**os.environ, "DEMO_BUNDLE": str(okf)}
    out = subprocess.run([str(ROOT / ".venv/bin/python"), "-c", code, *argv], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise SystemExit(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else f"the suite could not count the turns of {argv}")
    return int(out.stdout.strip().splitlines()[-1])


async def start(agro: Path, okf: Path, argv: Sequence[str], log: Path) -> asyncio.subprocess.Process:
    """Launches the suite of a side; what it prints goes to `log`."""
    env = {**os.environ, "DEMO_BUNDLE": str(okf)}
    with log.open("w") as f:
        return await asyncio.create_subprocess_exec(
            str(agro / ".venv/bin/python"), "-m", "evals", *argv, cwd=agro, env=env, stdout=f, stderr=subprocess.STDOUT
        )


def spent(log: Path) -> float:
    """The last thing a side said it has spent (`SPENT`), or 0 if no attempt has finished yet."""
    if not log.exists():
        return 0.0
    last = next((raw for raw in reversed(log.read_text().splitlines()) if raw.startswith(SPENT)), None)
    return float(last.removeprefix(SPENT)) if last else 0.0


async def watch(procs: Sequence[asyncio.subprocess.Process], logs: Sequence[Path], cut: float, every: float = 1.0) -> float:
    """Waits for the sides, adding up what they spend; if the sum passes `cut`, it kills them all and raises `Cut`.

    The suite states its spend when each attempt of a flow finishes, so the cut arrives at the first attempt
    that passes it: it can go over by what the parallel attempts of that moment were running.
    """
    while True:
        done = all(p.returncode is not None for p in procs)
        total = sum(spent(log) for log in logs)
        if total > cut:
            for p in procs:
                if p.returncode is None:
                    p.terminate()
            await asyncio.gather(*(p.wait() for p in procs))
            raise Cut(sum(spent(log) for log in logs))
        if done:
            return total
        await asyncio.sleep(every)


def transcripts(side: Side, agro: Path, log: Path) -> Path | None:
    """The JSONL left by the suite of a side, from the line it prints at the end."""
    for raw in reversed(log.read_text().splitlines()):
        if "transcripts:" in raw:
            return agro / raw.split("transcripts:", 1)[1].strip()
    print(f"  {side.name} left no transcripts: see {log}")
    return None


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(raw) for raw in path.read_text().splitlines() if raw.strip()]


def cell(rows: list[dict[str, Any]], key: str, test: Callable[[Any], bool] = bool) -> str:
    """`k/n` of the live runs with `key` judged; `·` if none has it."""
    judged = [r for r in rows if not r.get("lost") and r.get(key) is not None]
    return f"{sum(1 for r in judged if test(r[key]))}/{len(judged)}" if judged else "·"


def met(p: Any) -> bool:
    """The threshold of `evals/criterion.py`, without importing it: this module does not load the agent."""
    return bool(p >= 0.5)


def tally(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """How many live runs met it and how many were judged."""
    judged = [r for r in rows if not r.get("lost") and r.get("met") is not None]
    return sum(1 for r in judged if met(r["met"])), len(judged)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% interval of a rate `k/n`. Unlike `k/n ± 1.96·SE`, it does not collapse at 3/3 or leave [0, 1]:
    3/3 gives [0.44, 1], meaning three out of three does not rule out a case that fails half the time."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def fisher(ka: int, na: int, kb: int, nb: int) -> float:
    """The exact two-sided Fisher p for `ka/na` against `kb/nb`: the chance of seeing a difference like this or larger if A and B
    were equal. Exact, not normal, because with n=3 or 6 the normal lies: 0/3 against 3/3 gives 0.10, and 0/6 against 6/6, 0.002."""
    k, n = ka + kb, na + nb
    if n == 0 or na == 0 or nb == 0:
        return 1.0

    def prob(x: int) -> float:
        return math.comb(k, x) * math.comb(n - k, na - x) / math.comb(n, na)

    seen = prob(ka)
    return min(1.0, sum(prob(x) for x in range(max(0, k - nb), min(k, na) + 1) if prob(x) <= seen * (1 + 1e-9)))


def better(ka: int, na: int, kb: int, nb: int, grid: int = 2000) -> float:
    """The Bayesian question: given what was seen, the probability that the rate of B is higher than that of A. It starts with no
    opinion (Beta(1,1)) and sums the density of B times the cumulative of A on a grid. It answers something different from Fisher and with a small n
    it is more optimistic: 0/3 against 3/3 gives p=0.10 and P(B>A)=0.986. It works next to the p, not in its place."""
    xs = [(i + 0.5) / grid for i in range(grid)]
    fa = [x**ka * (1 - x) ** (na - ka) for x in xs]
    fb = [x**kb * (1 - x) ** (nb - kb) for x in xs]
    sa, sb = sum(fa), sum(fb)
    below, out = 0.0, 0.0
    for a, b in zip(fa, fb, strict=True):
        out += b / sb * (below + a / sa / 2)
        below += a / sa
    return out


def group(k: int, n: int) -> str:
    """Always, never or sometimes: where the fix is. Never is a missing fact or a badly written criterion; sometimes is a
    text the model reads two ways, or the judge that does not agree with itself."""
    return "always" if k == n else "never" if k == 0 else "sometimes"


def power(pa: float, pb: float, n: int) -> float:
    """The chance that Fisher declares B better (p < 0.05) with `n` runs per side, if the real rates are `pa` and `pb`."""
    odds = [[math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)] for p in (pa, pb)]
    return sum(odds[0][a] * odds[1][b] for a in range(n + 1) for b in range(a + 1, n + 1) if fisher(a, n, b, n) < 0.05)


def reach(n: int) -> str:
    """Before spending, what an A/B of `n` per side can claim: with n=3 no result reaches p < 0.05."""
    if fisher(0, n, n, n) >= 0.05:
        return f"with n={n} per side no result reaches p < 0.05: it works to see if something broke, not to declare an improvement"
    return f"with n={n} per side, the chance of noticing an improvement from 20% to 90% is {power(0.2, 0.9, n):.0%}, and from 50% to 90%, {power(0.5, 0.9, n):.0%}"


def plan(passthrough: Sequence[str], rest: Sequence[str]) -> int:
    """The n of the run, from `--repeats=`. With `--lever`, n < `GATE_N` does not run: it is smoke and is not recorded."""
    n = next((int(x.removeprefix("--repeats=")) for x in passthrough if x.startswith("--repeats=")), 1)
    if n < GATE_N and flag(rest, "lever") is not None:
        raise SystemExit(f"--lever with n={n}: a gate A/B takes n ≥ {GATE_N}; n={n} is smoke and is not recorded")
    return n


def allowed(estimate: float, rest: Sequence[str]) -> float:
    """The live cutoff of the run, or `SystemExit` if the estimate does not fit.

    Without flags the cutoff is `CAP`, and `--cap` changes it up to `CEILING`. `--yes` accepts an estimate
    above the cap and raises the cutoff to `CEILING`. Nothing goes past it: a change that does not fit is measured with fewer cases.
    """
    cap = next((float(x.removeprefix("--cap=")) for x in rest if x.startswith("--cap=")), CAP)
    if cap > CEILING:
        raise SystemExit(f"--cap={cap:.2f} is over USD {CEILING:.2f}, the ceiling of any run: shrink the cases (n does not go down)")
    cut = CEILING if "--yes" in rest else cap
    if estimate <= cut:
        return cut
    if estimate <= CEILING:
        raise SystemExit(f"~USD {estimate:.2f} is over the cap of USD {cap:.2f}: shrink the cases (n does not go down), or --yes raises the cutoff up to USD {CEILING:.2f}")
    raise SystemExit(f"~USD {estimate:.2f} is over USD {CEILING:.2f}, the ceiling of any run: shrink the cases (n does not go down)")


def sample(n: int, usd: float) -> str:
    """Whether the run works as a gate: with n < `GATE_N` it is smoke; if not, n and the real USD, which is what `F gate` asks for."""
    if n < GATE_N:
        return f"smoke: n={n} < {GATE_N}, it shows whether something broke and does not work for F gate (USD {usd:.4f})"
    return f"gate: n={n}, USD {usd:.4f} (F gate ... --n {n} --usd {usd:.4f})"


def threshold(spec: str | None) -> tuple[int, int] | None:
    """`--threshold=9/10`: B has to meet at least that fraction in each case. It is written before running."""
    if spec is None:
        return None
    k, sep, n = spec.partition("/")
    if not sep or not k.isdigit() or not n.isdigit() or int(n) == 0 or int(k) > int(n):
        raise SystemExit(f"--threshold={spec}: it goes as k/n, for example --threshold=9/10")
    return int(k), int(n)


def verdict(a: list[dict[str, Any]], b: list[dict[str, Any]], bar: tuple[int, int] | None = None) -> str:
    """The `met` of a case in one line: the group and the interval of each side, the p, P(B>A), whether it is enough to say
    something and, with `--threshold`, whether B passes it."""
    (ka, na), (kb, nb) = tally(a), tally(b)
    if not na or not nb:
        return "·"
    p = fisher(ka, na, kb, nb)
    (la, ha), (lb, hb) = wilson(ka, na), wilson(kb, nb)
    said = ("B better" if kb / nb > ka / na else "B worse") if p < 0.05 else "inconclusive"
    line = (
        f"A {ka}/{na} {group(ka, na):9s} [{la:.2f}–{ha:.2f}]  B {kb}/{nb} {group(kb, nb):9s} [{lb:.2f}–{hb:.2f}]"
        f"  p={p:.3f} P(B>A)={better(ka, na, kb, nb):.2f} {said}"
    )
    if bar is not None:
        line += f"  threshold {bar[0]}/{bar[1]}: {'passes' if kb * bar[1] >= bar[0] * nb else 'does not pass'}"
    return line


def table(a: list[dict[str, Any]], b: list[dict[str, Any]], bar: tuple[int, int] | None = None) -> None:
    ids = list(dict.fromkeys(r["case"] for r in (*a, *b)))
    print(f"\n  {'case':34s} {'cited':>11s} {'retrieved':>11s} {'met':>11s} {'escalated':>11s} {'effects':>11s} {'order':>11s} {'form':>11s} {'tok/turn':>15s}")
    print(f"  {'':34s} {'A    B':>11s} {'A    B':>11s} {'A    B':>11s} {'A    B':>11s} {'A    B':>11s} {'A    B':>11s} {'A      B':>15s}")
    for id_ in [*ids, "TOTAL"]:
        ra = a if id_ == "TOTAL" else [r for r in a if r["case"] == id_]
        rb = b if id_ == "TOTAL" else [r for r in b if r["case"] == id_]

        def tok(rows: list[dict[str, Any]]) -> str:
            alive = [r["spent"] for r in rows if not r.get("lost")]
            return f"{sum(alive) // len(alive):,}" if alive else "·"

        print(
            f"  {id_:34s} {cell(ra, 'ok'):>5s} {cell(rb, 'ok'):>5s} {cell(ra, 'retrieved'):>5s} {cell(rb, 'retrieved'):>5s}"
            f" {cell(ra, 'met', met):>5s} {cell(rb, 'met', met):>5s}"
            f" {cell(ra, 'escalation_ok'):>5s} {cell(rb, 'escalation_ok'):>5s}"
            f" {cell(ra, 'effects_ok'):>5s} {cell(rb, 'effects_ok'):>5s} {cell(ra, 'order_ok'):>5s} {cell(rb, 'order_ok'):>5s}"
            f" {cell(ra, 'form_ok'):>5s} {cell(rb, 'form_ok'):>5s} {tok(ra):>7s} {tok(rb):>7s}"
        )
    print("\n  met per side: always, never or sometimes, with the 95% interval (Wilson); Fisher p, inconclusive if p ≥ 0.05")
    for id_ in ids:
        print(f"  {id_:34s} {verdict([r for r in a if r['case'] == id_], [r for r in b if r['case'] == id_], bar)}")


def printed_row(log: Path) -> str | None:
    """The logbook row printed by the suite of a side: the line that follows the notice."""
    lines = log.read_text().splitlines()
    for i, raw in enumerate(lines[:-1]):
        if "with your lever, arm and note:" in raw:
            return lines[i + 1]
    return None


def annotate(lever: str, note: str, argv: Sequence[str], n: int, out: Path, a: list[dict[str, Any]], b: list[dict[str, Any]]) -> None:
    """The two A/B rows to the logbook: `baseline` and `new`, with the `met` of both sides in each note."""
    probe = " ".join(x for x in argv if not x.startswith("-") or x.startswith("--topic="))
    ma, mb = cell(a, "met", met), cell(b, "met", met)
    if len({r["case"] for r in (*a, *b)}) == 1 and all(tally(a)) and all(tally(b)):
        note = f"Fisher p={fisher(*tally(a), *tally(b)):.3f}, P(B>A)={better(*tally(a), *tally(b)):.2f}. {note}"
    rows = []
    for side, arm, mine, other in (("A", "baseline", ma, mb), ("B", "new", mb, ma)):
        line = printed_row(out / side / "output.txt")
        if line is None:
            print(f"  {side} did not print its row: recording nothing")
            return
        rows.append(fill(line, lever, arm, f"A/B {probe} n={n}: met {mine} (the other side {other}). {note}"))
    append(rows)


async def main(argv: list[str]) -> None:
    sides = [a for a in argv if not a.startswith("-")][:2]
    if len(sides) < 2:
        raise SystemExit(__doc__)
    a, b = Side.parse("A", sides[0]), Side.parse("B", sides[1])
    rest = list(argv)
    for s in sides:
        rest.remove(s)
    passthrough = [x for x in without_flags(rest) if x != "--yes" and not x.startswith(("--cap=", "--threshold="))]
    bar = threshold(flag(rest, "threshold"))
    n = plan(passthrough, rest)
    if not [x for x in passthrough if not x.startswith("-") or x.startswith("--topic=")]:
        raise SystemExit("missing the probe case or the topic: the A/B runs specific cases, not the whole suite")

    tmp = Path(tempfile.mkdtemp(prefix="agro-ab-"))
    try:
        print(a.label)
        print(b.label)
        (agro_a, okf_a), (agro_b, okf_b) = prepare(a, tmp), prepare(b, tmp)
        total = (turns(passthrough, okf_a) + turns(passthrough, okf_b)) * n
        usd = total * PER_TURN
        print(f"{total} turns between the two sides, ~USD {usd:.2f}")
        print(reach(n))
        cut = allowed(usd, rest)
        print(f"live cutoff: USD {cut:.2f} between the two sides")

        out = ROOT / "evals" / "runs" / f"ab-{datetime.now():%Y%m%d-%H%M%S}"
        (out / "A").mkdir(parents=True)
        (out / "B").mkdir()
        logs = [out / "A" / "output.txt", out / "B" / "output.txt"]
        procs = [await start(agro_a, okf_a, passthrough, logs[0]), await start(agro_b, okf_b, passthrough, logs[1])]
        try:
            paid = await watch(procs, logs, cut)
        except Cut as c:
            (out / "spend.txt").write_text(f"cut: USD {c.spent:.4f}, passed the cutoff of USD {cut:.2f}\n")
            raise SystemExit(f"cut: USD {c.spent:.4f} spent, passed the cutoff of USD {cut:.2f}; they stay in {out}") from None
        (out / "spend.txt").write_text(f"USD {paid:.4f}, cutoff USD {cut:.2f}\n")
        print(f"\n  spent: USD {paid:.4f} between the two sides (cutoff USD {cut:.2f})")
        print(f"  {sample(n, paid)}")
        got = [transcripts(a, agro_a, logs[0]), transcripts(b, agro_b, logs[1])]
        kept = []
        for side, path in zip("AB", got, strict=True):
            if path is not None:
                kept.append(Path(shutil.move(path, out / side / path.name)))
        (out / "sides.txt").write_text(f"{a.label}\n{b.label}\n{' '.join(argv)}\n")
        if len(kept) == 2:
            a_rows, b_rows = load(kept[0]), load(kept[1])
            table(a_rows, b_rows, bar)
            if (lever := flag(rest, "lever")) is not None:
                annotate(lever, flag(rest, "note") or "", passthrough, n, out, a_rows, b_rows)
        print(f"\n  transcripts and output: {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")
    finally:
        cleanup(tmp)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
