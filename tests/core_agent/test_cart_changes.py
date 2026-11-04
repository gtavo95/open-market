"""The cart of a deal (`QuestionJudge.cart`): it starts from what is recorded and the model writes only the changes."""

from __future__ import annotations

import json
from typing import Any

import pytest
from catalejo.core import Conversation, Log, Message, Role
from catalejo.llm import Reply

from core_agent.prompts.judge import CART_CHANGES_PROMPT, CART_EMPTY, CART_PROMPT
from core_agent.world import catalog
from core_agent.world.dialogue import wrap
from core_agent.world.question_judge import QuestionJudge, apply_cart, cart_lines
from tests.doubles import Echo, ScriptedJudge

RECORDED = [{"product": "Reapvane", "presentation": "1 L", "quantity": 2.0, "sku": "PT0107"}, {"product": "Brimsol", "presentation": "1 L", "quantity": 3.0}]
HEAD = CART_CHANGES_PROMPT[: CART_CHANGES_PROMPT.index("{cart}")]


@pytest.fixture(autouse=True)
def repo_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "BUNDLE", catalog.CATALOG)


class Changes(Echo):
    """The model that answers `CART_CHANGES_PROMPT` with some fixed changes, and everything else like `Echo`."""

    def __init__(self, changes: list[dict[str, Any]]) -> None:
        super().__init__()
        self.changes = changes
        self.cart_calls: list[Conversation] = []

    async def complete(self, conv: Conversation) -> Reply:
        if conv[-1].text.startswith(HEAD):
            self.cart_calls.append(conv)
            return Reply(Message(Role.ASSISTANT, json.dumps({"changes": self.changes})), spent=7)
        return await super().complete(conv)


def envelope(question: str) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, (("I want 2 of Reapvane", "done"),))),))


class TestTheChanges:
    def test_what_is_recorded_goes_numbered(self) -> None:
        assert cart_lines(RECORDED) == "1. Reapvane · 1 L · 2\n2. Brimsol · 1 L · 3"
        assert cart_lines([]) == CART_EMPTY

    def test_add_change_and_remove_by_number(self) -> None:
        out = apply_cart(
            RECORDED,
            [
                {"op": "change", "line": 1, "presentation": None, "quantity": 5},
                {"op": "remove", "line": 2},
                {"op": "add", "product": "Brimnitro", "presentation": "1 L", "quantity": 1},
            ],
        )

        assert out == [
            {"product": "Reapvane", "presentation": "1 L", "quantity": 5},
            {"product": "Brimnitro", "presentation": "1 L", "quantity": 1},
        ]

    def test_what_is_not_named_stays_and_what_has_no_shape_moves_nothing(self) -> None:
        out = apply_cart(RECORDED, [{"op": "remove", "line": 9}, {"op": "remove", "line": True}, {"op": "change"}, "x", {"op": "add"}])

        assert out == [{k: r[k] for k in ("product", "presentation", "quantity")} for r in RECORDED]
        assert apply_cart(RECORDED, None) == apply_cart(RECORDED, [])


class TestTheJudgeWithADeal:
    async def test_the_order_is_what_is_recorded_with_the_changes(self) -> None:
        model = Changes([{"op": "remove", "line": 2}])
        judge = QuestionJudge(ScriptedJudge(), model, cart=RECORDED)

        order = await judge.order(envelope("take out the Brimsol"))

        assert [(i.product, i.presentation, i.quantity) for i in order] == [("Reapvane", "1 L", 2.0)]
        (conv,) = model.cart_calls
        assert "1. Reapvane · 1 L · 2\n2. Brimsol · 1 L · 3" in conv[-1].text

    async def test_without_a_deal_the_cart_is_the_usual_one(self) -> None:
        model = Changes([])
        await QuestionJudge(ScriptedJudge(), model).order(envelope("hello"))

        assert model.cart_calls == []
        assert any(c[-1].text.startswith(CART_PROMPT) for c in model.conversations)

    async def test_the_judge_of_the_query_carries_its_cart(self) -> None:
        judge = QuestionJudge(ScriptedJudge(), Echo())

        assert judge.fresh(cart=RECORDED).cart == RECORDED and judge.fresh().cart is None
