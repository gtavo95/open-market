"""The sale's gates as a judge for `close_steps`: what it answers, when it goes to the network and what happens with no judge."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from typing import Any

import pytest
from core_agent.world.dialogue import conversation, customer_words, wrap
from core_agent.prompts.judge import COMPACT, CART, CART_PROMPT, LABEL_GATES, PAYMENT_METHOD, SALE_LABELS, REPLY_QUESTIONS, HANDOFF_REASON, HANDOFF_REASON_QUESTIONS, SALE_QUESTIONS, HANDOFF_REASONS, RECOMMENDED, LEFT_WITHOUT, PRESENTATION, PRODUCT
from core_agent.world.question_judge import STATE_QUESTIONS
from core_agent.world.facts import LOG_FACTS, answer_of
from core_agent.world.question_judge import (
    THRESHOLD,
    JudgeError,
    QuestionJudge,
    Judgment,
    cart,
    compact,
    judge,
    key_of,
    parse_state,
    transcript,
)
from catalejo.core import EffectOp, Log, Message, PlanOp, Role, project
from core_agent.world.order import billable, payment_args, price_order
from catalejo.rlm import close_steps
from core_agent.world import typesafe
from tests.doubles import HIGH, LOW, Echo, Said, ScriptedJudge, question_judge_with

ALL = frozenset(SALE_QUESTIONS) | frozenset(LABEL_GATES)


def envelope(question: str, history: tuple[tuple[str, str], ...] = ()) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, history)),))


class TestTheEnvelope:
    def test_conversation_takes_apart_what_wrap_put_together(self) -> None:
        history = (("I have a pest", "Which one?"), ("whitefly", "Larvane.\n\nTwo manzanas take 2 L."))

        assert conversation(envelope("it's 3 manzanas", history)) == ("it's 3 manzanas", history)
        assert conversation(envelope("hi")) == ("hi", ())
        assert conversation(Log()) == ("", ())

    def test_the_turn_key_is_the_same_from_the_envelope_and_from_the_history(self) -> None:
        history = (("I have a pest", "Which one?"),)

        assert key_of("whitefly", history) == customer_words(envelope("whitefly", history))
        assert key_of("whitefly", history) == "I have a pest\nwhitefly"

    def test_the_transcript_carries_the_whole_answers(self) -> None:
        long = "x" * 900
        text = transcript("and now", (("before", long),))

        assert long in text and text.endswith("Customer: and now")


class TestTheState:
    def test_parse_state_accepts_bare_json_fenced_or_with_prose_around_it(self) -> None:
        assert parse_state('{"crop": "tomato"}') == {"crop": "tomato"}
        assert parse_state('Here it is:\n```json\n{"crop": "coffee"}\n```') == {"crop": "coffee"}
        assert parse_state('the state is {"area": "3 manzanas"} and nothing else') == {"area": "3 manzanas"}

    def test_with_no_json_the_whole_text_is_the_state(self) -> None:
        assert parse_state("I don't know what to say") == {"text": "I don't know what to say"}
        assert parse_state("[1, 2]") == {"text": "[1, 2]"}

    async def test_compact_sends_the_model_the_whole_conversation_and_returns_what_it_spent(self) -> None:
        model = Echo(spent=42)

        state, spent = await compact(model, "it's 3 manzanas", (("whitefly", "Larvane"),))

        assert spent == 42
        assert "Customer: whitefly" in model.conversations[0][0].text
        assert model.conversations[0][0].text.startswith(COMPACT)
        assert state == {"said_raw": model.conversations[0][0].text.removeprefix(COMPACT)}

    async def test_cart_is_another_call_with_its_request_and_returns_the_raw_cart(self) -> None:
        model = Echo(spent=5)

        items, spent = await cart(model, "I want two liters", (("whitefly", "Larvane"),))

        assert spent == 5
        assert model.conversations[0][0].text.startswith(CART_PROMPT)
        assert "Customer: whitefly" in model.conversations[0][0].text
        assert items == [{"product": "Reapvane", "presentation": None, "quantity": 2}]


class TestTheJudge:
    """`QuestionJudge` is a `Judge`: `(Log, names) -> p per name`."""

    async def test_answers_what_it_is_asked_and_only_what_is_in_the_questions(self) -> None:
        question_judge = QuestionJudge(ScriptedJudge(), Echo())

        out = await question_judge(envelope("I have whitefly on the tomato"), frozenset({"has_search_terms", "said_quantity", "read_the_payment_methods"}))

        assert out == {"has_search_terms": HIGH, "said_quantity": LOW}

    async def test_the_questions_go_over_the_conversation_and_are_all_those_of_the_network(self) -> None:
        """Two are asked for and TypeSafe receives all of them and the payment label: they are independent
        over the same conversation, which is what is charged. What comes back to whoever asked is the two."""
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())

        out = await question_judge(envelope("hi"), frozenset({"said_quantity", "wants_to_buy"}))

        request = judge_.asked[0]
        assert request["state"] == {"conversation": [], "last_message": "hi"}
        assert set(request["questions"]) == set(STATE_QUESTIONS) | set(SALE_LABELS)
        assert set(out) == {"said_quantity", "wants_to_buy"}
        assert all(q["type"] == "noul" and "`conversation`" in q["instructions"] for q in SALE_QUESTIONS.values())

    async def test_with_no_network_names_it_does_not_go_to_the_network(self) -> None:
        judge_ = ScriptedJudge()
        model = Echo()

        assert await QuestionJudge(judge_, model)(envelope("hi"), frozenset({"read_the_payment_methods"})) == {}
        assert judge_.calls == 0 and model.conversations == []

    async def test_compacts_once_per_turn_and_goes_to_the_network_once(self) -> None:
        """Three requests of the same turn (`close_steps` in `before`, `propose_effects`, `close_steps` in `after`):
        one compaction, one cart and one request to TypeSafe. Until Sep 21, 2026 the
        second name was a second request with the same state."""
        judge_ = ScriptedJudge()
        model = Echo()
        question_judge = QuestionJudge(judge_, model)
        log = envelope("I have whitefly on the tomato")

        await question_judge(log, frozenset({"has_search_terms"}))
        await question_judge(log, frozenset({"has_search_terms"}))
        await question_judge(log, frozenset({"has_search_terms", "said_quantity", "asked_for_the_datasheet"}))

        assert len(model.conversations) == 2
        assert [set(a["questions"]) for a in judge_.asked] == [set(STATE_QUESTIONS) | set(SALE_LABELS)]
        judgment = question_judge.last("I have whitefly on the tomato", ())
        assert judgment is not None and set(judgment.p) == set(STATE_QUESTIONS) | set(LABEL_GATES)
        assert judgment.spent == 7 + 7 and judgment.tokens == 100, "the compaction and the cart"

    async def test_another_turn_is_another_judgment(self) -> None:
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())
        history = (("I have a pest", "Which one?"),)

        one = await question_judge(envelope("whitefly", history), ALL)
        two = await question_judge(envelope("I want two liters", history + (("whitefly", "Larvane"),)), ALL)

        assert one["has_search_terms"] == HIGH and one["said_quantity"] == LOW
        assert two["said_quantity"] == HIGH and judge_.calls == 2

    async def test_last_does_not_go_to_the_network(self) -> None:
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())

        assert question_judge.last("hi", ()) is None
        await question_judge(envelope("hi"), ALL)
        assert question_judge.last("hi", ()) is not None and judge_.calls == 1

    async def test_two_requests_of_the_same_turn_at_once_compact_a_single_time(self) -> None:
        judge_ = ScriptedJudge()
        model = Echo()
        question_judge = QuestionJudge(judge_, model)
        log = envelope("hi")

        a, b = await asyncio.gather(question_judge(log, ALL), question_judge(log, ALL))

        assert a == b and judge_.calls == 1 and len(model.conversations) == 2

    async def test_the_memory_is_bounded(self) -> None:
        question_judge = QuestionJudge(ScriptedJudge(), Echo(), keep=2)

        for q in ("one", "two", "three"):
            await question_judge(envelope(q), ALL)

        assert question_judge.last("one", ()) is None and question_judge.last("three", ()) is not None

    async def test_with_no_judge_it_raises_and_the_error_stays_memoized(self) -> None:
        question_judge = question_judge_with(down=True)
        log = envelope("whitefly")

        with pytest.raises(JudgeError, match="reading"):
            await question_judge(log, ALL)
        with pytest.raises(JudgeError, match="reading"):
            await question_judge(log, ALL)

        judgment = question_judge.last("whitefly", ())
        assert judgment is not None and judgment.p == {} and judgment.state["said_raw"]
        assert question_judge.errors == 1

    async def test_with_no_model_to_compact_it_raises(self) -> None:
        question_judge = question_judge_with(silent=True)

        with pytest.raises(JudgeError, match="compacting"):
            await question_judge(envelope("whitefly"), ALL)

        judgment = question_judge.last("whitefly", ())
        assert judgment is not None and judgment.state == {} and question_judge.errors == 1

    def test_as_dict_is_what_the_host_sees(self) -> None:
        j = Judgment({"a": 1}, {"said_quantity": 0.9}, spent=3, tokens=4, labels={PAYMENT_METHOD: "link"})

        assert j.as_dict() == {
            "state": {"a": 1},
            "p": {"said_quantity": 0.9},
            "labels": {PAYMENT_METHOD: "link"},
            "order": {"items": [], "total": None, "currency": None, "chargeable": False, "restarted": False},
            "already_said": [],
            "asks_again": [],
            "unanswered": [],
            "error": "",
        }
        assert json.dumps(j.as_dict())

    async def test_the_cart_comes_out_of_the_state_and_travels_as_an_order(self) -> None:
        """The state stays without `cart` for the host, TypeSafe does not read it, and the order arrives put against the catalog."""
        judge_ = ScriptedJudge()
        state = {"product": "Reapvane", "quantity": "2 liters"}
        question_judge = QuestionJudge(judge_, Said({**state, CART: [{"product": "Reapvane", "presentation": "1 L", "quantity": 2}]}))

        await question_judge(envelope("I want 2 liters of Reapvane"), frozenset({"said_quantity"}))

        judgment = question_judge.last("I want 2 liters of Reapvane", ())
        assert judgment is not None and judgment.state == state
        assert "state" not in judge_.asked[0]["state"]
        order = judgment.as_dict()["order"]
        assert order["items"][0]["product"] == "Reapvane" and order["items"][0]["path"] == "products/reapvane.md"
        assert order["total"] == 2 * order["items"][0]["price"]

    async def test_the_link_already_sent_is_the_memory_of_the_cart(self) -> None:
        """The payment link of the `effects` channel fills in the presentation this turn's compaction lost."""
        link = payment_args(price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 5}]))
        question_judge = QuestionJudge(ScriptedJudge(), Said({CART: [{"product": "Reapvane", "presentation": None, "quantity": 5}]}))
        seen = replace(
            envelope("thanks, I already paid"),
            effects=(EffectOp("propose", "send_payment_link", "payment_link", link), EffectOp("done", "send_payment_link", note="https://link")),
        )

        order = await question_judge.order(seen)

        assert order[0].presentation == "1 L" and billable(order)

    async def test_a_name_that_is_not_a_title_is_chosen_by_the_judge(self) -> None:
        """No string similarity in code: "TriVX" is read by a `choice` with the bundle's datasheets."""
        from core_agent.world.order import sheets

        titles = [t for t, _ in sheets()]
        with_cart = Said({CART: [{"product": "TriVX", "presentation": None, "quantity": 2}]})
        picks = QuestionJudge(ScriptedJudge(label=f"f{titles.index('Tri VX 35 EW') + 1}"), with_cart)
        picks_none = QuestionJudge(ScriptedJudge(label="none"), with_cart)

        (one,) = await picks.order(envelope("2 of TriVX"))
        (other,) = await picks_none.order(envelope("2 of TriVX"))

        assert one.product == "Tri VX 35 EW" and other.product is None
        assert picks._client.asked[0]["state"] == {"product": "TriVX"}  # type: ignore[attr-defined]

    async def test_a_presentation_the_cart_did_not_record_as_it_stands_is_chosen_by_the_judge(self) -> None:
        """No units dictionary in code: "liter" is read by a `choice` with the datasheet's rows."""
        with_cart = Said({CART: [{"product": "Reapvane", "presentation": "liter", "quantity": 2}]})
        picks = QuestionJudge(ScriptedJudge(label="p1"), with_cart)
        other = QuestionJudge(ScriptedJudge(label="other_unit"), with_cart)

        (one,) = await picks.order(envelope("2 liters of Reapvane"))
        (gallon,) = await other.order(envelope("2 liters of Reapvane"))

        assert (one.presentation, one.subtotal) == ("1 L", 2 * one.unit_price)  # type: ignore[operator]
        assert gallon.other_unit and gallon.presentation is None
        assert picks._client.asked[0]["state"] == {"product": "Reapvane", "asked": {"presentation": "liter", "quantity": 2.0}}  # type: ignore[attr-defined]

    async def test_a_choice_with_no_option_leaves_the_line_as_it_was_and_counts_the_error(self) -> None:
        """If TypeSafe answers without the key of the datasheet or presentation `choice`, the name stays without a datasheet and the
        presentation unchosen, and it is counted in `errors`; it does not raise."""

        class NoChoice(ScriptedJudge):
            async def ask(self, state: Any, questions: dict[str, Any]) -> typesafe.Response:
                full = await super().ask(state, questions)
                answers = {k: a for k, a in full.answers.items() if k not in (PRODUCT, PRESENTATION)}
                return typesafe.Response(answers=answers, tokens=full.tokens, model=full.model)

        name = QuestionJudge(NoChoice(), Said({CART: [{"product": "TriVX", "presentation": None, "quantity": 2}]}))
        unit = QuestionJudge(NoChoice(), Said({CART: [{"product": "Reapvane", "presentation": "liter", "quantity": 2}]}))

        (no_datasheet,) = await name.order(envelope("2 of TriVX"))
        (unchosen,) = await unit.order(envelope("2 liters of Reapvane"))

        assert no_datasheet.product is None and name.errors == 1
        assert unchosen.presentation is None and unit.errors == 1

    async def test_each_line_choice_stays_recorded_with_its_p(self) -> None:
        """For `Answer.rules`: which datasheet and which presentation the judge chose in each line, and with how much p."""
        with_cart = Said({CART: [{"product": "Reapvane", "presentation": "liter", "quantity": 2}]})
        picks = QuestionJudge(ScriptedJudge(label="p1"), with_cart)

        await picks.order(envelope("2 liters of Reapvane"))

        seen = picks.last("2 liters of Reapvane", ())
        assert seen is not None and PRODUCT not in seen.picks, "a title as it stands is not asked"
        (k,) = seen.picks[PRESENTATION]
        assert (k.said, k.option, k.p) == ("Reapvane: liter", "1 L", HIGH)

    async def test_the_turn_case_stays_recorded_with_its_distribution_or_its_error(self) -> None:
        """For `Answer.rules`: which line the writer received, or that it received all four because the judge went down."""
        working = question_judge_with()
        downed = question_judge_with(down=True)

        case = await working.turn_case(envelope("do you have anything for leafcutter ants?"), "no datasheet covers leafcutter ants")
        with pytest.raises(JudgeError):
            await downed.turn_case(envelope("do you have anything for leafcutter ants?"), "no datasheet covers leafcutter ants")

        seen = working.last_case("do you have anything for leafcutter ants?", ())
        assert seen is not None and seen.case == case and seen.p[case] == HIGH and not seen.error
        lost = downed.last_case("do you have anything for leafcutter ants?", ())
        assert lost is not None and lost.case == "" and "503" in lost.error

    async def test_order_with_quantities_is_answered_by_the_order_of_the_same_judgment(self) -> None:
        """1.0 or 0.0 from the cart, with no other compaction and no other request to TypeSafe."""
        judge_ = ScriptedJudge()
        two = [{"product": "Rootvane", "presentation": None, "quantity": 10}, {"product": "Roycel 25 EW", "presentation": None, "quantity": None}]
        missing = QuestionJudge(judge_, Said({CART: two}))
        complete = QuestionJudge(ScriptedJudge(), Said({CART: two[:1]}))

        one = await missing(envelope("I want 10 of Rootvane and also Roycel"), frozenset({"order_with_quantities", "wants_to_buy"}))
        other = await complete(envelope("I want 10 of Rootvane"), frozenset({"order_with_quantities"}))

        assert one["order_with_quantities"] == 0.0 and "wants_to_buy" in one
        assert other == {"order_with_quantities": 1.0}
        assert judge_.calls == 1

    async def test_the_payment_method_travels_as_a_label_in_the_same_request(self) -> None:
        """The label comes out in the judgment the host sees, and `said_payment_method` is its
        distribution over link or transfer. With no method said, `none`."""
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())

        paying = await question_judge(envelope("I'll pay by transfer"), frozenset({"said_payment_method"}))
        greeting = await question_judge(envelope("hi"), frozenset({"said_payment_method"}))

        payment = question_judge.last("I'll pay by transfer", ())
        hello = question_judge.last("hi", ())
        assert payment is not None and payment.labels[PAYMENT_METHOD] == "transfer"
        assert hello is not None and hello.labels[PAYMENT_METHOD] == "none"
        assert paying["said_payment_method"] >= HIGH and greeting["said_payment_method"] < LOW
        assert judge_.calls == 2
        assert "said_payment_method" not in judge_.asked[0]["questions"], "the gate comes out of the label, it is not asked"


class TestTheFactsOfTheTurn:
    def test_each_billing_step_looks_at_its_own_page(self) -> None:
        """With a shared gate, a grep on `payments.md` while the account was being given
        closed `accounts` without having opened `bank-accounts.md`."""
        methods, accounts = LOG_FACTS["read_the_payment_methods"], LOG_FACTS["read_the_accounts"]
        only_payments = Log(said=(Message(Role.USER, "company_info/payments.md:3: link payment link"),))

        assert methods(only_payments) and not accounts(only_payments)

    def test_the_gate_looks_at_what_read_and_grep_showed_and_not_at_a_path_in_prose(self) -> None:
        """`saw_file` parses with `seen_paths`, the one in `workspace.py`: a datasheet opened whole
        counts, a grep hit counts, and a path named in the prose of the model or
        of the contract does not."""
        datasheet = LOG_FACTS["opens_a_datasheet"]
        opened = Log(said=(Message(Role.USER, "products/x.md: 2 lines, from 1 to 2.\n---\ntitle: X"),))
        named = Log(said=(Message(Role.USER, "Look at products/x.md: it's the right one. SOURCE: products/x.md"),))
        spoken = Log(said=(Message(Role.ASSISTANT, "products/x.md:3: dose 1 L/ha"),))

        assert datasheet(opened)
        assert not datasheet(named) and not datasheet(spoken)

    def test_querying_is_reads(self) -> None:
        assert LOG_FACTS["queried_the_catalog"](Log(reads=1)) and not LOG_FACTS["queried_the_catalog"](Log())


class TestTheAdvisorAnswer:
    """`REPLY_QUESTIONS` and `HANDOFF_REASON_QUESTIONS`: the assistant's last prose is judged, with what the customer said alongside."""

    def turn(self, answer: str, history: tuple[tuple[str, str], ...] = ()) -> Log:
        return Log(said=(Message(Role.USER, wrap("whitefly on tomato", history)), Message(Role.ASSISTANT, answer)))

    def test_the_answer_is_the_assistant_last_prose(self) -> None:
        assert answer_of(envelope("hi")) == ""
        assert answer_of(self.turn("I recommend Larvane.")) == "I recommend Larvane."
        with_code = Log(said=(*self.turn("I recommend Larvane.").said, Message(Role.ASSISTANT, "```python\nprint(1)\n```")))
        assert answer_of(with_code) == "I recommend Larvane."

    async def test_with_no_answer_it_answers_zero_without_going_to_the_network(self) -> None:
        """The sale of `before`: the history travels in the envelope and there is no assistant in `said`."""
        judge_ = ScriptedJudge()

        out = await QuestionJudge(judge_, Echo())(envelope("whitefly on tomato"), frozenset({RECOMMENDED}))

        assert out == {RECOMMENDED: 0.0} and judge_.calls == 0

    async def test_with_an_answer_it_asks_about_it_with_the_customer_alongside(self) -> None:
        judge_ = ScriptedJudge()
        history = (("I have a problem on the tomato", "what pest do you see?"),)
        seen = self.turn("I recommend Larvane, certified for tomato.", history)

        out = await QuestionJudge(judge_, Echo())(seen, frozenset({RECOMMENDED}))

        assert out[RECOMMENDED] == HIGH
        assert judge_.asked[-1]["state"] == {
            "customer": ["I have a problem on the tomato", "whitefly on tomato"],
            "last_message": "whitefly on tomato",
            "advisor": "I recommend Larvane, certified for tomato.",
        }
        assert judge_.asked[-1]["questions"] == {**REPLY_QUESTIONS, **HANDOFF_REASON_QUESTIONS}, "the two questions and the reason in one request"

    async def test_a_question_is_not_a_recommendation(self) -> None:
        out = await question_judge_with()(self.turn("What pest do you see on the tomato?"), frozenset({RECOMMENDED}))

        assert out[RECOMMENDED] == LOW

    async def test_the_same_answer_is_judged_once(self) -> None:
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())
        seen = self.turn("I recommend Larvane.")

        await question_judge(seen, frozenset({RECOMMENDED}))
        await question_judge(seen, frozenset({RECOMMENDED}))

        assert judge_.calls == 1

    async def test_a_downed_judge_is_a_gate_error_and_is_counted(self) -> None:
        question_judge = question_judge_with(down=True)

        with pytest.raises(JudgeError, match="reading the answer"):
            await question_judge(self.turn("I recommend Larvane."), frozenset({RECOMMENDED}))
        assert question_judge.errors == 1

    async def test_it_does_not_go_through_compaction(self) -> None:
        """Both kinds of name in one call: one compaction for the customer's, a separate request for the answer."""
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())

        out = await question_judge(self.turn("I recommend Larvane."), frozenset({"has_search_terms", RECOMMENDED}))

        assert set(out) == {"has_search_terms", RECOMMENDED} and judge_.calls == 2
        assert [set(a["questions"]) for a in judge_.asked] == [{*STATE_QUESTIONS, *SALE_LABELS}, {*REPLY_QUESTIONS, *HANDOFF_REASON_QUESTIONS}]

    async def test_the_escalation_and_the_sale_are_a_single_request(self) -> None:
        """Whoever asks second comes from memory: the noul and the label came together."""
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())
        seen = self.turn("That is not in the datasheet.")

        recommended = await question_judge(seen, frozenset({RECOMMENDED}))
        escalates = await question_judge(seen, frozenset({LEFT_WITHOUT}))
        reason = await question_judge.label(seen, HANDOFF_REASON)

        assert recommended[RECOMMENDED] == LOW and escalates[LEFT_WITHOUT] == HIGH
        assert reason in HANDOFF_REASONS
        assert judge_.calls == 1

    async def test_the_label_is_the_one_the_judge_chose(self) -> None:
        question_judge = question_judge_with(label="unverifiable_specification")

        assert await question_judge.label(self.turn("That is not in the datasheet."), HANDOFF_REASON) == "unverifiable_specification"

    async def test_with_no_answer_there_is_no_label_and_it_warns(self) -> None:
        """With no answer to label there is no default reason: nobody guesses what an escalation is about."""
        with pytest.raises(JudgeError, match="no answer to label"):
            await question_judge_with().label(envelope("whitefly on tomato"), HANDOFF_REASON)

    async def test_a_name_that_is_not_a_label_is_not_answered(self) -> None:
        with pytest.raises(JudgeError, match="nobody answers"):
            await question_judge_with().label(self.turn("I recommend Larvane."), "made_up")

    async def test_the_answer_memory_is_bounded(self) -> None:
        question_judge = question_judge_with(keep=1)
        for answer in ("I recommend Larvane.", "I recommend Fungvane."):
            await question_judge(self.turn(answer), frozenset({RECOMMENDED}))

        assert list(question_judge._answered) == ["I recommend Fungvane."]


class TestTheSaleJudge:
    """`judge(question_judge)`: the twelve names through one door, the facts first."""

    async def test_answers_the_twelve(self) -> None:
        sale_judge = judge(question_judge_with())
        seen = Log(said=(Message(Role.USER, wrap("I have whitefly, it's two manzanas", ())),), reads=1)

        out = await sale_judge(seen, ALL | frozenset(LOG_FACTS) | {RECOMMENDED})

        assert set(out) == ALL | frozenset(LOG_FACTS) | {RECOMMENDED}
        assert out["queried_the_catalog"] == 1.0 and out["opens_a_datasheet"] == 0.0
        assert out["has_search_terms"] == HIGH and out["wants_to_buy"] == LOW
        assert out[RECOMMENDED] == 0.0

    async def test_the_facts_do_not_go_through_the_network(self) -> None:
        judge_ = ScriptedJudge()
        sale_judge = judge(QuestionJudge(judge_, Echo()))

        out = await sale_judge(Log(reads=1), frozenset(LOG_FACTS))

        assert out["queried_the_catalog"] == 1.0 and judge_.calls == 0

    async def test_with_no_gates_the_facts_answer_and_the_network_stays_unanswered(self) -> None:
        out = await judge(None)(Log(reads=1), frozenset({"queried_the_catalog", "said_quantity"}))

        assert out == {"queried_the_catalog": 1.0}

    async def test_a_name_nobody_knows_is_omitted(self) -> None:
        assert await judge(question_judge_with())(envelope("hi"), frozenset({"said_quantitty"})) == {}


SALE = (
    PlanOp("add_step", "diagnosis"),
    PlanOp("add_step", "pest", "what they are looking for", padre="diagnosis", done_when="has_search_terms"),
    PlanOp("add_step", "quantity", "how much they treat", padre="diagnosis", done_when="said_quantity"),
    PlanOp("add_step", "payment"),
)


class TestInSettle:
    """The gates wired as they go in agro: `close_steps(judge(question_judge), channel="course", umbral=THRESHOLD)`."""

    def cell(self, question_judge: QuestionJudge | None) -> object:
        return close_steps(judge(question_judge), channel="course", umbral=THRESHOLD)

    async def test_closes_the_sale_leaf_with_what_the_customer_said(self) -> None:
        seen = Log(said=(Message(Role.USER, wrap("I have whitefly on the tomato", ())),), course=SALE)

        out = await self.cell(question_judge_with())(seen)  # type: ignore[operator]

        assert [s.status for s in project(SALE + out.course)] == ["todo", "done", "todo", "todo"]

    async def test_the_leaf_stays_open_with_no_term(self) -> None:
        seen = Log(said=(Message(Role.USER, wrap("I have a problem on the tomato", ())),), course=SALE)

        out = await self.cell(question_judge_with())(seen)  # type: ignore[operator]

        assert out.course == () and out.fails == ()

    async def test_asks_only_about_what_is_open(self) -> None:
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())
        course = (*SALE, PlanOp("mark", "pest", status="done"))
        seen = Log(said=(Message(Role.USER, wrap("I want two liters", ())),), course=course)

        out = await self.cell(question_judge)(seen)  # type: ignore[operator]

        assert [op.id for op in out.course] == ["quantity"]
        assert set(judge_.asked[0]["questions"]) == {*STATE_QUESTIONS, *SALE_LABELS}, "all go to the network; `close_steps` filters what is open"

    async def test_the_threshold_decides(self) -> None:
        seen = Log(said=(Message(Role.USER, wrap("hi", ())),), course=SALE)

        exact = await self.cell(question_judge_with({"has_search_terms": THRESHOLD}))(seen)  # type: ignore[operator]
        nearly = await self.cell(question_judge_with({"has_search_terms": THRESHOLD - 0.01}))(seen)  # type: ignore[operator]

        assert [op.id for op in exact.course] == ["pest"] and nearly.course == ()

    async def test_with_no_judge_it_is_a_fail_and_nothing_closes(self) -> None:
        seen = Log(said=(Message(Role.USER, wrap("whitefly", ())),), course=SALE)

        out = await self.cell(question_judge_with(down=True))(seen)  # type: ignore[operator]

        assert out.course == ()
        assert len(out.fails) == 1 and "JudgeError" in out.fails[0].reason and "no judge" in out.fails[0].reason

    async def test_with_no_typesafe_each_network_gate_warns_by_its_name(self) -> None:
        seen = Log(said=(Message(Role.USER, wrap("whitefly", ())),), course=SALE)

        out = await self.cell(None)(seen)  # type: ignore[operator]

        assert out.course == ()
        assert {f.reason for f in out.fails} == {
            "nobody answers `has_search_terms`, so `pest` is never closed",
            "nobody answers `said_quantity`, so `quantity` is never closed",
        }

    async def test_a_fact_of_the_turn_closes_through_the_same_door(self) -> None:
        steps = (PlanOp("add_step", "search", done_when="queried_the_catalog"),)
        seen = Log(said=(Message(Role.USER, wrap("hi", ())),), steps=steps, reads=1)

        out = await close_steps(judge(question_judge_with()), channel="steps")(seen)

        assert project(steps + out.steps)[0].status == "done"


class TestFromEnv:
    def test_with_no_key_there_are_no_gates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

        assert QuestionJudge.from_env(Echo()) is None

    async def test_with_a_key_there_are(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TYPESAFE_API_KEY", "x")

        question_judge = QuestionJudge.from_env(Echo())

        assert question_judge is not None
        await question_judge.aclose()


def test_the_doubles_separate_what_the_real_judge_separated() -> None:
    """A reminder of what `HIGH` and `LOW` are for: the threshold sits between the two."""
    assert LOW < 1 - THRESHOLD < THRESHOLD < HIGH
    assert isinstance(JudgeError("x"), RuntimeError)
