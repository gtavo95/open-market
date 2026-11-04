"""A handoff reason open-market can raise reaches knowledge as one it accepts.

Knowledge turns a motivo it does not know into `otro` (`NewHandoff`, in `handoff/politica_handoff.go`) and
the case then opens as a generic one: the reason the judge worked out is lost without an error anywhere.
So this is checked against the host's own list, read from its source (skipped when it is not here).
"""

from __future__ import annotations

import re

import pytest

from core_agent.prompts import judge as prompts
from core_agent.roles import human_handoff
from wire import to_wire
from wire.tables import VALUES

from .go import needs_go, source

pytestmark = needs_go


def valid_motivos() -> set[str]:
    """The keys of `validHandoffMotivos`."""
    block = re.search(r"var validHandoffMotivos = map\[string\]bool\{(.*?)\n\}", source("handoff", "politica_handoff.go"), re.S)
    assert block, "validHandoffMotivos is no longer where it was"
    return set(re.findall(r'"([a-z_]+)":\s*true', block.group(1)))


def reasons() -> dict[str, str]:
    """Every reason the interior can put in a handoff, with where it comes from."""
    found: dict[str, str] = {}
    for reason in prompts.HANDOFF_REASONS:
        found[reason] = "the judge's choice of reason (`HANDOFF_REASONS`)"
    for case, reason in human_handoff.CASE_HANDOFF.items():
        found[reason] = f"the turn's case `{case}` (`CASE_HANDOFF`)"
    for question, reason in human_handoff.HANDOFF_ASKED.items():
        found[reason] = f"the question `{question}` (`HANDOFF_ASKED`)"
    found[human_handoff.SOLD_REASON] = "a sale that closed (`SOLD_REASON`)"
    return found


def test_the_host_list_was_read() -> None:
    valid = valid_motivos()

    assert len(valid) > 20 and {"otro", "reclamo_calidad", "venta_completada"} <= valid


@pytest.mark.parametrize("reason", sorted(reasons()))
def test_each_reason_the_interior_can_raise_is_one_the_host_accepts(reason: str) -> None:
    assert reason in VALUES["handoff_reason"], f"no twin for {reason!r}: {reasons()[reason]}"
    assert VALUES["handoff_reason"][reason] in valid_motivos()


@pytest.mark.parametrize("reason", sorted(reasons()))
def test_and_so_does_the_pending_effect_that_carries_it(reason: str) -> None:
    """End to end through the walker, in the shape of the effect that goes out (`origin` and `reason` args)."""
    key, origin = human_handoff.ORIGIN
    pending = {"id": human_handoff.HANDOFF, "kind": "handoff", "args": [[key, origin], ["reason", reason]], "executable": True}

    args = dict(to_wire("PendingOut", pending)["args"])

    assert args["reason"] in valid_motivos()
    assert args["origin"] == "solicitado_por_el_agente"


def test_every_word_of_the_table_is_a_reason_the_host_accepts() -> None:
    """The table has no entry that sends the host a motivo it would collapse to `otro`."""
    assert set(VALUES["handoff_reason"].values()) <= valid_motivos()


def test_the_host_motivos_open_market_never_raises_are_listed_for_the_record() -> None:
    """Not a gap: the host has reasons of its own (technical errors, a closed conversation, urgency). They never come from here."""
    never = valid_motivos() - set(VALUES["handoff_reason"].values())

    assert {"error_tecnico", "urgencia", "conversacion_cerrada", "tope_del_plan"} <= never
