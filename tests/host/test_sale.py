"""The sale as it travels with the customer: the ops there and back, and what the host reads from the plan."""

from __future__ import annotations

import pytest
from catalejo.core import PlanOp
from catalejo.rlm.cells.planner import STATE

import core_agent
from host.sale import NextAsk, op_to_dict, op_from_dict, ops_from, summary, sale_to_dict


class TestOps:
    def test_there_and_back_without_the_empty_fields(self) -> None:
        op = PlanOp("add_step", "quantity", "how much area", done_when="said_quantity", padre="diagnosis")

        d = op_to_dict(op)

        assert d == {
            "verb": "add_step",
            "id": "quantity",
            "intent": "how much area",
            "done_when": "said_quantity",
            "parent": "diagnosis",
        }
        assert op_from_dict(d) == op

    def test_the_whole_seed_survives_the_trip(self) -> None:
        assert tuple(op_from_dict(op_to_dict(op)) for op in core_agent.SESSION) == core_agent.SESSION

    def test_an_unknown_key_is_an_error_and_not_a_half_op(self) -> None:
        with pytest.raises(ValueError, match="state"):
            op_from_dict({"verb": "mark", "id": "pest", "state": "done"})

    def test_without_verb_there_is_no_op(self) -> None:
        with pytest.raises(ValueError, match="verb"):
            op_from_dict({"id": "pest"})

    def test_ops_from_reads_the_list_and_names_the_index_of_the_failing_one(self) -> None:
        assert ops_from(None) == ()
        assert ops_from([]) == ()
        assert ops_from([{"verb": "mark", "id": "pest", "status": "done"}]) == (PlanOp("mark", "pest", status="done"),)
        with pytest.raises(ValueError, match=r"sale\[1\]"):
            ops_from([{"verb": "mark", "id": "pest"}, {"verb": "mark", "nope": 1}])
        with pytest.raises(ValueError, match="list"):
            ops_from({"verb": "mark"})


class TestSummary:
    def test_without_moves_there_is_no_sale(self) -> None:
        v = summary(())

        assert v.ops == () and v.state == "" and v.ask is None and v.tree == ""
        assert not v.done and v.pending == () and v.closed == ()

    def test_the_freshly_sown_seed_asks_for_the_pest(self) -> None:
        v = summary(core_agent.SESSION)

        assert v.state == "sale 0/8: next `pest`"
        assert v.stage == "diagnosis" and v.step == "pest"
        assert v.ask == NextAsk("pest", core_agent.ASKS["pest"])
        assert v.pending == ("pest", "product", "recipe", "quantity", "decision", "method", "charge", "data")
        assert v.closed == ()
        assert v.tree.startswith(STATE) and "[ ] pest" in v.tree
        assert not v.done

    def test_with_pest_and_product_closed_what_follows_is_advisor_work_and_asks_for_the_quantity(self) -> None:
        ops = (*core_agent.SESSION, PlanOp("mark", "pest", status="done"), PlanOp("mark", "product", status="done"))

        v = summary(ops)

        assert v.step == "recipe", "the active leaf is reading the datasheet, which is not asked of the customer"
        assert v.ask == NextAsk("quantity", core_agent.ASKS["quantity"]), "what gets asked is the next thing only they can close"
        assert v.closed == ("pest", "product")
        assert "quantity" in v.pending and "pest" not in v.pending

    def test_the_closed_sale(self) -> None:
        leaves = ("pest", "product", "recipe", "quantity", "decision", "method", "charge", "data")
        ops = (*core_agent.SESSION, *(PlanOp("mark", h, status="done") for h in leaves))

        v = summary(ops)

        assert v.done and v.pending == () and v.ask is None
        assert v.stage == "" and v.step == ""
        assert v.state == "sale 8/8: closed"

    def test_as_json(self) -> None:
        d = sale_to_dict(summary(core_agent.SESSION))

        assert d["ops"][0] == op_to_dict(core_agent.SESSION[0])
        assert d["asks"] == {"id": "pest", "what": core_agent.ASKS["pest"]}
        assert d["pending"][0] == "pest" and d["closed_steps"] == [] and d["closed"] is False
        assert d["stage"] == "diagnosis" and d["active"] == "pest"
        assert sale_to_dict(summary(()))["asks"] is None
