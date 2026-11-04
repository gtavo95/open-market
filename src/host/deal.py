"""The deal's cart as knowledge keeps it, and what a turn changes in it.

knowledge sends the deal's lines (`Query.deal.items`) and keeps what is returned to it
as deltas (`changes.items`): what is not mentioned does not change. The judge starts from those
lines (`QuestionJudge.cart`) and the turn's order (`Answer.order`) is how they ended up;
here the two are compared.

A line is identified by `product` and `presentation`, which are the catalog's: the
deal's lines came out of an earlier turn of this service, and `price_order` finds them
again as they are. One the catalog no longer has (the operator entered it, or the datasheet was withdrawn)
stays with what was said, and is compared by what was said. Only what can be charged enters the deal: a
line without a datasheet, a presentation or a quantity is a pending question from the advisor, not a
change.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core_agent.world.order import Item

Key = tuple[str, str]


def _key(row: dict[str, Any]) -> Key:
    return (str(row.get("product") or ""), str(row.get("presentation") or ""))


def _item_key(item: Item) -> Key:
    return (item.product or item.said_product, item.presentation or item.said_presentation)


def _billable(item: Item) -> bool:
    return bool(item.product and item.presentation and item.quantity is not None)


def _line(item: Item, sku: str | None) -> dict[str, Any]:
    return {"sku": sku, "product": item.product, "presentation": item.presentation, "quantity": item.quantity, "price": item.unit_price}


def item_changes(seed: Sequence[dict[str, Any]], order: Sequence[Item]) -> list[dict[str, Any]]:
    """The changes from `seed` (the deal's lines) to `order` (the turn's order): add, change and remove.

    `change` is another quantity on the same line; another presentation is another line, so it
    comes out as `remove` the old one and `add` the new one. The price is the datasheet's.
    """
    now = {_item_key(i): i for i in order}
    before = {_key(r): r for r in seed}
    changes: list[dict[str, Any]] = []
    for key, row in before.items():
        item = now.get(key)
        if item is None:
            changes.append({"op": "remove", "sku": row.get("sku"), "product": key[0], "presentation": key[1]})
        elif _billable(item) and item.quantity != row.get("quantity"):
            changes.append({"op": "change", **_line(item, row.get("sku"))})
    for key, item in now.items():
        if key not in before and _billable(item):
            changes.append({"op": "add", **_line(item, item.code or None)})
    return changes
