"""The HTTP layer with a fake advisor: which status code comes out for each thing that can happen."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from catalejo.core import EffectOp, Entry, Memory, Node, PlanOp
from catalejo.rlm.cells.planner import STATE
from fastapi.testclient import TestClient

import core_agent
from core_agent.world.order import price_order
from host import Answer, TurnFailed
from host.form import form_to_dict
from host.sale import op_to_dict, summary, sale_to_dict
from config import Settings, get_settings
from main import app

DATASHEET = "products/hyphavane.md"
SALE = (*core_agent.SESSION, PlanOp("mark", "pest", status="done"), PlanOp("mark", "product", status="done"))
JUDGMENT = {
    "state": {"pest": "thrips", "crop": "tomato"},
    "p": {"has_search_terms": 0.95, "said_quantity": 0.05, "wants_to_buy": 0.05, "said_payment_method": 0.04, "said_billing_data": 0.04},
    "error": "",
}
SALE_JSON = {**sale_to_dict(summary(SALE)), "judgment": JUDGMENT}
EFFECTS = (
    EffectOp("propose", "send_datasheet", "document"),
    EffectOp("resolve", "send_datasheet", args=(("path", DATASHEET),)),
)
EFFECTS_JSON: dict[str, Any] = {
    "ops": [
        {"verb": "propose", "id": "send_datasheet", "kind": "document"},
        {"verb": "resolve", "id": "send_datasheet", "args": [["path", DATASHEET]]},
    ],
    "pending": [{"id": "send_datasheet", "kind": "document", "args": [["path", DATASHEET]], "executable": True}],
    "state": f"send_datasheet proposed ({DATASHEET})",
}
RULES: tuple[dict[str, Any], ...] = (
    {"id": "sale/has-search-terms_tag", "p": 0.95, "threshold": 0.8, "fired": True, "action": "closes:pest"},
    {"id": "alerts/ambiguous-order_tag", "p": 0.12, "threshold": 0.7, "fired": False, "action": "line:ALERT_LINES"},
    {"id": "case/not-covered_tag", "p": None, "threshold": "argmax", "fired": False, "action": "line:CASE_LINES"},
    {"id": "escalation.outbound/reason_tag", "p": 0.81, "threshold": "argmax", "fired": True, "action": "handoff", "option": "product_not_found"},
    {"id": "sale/datasheet_tag", "p": 0.88, "threshold": "argmax", "fired": True, "action": "cart_line:product", "lines": [{"said": "the reapvane", "option": "Reapvane", "p": 0.88}]},
)
GROUNDED = Answer(
    text="Hyphavane, 1.0 to 1.5 l/ha",
    sources=(DATASHEET,),
    grounded=True,
    tokens=1200,
    tokens_input=1000,
    tokens_cached=600,
    tokens_output=200,
    turns=4,
    halt=False,
    fails=(),
    seconds=12.5,
    sale=SALE,
    effects=EFFECTS,
    judgment=JUDGMENT,
    rules=RULES,
)
QUESTION = Answer("What pest do you see?", (), False, 200, 2, False, (), nothing_to_search=True, sale=core_agent.SESSION)
OPINION = Answer("2 l/ha", (), False, 300, 2, False, ("grounding: answered without run_query",), sale=SALE)
WITH_FAILURE = Answer("x", (DATASHEET,), True, 300, 2, False, ("cite: cited paths that do not exist: products/no.md",), sale=SALE)
EMPTY = Answer("", (), False, 0, 0, True, ("model: the API did not answer",), sale=SALE)
CUT = Answer("", (), True, 4000, 5, False, ("loop: time cap: 9/9 s",), seconds=9.1, cut_off=True, sale=SALE)


MEMORY_JSON = {
    "messages": [{"i": 0, "kind": "customer", "text": "2 gallons", "date": "2026-06-02T15:04:00-06:00"}],
    "tree": [{"l": 1, "i": 0, "text": "customer: 2 gallons; advisor: ready"}],
}
DEAL_JSON = {
    "id": "6650f0c2a1b2c3d4e5f60718",
    "kind": "sale",
    "stage": "open",
    "version": 3,
    "number": 12,
    "from_turn": None,
    "items": [{"sku": "SEG-1L", "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": 229.0, "subtotal": 458.0}],
    "total": 458.0,
    "currency": "GTQ",
    "form": {"fields": {"nit": "CF"}, "missing": ["address"]},
    "payment": {"link": {"url": "https://pay.example/x", "active": True, "expires_at": None}, "paid": False, "paid_at": None},
    "quote": None,
    "effects": [{"id": "e1", "kind": "payment_link", "status": "done"}],
    "opened_at": "2026-10-08T10:00:00Z",
    "updated_at": "2026-10-08T10:05:00Z",
}
CUSTOMER_JSON = {"name": "Rodrigo", "nit": "1234567-8", "legal_name": None, "addresses": [{"label": "farm", "address": "zona 5, Xela"}], "email": None, "phone": "5555-0101"}
MEMORY = (Entry(0, "customer", "2 gallons", "2026-06-02T15:04:00-06:00"), Node(1, 0, "customer: 2 gallons; advisor: ready"))


class FakeAdvisor:
    sheets = 2
    text = "x" * 8000
    free = 1

    def __init__(self, answer: Answer = GROUNDED, error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.calls: list[tuple[str, tuple[tuple[str, str], ...], float | None]] = []
        self.sales: list[tuple[PlanOp, ...]] = []
        self.effects: list[tuple[EffectOp, ...]] = []
        self.payments: list[str] = []
        self.memories: list[Memory] = []
        self.forms: list[tuple[dict[str, str] | None, bool]] = []
        self.closings: list[tuple[dict[str, str] | None, int | None]] = []
        self.carts: list[list[dict[str, Any]] | None] = []

    async def ask(
        self,
        question: str,
        history: tuple[tuple[str, str], ...] = (),
        *,
        sale: tuple[PlanOp, ...] = (),
        effects: tuple[EffectOp, ...] = (),
        timeout: float | None = None,
        payment: str = "",
        memory: Memory = (),
        form: dict[str, str] | None = None,
        resumed: bool = False,
        previous: dict[str, str] | None = None,
        closed: int | None = None,
        cart: list[dict[str, Any]] | None = None,
    ) -> Answer:
        self.calls.append((question, history, timeout))
        self.carts.append(cart)
        self.forms.append((form, resumed))
        self.closings.append((previous, closed))
        self.payments.append(payment)
        self.memories.append(memory)
        self.sales.append(sale)
        self.effects.append(effects)
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture
def customer() -> Iterator[TestClient]:
    """Without `with`: the lifespan does not run, so nobody tries to load the real bundle."""
    app.dependency_overrides[get_settings] = lambda: Settings(timeout_s=9, public_url="", _env_file=None)  # type: ignore[call-arg]
    app.state.advisor = None
    app.state.advisor_error = ""
    yield TestClient(app)
    app.dependency_overrides.clear()


def built(customer: TestClient, a: FakeAdvisor) -> FakeAdvisor:
    customer.app.state.advisor = a  # type: ignore[attr-defined]
    return a


def rpc(customer: TestClient, method: str, params: dict[str, Any] | None = None, id_: Any = 1) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    r = customer.post("/a2a", json=body)
    assert r.status_code == 200
    data: dict[str, Any] = r.json()
    return data


def message(text: str, **extra: Any) -> dict[str, Any]:
    return {"message": {"role": "user", "messageId": "m1", "parts": [{"kind": "text", "text": text}], **extra}}


class TestHealth:
    def test_alive_but_without_advisor_says_so(self, customer: TestClient) -> None:
        app.state.advisor_error = "FileNotFoundError: the bundle does not exist"

        body = customer.get("/health").json()

        assert body["status"] == "ok"
        assert body["advisor"] is False
        assert body["advisor_error"] == "FileNotFoundError: the bundle does not exist"

    def test_with_advisor(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert customer.get("/health").json()["advisor"] is True

    def test_the_root_points_to_the_docs(self, customer: TestClient) -> None:
        assert "<title>" in customer.get("/").text


class TestQueries:
    def test_without_advisor_is_503_with_the_reason(self, customer: TestClient) -> None:
        app.state.advisor_error = "ValueError: PROVIDER='x'"

        r = customer.post("/queries", json={"question": "thrips on tomato?"})

        assert r.status_code == 503
        assert r.json()["detail"] == "ValueError: PROVIDER='x'"

    def test_the_answer_with_its_backing(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())

        r = customer.post("/queries", json={"question": "thrips on tomato?"})

        assert r.status_code == 200
        assert r.json() == {
            "answer": GROUNDED.text,
            "messages": [GROUNDED.text],
            "sources": [DATASHEET],
            "grounded": True,
            "tokens": 1200,
            "tokens_input": 1000,
            "tokens_cached": 600,
            "tokens_output": 200,
            "tokens_typesafe": 0,
            "turns": 4,
            "halt": False,
            "fails": [],
            "seconds": 12.5,
            "truncated": False,
            "no_search_terms": False,
            "sale": SALE_JSON,
            "effects": EFFECTS_JSON,
            "form": form_to_dict({}),
            "restart": False,
            "changes": None,
            "rules": [{"option": None, "lines": None, **e} for e in RULES],
        }
        assert a.calls == [("thrips on tomato?", (), 9.0)]
        assert a.sales == [()]
        assert a.forms == [({}, False)]

    def test_the_deal_form_comes_in_filtered_and_goes_out_with_what_is_missing_and_the_changes(
        self, customer: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`deal.form.fields` is the seed: a field the bundle does not have or a method outside the options does not come in."""
        monkeypatch.setattr(core_agent.world.catalog, "BUNDLE", core_agent.world.catalog.CATALOG)
        fields = {"nit": "1234567-8", "recipient": "Rodrigo", "phone": "5555-0101", "address": "zona 5", "payment_method": "link"}
        a = built(customer, FakeAdvisor(replace(GROUNDED, form=fields)))
        deal = {**DEAL_JSON, "form": {"fields": {"nit": "CF", "legal_name": "Agro SA", "color": "blue", "payment_method": "check"}, "missing": []}}

        r = customer.post("/queries", json={"question": "hi", "deal": deal, "resumption": True})

        assert r.status_code == 200
        assert a.forms == [({"nit": "CF", "legal_name": "Agro SA"}, True)]
        form = r.json()["form"]
        assert form["title"] == "Billing details"
        assert form["fields"] == fields and form["missing"] == []
        assert [c["id"] for c in form["form_schema"]] == ["legal_name", "nit", "recipient", "phone", "email", "address", "payment_method"]
        assert r.json()["changes"] == {
            "base": 3,
            "items": [],
            "form": {"nit": "1234567-8", "recipient": "Rodrigo", "phone": "5555-0101", "address": "zona 5", "payment_method": "link", "legal_name": None},
            "deal": None,
        }

    def test_the_deal_cart_goes_to_the_judge_and_comes_back_as_deltas(self, customer: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(core_agent.world.catalog, "BUNDLE", core_agent.world.catalog.CATALOG)
        order = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 5}])
        a = built(customer, FakeAdvisor(replace(GROUNDED, order=order)))
        deal = {**DEAL_JSON, "form": None, "items": [{"sku": "PT0107", "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": 275.0, "subtotal": 550.0}]}

        r = customer.post("/queries", json={"question": "better make it 5", "deal": deal}).json()

        assert a.carts == [deal["items"]]
        assert r["changes"] == {
            "base": 3,
            "items": [{"op": "change", "sku": "PT0107", "product": "Reapvane", "presentation": "1 L", "quantity": 5.0, "price": 275.0}],
            "form": {},
            "deal": None,
        }

    def test_without_order_judgment_nothing_is_removed(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(replace(GROUNDED, order=None)))

        assert customer.post("/queries", json={"question": "x", "deal": {**DEAL_JSON, "form": None}}).json()["changes"] is None

    def test_starting_over_is_clearing_the_deal(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(replace(GROUNDED, reset=True)))

        r = customer.post("/queries", json={"question": "delete it", "deal": DEAL_JSON}).json()

        assert r["restart"] is True and r["changes"]["deal"] == "clear"

    def test_without_deal_there_are_no_changes(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(replace(GROUNDED, reset=True)))

        assert customer.post("/queries", json={"question": "delete it"}).json()["changes"] is None

    def test_the_deal_starts_at_a_turn_of_the_trimmed_history(self, customer: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """What comes before `from_turn` is what was sold: the index shifts with the trim, and if it falls outside it cuts nothing."""
        monkeypatch.setattr(core_agent.world.catalog, "BUNDLE", core_agent.world.catalog.CATALOG)
        a = built(customer, FakeAdvisor())
        history = [{"question": f"p{i}", "answer": f"r{i}"} for i in range(8)]
        suggested = {"name": "Rodrigo", "nit": "1234567-8", "addresses": [{"label": "farm", "address": "zona 5"}, {"address": "zona 1"}]}

        for n in (7, 2, 0, None):
            customer.post("/queries", json={"question": "another", "history": history, "deal": {**DEAL_JSON, "from_turn": n}, "customer": suggested})

        previous = {"nit": "1234567-8", "address": "zona 5 or zona 1"}
        assert a.closings == [(previous, 4), (previous, None), (previous, None), (previous, None)]
        outside = customer.post("/queries", json={"question": "another", "history": history[:2], "deal": {**DEAL_JSON, "from_turn": 3}})
        assert outside.status_code == 422

    def test_a_form_that_is_not_of_texts_is_422(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert customer.post("/queries", json={"question": "hi", "deal": {**DEAL_JSON, "form": {"fields": {"nit": ["1"]}}}}).status_code == 422

    def test_the_sale_comes_in_as_ops_and_goes_out_read(self, customer: TestClient) -> None:
        """The customer sends `sale.ops` back as it is; what it receives is the sale after the turn, with what to ask for."""
        a = built(customer, FakeAdvisor())

        r = customer.post("/queries", json={"question": "thrips on tomato", "sale": SALE_JSON["ops"]})

        assert r.status_code == 200
        assert a.sales == [SALE]
        sale = r.json()["sale"]
        assert sale["ops"] == [op_to_dict(op) for op in SALE]
        assert sale["state"] == "sale 2/8: next `recipe`"
        assert sale["stage"] == "diagnosis" and sale["active"] == "recipe"
        assert sale["asks"] == {"id": "quantity", "what": core_agent.ASKS["quantity"]}
        assert sale["closed_steps"] == ["pest", "product"] and "quantity" in sale["pending"]
        assert sale["tree"].startswith(STATE) and sale["closed"] is False

    def test_the_payment_comes_in_and_an_unknown_one_is_422(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())

        customer.post("/queries", json={"question": "I already paid", "payment": "paid"})
        customer.post("/queries", json={"question": "I already paid"})

        assert a.payments == ["paid", ""]
        assert customer.post("/queries", json={"question": "I already paid", "payment": "refunded"}).status_code == 422

    def test_the_memory_comes_in_as_the_channel_and_a_malformed_one_is_422(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())

        customer.post("/queries", json={"question": "the same", "memory": MEMORY_JSON})
        customer.post("/queries", json={"question": "the same"})

        assert a.memories == [MEMORY, ()]
        no_kind = {"messages": [{"i": 0, "text": "hi"}]}
        assert customer.post("/queries", json={"question": "x", "memory": no_kind}).status_code == 422

    def test_resumption_comes_in_and_is_not_422(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert customer.post("/queries", json={"question": "hi", "resumption": True, "deal": DEAL_JSON}).status_code == 200
        assert customer.post("/queries", json={"question": "hi", "resumption": "x"}).status_code == 422

    def test_the_deal_and_the_customer_come_in_and_a_malformed_one_is_422(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert customer.post("/queries", json={"question": "I want 2 liters", "deal": DEAL_JSON, "customer": CUSTOMER_JSON}).status_code == 200
        assert customer.post("/queries", json={"question": "x", "deal": {**DEAL_JSON, "stage": "opened"}}).status_code == 422
        assert customer.post("/queries", json={"question": "x", "deal": {**DEAL_JSON, "from_turn": 1}}).status_code == 422
        with_history = {"question": "x", "history": [{"question": "hi", "answer": "hi"}], "deal": {**DEAL_JSON, "from_turn": 1}}
        assert customer.post("/queries", json=with_history).status_code == 200

    def test_the_effects_come_in_as_ops_and_go_out_with_what_is_left_to_send(self, customer: TestClient) -> None:
        """The same as the sale, and one thing more: `pending` is what this service cannot do."""
        a = built(customer, FakeAdvisor())

        r = customer.post(
            "/queries",
            json={"question": "send me the datasheet", "effects": EFFECTS_JSON["ops"]},
        )

        assert r.status_code == 200
        assert a.effects == [EFFECTS]
        assert r.json()["effects"] == EFFECTS_JSON

    def test_the_client_done_comes_in_and_the_effect_stops_being_pending(self, customer: TestClient) -> None:
        """Whoever sent the WhatsApp closes it in the next request: the id from `pending` and its reference."""
        closed = (*EFFECTS, EffectOp("done", "send_datasheet", note="wamid.HBg"))
        a = built(customer, FakeAdvisor(replace(GROUNDED, effects=closed)))

        r = customer.post(
            "/queries",
            json={
                "question": "thanks",
                "effects": [*EFFECTS_JSON["ops"], {"verb": "done", "id": "send_datasheet", "note": "wamid.HBg"}],
            },
        )

        assert a.effects == [closed]
        assert r.json()["effects"]["pending"] == []
        assert r.json()["effects"]["state"] == f"send_datasheet done ({DATASHEET})"

    def test_a_sale_from_before_done_when_is_rebuilt_and_is_not_422(self, customer: TestClient) -> None:
        """The channel keeps the sale of each conversation: one from before Sep 23, 2026 brings `completes_when`."""
        a = built(customer, FakeAdvisor())
        old = [
            {"verb": "add_step", "id": "diagnosis", "intent": "diagnose and build the cart"},
            {"verb": "add_step", "id": "pest", "intent": "find out what they are after", "completes_when": "has_search_terms", "parent": "diagnosis"},
            {"verb": "mark", "id": "pest", "status": "done"},
        ]

        r = customer.post("/queries", json={"question": "how much is the 30 cm roll?", "sale": old})

        assert r.status_code == 200
        assert a.sales == [()]

    def test_the_turn_that_only_asks_is_not_an_opinion(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(QUESTION))

        r = customer.post("/queries", json={"question": "I have a problem on the tomato"})

        data = r.json()
        assert r.status_code == 200
        assert data["grounded"] is False and data["no_search_terms"] is True
        assert data["sale"]["asks"] == {"id": "pest", "what": core_agent.ASKS["pest"]}

    def test_the_history_arrives_trimmed_to_the_last_turns(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        history = [{"question": f"p{i}", "answer": f"r{i}"} for i in range(8)]

        customer.post("/queries", json={"question": "and on banana?", "history": history})

        assert a.calls[0][1] == tuple((f"p{i}", f"r{i}") for i in range(2, 8))

    def test_a_field_that_does_not_exist_is_ignored_and_warned_about(self, customer: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        """Until Oct 9, 2026 it was 422: knowledge resent `form` and agro stopped answering (agro-00120)."""
        a = built(customer, FakeAdvisor())

        assert customer.post("/queries", json={"question": "thrips?", "session": "abc"}).status_code == 200
        assert "Query" in caplog.text and "session" in caplog.text
        assert customer.post("/queries", json={"question": "thrips", "sale": [{"verb": "mark", "id": "pest", "state": "done"}]}).status_code == 200
        assert "OpIn" in caplog.text and "state" in caplog.text
        assert a.sales[-1] == (PlanOp(verb="mark", id="pest"),)
        assert customer.post("/queries", json={"question": "   "}).status_code == 422
        assert customer.post("/queries", json={"question": ""}).status_code == 422

    def test_the_second_turn_with_what_agro_returned_is_the_same_turn(self, customer: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        """Knowledge keeps the answer and resends what is not its own: `form`, `interview`, and whatever comes."""
        a = built(customer, FakeAdvisor())
        first = customer.post("/queries", json={"question": "I want 2 liters", "deal": DEAL_JSON}).json()

        clean = {"question": "pay with link", "history": [{"question": "I want 2 liters", "answer": first["answer"]}], "deal": DEAL_JSON}
        resent = {
            **clean,
            "form": first["form"],
            "interview": {},
            "changes": first["changes"],
            "judgment": {"asks_link": 0.9},
            "restart": False,
            "messages": first["messages"],
            "deal": {**DEAL_JSON, "created_at": "2026-10-09T04:00:00Z"},
            "customer": {**CUSTOMER_JSON, "origin": "deal-won"},
        }
        assert customer.post("/queries", json=clean).status_code == 200
        caplog.clear()
        assert customer.post("/queries", json=resent).status_code == 200

        assert a.calls[-1] == a.calls[-2] and a.forms[-1] == a.forms[-2] and a.carts[-1] == a.carts[-2]
        warnings = caplog.text
        assert all(c in warnings for c in ("changes", "judgment", "restart", "messages", "created_at", "origin"))
        assert "form" not in warnings and "interview" not in warnings

    def test_a_yes_is_a_whole_turn(self, customer: TestClient) -> None:
        """In a sale the customer answers "yes", "no", "2": there is no minimum length, only blank is 422."""
        a = built(customer, FakeAdvisor())

        assert customer.post("/queries", json={"question": " yes "}).status_code == 200
        assert customer.post("/queries", json={"question": "2"}).status_code == 200
        assert [ll[0] for ll in a.calls] == ["yes", "2"]

    def test_the_turn_cut_by_the_cap_is_504_with_the_fail(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(CUT))

        r = customer.post("/queries", json={"question": "thrips on tomato?"})

        assert r.status_code == 504
        assert r.json() == {
            "detail": "loop: time cap: 9/9 s",
            "tokens": 4000,
            "tokens_input": 0,
            "tokens_cached": 0,
            "tokens_output": 0,
            "tokens_typesafe": 0,
        }, "what it cost is charged anyway"

    def test_the_cut_turn_with_prose_goes_out_200_marked(self, customer: TestClient) -> None:
        """If the loop managed to say something before the cap (a prose vetoed by `grounded`), that travels with `cut_off`."""
        from dataclasses import replace

        built(customer, FakeAdvisor(replace(CUT, text="what I managed to see", grounded=False)))

        body = customer.post("/queries", json={"question": "thrips on tomato?"}).json()

        assert body["truncated"] is True and body["answer"] == "what I managed to see"

    def test_without_answer_is_502_with_the_fails(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(EMPTY))

        r = customer.post("/queries", json={"question": "thrips on tomato?"})

        assert r.status_code == 502
        assert r.json()["detail"] == "model: the API did not answer"
        assert r.json()["tokens"] == 0

    def test_a_turn_that_raises_is_500_with_what_it_charged(self, customer: TestClient) -> None:
        cost = {"tokens": 900, "tokens_input": 800, "tokens_cached": 0, "tokens_output": 100, "tokens_typesafe": 300}
        built(customer, FakeAdvisor(error=TurnFailed(ZeroDivisionError("bug"), cost)))

        r = customer.post("/queries", json={"question": "thrips on tomato?"})

        assert r.status_code == 500
        assert r.json() == {"detail": "ZeroDivisionError: bug", **cost}

    def test_an_opinion_goes_out_200_marked(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(OPINION))

        body = customer.post("/queries", json={"question": "thrips on tomato?"}).json()

        assert body["grounded"] is False
        assert body["sources"] == []

    def test_the_catalog_says_how_much_there_is_and_how_much_fits(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert customer.get("/queries/catalog").json() == {
            "datasheets": 2,
            "kb": 8,
            "tokens_approx": 2000,
            "free_slots": 1,
            "model": None,
        }

    def test_the_catalog_brings_the_model_count_if_it_keeps_one(self, customer: TestClient) -> None:
        """With an adapter that counts (`Usage`), the `model` block states calls, attempts and the wait."""
        from catalejo.llm import Usage

        class WithCount:
            usage = Usage(calls=4, attempts=6, seconds=270.04, slowest=120.0)

        a = built(customer, FakeAdvisor())
        a.model = WithCount()  # type: ignore[attr-defined]

        assert customer.get("/queries/catalog").json()["model"] == {
            "calls": 4,
            "attempts": 6,
            "seconds": 270.0,
            "slowest": 120.0,
        }


class TestA2AErrors:
    def test_body_that_is_not_json(self, customer: TestClient) -> None:
        r = customer.post("/a2a", content=b"{no", headers={"content-type": "application/json"})

        assert r.status_code == 200
        assert r.json() == {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "the body is not JSON"}}

    def test_without_jsonrpc_envelope(self, customer: TestClient) -> None:
        r = customer.post("/a2a", json={"method": "message/send"})

        assert r.json()["error"]["code"] == -32600

    def test_unknown_method(self, customer: TestClient) -> None:
        assert rpc(customer, "agent/hello", id_="abc") == {
            "jsonrpc": "2.0",
            "id": "abc",
            "error": {"code": -32601, "message": "unknown method: 'agent/hello'"},
        }

    @pytest.mark.parametrize("method", ["message/stream", "tasks/get", "tasks/cancel", "tasks/pushNotificationConfig/set"])
    def test_what_asks_for_state_is_unsupported(self, customer: TestClient, method: str) -> None:
        built(customer, FakeAdvisor())

        assert rpc(customer, method, {})["error"]["code"] == -32004

    def test_without_message_is_invalid_params(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        assert rpc(customer, "message/send", {})["error"]["code"] == -32602
        assert rpc(customer, "message/send", {"message": {"parts": []}})["error"]["code"] == -32602

    def test_without_text_is_content_type_not_supported(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())
        params = {"message": {"parts": [{"kind": "file", "file": {"uri": "x"}}, {"kind": "text", "text": "  "}]}}

        assert rpc(customer, "message/send", params)["error"]["code"] == -32005

    def test_the_turn_cut_by_the_cap_is_internal(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(CUT))

        error = rpc(customer, "message/send", message("thrips?"))["error"]

        assert error["code"] == -32603
        assert error["message"] == "loop: time cap: 9/9 s"

    def test_without_answer_is_invalid_agent_response(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(EMPTY))

        error = rpc(customer, "message/send", message("thrips?"))["error"]

        assert error["code"] == -32006
        assert error["message"] == "model: the API did not answer"


class TestA2AMessageSend:
    def test_the_message_with_the_text_and_the_evidence(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())

        result = rpc(customer, "message/send", message("thrips on tomato?", contextId="c1", taskId="t1"))["result"]

        assert result["kind"] == "message" and result["role"] == "agent"
        assert result["messageId"]
        assert result["contextId"] == "c1" and result["taskId"] == "t1"
        assert result["parts"][0] == {"kind": "text", "text": GROUNDED.text}
        assert result["parts"][1]["kind"] == "data"
        assert result["parts"][1]["data"] == {
            "kind": "agro_evidence",
            "messages": [GROUNDED.text],
            "sources": [DATASHEET],
            "grounded": True,
            "tokens": 1200,
            "turns": 4,
            "halt": False,
            "fails": [],
            "seconds": 12.5,
            "truncated": False,
            "no_search_terms": False,
            "sale": SALE_JSON,
            "effects": EFFECTS_JSON,
        }
        assert "metadata" not in result
        assert a.calls == [("thrips on tomato?", (), 9.0)]
        assert a.sales == [()]

    def test_the_sale_comes_in_the_data_part_or_in_metadata(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        ops = SALE_JSON["ops"]
        params = {
            "message": {"parts": [{"kind": "text", "text": "thrips"}, {"kind": "data", "data": {"sale": ops}}]}
        }
        rpc(customer, "message/send", params)
        by_metadata = message("thrips")
        by_metadata["metadata"] = {"sale": ops}
        rpc(customer, "message/send", by_metadata)
        whole = message("thrips")
        whole["metadata"] = {"sale": SALE_JSON}
        rpc(customer, "message/send", whole)

        assert a.sales == [SALE, SALE, SALE]

    def test_the_payment_comes_in_metadata_and_another_value_does_not_count(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        for payment in ("pending", "refunded"):
            m = message("I already paid")
            m["metadata"] = {"payment": payment}
            rpc(customer, "message/send", m)

        assert a.payments == ["pending", ""]

    def test_the_memory_comes_in_metadata_and_malformed_is_invalid_params(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        m = message("the same")
        m["metadata"] = {"memory": MEMORY_JSON}
        rpc(customer, "message/send", m)
        bad = message("the same")
        bad["metadata"] = {"memory": {"tree": [{"l": -1, "i": 0, "text": "x"}]}}

        assert a.memories == [MEMORY]
        assert rpc(customer, "message/send", bad)["error"]["code"] == -32602

    def test_the_effects_come_in_the_data_part_or_in_metadata(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        ops = EFFECTS_JSON["ops"]
        params = {
            "message": {"parts": [{"kind": "text", "text": "the datasheet"}, {"kind": "data", "data": {"effects": ops}}]}
        }
        rpc(customer, "message/send", params)
        by_metadata = message("the datasheet")
        by_metadata["metadata"] = {"effects": ops}
        rpc(customer, "message/send", by_metadata)
        whole = message("the datasheet")
        whole["metadata"] = {"effects": EFFECTS_JSON}
        rpc(customer, "message/send", whole)

        assert a.effects == [EFFECTS, EFFECTS, EFFECTS]

    def test_a_malformed_effect_is_invalid_params_with_the_index(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())
        params = message("the datasheet")
        params["metadata"] = {"effects": [{"verb": "done", "id": "send_datasheet"}, {"verb": "resolve", "args": "x"}]}

        error = rpc(customer, "message/send", params)["error"]

        assert error["code"] == -32602
        assert "effects[1]" in error["message"] and "list of" in error["message"]

    def test_a_malformed_op_is_invalid_params_with_the_index(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())
        params = message("thrips")
        params["metadata"] = {"sale": [{"verb": "mark", "id": "pest"}, {"verb": "mark", "state": "done"}]}

        error = rpc(customer, "message/send", params)["error"]

        assert error["code"] == -32602
        assert "sale[1]" in error["message"] and "state" in error["message"]

    def test_the_turn_that_only_asks_does_not_warn_guardrails(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(QUESTION))

        result = rpc(customer, "message/send", message("I have a problem on the tomato"))["result"]

        data = result["parts"][1]["data"]
        assert data["grounded"] is False and data["no_search_terms"] is True
        assert data["sale"]["asks"]["id"] == "pest"
        assert "metadata" not in result

    def test_without_contextid_none_is_invented(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor())

        result = rpc(customer, "message/send", message("thrips?"))["result"]

        assert "contextId" not in result and "taskId" not in result

    def test_several_text_parts_are_joined(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        params = {"message": {"parts": [{"kind": "text", "text": "thrips"}, {"text": "on tomato"}]}}

        rpc(customer, "message/send", params)

        assert a.calls[0][0] == "thrips\non tomato"

    def test_the_history_comes_in_a_data_part(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        history = [{"question": f"p{i}", "answer": f"r{i}"} for i in range(7)]
        params = {
            "message": {
                "parts": [{"kind": "text", "text": "and on banana?"}, {"kind": "data", "data": {"history": history}}]
            }
        }

        rpc(customer, "message/send", params)

        assert a.calls[0][1] == tuple((f"p{i}", f"r{i}") for i in range(1, 7))

    def test_or_in_metadata_and_what_has_no_shape_is_ignored(self, customer: TestClient) -> None:
        a = built(customer, FakeAdvisor())
        params = message("and on banana?")
        params["metadata"] = {"history": [{"question": "p", "answer": "r"}, {"question": 3}, "garbage"]}

        rpc(customer, "message/send", params)

        assert a.calls[0][1] == (("p", "r"),)

    def test_an_opinion_brings_the_guardrails_warning(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(OPINION))

        result = rpc(customer, "message/send", message("thrips?"))["result"]

        assert result["parts"][1]["data"]["grounded"] is False
        (warning,) = result["metadata"]["guardrails"]
        assert warning["name"] == "grounding" and warning["applied"] is False
        assert warning["outcome"] == "no_evidence"
        assert warning["reasonCode"] == "did_not_query_catalog"
        assert warning["detail"] == "grounding: answered without run_query"

    def test_a_grounded_run_with_failures_is_incomplete(self, customer: TestClient) -> None:
        built(customer, FakeAdvisor(WITH_FAILURE))

        (warning,) = rpc(customer, "message/send", message("thrips?"))["result"]["metadata"]["guardrails"]

        assert warning["outcome"] == "incomplete"
        assert warning["reasonCode"] == "run_with_failures"
        assert warning["detail"].startswith("cite: ")


class TestCard:
    def test_the_card_points_to_the_request_host(self, customer: TestClient) -> None:
        card = customer.get("/.well-known/agent-card.json").json()

        assert card["url"] == "http://testserver/a2a"
        assert card["capabilities"] == {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False}
        assert card["skills"][0]["id"] == "agronomic_query"

    def test_public_url_rules_when_present(self, customer: TestClient) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(public_url="https://advisor.example/", _env_file=None)  # type: ignore[call-arg]

        assert customer.get("/.well-known/agent-card.json").json()["url"] == "https://advisor.example/a2a"

    def test_the_old_name_returns_the_same(self, customer: TestClient) -> None:
        assert customer.get("/.well-known/agent.json").json() == customer.get("/.well-known/agent-card.json").json()
