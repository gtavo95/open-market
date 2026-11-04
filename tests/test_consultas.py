"""`POST /consultas`: the turn of `/queries` in the Spanish contract of the host, and its stream of lines.

The advisor is the fake of `tests/test_routes.py`, so what is held here is the edge: what reaches the
advisor is the interior's English, what comes back is knowledge's Spanish, and the stream keeps the
host's connection alive and always ends with `fin`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from catalejo.core import EffectOp, Entry, Node
from fastapi.testclient import TestClient

import core_agent
from auth import Gate, gate
from config import Settings, get_settings
from core_agent.agent import CLAUDE_THINKING, GEMINI_THINKING, MUSE_THINKING, OPENAI_THINKING
from core_agent.world.order import Item
from host import Answer, TurnFailed
from main import app
from routes import consultas
from routes.consultas import NDJSON, live, llm_of
from tests.test_routes import CUT, EMPTY, GROUNDED, QUESTION, FakeAdvisor
from wire import to_english

LLM = {"proveedor": "openai", "modelo": "gpt-test", "esfuerzo": "low"}
EXTRAS = {"traza": {"pasos": []}, "turnId": "t-7", "conversationId": "c-3", "adjuntos": [{"ruta": "a.jpg", "tipo": "imagen"}], "aviso": {"motivo": "x"}, "cerrados": [1]}

DEAL = {
    "id": "6650f0c2a1b2c3d4e5f60718",
    "kind": "venta",
    "stage": "en_pago",
    "version": 3,
    "numero": 12,
    "desde_turno": None,
    "items": [{"sku": "SEG-1L", "producto": "Reapvane", "presentacion": "1 L", "cantidad": 2, "precio": 229.0, "subtotal": 458.0, "precio_de": None}],
    "total": 458.0,
    "moneda": "GTQ",
    "form": {"campos": {"nit": "CF", "razon_social": "Agro SA", "color": "azul", "medio_pago": "cheque"}, "faltan": []},
    "pago": {"link": {"url": "https://pay.example/x", "activo": True, "vence_en": None}, "pagado": False, "pagado_en": None},
    "cita": None,
    "efectos": [{"id": "send_ficha", "kind": "document", "status": "done"}],
    "abierto_en": "2026-10-08T10:00:00Z",
    "actualizado_en": "2026-10-08T10:05:00Z",
}
REQUEST: dict[str, Any] = {
    "pregunta": "  dos galones ",
    "historia": [{"pregunta": "hola", "respuesta": "buenas"}],
    "venta": [
        {"verb": "add_step", "id": "diagnostico", "intent": "diagnose"},
        {"verb": "add_step", "id": "plaga", "intent": "find out", "done_when": "hay_con_que_buscar", "padre": "diagnostico"},
        {"verb": "mark", "id": "plaga", "status": "done"},
    ],
    "efectos": [
        {"verb": "propose", "id": "send_ficha", "kind": "document"},
        {"verb": "resolve", "id": "send_ficha", "args": [["path", "products/hyphavane.md"]]},
        {"verb": "done", "id": "send_catalogo"},
    ],
    "pago": "pendiente",
    "memoria": {
        "mensajes": [{"i": 0, "kind": "cliente", "text": "2 galones", "date": "2026-06-02T15:04:00-06:00"}, {"i": 1, "kind": "asesor", "text": "listo"}],
        "arbol": [{"l": 1, "i": 0, "text": "cliente: 2 galones; asesor: listo"}],
    },
    "deal": DEAL,
    "cliente": {"nombre": "Rodrigo", "nit": "1234567-8", "razon_social": None, "direcciones": [{"label": "finca", "address": "zona 5, Xela"}], "correo": None, "telefono": "5555-0101"},
    "retomada": True,
}


@pytest.fixture
def customer(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Without `with`: the lifespan does not run, so nobody tries to load the real bundle."""
    monkeypatch.setattr(core_agent.world.catalog, "BUNDLE", core_agent.world.catalog.CATALOG)
    app.dependency_overrides[get_settings] = lambda: Settings(timeout_s=9, public_url="", provider="openai", model="gpt-test", thinking="low", _env_file=None)  # type: ignore[call-arg]
    app.state.advisor = None
    app.state.advisor_error = ""
    yield TestClient(app)
    app.dependency_overrides.clear()


def built(customer: TestClient, a: FakeAdvisor) -> FakeAdvisor:
    customer.app.state.advisor = a  # type: ignore[attr-defined]
    return a


def lines(text: str) -> list[str]:
    return text.split("\n")


class Slow(FakeAdvisor):
    """An advisor that takes `delay` seconds to answer, to see what the stream does meanwhile."""

    def __init__(self, delay: float, answer: Answer = GROUNDED, error: Exception | None = None) -> None:
        super().__init__(answer, error)
        self.delay = delay

    async def ask(self, *args: Any, **kwargs: Any) -> Answer:
        await asyncio.sleep(self.delay)
        return await super().ask(*args, **kwargs)


class TestWhatReachesTheAdvisor:
    def test_the_spanish_request_arrives_in_english(self, customer: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        a = built(customer, FakeAdvisor())

        with caplog.at_level(logging.WARNING):
            r = customer.post("/consultas", json=REQUEST)

        assert r.status_code == 200
        assert a.calls == [("dos galones", (("hola", "buenas"),), 9.0)]
        assert a.payments == ["pending"]
        assert [(o.verb, o.id, o.padre, o.done_when) for o in a.sales[0]] == [
            ("add_step", "diagnosis", "", ""),
            ("add_step", "pest", "diagnosis", "has_search_terms"),
            ("mark", "pest", "", ""),
        ]
        assert a.effects[0] == (
            EffectOp("propose", "send_datasheet", "document"),
            EffectOp("resolve", "send_datasheet", args=(("path", "products/hyphavane.md"),)),
            EffectOp("done", "send_catalog"),
        )
        assert a.memories[0] == (Entry(0, "customer", "2 galones", "2026-06-02T15:04:00-06:00"), Entry(1, "advisor", "listo", ""), Node(1, 0, "cliente: 2 galones; asesor: listo"))
        assert a.forms == [({"nit": "CF", "legal_name": "Agro SA"}, True)], "the seed is the bundle's fields, with the English ids"
        assert a.carts == [[{"sku": "SEG-1L", "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": 229.0, "subtotal": 458.0}]]
        assert a.closings[0][0] == {"nit": "1234567-8", "phone": "5555-0101", "address": "zona 5, Xela"}
        assert "color" in caplog.text, "a form id nobody knows is said, and does not break the turn"

    def test_the_fields_knowledge_sends_that_the_interior_has_no_use_for_are_not_a_422(self, customer: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        a = built(customer, FakeAdvisor())

        with caplog.at_level(logging.WARNING):
            r = customer.post("/consultas", json={"pregunta": "hola", **EXTRAS})

        assert r.status_code == 200
        assert a.calls == [("hola", (), 9.0)]
        assert not [x for x in caplog.records if x.name != "routes.consultas"], caplog.text

    def test_the_conversation_and_the_turn_are_logged_at_info(self, customer: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        built(customer, FakeAdvisor())

        with caplog.at_level(logging.INFO, logger="routes.consultas"):
            customer.post("/consultas", json={"pregunta": "hola", **EXTRAS})

        assert "conversation=c-3 turn=t-7" in caplog.text

    def test_it_is_the_same_turn_as_queries(self, customer: TestClient) -> None:
        """The same request in each tongue: the advisor sees the same thing and the answer is the same answer."""
        english = to_english("Query", REQUEST)
        first, second = built(customer, FakeAdvisor()), FakeAdvisor()

        r_en = customer.post("/queries", json=english)
        built(customer, second)
        r_es = customer.post("/consultas", json=REQUEST)

        assert r_en.status_code == r_es.status_code == 200
        for name in ("calls", "sales", "effects", "payments", "memories", "forms", "closings", "carts"):
            assert getattr(first, name) == getattr(second, name), name
        spanish = r_es.json()
        assert spanish.pop("llm") == LLM
        assert to_english("AnswerOut", spanish) == r_en.json()


class TestTheAnswer:
    def test_it_speaks_spanish(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        r = customer.post("/consultas", json={"pregunta": "thrips en tomate?"})

        assert r.status_code == 200
        body = r.json()
        assert list(body) == [
            "respuesta", "mensajes", "fuentes", "fundada", "tokens", "tokens_entrada", "tokens_cacheados", "tokens_salida", "tokens_typesafe",
            "turnos", "halt", "fails", "segundos", "cortada", "sin_que_buscar", "venta", "efectos", "formulario", "reiniciar", "cambios", "reglas", "llm",
        ]  # fmt: skip
        assert body["respuesta"] == GROUNDED.text and body["fundada"] is True
        assert (body["tokens"], body["tokens_entrada"], body["tokens_cacheados"], body["tokens_salida"]) == (1200, 1000, 600, 200)
        assert body["llm"] == LLM
        assert body["venta"]["ops"][0] == {"verb": "add_step", "id": "diagnostico", "intent": "diagnose and build the cart"}
        assert body["venta"]["activa"] == "receta" and body["venta"]["pendientes"][:2] == ["receta", "cantidad"]
        assert set(body["venta"]["juicio"]["p"]) == {"hay_con_que_buscar", "dijo_cantidad", "quiere_comprar", "dijo_medio_de_pago", "dijo_datos_de_factura"}
        assert body["efectos"]["ops"][0] == {"verb": "propose", "id": "send_ficha", "kind": "document"}
        assert body["efectos"]["pendientes"] == [{"id": "send_ficha", "kind": "document", "args": [["path", "products/hyphavane.md"]], "ejecutable": True}]
        assert [c["id"] for c in body["formulario"]["esquema"]] == ["razon_social", "nit", "recibe", "telefono", "correo", "direccion", "medio_pago"]
        assert body["formulario"]["titulo"] == "Billing details", "the bundle's prose is the bundle's"

    def test_what_is_not_filled_is_not_there(self, customer: TestClient) -> None:
        """`modelo`, `traza` and `opted_out` are omitted, not invented: the interior has no honest value for them."""
        built(customer, FakeAdvisor())

        body = customer.post("/consultas", json={"pregunta": "hola"}).json()

        assert not {"modelo", "traza", "opted_out", "entrevista"} & set(body)

    def test_the_question_of_the_sale_says_it_is_asking(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(QUESTION))

        body = customer.post("/consultas", json={"pregunta": "hola"}).json()

        assert body["sin_que_buscar"] is True and body["respuesta"] == "What pest do you see?"

    def test_the_deal_changes_are_in_spanish(self, customer: TestClient) -> None:
        fields = {"nit": "1234567-8", "recipient": "Rodrigo", "phone": "5555-0101", "address": "zona 5", "payment_method": "transfer", "email": "r@example.com"}
        built(customer, FakeAdvisor(replace(GROUNDED, form=fields)))

        body = customer.post("/consultas", json={"pregunta": "hola", "deal": DEAL}).json()

        assert body["cambios"]["base"] == 3
        assert body["cambios"]["form"] == {
            "nit": "1234567-8", "recibe": "Rodrigo", "telefono": "5555-0101", "direccion": "zona 5", "medio_pago": "transferencia", "correo": "r@example.com", "razon_social": None,
        }  # fmt: skip
        assert body["formulario"]["campos"]["medio_pago"] == "transferencia"
        assert "cita" not in body["cambios"], "no appointment is ever filled in"

    def test_starting_over_clears_the_deal_in_spanish(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(replace(GROUNDED, reset=True)))

        body = customer.post("/consultas", json={"pregunta": "borra todo", "deal": DEAL}).json()

        assert body["reiniciar"] is True and body["cambios"]["deal"] == "vaciar"

    def test_the_cart_deltas_use_the_spanish_verbs(self, customer: TestClient) -> None:
        line = Item("reapvane", "1 L", 5.0, product="Reapvane", path="products/reapvane.md", presentation="1 L", unit_price=275.0, status="current", currency="GTQ", code="PT0107")
        built(customer, FakeAdvisor(replace(GROUNDED, order=(line,))))
        deal = {**DEAL, "stage": "abierto", "form": None, "items": [{"sku": "PT0107", "producto": "Reapvane", "presentacion": "1 L", "cantidad": 2, "precio": 275.0, "subtotal": 550.0}]}

        body = customer.post("/consultas", json={"pregunta": "mejor 5", "deal": deal}).json()

        assert body["cambios"]["items"] == [{"op": "cambiar", "sku": "PT0107", "producto": "Reapvane", "presentacion": "1 L", "cantidad": 5.0, "precio": 275.0}]

    def test_a_handoff_goes_out_with_the_reasons_of_the_host(self, customer: TestClient) -> None:
        effects = (
            EffectOp("propose", "handoff", "handoff"),
            EffectOp("resolve", "handoff", args=(("origin", "requested_by_agent"), ("reason", "quality_complaint"))),
        )
        built(customer, FakeAdvisor(replace(GROUNDED, effects=effects)))

        body = customer.post("/consultas", json={"pregunta": "me llegó malo"}).json()

        assert body["efectos"]["ops"][1]["args"] == [["origin", "solicitado_por_el_agente"], ["reason", "reclamo_calidad"]]
        assert body["efectos"]["pendientes"][0]["args"] == [["origin", "solicitado_por_el_agente"], ["reason", "reclamo_calidad"]]

    def test_the_payment_link_lines_are_translated_inside_their_json(self, customer: TestClient) -> None:
        item = json.dumps({"line": 1, "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": "229.00", "subtotal": "458.00", "item_code": "C1"})
        args = (("item", item), ("currency", "GTQ"), ("total", "458.00"))
        effects = (EffectOp("propose", "send_payment_link", "payment_link"), EffectOp("resolve", "send_payment_link", args=args))
        built(customer, FakeAdvisor(replace(GROUNDED, effects=effects)))

        sent = customer.post("/consultas", json={"pregunta": "el link"}).json()["efectos"]["pendientes"][0]["args"]

        assert sorted(k for k, _ in sent) == ["item", "moneda", "total"]
        assert json.loads(dict(sent)["item"]) == {"renglon": 1, "producto": "Reapvane", "presentacion": "1 L", "cantidad": 2, "precio": "229.00", "subtotal": "458.00", "item_code": "C1"}


class TestWhenTheTurnFails:
    @pytest.mark.parametrize("answer, status, detail", [(CUT, 504, "loop: time cap: 9/9 s"), (EMPTY, 502, "model: the API did not answer")])
    def test_a_turn_that_did_not_answer_carries_what_it_charged_and_the_llm(self, customer: TestClient, answer: Answer, status: int, detail: str) -> None:
        built(customer, FakeAdvisor(answer))

        r = customer.post("/consultas", json={"pregunta": "hola"})

        assert r.status_code == status
        assert r.json() == {
            "detail": detail,
            "tokens": answer.tokens,
            "tokens_entrada": 0,
            "tokens_cacheados": 0,
            "tokens_salida": 0,
            "tokens_typesafe": 0,
            "llm": LLM,
        }

    def test_a_turn_that_raises_is_a_500_with_its_cost_in_spanish(self, customer: TestClient) -> None:
        cost = {"tokens": 900, "tokens_input": 800, "tokens_cached": 0, "tokens_output": 100, "tokens_typesafe": 300}
        built(customer, FakeAdvisor(error=TurnFailed(ZeroDivisionError("bug"), cost)))

        r = customer.post("/consultas", json={"pregunta": "hola"})

        assert r.status_code == 500
        assert r.json() == {
            "detail": "ZeroDivisionError: bug",
            "tokens": 900,
            "tokens_entrada": 800,
            "tokens_cacheados": 0,
            "tokens_salida": 100,
            "tokens_typesafe": 300,
            "llm": LLM,
        }

    def test_without_advisor_is_503_with_the_reason(self, customer: TestClient) -> None:
        app.state.advisor_error = "ValueError: PROVIDER='x'"

        r = customer.post("/consultas", json={"pregunta": "hola"})

        assert r.status_code == 503 and r.json()["detail"] == "ValueError: PROVIDER='x'"

    def test_a_request_the_interior_refuses_is_a_422_that_names_the_field(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())

        for body in ({}, {"pregunta": "   "}, {"pregunta": "hola", "pago": "trueque"}, {"pregunta": "hola", "historia": "no"}):
            r = customer.post("/consultas", json=body)
            assert r.status_code == 422, body
            assert isinstance(r.json()["detail"], list)
            assert not any("input" in e for e in r.json()["detail"]), "what the customer wrote is not echoed back"

        assert a.calls == []

    def test_a_body_that_is_not_an_object_is_a_422(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert customer.post("/consultas", json=["hola"]).status_code == 422
        assert customer.post("/consultas", content=b"not json", headers={"content-type": "application/json"}).status_code == 422


class TestTheStream:
    ASK = {"accept": NDJSON}

    def test_a_fast_turn_is_one_line_the_fin(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        r = customer.post("/consultas", json={"pregunta": "hola"}, headers=self.ASK)

        assert r.status_code == 200
        assert r.headers["content-type"].startswith(NDJSON)
        assert lines(r.text)[1:] == [""] and r.text.endswith("\n")
        fin = json.loads(lines(r.text)[0])
        assert list(fin) == ["fin"] and fin["fin"]["status"] == 200
        assert fin["fin"]["body"]["respuesta"] == GROUNDED.text
        assert fin["fin"]["body"]["llm"] == LLM

    def test_the_body_of_fin_is_the_plain_answer(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        plain = customer.post("/consultas", json={"pregunta": "hola"}).json()
        streamed = json.loads(customer.post("/consultas", json={"pregunta": "hola"}, headers=self.ASK).text)

        assert streamed == {"fin": {"status": 200, "body": plain}}

    def test_while_the_turn_runs_an_empty_line_goes_out_every_heartbeat(self, customer: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(consultas, "HEARTBEAT", 0.05)
        built(customer, Slow(0.4))

        r = customer.post("/consultas", json={"pregunta": "hola"}, headers=self.ASK)

        heartbeats = r.text.split('{"fin"')[0]
        assert heartbeats and set(heartbeats) == {"\n"}, "the silence is filled with empty lines only"
        assert len(heartbeats) >= 3
        assert json.loads(r.text.strip())["fin"]["status"] == 200

    def test_a_failed_turn_ends_with_fin_carrying_the_status_and_what_it_charged(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(CUT))

        r = customer.post("/consultas", json={"pregunta": "hola"}, headers=self.ASK)

        assert r.status_code == 200, "the status of the turn travels inside `fin`, because the headers are already out"
        fin = json.loads(r.text)["fin"]
        assert fin["status"] == 504
        assert fin["body"] == {
            "detail": "loop: time cap: 9/9 s", "tokens": 4000, "tokens_entrada": 0, "tokens_cacheados": 0, "tokens_salida": 0, "tokens_typesafe": 0, "llm": LLM,
        }  # fmt: skip

    def test_a_turn_that_raises_the_failure_with_cost_is_also_a_fin(self, customer: TestClient) -> None:
        cost = {"tokens": 5, "tokens_input": 4, "tokens_cached": 0, "tokens_output": 1, "tokens_typesafe": 0}
        built(customer, FakeAdvisor(error=TurnFailed(ZeroDivisionError("bug"), cost)))

        fin = json.loads(customer.post("/consultas", json={"pregunta": "hola"}, headers=self.ASK).text)["fin"]

        assert fin["status"] == 500 and fin["body"]["tokens_entrada"] == 4 and fin["body"]["llm"] == LLM

    def test_a_turn_that_blows_up_outside_the_failure_path_is_still_a_fin(self, customer: TestClient) -> None:
        """A stream that ends without `fin` is a 502 for the host, so even a bug is written."""
        built(customer, FakeAdvisor(error=ZeroDivisionError("boom")))

        r = customer.post("/consultas", json={"pregunta": "hola"}, headers=self.ASK)

        fin = json.loads(r.text)["fin"]
        assert fin == {"status": 500, "body": {"detail": "ZeroDivisionError: boom"}}

    def test_a_request_that_is_invalid_is_refused_before_the_stream_opens(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        r = customer.post("/consultas", json={"pregunta": "  "}, headers=self.ASK)

        assert r.status_code == 422 and r.headers["content-type"].startswith("application/json")

    @pytest.mark.parametrize("accept", [{}, {"accept": "application/json"}, {"accept": "*/*"}, {"accept": "text/html"}])
    def test_without_ndjson_in_accept_it_is_plain_json(self, customer: TestClient, accept: dict[str, str]) -> None:
        built(customer, FakeAdvisor())

        r = customer.post("/consultas", json={"pregunta": "hola"}, headers=accept)

        assert r.status_code == 200
        assert r.headers["content-type"] == "application/json"
        assert r.json()["respuesta"] == GROUNDED.text

    @pytest.mark.parametrize("accept", ["application/x-ndjson", "application/json, application/x-ndjson;q=0.9", "application/x-ndjson; charset=utf-8"])
    def test_ndjson_anywhere_in_accept_streams(self, customer: TestClient, accept: str) -> None:
        built(customer, FakeAdvisor())

        r = customer.post("/consultas", json={"pregunta": "hola"}, headers={"accept": accept})

        assert r.headers["content-type"].startswith(NDJSON)

    def test_a_failed_turn_without_ndjson_keeps_its_own_status(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(EMPTY))

        assert customer.post("/consultas", json={"pregunta": "hola"}, headers={"accept": "application/json"}).status_code == 502


class TestLive:
    async def test_when_the_client_goes_away_the_turn_is_cancelled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(consultas, "HEARTBEAT", 0.01)
        ended: list[str] = []

        async def turn() -> tuple[int, dict[str, Any]]:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                ended.append("cancelled")
                raise
            return 200, {}

        stream = live(turn())
        assert await anext(stream) == "\n"
        await stream.aclose()
        await asyncio.sleep(0.01)

        assert ended == ["cancelled"]

    async def test_the_fin_comes_after_the_last_heartbeat_and_nothing_follows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(consultas, "HEARTBEAT", 0.01)

        async def turn() -> tuple[int, dict[str, Any]]:
            await asyncio.sleep(0.06)
            return 200, {"respuesta": "ñ"}

        out = [chunk async for chunk in live(turn())]

        assert out[-1] == '{"fin": {"status": 200, "body": {"respuesta": "ñ"}}}\n'
        assert out[:-1] and set(out[:-1]) == {"\n"}


def adapter(model: str) -> Any:
    """What `llm_of` reads of a live provider: a `model` that is a string."""
    return SimpleNamespace(model=model)


class TestWhichModel:
    @pytest.mark.parametrize("provider, effort", [("muse", MUSE_THINKING), ("openai", OPENAI_THINKING), ("anthropic", CLAUDE_THINKING), ("gemini", GEMINI_THINKING)])
    def test_the_effort_is_the_one_each_provider_runs_with(self, provider: str, effort: str) -> None:
        s = Settings(provider=provider, model="", thinking="", _env_file=None)  # type: ignore[call-arg]

        assert llm_of(adapter("the-default"), s) == {"provider": provider, "model": "the-default", "effort": effort}

    def test_the_setting_wins_for_the_effort(self) -> None:
        s = Settings(provider="openai", thinking="high", _env_file=None)  # type: ignore[call-arg]

        assert llm_of(adapter("m"), s)["effort"] == "high"

    def test_the_model_is_what_the_adapter_says_even_when_the_setting_is_empty(self) -> None:
        s = Settings(provider="openai", model="", _env_file=None)  # type: ignore[call-arg]

        assert llm_of(adapter("gpt-picked-by-the-adapter"), s)["model"] == "gpt-picked-by-the-adapter"

    def test_without_an_adapter_it_falls_back_to_the_setting(self) -> None:
        s = Settings(provider="openai", model="gpt-set", _env_file=None)  # type: ignore[call-arg]

        assert llm_of(None, s)["model"] == "gpt-set"
        assert llm_of(object(), s)["model"] == "gpt-set"  # type: ignore[arg-type]

    def test_a_provider_the_table_does_not_know_has_no_effort_and_no_crash(self) -> None:
        s = Settings(provider="other", _env_file=None)  # type: ignore[call-arg]

        assert llm_of(None, s) == {"provider": "other", "model": "", "effort": ""}


class TestTheGate:
    """`/consultas` and `/compactar` sit behind the same OIDC gate as `/queries`."""

    ISSUER = "https://oidc.example"

    def client(self, active: bool = True) -> TestClient:
        def introspect(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"active": active, "client_id": "knowledge", "sub": "knowledge"})

        app.dependency_overrides[gate] = lambda: Gate(
            issuer=self.ISSUER, secret="s3cr3t", allowed=frozenset({"knowledge"}), on_cloud_run=True, transport=httpx.MockTransport(introspect)
        )
        app.state.advisor = None
        app.state.advisor_error = ""
        app.state.compactor = None
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def clean(self) -> Iterator[None]:
        yield
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("path, body", [("/consultas", {"pregunta": "hola"}), ("/compactar", {"memoria": {"mensajes": [], "arbol": []}})])
    def test_without_a_token_it_is_401(self, path: str, body: dict[str, Any]) -> None:
        assert self.client().post(path, json=body).status_code == 401

    @pytest.mark.parametrize("path, body", [("/consultas", {"pregunta": "hola"}), ("/compactar", {"memoria": {"mensajes": [], "arbol": []}})])
    def test_with_an_inactive_token_it_is_401(self, path: str, body: dict[str, Any]) -> None:
        assert self.client(active=False).post(path, json=body, headers={"Authorization": "Bearer t"}).status_code == 401

    @pytest.mark.parametrize("path, body", [("/consultas", {"pregunta": "hola"}), ("/compactar", {"memoria": {"mensajes": [], "arbol": []}})])
    def test_with_an_active_token_it_gets_to_the_handler(self, path: str, body: dict[str, Any]) -> None:
        r = self.client().post(path, json=body, headers={"Authorization": "Bearer t"})

        assert r.status_code == 503, "past the gate, and then there is no advisor or compactor built"


def test_both_routes_are_in_the_openapi_of_the_service() -> None:
    paths = app.openapi()["paths"]

    assert "post" in paths["/consultas"] and "post" in paths["/compactar"]
