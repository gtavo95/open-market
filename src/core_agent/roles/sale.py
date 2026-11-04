"""The role that talks to nobody: the plan that lasts the conversation, what closes it and what it asks for.

It is a `planner` with no voice over the `course` channel: `seed` seeds `SESSION` on the
first turn and `close_steps` closes by judgment what happened. It runs twice per
turn, at both boundaries, and its only voice is the line the writer reads
(`sale_line`).

What it costs: no call to the model. One request to the judge per turn, shared
with the effects: the second run comes out of the turn's memory.

The file's order: first the table (`SESSION`), then the readings of the
plan, and at the end the cell. What the writer ends up reading from the sale
(`ASKS`, `ANSWER`, `SALE_LINE`) lives in `prompts/writer.py`.
"""

from __future__ import annotations

from catalejo.core import (
    Cell,
    Plan,
    Step,
    active,
    children,
    closed,
    find_step,
    outline,
    pending,
    stage,
    step,
)
from catalejo.rlm import planner

from ..prompts.judge import RECOMMENDED
from ..prompts.writer import ANSWER, ASKS, FOUND, SALE_ASKED, SALE_LINE, SEARCHING
from ..world.question_judge import THRESHOLD, QuestionJudge, judge
from .form import BILLED, Forms

SEARCHABLE = "has_search_terms"
"""The condition that opens the advisor's work: the customer already said something traceable.

It has a name because two distant places depend on it and are linked by the
closing condition and not by the step's id: `nothing_to_search` looks at whether the
leaf that closes with this is still open, and `question_judge.SALE_QUESTIONS` answers it.
"""

SESSION = outline(
    stage("diagnosis", "diagnose and build the cart",
        step("pest", "find out what they are looking for: the pest, or the product they already have in mind", done_when=SEARCHABLE),
        step("product", "one that works for that pest", done_when=RECOMMENDED),
        step("recipe", "the dose as the datasheet gives it", done_when="opens_a_datasheet"),
        step("quantity", "how many liters or containers of the product they want", done_when="order_with_quantities"),
        step("decision", "whether they want it: answer what they ask until they say they will buy it", done_when="wants_to_buy"),
    ),
    stage("payment", "charge",
        step("method", "which of the two ways: payment link or transfer", done_when="said_payment_method"),
        step("charge", "give them the link, or the account of the company that collects"),
    ),
    stage("billing", "the billing details",
        step("data", "NIT, who receives, their phone and the delivery address", done_when=BILLED),
    ),
)
"""The sale's plan: three stages with their parts, and on each leaf what closes it.

It goes in the `course` channel and lasts the conversation: the host seeds it each
turn with the moves so far and takes away those of this turn (`turn`). Each
`done_when` is a name `close_steps` asks the judge in
`world/question_judge.py`: `recipe` with a fact of the turn (`LOG_FACTS`), `quantity`
with the order (`ORDER_GATES`: everything sold has a quantity), four with
judgments on what the customer said (`SALE_QUESTIONS`) and `product` with a judgment
on what the advisor answered (`REPLY_QUESTIONS`): it closes in the sale
in `after`, when the writer has already written, and that is why the turn on which it
recommends still asks for the quantity conditionally (`sale_line`). `data` closes with the form
(`complete_invoice`, `roles/form.py`) since Oct 8, 2026; plans seeded before
close it with `said_billing_data`, which the judge keeps answering. `charge` has no
gate: the fact of charging closes it, which does not exist yet, so today it
stays open.

`pest` closes with anything that can be searched with, whether it is in the
catalog or not: half of the real questions open with a product, and closing only
with the pest turned them into an interrogation (11/11 -> 5/11 in the
`old/` suite). No `requires`: the sale does not derive steps per turn, the searcher searches for
what the question asks. The only turn checklist is its own (`SEARCH_PLAN`),
in `steps`, and it does not leave its boundary.
"""

def ask_next(plan: Plan) -> Step | None:
    """The next thing to ask the customer for, or nothing if no information of theirs is missing.

    The first pending leaf that falls to the customer, skipping those the
    advisor closes: when they name a product what follows is reading the datasheet, and that is not
    asked.
    """
    return next((s for s in pending(plan) if s.id in ASKS), None)


def nothing_to_search(plan: Plan) -> bool:
    """Whether the conversation has not yet given any term to query the catalog with.

    It is the turn in which the answer is a question. It looks at the closing condition
    and not the id (see `SEARCHABLE`). On an empty plan it is false. Until Sep 20,
    2026 it also switched off the searcher, with the judge sure there was
    nothing to search with; today the searcher runs every turn and this only
    decides the writer's line (`sale_line`).
    """
    return any(s.done_when == SEARCHABLE for s in pending(plan))


def sale_line(sale: Plan, unanswered: frozenset[str] = frozenset(), data_ask: str = "") -> str:
    """The only voice the sale has in the writer's request, or empty.

    One thing per turn and nothing else: `SALE_LINE` with the next leaf. With nothing
    to search it returns empty: `WRITER` already asks that question, and "answer what
    they asked, in full" there pushes it to list everything certified. With
    `product` pending it asks for the quantity conditionally (`SEARCHING`). If the
    advisor already asked for that leaf and the customer did not answer it (`unanswered`, from the
    judge), it says not to ask again (`SALE_ASKED`). On `data`, with `data_ask` (what the
    form says is missing, `Forms.next_ask`) it asks for that and not all the data together.
    """
    sheet = ask_next(sale)
    if sheet is None or nothing_to_search(sale):
        return ""
    ask = data_ask if sheet.id == "data" and data_ask else ASKS[sheet.id]
    if sheet.id in unanswered:
        return SALE_ASKED.format(answer=ANSWER, ask=ask)
    product = find_step(sale, "product")
    searching = product is not None and not closed(sale, product)
    return SALE_LINE.format(answer=ANSWER, when=SEARCHING if searching else FOUND, ask=ask)


def sale_state(plan: Plan) -> str:
    """One line for the terminal: how many leaves the sale closed and which one is next."""
    leaves = [s for s in plan if not children(plan, s.id)]
    done = sum(closed(plan, s) for s in leaves)
    sheet = active(plan)
    return f"sale {done}/{len(leaves)}: {f'next `{sheet.id}`' if sheet else 'closed'}"


def close_sale_steps(question_judge: QuestionJudge | None, form: Forms | None = None) -> Cell:
    """The sale at the turn's boundary: a `planner` with no voice over `course`, which seeds and closes by judgment.

    It goes twice in `orchestrate`: on the way in it closes what the customer just
    said, which the searcher and the writer need; on the way out it closes what the
    turn did (it queried, opened a datasheet, read the payment methods). The judge
    memoizes the turn, so the second time does not go back to the network. No voice because
    the sale does not command the turn: it can stay open at the end and that is
    normal, and its only voice is the line the writer reads (`sale_line`). `form` answers
    `complete_invoice`; without it, an empty one, and `data` does not close.
    """
    more = ((form if form is not None else Forms()).judge(),)
    return planner(judge(question_judge, *more), seed_ops=SESSION, channel="course", umbral=THRESHOLD)
