"""The criterion judge: whether the answer did what the `criterion` column asks, read by TypeSafe.

    uv run python -m evals.criterion <run.jsonl> ... [<case> ...] [--cases] [-v [--all]]
        judges saved runs again, without running the agent; with ids, only those cases

The suite grades two more things than the citation, and the two are seen separately:

- `retrieved`: whether the searcher brought one of the `pages` in the sources of its
  report. It is what a change to the bundle or the searcher moves.
- `met`: whether the writer's answer does what the criterion says and does not
  do what the criterion calls a failure. It is what a change to the writer moves.

Until Sep 24, 2026 the only grade was the citation (`is_hit`), and in 958
saved turns it was wrong in both directions: "the catalog does not cover Zelvora
on tomato; I will escalate" passed because it cited the Zelvora datasheet, and an answer
that offered exactly Brimnitro, Brimsol and Rootvane failed because it cited only the
Kelthar Total one. The citation stays as a cheap floor and as a column, not as a verdict.

# Atomic conditions

A row can carry, after the criterion, the `conditions` column: things the
answer does (`+`) or does not do (`-`), separated by ` | `:

    + recommends Metavane | + gives a dose | - asks the customer for the area

Each one goes to TypeSafe as its own `noul`, all in the same request, and the
row is met if each `+` comes out yes and each `-` comes out no. `p` is the worst of the
conditions, and `unmet` says which ones failed. Without the column the
criterion is judged in prose, with a single question.

Why atomic. With the criterion in prose, TypeSafe hesitated when faced with several
conditions together: the answers of `compra-metavane:1`, which met everything,
came out between 0.2 and 0.5, and rewriting the sentence did not get them off the edge. A
simple question is where this judge does well (the sale gates measure
0.9 against 0.05), and TypeSafe charges for the input once, so ten conditions
cost almost the same as one: the state is what gets paid for.

The judge does not see the datasheets, so it cannot verify a number: it judges what the
answer does (offers, escalates, asks, remembers, refuses), and the number stays
in the care of the citation. That is why a condition says "gives a dose", not which one.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core_agent.world.typesafe import Client

MET = "meets_the_criterion"

QUESTION: dict[str, Any] = {
    MET: {
        "type": "noul",
        "instructions": (
            "`conversation` is the previous turns between a customer and the advisor of an agricultural "
            "catalog, `customer` is what the customer says now and `advisor` is the answer being "
            "judged. `criterion` is what an agronomist of the business wrote that a good answer "
            "has to do in this turn, and what counts as a failure. Does the advisor's answer "
            "meet the criterion?"
        ),
        "criteria": {
            "true": (
                "It does what the criterion asks: it names what it has to name, offers what it has "
                "to offer, asks what it has to ask. And it does none of what the "
                "criterion marks as a failure. It can say it in other words or add facts "
                "alongside. If the criterion asks for a number from the datasheet, giving it is enough: "
                "whether the number is exact is not judged."
            ),
            "false": (
                "It lacks something the criterion asks for, or does something the criterion says is the "
                "failure: it says there is none or that the catalog does not cover it when the criterion says "
                "there is, it escalates or passes it to another person when the criterion asks to answer it, "
                "it offers a product the criterion rules out, it chooses for the customer, or it asks "
                "again what was already said."
            ),
        },
    }
}

THRESHOLD = 0.5
"""From which `p` the answer met it. It is a grade and not a gate: the report prints `p` all the same."""


@dataclass(frozen=True, slots=True)
class Condition:
    text: str
    wanted: bool
    """`+`: the answer does it. `-`: it does not."""


def conditions(column: str) -> tuple[Condition, ...]:
    """The `conditions` column as a tuple. Each one starts with `+` or `-`; empty is none."""
    out = []
    for raw in column.split("|"):
        raw = raw.strip()
        if not raw:
            continue
        if raw[0] not in "+-":
            raise ValueError(f"a condition starts with + or -: {raw!r}")
        out.append(Condition(raw[1:].strip(), raw[0] == "+"))
    return tuple(out)


def asked(conds: Sequence[Condition]) -> dict[str, Any]:
    """One `noul` question per condition, with the same shape: does the answer do this?"""
    return {
        f"c{i}": {
            "type": "noul",
            "instructions": (
                "`conversation` is the previous turns between a customer and the advisor of an agricultural "
                "catalog, `customer` is what the customer says now and `advisor` is the answer being "
                f"judged. Does the advisor's answer do this?: {c.text}"
            ),
            "criteria": {
                "true": "The answer does it, in these words or in others.",
                "false": "The answer does not do it.",
            },
        }
        for i, c in enumerate(conds)
    }


@dataclass(frozen=True, slots=True)
class Verdict:
    p: float | None
    """The worst condition, or the `p` of the criterion in prose. `None` if there was no judgment."""
    unmet: tuple[str, ...] = ()
    """The conditions that failed, with their sign."""


def state(criterion: str, question: str, reply: str, before: Sequence[tuple[str, str]] = ()) -> dict[str, Any]:
    """What the judge reads: the previous turns, the current one and the criterion."""
    return {
        "conversation": [{"customer": q, "advisor": a} for q, a in before],
        "customer": question,
        "advisor": reply,
        "criterion": criterion,
    }


async def met(client: Client, criterion: str, question: str, reply: str, before: Sequence[tuple[str, str]] = ()) -> float | None:
    """The `p` that it met the criterion in prose, or `None` if the row has no criterion or TypeSafe did not answer."""
    if not criterion.strip():
        return None
    try:
        r = await client.ask(state(criterion, question, reply, before), QUESTION)
        return round(r.noul(MET), 2)
    except Exception as e:
        print(f"  [criterion] no judgment: {type(e).__name__}: {e}", file=sys.stderr)
        return None


async def judge(
    client: Client, criterion: str, column: str, question: str, reply: str, before: Sequence[tuple[str, str]] = ()
) -> Verdict:
    """With `conditions`, one question per condition in a single request; without them, the criterion in prose."""
    conds = conditions(column)
    if not conds:
        return Verdict(await met(client, criterion, question, reply, before))
    st = state("", question, reply, before)
    del st["criterion"]
    try:
        r = await client.ask(st, asked(conds))
        scores = [(c, r.noul(f"c{i}") if c.wanted else 1 - r.noul(f"c{i}")) for i, c in enumerate(conds)]
    except Exception as e:
        print(f"  [criterion] no judgment: {type(e).__name__}: {e}", file=sys.stderr)
        return Verdict(None)
    unmet = tuple(f"{'+' if c.wanted else '-'} {c.text} ({q:.2f})" for c, q in scores if q < THRESHOLD)
    return Verdict(round(min(q for _, q in scores), 2), unmet)




@dataclass(frozen=True, slots=True)
class Saved:
    case: str
    attempt: int
    ok: bool
    reply: str
    path: str


def load(path: Path) -> list[Saved]:
    out = []
    for raw in path.read_text().splitlines():
        d = json.loads(raw)
        if not d.get("lost"):
            out.append(Saved(d["case"], d["attempt"], d["ok"], d["answer"], path.name))
    return out


async def main(argv: list[str]) -> None:
    from evals.suite import cases, flows

    files = [Path(a) for a in argv if a.endswith(".jsonl")]
    only = {a for a in argv if not a.startswith("-") and not a.endswith(".jsonl")}
    if not files:
        raise SystemExit(__doc__)
    table = {c.id: c for tsv in ("cases.tsv", "questions.tsv") for c in cases(tsv)}
    for tsv in ("flows.tsv", "flows-complex.tsv", "flows-cart.tsv"):
        for f in flows(tsv):
            table.update({t.id: t for t in f.turns})
    saved = [s for p in files for s in load(p)]
    replies = {(s.path, s.case, s.attempt): s.reply for s in saved}
    if only:
        saved = [s for s in saved if s.case in only]

    def before(s: Saved) -> list[tuple[str, str]]:
        flow, _, n = s.case.rpartition(":")
        if not flow or not n.isdigit():
            case = table.get(s.case)
            return list(case.history)[-3:] if case else []
        ids = [f"{flow}:{i}" for i in range(1, int(n))]
        return [(table[i].question, replies.get((s.path, i, s.attempt), "")) for i in ids if i in table][-3:]

    client = Client.from_env()
    if client is None:
        raise SystemExit("without TYPESAFE_API_KEY there is no judge")
    sem = asyncio.Semaphore(8)

    async def one(s: Saved) -> tuple[Saved, float | None, tuple[str, ...]]:
        case = table.get(s.case)
        if case is None:
            return s, None, ()
        async with sem:
            v = await judge(client, case.criterion, case.conditions, case.question, s.reply, before(s))
            return s, v.p, v.unmet

    try:
        judged = await asyncio.gather(*(one(s) for s in saved))
    finally:
        await client.aclose()

    both = {(True, True): 0, (True, False): 0, (False, True): 0, (False, False): 0}
    for s, p, _ in judged:
        if p is None:
            continue
        both[(s.ok, p >= THRESHOLD)] += 1
    print(f"judged {sum(both.values())}/{len(judged)} turns, USD {client.cost:.4f}")
    print(f"  cited and met         {both[(True, True)]}")
    print(f"  cited and not met     {both[(True, False)]}")
    print(f"  not cited and met     {both[(False, True)]}")
    print(f"  not cited and not met {both[(False, False)]}")
    by_case: dict[str, list[bool]] = {}
    for s, p, _ in judged:
        if p is not None:
            by_case.setdefault(s.case, []).append(p >= THRESHOLD)
    if "--cases" in argv:
        for case_id, got in by_case.items():
            print(f"  {sum(got):3d}/{len(got):<3d} {case_id}")
    if "-v" in argv:
        for s, p, unmet in judged:
            if p is not None and (s.ok != (p >= THRESHOLD) or "--all" in argv and p < THRESHOLD):
                print(f"\n  {'cited' if s.ok else 'not cited'} · p={p:.2f}  {s.case} #{s.attempt}  ({s.path})")
                for u in unmet:
                    print(f"    failed: {u}")
                print(f"    {s.reply[:400]}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
