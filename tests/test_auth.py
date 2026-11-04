"""The OIDC gate: what happens with each token, against a fake OIDC (`httpx.MockTransport`)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from auth import Gate, gate
from main import app

ISSUER = "https://oidc.example"
PROTECTED = "/queries/catalog"
NO_ADVISOR = "the advisor is not built"


class OIDC:
    """Answers the introspection with whatever `answer` says and notes each request."""

    def __init__(self, answer: Callable[[httpx.Request], httpx.Response]) -> None:
        self.answer = answer
        self.orders: list[dict[str, list[str]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{ISSUER}/oidc/token/introspection"
        self.orders.append(parse_qs(request.content.decode()))
        return self.answer(request)


def active(client_id: str) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _: httpx.Response(200, json={"active": True, "client_id": client_id, "sub": client_id})


def with_gate(p: Gate) -> TestClient:
    app.dependency_overrides[gate] = lambda: p
    app.state.advisor = None
    app.state.advisor_error = ""
    return TestClient(app)


def built(oidc: OIDC | None = None, *, allowed: str = "knowledge", issuer: str = ISSUER, secret: str = "s3cr3t", on_cloud_run: bool = True) -> Gate:
    return Gate(
        issuer=issuer,
        secret=secret,
        allowed=frozenset(c for c in allowed.split(",") if c),
        on_cloud_run=on_cloud_run,
        transport=httpx.MockTransport(oidc) if oidc else None,
    )


@pytest.fixture(autouse=True)
def clean() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def test_without_issuer_in_dev_the_gate_is_open() -> None:
    r = with_gate(built(issuer="", on_cloud_run=False)).get(PROTECTED)
    assert (r.status_code, r.json()["detail"]) == (503, NO_ADVISOR)


@pytest.mark.parametrize("issuer, secret", [("", "s3cr3t"), (ISSUER, "")])
def test_on_cloud_run_unconfigured_does_not_open(issuer: str, secret: str) -> None:
    r = with_gate(built(issuer=issuer, secret=secret)).get(PROTECTED, headers={"Authorization": "Bearer t"})
    assert r.status_code == 503
    assert "auth not configured" in r.json()["detail"]


@pytest.mark.parametrize("header", [{}, {"Authorization": "t"}, {"Authorization": "Basic dDp0"}])
def test_without_bearer_is_401_and_does_not_ask(header: dict[str, str]) -> None:
    oidc = OIDC(active("knowledge"))
    r = with_gate(built(oidc)).get(PROTECTED, headers=header)
    assert r.status_code == 401
    assert oidc.orders == []


def test_active_token_of_an_allowed_client_passes_and_is_remembered() -> None:
    oidc = OIDC(active("knowledge"))
    c = with_gate(built(oidc))
    for _ in range(3):
        r = c.get(PROTECTED, headers={"Authorization": "Bearer t"})
        assert (r.status_code, r.json()["detail"]) == (503, NO_ADVISOR)
    assert oidc.orders == [{"token": ["t"], "client_id": ["demo"], "client_secret": ["s3cr3t"]}]


def test_inactive_token_is_401() -> None:
    oidc = OIDC(lambda _: httpx.Response(200, json={"active": False}))
    r = with_gate(built(oidc)).get(PROTECTED, headers={"Authorization": "Bearer t"})
    assert r.status_code == 401


def test_oidc_rejecting_the_introspection_is_401() -> None:
    oidc = OIDC(lambda _: httpx.Response(401, json={"error": "invalid_client"}))
    r = with_gate(built(oidc)).get(PROTECTED, headers={"Authorization": "Bearer t"})
    assert r.status_code == 401


def test_an_inactive_one_is_not_remembered() -> None:
    answers = iter([httpx.Response(200, json={"active": False}), httpx.Response(200, json={"active": True, "client_id": "knowledge"})])
    oidc = OIDC(lambda _: next(answers))
    c = with_gate(built(oidc))
    assert c.get(PROTECTED, headers={"Authorization": "Bearer t"}).status_code == 401
    assert c.get(PROTECTED, headers={"Authorization": "Bearer t"}).json()["detail"] == NO_ADVISOR
    assert len(oidc.orders) == 2


def test_client_outside_the_allowlist_is_403_also_remembered() -> None:
    oidc = OIDC(active("chatroom"))
    c = with_gate(built(oidc))
    for _ in range(2):
        r = c.get(PROTECTED, headers={"Authorization": "Bearer t"})
        assert r.status_code == 403
        assert "chatroom" in r.json()["detail"]
    assert len(oidc.orders) == 1


def test_empty_allowlist_lets_any_active_client_through() -> None:
    r = with_gate(built(OIDC(active("chatroom")), allowed="")).get(PROTECTED, headers={"Authorization": "Bearer t"})
    assert r.json()["detail"] == NO_ADVISOR


def test_oidc_down_is_500() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    r = with_gate(built(OIDC(down))).get(PROTECTED, headers={"Authorization": "Bearer t"})
    assert r.status_code == 500


def test_oidc_answering_garbage_is_500() -> None:
    r = with_gate(built(OIDC(lambda _: httpx.Response(200, text="<html>")))).get(PROTECTED, headers={"Authorization": "Bearer t"})
    assert r.status_code == 500


def test_a2a_is_also_protected() -> None:
    r = with_gate(built(OIDC(active("knowledge")))).post("/a2a", json={"jsonrpc": "2.0", "id": 1, "method": "message/send"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", ["/health", "/", "/.well-known/agent-card.json", "/docs"])
def test_what_is_public_stays_public(path: str) -> None:
    oidc = OIDC(active("knowledge"))
    r = with_gate(built(oidc)).get(path)
    assert r.status_code == 200
    assert oidc.orders == []
