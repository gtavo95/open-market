"""The billing form (`world/form.py`, `roles/form.py`): it carries over, changes only what the customer gives or corrects, and handles what they ask about their purchase."""

from __future__ import annotations

import pytest
from catalejo.core import Log, Message, PlanOp, Role, project

from core_agent.prompts.judge import ASKS_RESET, ASKS_SUMMARY, GIVES_DATA
from core_agent.prompts.writer import FORM_ASK, FORM_CONFIRM, FORM_WHO, RESET_LINE, RESUME_LINE, SUMMARY_LINE
from core_agent.roles.form import BILLED, Forms, form_text
from core_agent.roles.sale import SESSION, sale_line
from core_agent.roles.writer import dictation
from core_agent.world import catalog
from core_agent.world.dialogue import History, wrap
from core_agent.world.form import apply, check, missing, prompt, schema, title
from core_agent.world.question_judge import spoken
from tests.doubles import FORM_HEAD, HIGH, LOW, Echo, ScriptedJudge, question_judge_with
from core_agent.world.question_judge import QuestionJudge

COMPLETE = {"nit": "1234567-8", "recipient": "Rodrigo Pérez", "phone": "5555-0101", "address": "zona 5, Quetzaltenango"}


@pytest.fixture(autouse=True)
def repo_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """The form from `okf/`: other tests move `BUNDLE` to a small catalog with no forms."""
    monkeypatch.setattr(catalog, "BUNDLE", catalog.CATALOG)


def envelope(question: str, history: History = (), course: tuple[PlanOp, ...] = ()) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, history)),), course=course)


def form_calls(model: Echo) -> int:
    return sum(1 for c in model.conversations if c[-1].text.startswith(FORM_HEAD))


class TestTheBundle:
    def test_the_fields_come_from_forms_billing(self) -> None:
        assert [c["id"] for c in schema()] == ["legal_name", "nit", "recipient", "phone", "email", "address", "payment_method"]
        assert [c["id"] for c in schema() if c["required"]] == ["nit", "recipient", "phone", "address", "payment_method"]
        assert next(c for c in schema() if c["id"] == "payment_method")["options"] == ["link", "transfer"]
        assert title() == "Billing details"

    def test_what_is_not_in_the_form_does_not_go_in(self) -> None:
        assert check({"nit": " CF ", "color": "blue", "payment_method": "check", "recipient": ""}) == {"nit": "CF"}

    def test_the_required_ones_are_missing_in_order(self) -> None:
        assert missing({}) == ["nit", "recipient", "phone", "address", "payment_method"]
        assert missing({**COMPLETE, "payment_method": "link"}) == []


class TestTheChanges:
    def test_a_value_records_or_corrects_a_null_removes_and_the_rest_stays(self) -> None:
        seed = {"nit": "1234567-8", "address": "Xela", "legal_name": "Agro SA"}

        out = apply(seed, {"address": "Cobán", "legal_name": None, "phone": "5555"})

        assert out == {"nit": "1234567-8", "address": "Cobán", "phone": "5555"}

    def test_the_model_does_not_touch_the_payment_method(self) -> None:
        assert apply({"payment_method": "link"}, {"payment_method": None}) == {"payment_method": "link"}
        assert apply({}, {"payment_method": "transfer"}) == {}

    def test_without_a_changes_object_it_stays_the_same(self) -> None:
        assert apply({"nit": "CF"}, "nothing") == {"nit": "CF"}


class TestTheCell:
    async def test_it_records_what_the_customer_gave_and_the_method_from_the_label(self) -> None:
        form = Forms()

        out = await form.cell(Echo(), question_judge_with())(envelope("paying by transfer, NIT 1234567-8, received by Rodrigo Pérez"))

        assert form.latest == {**COMPLETE, "payment_method": "transfer"}
        assert form.complete() and out.reports == ()

    async def test_without_data_in_the_message_it_does_not_pay_for_the_call_and_does_not_move(self) -> None:
        """The drift: the NIT recorded turns ago does not change because the model reads the conversation differently."""
        model = Echo()
        form = Forms({"nit": "1234567-8"})

        await form.cell(model, QuestionJudge(ScriptedJudge({GIVES_DATA: LOW}), model))(envelope("when does it arrive?", (("NIT 7654321-0", "noted"),)))

        assert form.latest == {"nit": "1234567-8"}
        assert form_calls(model) == 0

    async def test_it_changes_the_address_and_nothing_else(self) -> None:
        model = Echo()
        form = Forms({**COMPLETE, "payment_method": "link"})

        await form.cell(model, QuestionJudge(ScriptedJudge({GIVES_DATA: HIGH}), model))(envelope("change the address to Cobán"))

        assert form.latest == {**COMPLETE, "address": "Cobán", "payment_method": "link"}
        assert form_calls(model) == 1

    async def test_starting_over_empties_the_form_and_warns(self) -> None:
        form = Forms({**COMPLETE, "payment_method": "link"})

        out = await form.cell(Echo(), question_judge_with())(envelope("delete it, let's start over"))

        assert form.latest == {} and form.reset
        assert [(r.who, r.text) for r in out.reports] == [(FORM_WHO, RESET_LINE)]

    async def test_the_reset_lasts_one_turn(self) -> None:
        form = Forms()
        cell = form.cell(Echo(), question_judge_with())
        await cell(envelope("delete it"))

        await cell(envelope("I want 2 liters of Reapvane"))

        assert not form.reset

    async def test_the_summary_carries_what_is_recorded_and_what_is_missing(self) -> None:
        form = Forms({"nit": "1234567-8"})

        out = await form.cell(Echo(), question_judge_with())(envelope("what do I have so far?"))

        (report,) = out.reports
        assert report.who == FORM_WHO and report.text.endswith(SUMMARY_LINE)
        assert "- NIT: 1234567-8" in report.text
        assert "Missing: Recipient, Recipient's phone, Delivery address, Payment method." in report.text

    async def test_the_return_opens_with_what_is_missing(self) -> None:
        form = Forms({"nit": "1234567-8"}, resumed=True)

        out = await form.cell(Echo(), question_judge_with())(envelope("hello"))

        (report,) = out.reports
        assert report.text == f"{form_text(form.latest)}\n\n{RESUME_LINE}"

    async def test_with_the_judge_down_it_stays_as_it_was(self) -> None:
        form = Forms({"nit": "CF"})

        out = await form.cell(Echo(), question_judge_with(down=True))(envelope("NIT 1234567-8"))

        assert form.latest == {"nit": "CF"} and form.errors == 1 and out.reports == ()

    async def test_complete_invoice_is_the_form_with_all_the_required_ones(self) -> None:
        judge = Forms({**COMPLETE, "payment_method": "link"}).judge()

        assert await judge(envelope("hello"), frozenset({BILLED, "wants_to_buy"})) == {BILLED: 1.0}
        assert await Forms(COMPLETE).judge()(envelope("hello"), frozenset({BILLED})) == {BILLED: 0.0}


class TestTheOrderEmpties:
    async def test_with_starting_over_the_judgment_comes_out_without_an_order(self) -> None:
        question_judge = question_judge_with({ASKS_RESET: HIGH})
        seen = envelope("delete it", (("I want two liters of Reapvane", "done"),))

        assert await question_judge.order(seen) == ()
        judgment = question_judge.last("delete it", (("I want two liters of Reapvane", "done"),))
        assert judgment is not None and judgment.as_dict()["order"]["restarted"] is True

    async def test_without_asking_for_it_the_order_continues(self) -> None:
        question_judge = question_judge_with({ASKS_RESET: LOW, ASKS_SUMMARY: HIGH})

        assert await question_judge.order(envelope("what do I have so far?", (("I want two liters of Reapvane", "done"),))) != ()


class TestTheWriter:
    def test_data_asks_for_the_first_required_one_missing(self) -> None:
        sale = project((*SESSION, *(PlanOp("mark", i, status="done") for i in ("pest", "product", "recipe", "quantity", "decision", "method", "charge"))))

        ask = Forms({"nit": "CF", "recipient": "Ana"}).next_ask()

        assert ask == FORM_ASK.format(field="Recipient's phone")
        assert ask in sale_line(sale, data_ask=ask)
        assert "NIT, name and phone" in sale_line(sale)

    async def test_on_the_reset_turn_the_sale_line_does_not_go(self) -> None:
        form = Forms()
        form.reset = True
        sale = (*SESSION, PlanOp("mark", "pest", status="done"))

        with_sale = await dictation("", "")(envelope("delete it", course=sale))
        after_reset = await dictation("", "", form=form)(envelope("delete it", course=sale))

        assert "ask them for the next thing" in with_sale.said[0].text
        assert "ask them for the next thing" not in after_reset.said[0].text


PREVIOUS = {**COMPLETE, "payment_method": "link"}
SOLD = (("I want two liters of Reapvane, NIT 1234567-8", "Done, here is the link"), ("I already paid", "Thank you! Your order is ready."))


def after_closed_sale(question: str) -> Log:
    """The envelope with a sale closed on the last turn of the history."""
    return Log(said=(Message(Role.USER, wrap(question, SOLD, closed=1)),))


class TestAfterAClosedSale:
    async def test_the_order_and_the_gates_read_from_the_close(self) -> None:
        question_judge = question_judge_with()
        seen = after_closed_sale("I want 1 liter of Roycel")

        assert await question_judge.order(seen) == ()
        assert spoken(seen)["conversation"] == []
        assert "Reapvane" in seen.said[0].text, "the writer still sees what was sold"

    async def test_the_previous_sale_data_do_not_count_until_they_confirm(self) -> None:
        form = Forms(previous=PREVIOUS)

        assert form.latest == {} and not form.complete()
        assert form.next_ask() == FORM_CONFIRM.format(
            fields="NIT: 1234567-8, Recipient: Rodrigo Pérez, Recipient's phone: 5555-0101, Delivery address: zona 5, Quetzaltenango"
        )

    def test_what_they_already_gave_again_is_not_confirmed_again(self) -> None:
        form = Forms({"nit": "7654321-0"}, previous=PREVIOUS)

        assert form.next_ask() == FORM_CONFIRM.format(
            fields="Recipient: Rodrigo Pérez, Recipient's phone: 5555-0101, Delivery address: zona 5, Quetzaltenango"
        )
        assert '"nit"' not in prompt(form.latest, form.previous).split("The details from their earlier purchase")[1]

    def test_without_a_previous_sale_the_form_request_is_the_usual_one(self) -> None:
        assert prompt({"nit": "CF"}) == prompt({"nit": "CF"}, {})
        assert "earlier purchase" not in prompt({"nit": "CF"})
