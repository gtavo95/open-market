"""What the writer has to know before writing: the customer's state and the turn's alerts.

Three reports, on the way in, for the writer. `context` is the state the
sale compacted, in JSON: what the customer has said so far, without the
whole conversation. `already_said` is what the advisor already gave and asked, with the
rule of not repeating it (`SAID_PROMPT`). `alerts` are loose lines, one per raised flag:
the ad the customer arrives from, which the host marks and is read with code,
and each noul of `ALERT_ASKS` that passes `ALERT_THRESHOLD`.

What it costs: nothing extra. The state, what was already said and the nouls are from the same judgment
`close_sale_steps` already paid for; this cell reads them from the judge's memory.

From Sep 26, 2026: "Bellota" after the Escudo ad for
melon and watermelon was answered "We do not sell Bellota" and the guardian escalated it.
"""

from __future__ import annotations

import json
import re

from catalejo.core import Cell, Fail, Log, Report

from ..prompts.judge import ALERT_ASKS
from ..prompts.writer import AD_LINE, ALERT_LINES, ALERTS_WHO, CONTEXT_WHO, SAID_AGAIN, SAID_HEAD, SAID_WHO
from ..world.dialogue import conversation
from ..world.question_judge import QuestionJudge

ZERO = Log()

ALERT_THRESHOLD = 0.7
"""Lower than `THRESHOLD` (0.8) because one alert too many costs little: the writer asks what
they need. Measured on Sep 26, 2026 on `ambiguous_order`: "Bellota" 0.77, "Juan
Carlos" 0.93; "hello" 0.58, "Catalog" and "Escudo" 0.22.
"""

AD = re.compile(r"\[SYSTEM:[^\]]*\bad\b[^\]]*?\"([^\"]+)\"[^\]]*\]", re.IGNORECASE)
"""The mark the host puts when the customer answers an ad, with the ad's name in quotes."""


def ad_of(question: str) -> str:
    """The ad's name if this message carries the mark, or empty."""
    m = AD.search(question)
    return m.group(1).strip() if m else ""


def said_text(said: tuple[str, ...], again: tuple[str, ...]) -> str:
    """The `already_said` report: the rule, the list, and what the customer asks for again if they ask for anything."""
    lines = [SAID_HEAD, *(f"- {s}" for s in said)]
    if again:
        lines.append(SAID_AGAIN.format(again="; ".join(again)))
    return "\n".join(lines)


def alerts(question_judge: QuestionJudge | None) -> Cell:
    """The `context` and `alerts` reports, on the way in. Without a judge, only the ad one; a judgment that blows up is a `Fail`."""

    async def cell(seen: Log) -> Log:
        question, _ = conversation(seen)
        lines = [AD_LINE.format(ad=ad)] if (ad := ad_of(question)) else []
        reports: list[Report] = []
        fails: tuple[Fail, ...] = ()
        if question_judge is not None:
            try:
                state = await question_judge.state(seen)
                said, again = await question_judge.already(seen)
                p = await question_judge(seen, frozenset(ALERT_ASKS))
            except Exception as e:
                fails = (Fail("alerts", f"the judgment blew up: {type(e).__name__}: {e}"),)
            else:
                if state:
                    text = json.dumps(state, ensure_ascii=False, indent=1)
                    reports.append(Report(CONTEXT_WHO, text, is_grounded=True))
                if said:
                    reports.append(Report(SAID_WHO, said_text(said, again), is_grounded=True))
                lines += [ALERT_LINES[n] for n in ALERT_ASKS if p.get(n, 0.0) >= ALERT_THRESHOLD]
        if lines:
            text = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))
            reports.append(Report(ALERTS_WHO, text, is_grounded=True))
        return Log(reports=tuple(reports), fails=fails) if reports or fails else ZERO

    return cell
