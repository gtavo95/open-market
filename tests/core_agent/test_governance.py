"""The bundle's `governance/` against the code: that the table names what the judge answers, with the threshold it acts on.

The table is data and the threshold that acts is in the code. If they diverge, `Answer.rules`
would say a rule fired when the code did nothing, or the other way around. These tests are what
keeps them together: changing one without the other fails here.
"""

from __future__ import annotations

from pathlib import Path

from core_agent.prompts.judge import (
    HANDOFF_QUESTIONS,
    HANDOFF_REASON_QUESTIONS,
    LABEL_GATES,
    PRESENTATION,
    PRODUCT,
    REPLY_QUESTIONS,
    SALE_LABELS,
    TURN_CASE,
    TURN_CASES,
)
from core_agent.roles.alerts import ALERT_THRESHOLD
from core_agent.roles.form import BILLED
from core_agent.roles.human_handoff import CASE_HANDOFF, ESCALATE_THRESHOLD, HANDOFF_ASKED
from core_agent.world.facts import LOG_FACTS
from core_agent.world.governance import ARGMAX, rules, table
from core_agent.world.question_judge import ORDER_GATES, STATE_QUESTIONS, THRESHOLD

RULES = rules()
BY_QUESTION = {r.question: r for r in RULES}
CODE = {*ORDER_GATES, *LOG_FACTS, "sale_completed", BILLED}
"""The keys `host.agent.code_facts` knows how to compute, plus the `Log` facts it could."""


def gate_question(gate: str) -> str:
    """How the table writes a `LABEL_GATES` gate: `label=a,b`."""
    label, options = LABEL_GATES[gate]
    return f"{label}={','.join(options)}"


class TestTheTable:
    def test_the_repo_bundle_carries_the_rules_with_unique_ids(self) -> None:
        ids = [r.id for r in RULES]
        assert len(ids) == 35 and len(set(ids)) == 35
        assert {i.split("/")[0] for i in ids} == {"sale", "effects", "escalation.inbound", "alerts", "case", "escalation.outbound"}
        assert all(i.endswith("_tag") for i in ids), "the `_tag` says it is a governed tag"

    def test_a_row_is_read_with_its_options_and_its_threshold(self) -> None:
        text = """Prose.

| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| x/payment | payment_method=credit,check | choice | conversation | 0.8 | takeover | card_payment |  |
| x/case | case=not_covered | choice | report | argmax | line:CASE_LINES |  | x/payment, y/other |
| x/fact | opens_a_datasheet | code | log |  | closes:recipe |  |  |
"""
        payment, case, fact = table(text)

        assert (payment.label, payment.options, payment.threshold, payment.reason) == ("payment_method", ("credit", "check"), 0.8, "card_payment")
        assert case.threshold == ARGMAX and case.same_fact == ("x/payment", "y/other")
        assert fact.threshold is None and fact.options == ()

    def test_without_the_folder_there_are_no_rules(self, tmp_path: Path) -> None:
        """A bundle from before `governance/` does not fail: `Answer.rules` comes out empty."""
        assert rules(tmp_path) == ()


class TestAgainstTheCode:
    def test_each_question_in_the_table_is_answered_by_someone(self) -> None:
        for r in RULES:
            if r.kind == "noul":
                assert r.question in STATE_QUESTIONS or r.question in REPLY_QUESTIONS, r.id
            elif r.kind == "choice" and r.label == TURN_CASE:
                assert set(r.options) <= set(TURN_CASES), r.id
            elif r.kind == "choice" and r.label in SALE_LABELS:
                assert set(r.options) <= set(SALE_LABELS[r.label]["criteria"]), r.id
            elif r.kind == "choice":
                assert r.label in {*HANDOFF_REASON_QUESTIONS, PRODUCT, PRESENTATION} and not r.options, r.id
            else:
                assert r.kind == "code" and r.question in CODE, r.id

    def test_each_question_in_the_code_has_its_row(self) -> None:
        """A new question with no row in okf does not get recorded in `Answer.rules`."""
        expected = {
            *STATE_QUESTIONS,
            *REPLY_QUESTIONS,
            *HANDOFF_REASON_QUESTIONS,
            *(gate_question(g) for g in LABEL_GATES),
            *(f"{TURN_CASE}={c}" for c in TURN_CASES if c != "normal"),
            *ORDER_GATES,
        }
        assert expected - BY_QUESTION.keys() == set()

    def test_the_table_threshold_is_the_one_the_code_uses(self) -> None:
        for r in RULES:
            if not isinstance(r.threshold, float):
                continue
            if r.id.startswith("alerts/"):
                assert r.threshold == ALERT_THRESHOLD, r.id
            elif r.question in HANDOFF_QUESTIONS:
                assert r.threshold == ESCALATE_THRESHOLD, r.id
            else:
                assert r.threshold == THRESHOLD, r.id

    def test_the_case_reason_is_the_one_the_code_sends(self) -> None:
        for case, reason in CASE_HANDOFF.items():
            assert BY_QUESTION[f"{TURN_CASE}={case}"].reason == reason, case
        assert {r.question for r in RULES if r.label == TURN_CASE and r.reason} == {f"{TURN_CASE}={c}" for c in CASE_HANDOFF}

    def test_the_inbound_reason_is_the_one_the_code_sends(self) -> None:
        for name, reason in HANDOFF_ASKED.items():
            question = gate_question(name) if name in LABEL_GATES else name
            assert BY_QUESTION[question].reason == reason, name
