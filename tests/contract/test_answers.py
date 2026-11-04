"""What `/queries` returns to the host, pinned in `answers/*.json` so the host can test it.

Each case goes through the real path and serializers (`AnswerOut`, `Judgment.as_dict`,
`payment_link` with `payment_args`, `changes` with `item_changes`); the only fake thing is the advisor,
which returns an `Answer` built with the agent's types. The host copies them with its sync
script and runs them through `TurnAnswerer` up to `chat.turns` and `chat.orders` against the Mongo validator:
that is where the two errors of Oct 8, 2026 were (`restarted` and `items` as null).

Without `DEMO_CONTRACT=update` the test fails if an answer changed and its file did not: the contract
change is committed on purpose and the host is told. With it, they are rewritten.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from catalejo.core import EffectOp, PlanOp
from fastapi.testclient import TestClient

import core_agent
from config import Settings, get_settings
from core_agent.prompts.judge import ASKS_RESET
from core_agent.roles.human_handoff import HANDOFF, ORIGIN
from core_agent.world import catalog
from core_agent.world.order import Item, payment_args, price_order
from core_agent.world.question_judge import Judgment
from host import Answer
from main import app

ANSWERS = Path(__file__).parent / "answers"
UPDATE = os.environ.get("DEMO_CONTRACT") == "update"

SALE = (*core_agent.SESSION, PlanOp("mark", "pest", status="done"), PlanOp("mark", "product", status="done"))
P = {"has_search_terms": 0.95, "said_quantity": 0.9, "wants_to_buy": 0.85, "said_payment_method": 0.04, "said_billing_data": 0.04}
DEAL: dict[str, Any] = {
    "id": "6650f0c2a1b2c3d4e5f60718",
    "kind": "sale",
    "stage": "open",
    "version": 3,
    "number": 12,
    "from_turn": None,
    "items": [],
    "total": None,
    "currency": "GTQ",
    "form": {"fields": {"nit": "CF"}, "missing": ["address"]},
    "payment": None,
    "quote": None,
    "effects": [],
    "opened_at": "2026-10-08T10:00:00Z",
    "updated_at": "2026-10-08T10:05:00Z",
}
NOTED = [
    {"sku": "PT0107", "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": 275.0, "subtotal": 550.0},
    {"sku": "PT0011", "product": "Brimsol", "presentation": "1 L", "quantity": 3, "price": 250.0, "subtotal": 750.0},
]


@pytest.fixture(autouse=True)
def repo_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "BUNDLE", catalog.CATALOG)


@pytest.fixture
def customer() -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(timeout_s=9, public_url="", _env_file=None)  # type: ignore[call-arg]
    app.state.advisor_error = ""
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.state.advisor = None


class Advisor:
    """The fake advisor: it always answers the same `Answer`."""

    sheets, text, free = 2, "x" * 8000, 1

    def __init__(self, answer: Answer) -> None:
        self.answer = answer

    async def ask(self, *_: Any, **__: Any) -> Answer:
        return self.answer


def order(*rows: tuple[str, str | None, float | None]) -> tuple[Item, ...]:
    return price_order([{"product": p, "presentation": s, "quantity": c} for p, s, c in rows])


def judgment(order: tuple[Item, ...] = (), p: dict[str, float] = P, labels: dict[str, str] | None = None) -> dict[str, Any]:
    return Judgment(state={"pest": "thrips", "crop": "tomato"}, p=p, labels=labels or {}, order=order).as_dict()


def answering(text: str, **kw: Any) -> Answer:
    base: dict[str, Any] = {"form": {"nit": "CF"}, "tokens": 1200, "tokens_input": 1000, "tokens_cached": 600, "tokens_output": 200, "seconds": 12.5, "sale": SALE}
    return Answer(text, kw.pop("sources", ("products/reapvane.md",)), True, turns=4, halt=False, fails=(), **{**base, **kw})


def cases() -> dict[str, tuple[dict[str, Any], Answer]]:
    cart = order(("Reapvane", "1 L", 2), ("Reapvane", "20 L", 1))
    changed = order(("Reapvane", "1 L", 5), ("Brimnitro", "1 L", 1))
    link = (EffectOp("propose", "send_payment_link", "payment_link"), EffectOp("resolve", "send_payment_link", args=payment_args(cart)))
    no_price = order(("Reapvane", None, 2))
    return {
        "simple_answer": (
            {"question": "what do I use for thrips on tomato?"},
            answering("For thrips on tomato, Reapvane at 1 L/ha.", judgment=judgment(p={"has_search_terms": 0.95}), form={}),
        ),
        "sale_with_cart": (
            {"question": "I want 2 liters of Reapvane and a 20 L jerrycan", "deal": DEAL},
            answering("I'll prepare 2 containers of 1 L (Q550) and 1 jerrycan of 20 L (Q4,650): Q5,200.", judgment=judgment(cart), order=cart),
        ),
        "restart_turn": (
            {"question": "let's start over instead", "deal": {**DEAL, "items": NOTED, "total": 1300.0}},
            answering("Done, we start over. What product are you looking for?", sources=(), judgment=judgment(p={**P, ASKS_RESET: 0.95}), order=(), reset=True, form={}),
        ),
        "changes_with_form": (
            {"question": "make it 5 of Reapvane, remove the Brimsol, add a Brimnitro; NIT 1234567-8, under Agro SA", "deal": {**DEAL, "items": NOTED, "total": 1300.0}},
            answering(
                "That leaves 5 of Reapvane (Q1,375) and 1 Brimnitro (Q250): Q1,625. I noted the NIT and the legal name.",
                judgment=judgment(changed),
                order=changed,
                form={"nit": "1234567-8", "legal_name": "Agro SA"},
            ),
        ),
        "payment_link": (
            {"question": "pay with link", "deal": {**DEAL, "items": NOTED[:1], "total": 550.0}},
            answering("I'm sending you the payment link for Q5,200.", sources=(), judgment=judgment(cart, labels={"payment_method": "link"}), order=cart, effects=link),
        ),
        "handoff": (
            {"question": "I want to talk to a person"},
            answering(
                "I'm passing you to a person on our team through this same chat.",
                sources=(),
                judgment=judgment(),
                form={},
                effects=(EffectOp("propose", HANDOFF, HANDOFF, (ORIGIN, ("reason", "asks_for_human"))),),
            ),
        ),
        "line_without_price": (
            {"question": "I want 2 of Reapvane", "deal": DEAL},
            answering("1 L or 20 L?", judgment=judgment(no_price), order=no_price),
        ),
    }


@pytest.mark.parametrize("case", sorted(cases()))
def test_the_answer_is_the_contract_one(customer: TestClient, case: str) -> None:
    body, answer = cases()[case]
    app.state.advisor = Advisor(answer)

    r = customer.post("/queries", json=body)

    assert r.status_code == 200
    out = json.dumps(r.json(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path = ANSWERS / f"{case}.json"
    if UPDATE:
        ANSWERS.mkdir(exist_ok=True)
        path.write_text(out, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == out, f"{path.name} changed: DEMO_CONTRACT=update, commit it and tell the host"
