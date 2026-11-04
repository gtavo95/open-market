"""The order cell: what report it leaves for the writer, and when it leaves nothing."""

from __future__ import annotations

from core_agent.prompts.judge import CART
from core_agent.roles.order import WHO, order_text, take_order
from core_agent.world.dialogue import wrap
from core_agent.world.order import Item
from core_agent.world.question_judge import QuestionJudge
from catalejo.core import Log, Message, Role
from tests.doubles import Echo, Said, ScriptedJudge


def envelope(question: str) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, ())),))


def test_the_report_carries_lines_with_price_and_the_total_only_if_all_have_it() -> None:
    roycel = Item("Roycel", "1 L", 2.0, product="Roycel 25 EW", presentation="1 L", unit_price=250.0)
    rootvane = Item("Rootvane", "", 3.0, product="Rootvane", options=("1 L", "20 L"))

    complete = order_text((roycel,))
    partial = order_text((roycel, rootvane))

    assert "- 2 × Roycel 25 EW, 1 L: Q250.00 each, Q500.00" in complete
    assert "Products total: Q500.00" in complete
    assert "- 3 × Rootvane: the presentation is missing (1 L, 20 L)" in partial
    assert "Products total" not in partial


def test_what_is_discontinued_is_said_and_does_not_add_and_what_is_not_in_the_catalog_does_not_go_in() -> None:
    items = (
        Item("Stelvane Fe", "1 L", 1.0, product="Stelvane Fe", status="discontinued"),
        Item("Reapvane", "1 L", 1.0, product="Reapvane", presentation="1 L", unit_price=275.0),
        Item("yellow traps", "", 10.0),
    )

    text = order_text(items)

    assert "- Stelvane Fe: we no longer have it" in text
    assert "Products total: Q275.00" in text
    assert "traps" not in text
    assert order_text((items[2],)) == "", "with nothing from the catalog there is no report"


async def test_the_cell_signs_the_report_and_it_comes_from_the_turn_judgment() -> None:
    cart = [{"product": "Reapvane", "presentation": "1 L", "quantity": 2}]
    question_judge = QuestionJudge(ScriptedJudge(), Said({"order": "2 liters of Reapvane", CART: cart}))

    out = await take_order(question_judge)(envelope("I want 2 liters of Reapvane"))

    (report,) = out.reports
    assert report.who == WHO and report.is_grounded and report.sources == ()
    assert "2 × Reapvane, 1 L" in report.text


async def test_without_a_judge_or_with_the_judge_down_there_is_no_report() -> None:
    assert await take_order(None)(envelope("I want 2 liters of Reapvane")) == Log()
    down = QuestionJudge(ScriptedJudge(down=True), Echo())
    assert await take_order(down)(envelope("I want 2 liters of Reapvane")) == Log()


async def test_it_compacts_even_if_the_sale_asked_nothing_and_only_once() -> None:
    model = Said({CART: [{"product": "Reapvane", "presentation": "1 L", "quantity": 1}]})
    question_judge = QuestionJudge(ScriptedJudge(), model)
    seen = envelope("one of Reapvane")

    await question_judge.order(seen)
    await question_judge(seen, frozenset({"said_quantity"}))

    assert len(model.conversations) == 2


def test_a_unit_the_datasheet_does_not_have_is_said_with_what_they_asked_for() -> None:
    """The unit it does not have is read by the judge (`OTHER_UNIT`) and arrives marked on the line."""
    gallons = Item("Reapvane", "1 gallon", 2.0, product="Reapvane", options=("1 L", "20 L", "1000 L"), other_unit=True)
    tie = Item("Rootvane", "1 L", 2.0, product="Rootvane", options=("1 L", "20 L"))

    assert "- Reapvane: they asked for 2 × 1 gallon, which is not a presentation in the datasheet (1 L, 20 L, 1000 L)" in order_text((gallons,))
    assert "- 2 × Rootvane: the presentation is missing (1 L, 20 L)" in order_text((tie,)), "without the judge's mark it is not another unit"
