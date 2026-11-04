"""The shape: how the roles are composed, and nothing else.

    orchestrate([with_memory(recollections, searcher)], writer, before=[sale, order, effects, escalation], after=[sale, resolver, escalation])

That is the advisor. What each role asks for and closes lives in `roles/`, what the
model reads in `prompts/`, and the catalog, the judges, the envelope and the network in
`world/`. Here there is only the wiring, the turn's envelope and where the
model comes from, which is what there is to read to know what this agent is.

The two boundaries are not symmetrical: on the way in the sale closes what the
customer just said, the effects propose on that and what the
customer asks for and the advisor cannot solve escalates (`asked_handoff`); on the way out the sale
closes what the turn did, `fill_effect_args` completes the datasheet with what the
writer cited, and the escalation looks at whether the answer left the customer without what they
asked for. In between, the searcher and the writer, who do not see each other except
through the report. With customer memory seeded, the memory searcher runs before the
searcher (`memory_search` from catalejo), which brings its own report, and the
searcher reads it: "the same as last time" reaches it with the product.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from catalejo.core import Cell, EffectOp, Log, Memory, Message, PlanOp, Report, Role, then
from catalejo.llm import Claude, Gemini, Muse, OpenAI, Provider
from catalejo.rlm import Dossier, memory_search, orchestrate, paths

from .prompts.memory import MEMORY_SEARCHER, MEMORY_WHO
from .prompts.writer import PAYMENT_LINES, PAYMENT_WHO
from .roles.effects import capture_effects, fill_effect_args
from .roles.alerts import alerts
from .roles.form import Forms
from .roles.human_handoff import asked_handoff, human_handoff, sale_closed
from .roles.order import take_order
from .roles.sale import close_sale_steps
from .roles.searcher import search_catalog, with_memory
from .roles.writer import write_reply
from .world.catalog import corpus, voice
from .world.dialogue import History, wrap
from .world.trace import Span, note, observed
from .world.question_judge import QuestionJudge
from .world.recap import Recaps


def moved(seen: Log, out: Log, step: Span) -> None:
    """The trace of a stretch of the turn: what it moved in the plan and in the effects, as they came out."""
    for op in out.course:
        note("plan", f"{op.verb} {op.id}", text=op.intent)
    for effect in out.effects:
        note("effect", f"{effect.verb} {effect.id}", text=effect.note)


def judged(question_judge: QuestionJudge | None) -> Callable[[Log, Log, Span], None]:
    """The trace of the way in: what the judge read, with its numbers, and what that moved."""

    def detail(seen: Log, out: Log, step: Span) -> None:
        judgment = question_judge.read(seen) if question_judge is not None else None
        if judgment is not None:
            read = {k: v for k, v in judgment.as_dict().items() if k in ("state", "p", "labels", "error")}
            step.fill(output=json.dumps(read, ensure_ascii=False, indent=2, default=str))
        moved(seen, out, step)

    return detail


def reported(seen: Log, out: Log, step: Span) -> None:
    """The trace of the search: the report that crossed the boundary and the datasheets it cites."""
    step.fill(
        text="\n\n".join(r.text for r in out.reports),
        sources=[s for r in out.reports for s in r.sources],
    )


def build(
    model: Provider,
    *,
    question_judge: QuestionJudge | None = None,
    dossier: Dossier | None = None,
    deadline: float | None = None,
    contained: bool = False,
    form: Forms | None = None,
) -> Cell:
    """The advisor: `orchestrate([with_memory(memory_search, search_catalog)], write_reply, before=[close_sale_steps, take_order, capture_effects, asked_handoff], after=[close_sale_steps, fill_effect_args, human_handoff])`. Reads the bundle when built.

    `question_judge` is the network judge (`QuestionJudge.from_env(model)`); without it the sale
    runs with the turn's four facts and warns on every run about the five
    customer slots nobody answers, `capture_effects` about its two questions and
    `human_handoff` about its own. The host closes it, like the model. `take_order` goes after
    the sale because it reads the same judgment, and passes the order to the writer as one more
    report (`roles/order.py`). `capture_effects` goes
    after `close_sale_steps` so the judge's memory already has the turn; `fill_effect_args`
    goes at the end because it reads what the writer cited, and `human_handoff` after
    the outbound sale to read the same request on the answer. The form goes first:
    `data` closes with the complete form (`Forms.judge`), and on the turn the customer gives
    the data the sale has to see it already noted to escalate `sale_completed` on that turn
    (sale-closed:3 did not escalate in 0/2 with the form after, Oct 8, 2026).
    `deadline` is the cap of each role, not of the turn: the searcher and the
    writer each have their `loop`, and the searcher's covers its
    `SEARCH_ROUNDS` rounds together (see `search_catalog`). `contained` is the
    searcher's REPL in a child process (see `workshop`).

    The memory searcher runs before the searcher, and only if the host seeded memory
    (`has_memory`, a fact of the Log): without it, it does not run or cost anything. It answers another
    question, what we know about this customer from previous conversations, and comes out
    as the `memory` report (logbook todo #24, Oct 5, 2026), which reaches the
    writer and the searcher (`with_memory`). The two share the
    searcher's cap: memory gets half, the catalog whatever is left. Until Oct 7,
    2026 they ran in parallel, and with "I want the same as last
    time" the catalog did not know what to search for: the turn came out with no datasheet, no
    price and no order.

    `form` is the conversation's billing form (`roles/form.py`): the caller keeps it
    to read `latest` and `reset` after the turn. Without it, an empty one that lasts as long as the
    agent. It goes on the way in after the order and before the effects, because the SAP draft
    reads what it noted; the sale and the writer read it for `data`.

    Each stretch goes inside `observed`, which draws its step on the page and returns the Log as
    is. `before` and `after` are one `then` each: `then` is associative, so they run as they did
    when `orchestrate` chained them cell by cell.
    """
    catalog_text = corpus()
    dossier = dossier if dossier is not None else Dossier()
    form = form if form is not None else Forms()
    sale_steps = close_sale_steps(question_judge, form)
    def catalog_search(left: float | None) -> Cell:
        return search_catalog(catalog_text, model, dossier=dossier, deadline=left, contained=contained)

    recall = memory_search(
        model,
        MEMORY_SEARCHER,
        who=MEMORY_WHO,
        deadline=None if deadline is None else deadline / 2,
        keep=dossier.keep(MEMORY_WHO),
        contained=contained,
    )
    way_in = then(
        form.cell(model, question_judge),
        sale_closed(sale_steps),
        take_order(question_judge),
        capture_effects(question_judge, form),
        asked_handoff(question_judge),
        alerts(question_judge),
    )
    way_out = then(
        sale_steps,
        fill_effect_args(paths(catalog_text), question_judge, form),
        human_handoff(question_judge),
    )
    return orchestrate(
        [observed("searcher", "Searching the catalog", with_memory(recall, catalog_search, deadline), reported)],
        observed("writer", "Writing the answer", write_reply(catalog_text, model, voice(), deadline=deadline, question_judge=question_judge, form=form)),
        before=[observed("judge", "Reading the message", way_in, judged(question_judge))],
        after=[observed("check", "Closing the turn", way_out, moved)],
    )


async def turn(
    agent: Cell,
    question: str,
    history: History,
    course: tuple[PlanOp, ...] = (),
    effects: tuple[EffectOp, ...] = (),
    recaps: Recaps | None = None,
    payment: str = "",
    memory: Memory = (),
    closed: int | None = None,
) -> Log:
    """One question, run. The Log starts clean every time, except `course`, `effects` and `memory`.

    Only the prose of what was spoken travels, in the `dialogue.wrap` envelope the
    gates know how to take apart. `course` and `effects` are the exception: the moves
    of the sale and of the effects so far, and the Log that comes back brings only those of
    this turn, so the host adds them up, `course = (*course, *out.course)` and
    `effects = (*effects, *out.effects, *what_it_executed)`, with the `done` or the
    `reject` of each proposed one it handled. Empty on the first turn. With `recaps`
    the long answers of the history go in summarized; without it, whole.
    `payment` is the state of the payment link the host checked (`paid` or
    `pending`), and it goes in as a report for the writer (`PAYMENT_LINES`).
    `memory` is the customer's memory between sessions that the host keeps (the
    messages and the summary tree); it is seeded in the `memory` channel and the Log
    that comes back brings it empty, because the agent does not write it. `closed` is the index in `history`
    of the last turn of a closed sale: the envelope marks it (`dialogue.SOLD`) and the order, the
    gates and the form read only what follows.
    """
    if recaps is not None:
        history = await recaps(history)
    return await agent(
        Log(
            said=(Message(Role.USER, wrap(question, history, closed=closed)),),
            course=course,
            effects=effects,
            reports=(Report(PAYMENT_WHO, PAYMENT_LINES[payment], is_grounded=True),) if payment in PAYMENT_LINES else (),
            memory=memory,
        )
    )


MUSE_MODEL = "muse-wonder-1.0"
MUSE_THINKING = "medium"
OPENAI_MODEL = "gpt-6-luna"
OPENAI_THINKING = "medium"
GEMINI_THINKING = "low"
CLAUDE_MODEL = "claude-haiku-5-5"
CLAUDE_THINKING = "medium"
TIMEOUT = 40.0
"""The root model and the seconds per call; `lifespan.agent.provider` reads the same ones.

`gpt-6-luna` with `medium` since Sep 22, 2026 (round 20 of the logbook):
78/78 at n=3 and 48/48 at n=6 like `gpt-5.6-luna` with `low`, 61% cheaper and 37% slower
per turn. With `low`, gpt-6-luna regressed: it said the catalog did not cover what it does cover.
The slowest call took 21 s, so the per-call cap goes up from 25 to 40 s, below
the role's 45 with `TIMEOUT_S=90`.
"""


def provider() -> Provider:
    """Muse unless `PROVIDER` says otherwise; four retries, `TIMEOUT` per call.

    Muse runs Wonder 1.0 with `medium` (`MUSE_MODEL` and `THINKING` change them; `THINKING` is
    the same name `Settings.thinking` reads in the API). Measured on Nov 3, 2026 on the 6 demo
    turns, n=3: Wonder `medium` 16/18 correct, met 18/18, order 6/9, 45 s per turn; Wonder `low`
    16/18, met 17/18, 6/9, 39 s; Spark 1.3 contributor `low` 9/18, 17/18, 3/9, 44 s; Spark
    `medium` 8/18, 18/18, 3/9, 112 s. Not in the logbook, and low against medium is not settled
    at n=3. Every number below and in `OPENAI_MODEL` is from another provider.

    `PROVIDER=anthropic` picks Claude (Haiku 5.5 with `medium`, the model's default), not
    used in prod. Measured on Oct 7, 2026 against gpt-6-luna, 4 probes n=3
    (`haiku-5-5-root` in the logbook): with `medium` 11/12, escalated correctly 4/6 (luna 6/6) and
    USD 0.0050 per turn against ~0.0022, for double the tokens; with `low` 12/12, 4/6 and
    USD 0.0037. It escalates when the customer merely says thanks; n=3 is not enough to claim it.
    Both cost the same per token, so Haiku comes out 1.7 to 2.3 times more expensive per
    turn. The row says 0.0047 for luna because it was counted at the gpt-5.6-luna price.
    """
    chosen = os.environ.get("PROVIDER") or "muse"
    if chosen == "muse":
        return Muse(
            os.environ.get("MUSE_MODEL") or MUSE_MODEL,
            thinking=os.environ.get("THINKING") or MUSE_THINKING,
            retries=4,
            timeout=TIMEOUT,
        )
    if chosen == "anthropic":
        return Claude(CLAUDE_MODEL, thinking=CLAUDE_THINKING, retries=4, timeout=TIMEOUT)
    if chosen == "openai":
        return OpenAI(
            OPENAI_MODEL, thinking=OPENAI_THINKING, retries=4, timeout=TIMEOUT
        )
    if chosen == "gemini":
        return Gemini(thinking=GEMINI_THINKING, retries=4, timeout=TIMEOUT)
    raise ValueError(f"PROVIDER={chosen!r}: must be muse, gemini, openai or anthropic")
