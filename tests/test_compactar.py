"""`POST /compactar`: the compactor of `/compaction` in the Spanish contract of the host.

The work is the same; what is held here is the edge: `{memoria, max}` in, `{nodos, fallidos, pendientes,
tokens, ...}` out, the memory kinds in the host's words on the way in, and the same gate and 503.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

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


def long_messages(n: int) -> list[dict[str, Any]]:
    return [{"i": i, "kind": "cliente" if i % 2 == 0 else "asesor", "text": f"mensaje {i} " + "x" * 600} for i in range(n)]


@pytest.fixture
def customer() -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)  # type: ignore[call-arg]
    app.state.compactor = None
    app.state.advisor_error = ""
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_the_nodes_come_out_in_spanish_keys(customer: TestClient) -> None:
    model = Echo()
    app.state.compactor = model

    r = customer.post("/compactar", json={"memoria": {"mensajes": long_messages(2), "arbol": []}})

    assert r.status_code == 200
    body = r.json()
    assert list(body) == ["nodos", "fallidos", "pendientes", "tokens", "tokens_entrada", "tokens_cacheados", "tokens_salida", "segundos"]
    assert [(n["l"], n["i"]) for n in body["nodos"]] == [(0, 0), (0, 1), (1, 0)]
    assert body["pendientes"] == 0 and body["fallidos"] == []
    assert body["tokens"] == 21 and body["tokens_entrada"] == body["tokens_salida"] == 0
    assert model.conversations[0][0].text == COMPACTOR


def test_the_kinds_of_the_memory_are_the_hosts_and_the_compactor_reads_them_in_english(customer: TestClient) -> None:
    model = Echo()
    app.state.compactor = model
    kinds = ["cliente", "asesor", "operador", "sistema"]
    messages = [{"i": i, "kind": kind, "text": f"mensaje{i} " + "x" * 600} for i, kind in enumerate(kinds)]

    r = customer.post("/compactar", json={"memoria": {"mensajes": messages, "arbol": []}})

    assert r.status_code == 200
    asked = "\n".join(m.text for conv in model.conversations for m in conv)
    for i, english in enumerate(["customer", "advisor", "operator", "system"]):
        assert f"{english}: mensaje{i} " in asked, "the line the compactor reads says who spoke, in the interior's words"
    assert not any(f"{spanish}: mensaje" in asked for spanish in kinds)


def test_with_a_cap_says_how_many_are_left(customer: TestClient) -> None:
    app.state.compactor = Echo()

    r = customer.post("/compactar", json={"memoria": {"mensajes": long_messages(2), "arbol": []}, "max": 1})

    assert [(n["l"], n["i"]) for n in r.json()["nodos"]] == [(0, 0)]
    assert r.json()["pendientes"] == 1


def test_what_is_already_built_is_not_asked_for_again(customer: TestClient) -> None:
    model = Echo()
    app.state.compactor = model
    tree = [{"l": 0, "i": 0, "text": "a" * 300}, {"l": 0, "i": 1, "text": "b" * 300}, {"l": 1, "i": 0, "text": "ab"}]

    r = customer.post("/compactar", json={"memoria": {"mensajes": long_messages(2), "arbol": tree}})

    assert r.json()["nodos"] == []
    assert model.conversations == []


def test_it_is_the_same_work_as_compaction(customer: TestClient) -> None:
    """The same memory in each tongue builds the same nodes."""
    app.state.compactor = Echo()
    english = [{**m, "kind": {"cliente": "customer", "asesor": "advisor"}[m["kind"]]} for m in long_messages(2)]

    plain = customer.post("/compaction", json={"memory": {"messages": english, "tree": []}}).json()
    app.state.compactor = Echo()
    spanish = customer.post("/compactar", json={"memoria": {"mensajes": long_messages(2), "arbol": []}}).json()

    assert spanish["nodos"] == plain["nodes"]
    assert (spanish["pendientes"], spanish["tokens"]) == (plain["pending"], plain["tokens"])


def test_without_compactor_is_503(customer: TestClient) -> None:
    app.state.advisor_error = "missing OPENAI_API_KEY"

    r = customer.post("/compactar", json={"memoria": {"mensajes": [], "arbol": []}})

    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


@pytest.mark.parametrize("body", [{}, {"memoria": "no"}, {"memoria": {"mensajes": [{"i": 0}], "arbol": []}}, {"memoria": {"mensajes": [], "arbol": []}, "max": "many"}])
def test_a_body_the_interior_refuses_is_a_422(customer: TestClient, body: dict[str, Any]) -> None:
    app.state.compactor = Echo()

    r = customer.post("/compactar", json=body)

    assert r.status_code == 422
    assert not any("input" in e for e in r.json()["detail"])


def test_a_body_that_is_not_an_object_is_a_422(customer: TestClient) -> None:
    app.state.compactor = Echo()

    assert customer.post("/compactar", json=["no"]).status_code == 422
