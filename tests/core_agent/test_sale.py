"""The sale wired in `roles/sale.py`: the plan in `course` and the writer's line, with no bundle or network."""

from __future__ import annotations

from core_agent.agent import turn
from core_agent.prompts.judge import LABEL_GATES, SALE_LABELS, REPLY_QUESTIONS, HANDOFF_REASON_QUESTIONS, SALE_QUESTIONS
from core_agent.world.question_judge import STATE_QUESTIONS
from core_agent.prompts.writer import ASKS, CASE_LINES, HUMAN_LINE, PAYMENT_LINES
from core_agent.roles.form import BILLED
from core_agent.roles.sale import (
    SESSION,
    ask_next,
    close_sale_steps,
    nothing_to_search,
    sale_line,
    sale_state,
)
from core_agent.roles.writer import dictation
from core_agent.world.dialogue import HUMAN, History, wrap
from core_agent.world.facts import LOG_FACTS
from core_agent.world.question_judge import ORDER_GATES, QuestionJudge
from catalejo.core import Entry, Log, Message, Node, PlanOp, Report, Role, closed, find_step, merge, pending, project
from tests.doubles import Echo, ScriptedJudge, question_judge_with

PEST = "I have whitefly on the tomato"

READ = "products/larvane.md: 2 lines, from 1 to 2.\n---\ntitle: Larvane"
"""A datasheet opened the way `read` leaves it in the writer's request: the header and the text."""


def envelope(question: str, history: History = (), course: tuple[PlanOp, ...] = ()) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, history)),), course=course)


def with_closed(*ids: str) -> tuple[PlanOp, ...]:
    """The sale seeded with those leaves already closed."""
    return (*SESSION, *(PlanOp("mark", i, status="done") for i in ids))


class TestThePlan:
    def test_each_gate_has_someone_to_answer_it(self) -> None:
        names = {op.done_when for op in SESSION if op.done_when}

        assert names <= LOG_FACTS.keys() | SALE_QUESTIONS.keys() | LABEL_GATES.keys() | ORDER_GATES.keys() | REPLY_QUESTIONS.keys() | {BILLED}

    def test_what_is_asked_of_the_customer_are_leaves_of_the_sale(self) -> None:
        assert set(ASKS) <= {op.id for op in SESSION}

    def test_it_starts_by_asking_for_the_pest(self) -> None:
        plan = project(SESSION)

        assert nothing_to_search(plan)
        assert ask_next(plan) is not None and ask_next(plan).id == "pest"  # type: ignore[union-attr]
        assert sale_state(plan) == "sale 0/8: next `pest`"


class TestTheSaleAtTheEdge:
    async def test_the_first_turn_seeds_and_closes_what_the_customer_said(self) -> None:
        out = await close_sale_steps(question_judge_with())(envelope(PEST))

        plan = project(out.course)
        assert [s.id for s in plan] == [op.id for op in SESSION]
        assert closed(plan, find_step(plan, "pest"))  # type: ignore[arg-type]
        assert [s.id for s in pending(plan) if s.done_when] == ["product", "recipe", "quantity", "decision", "method", "data"]
        assert not out.fails

    async def test_the_next_turn_receives_the_sale_and_does_not_ask_again_what_is_closed(self) -> None:
        """What `close_steps` asks the judge is only what is open; what the judge sends TypeSafe
        is something else (all of them, in one request: `test_gates`)."""
        asked: list[frozenset[str]] = []

        class Spy(QuestionJudge):
            async def __call__(self, seen: Log, names: frozenset[str]) -> dict[str, float]:
                asked.append(names)
                return await super().__call__(seen, names)

        question_judge = Spy(ScriptedJudge(), Echo())
        first = await close_sale_steps(question_judge)(envelope(PEST))

        second = await close_sale_steps(question_judge)(envelope("I want two liters", ((PEST, "Larvane works for you"),), first.course))

        plan = project((*first.course, *second.course))
        assert closed(plan, find_step(plan, "quantity"))  # type: ignore[arg-type]
        assert "has_search_terms" not in asked[-1]
        assert "order_with_quantities" in asked[-1]
        assert sale_state(plan) == "sale 2/8: next `product`"

    async def test_the_exit_closes_what_the_turn_did_and_what_the_advisor_answered(self) -> None:
        """`recipe` with the datasheet that went through; `product` with the answer, a separate request and without going back to compaction."""
        judge_ = ScriptedJudge()
        question_judge = QuestionJudge(judge_, Echo())
        seen = envelope(PEST)
        opening = await close_sale_steps(question_judge)(seen)
        turn_ = Log(reads=2, said=(Message(Role.USER, READ), Message(Role.ASSISTANT, "I recommend Larvane, certified for tomato.")))

        closing = await close_sale_steps(question_judge)(merge(merge(seen, opening), turn_))

        plan = project((*opening.course, *closing.course))
        assert closed(plan, find_step(plan, "product"))  # type: ignore[arg-type]
        assert closed(plan, find_step(plan, "recipe"))  # type: ignore[arg-type]
        assert [set(a["questions"]) for a in judge_.asked] == [{*STATE_QUESTIONS, *SALE_LABELS}, {*REPLY_QUESTIONS, *HANDOFF_REASON_QUESTIONS}], (
            "two requests per turn and no more: the customer's state, and everything about the answer together"
        )

    async def test_querying_the_catalog_does_not_close_product(self) -> None:
        """The searcher queries on every turn; what closes `product` is having recommended one."""
        question_judge = question_judge_with()
        seen = envelope(PEST)
        opening = await close_sale_steps(question_judge)(seen)
        turn_ = Log(reads=2, said=(Message(Role.USER, READ), Message(Role.ASSISTANT, "How many liters do you want?")))

        closing = await close_sale_steps(question_judge)(merge(merge(seen, opening), turn_))

        plan = project((*opening.course, *closing.course))
        assert not closed(plan, find_step(plan, "product"))  # type: ignore[arg-type]
        assert sale_state(plan) == "sale 2/8: next `product`"

    async def test_without_a_judge_the_sale_warns_for_each_customer_slot(self) -> None:
        """For each network gate the plan names; the ones that propose effects are warned by `propose_effects`. `complete_invoice` is answered by the form."""
        out = await close_sale_steps(None)(envelope(PEST))

        plan = project(out.course)
        gated = {op.done_when for op in SESSION if op.done_when} - LOG_FACTS.keys() - {BILLED}
        assert not closed(plan, find_step(plan, "pest"))  # type: ignore[arg-type]
        assert sorted(f.reason.split("`")[1] for f in out.fails) == sorted(gated)
        assert gated < SALE_QUESTIONS.keys() | LABEL_GATES.keys() | ORDER_GATES.keys() | REPLY_QUESTIONS.keys()


class TestTheSaleLine:
    def test_with_nothing_to_search_there_is_no_line(self) -> None:
        assert sale_line(project(SESSION)) == ""

    def test_with_product_pending_it_asks_for_the_quantity_conditionally(self) -> None:
        line = sale_line(project(with_closed("pest")))

        assert line.startswith("Answer what they asked")
        assert "If you find them a product" in line
        assert ASKS["quantity"] in line

    def test_with_product_closed_it_asks_plainly(self) -> None:
        line = sale_line(project(with_closed("pest", "product", "recipe")))

        assert "At the end, in one line" in line
        assert ASKS["quantity"] in line

    def test_what_was_already_asked_with_no_answer_is_not_asked_again(self) -> None:
        """no-repeat-quantity, Sep 28, 2026: the advisor had already asked for the liters twice and the line told it to ask a third time."""
        line = sale_line(project(with_closed("pest", "product", "recipe")), frozenset({"quantity"}))

        assert line.startswith("Answer what they asked")
        assert "do not ask them for it again" in line
        assert "ask them for the next thing" not in line

    def test_with_nothing_to_ask_the_customer_there_is_no_line(self) -> None:
        assert sale_line(project(with_closed(*ASKS))) == ""

    async def test_the_writer_receives_it_at_the_end_of_her_request(self) -> None:
        out = await dictation("", "")(envelope("it's two manzanas", course=with_closed("pest")))

        assert out.said[0].text.endswith(ASKS["quantity"] + ". If they already said it in other words, do not ask them for it again.")

    async def test_with_a_human_advisor_in_between_the_writer_knows_it(self) -> None:
        out = await dictation("", "")(envelope("thanks", (("can you invoice it to Agro S.A.?", HUMAN + "Sure, it is now under the name Agro S.A."),)))

        assert HUMAN_LINE in out.said[0].text

    async def test_without_a_human_advisor_the_line_does_not_go(self) -> None:
        out = await dictation("", "")(envelope("thanks", ((PEST, "Larvane works for you"),)))

        assert HUMAN_LINE not in out.said[0].text

    async def test_without_a_sale_the_request_is_the_one_from_before(self) -> None:
        out = await dictation("", "")(envelope("it's two manzanas"))

        assert "SOURCE: none" in out.said[0].text
        assert "for the sale" not in out.said[0].text


def with_report(question: str, text: str) -> Log:
    return Log(said=(Message(Role.USER, wrap(question, ())),), reports=(Report("searcher", text),))


class TestTheCaseOfTheTurn:
    """The writer receives only the rule of the case the judge read from the searcher's report (Sep 28, 2026)."""

    async def test_it_carries_only_the_rule_of_its_case(self) -> None:
        judge = question_judge_with(label="not_covered")
        out = await dictation("", "", judge)(with_report("what works for leafcutter ants?", "The catalog does not cover leafcutter ants."))

        text = out.said[0].text
        assert CASE_LINES["not_covered"] in text
        assert all(line not in text for case, line in CASE_LINES.items() if case != "not_covered")
        assert judge._client.asked[-1]["state"] == {"last_message": "what works for leafcutter ants?", "report": "The catalog does not cover leafcutter ants."}  # type: ignore[attr-defined]

    async def test_a_normal_turn_carries_none(self) -> None:
        out = await dictation("", "", question_judge_with())(with_report("how much Reapvane per manzana?", "Reapvane: 1 L/mz."))

        assert all(line not in out.said[0].text for line in CASE_LINES.values())

    async def test_without_a_judgment_all_four_go_as_before(self) -> None:
        out = await dictation("", "", question_judge_with(down=True))(with_report("hello", "nothing"))

        assert all(line in out.said[0].text for line in CASE_LINES.values())


class TestTurn:
    async def test_it_seeds_the_envelope_and_the_sale(self) -> None:
        seen_by_agent: list[Log] = []

        async def agent(seen: Log) -> Log:
            seen_by_agent.append(seen)
            return Log(course=(PlanOp("mark", "pest", status="done"),))

        history: History = ((PEST, "Larvane works for you"),)
        out = await turn(agent, "it's two manzanas", history, SESSION)

        assert seen_by_agent[0].said[0].text == wrap("it's two manzanas", history)
        assert seen_by_agent[0].course == SESSION
        assert out.course == (PlanOp("mark", "pest", status="done"),)
        assert seen_by_agent[0].reports == ()

    async def test_the_host_memory_is_seeded_and_does_not_come_back(self) -> None:
        """The `memory` channel is filled by the host and no cell writes it (logbook todo #24)."""
        seen_by_agent: list[Log] = []
        memory = (Entry(0, "customer", "2 gallons of Larvane"), Node(1, 0, "customer: 2 gallons of Larvane"))

        async def agent(seen: Log) -> Log:
            seen_by_agent.append(seen)
            return Log()

        out = await turn(agent, "the same as last time", (), SESSION, memory=memory)

        assert seen_by_agent[0].memory == memory
        assert out.memory == ()

    async def test_the_payment_the_host_sends_reaches_the_writer(self) -> None:
        seen_by_agent: list[Log] = []

        async def agent(seen: Log) -> Log:
            seen_by_agent.append(seen)
            return Log()

        await turn(agent, "I already paid", ((PEST, "Larvane works for you"),), SESSION, payment="paid")
        out = await dictation("", "")(seen_by_agent[0])

        assert PAYMENT_LINES["paid"] in out.said[0].text
        assert PAYMENT_LINES["pending"] not in out.said[0].text
