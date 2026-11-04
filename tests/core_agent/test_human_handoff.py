"""The escalation wired in `roles/human_handoff.py`: when the turn passes to a person, with what reason and at what cost."""

from __future__ import annotations

import pytest

from core_agent.agent import turn
from core_agent.prompts.judge import HANDOFF_ASKS, LABEL_GATES, SALE_LABELS, HANDOFF_REASON, HANDOFF_REASON_QUESTIONS, SALE_QUESTIONS, HANDOFF_REASONS, HANDOFF_QUESTIONS, LEFT_WITHOUT, REPLY_REASONS, TAKEN_OVER, TURN_CASES
from core_agent.world.question_judge import STATE_QUESTIONS
from core_agent.prompts.writer import HANDOFF_LINES
from core_agent.roles.effects import capture_effects, effects_state, host_sim, fill_effect_args
from core_agent.roles.human_handoff import ASKED_WHO, CASE_HANDOFF, ESCALATE_THRESHOLD, HANDOFF, HANDOFF_ASKED, ORIGIN, SOLD_REASON, TAKEOVER, asked_handoff, asked_verdict, human_handoff, sale_closed, sold, verdict
from core_agent.roles.sale import SESSION
from core_agent.roles.sale import close_sale_steps
from core_agent.world.dialogue import History, wrap
from core_agent.world.question_judge import THRESHOLD, QuestionJudge
from catalejo.core import ZERO, Cell, EffectOp, Log, Message, PlanOp, Role, Status, effects_of, merge, then
from tests.doubles import Echo, ScriptedJudge, question_judge_with

QUESTION = "how many days is the Larvane pre-harvest interval on tomato?"

NO_ANSWER = "That detail is not in the datasheet for Larvane."
"""What triggers the escalation: a catalog refusal. The double recognises it through `WORDS`."""

WITH_ANSWER = "I recommend Larvane, certified for tomato: 1 L/ha."


def envelope(question: str = QUESTION, history: History = (), effects: tuple[EffectOp, ...] = (), course: tuple[PlanOp, ...] = ()) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, history)),), effects=effects, course=course)


def with_closed(*ids: str) -> tuple[PlanOp, ...]:
    """The sale seeded with those leaves closed."""
    return (*SESSION, *(PlanOp("mark", i, status="done") for i in ids))


SOLD = with_closed("pest", "product", "recipe", "quantity", "decision", "method", "data")
ACCOUNT = (EffectOp("propose", "send_payment_accounts", "bank_account"), EffectOp("done", "send_payment_accounts"))
DATA = "NIT 1234567-8, under the name Juan Pérez, he receives it, 5555-1234, 3a calle 4-15 zona 1 Chimaltenango"


def turn_log(answer: str, effects: tuple[EffectOp, ...] = ()) -> Log:
    """The Log of a turn with the answer already written, which is all the escalation looks at."""
    return merge(envelope(effects=effects), Log(said=(Message(Role.ASSISTANT, answer),)))


class TestTheReasonsTable:
    def test_the_reason_is_a_choice_option_and_the_crm_label(self) -> None:
        assert HANDOFF_REASON_QUESTIONS[HANDOFF_REASON]["criteria"].items() <= HANDOFF_REASONS.items()
        assert HANDOFF_REASON_QUESTIONS[HANDOFF_REASON]["type"] == "choice"

    def test_the_outbound_guardian_does_not_pick_a_reason_that_turns_off_the_advisor(self) -> None:
        """With the answer already written, turning off the advisor left the customer not knowing that a person now answers them."""
        assert TAKEN_OVER <= HANDOFF_REASONS.keys()
        assert REPLY_REASONS.keys() == HANDOFF_REASONS.keys() - TAKEN_OVER
        assert not TAKEN_OVER & HANDOFF_REASON_QUESTIONS[HANDOFF_REASON]["criteria"].keys()

    def test_the_ones_that_turn_off_the_advisor_are_the_inbound_ones(self) -> None:
        """The "heavy" ones of the host come only from `HANDOFF_ASKED` and from the closed sale: both know before writing."""
        assert TAKEN_OVER == {*HANDOFF_ASKED.values(), SOLD_REASON}

    def test_there_is_a_reason_for_what_does_not_fit(self) -> None:
        """A `choice` always chooses: without an unclassified bin it would choose wrong instead of not choosing."""
        assert "other" in HANDOFF_REASONS

    def test_the_escalation_is_not_a_sale_gate(self) -> None:
        """It is asked about the answer, not about the customer's state: it does not go in `SALE_QUESTIONS`."""
        assert not SALE_QUESTIONS.keys() & {*HANDOFF_QUESTIONS, HANDOFF_REASON}

    def test_the_cases_that_escalate_are_cases_and_their_reason_is_the_guardian_s(self) -> None:
        """A case escalates without turning off the advisor: its reason is one of those the guardian can pick."""
        assert CASE_HANDOFF.keys() <= TURN_CASES.keys() - {"normal", "we_do_not_sell"}
        assert set(CASE_HANDOFF.values()) <= REPLY_REASONS.keys()


class TestTheVerdict:
    async def test_a_catalog_refusal_escalates_with_its_reason(self) -> None:
        out = await verdict(question_judge_with(label="unverifiable_specification"))(turn_log(NO_ANSWER))

        assert out == (ORIGIN, ("reason", "unverifiable_specification"))

    async def test_an_answer_with_the_catalog_does_not_escalate(self) -> None:
        assert await verdict(question_judge_with())(turn_log(WITH_ANSWER)) is None

    async def test_without_an_answer_it_neither_escalates_nor_goes_to_the_network(self) -> None:
        """The escalation runs in `after`, but a turn that went down leaves no prose: there is nothing to judge."""
        judge_ = ScriptedJudge()

        assert await verdict(QuestionJudge(judge_, Echo()))(envelope()) is None
        assert judge_.calls == 0

    async def test_the_threshold_decides(self) -> None:
        just_below = question_judge_with({LEFT_WITHOUT: ESCALATE_THRESHOLD - 0.01})
        just_above = question_judge_with({LEFT_WITHOUT: ESCALATE_THRESHOLD})

        assert await verdict(just_below)(turn_log(NO_ANSWER)) is None
        assert await verdict(just_above)(turn_log(NO_ANSWER)) is not None

    async def test_one_of_the_three_is_enough(self) -> None:
        """A complaint answered well: the advisor left nothing ungiven and did not pass it on, and it escalates anyway."""
        out = await verdict(question_judge_with(label="quality_complaint"))(turn_log("I am sorry the Larvane arrived damaged."))

        assert out == (ORIGIN, ("reason", "quality_complaint"))

    async def test_the_case_of_the_turn_escalates_by_code_with_its_reason(self) -> None:
        """The writer received the `no_data` line: it escalates without reading the answer, and with the reason from the table."""
        judge_ = ScriptedJudge(label="no_data")
        question_judge = QuestionJudge(judge_, Echo())
        seen = turn_log(WITH_ANSWER)
        await question_judge.turn_case(seen, "the datasheet does not carry the pre-harvest interval")
        calls = judge_.calls

        assert await verdict(question_judge)(seen) == (ORIGIN, ("reason", CASE_HANDOFF["no_data"]))
        assert judge_.calls == calls

    async def test_a_case_that_does_not_escalate_leaves_it_to_the_guardian(self) -> None:
        for case, answer, escalates in (("we_do_not_sell", WITH_ANSWER, False), ("normal", NO_ANSWER, True)):
            question_judge = QuestionJudge(ScriptedJudge(label=case), Echo())
            seen = turn_log(answer)
            await question_judge.turn_case(seen, "report")

            assert (await verdict(question_judge)(seen) is not None) is escalates, case

    async def test_the_failed_case_leaves_it_to_the_guardian(self) -> None:
        """With the case down the writer received all four lines and chose herself: what she said is read by the guardian."""
        question_judge = QuestionJudge(ScriptedJudge(down=True), Echo())
        seen = turn_log(WITH_ANSWER)
        with pytest.raises(Exception):
            await question_judge.turn_case(seen, "report")

        with pytest.raises(Exception, match="reading the answer"):
            await verdict(question_judge)(seen)

    async def test_without_a_judge_it_raises_instead_of_never_escalating(self) -> None:
        with pytest.raises(Exception, match="nobody answers"):
            await verdict(None)(turn_log(NO_ANSWER))

    async def test_the_judge_down_raises(self) -> None:
        with pytest.raises(Exception, match="reading the answer"):
            await verdict(question_judge_with(down=True))(turn_log(NO_ANSWER))


class TestTheCell:
    async def test_it_proposes_the_handoff_with_origin_and_reason(self) -> None:
        out = await human_handoff(question_judge_with(label="product_not_found"))(turn_log(NO_ANSWER))

        assert out.effects == (
            EffectOp("propose", HANDOFF, HANDOFF, (ORIGIN, ("reason", "product_not_found"))),
        )
        assert out.said == () and out.vote is Status.QUIET

    async def test_with_the_turn_resolved_it_does_not_emit(self) -> None:
        assert await human_handoff(question_judge_with())(turn_log(WITH_ANSWER)) == ZERO

    async def test_without_a_judge_it_warns_on_each_run_and_does_not_escalate(self) -> None:
        out = await human_handoff(None)(turn_log(NO_ANSWER))

        assert out.effects == ()
        assert [f.who for f in out.fails] == ["effects"]
        assert "nobody answers `HANDOFF_QUESTIONS`" in out.fails[0].reason

    async def test_one_case_per_conversation(self) -> None:
        """The host seeds the channel: with the case open or closed no other is opened, and nothing is asked."""
        judge_ = ScriptedJudge()
        open_ = (EffectOp("propose", HANDOFF, HANDOFF),)
        closed_ops = (*open_, EffectOp("done", HANDOFF, note="case 41"))

        for seeded in (open_, closed_ops):
            out = await human_handoff(QuestionJudge(judge_, Echo()))(turn_log(NO_ANSWER, effects=seeded))

            assert out == ZERO
        assert judge_.calls == 0

    async def test_the_datasheet_proposed_in_the_same_turn_does_not_stop_it(self) -> None:
        requested = (EffectOp("propose", "send_datasheet", "document"),)

        out = await human_handoff(question_judge_with())(turn_log(NO_ANSWER, effects=requested))

        assert [op.id for op in out.effects] == [HANDOFF]


class TestWhatItCosts:
    async def test_the_sale_and_the_escalation_are_one_request_about_the_answer(self) -> None:
        """`then(close_sale_steps, human_handoff)` on the outbound edge: two requests in the turn, the one for
        the customer's state and the one for the answer, and the reason comes inside the second."""
        judge_ = ScriptedJudge(label="unverifiable_specification")
        question_judge = QuestionJudge(judge_, Echo())

        out = await then(close_sale_steps(question_judge), human_handoff(question_judge))(turn_log(NO_ANSWER))

        assert [set(a["questions"]) for a in judge_.asked] == [{*STATE_QUESTIONS, *SALE_LABELS}, {*HANDOFF_REASON_QUESTIONS, "recommended_a_product", *HANDOFF_QUESTIONS}]
        assert effects_of(out.effects)[0].args == (ORIGIN, ("reason", "unverifiable_specification"))

    async def test_it_does_not_talk_to_the_model(self) -> None:
        """Zero calls to the model: the only thing that compacts is the sale, and that was already paid for."""
        echo = Echo()

        await human_handoff(QuestionJudge(ScriptedJudge(), echo))(turn_log(NO_ANSWER))

        assert echo.conversations == []


class TestTheEndToEndShape:
    REAL = frozenset({"products/larvane.md"})

    def wired(self, question_judge: QuestionJudge, answer: str) -> Cell:
        async def scripted_writer(seen: Log) -> Log:
            return Log(said=(Message(Role.ASSISTANT, answer),))

        return then(
            close_sale_steps(question_judge),
            capture_effects(question_judge),
            scripted_writer,
            close_sale_steps(question_judge),
            fill_effect_args(self.REAL),
            human_handoff(question_judge),
        )

    async def test_the_turn_that_does_not_resolve_comes_out_with_the_case_proposed(self) -> None:
        """The whole shape without a model: the writer says it is not in the datasheet and the turn
        comes out with a `handoff` the host opens outside."""
        question_judge = question_judge_with(label="unverifiable_specification")

        out = await turn(self.wired(question_judge, NO_ANSWER), QUESTION, ())

        [case] = effects_of(out.effects)
        assert (case.id, case.kind, case.status) == (HANDOFF, HANDOFF, "proposed")
        assert case.args == (ORIGIN, ("reason", "unverifiable_specification"))
        assert effects_state((case,)) == "handoff proposed (requested_by_agent, unverifiable_specification)"

    async def test_the_host_closes_it_and_the_next_turn_does_not_open_it_again(self) -> None:
        """The channel comes back with the `done` the host seeded: the conversation already has an owner."""
        question_judge = question_judge_with()
        first = await turn(self.wired(question_judge, NO_ANSWER), QUESTION, ())
        closed_ops = (*first.effects, *host_sim(effects_of(first.effects)))

        assert host_sim(effects_of(first.effects)) == (EffectOp("done", HANDOFF, note="simulated"),)

        second = await turn(self.wired(question_judge, NO_ANSWER), "and the Fungvane?", (), (), closed_ops)

        assert second.effects == ()


class TestTheInbound:
    """`asked_handoff`: what the customer asks for and the advisor does not resolve escalates before the writer writes."""

    def test_the_table_names_questions_someone_answers_and_crm_reasons(self) -> None:
        assert HANDOFF_ASKED.keys() <= HANDOFF_ASKS.keys() | LABEL_GATES.keys()
        assert set(HANDOFF_ASKED.values()) <= HANDOFF_REASONS.keys()

    def test_each_inbound_reason_has_its_line_for_the_writer(self) -> None:
        assert TAKEN_OVER == HANDOFF_LINES.keys()

    async def test_it_escalates_with_the_reason_of_the_question(self) -> None:
        out = await asked_verdict(question_judge_with({"asks_about_their_order": 0.9}))(envelope("has my order shipped yet?"))

        assert out == (ORIGIN, ("reason", "quote_not_found"))

    async def test_with_two_above_the_highest_wins(self) -> None:
        judge_ = question_judge_with({"brings_a_complaint": 0.85, "asks_for_return": 0.95})

        assert await asked_verdict(judge_)(envelope("it arrived broken, I want to return it")) == (ORIGIN, ("reason", "warranty_return"))

    async def test_the_threshold_is_the_one_of_the_sale(self) -> None:
        below = question_judge_with({"asks_about_their_order": THRESHOLD - 0.01})

        assert await asked_verdict(below)(envelope("has my order shipped yet?")) is None

    async def test_the_check_comes_from_the_payment_label(self) -> None:
        out = await asked_verdict(question_judge_with())(envelope("I want 4 liters, I will pay by check"))

        assert out == (ORIGIN, ("reason", "card_payment"))

    async def test_what_is_not_in_the_table_does_not_escalate_inbound(self) -> None:
        assert await asked_verdict(question_judge_with())(envelope(QUESTION)) is None

    async def test_it_goes_out_in_the_same_request_as_the_sale(self) -> None:
        """The inbound questions travel with the sale: one network request, one compaction."""
        judge_ = ScriptedJudge(fixed={"asks_about_their_order": 0.9})
        echo = Echo()
        question_judge = QuestionJudge(judge_, echo)

        out = await then(close_sale_steps(question_judge), asked_handoff(question_judge))(envelope("has my order shipped yet?"))

        assert judge_.calls == 1 and len(echo.conversations) == 2
        assert [(op.id, op.kind) for op in out.effects] == [(TAKEOVER, HANDOFF)]

    async def test_the_writer_reads_the_line_of_its_reason_in_a_report(self) -> None:
        out = await asked_handoff(question_judge_with({"asks_about_their_order": 0.9}))(envelope("has my order shipped yet?"))

        assert [(r.who, r.text) for r in out.reports] == [(ASKED_WHO, HANDOFF_LINES["quote_not_found"])]

    async def test_with_the_case_already_open_the_report_goes_and_not_another_proposal(self) -> None:
        """One per conversation: the case from turn 1 stays, but the writer still has to know what to say."""
        open_ = (EffectOp("propose", TAKEOVER, HANDOFF), EffectOp("done", TAKEOVER, note="case 41"))

        out = await asked_handoff(question_judge_with({"asks_about_their_order": 0.9}))(envelope("has my order shipped yet?", effects=open_))

        assert out.effects == () and [r.who for r in out.reports] == [ASKED_WHO]

    async def test_a_guardian_case_does_not_stop_the_one_that_turns_off_the_advisor(self) -> None:
        """A `product_not_found` from turn 2 left the complaint of turn 6 unproposed: the host did not turn off the advisor."""
        from_guardian = (EffectOp("propose", HANDOFF, HANDOFF), EffectOp("done", HANDOFF, note="case 40"))

        out = await asked_handoff(question_judge_with({"brings_a_complaint": 0.9}))(envelope("it burned my tomato", effects=from_guardian))

        assert [(op.id, dict(op.args)["reason"]) for op in out.effects] == [(TAKEOVER, "quality_complaint")]

    async def test_without_a_request_that_escalates_there_is_no_report(self) -> None:
        assert await asked_handoff(question_judge_with())(envelope(QUESTION)) == ZERO

    async def test_without_a_judge_it_warns_and_does_not_escalate(self) -> None:
        out = await asked_handoff(None)(envelope("has my order shipped yet?"))

        assert out.effects == () and out.reports == () and [f.who for f in out.fails] == ["effects"]


class TestTheCompletedSale:
    """`sale_completed`: the closed plan, by code and with no judge."""

    def test_the_closed_sale_is_complete(self) -> None:
        assert sold(envelope(DATA, course=SOLD))

    def test_it_does_not_require_the_account_to_have_gone_out(self) -> None:
        """"paying by transfer" closes `method` and does not ask for the account: `sale-closed` ended 0/3 when it was required."""
        assert sold(envelope(DATA, course=SOLD, effects=()))

    def test_without_deciding_it_is_not_complete(self) -> None:
        no_decision = with_closed("pest", "product", "recipe", "quantity", "method", "data")

        assert not sold(envelope(DATA, course=no_decision, effects=ACCOUNT))

    def test_without_the_invoice_data_it_is_not_complete(self) -> None:
        no_data = with_closed("pest", "product", "recipe", "quantity", "decision", "method")

        assert not sold(envelope("transfer", course=no_data, effects=ACCOUNT))


def closes(*ids: str) -> Cell:
    """A fake `close_sale_steps`: it closes those leaves, with no judge."""

    async def cell(seen: Log) -> Log:
        return Log(course=tuple(PlanOp("mark", i, status="done") for i in ids))

    return cell


PRIOR = with_closed("pest", "product", "recipe", "quantity", "decision", "method")
"""The sale seeded one step from closing: the invoice data are missing."""


class TestTheSaleThatClosesThisTurn:
    """`sale_closed`: `sale_completed` goes out on the turn the sale passes from open to closed, and on no other."""

    async def test_it_closes_this_turn_and_the_takeover_goes_out(self) -> None:
        out = await sale_closed(closes("data"))(envelope(DATA, course=PRIOR))

        assert [(r.who, r.text) for r in out.reports] == [(ASKED_WHO, HANDOFF_LINES[SOLD_REASON])]
        assert [(op.id, op.kind, dict(op.args)["reason"]) for op in out.effects] == [(TAKEOVER, HANDOFF, SOLD_REASON)]
        assert [op.id for op in out.course] == ["data"]

    async def test_a_sale_closed_before_does_not_escalate(self) -> None:
        """Prod, Sep 28, 2026: Brimsol closed before the deploy, "The prise" of Reapvane, and it escalated with the old order."""
        out = await sale_closed(closes())(envelope("The prise", course=SOLD))

        assert out.effects == () and out.reports == ()

    async def test_with_an_earlier_takeover_it_does_not_promise_a_person(self) -> None:
        """A person already had the case and reactivated the agent: the report with no case promises someone nobody called."""
        before = (EffectOp("propose", TAKEOVER, HANDOFF), EffectOp("done", TAKEOVER))

        out = await sale_closed(closes("data"))(envelope(DATA, course=PRIOR, effects=before))

        assert out.effects == () and out.reports == ()

    async def test_without_closing_it_does_not_escalate(self) -> None:
        out = await sale_closed(closes("method"))(envelope("by transfer", course=with_closed("decision")))

        assert out.effects == () and out.reports == ()

    async def test_the_inbound_does_not_ask_with_the_sale_closed_on_the_turn(self) -> None:
        """One case per turn: with the sale's `takeover`, the `HANDOFF_ASKED` judge does not go to the network."""
        judge_ = ScriptedJudge()
        proposed_op = (EffectOp("propose", TAKEOVER, HANDOFF, (ORIGIN, ("reason", SOLD_REASON))),)

        out = await asked_handoff(QuestionJudge(judge_, Echo()))(envelope(DATA, course=SOLD, effects=proposed_op))

        assert out == ZERO and judge_.calls == 0

    async def test_the_inbound_does_not_escalate_for_an_already_closed_sale(self) -> None:
        out = await asked_handoff(question_judge_with())(envelope("The prise", course=SOLD))

        assert out == ZERO


class TestOneCasePerTurn:
    async def test_with_the_takeover_proposed_the_guardian_does_not_open_another(self) -> None:
        """The writer said a person is attending them; the guardian read it as one more escalation."""
        out = await human_handoff(question_judge_with(label="other"))(turn_log(NO_ANSWER, effects=(EffectOp("propose", TAKEOVER, HANDOFF),)))

        assert out == ZERO

    async def test_with_a_takeover_from_an_earlier_turn_the_guardian_continues(self) -> None:
        """If a person reactivated the advisor, what is left unanswered again is another case."""
        closed_ops = (EffectOp("propose", TAKEOVER, HANDOFF), EffectOp("done", TAKEOVER, note="case 41"))

        out = await human_handoff(question_judge_with(label="product_not_found"))(turn_log(NO_ANSWER, effects=closed_ops))

        assert [op.id for op in out.effects] == [HANDOFF]
