"""`Answer.rules`: each rule of the table with what it read, whether it fired or not, deciding nothing."""

from __future__ import annotations

from typing import Any

from core_agent.world.governance import table
from core_agent.world.question_judge import Answered, Judgment, Pick, TurnCase
from host.rules import turn_rules

TABLE = table("""
| id | question | type | reads | threshold | action | crm_reason | same_fact |
|---|---|---|---|---|---|---|---|
| sale/purchase_tag | wants_to_buy | noul | conversation | 0.8 | closes:decision |  |  |
| sale/method_tag | payment_method=link,transfer | choice | conversation | 0.8 | closes:method |  |  |
| case/not-covered_tag | case=not_covered | choice | report | argmax | line:CASE_LINES |  |  |
| case/no-data_tag | case=no_data | choice | report | argmax | line:CASE_LINES |  |  |
| outbound/person_tag | did_not_give_what_was_asked | noul | answer | 0.5 | handoff |  |  |
| outbound/reason_tag | escalation_reason | choice | answer | argmax | handoff |  |  |
| sale/quantities_tag | order_with_quantities | code | cart |  | closes:quantity |  |  |
| sale/datasheet_tag | datasheet | choice | cart | argmax | cart_line:product |  |  |
""")

JUDGMENT = Judgment(
    state={},
    p={"wants_to_buy": 0.62},
    labels={"payment_method": "link"},
    dist={"payment_method": {"link": 0.55, "transfer": 0.3, "none": 0.15}},
)
ANSWER = Answered(p={"did_not_give_what_was_asked": 0.67}, labels={"escalation_reason": "product_not_found"}, label_p={"escalation_reason": 0.81})


def by_id(rules: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rules}


class TestTheTurnRules:
    def test_one_entry_per_row_in_table_order(self) -> None:
        rules = turn_rules(TABLE)

        assert [r["id"] for r in rules] == [r.id for r in TABLE]
        assert all(r["p"] is None and r["fired"] is False for r in rules), "with nothing asked, nothing was read"

    def test_the_one_below_the_threshold_still_goes_out_with_its_p(self) -> None:
        r = by_id(turn_rules(TABLE, judgment=JUDGMENT))["sale/purchase_tag"]

        assert r == {"id": "sale/purchase_tag", "p": 0.62, "threshold": 0.8, "fired": False, "action": "closes:decision"}

    def test_a_label_adds_up_its_options_against_the_threshold(self) -> None:
        r = by_id(turn_rules(TABLE, judgment=JUDGMENT))["sale/method_tag"]

        assert (r["p"], r["fired"]) == (0.85, True)

    def test_the_case_fires_only_its_option(self) -> None:
        case = TurnCase("not_covered", {"not_covered": 0.91, "no_data": 0.05, "normal": 0.04})

        rules = by_id(turn_rules(TABLE, case=case))

        assert (rules["case/not-covered_tag"]["p"], rules["case/not-covered_tag"]["fired"]) == (0.91, True)
        assert (rules["case/no-data_tag"]["p"], rules["case/no-data_tag"]["fired"]) == (0.05, False)

    def test_the_failed_case_fires_all_its_lines_without_p(self) -> None:
        """It is what the writer received: the four lines, without anybody saying so."""
        rules = by_id(turn_rules(TABLE, case=TurnCase("", {}, error="HTTP 503")))

        assert all(rules[i]["p"] is None and rules[i]["fired"] for i in ("case/not-covered_tag", "case/no-data_tag"))

    def test_the_answer_brings_the_guardian_and_the_reason_with_its_option(self) -> None:
        rules = by_id(turn_rules(TABLE, reply=ANSWER))

        assert (rules["outbound/person_tag"]["p"], rules["outbound/person_tag"]["fired"]) == (0.67, True)
        assert rules["outbound/reason_tag"]["option"] == "product_not_found" and rules["outbound/reason_tag"]["p"] == 0.81

    def test_a_judgment_with_an_error_reads_nothing(self) -> None:
        down = Judgment(state={}, p={}, error="reading: HTTP 503")

        r = by_id(turn_rules(TABLE, judgment=down))["sale/purchase_tag"]

        assert r["p"] is None and r["fired"] is False

    def test_a_code_rule_is_one_or_zero(self) -> None:
        yes = by_id(turn_rules(TABLE, codes={"order_with_quantities": True}))["sale/quantities_tag"]
        no = by_id(turn_rules(TABLE, codes={"order_with_quantities": False}))["sale/quantities_tag"]

        assert (yes["p"], yes["fired"], yes["threshold"]) == (1.0, True, None)
        assert (no["p"], no["fired"]) == (0.0, False)

    def test_a_choice_per_line_brings_each_pick_and_the_weakest(self) -> None:
        picks = (Pick("the reapvane", "Reapvane", 0.91), Pick("triVX", "Tri VX 35 EW", 0.64))
        with_picks = by_id(turn_rules(TABLE, judgment=Judgment(state={}, p={}, picks={"datasheet": picks})))["sale/datasheet_tag"]
        without = by_id(turn_rules(TABLE, judgment=JUDGMENT))["sale/datasheet_tag"]

        assert (with_picks["p"], with_picks["fired"]) == (0.64, True)
        assert with_picks["lines"] == [{"said": "the reapvane", "option": "Reapvane", "p": 0.91}, {"said": "triVX", "option": "Tri VX 35 EW", "p": 0.64}]
        assert (without["p"], without["fired"]) == (None, False) and "lines" not in without
