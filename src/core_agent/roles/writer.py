"""The role that talks: the request built for it and what comes out of the turn.

It reads the reports with the datasheets they cited open in full, and writes. It does not
query the catalog and has no REPL.

What it costs: one call to the model, none to the judge.

It is the only role that looks at the other two: its request carries the
sale's line (`sale_line`) and the effects' line (`effect_line`). They are the only two
voices another role has here, and they go in as a line at the end, not as the
drawn plan: the writer manages nothing, it asks for the next thing missing and
says what the system is going to send.

The texts of the request, the writer's and the lines of the other two,
live in `prompts/writer.py`; here it is decided when each one goes in.
"""

from __future__ import annotations

from functools import partial

from catalejo.core import (
    Cell,
    Fail,
    Log,
    Message,
    Role,
    effects_of,
    loop,
    project,
    proposed,
    then,
)
from catalejo.llm import Provider
from catalejo.rlm import read, render_reports

from ..prompts.writer import CASE_LINES, HUMAN_LINE, MESSAGE_BREAK, NO_REPORTS, NO_SOURCES, SOURCES, WRITER, WRITER_PREAMBLE
from ..world.dialogue import by_human, conversation
from ..world.facts import answer_of
from ..world.question_judge import JudgeError, QuestionJudge
from .effects import effect_line, sent_line
from .human_handoff import ASKED_WHO
from .form import Forms
from .sale import sale_line

SEARCHER_WHO = "searcher"


def text_of_search(seen: Log) -> str:
    """What the searcher reported this turn, joined."""
    return "\n\n".join(r.text for r in seen.reports if r.who == SEARCHER_WHO)


async def case_lines(report: str, seen: Log, question_judge: QuestionJudge | None) -> list[str]:
    """The turn's case rule for the writer: one, none if it is normal, or all four with no judge or if the judgment blew up."""
    if question_judge is None:
        return list(CASE_LINES.values())
    try:
        case = await question_judge.turn_case(seen, report)
    except JudgeError:
        return list(CASE_LINES.values())
    return [CASE_LINES[case]] if case in CASE_LINES else []


def dictation(text: str, voice: str, question_judge: QuestionJudge | None = None, form: Forms | None = None) -> Cell:
    """The writer's request, built from the Log: the voice, the contract, the reports with their sources open, the sale's line and the effects' line.

    The sale goes in as a line at the end (`sale_line` over `seen.course`, already
    moved by the inbound `close_sale_steps`), not as the drawn tree: the
    writer does not manage the plan, it only asks for the next thing missing. With no sale
    in the channel there is no line, and the request is the old one. The effects go in
    the same way (`effect_line` over `seen.effects`, already proposed by `capture_effects`):
    one line per send the system will do with this message, so the
    writer says it and does not describe or transcribe it. With no proposals, nothing.
    Before that goes `sent_line`: what the host already closed on previous turns,
    with what it returned (since Sep 28, 2026). With no closed
    effects, nothing, and the request is the old one. With an `escalation` report
    the sale's line does not go: that is the advisor's last message, and "ask them for the
    next thing missing" left a question nobody answers anymore (since Sep 28,
    2026). With a judge, the sale's line does not ask again for
    what the advisor already asked for without an answer (`unanswered`, from the judge's memory;
    if the judgment blew up, it asks as before). If a person on the team
    attended the customer in between, `HUMAN_LINE` goes: their answers are not
    the writer's and what they agreed stays agreed. With `form`, the `data` leaf asks for the first required field
    the form is missing (`Forms.next_ask`), and on the turn in which the customer emptied the order
    (`Forms.reset`) the sale's line does not go: the previous sale no longer exists.
    """
    head = f"{voice}\n\n{WRITER}" if voice else WRITER

    async def cell(seen: Log) -> Log:
        body = (
            render_reports(seen.reports, partial(read, text))
            if seen.reports
            else NO_REPORTS
        )
        sources = tuple(dict.fromkeys(f for r in seen.reports for f in r.sources))
        footer = SOURCES.format(sources=", ".join(f"`{s}`" for s in sources)) if sources else NO_SOURCES
        try:
            unanswered = await question_judge.unanswered(seen) if question_judge is not None else frozenset()
        except JudgeError:
            unanswered = frozenset()
        case = await case_lines(text_of_search(seen), seen, question_judge)
        silent = any(r.who == ASKED_WHO for r in seen.reports) or (form is not None and form.reset)
        line = "" if silent else sale_line(project(seen.course), unanswered, form.next_ask() if form is not None else "")
        effects = effects_of(seen.effects)
        past = sent_line(effects)
        eff = effect_line(proposed(effects))
        human = [HUMAN_LINE] if by_human(conversation(seen)[1]) else []
        parts = [head, body, footer, *case, *human, *([line] if line else []), *([past] if past else []), *([eff] if eff else [])]
        return Log(said=(Message(Role.USER, "\n\n".join(parts)),))

    return cell


def speak(model: Provider) -> Cell:
    """A single call: the preamble plus what was said, and what it answered.

    No REPL or loop. The sums it has left (containers by price) it does in
    prose: with the REPL, the sum sometimes came out as the answer ("3 * 280.00",
    round 23) or the whole answer inside a `print`. A model that blows up
    is a `Fail`, same as in `worker`.
    """

    async def cell(seen: Log) -> Log:
        try:
            reply = await model.complete((Message(Role.SYSTEM, WRITER_PREAMBLE), *seen.said))
        except Exception as e:
            return Log(fails=(Fail("model", f"{type(e).__name__}: {e}"),))
        return Log(said=(reply.message,), spent=reply.spent)

    return cell


def write_reply(
    text: str,
    model: Provider,
    voice: str,
    *,
    deadline: float | None = None,
    question_judge: QuestionJudge | None = None,
    form: Forms | None = None,
) -> Cell:
    """The one that talks to the customer: reads the reports with their datasheets and writes, in one call.

    The one-step `loop` is there for the `deadline`: it is what cancels a hung
    provider and signs the timeout `Fail` the host reads as `truncated`.
    """
    return then(dictation(text, voice, question_judge, form), loop(speak(model), max_steps=1, deadline=deadline))


UNGROUNDED = (
    "I could not check the catalog, so I have nothing to recommend. Please ask again."
)


def messages(text: str) -> tuple[str, ...]:
    """The answer split into the WhatsApp messages the writer separated with `MESSAGE_BREAK`.

    With no separator it is a single message. Empty pieces do not come out: a `---`
    before the `SOURCE:` lines the host already removed leaves one.
    """
    parts: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.strip() == MESSAGE_BREAK:
            parts.append([])
        else:
            parts[-1].append(line)
    return tuple(p for p in ("\n".join(ls).strip() for ls in parts) if p)


def answer(out: Log) -> str:
    """The last thing the writer said in prose, unless nobody queried the catalog.

    The messages are joined by a blank line, without the separator: whoever reads
    this (the CLI, the evals) reads a single text.
    """
    if any(f.role_name == "grounding" for f in out.fails):
        return UNGROUNDED
    return "\n\n".join(messages(answer_of(out))) or "(ran out of steps before answering)"

