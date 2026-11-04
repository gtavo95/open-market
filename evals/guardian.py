"""The guardian eval: whether the judge escalates the answers it has to escalate, and only those.

    uv run python -m evals.guardian                  the cases in guardian.tsv
    uv run python -m evals.guardian <id> <id>        a subset by id
    uv run python -m evals.guardian --repeats=3      each case three times, with a new judge each round

It does not run the agent. It builds the turn with the customer's question and the answer already
written, and asks the judge the same thing `roles/human_handoff.py` asks it:
`HANDOFF_QUESTIONS` against `ESCALATE_THRESHOLD` (it escalates if any passes), and the reason (`HANDOFF_REASON`). That way
a writer sentence is tested without paying for the searcher, and it costs what
TypeSafe costs: about a thousand tokens per case, no model.

A case fails when `escalates` does not match. The reason is reported separately and does not make
it fail: a case that lands in the neighboring drawer gets attended all the same (see `HANDOFF_REASON_QUESTIONS`).
What matters most in the report are the edges: the lowest `p` of those that
escalate and the highest of those that do not. A threshold between the two classifies everything; the
air left on each side is what says how much a new sentence can take.

The cases live in `<bundle>/evals/guardian.tsv`, like those of `evals.py`:
`uv run python -m evals.guardian`.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core_agent import BUNDLE, QuestionJudge, provider
from core_agent.prompts.judge import HANDOFF_QUESTIONS, HANDOFF_REASON
from core_agent.roles.human_handoff import ESCALATE_THRESHOLD
from core_agent.world.dialogue import wrap
from catalejo.core import Log, Message, Role

from evals.suite import repeats

TSV = "guardian.tsv"


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    question: str
    answer: str
    escalates: bool
    reasons: tuple[str, ...]
    criterion: str


@dataclass(frozen=True, slots=True)
class Read:
    case: Case
    attempt: int
    p: float
    reason: str
    each: tuple[float, ...] = ()

    @property
    def escalated(self) -> bool:
        return self.p >= ESCALATE_THRESHOLD

    @property
    def ok(self) -> bool:
        return self.escalated == self.case.escalates

    @property
    def reason_ok(self) -> bool:
        return not self.case.escalates or self.reason in self.case.reasons


def cases() -> list[Case]:
    out = []
    for row in (BUNDLE / "evals" / TSV).read_text().splitlines():
        if not row.strip() or row.startswith("#"):
            continue
        id_, question, answer, escalates, reasons, criterion = row.split("\t")
        out.append(Case(id_, question, answer, escalates == "yes", tuple(reasons.split()) if reasons != "·" else (), criterion))
    return out


def turn(case: Case) -> Log:
    """The turn as the guardian sees it: the question in the envelope and the writer's answer behind it."""
    return Log(said=(Message(Role.USER, wrap(case.question, ())), Message(Role.ASSISTANT, case.answer)))


async def judge(chosen: list[Case], attempt: int) -> tuple[list[Read], float]:
    """A round with a new judge: the memory is per answer text, and a repeated round would not go to the network."""
    model = provider()
    question_judge = QuestionJudge.from_env(model)
    if question_judge is None:
        raise SystemExit("without TYPESAFE_API_KEY there is no judge to measure")
    try:
        async def one(case: Case) -> Read:
            seen = turn(case)
            answers = await question_judge(seen, frozenset(HANDOFF_QUESTIONS))
            each = tuple(answers[n] for n in HANDOFF_QUESTIONS)
            return Read(case, attempt, max(each), await question_judge.label(seen, HANDOFF_REASON), each)

        return list(await asyncio.gather(*(one(c) for c in chosen))), question_judge.cost
    finally:
        await question_judge.aclose()
        await model.aclose()


def line(r: Read, n: int) -> str:
    mark = "ok " if r.ok else "BAD"
    which = f" #{r.attempt + 1}" if n > 1 else ""
    said = "escalates" if r.escalated else "does not escalate"
    reason = f"  {r.reason}{'' if r.reason_ok else ' (expected ' + ' or '.join(r.case.reasons) + ')'}" if r.escalated else ""
    each = " ".join(f"{p:.2f}" for p in r.each)
    return f"  {mark} {r.case.id:30s}{which} p={r.p:.2f} [{each}]  {said}{reason}"


async def main(argv: list[str]) -> None:
    n = repeats(argv)
    asked = [a for a in argv if not a.startswith("-")]
    everything = cases()
    chosen = [c for c in everything if c.id in asked] if asked else everything
    if not chosen:
        print(f"no case {asked}. There are: {', '.join(c.id for c in everything)}")
        return
    print(f"guardian: {len(chosen)} cases, n={n}, threshold {ESCALATE_THRESHOLD}, p = the highest of [{' '.join(HANDOFF_QUESTIONS)}]")

    reads: list[Read] = []
    cost = 0.0
    for attempt in range(n):
        got, spent = await judge(chosen, attempt)
        reads += got
        cost += spent
    order = {c.id: i for i, c in enumerate(chosen)}
    reads.sort(key=lambda r: (order[r.case.id], r.attempt))
    for r in reads:
        print(line(r, n))

    up = [r for r in reads if r.case.escalates]
    down = [r for r in reads if not r.case.escalates]
    stable = [c for c in chosen if all(r.ok for r in reads if r.case is c)]
    print("\n\033[1m[result]\033[0m")
    print(f"  {'correct' if n == 1 else f'correct all {n}':25s} {len(stable)}/{len(chosen)} cases")
    print(f"  hits                      {sum(r.ok for r in reads)}/{len(reads)} reads")
    if up:
        low = min(up, key=lambda r: r.p)
        print(f"  edge of those escalating  {low.p:.2f} ({low.case.id})")
        print(f"  expected reason           {sum(r.reason_ok for r in up if r.escalated)}/{sum(r.escalated for r in up)} of those that escalated")
    if down:
        high = max(down, key=lambda r: r.p)
        print(f"  edge of those not         {high.p:.2f} ({high.case.id})")
    print(f"  judge                     USD {cost:.4f}")

    for case in chosen:
        bad = [r for r in reads if r.case is case and not r.ok]
        if bad:
            print(f"\n  \033[1m{case.id}\033[0m  expected {'it to escalate' if case.escalates else 'it not to escalate'}")
            print(f"    criterion: {case.criterion}")
            print(f"    answer: {case.answer}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
