"""The walker: what it translates, what it carries across untouched and what it says when it does not know."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from wire import to_english, to_wire
from wire.translate import _inverse

WARNINGS = "wire.translate"


def args_of(record: logging.LogRecord) -> tuple[Any, ...]:
    assert isinstance(record.args, tuple)
    return record.args


@pytest.fixture
def seen(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.WARNING, logger=WARNINGS)
    return caplog


class TestNamesAndValues:
    def test_a_field_name_and_a_value_go_both_ways(self) -> None:
        spanish = {"pregunta": "hola", "pago": "pagado", "retomada": True}
        english = {"question": "hola", "payment": "paid", "resumption": True}

        assert to_english("Query", spanish) == english
        assert to_wire("Query", english) == spanish

    def test_nested_objects_and_lists_are_walked(self) -> None:
        english = {"deal": {"kind": "quote", "stage": "in_payment", "items": [{"sku": "S", "product": "P", "quantity": 2}]}}
        spanish = {"deal": {"kind": "cita", "stage": "en_pago", "items": [{"sku": "S", "producto": "P", "cantidad": 2}]}}

        assert to_wire("Query", english) == spanish
        assert to_english("Query", spanish) == english

    def test_a_list_of_words_is_translated_word_by_word(self) -> None:
        english = {"form": {"fields": {}, "missing": ["legal_name", "nit", "payment_method"]}}
        assert to_wire("AnswerOut", english) == {"formulario": {"campos": {}, "faltan": ["razon_social", "nit", "medio_pago"]}}

    def test_what_is_not_a_name_crosses_as_it_is(self, seen: pytest.LogCaptureFixture) -> None:
        """The customer's words, numbers, booleans, nulls and the prose of the bundle are data."""
        english = {"answer": "Hola, ¿qué plaga ve?", "tokens": 12, "grounded": True, "halt": None, "sources": ["products/a.md"]}

        assert to_wire("AnswerOut", english) == {"respuesta": "Hola, ¿qué plaga ve?", "tokens": 12, "fundada": True, "halt": None, "fuentes": ["products/a.md"]}
        assert not seen.records

    def test_an_empty_word_is_nothing_and_says_nothing(self, seen: pytest.LogCaptureFixture) -> None:
        assert to_wire("OrderItem", {"state": ""}) == {"estado": ""}
        assert to_english("Query", {"pago": ""}) == {"payment": ""}
        assert to_english("Query", {"pago": None}) == {"payment": None}
        assert not seen.records

    def test_what_is_not_a_dict_goes_through(self) -> None:
        assert to_wire("AnswerOut", None) is None
        assert to_english("Query", ["x"]) == ["x"]
        assert to_wire("AnswerOut", {"sale": "not a dict", "rules": 3}) == {"venta": "not a dict", "reglas": 3}

    def test_the_input_is_not_changed(self) -> None:
        english = {"deal": {"kind": "sale", "items": [{"product": "P"}]}}
        before = json.dumps(english)

        to_wire("Query", english)

        assert json.dumps(english) == before


class TestWhatItDoesNotKnow:
    def test_a_word_outside_its_table_goes_through_and_is_said(self, seen: pytest.LogCaptureFixture) -> None:
        assert to_wire("Query", {"payment": "barter"}) == {"pago": "barter"}
        assert to_english("Query", {"pago": "trueque"}) == {"payment": "trueque"}

        assert [args_of(r)[1:] for r in seen.records] == [("barter", "payment_state"), ("trueque", "payment_state")]
        assert all(r.levelno == logging.WARNING for r in seen.records)

    def test_the_warning_says_where(self, seen: pytest.LogCaptureFixture) -> None:
        to_wire("AnswerOut", {"changes": {"items": [{"op": "swap"}]}})

        assert "AnswerOut.changes.items[].op" in seen.text
        assert "item_op" in seen.text

    def test_a_key_outside_its_shape_goes_through_and_is_said(self, seen: pytest.LogCaptureFixture) -> None:
        assert to_wire("AnswerOut", {"answer": "x", "brand_new": 1}) == {"respuesta": "x", "brand_new": 1}
        assert to_english("Query", {"pregunta": "x", "nuevo": 1}) == {"question": "x", "nuevo": 1}

        assert [args_of(r)[1] for r in seen.records] == ["brand_new", "nuevo"]

    def test_a_nested_key_is_said_where_it_is(self, seen: pytest.LogCaptureFixture) -> None:
        to_english("Query", {"deal": {"items": [{"sku": "S", "color": "rojo"}]}})

        assert "Query.deal.items[]" in seen.text and "color" in seen.text

    def test_a_blank_state_is_not_a_gap_but_an_unknown_one_is(self, seen: pytest.LogCaptureFixture) -> None:
        to_wire("OrderItem", {"state": "current"})
        assert not seen.records

        to_wire("OrderItem", {"state": "on_sale"})
        assert "datasheet_state" in seen.text


class TestOpenShapes:
    """A plan op and an effect op travel to the host and come back as they are: a key outside the table is not a gap."""

    def test_an_op_with_a_key_nobody_named_crosses_in_silence(self, seen: pytest.LogCaptureFixture) -> None:
        op = {"verb": "add_step", "id": "plaga", "padre": "diagnostico", "novelty": {"a": 1}}

        english = to_english("OpIn", op)

        assert english == {"verb": "add_step", "id": "pest", "parent": "diagnosis", "novelty": {"a": 1}}
        assert to_wire("OpIn", english) == op
        assert not seen.records

    def test_an_effect_op_with_a_key_nobody_named_crosses_in_silence(self, seen: pytest.LogCaptureFixture) -> None:
        op = {"verb": "propose", "id": "send_ficha", "kind": "document", "priority": 3}

        assert to_wire("EffectIn", to_english("EffectIn", op)) == op
        assert not seen.records

    def test_the_plan_translates_the_ids_and_what_closes_a_step(self) -> None:
        english = {"verb": "add_step", "id": "pest", "intent": "find out", "status": "", "done_when": "has_search_terms", "parent": "diagnosis"}
        spanish = {"verb": "add_step", "id": "plaga", "intent": "find out", "status": "", "done_when": "hay_con_que_buscar", "padre": "diagnostico"}

        assert to_wire("OpIn", english) == spanish
        assert to_english("OpIn", spanish) == english

    def test_the_verb_belongs_to_the_planning_library_and_stays_english(self) -> None:
        for verb in ("propose", "resolve", "done", "reject", "mark", "add_step"):
            assert to_wire("OpIn", {"verb": verb})["verb"] == verb
            assert to_wire("EffectIn", {"verb": verb})["verb"] == verb


class TestEffectArgs:
    def wire(self, args: list[Any]) -> list[Any]:
        return to_wire("PendingOut", {"id": "handoff", "kind": "handoff", "args": args, "executable": True})["args"]  # type: ignore[no-any-return]

    def english(self, args: list[Any]) -> list[Any]:
        return to_english("PendingOut", {"id": "handoff", "kind": "handoff", "args": args, "ejecutable": True})["args"]  # type: ignore[no-any-return]

    def test_the_handoff_args(self) -> None:
        english = [["origin", "requested_by_agent"], ["reason", "quality_complaint"]]
        spanish = [["origin", "solicitado_por_el_agente"], ["reason", "reclamo_calidad"]]

        assert self.wire(english) == spanish
        assert self.english(spanish) == english

    def test_the_keys_knowledge_reads_in_spanish(self) -> None:
        english = [["currency", "GTQ"], ["total", "10.00"], ["name", "Rosa"], ["recipient", "Luis"], ["phone", "5555"], ["address", "zona 1"], ["payment_method", "transfer"]]
        spanish = [["moneda", "GTQ"], ["total", "10.00"], ["nombre", "Rosa"], ["recibe", "Luis"], ["telefono", "5555"], ["direccion", "zona 1"], ["medio_pago", "transferencia"]]

        assert self.wire(english) == spanish
        assert self.english(spanish) == english

    def test_the_line_of_the_payment_link_is_json_inside_a_string(self) -> None:
        english = {"line": 1, "product": "Reapvane", "presentation": "1 L", "quantity": 2, "price": "229.00", "subtotal": "458.00", "item_code": "C1"}
        spanish = {"renglon": 1, "producto": "Reapvane", "presentacion": "1 L", "cantidad": 2, "precio": "229.00", "subtotal": "458.00", "item_code": "C1"}

        out = self.wire([["item", json.dumps(english)]])

        assert out == [["item", json.dumps(spanish)]]
        assert self.english(out) == [["item", json.dumps(english)]]

    def test_the_line_keeps_the_way_the_interior_writes_json(self) -> None:
        """Non-ASCII stays as it is (`ensure_ascii=False`), like `order.payment_args` writes it."""
        line = json.dumps({"line": 1, "product": "Fumigación"}, ensure_ascii=False)

        assert "Fumigación" in self.wire([["item", line]])[0][1]

    def test_an_item_that_is_not_a_json_object_goes_through_and_is_said(self, seen: pytest.LogCaptureFixture) -> None:
        assert self.wire([["item", "not json"], ["item", "[1]"], ["item", 3]]) == [["item", "not json"], ["item", "[1]"], ["item", 3]]
        assert len(seen.records) == 2

    def test_a_pair_that_is_not_two_strings_crosses_as_it_is(self, seen: pytest.LogCaptureFixture) -> None:
        odd = [["only-one"], ["a", "b", "c"], "text", [1, 2], None]

        assert self.wire(odd) == odd
        assert not seen.records

    def test_a_key_nobody_named_is_said(self, seen: pytest.LogCaptureFixture) -> None:
        assert self.wire([["colour", "red"]]) == [["colour", "red"]]
        assert "args_key" in seen.text

    def test_data_values_are_not_touched(self) -> None:
        """A NIT, an address, a path, a URL: the key says it is data and the value crosses as it is."""
        args = [["nit", "CF"], ["address", "link"], ["url", "https://pay.example/x"], ["path", "products/a.md"], ["file", "a.pdf"]]

        assert [v for _, v in self.wire(args)] == ["CF", "link", "https://pay.example/x", "products/a.md", "a.pdf"]

    def test_a_reason_nobody_knows_is_said_and_stays(self, seen: pytest.LogCaptureFixture) -> None:
        assert self.wire([["reason", "asks_for_human"]]) == [["reason", "asks_for_human"]]
        assert "handoff_reason" in seen.text


class TestMapsAndTheJudgment:
    def test_the_fields_of_the_form_and_the_method_they_hold(self) -> None:
        english = {"form": {"fields": {"legal_name": "Agro SA", "payment_method": "on_delivery", "nit": "CF"}, "missing": ["address"], "title": "Billing", "form_schema": []}}
        spanish = {"formulario": {"campos": {"razon_social": "Agro SA", "medio_pago": "contra_entrega", "nit": "CF"}, "faltan": ["direccion"], "titulo": "Billing", "esquema": []}}

        assert to_wire("AnswerOut", english) == spanish
        assert to_english("AnswerOut", spanish, extras=True) == english

    def test_the_changes_of_the_form(self) -> None:
        english = {"changes": {"base": 3, "items": [], "form": {"email": "a@b.c", "payment_method": "link", "legal_name": None}, "deal": "clear"}}
        spanish = {"cambios": {"base": 3, "items": [], "form": {"correo": "a@b.c", "medio_pago": "link", "razon_social": None}, "deal": "vaciar"}}

        assert to_wire("AnswerOut", english) == spanish

    def test_the_judgment(self, caplog: pytest.LogCaptureFixture) -> None:
        english = {
            "state": {"pest": "thrips", "crop": "tomato", "cart": [{"product": "Reapvane"}]},
            "p": {"has_search_terms": 0.95, "complete_invoice": 0.1, "another_question": 0.5},
            "labels": {"payment_method": "transfer", "payment_request": "account", "escalation_reason": "special_order", "case": "no_data", "free": "kept"},
            "order": {"items": [{"said": {"product": "x", "presentation": "y"}, "product": "P", "state": "discontinued"}], "total": None, "currency": "GTQ", "chargeable": False, "restarted": False},
            "already_said": ["asked for the NIT; the customer answered 1234567-8"],
            "asks_again": ["can you send me the accounts again?"],
            "unanswered": ["method"],
            "error": "",
        }

        wire = to_wire("Judgment", english)

        assert wire["p"] == {"hay_con_que_buscar": 0.95, "factura_completa": 0.1, "another_question": 0.5}
        assert wire["etiquetas"] == {"medio_de_pago": "transferencia", "pedido_de_pago": "cuenta", "motivo_de_escalada": "pedido_especial", "caso": "sin_dato", "free": "kept"}
        assert wire["pedido"]["items"][0]["estado"] == "descontinuado"
        assert wire["sin_contestar"] == ["medio"]
        assert wire["ya_dicho"] == english["already_said"] and wire["pide_de_nuevo"] == english["asks_again"], "the judge's prose crosses as it is"
        assert "1234567-8" not in caplog.text, "prose is not an unmapped value: a warning would put the customer's data in the logs"
        assert wire["estado"] == english["state"], "the model's own notes cross as they are"

    def test_what_the_model_wrote_in_the_judgment_state_is_lossless(self) -> None:
        state = {"pest": "thrips", "nested": {"list": [1, {"x": "venta"}], "pago": "pagado"}, "kind": "sale"}

        assert to_english("Judgment", to_wire("Judgment", {"state": state}))["state"] == state

    def test_the_open_dicts_of_the_sale_and_the_effects_round_trip(self) -> None:
        english = {
            "sale": {"ops": [{"verb": "mark", "id": "pest", "status": "done", "extra_key": [1, 2]}], "state": "sale 2/8", "stage": "diagnosis", "active": "pest", "pending": ["pest", "product"], "closed_steps": ["recipe"], "tree": "t", "closed": False},
            "effects": {"ops": [{"verb": "resolve", "id": "send_datasheet", "args": [["path", "products/a.md"]], "note": "n"}], "pending": [], "state": "s"},
        }

        assert to_english("AnswerOut", to_wire("AnswerOut", english), extras=True) == english

    def test_the_compactor(self) -> None:
        memory = {"messages": [{"i": 0, "kind": "advisor", "text": "t", "date": "d"}], "tree": [{"l": 1, "i": 0, "text": "n"}]}
        wire = {"memoria": {"mensajes": [{"i": 0, "kind": "asesor", "text": "t", "date": "d"}], "arbol": [{"l": 1, "i": 0, "text": "n"}]}, "max": 2}

        assert to_english("Compaction", wire) == {"memory": memory, "max": 2}
        out = {"nodes": [{"l": 0, "i": 0, "text": "n"}], "failed": [{"l": 0, "i": 1, "error": "e"}], "pending": 1, "tokens": 5, "seconds": 0.5}
        assert to_wire("CompactionOut", out) == {"nodos": [{"l": 0, "i": 0, "text": "n"}], "fallidos": [{"l": 0, "i": 1, "error": "e"}], "pendientes": 1, "tokens": 5, "segundos": 0.5}


class TestWhatKnowledgeSendsAndTheInteriorDoesNot:
    GO_ONLY = {"traza": {"pasos": []}, "turnId": "t-1", "conversationId": "c-1", "adjuntos": [{"ruta": "a.jpg", "tipo": "imagen"}], "aviso": {"motivo": "x"}, "cerrados": [1, 2]}

    def test_they_are_dropped_on_the_way_in(self, seen: pytest.LogCaptureFixture) -> None:
        assert to_english("Query", {"pregunta": "hola", **self.GO_ONLY}) == {"question": "hola"}
        assert not seen.records, "dropping them is on purpose and is not a gap"

    def test_they_are_kept_under_their_english_names_when_asked(self) -> None:
        english = to_english("Query", {"pregunta": "hola", **self.GO_ONLY}, extras=True)

        assert english == {
            "question": "hola",
            "trace": {"pasos": []},
            "turn_id": "t-1",
            "conversation_id": "c-1",
            "attachments": [{"path": "a.jpg", "type": "imagen"}],
            "notice": {"reason": "x"},
            "closed_ids": [1, 2],
        }
        assert to_wire("Query", english) == {"pregunta": "hola", **self.GO_ONLY}

    def test_the_fields_of_the_answer_the_interior_fills_go_out(self) -> None:
        llm = {"provider": "openai", "model": "m", "effort": "low"}

        assert to_wire("AnswerOut", {"llm": llm, "model": {"calls": 1, "attempts": 2, "seconds": 3.0, "slowest": 1.5}, "trace": None}) == {
            "llm": {"proveedor": "openai", "modelo": "m", "esfuerzo": "low"},
            "modelo": {"llamadas": 1, "intentos": 2, "segundos": 3.0, "mas_lenta": 1.5},
            "traza": None,
        }

    def test_a_failed_turn_carries_what_it_charged(self) -> None:
        failed = {
            "detail": "ZeroDivisionError: bug",
            "tokens": 900,
            "tokens_input": 800,
            "tokens_cached": 0,
            "tokens_output": 100,
            "tokens_typesafe": 300,
            "llm": {"provider": "muse", "model": "m", "effort": ""},
        }

        assert to_wire("FailedTurnOut", failed) == {
            "detail": "ZeroDivisionError: bug",
            "tokens": 900,
            "tokens_entrada": 800,
            "tokens_cacheados": 0,
            "tokens_salida": 100,
            "tokens_typesafe": 300,
            "llm": {"proveedor": "muse", "modelo": "m", "esfuerzo": ""},
        }


class TestInjectivity:
    def test_a_table_that_cannot_turn_back_is_refused(self) -> None:
        with pytest.raises(ValueError, match="one to one"):
            _inverse("t", {"a": "x", "b": "x"})

    def test_one_that_can_is_inverted(self) -> None:
        assert _inverse("t", {"a": "x", "b": "y"}) == {"x": "a", "y": "b"}
