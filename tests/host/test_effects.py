"""The effects as they travel with the customer: the ops there and back, and what is left to send."""

from __future__ import annotations

import pytest
from catalejo.core import EffectOp

import core_agent
from host.effects import (
    NEEDS_ARGS,
    Pending,
    effects_to_dict,
    op_to_dict,
    op_from_dict,
    ops_from,
    summary,
)

DATASHEET = "products/hyphavane.md"


class TestOps:
    def test_there_and_back_without_the_empty_fields(self) -> None:
        op = EffectOp("resolve", "send_datasheet", args=(("path", DATASHEET), ("path", "products/other.md")))

        d = op_to_dict(op)

        assert d == {"verb": "resolve", "id": "send_datasheet", "args": [["path", DATASHEET], ["path", "products/other.md"]]}
        assert op_from_dict(d) == op

    def test_a_propose_carries_no_args(self) -> None:
        op = EffectOp("propose", "send_payment_accounts", "bank_account")

        assert op_to_dict(op) == {"verb": "propose", "id": "send_payment_accounts", "kind": "bank_account"}
        assert op_from_dict(op_to_dict(op)) == op

    def test_the_client_done_is_an_op_like_the_others(self) -> None:
        """What whoever sent the WhatsApp writes: the id they got in `pending` and the reference."""
        d = {"verb": "done", "id": "send_datasheet", "note": "wamid.HBg"}

        assert op_from_dict(d) == EffectOp("done", "send_datasheet", note="wamid.HBg")

    def test_a_key_that_does_not_exist_is_an_error_and_is_not_ignored(self) -> None:
        with pytest.raises(ValueError, match="keys that do not exist"):
            op_from_dict({"verb": "done", "id": "send_datasheet", "state": "ready"})

    def test_without_verb_there_is_no_op(self) -> None:
        with pytest.raises(ValueError, match="without `verb`"):
            op_from_dict({"id": "send_datasheet"})

    def test_args_that_are_not_pairs_of_strings(self) -> None:
        with pytest.raises(ValueError, match=r"args\[0\] is not a"):
            op_from_dict({"verb": "resolve", "id": "send_datasheet", "args": [[DATASHEET]]})
        with pytest.raises(ValueError, match=r"args\[0\]: the key and the value are strings"):
            op_from_dict({"verb": "resolve", "id": "send_datasheet", "args": [["path", 3]]})
        with pytest.raises(ValueError, match="list of"):
            op_from_dict({"verb": "resolve", "id": "send_datasheet", "args": {"path": DATASHEET}})

    def test_the_list_says_which_one_broke(self) -> None:
        with pytest.raises(ValueError, match=r"effects\[1\]: op without `verb`"):
            ops_from([{"verb": "propose", "id": "x", "kind": "document"}, {"id": "y"}])
        with pytest.raises(ValueError, match="must be a list"):
            ops_from({"ops": []})
        assert ops_from(None) == ()


class TestSummary:
    def test_what_is_proposed_and_resolved_is_what_has_to_be_sent(self) -> None:
        ops = (
            EffectOp("propose", "send_datasheet", "document"),
            EffectOp("resolve", "send_datasheet", args=(("path", DATASHEET),)),
        )

        e = summary(ops)

        assert e.ops == ops
        assert e.pending == (Pending("send_datasheet", "document", (("path", DATASHEET),), True),)
        assert e.state == f"send_datasheet proposed ({DATASHEET})"

    def test_what_the_client_closed_is_no_longer_pending(self) -> None:
        """The `done` comes from the customer in the next request: the turn that reads it does not ask for it again."""
        ops = (
            EffectOp("propose", "send_datasheet", "document"),
            EffectOp("resolve", "send_datasheet", args=(("path", DATASHEET),)),
            EffectOp("done", "send_datasheet", note="wamid.HBg"),
        )

        e = summary(ops)

        assert e.pending == ()
        assert e.state == f"send_datasheet done ({DATASHEET})"

    def test_a_proposed_one_without_args_is_not_executable(self) -> None:
        """The writer cited `none`: there is no datasheet to send, and what is due is a `reject`."""
        e = summary((EffectOp("propose", "send_datasheet", "document"),))

        assert e.pending == (Pending("send_datasheet", "document", (), False),)

    def test_the_account_needs_no_args(self) -> None:
        """`send_payment_accounts` has no resolver: the host knows the account, it does not come out of the turn."""
        e = summary((EffectOp("propose", "send_payment_accounts", "bank_account"),))

        assert e.pending == (Pending("send_payment_accounts", "bank_account", (), True),)

    def test_the_escalation_is_a_pending_one_with_its_reason(self) -> None:
        """The `handoff` goes out the same way as the datasheet: `kind` is where it is routed, `args` what it is about."""
        args = (("origin", "requested_by_agent"), ("reason", "quality_complaint"))
        e = summary((EffectOp("propose", core_agent.HANDOFF, core_agent.HANDOFF, args),))

        assert e.pending == (Pending("handoff", "handoff", args, True),)
        assert e.state == "handoff proposed (requested_by_agent, quality_complaint)"

    def test_without_moves_there_is_no_line(self) -> None:
        e = summary(())

        assert e.ops == () and e.pending == () and e.state == ""

    def test_as_json(self) -> None:
        d = effects_to_dict(summary((EffectOp("propose", "send_payment_accounts", "bank_account"),)))

        assert d == {
            "ops": [{"verb": "propose", "id": "send_payment_accounts", "kind": "bank_account"}],
            "pending": [{"id": "send_payment_accounts", "kind": "bank_account", "args": [], "executable": True}],
            "state": "send_payment_accounts proposed",
        }


class TestTheExampleTable:
    def test_the_ids_are_the_agent_ones(self) -> None:
        """A new intent in the agent and this host does not know it: `pending` passes it anyway, but the test warns."""
        assert set(core_agent.EFFECT_RULES) == {"send_datasheet", "send_payment_accounts", "send_catalog", "send_payment_link", "sap_draft"}

    def test_the_escalation_is_not_an_intent(self) -> None:
        """`human_handoff` proposes it at the end of the turn, not `propose_effects`: it is not in `EFFECT_RULES` and needs no resolving."""
        assert core_agent.HANDOFF not in core_agent.EFFECT_RULES
        assert core_agent.HANDOFF not in NEEDS_ARGS

    def test_those_that_need_args_are_those_the_agent_resolves(self) -> None:
        """`NEEDS_ARGS` is a copy of the `NEEDS_ARGS` of `advisor`, which `__all__` does not export."""
        from core_agent.roles.effects import NEEDS_ARGS

        assert NEEDS_ARGS == NEEDS_ARGS
