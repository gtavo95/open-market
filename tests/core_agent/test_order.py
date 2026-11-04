"""The order against the catalog: what the code finds and what it leaves as `None` so as not to invent."""

from __future__ import annotations

import json

from core_agent.prompts.judge import OTHER_UNIT
from core_agent.world.order import Item, billable, choose, exact, has_quantities, order_dict, payment_args, presentations, price_order, remember, said_products

ROLLS = """# Presentations
| Size | Unit | Presentation | Base quantity | Base unit | Price | Price/unit | Currency |
|---|---|---|---|---|---|---|---|
| 1 | yellow roll 0.10 mt X 50 mt | roll | 1 | roll | 199.36 |  | GTQ |
| 1 | blue roll 0.10 mt X 50 mt | roll | 1 | roll | 199.36 |  | GTQ |
| 1 | yellow roll 0.15 mt X 50 mt | roll | 1 | roll | 224.00 |  | GTQ |

# Datasheet
"""

LITERS = """# Presentations
| Size | Unit | Price | Price/unit | Currency |
|---|---|---|---|---|
| 1 | L | 275.00 |  | GTQ |
| 20 | L | 4,650.00 |  | GTQ |
"""


GALLONS = """# Presentations
| Size | Unit | Price | Price/unit | Currency |
|---|---|---|---|---|
| 0.5 | gl | 200.00 |  | GTQ |
| 1 | gl | 350.00 |  | GTQ |
"""


def test_without_asking_only_the_single_one_or_the_exact_label() -> None:
    """The rest is chosen by the judge (`presentation_question`): the code does not read "4 liters", "jerrycan" or "1 gallon"."""
    liters, gallons = presentations(LITERS), presentations(GALLONS)
    assert exact("20 L", liters) == liters[1]
    assert exact("4 liters", liters) is None
    assert exact("1 gallon", gallons) is None
    assert exact("", liters[:1]) == liters[0], "with only one there is nothing to choose"


def test_the_table_gives_label_and_price_with_or_without_extra_columns() -> None:
    assert [(p.label, p.price) for p in presentations(LITERS)] == [("1 L", 275.0), ("20 L", 4650.0)]
    assert presentations(ROLLS)[2].label == "1 yellow roll 0.15 mt X 50 mt"


def test_the_judge_s_choice_sets_the_price_and_another_unit_marks_it() -> None:
    """reapvane-two-gallons, Sep 28, 2026: "1 gallon" of Reapvane, which comes in liters, is not the 1 L one."""
    (item,) = price_order([{"product": "Reapvane", "presentation": "liter", "quantity": 2}])

    chosen = choose(item, "1 L")
    gallon = choose(item, OTHER_UNIT)

    assert item.presentation is None and item.options and item.subtotal is None
    assert (chosen.presentation, chosen.subtotal, chosen.options) == ("1 L", 2 * chosen.unit_price, ())  # type: ignore[operator]
    assert gallon.other_unit and gallon.presentation is None
    assert choose(item, "unchosen") == item


def test_the_order_from_the_bundle_has_a_price_only_when_everything_appears() -> None:
    items = price_order([
        {"product": "Reapvane", "presentation": "1 L", "quantity": 2},
        {"product": "Stelvane", "presentation": "1 L", "quantity": 1},
        {"product": "Reapvane", "presentation": None, "quantity": None},
        "not an object",
    ])

    assert [(i.product, i.presentation, i.quantity) for i in items] == [
        ("Reapvane", "1 L", 2.0),
        (None, None, 1.0),
        ("Reapvane", None, None),
    ]
    assert items[0].subtotal == 2 * items[0].unit_price
    assert items[1].subtotal is None, "Stelvane is several datasheets: none is chosen"
    assert order_dict(items)["total"] is None, "without all the subtotals there is no total"
    assert order_dict(items[:1])["total"] == items[0].subtotal


def test_the_name_reaches_its_datasheet_by_the_exact_title_or_by_the_judge() -> None:
    """What is not an exact title is chosen by the judge (`product_question`) and arrives in `named`."""
    said = ["reapvane", "TriVX", "Stelvane", "yellow traps"]
    alone = price_order([{"product": d, "quantity": 1} for d in said])
    with_judge = price_order([{"product": d, "quantity": 1} for d in said], named={"TriVX": "Tri VX 35 EW", "Stelvane": "not a title"})

    assert [i.product for i in alone] == ["Reapvane", None, None, None]
    assert [i.product for i in with_judge] == ["Reapvane", "Tri VX 35 EW", None, None]
    assert said_products([{"product": "Reapvane"}, {"product": "Reapvane"}, "x", {"product": "Roycel"}]) == ("Reapvane", "Roycel")


def test_the_unit_stuck_to_the_quantity_stays_as_what_was_said_for_the_judge() -> None:
    (item,) = price_order([{"product": "Reapvane", "presentation": None, "quantity": "4 liters"}])

    assert (item.quantity, item.said_presentation, item.presentation) == (4.0, "liters", None)


def test_what_is_not_a_list_is_an_empty_order() -> None:
    assert price_order(None) == ()
    assert price_order("2 liters") == ()


def test_the_order_says_how_much_when_everything_sold_has_a_quantity() -> None:
    """What closes `quantity`: a "yes, they said a quantity" does not see that the second product is missing one."""
    rootvane, roycel = Item("Rootvane", "", 10.0), Item("Roycel", "", None)
    stelvane = Item("Stelvane Fe", "", None, status="discontinued")

    assert has_quantities((rootvane,))
    assert not has_quantities((rootvane, roycel))
    assert has_quantities((rootvane, stelvane)), "what is discontinued is not sold and needs no quantity"
    assert not has_quantities((stelvane,)) and not has_quantities(())


def test_it_charges_only_with_everything_priced_and_a_whole_quantity() -> None:
    two = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2}])
    half = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2.5}])
    no_datasheet = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2}, {"product": "yellow traps", "presentation": None, "quantity": 1}])

    assert billable(two)
    assert not billable(half), "the payment order counts whole units"
    assert not billable(no_datasheet), "what is not in the catalog has no price to charge"
    assert not billable(())


def test_the_link_args_are_the_order_put_there_by_code() -> None:
    items = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2}])
    args = dict(payment_args(items))

    assert json.loads(args["item"]) == {"line": 1, "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": f"{items[0].unit_price:.2f}", "subtotal": f"{items[0].subtotal:.2f}", "item_code": "PT0107"}
    assert args["currency"] == "GTQ" and args["total"] == f"{items[0].subtotal:.2f}"
    assert payment_args(price_order([{"product": "Reapvane", "presentation": None, "quantity": 2}])) == ()


def test_the_link_that_went_out_fills_the_presentation_and_quantity_compaction_lost() -> None:
    """Prod sale of Sep 28, 2026: the advisor said "Reapvane 1 L", and after the payment 2 of 3 compactions lost it."""
    link = payment_args(price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 5}]))
    no_size = price_order([{"product": "Reapvane", "presentation": None, "quantity": 5}])
    nothing = price_order([{"product": "Reapvane", "presentation": None, "quantity": None}])

    filled = remember(no_size, link)
    assert filled[0].presentation == "1 L" and filled[0].quantity == 5 and billable(filled)
    assert remember(nothing, link)[0].quantity == 5


def test_the_link_does_not_overwrite_what_the_customer_said() -> None:
    link = payment_args(price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 5}]))
    twenty = price_order([{"product": "Reapvane", "presentation": "20 L", "quantity": 1}])
    other = price_order([{"product": "Roycel", "presentation": None, "quantity": 2}])

    assert remember(twenty, link) == twenty, "they changed presentation: what they say now rules"
    assert remember(other, link) == other, "a product that was not in the link stays as it came"
    assert remember(other, ()) == other


def test_each_presentation_carries_its_sap_code_if_the_datasheet_has_it() -> None:
    with_code = "# Presentations\n| Size | Unit | Price | Currency | SAP Code |\n|---|---|---|---|---|\n| 1 | L | 250.00 | GTQ | PT0050 |\n| 20 | L | 4,650.00 | GTQ |  |\n"
    without_code = "# Presentations\n| Size | Unit | Price | Currency |\n|---|---|---|---|\n| 1 | L | 250.00 | GTQ |\n"

    assert [p.code for p in presentations(with_code)] == ["PT0050", ""]
    assert [p.code for p in presentations(without_code)] == [""]


def test_the_code_follows_the_chosen_presentation() -> None:
    [one] = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2}])
    [unchosen] = price_order([{"product": "Reapvane", "presentation": "", "quantity": 2}])

    assert one.code == "PT0107"
    assert unchosen.code == "" and choose(unchosen, "20 L").code == "PT0105"


def test_the_order_for_the_card_carries_sku_currency_and_whether_it_is_charged() -> None:
    """The host copies the order to the card without interpreting it; everything is a number, text or null."""
    items = price_order([
        {"product": "Reapvane", "presentation": "1 L", "quantity": 2},
        {"product": "yellow traps", "presentation": None, "quantity": 1},
    ])

    order = order_dict(items[:1])
    assert order["items"][0]["sku"] == "PT0107" and order["items"][0]["currency"] == "GTQ"
    assert (order["currency"], order["chargeable"]) == ("GTQ", True)

    with_other = order_dict(items)
    assert with_other["items"][1]["sku"] is None and with_other["items"][1]["currency"] is None
    assert (with_other["currency"], with_other["chargeable"]) == ("GTQ", False), "with no datasheet it is not charged, but the currency is the only one"
    assert order_dict(()) == {"items": [], "total": None, "currency": None, "chargeable": False}
