"""The role that keeps the order: no model and no REPL, one more report for the writer.

    orchestrate([searcher], writer, before=[sale, order, effects], after=[...])

It reads the order from the turn's judgment, the same one that closes the sale (the compaction's
`cart`, set against the catalog in `world/order.py`), and comes out through
the boundary like the searcher: a `Report` signed `order`, with the lines and the
total. No sources, because the searcher already opens the datasheets and the price is already
on the line.

What it costs: nothing not already paid. The sale in `before` requested the judgment,
and if the sale had no open gates, `QuestionJudge.order` compacts
all the same: that is the only new call, and only in sales with closed steps.

Without a judge, or with the judge down, there is no report and the turn goes on: the sale already
notes the failure, and a missing order changes nothing for the writer.
"""

from __future__ import annotations

from catalejo.core import Cell, Log, Report

from ..prompts.writer import ORDER_HEAD, ORDER_ITEM, ORDER_NO_PRESENTATION, ORDER_OTHER_UNIT, ORDER_NO_QUANTITY, ORDER_RETIRED, ORDER_TOTAL
from ..world.order import Item
from ..world.question_judge import JudgeError, QuestionJudge

WHO = "order"


def money(value: float) -> str:
    return f"{value:,.2f}"


def amount(value: float) -> str:
    return f"{value:g}"


def order_text(items: tuple[Item, ...]) -> str:
    """The order's report in prose, or empty if there is nothing from the catalog in it."""
    lines = []
    for i in items:
        if i.product is None:
            continue
        if not i.sold:
            lines.append(ORDER_RETIRED.format(product=i.product))
        elif i.quantity is None:
            lines.append(ORDER_NO_QUANTITY.format(product=i.product))
        elif i.subtotal is None and i.other_unit:
            lines.append(ORDER_OTHER_UNIT.format(quantity=amount(i.quantity), product=i.product, said=i.said_presentation, options=", ".join(i.options)))
        elif i.subtotal is None:
            lines.append(ORDER_NO_PRESENTATION.format(quantity=amount(i.quantity), product=i.product, options=", ".join(i.options) or "the datasheet has no prices"))
        else:
            lines.append(ORDER_ITEM.format(quantity=amount(i.quantity), product=i.product, presentation=i.presentation, price=money(i.unit_price or 0.0), subtotal=money(i.subtotal)))
    if not lines:
        return ""
    priced = [i.subtotal for i in items if i.product is not None and i.sold]
    if priced and None not in priced:
        lines.append(ORDER_TOTAL.format(total=money(sum(s for s in priced if s is not None))))
    return "\n".join([ORDER_HEAD, *lines])


def take_order(question_judge: QuestionJudge | None) -> Cell:
    """The turn's order as a report signed `order`, or nothing if there is no order or no judge."""

    async def cell(seen: Log) -> Log:
        if question_judge is None:
            return Log()
        try:
            items = await question_judge.order(seen)
        except JudgeError:
            return Log()
        text = order_text(items)
        if not text:
            return Log()
        return Log(reports=(Report(WHO, text, is_grounded=True),))

    return cell
