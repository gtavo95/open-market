"""The advisor behind a server: what it serves, with what backing, and what it does NOT share between queries.

The agent is the `core_agent/` package and is tested in catalejo. Here the host is tested: that it
builds the agent with the catalog voice, that the sale comes in and goes out, that the cap
cuts and releases, and that the `Answer` says what the `Log` said.
"""

from __future__ import annotations

import asyncio
import multiprocessing
from pathlib import Path

import pytest
from catalejo.core import Conversation, EffectOp, Log, Message, PlanOp, Role
from catalejo.llm import Reply, ScriptedModel, Usage

from core_agent import ASKS, HANDOFF, HANDOFF_REASONS, SESSION, messages
from core_agent.prompts.writer import EFFECT_LINES, WRITER, WRITER_PREAMBLE
from core_agent.world import governance
from tests.doubles import question_judge_with
from core_agent.world import typesafe
from host import Advisor, Catalog, TurnFailed, load
from host.agent import cost, final, prose, raw, sources
from host.effects import Pending
from host.effects import summary as effects_summary
from host.sale import summary

DATASHEET = "products/hyphavane.md"


def said(text: str, role: Role = Role.ASSISTANT) -> Message:
    return Message(role, text)


def block(code: str) -> str:
    return f"```python\n{code}\n```"


class Scripted(ScriptedModel):
    """A `ScriptedModel` that is also a `Provider`: it has a name and can be closed."""

    model = "scripted"
    closed = False

    async def aclose(self) -> None:
        self.closed = True


class Hung:
    """A Provider that never answers: what the server sees when the provider hangs."""

    model = "hung"

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def complete(self, conv: Conversation) -> Reply:
        self.started.set()
        await asyncio.sleep(60)
        return Reply(Message(Role.ASSISTANT, "late"))

    async def aclose(self) -> None:
        pass


SEARCH = block("print(grep(catalog, 'thrips'))")
REPORT = f"Hyphavane covers thrips and is certified on tomato.\nSOURCE: {DATASHEET}"
WRITE_PROSE = "Hyphavane: 1.0 to 1.5 l/ha in 200 l of water, foliar route. How many liters do you want?"
WRITE = f"{WRITE_PROSE}\nSOURCE: {DATASHEET}"


def advisor(small_catalog: Catalog, *answers: str, **kw: object) -> tuple[Advisor, Scripted]:
    """The prod advisor in process, with the model scripted searcher → writer and the scripted gates of `doubles.py`."""
    model = Scripted(*answers)
    return Advisor(small_catalog, model, question_judge=question_judge_with(), contained=False, **kw), model  # type: ignore[arg-type]


class TestCost:
    def test_with_the_adapter_count_the_total_is_input_plus_output(self) -> None:
        """The `spent` of the `Log` does not see the judge; the adapter's count does, and it rules."""
        usage = Usage(input=1000, cached=600, output=200, calls=3)

        assert cost(usage, typesafe.Spend(tokens=900, calls=2), spent=700) == {
            "tokens": 1200,
            "tokens_input": 1000,
            "tokens_cached": 600,
            "tokens_output": 200,
            "tokens_typesafe": 900,
        }

    def test_without_the_adapter_count_the_total_is_the_log_one(self) -> None:
        assert cost(Usage(), typesafe.Spend(), spent=700)["tokens"] == 700

    async def test_what_typesafe_charges_is_counted_per_turn(self, small_catalog: Catalog) -> None:
        """The judge double charges 100 per request and the turn carries its own, apart from the model."""
        a, _ = advisor(small_catalog, SEARCH, REPORT, WRITE)

        r = await a.ask("thrips on tomato")

        assert r.tokens_typesafe > 0 and r.tokens_typesafe % 100 == 0

    async def test_a_turn_that_raises_goes_out_with_what_it_managed_to_charge(
        self, small_catalog: Catalog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The loop turns model failures into `fails`; what raises anyway is a bug, and it is charged."""

        async def broken(*_: object) -> Log:
            typesafe.charge(40)
            raise ZeroDivisionError("bug")

        monkeypatch.setattr("host.agent.core_agent.turn", broken)
        a, _ = advisor(small_catalog)

        with pytest.raises(TurnFailed) as e:
            await a.ask("thrips on tomato")

        assert "ZeroDivisionError: bug" in str(e.value)
        assert e.value.cost["tokens_typesafe"] == 40
        assert a.free == 2, "the slot comes back anyway"


class TestFinal:
    def test_the_last_said_that_is_not_code_without_its_sources(self) -> None:
        out = Log(said=(said("dose?", Role.USER), said("1.0 l/ha\nSOURCE: " + DATASHEET)))

        assert final(out) == "1.0 l/ha"

    def test_prose_removes_the_source_lines_and_nothing_else(self) -> None:
        """`SOURCE: none` is for the host; the prose is what reaches WhatsApp."""
        assert prose("For thrips use Isaria.\n\nHow many manzanas?\n\nSOURCE: none") == "For thrips use Isaria.\n\nHow many manzanas?"
        assert prose(f"Use 1 L.\nsource: {DATASHEET}\nSOURCE: products/other.md") == "Use 1 L."
        assert prose("no sources") == "no sources"
        assert prose("SOURCE: none") == ""

    def test_the_question_in_its_own_message(self) -> None:
        """The writer separates with `---`; the text joins them without the separator."""
        said_ = f"For thrips use Isaria.\n---\nHow many liters do you need?\n---\nSOURCE: {DATASHEET}"
        out = Log(said=(said("thrips?", Role.USER), said(said_)))

        assert messages(prose(raw(out))) == ("For thrips use Isaria.", "How many liters do you need?")
        assert final(out) == "For thrips use Isaria.\n\nHow many liters do you need?"
        assert sources(raw(out)) == (DATASHEET,)
        assert messages("A single thing.\n\nIn two paragraphs.") == ("A single thing.\n\nIn two paragraphs.",)
        assert messages("") == ()

    def test_a_source_stuck_to_the_sentence_does_not_reach_the_customer_either(self) -> None:
        """"…business days. SOURCE: company_info/shipping.md", on a single line."""
        said_ = f"It reaches you in 4 to 7 business days. SOURCE: {DATASHEET}"
        out = Log(said=(said("when?", Role.USER), said(said_)))

        assert final(out) == "It reaches you in 4 to 7 business days."
        assert sources(raw(out)) == (DATASHEET,)

    def test_a_code_block_is_not_an_answer(self) -> None:
        out = Log(said=(said("I see"), said(block("print(1)"))))

        assert final(out) == "I see"

    def test_what_the_repl_said_is_not_either(self) -> None:
        out = Log(said=(said("hi"), said("products/x.md:3: dose 1 l/ha", Role.USER)))

        assert final(out) == "hi"

    def test_without_prose_it_is_empty_and_not_a_filler(self) -> None:
        """The API has a 502 for this; the CLI does not, and that is why there is a text there."""
        assert final(Log(said=(said(block("print(1)")),))) == ""
        assert final(Log()) == ""


class TestSources:
    def test_one_per_line_without_repeating(self) -> None:
        text = f"use Isaria\nSOURCE: {DATASHEET}\nSOURCE: products/other.md\nSOURCE: {DATASHEET}"

        assert sources(text) == (DATASHEET, "products/other.md")

    def test_several_on_one_line_separated_by_comma(self) -> None:
        assert sources(f"SOURCE: {DATASHEET}, products/other.md") == (DATASHEET, "products/other.md")

    def test_none_is_a_datum_and_not_a_source(self) -> None:
        assert sources("it is not in the catalog\nSOURCE: none") == ()
        assert sources("SOURCE: None") == ()

    def test_without_source_line_there_are_no_sources(self) -> None:
        assert sources("an opinion without a citation") == ()


class TestAdvisor:
    async def test_a_grounded_query_brings_the_source_and_moves_the_sale(self, small_catalog: Catalog) -> None:
        """The searcher queries and cites, the writer answers with the datasheet in its request, and the
        sale closes `pest` (by the customer's word), `product` (it queried) and `recipe`
        (the source of the report). What comes next to ask for is the quantity."""
        a, model = advisor(small_catalog, SEARCH, REPORT, WRITE)

        r = await a.ask("thrips on tomato")

        assert r.text == WRITE_PROSE, "without the SOURCE line, which goes in `sources`"
        assert r.sources == (DATASHEET,)
        assert r.grounded is True and r.nothing_to_search is False
        assert r.halt is False and r.cut_off is False and r.fails == ()
        assert r.seconds >= 0
        assert len(model.conversations) == 3, "two steps of the searcher and one of the writer"
        assert r.turns == 7, "the searcher (contract, the planner voice, code, REPL output, prose) plus the writer (request, prose)"
        v = summary(r.sale)
        assert v.closed == ("pest", "product", "recipe")
        assert v.ask is not None and v.ask.id == "quantity"
        assert v.state == "sale 3/8: next `quantity`"
        assert r.judgment is not None and r.judgment["error"] == ""
        assert r.judgment["p"]["has_search_terms"] >= 0.8 and r.judgment["p"]["said_quantity"] < 0.2
        assert "thrips on tomato" in r.judgment["state"]["said_raw"], "the state the model compacted travels to the host"
        rules = {e["id"]: e for e in r.rules}
        assert len(r.rules) == len(governance.rules()) > 0, "one entry per rule of the table, fired or not"
        assert rules["sale/has-search-terms_tag"]["fired"] and not rules["sale/wants-to-buy_tag"]["fired"]
        assert rules["sale/opens-a-datasheet_tag"] == {**rules["sale/opens-a-datasheet_tag"], "p": 1.0, "fired": True}
        assert rules["escalation.outbound/did-not-give-what-was-asked_tag"]["p"] is not None, "the p of the answer, which the judgment does not bring"
        cases = [e for i, e in rules.items() if i.startswith("case/")]
        assert all(e["p"] is not None for e in cases) and sum(e["fired"] for e in cases) <= 1

    async def test_the_writer_reads_the_whole_datasheet_in_its_request(self, small_catalog: Catalog) -> None:
        a, model = advisor(small_catalog, SEARCH, REPORT, WRITE)

        await a.ask("thrips on tomato")

        writer = model.conversations[2]
        assert writer[0] == Message(Role.SYSTEM, WRITER_PREAMBLE)
        assert writer[1].text == "thrips on tomato"
        order = writer[2].text
        assert order.startswith(WRITER), "without voice.md, the measured contract"
        assert "[report from searcher]" in order and DATASHEET in order
        assert "# Agronomy" in order, "the datasheet goes whole, not summarised"
        assert ASKS["quantity"] in order, "the sale line asks for the quantity"

    async def test_the_catalog_voice_opens_the_writer_request(self, bundle: Path) -> None:
        (bundle / "voice.md").write_text("You are Ana, of Insumos del Sur. You speak informally.\n")
        cat = load(bundle)
        a, model = advisor(cat, SEARCH, REPORT, WRITE)

        await a.ask("thrips on tomato")

        order = model.conversations[2][2].text
        assert order.startswith("You are Ana, of Insumos del Sur. You speak informally.\n\nAbove is what the customer asked")
        assert "If there is a product, state the dose" in order
        searcher = model.conversations[0]
        assert not any("Ana" in m.text for m in searcher), "the voice belongs to the writer, not the searcher"

    async def test_the_turn_with_nothing_to_search_asks_and_is_not_an_opinion(self, small_catalog: Catalog) -> None:
        """With no pest or product the searcher runs anyway, queries and closes with `SOURCE: none`;
        the writer asks, and the answer goes out with `nothing_to_search` true."""
        a, model = advisor(
            small_catalog,
            block("print(grep(catalog, 'problem'))"),
            "They named no pest or product: there is nothing to search for.\nSOURCE: none",
            "What pest do you see on the tomato?",
        )

        r = await a.ask("I have a problem on the tomato")

        assert r.text == "What pest do you see on the tomato?"
        assert r.nothing_to_search is True
        assert r.sources == () and r.fails == ()
        assert len(model.conversations) == 3
        v = summary(r.sale)
        assert v.ask is not None and v.ask.id == "pest"
        assert "pest" not in v.closed
        assert v.closed == ()

    async def test_the_sale_comes_in_with_the_request_and_goes_out_accumulated(self, small_catalog: Catalog) -> None:
        """TurnIn 2 with what came out of turn 1: the seed is not sown twice and what is closed stays closed."""
        first, _ = advisor(small_catalog, "What pest do you see on the tomato?")
        r1 = await first.ask("I have a problem on the tomato")
        assert r1.sale[: len(SESSION)] == SESSION

        second, _ = advisor(small_catalog, SEARCH, REPORT, WRITE)
        history = (("I have a problem on the tomato", r1.text),)
        r2 = await second.ask("thrips", history, sale=r1.sale)

        assert r2.sale[: len(r1.sale)] == r1.sale, "what came in goes out up front, whole"
        assert len(r2.sale) > len(r1.sale)
        assert sum(op.verb == "add_step" and op.id == "pest" for op in r2.sale) == 1, "the seed goes once"
        v = summary(r2.sale)
        assert "pest" in v.closed and v.ask is not None and v.ask.id == "quantity"

    async def test_without_a_sale_sent_the_sale_is_rebuilt_from_the_history(self, small_catalog: Catalog) -> None:
        """A customer that does not send `sale` back loses only what the advisor closes: the gates
        over the customer's words read the whole history."""
        a, _ = advisor(small_catalog, SEARCH, REPORT, WRITE)
        history = (("I have a problem on the tomato", "What pest do you see?"), ("thrips", "Hyphavane. How many manzanas?"))

        r = await a.ask("three liters", history)

        v = summary(r.sale)
        assert "pest" in v.closed and "quantity" in v.closed
        assert v.ask is not None and v.ask.id == "decision"

    async def test_the_advisor_proposes_sending_the_datasheet_and_does_not_send_it_twice(self, small_catalog: Catalog) -> None:
        """The customer asks for it, the judge reads that, the turn proposes it with the path the answer cited,
        and the `done` the customer sends back is what keeps the next turn from proposing it again."""
        a, model = advisor(small_catalog, SEARCH, REPORT, WRITE)

        r = await a.ask("send me the datasheet, it is for thrips on tomato")

        assert r.effects == (
            EffectOp("propose", "send_datasheet", "document"),
            EffectOp("resolve", "send_datasheet", args=(("path", DATASHEET),)),
        )
        e = effects_summary(r.effects)
        assert e.pending == (Pending("send_datasheet", "document", (("path", DATASHEET),), True),)
        assert EFFECT_LINES["send_datasheet"] in model.conversations[2][2].text, "the writer knew before writing"

        second, other = advisor(small_catalog, SEARCH, REPORT, WRITE)
        history = (("send me the datasheet, it is for thrips on tomato", r.text),)
        sent = (*r.effects, EffectOp("done", "send_datasheet", note="wamid.HBg"))

        r2 = await second.ask("and for pepper?", history, sale=r.sale, effects=sent)

        assert r2.effects == sent, "the turn added no moves: the effect was already closed"
        assert effects_summary(r2.effects).pending == ()
        assert EFFECT_LINES["send_datasheet"] not in other.conversations[2][2].text

    async def test_without_the_effects_back_the_advisor_proposes_them_again(self, small_catalog: Catalog) -> None:
        """The channel is the only thing that remembers the datasheet went out: the judgment is over the whole conversation."""
        a, _ = advisor(small_catalog, SEARCH, REPORT, WRITE)
        history = (("send me the datasheet, it is for thrips on tomato", "Hyphavane. How many manzanas?"),)

        r = await a.ask("and for pepper?", history)

        assert effects_summary(r.effects).pending[0].id == "send_datasheet"

    async def test_without_a_datasheet_to_cite_the_proposed_one_is_not_executable(self, small_catalog: Catalog) -> None:
        """`resolve` has nothing to put in: what the customer sends back is a `reject`, not a `done`."""
        a, _ = advisor(
            small_catalog,
            block("print(grep(catalog, 'leafcutter ant'))"),
            "The catalog does not cover leafcutter ant.\nSOURCE: none",
            "I have nothing for leafcutter ant.\nSOURCE: none",
        )

        r = await a.ask("send me the datasheet of the leafcutter ant one")

        assert r.effects == (EffectOp("propose", "send_datasheet", "document"),)
        assert effects_summary(r.effects).pending == (Pending("send_datasheet", "document", (), False),)

    async def test_the_turn_that_does_not_resolve_goes_out_with_the_escalation_and_does_not_repeat_it(self, small_catalog: Catalog) -> None:
        """The writer says it is not in the datasheet: the turn proposes the `handoff` with its reason, and
        with the customer's `done` back the conversation already has an owner and no other case opens."""
        unknown = "That figure is not in the datasheet of Hyphavane.\nSOURCE: none"
        a, _ = advisor(small_catalog, SEARCH, REPORT, unknown)

        r = await a.ask("how many days of pre-harvest interval does Hyphavane have on tomato?")

        [case] = [p for p in effects_summary(r.effects).pending if p.id == HANDOFF]
        assert case.kind == HANDOFF and case.executable
        assert dict(case.args)["origin"] == "requested_by_agent"
        assert dict(case.args)["reason"] in HANDOFF_REASONS
        assert "notice" not in dict(case.args), "what the customer reads about the escalation is said by the writer"

        second, _ = advisor(small_catalog, SEARCH, REPORT, unknown)
        opened = (*r.effects, EffectOp("done", HANDOFF, note="case 41"))

        r2 = await second.ask("and on pepper?", (("pre-harvest interval?", r.text),), sale=r.sale, effects=opened)

        assert HANDOFF not in {p.id for p in effects_summary(r2.effects).pending}

    async def test_answering_without_querying_with_something_to_search_goes_out_as_opinion(self, small_catalog: Catalog) -> None:
        """The searcher answers from memory: `grounded` warns and insists inside the step, the planner
        insists one more round from outside, and the turn goes out without backing and with its failures signed."""
        a, _ = advisor(
            small_catalog,
            "use 2 l/ha of anything",
            "I insist, 2 l/ha",
            "still no run_query, 2 l/ha",
            "Use 2 l/ha.\nSOURCE: none",
        )

        r = await a.ask("thrips on tomato")

        assert r.grounded is False and r.nothing_to_search is False
        assert r.text == "Use 2 l/ha." and r.sources == ()
        assert any(f.endswith("answered without having consulted the context") for f in r.fails)
        assert any(f.startswith("searcher/") for f in r.fails), "the failure comes signed by the searcher"
        assert "searcher/loop: step cap: 2" in r.fails, "the searcher checklist stayed open"
        assert r.cut_off is False, "the step cap is not the time cap: the turn finished whole"

    async def test_without_answer_there_are_no_sources_or_backing(self, small_catalog: Catalog) -> None:
        """The writer has no REPL: a code block of hers is not an answer, and it is not run."""
        a, model = advisor(small_catalog, SEARCH, REPORT, block("print(1)"))

        r = await a.ask("thrips on tomato")

        assert r.text == "" and r.sources == ()
        assert len(model.conversations) == 3, "searcher twice, writer once"

    async def test_what_the_model_mutates_in_the_repl_does_not_change_the_catalog_for_the_next(
        self, small_catalog: Catalog
    ) -> None:
        a, _ = advisor(small_catalog, block("products.clear(); print(grep(catalog, 'thrips'))"), REPORT, WRITE)
        await a.ask("thrips on tomato")

        following = Scripted(block("print(len(products))"), REPORT, WRITE)
        b = Advisor(small_catalog, following, contained=False, question_judge=question_judge_with())
        await b.ask("thrips on tomato")

        output = following.conversations[1][-1].text
        assert "2" in output and "0\n" not in output, "the index is built per query, from disk"

    async def test_the_cap_cuts_the_turn_and_releases_the_slot(self, small_catalog: Catalog) -> None:
        """A hung provider returns no Log: the loop `deadline` cancels the step and the query comes back truncated, it does not raise."""
        model = Hung()
        a = Advisor(small_catalog, model, slots=1, contained=False, question_judge=question_judge_with())

        r = await a.ask("thrips on tomato", timeout=0.1)

        assert model.started.is_set()
        assert r.cut_off is True and r.text == "" and r.grounded is False
        assert any(f.endswith("time cap: 0/0 s") for f in r.fails)
        assert 0.05 <= r.seconds < 2.0
        assert a.free == 1

    async def test_the_cap_kills_the_child_with_the_exec_half_done(self, small_catalog: Catalog) -> None:
        """With `contained`, a block that does not finish is cut with the turn and no process stays alive."""
        model = Scripted(block("while True: pass"), "Without a report I cannot tell you.\nSOURCE: none")
        a = Advisor(small_catalog, model, slots=1, contained=True, question_judge=question_judge_with())

        r = await a.ask("thrips on tomato", timeout=0.6)

        assert r.cut_off is True
        assert any(f.startswith("searcher/loop: time cap") for f in r.fails), "the cut was the searcher's"
        assert a.free == 1
        assert multiprocessing.active_children() == []

    async def test_the_slots_are_the_queries_in_flight(self, small_catalog: Catalog) -> None:
        model = Hung()
        a = Advisor(small_catalog, model, slots=2, contained=False, question_judge=question_judge_with())
        assert a.free == 2

        task = asyncio.create_task(a.ask("thrips", timeout=0.5))
        await model.started.wait()
        assert a.free == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert a.free == 2

    async def test_aclose_closes_the_model(self, small_catalog: Catalog) -> None:
        model = Scripted()
        await Advisor(small_catalog, model, question_judge=question_judge_with()).aclose()

        assert model.closed

    async def test_without_judge_the_sale_does_not_close_and_the_searcher_runs(self, small_catalog: Catalog) -> None:
        """TypeSafe down: `close_steps` notes it and closes nothing, not even the facts of the turn (the judge is a
        single one and it blew up); the searcher searches anyway, and the turn is served. The sale resumes when it returns."""
        model = Scripted(SEARCH, REPORT, WRITE)
        a = Advisor(small_catalog, model, contained=False, question_judge=question_judge_with(down=True))

        r = await a.ask("thrips on tomato")

        assert r.text == WRITE_PROSE and r.grounded is True
        assert r.judgment is not None and r.judgment["error"].startswith("reading:") and r.judgment["p"] == {}
        assert [f for f in r.fails if f.startswith("plan: the judge blew up: JudgeError")]
        v = summary(r.sale)
        assert v.closed == () and v.ask is not None and v.ask.id == "pest"

    async def test_the_moves_are_planops(self, small_catalog: Catalog) -> None:
        a, _ = advisor(small_catalog, "What pest do you see on the tomato?")

        r = await a.ask("I have a problem on the tomato")

        assert all(isinstance(op, PlanOp) for op in r.sale)


OFFERS = (("hi", "Shall I get two liters of Reapvane ready for you?"),)
GREETS = (("hi", "Hi! How can I help you?"),)


class TestOneJudgmentPerQuery:
    async def test_two_conversations_with_the_same_customer_lines_do_not_share_the_cart(self, small_catalog: Catalog) -> None:
        """"hi" and "yes" in both: in one the advisor offered two liters, in the other not. With one judge per process,
        the second received the cart of the first (the memory is indexed by the customer's lines)."""
        a, _ = advisor(small_catalog, SEARCH, REPORT, WRITE, SEARCH, REPORT, WRITE)

        offered = await a.ask("yes", OFFERS)
        greeted = await a.ask("yes", GREETS)

        assert offered.judgment is not None and offered.judgment["order"]["items"]
        assert greeted.judgment is not None and greeted.judgment["order"]["items"] == []

    async def test_each_query_judge_shares_the_client_and_the_model(self, small_catalog: Catalog) -> None:
        a, _ = advisor(small_catalog)
        root = a._gates
        child = root.fresh()

        assert child is not root and child._client is root._client and child._model is root._model
        assert child.last("yes", OFFERS) is None
