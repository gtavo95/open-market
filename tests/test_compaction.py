"""`POST /compaction`: the memory comes in, the new nodes go out, and nothing is kept here."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from catalejo.core import Conversation, Message, Role
from catalejo.llm import Reply
from fastapi.testclient import TestClient

from config import Settings, get_settings
from core_agent.prompts.memory import COMPACTOR
from main import app


class Echo:
    """Answers a 300-byte line per call: two do not fit together and the parent gets built."""

    def __init__(self) -> None:
        self.conversations: list[Conversation] = []

    async def complete(self, conv: Conversation) -> Reply:
        self.conversations.append(conv)
        return Reply(Message(Role.ASSISTANT, f"summary {len(self.conversations)} ".ljust(300, "r")), spent=7)


def long_messages(n: int) -> list[dict[str, object]]:
    return [{"i": i, "kind": "customer", "text": f"message {i} " + "x" * 600} for i in range(n)]


@pytest.fixture
def customer() -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)  # type: ignore[call-arg]
    app.state.compactor = None
    app.state.advisor_error = ""
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_builds_the_tree_and_says_nothing_is_left(customer: TestClient) -> None:
    model = Echo()
    app.state.compactor = model

    r = customer.post("/compaction", json={"memory": {"messages": long_messages(2), "tree": []}})

    assert r.status_code == 200
    body = r.json()
    assert [(n["l"], n["i"]) for n in body["nodes"]] == [(0, 0), (0, 1), (1, 0)]
    assert body["pending"] == 0
    assert body["failed"] == []
    assert body["tokens"] == 21, "without the adapter's count, the `spent` of each call"
    assert body["tokens_input"] == body["tokens_output"] == 0
    assert model.conversations[0][0].text == COMPACTOR


def test_with_a_cap_says_how_many_are_left(customer: TestClient) -> None:
    app.state.compactor = Echo()

    r = customer.post("/compaction", json={"memory": {"messages": long_messages(2), "tree": []}, "max": 1})

    assert [(n["l"], n["i"]) for n in r.json()["nodes"]] == [(0, 0)]
    assert r.json()["pending"] == 1


def test_what_is_already_built_is_not_asked_for_again(customer: TestClient) -> None:
    model = Echo()
    app.state.compactor = model
    tree = [{"l": 0, "i": 0, "text": "a" * 300}, {"l": 0, "i": 1, "text": "b" * 300}, {"l": 1, "i": 0, "text": "ab"}]

    r = customer.post("/compaction", json={"memory": {"messages": long_messages(2), "tree": tree}})

    assert r.json()["nodes"] == []
    assert model.conversations == []


def test_without_compactor_is_503(customer: TestClient) -> None:
    app.state.advisor_error = "missing OPENAI_API_KEY"

    r = customer.post("/compaction", json={"memory": {"messages": [], "tree": []}})

    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_the_prompt_carries_the_host_kinds() -> None:
    assert "customer (the customer's words)" in COMPACTOR
    assert "{" not in COMPACTOR
