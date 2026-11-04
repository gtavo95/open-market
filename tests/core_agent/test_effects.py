"""The effects wired in `roles/effects.py`: what the judge proposes, what the writer reads, what the turn resolves and what the host does."""

from __future__ import annotations

import json

from core_agent.agent import turn
from core_agent.prompts.judge import SALE_LABELS, ASKED_CATALOG, ASKED_ACCOUNT, ASKED_DATASHEET, ASKED_LINK, LABEL_GATES, SALE_QUESTIONS
from core_agent.world.question_judge import STATE_QUESTIONS
from core_agent.prompts.writer import EFFECT_LINES, HANDOFF_LINES, REGISTERED, SENT_WHAT
from core_agent.roles.human_handoff import ASKED_WHO
from core_agent.roles.effects import (
    EFFECT_RULES,
    SILENT,
    capture_effects,
    effect_line,
    effects_state,
    fill_effect_args,
    SIMULATED_URL,
    host_sim,
    resolvers,
    sent_line,
)
from core_agent.roles.sale import SESSION, close_sale_steps
from core_agent.roles.writer import dictation
from core_agent.world.dialogue import History, conversation, wrap
from core_agent.world.order import Item, payment_args, price_order
from core_agent.roles.form import BILLED, Forms
from core_agent.world.question_judge import ORDER_GATES, QuestionJudge
from catalejo.core import ZERO, Args, EffectOp, Log, Message, PlanOp, Report, Role, Status, effects_of, merge, proposed, then
from tests.doubles import HIGH, LOW, Echo, ScriptedJudge, question_judge_with

ASKS_DATASHEET = "I have whitefly on the tomato, send me the datasheet for Larvane"
ASKS_ACCOUNT = "I want it, send me the account"

REAL = frozenset({"products/larvane.md", "products/fungvane.md", "company_info/payments.md"})

PROPOSED = EffectOp("propose", "send_datasheet", "document")


def envelope(question: str, history: History = (), effects: tuple[EffectOp, ...] = ()) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, history)),), effects=effects)


def answered(seen: Log, text: str) -> Log:
    """The Log after the writer answered that."""
    return merge(seen, Log(said=(Message(Role.ASSISTANT, text),)))


class TestTheTable:
    def test_each_intent_has_someone_to_answer_it_and_a_voice(self) -> None:
        names = {n for i in EFFECT_RULES.values() for n in (i.asked, *i.requires)}

        assert names <= SALE_QUESTIONS.keys() | LABEL_GATES.keys() | ORDER_GATES.keys() | {BILLED}
        assert set(EFFECT_LINES) == set(EFFECT_RULES) - SILENT
        assert set(SENT_WHAT) == set(EFFECT_RULES) - SILENT

    def test_the_two_questions_do_not_close_steps(self) -> None:
        """They propose effects; the sale plan does not name them."""
        gated = {op.done_when for op in SESSION}

        assert ASKED_DATASHEET not in gated and ASKED_ACCOUNT not in gated


class TestCapture:
    async def test_it_proposes_the_datasheet_when_the_customer_asks_for_it(self) -> None:
        out = await capture_effects(question_judge_with())(envelope(ASKS_DATASHEET))

        assert out.effects == (PROPOSED,)
        assert out.said == () and out.vote is Status.QUIET and not out.fails

    async def test_without_a_request_it_does_not_propose(self) -> None:
        assert await capture_effects(question_judge_with())(envelope("I have whitefly on the tomato")) == ZERO

    async def test_the_threshold_is_the_one_of_the_sale(self) -> None:
        assert (await capture_effects(question_judge_with({ASKED_DATASHEET: HIGH}))(envelope("hello"))).effects == (PROPOSED,)
        assert await capture_effects(question_judge_with({ASKED_DATASHEET: LOW}))(envelope("hello")) == ZERO

    async def test_the_account_only_to_whoever_buys(self) -> None:
        no_purchase = await capture_effects(question_judge_with({ASKED_ACCOUNT: HIGH, "wants_to_buy": LOW}))(envelope("hello"))
        with_purchase = await capture_effects(question_judge_with())(envelope(ASKS_ACCOUNT))

        assert no_purchase == ZERO
        assert with_purchase.effects == (EffectOp("propose", "send_payment_accounts", "bank_account"),)

    async def test_it_proposes_the_catalog_when_the_customer_asks_for_it(self) -> None:
        """The catalog is a `document` like the datasheet: the host sends it the same way."""
        out = await capture_effects(question_judge_with())(envelope("I want the catalog please"))

        assert out.effects == (EffectOp("propose", "send_catalog", "document"),)

    async def test_what_the_host_seeded_as_done_is_not_proposed_again(self) -> None:
        """The judgment stays at yes over the whole session; the channel is what says it was already sent."""
        done_ops = (PROPOSED, EffectOp("done", "send_datasheet", note="msg-1"))

        out = await capture_effects(question_judge_with())(envelope("and the price?", ((ASKS_DATASHEET, "here is the datasheet"),), done_ops))

        assert out.effects == ()

    async def test_it_shares_the_turn_with_the_sale_in_one_network_request(self) -> None:
        """`then(sale, effects)` compacts once and goes to TypeSafe once: `_read` asks them all."""
        judge_ = ScriptedJudge()
        model = Echo()
        question_judge = QuestionJudge(judge_, model)

        out = await then(close_sale_steps(question_judge), capture_effects(question_judge))(envelope(ASKS_DATASHEET))

        assert len(model.conversations) == 2 and judge_.calls == 1
        assert set(judge_.asked[0]["questions"]) == {*STATE_QUESTIONS, *SALE_LABELS}
        assert PROPOSED in out.effects and out.course != ()

    async def test_without_a_judge_it_warns_for_each_question_of_the_intents(self) -> None:
        out = await capture_effects(None)(envelope(ASKS_DATASHEET))

        assert out.effects == ()
        assert sorted(f.reason.split("`")[1] for f in out.fails) == sorted([ASKED_DATASHEET, ASKED_ACCOUNT, ASKED_CATALOG, ASKED_LINK, "wants_to_buy", "wants_to_buy", "chargeable_order",
                                                                                   "wants_to_buy", "said_payment_method", "chargeable_order"])
        assert {f.who for f in out.fails} == {"effects"}


class TestTheWriter:
    async def test_with_the_datasheet_proposed_the_request_carries_its_line(self) -> None:
        out = await dictation("", "")(envelope("hello", effects=(PROPOSED,)))

        assert out.said[0].text.endswith(EFFECT_LINES["send_datasheet"])

    async def test_without_effects_the_request_is_the_one_from_before_byte_for_byte(self) -> None:
        before = await dictation("", "")(envelope("hello"))
        handled = await dictation("", "")(envelope("hello", effects=(EffectOp("propose", "handoff", "handoff"), EffectOp("done", "handoff"))))

        assert before.said[0].text == handled.said[0].text, "human_handoff carries the handoff, not this line"
        assert "the system sends them" not in before.said[0].text
        assert "was already sent to them" not in before.said[0].text

    async def test_with_the_inbound_escalation_the_sale_line_does_not_go(self) -> None:
        """It is the advisor's last message: "ask them for the next thing missing" left a question nobody answers."""
        sale = (*SESSION, PlanOp("mark", "pest", status="done"))
        without_sale = await dictation("", "")(merge(envelope("I want Reapvane"), Log(course=sale)))
        with_escalation = await dictation("", "")(merge(envelope("I want Reapvane"), Log(course=sale, reports=(Report(ASKED_WHO, HANDOFF_LINES["card_payment"]),))))

        assert "ask them for the next thing missing" in without_sale.said[0].text
        assert "ask them for the next thing missing" not in with_escalation.said[0].text

    async def test_a_closed_effect_carries_what_went_out_and_not_the_current_line(self) -> None:
        """The `done` of an earlier turn is not announced again: it says it already went out, with what the host returned."""
        before = await dictation("", "")(envelope("hello"))
        done_ops = await dictation("", "")(
            envelope("hello", effects=(PROPOSED, EffectOp("done", "send_datasheet", args=(("file", "larvane.pdf"),))))
        )

        assert done_ops.said[0].text == before.said[0].text + "\n\nIn this conversation the PDF datasheet was already sent to them (file: larvane.pdf)."
        assert EFFECT_LINES["send_datasheet"] not in done_ops.said[0].text

    def test_the_sent_link_carries_the_url_and_the_total(self) -> None:
        link = EffectOp("propose", "send_payment_link", "payment_link")
        done_ops = EffectOp("done", "send_payment_link", args=(("url", "https://pay.example/l/abc"), ("currency", "GTQ"), ("total", "598.08")))

        assert sent_line(effects_of((link, done_ops))) == (
            "In this conversation the payment link was already sent to them (currency: GTQ; total: 598.08; url: https://pay.example/l/abc)."
        )

    def test_a_rejection_says_it_did_not_go_out_without_the_host_reason(self) -> None:
        rejection = EffectOp("reject", "send_datasheet", note="gateway down")

        line = sent_line(effects_of((PROPOSED, rejection)))

        assert line == "In this conversation the PDF datasheet could not be sent to them."
        assert "gateway" not in line

    def test_a_done_without_a_result_says_it_went_out(self) -> None:
        assert sent_line(effects_of((PROPOSED, EffectOp("done", "send_datasheet")))) == "In this conversation the PDF datasheet was already sent to them."

    def test_what_is_proposed_is_not_in_the_line_of_what_went_out(self) -> None:
        assert sent_line(effects_of((PROPOSED,))) == ""

    def test_one_line_per_proposed(self) -> None:
        two = effects_of((PROPOSED, EffectOp("propose", "send_payment_accounts", "bank_account")))

        assert effect_line(proposed(two)) == EFFECT_LINES["send_datasheet"] + "\n" + EFFECT_LINES["send_payment_accounts"]
        assert effect_line(()) == ""


class TestResolver:
    async def test_the_catalog_resolves_with_its_name_in_the_folder(self) -> None:
        """`catalog` is what the host looks for in the PDF folder: it gives `catalog.pdf`."""
        proposed_op = EffectOp("propose", "send_catalog", "document")

        out = await fill_effect_args(REAL)(answered(envelope("hello", effects=(proposed_op,)), "I am sending you the catalog"))

        assert out.effects == (EffectOp("resolve", "send_catalog", args=(("path", "catalog"),)),)

    async def test_the_datasheet_is_the_cited_source_that_exists(self) -> None:
        seen = answered(envelope("hello", effects=(PROPOSED,)), "Larvane works for you.\nSOURCE: products/Larvane.md")

        out = await fill_effect_args(REAL)(seen)

        assert out.effects == (EffectOp("resolve", "send_datasheet", args=(("path", "products/larvane.md"),)),)

    async def test_two_datasheets_are_two_args(self) -> None:
        seen = answered(
            envelope("hello", effects=(PROPOSED,)),
            "Larvane or Fungvane.\nSOURCE: products/larvane.md\nSOURCE: products/fungvane.md",
        )

        out = await fill_effect_args(REAL)(seen)

        assert effects_of((PROPOSED, *out.effects))[0].args == (
            ("path", "products/fungvane.md"),
            ("path", "products/larvane.md"),
        )

    async def test_none_payments_or_an_invented_path_are_not_datasheets(self) -> None:
        for answer in (
            "I found nothing.\nSOURCE: none",
            "Payment is by transfer.\nSOURCE: company_info/payments.md",
            "Larvane works for you.\nSOURCE: products/invented.md",
        ):
            assert await fill_effect_args(REAL)(answered(envelope("hello", effects=(PROPOSED,)), answer)) == ZERO

    async def test_what_the_host_closed_is_not_resolved(self) -> None:
        closed_ops = (PROPOSED, EffectOp("done", "send_datasheet"))
        seen = answered(envelope("hello", effects=closed_ops), "Larvane works for you.\nSOURCE: products/larvane.md")

        assert await fill_effect_args(REAL)(seen) == ZERO

    async def test_the_account_needs_no_resolving(self) -> None:
        account = (EffectOp("propose", "send_payment_accounts", "bank_account"),)
        seen = answered(envelope("hello", effects=account), "Here is the account.\nSOURCE: company_info/payments.md")

        assert await fill_effect_args(REAL)(seen) == ZERO


class TestTheHost:
    def test_it_does_what_has_args_or_needs_none_and_rejects_what_needs_them_and_has_none(self) -> None:
        out = effects_of(
            (
                PROPOSED,
                EffectOp("resolve", "send_datasheet", args=(("path", "products/larvane.md"),)),
                EffectOp("propose", "send_payment_accounts", "bank_account"),
            )
        )
        no_datasheet = effects_of((PROPOSED,))

        assert host_sim(out) == (
            EffectOp("done", "send_datasheet", note="simulated", args=(("file", "larvane.pdf"),)),
            EffectOp("done", "send_payment_accounts", note="simulated"),
        )
        assert host_sim(no_datasheet) == (EffectOp("reject", "send_datasheet", note="no args to send"),)

    def test_the_simulated_link_returns_nobody_s_url_and_the_total(self) -> None:
        """Like the real host, so the next turn of the eval sees `result`."""
        link = effects_of(
            (
                EffectOp("propose", "send_payment_link", "payment_link"),
                EffectOp("resolve", "send_payment_link", args=(("item", "{}"), ("currency", "GTQ"), ("total", "598.08"))),
            )
        )

        assert host_sim(link) == (
            EffectOp("done", "send_payment_link", note="simulated", args=(("url", SIMULATED_URL), ("currency", "GTQ"), ("total", "598.08"))),
        )

    def test_what_is_already_closed_is_not_touched(self) -> None:
        assert host_sim(effects_of((PROPOSED, EffectOp("done", "send_datasheet")))) == ()

    def test_the_terminal_line(self) -> None:
        e = effects_of((PROPOSED, EffectOp("resolve", "send_datasheet", args=(("path", "products/larvane.md"),))))

        assert effects_state(e) == "send_datasheet proposed (products/larvane.md)"
        assert effects_state(()) == "no effects"


class TestTurn:
    async def test_it_seeds_the_effects_and_returns_only_those_of_the_turn(self) -> None:
        seen_by_agent: list[Log] = []

        async def agent(seen: Log) -> Log:
            seen_by_agent.append(seen)
            return Log(effects=(EffectOp("propose", "send_payment_accounts", "bank_account"),))

        done_ops = (PROPOSED, EffectOp("done", "send_datasheet"))
        out = await turn(agent, ASKS_ACCOUNT, (), SESSION, done_ops)

        assert seen_by_agent[0].effects == done_ops and seen_by_agent[0].course == SESSION
        assert out.effects == (EffectOp("propose", "send_payment_accounts", "bank_account"),)

    async def test_the_end_to_end_shape_without_a_model(self) -> None:
        """Incoming: the sale and the effects. Outgoing: the sale and the resolver. A turn in which the
        customer asks for the datasheet and a scripted writer cites it."""
        question_judge = question_judge_with()

        async def scripted_writer(seen: Log) -> Log:
            assert PROPOSED in seen.effects, "the writer sees the proposal before writing"
            return Log(said=(Message(Role.ASSISTANT, "Larvane works for you.\nSOURCE: products/larvane.md"),))

        agent = then(close_sale_steps(question_judge), capture_effects(question_judge), scripted_writer, close_sale_steps(question_judge), fill_effect_args(REAL))
        out = await turn(agent, ASKS_DATASHEET, ())

        [datasheet] = proposed(effects_of(out.effects))
        assert datasheet.args == (("path", "products/larvane.md"),)
        assert host_sim(effects_of(out.effects)) == (EffectOp("done", "send_datasheet", note="simulated", args=(("file", "larvane.pdf"),)),)
        assert isinstance(out.course, tuple) and any(isinstance(op, PlanOp) for op in out.course)


class TestThePaymentLink:
    def test_the_args_are_the_order_the_inbound_already_judged(self) -> None:
        """The resolver does not go to the network: it reads the order from the turn's judgment, and without a judge there are no args."""
        items = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2}])

        class Judged:
            def known_order(self, seen: Log) -> tuple:
                return items

        payment = resolvers(REAL, Judged())["send_payment_link"]  # type: ignore[arg-type]

        assert payment(envelope("paying by link")) == payment_args(items)
        assert resolvers(REAL)["send_payment_link"](envelope("paying by link")) == ()


GIVES_THE_DATA = "paying by transfer, NIT 1234567-8, received by Rodrigo Pérez, 5555-0101, zona 5, Quetzaltenango"


class TestTheSAPDraft:
    def test_the_args_are_the_link_order_and_the_form(self) -> None:
        """The same order as the link, with the `item_code`, plus the complete form with the keys from before; without either of the two, nothing."""
        items = price_order([{"product": "Reapvane", "presentation": "1 L", "quantity": 2}])
        complete = {"legal_name": "Agro SA", "nit": "1234567-8", "recipient": "Rodrigo Pérez", "phone": "5555-0101", "address": "zona 5", "payment_method": "transfer"}

        class Judged:
            def __init__(self, order: tuple[Item, ...]) -> None:
                self.order = order

            def known_order(self, seen: Log) -> tuple[Item, ...]:
                return self.order

        def draft(order: tuple[Item, ...], form: dict[str, str]) -> Args:
            return resolvers(REAL, Judged(order), Forms(form))["sap_draft"](envelope("hello"))  # type: ignore[arg-type]

        assert draft(items, complete) == (
            *payment_args(items),
            ("nit", "1234567-8"),
            ("name", "Agro SA"),
            ("recipient", "Rodrigo Pérez"),
            ("phone", "5555-0101"),
            ("address", "zona 5"),
            ("payment_method", "transfer"),
        )
        assert json.loads(dict(draft(items, complete))["item"])["item_code"] == "PT0107"
        assert draft(items, {k: v for k, v in complete.items() if k != "address"}) == ()
        assert draft(price_order([{"product": "Reapvane", "presentation": None, "quantity": 2}]), complete) == ()
        assert resolvers(REAL)["sap_draft"](envelope("hello")) == ()

    def test_the_simulated_host_returns_an_order_number_and_rejects_the_empty_one(self) -> None:
        proposed_op = EffectOp("propose", "sap_draft", "sap_draft")
        with_args = effects_of((proposed_op, EffectOp("resolve", "sap_draft", args=(("item", "{}"), ("nit", "CF")))))

        assert host_sim(with_args) == (EffectOp("done", "sap_draft", note="simulated", args=(("order", "simulated"),)),)
        assert host_sim(effects_of((proposed_op,))) == (EffectOp("reject", "sap_draft", note="no args to send"),)

    def test_the_writer_does_not_announce_it(self) -> None:
        assert effect_line(effects_of((EffectOp("propose", "sap_draft", "sap_draft"),))) == ""

    def test_done_gives_the_writer_the_order_number_in_case_they_ask(self) -> None:
        proposed_op = EffectOp("propose", "sap_draft", "sap_draft")
        done_ops = effects_of((proposed_op, EffectOp("done", "sap_draft", args=(("order", "1042"),))))

        assert sent_line(done_ops) == REGISTERED.format(order="1042")
        assert "1042" in sent_line(done_ops)

    def test_without_a_number_or_rejected_it_says_nothing(self) -> None:
        proposed_op = EffectOp("propose", "sap_draft", "sap_draft")

        assert sent_line(effects_of((proposed_op, EffectOp("done", "sap_draft")))) == ""
        assert sent_line(effects_of((proposed_op, EffectOp("reject", "sap_draft", note="SAP 503")))) == ""
