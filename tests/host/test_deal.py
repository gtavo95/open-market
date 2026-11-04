"""What a turn changes in the deal's cart (`host/deal.py`): deltas, by product and presentation."""

from __future__ import annotations

import pytest

from core_agent.world import catalog
from core_agent.world.order import price_order
from host.deal import item_changes

DEAL = [
    {"sku": "PT0107", "product": "Reapvane", "presentation": "1 L", "quantity": 2.0, "price": 275.0},
    {"sku": None, "product": "Roycel", "presentation": "1 L", "quantity": 3.0, "price": 150.0},
]


@pytest.fixture(autouse=True)
def repo_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "BUNDLE", catalog.CATALOG)


def order(*rows: tuple[str, str | None, float | None]) -> tuple:
    return price_order([{"product": p, "presentation": s, "quantity": c} for p, s, c in rows])


def test_what_did_not_change_does_not_go_out_even_if_the_catalog_lacks_it() -> None:
    assert item_changes(DEAL, order(("Reapvane", "1 L", 2), ("Roycel", "1 L", 3))) == []


def test_another_quantity_is_change_with_the_datasheet_price() -> None:
    assert item_changes(DEAL, order(("Reapvane", "1 L", 5), ("Roycel", "1 L", 3))) == [
        {"op": "change", "sku": "PT0107", "product": "Reapvane", "presentation": "1 L", "quantity": 5.0, "price": 275.0}
    ]


def test_what_is_gone_is_remove_and_what_is_new_add() -> None:
    assert item_changes(DEAL, order(("Reapvane", "20 L", 1))) == [
        {"op": "remove", "sku": "PT0107", "product": "Reapvane", "presentation": "1 L"},
        {"op": "remove", "sku": None, "product": "Roycel", "presentation": "1 L"},
        {"op": "add", "sku": "PT0105", "product": "Reapvane", "presentation": "20 L", "quantity": 1.0, "price": 4650.0},
    ]


def test_what_cannot_be_charged_yet_does_not_go_in() -> None:
    out = item_changes([], order(("Reapvane", None, 2), ("Roycel", "1 L", 1), ("Brimsol", "1 L", None)))

    assert out == []
