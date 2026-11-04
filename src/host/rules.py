"""`Answer.rules`: what each `governance/` rule read in this turn, whether it fired or not.

Before Oct 3, 2026 the host saw the sale's p values and nothing else: not the turn's
case, nor which line the writer received, nor the answer's p values (the guardian), nor the
order's gates, nor that the case fell over and the writer received all four lines.
Auditing a turn meant comparing each p with its threshold by hand, and looking for the threshold
in the code.

One entry per table row, in table order: `id`, `p`, `threshold`, `fired`
and `action`. `p` is `None` if the rule was not asked this turn (the answer was not judged,
the case did not run, the judgment failed); then `fired` is `False`, except for the fallen case,
which fires all four lines at once because that is what the writer received. A
`choice` without options in the question (the escalation reason) also says which `option`
it chose. A code rule has no p: it comes out 1.0 or 0.0. A `choice` per cart line
(the datasheet and the presentation of each name) brings `lines`, one per choice with what was said,
the option and its p; the rule's `p` is the lowest, the weakest choice of the turn, and
`fired` means it chose some. With no lines to choose, `p` is null.

Nothing is decided here: each value was already read by the judge or computed by the code that acts, and
this only sets it next to the table's threshold. That the table's threshold is the one the
code uses is proven by `tests/core_agent/test_governance.py`.
"""

from __future__ import annotations

from typing import Any

from core_agent.prompts.judge import TURN_CASE
from core_agent.world.governance import ARGMAX, Rule
from core_agent.world.question_judge import Answered, Judgment, TurnCase


def entry(
    rule: Rule,
    *,
    judgment: Judgment | None = None,
    reply: Answered | None = None,
    case: TurnCase | None = None,
    codes: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """What a rule read in the turn."""
    out: dict[str, Any] = {"id": rule.id, "p": None, "threshold": rule.threshold, "fired": False, "action": rule.action}
    if rule.kind == "code":
        value = (codes or {}).get(rule.question)
        if value is not None:
            out.update(p=1.0 if value else 0.0, fired=value)
        return out
    if rule.label == TURN_CASE:
        if case is not None and case.error:
            out["fired"] = True
        elif case is not None:
            out.update(p=_sum(case.p, rule.options) if case.p else None, fired=case.case in rule.options)
        return out
    judged = judgment if judgment is not None and not judgment.error else None
    if rule.kind == "noul":
        p = judged.p.get(rule.question) if judged is not None else None
        if p is None and reply is not None:
            p = reply.p.get(rule.question)
        if p is not None:
            out.update(p=p, fired=_passes(p, rule.threshold))
        return out
    if rule.options:
        if judged is not None and rule.label in judged.dist:
            p = _sum(judged.dist[rule.label], rule.options)
            fired = judged.labels.get(rule.label) in rule.options if rule.threshold == ARGMAX else _passes(p, rule.threshold)
            out.update(p=p, fired=fired)
        return out
    if judged is not None and rule.label in judged.picks:
        picks = judged.picks[rule.label]
        ps = [k.p for k in picks if k.p is not None]
        out.update(
            p=min(ps) if ps else None,
            fired=True,
            lines=[{"said": k.said, "option": k.option, "p": k.p} for k in picks],
        )
        return out
    if reply is not None and rule.label in reply.labels:
        out.update(p=reply.label_p.get(rule.label), fired=True, option=reply.labels[rule.label])
    return out


def turn_rules(
    table: tuple[Rule, ...],
    *,
    judgment: Judgment | None = None,
    reply: Answered | None = None,
    case: TurnCase | None = None,
    codes: dict[str, bool] | None = None,
) -> tuple[dict[str, Any], ...]:
    """`Answer.rules`: one entry per rule of the table."""
    return tuple(entry(r, judgment=judgment, reply=reply, case=case, codes=codes) for r in table)


def _sum(dist: dict[str, float], options: tuple[str, ...]) -> float:
    return round(min(1.0, sum(dist.get(o, 0.0) for o in options)), 2)


def _passes(p: float, threshold: float | str | None) -> bool:
    return isinstance(threshold, float) and p >= threshold
