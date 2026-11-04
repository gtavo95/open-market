"""The tables of the wire against what they describe: the schemas, the interior's vocabularies and themselves.

A table is a promise that every word the interior can say has its Spanish twin, and a promise nobody
checks goes stale the day a reason or a question is added. These tests read the vocabularies from
the live interior (the modules, the schemas, the bundle's form and format page), so a new word
that is not in `wire/tables.py` turns one of them red. The walker would carry it across unchanged
and log a WARNING; this is where it is noticed before that.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel

import core_agent
from core_agent.prompts import judge as prompts
from core_agent.roles import human_handoff
from core_agent.roles.effects import EFFECT_RULES
from core_agent.roles.form import BILLED
from core_agent.world import catalog, form
from core_agent.world.facts import LOG_FACTS
from core_agent.world.order import Item, order_dict, payment_args
from core_agent.world.question_judge import ORDER_GATES, Judgment
from schemas import compaction as compaction_schemas
from schemas import queries as query_schemas
from wire.tables import KEYED, NOT_ON_THE_WIRE, OPEN, SHAPES, VALUES
from wire.translate import BACKWARD

FORMAT_PAGE = Path(__file__).resolve().parents[2] / "okf" / "FORMAT.md"


def schema_classes() -> dict[str, type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for module in (query_schemas, compaction_schemas):
        for name, obj in vars(module).items():
            if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj.__module__ == module.__name__:
                found[name] = obj
    return found


def literal(cls: type[BaseModel], name: str) -> set[str]:
    """The strings a `Literal` field allows, looking through `Optional`."""
    found: set[str] = set()
    stack = [cls.model_fields[name].annotation]
    while stack:
        t = stack.pop()
        if get_origin(t) is Literal:
            found |= {a for a in get_args(t) if isinstance(a, str)}
        else:
            stack.extend(get_args(t))
    return found


def words(table: str) -> set[str]:
    return set(VALUES[table])


class TestTheTablesThemselves:
    @pytest.mark.parametrize("table", sorted(VALUES))
    def test_each_value_table_turns_back(self, table: str) -> None:
        assert len(BACKWARD[table]) == len(VALUES[table]), "two English words share a Spanish one"
        assert {BACKWARD[table][es] for es in BACKWARD[table]} == set(VALUES[table])

    @pytest.mark.parametrize("table", sorted(VALUES))
    def test_no_word_is_blank(self, table: str) -> None:
        """Empty means nothing on both sides and is never looked up."""
        assert all(en.strip() and es.strip() for en, es in VALUES[table].items())

    @pytest.mark.parametrize("shape", sorted(SHAPES))
    def test_each_shape_has_one_name_per_field_in_each_tongue(self, shape: str) -> None:
        fields = SHAPES[shape]
        assert len({f.wire for f in fields.values()}) == len(fields)

    def test_every_reference_exists(self) -> None:
        for shape, fields in SHAPES.items():
            for en, f in fields.items():
                where = f"{shape}.{en}"
                assert not f.shape or f.shape in SHAPES, where
                assert not f.table or f.table in VALUES, where
                assert not f.keyed or f.keyed in KEYED, where
                if f.kind in ("object", "list"):
                    assert f.shape, f"{where}: a nested value needs its shape"
                if f.keyed:
                    assert f.kind == "map", f"{where}: only a map picks a table by key"
        for name, by_key in KEYED.items():
            assert set(by_key.values()) <= set(VALUES), name

    def test_the_open_shapes_are_shapes(self) -> None:
        assert OPEN <= set(SHAPES)

    def test_extras_are_only_what_the_schema_does_not_have(self) -> None:
        """An `extra` field is knowledge's alone; if the schema grows it, the table must stop calling it extra."""
        classes = schema_classes()
        for shape, fields in SHAPES.items():
            if shape in classes:
                assert not {en for en, f in fields.items() if f.extra} & set(classes[shape].model_fields), shape


class TestTheShapesAgainstTheSchemas:
    def test_every_class_of_the_schemas_has_its_shape(self) -> None:
        missing = set(schema_classes()) - set(SHAPES) - NOT_ON_THE_WIRE
        assert not missing, f"a class that crosses the wire and has no shape: {sorted(missing)}"

    def test_the_classes_that_are_not_on_the_wire_are_the_ones_said(self) -> None:
        assert NOT_ON_THE_WIRE <= set(schema_classes())
        assert not NOT_ON_THE_WIRE & set(SHAPES)

    @pytest.mark.parametrize("name", sorted(set(schema_classes()) - NOT_ON_THE_WIRE))
    def test_a_shape_names_exactly_the_fields_of_its_class(self, name: str) -> None:
        mine = {en for en, f in SHAPES[name].items() if not f.extra}
        assert mine == set(schema_classes()[name].model_fields)

    def test_the_shapes_without_a_class_are_the_objects_inside_open_dicts(self) -> None:
        """What the schemas leave as a free dict (the judgment, an effect's args) and the wire still names."""
        assert set(SHAPES) - set(schema_classes()) == {"ArgsItem", "Attachment", "Judgment", "LLM", "Notice", "Order", "OrderItem", "Said"}

    def test_the_nested_shapes_are_the_ones_the_schema_nests(self) -> None:
        """`Query.deal` is a `DealIn`: when the annotation names a class, the shape the field points at is that class.

        Where the schema says a free `dict` (`SaleOut.ops`, `SaleOut.judgment`) the table is what names the inside.
        """
        classes = schema_classes()
        for shape, fields in SHAPES.items():
            if shape not in classes:
                continue
            for en, f in fields.items():
                if f.extra:
                    continue
                text = str(classes[shape].model_fields[en].annotation)
                named = [n for n in classes if re.search(rf"\b{n}\b", text)]
                assert named == ([f.shape] if named else []), f"{shape}.{en} points at {f.shape!r}, the schema says {text}"


class TestEveryWordTheInteriorSaysHasItsTwin:
    def test_the_values_the_schemas_allow(self) -> None:
        classes = query_schemas
        assert literal(classes.ItemChangeOut, "op") == words("item_op")
        assert literal(classes.ChangesOut, "deal") == words("changes_deal")
        assert literal(classes.DealIn, "kind") == words("deal_kind")
        assert literal(classes.DealIn, "stage") == words("deal_stage")
        assert literal(classes.Query, "payment") == words("payment_state")

    def test_the_plan_ids_and_what_closes_them(self) -> None:
        ids = {op.id for op in core_agent.SESSION}
        assert ids <= words("plan_id"), sorted(ids - words("plan_id"))
        assert words("plan_id") <= ids, "a plan id the sale no longer has"
        assert {op.done_when for op in core_agent.SESSION if op.done_when} <= words("question")

    def test_the_questions_the_judge_answers(self) -> None:
        live = (
            set(prompts.SALE_QUESTIONS)
            | set(prompts.LABEL_GATES)
            | set(prompts.REPLY_QUESTIONS)
            | set(prompts.HANDOFF_ASKS)
            | set(prompts.ALERT_ASKS)
            | set(ORDER_GATES)
            | set(LOG_FACTS)
            | {BILLED}
        )
        assert live <= words("question"), sorted(live - words("question"))
        assert words("question") <= live, f"a question the judge no longer asks: {sorted(words('question') - live)}"

    def test_the_labels_the_judge_reads(self) -> None:
        live = {prompts.PAYMENT_METHOD, prompts.PAYMENT_ASK, prompts.HANDOFF_REASON, prompts.TURN_CASE}
        assert live == words("label")
        assert KEYED["label_value"].keys() == live

    def test_the_values_of_each_label(self) -> None:
        assert set(prompts.PAYMENT_METHODS) == words("payment_methods")
        assert set(prompts.PAYMENT_ASKS) == words("payment_requests")
        assert set(prompts.TURN_CASES) == words("turn_case")
        assert KEYED["label_value"][prompts.PAYMENT_METHOD] == "payment_methods"
        assert KEYED["label_value"][prompts.PAYMENT_ASK] == "payment_requests"
        assert KEYED["label_value"][prompts.HANDOFF_REASON] == "handoff_reason"
        assert KEYED["label_value"][prompts.TURN_CASE] == "turn_case"

    def test_every_handoff_reason_the_interior_can_carry(self) -> None:
        live = set(prompts.HANDOFF_REASONS) | set(human_handoff.CASE_HANDOFF.values()) | set(human_handoff.HANDOFF_ASKED.values())
        live |= {human_handoff.SOLD_REASON}
        assert live <= words("handoff_reason"), sorted(live - words("handoff_reason"))
        assert words("handoff_reason") <= live, f"a reason nobody can emit: {sorted(words('handoff_reason') - live)}"

    def test_the_origin_of_a_handoff(self) -> None:
        key, value = human_handoff.ORIGIN
        assert value in words("handoff_origin")
        assert key in words("args_key") and KEYED["args_value"][key] == "handoff_origin"

    def test_the_effects_the_interior_proposes(self) -> None:
        live = set(EFFECT_RULES) | {human_handoff.HANDOFF, human_handoff.TAKEOVER}
        assert live <= words("effect_id"), sorted(live - words("effect_id"))

    def test_the_billing_form(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(catalog, "BUNDLE", catalog.CATALOG)
        ids = {f["id"] for f in form.fields()}
        assert ids, "the bundle's form did not load"
        assert ids == words("form_field")
        assert KEYED["form_value"] == {form.PAYMENT: "payment_methods"}
        options = {o for f in form.fields() for o in f.get("options", [])}
        assert options <= words("payment_methods")

    def test_the_states_of_a_datasheet(self) -> None:
        row = next(line for line in FORMAT_PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("| `state` |"))
        assert set(re.findall(r"`(\w+)`", row)[1:]) == words("datasheet_state")

    def test_the_memory_kinds_are_the_ones_the_host_speaks(self) -> None:
        assert words("memory_kind") == {"customer", "advisor", "operator", "system"}

    def test_the_keys_of_an_effects_args(self) -> None:
        """The keys the interior writes into args (`order.payment_args`, the handoff, the resolvers) and the host reads."""
        item = Item("x", "y", 2.0, product="P", presentation="1 L", unit_price=10.0, status="current", currency="GTQ", code="C")
        keys = {k for k, _ in payment_args((item,))}
        assert keys == {"item", "currency", "total"}
        assert keys <= words("args_key")
        assert {"path", "origin", "reason"} <= words("args_key")
        assert set(KEYED["args_value"]) <= words("args_key")


class TestTheNamesInsideTheOpenDicts:
    """A judgment, an order and a payment line are plain dicts in the schemas; the tables name their insides."""

    ITEM = Item(
        "reapvane", "1 L", 2.0, product="Reapvane", path="products/reapvane.md", presentation="1 L", unit_price=229.0, status="current", currency="GTQ", code="C1"
    )

    def judgment(self) -> dict[str, Any]:
        return Judgment({"pest": "thrips"}, {"has_search_terms": 0.9}, order=(self.ITEM,), said=("pest",), again=("quantity",), unanswered=frozenset({"quantity"})).as_dict()

    def test_the_judgment(self) -> None:
        assert set(self.judgment()) == set(SHAPES["Judgment"])

    def test_the_order(self) -> None:
        assert set(self.judgment()["order"]) == set(SHAPES["Order"])
        assert set(order_dict((self.ITEM,))) | {"restarted"} == set(SHAPES["Order"])

    def test_a_line_of_the_order(self) -> None:
        line = self.ITEM.as_dict()
        assert set(line) == {en for en, f in SHAPES["OrderItem"].items() if not f.extra}
        assert set(line["said"]) == set(SHAPES["Said"])

    def test_a_line_of_the_payment_link(self) -> None:
        import json

        pairs = dict(payment_args((self.ITEM,)))
        assert set(json.loads(pairs["item"])) == set(SHAPES["ArgsItem"])

    def test_the_state_of_a_datasheet_in_a_line_is_translated(self) -> None:
        assert SHAPES["OrderItem"]["state"].table == "datasheet_state"


def test_the_helper_that_walks_the_shapes_sees_them_all() -> None:
    def names() -> Iterator[str]:
        for fields in SHAPES.values():
            for f in fields.values():
                if f.shape:
                    yield f.shape

    assert set(names()) <= set(SHAPES)
