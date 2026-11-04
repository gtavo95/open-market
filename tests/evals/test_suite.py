"""The arithmetic of the evals report, measured without spending a cent.

It exists because a suite whose math is untested is the failure mode the
skill already names: in `exp` a `price_min=0` from the join fabricated five false failures
on answers that gave the correct price. A broken evaluator does not show,
because what it reports looks like a result.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from evals import logbook, criterion, suite
from core_agent.world import catalog
from core_agent.world.order import Item
from core_agent.world.typesafe import Response
from catalejo.core import EffectOp, Entry, Fail, Log, Message, Node, Report, Role
from catalejo.rlm import Transcript
from evals.ab import Cut, sample
from evals.suite import ASK_BACK, Case, Run, flows, is_hit, percentile, repeats, summarize, tsv_of

CASE = Case("x", "?", ("products/a.md",), "# Datasheet", "cites a")


def run(ok: bool, *, lost: bool = False, spent: int = 100, secs: float = 1.0, ghosts: tuple[str, ...] = (), case: Case = CASE, attempt: int = 0) -> Run:
    fails = (Fail("searcher/model", "empty turn"),) if lost else ()
    out = Log(said=(Message(Role.ASSISTANT, "hello"),), fails=fails, spent=spent)
    return Run(case, attempt, out, "hello", secs, ok, ghosts, (Transcript("searcher", (Message(Role.USER, "a"), Message(Role.ASSISTANT, "b"))),))


class TestSummarize:
    def test_hitting_all_is_stable(self) -> None:
        r = summarize([run(True), run(True), run(True)], 3)

        assert r.stable == ("x",) and not r.flippers and not r.fallen

    def test_hitting_some_is_flipper(self) -> None:
        r = summarize([run(True), run(False), run(True)], 3)

        assert r.flippers == ("x",) and not r.stable

    def test_always_failing_is_fallen(self) -> None:
        r = summarize([run(False), run(False)], 2)

        assert r.fallen == ("x",) and not r.flippers

    def test_an_empty_turn_leaves_the_denominator(self) -> None:
        """Losing the sample to the API is not failing the exam: the case stays stable and the mean spend goes over the live ones."""
        r = summarize([run(True, spent=100), run(False, lost=True, spent=500), run(True, spent=100)], 3)

        assert r.stable == ("x",)
        assert (r.hits, r.alive_ones, r.lost_count) == (2, 2, 1)
        assert (r.spent, r.spent_all) == (100, 700)

    def test_losing_them_all_is_mute_and_not_fallen(self) -> None:
        r = summarize([run(False, lost=True), run(False, lost=True)], 2)

        assert r.mute_ones == ("x",) and not r.fallen

    def test_running_out_of_steps_does_count(self) -> None:
        out = Log(said=(Message(Role.ASSISTANT, "hello"),), fails=(Fail("loop", "step cap: 8"),))
        c = Run(CASE, 0, out, "hello", 1.0, False)

        assert not c.lost
        assert summarize([c], 1).fallen == ("x",)

    def test_the_messages_count_the_searcher(self) -> None:
        r = summarize([run(True)], 1)

        assert r.turns == 3.0

    def test_phantom_paths_gather_across_rounds(self) -> None:
        r = summarize([run(True, ghosts=("products/no.md",)), run(True, ghosts=("products/other.md",))], 2)

        assert r.ghosts == {"x": ("products/no.md", "products/other.md")}

    def test_time_goes_over_the_live_ones_and_the_max_over_all(self) -> None:
        r = summarize([run(True, secs=1.0), run(True, secs=3.0), run(False, lost=True, secs=120.0, attempt=2)], 3)

        assert r.secs == 2.0
        assert r.slowest == ("x #3", 120.0)

    def test_no_runs_does_not_divide_by_zero(self) -> None:
        r = summarize([], 1)

        assert (r.cases, r.spent, r.turns, r.secs) == (0, 0, 0.0, 0.0)

    def test_p95_is_by_nearest_rank(self) -> None:
        assert percentile([1.0, 2.0, 3.0, 4.0, 100.0], 95) == 100.0
        assert percentile([], 95) == 0.0


class TestIsHit:
    def test_asks_for_the_expected_page(self) -> None:
        assert is_hit(CASE, "... SOURCE: products/a.md")
        assert not is_hit(CASE, "... SOURCE: products/b.md")

    def test_without_pages_the_hit_is_saying_there_is_none(self) -> None:
        case = Case("x", "?", (), "·", "")

        assert is_hit(case, "we do not carry it.\nSOURCE: none")
        assert not is_hit(case, "SOURCE: products/a.md")

    def test_with_question_the_hit_is_asking(self) -> None:
        case = Case("x", "?", (ASK_BACK,), "·", "")

        assert is_hit(case, "Which crop?")
        assert not is_hit(case, "Use Larvane.")


class TestFlows:
    def test_one_row_per_turn_with_the_id_flow_colon_n(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "evals").mkdir()
        (tmp_path / "evals" / "f.tsv").write_text("# head\none\t1\tp1\tquestion\t·\tc\none\t2\tp2\tproducts/a.md\t# Datasheet\tc\n")
        monkeypatch.setattr(suite, "BUNDLE", tmp_path)

        [flow] = flows("f.tsv")

        assert flow.id == "one"
        assert [t.id for t in flow.turns] == ["one:1", "one:2"]
        assert flow.turns[0].pages == (ASK_BACK,)

    def test_a_skipped_turn_is_a_tsv_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "evals").mkdir()
        (tmp_path / "evals" / "f.tsv").write_text("one\t1\tp\tnone\t·\tc\none\t3\tp\tnone\t·\tc\n")
        monkeypatch.setattr(suite, "BUNDLE", tmp_path)

        with pytest.raises(SystemExit):
            flows("f.tsv")

    @pytest.mark.skipif(
        not (catalog.BUNDLE / "evals").is_dir(),
        reason="`okf/` does not bring evals/: run with DEMO_BUNDLE pointing at okf/",
    )
    def test_the_bundle_ones_load(self) -> None:
        assert [f.id for f in flows("flows.tsv")]
        assert [c.id for c in suite.cases("cases.tsv")]

    @pytest.mark.skipif(not (catalog.BUNDLE / "evals").is_dir(), reason="`okf/` does not bring evals/")
    def test_every_bundle_case_has_a_topic(self) -> None:
        every = suite.units()

        assert set(suite.topics(every)) == {u.id for u in every}


class TestFlags:
    def test_repeats_goes_with_equals(self) -> None:
        assert repeats([]) == 1
        assert repeats(["--repeats=3"]) == 3
        with pytest.raises(SystemExit):
            repeats(["--repeats=0"])

    def test_flows(self) -> None:
        assert tsv_of([]) == "cases.tsv"
        assert tsv_of(["--flows"]) == "flows.tsv"
        assert tsv_of(["--flows=complex"]) == "flows-complex.tsv"


class TestRetrievedAndMet:
    """The two grades that are not the citation: whether the searcher brought the page and whether the answer met the criterion."""

    def test_retrieved_looks_at_the_report_sources_and_not_the_answer(self) -> None:
        """B's answer that cited only Kelthar Total: the searcher had brought the page."""
        out = Log(reports=(Report("searcher", "…", ("products/b.md", "products/a.md")),))

        assert suite.retrieved(CASE, out) is True
        assert suite.retrieved(CASE, Log(reports=(Report("searcher", "…", ("products/b.md",)),))) is False

    def test_no_page_to_look_for_means_no_grade(self) -> None:
        assert suite.retrieved(Case("x", "?", (), "", ""), Log()) is None
        assert suite.retrieved(Case("x", "?", (ASK_BACK,), "", ""), Log()) is None

    def test_the_summary_counts_only_what_was_judged(self) -> None:
        runs = [replace(run(True), found=True, met=0.9), replace(run(True), found=False, met=0.1), run(True)]
        r = summarize(runs, 3)

        assert r.found == (1, 2) and r.met == (1, 2)


class TestConditions:
    """The criterion in atomic conditions: one question per condition, and it is met if all come out right."""

    def test_the_sign_says_whether_the_answer_does_it_or_not(self) -> None:
        conds = criterion.conditions("+ recommends Metavane | - asks for the area |")

        assert [(c.text, c.wanted) for c in conds] == [("recommends Metavane", True), ("asks for the area", False)]

    def test_no_sign_is_a_tsv_error(self) -> None:
        with pytest.raises(ValueError):
            criterion.conditions("recommends Metavane")

    def test_the_worst_condition_decides_and_says_which(self) -> None:
        """A `-` that came out yes is the one that fails, even if the `+` ones come out perfect."""

        class Fake:
            async def ask(self, state: object, questions: dict[str, object]) -> Response:
                return Response({"c0": {"noul": 0.97}, "c1": {"noul": 0.9}}, 100, "fake")

        v = asyncio.run(criterion.judge(Fake(), "", "+ recommends Metavane | - escalates", "?", "…"))  # type: ignore[arg-type]

        assert v.p == 0.1
        assert v.unmet == ("- escalates (0.10)",)

    def test_without_conditions_the_prose_criterion_goes(self) -> None:
        class Fake:
            async def ask(self, state: dict[str, object], questions: dict[str, object]) -> Response:
                assert "criterion" in state and criterion.MET in questions
                return Response({criterion.MET: {"noul": 0.8}}, 100, "fake")

        assert asyncio.run(criterion.judge(Fake(), "offers X", "", "?", "…")).p == 0.8  # type: ignore[arg-type]


class TestMemory:
    def test_the_column_is_the_host_json(self) -> None:
        column = '{"messages": [{"i": 0, "kind": "customer", "text": "2 gal"}], "tree": [{"l": 1, "i": 0, "text": "x"}]}'

        assert suite.memory_of(column) == (Entry(0, "customer", "2 gal"), Node(1, 0, "x"))
        assert suite.memory_of("·") == () and suite.memory_of("") == ()

    def test_malformed_is_an_error_that_says_what(self) -> None:
        with pytest.raises(ValueError, match="memory"):
            suite.memory_of('{"messages": [{"i": 0}]}')


class TestHistoryAndEscalates:
    """The two columns of the probe: the conversation already written ahead, and whether the turn has to escalate."""

    def test_the_history_is_customer_advisor_pairs(self) -> None:
        h = suite.history_of("I want Larvane >> Larvane goes at 1 L/ha || two liters >> that is Q500")

        assert h == (("I want Larvane", "Larvane goes at 1 L/ha"), ("two liters", "that is Q500"))
        assert suite.history_of("") == () and suite.history_of("·") == ()

    def test_a_turn_without_advisor_is_a_tsv_error(self) -> None:
        with pytest.raises(ValueError):
            suite.history_of("I want Larvane")

    def test_escalates_yes_no_or_nothing(self) -> None:
        assert (suite.escalates_of("yes"), suite.escalates_of("no")) == (True, False)
        assert suite.escalates_of("·") is None and suite.escalates_of("") is None
        with pytest.raises(ValueError):
            suite.escalates_of("maybe")

    def test_the_optional_columns_go_in_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "evals").mkdir()
        (tmp_path / "evals" / "a.tsv").write_text(
            "alone\t?\tnone\t·\tc\n"
            "full\t?\tnone\t·\tc\t+ says no\tI want X >> we have none\tyes\tsend_datasheet\n"
        )
        monkeypatch.setattr(suite, "BUNDLE", tmp_path)

        alone, full = suite.cases("a.tsv")

        assert (alone.conditions, alone.history, alone.escalates, alone.effects) == ("", (), None, ())
        assert (full.conditions, full.history, full.escalates) == ("+ says no", (("I want X", "we have none"),), True)
        assert [str(x) for x in full.effects] == ["send_datasheet"]

    def test_escalated_is_read_in_the_effects_and_not_the_text(self) -> None:
        """'We do not sell chlorpyrifos.' does not say it escalates, and the guardian opens the case all the same."""
        handoff = EffectOp("propose", "handoff", "handoff")
        case = replace(CASE, escalates=True)
        yes = Run(case, 0, Log(effects=(handoff,)), "We do not sell chlorpyrifos.", 1.0, True)
        no = Run(case, 0, Log(), "We do not sell chlorpyrifos.", 1.0, True)

        assert (yes.escalated, yes.escalation_ok) == (True, True)
        assert (no.escalated, no.escalation_ok) == (False, False)
        assert run(True).escalation_ok is None

    def test_effects_that_come_out_that_do_not_and_the_reason(self) -> None:
        assert [str(x) for x in suite.effects_expected("send_datasheet -send_payment_link handoff:card_payment")] == [
            "send_datasheet", "-send_payment_link", "handoff:card_payment",
        ]
        assert suite.effects_expected("·") == () and suite.effects_expected("") == ()
        for bad in ("send_pdf", "send_datasheet:quality_complaint", "handoff:does_not_exist"):
            with pytest.raises(ValueError):
                suite.effects_expected(bad)

    def test_effects_are_read_in_the_channel(self) -> None:
        """A turn that escalates for the wrong reason, or that sends the link out of turn, fails even if the text is fine."""
        case = replace(CASE, effects=suite.effects_expected("send_datasheet -send_payment_link handoff:card_payment"))
        datasheet = EffectOp("propose", "send_datasheet", "document")
        handoff = EffectOp("propose", "handoff", "handoff", (("origin", "requested_by_customer"), ("reason", "card_payment")))
        other_reason = EffectOp("propose", "handoff", "handoff", (("reason", "quality_complaint"),))
        link = EffectOp("propose", "send_payment_link", "payment_link")

        good = Run(case, 0, Log(effects=(datasheet, handoff)), "hello", 1.0, True)
        bad = Run(case, 0, Log(effects=(other_reason, link)), "hello", 1.0, True)

        assert (good.effects_ok, good.effect_misses) == (True, ())
        assert bad.effects_ok is False
        assert bad.effect_misses == (
            "did not propose send_datasheet",
            "proposed send_payment_link and should not have",
            "handoff with reason quality_complaint, and the row says card_payment",
        )
        assert run(True).effects_ok is None

    def test_handoff_in_the_row_covers_the_takeover(self) -> None:
        """`handoff` is the kind: the case that turns the advisor off comes out with another id (`takeover`) and the row does not change."""
        case = replace(CASE, effects=suite.effects_expected("handoff:quality_complaint"))
        takeover = EffectOp("propose", "takeover", "handoff", (("reason", "quality_complaint"),))

        assert Run(case, 0, Log(effects=(takeover,)), "hello", 1.0, True).effects_ok is True

    def test_order_lines_wildcards_and_empty(self) -> None:
        assert [str(x) for x in suite.order_expected("Reapvane:1 L:5 + Roycel:?:3 + NoviTrap:-:?")] == [
            "Reapvane:1 L:5", "Roycel:?:3", "NoviTrap:-:?",
        ]
        assert suite.order_expected("empty") == () and suite.order_expected("·") is None
        for bad in ("Reapvane", "Reapvane:1 L:five", ":1 L:2"):
            with pytest.raises(ValueError):
                suite.order_expected(bad)

    def test_order_is_read_in_the_judge_cart(self) -> None:
        """What is missing and what is extra, against the cart set by the catalog. Without a cart, it fails: the judgment is part of what is measured."""
        case = replace(CASE, order=suite.order_expected("Reapvane:1 L:5 + Roycel:?:3"))
        reapvane = Item("Reapvane", "1 L", 5, product="Reapvane", presentation="1 L")
        roycel = Item("Roycel", "", 3, product="Roycel 25 EW")
        rootvane = Item("Rootvane", "", 2, product="Rootvane")

        good = Run(case, 0, Log(), "hello", 1.0, True, order=(roycel, reapvane))
        bad = Run(case, 0, Log(), "hello", 1.0, True, order=(replace(reapvane, quantity=10), roycel, rootvane))
        empty = Run(replace(CASE, order=()), 0, Log(), "hello", 1.0, True, order=())

        assert (good.order_ok, empty.order_ok) == (True, True)
        assert bad.order_misses == ("missing Reapvane:1 L:5", "extra Reapvane:1 L:10", "extra Rootvane:-:2")
        assert Run(case, 0, Log(), "hello", 1.0, True).order_misses == ("no judgment: no cart",)
        assert run(True).order_ok is None


class TestTopics:
    """A change is measured by the topics it touches: `--topic=` picks by the main one, and a case without a topic does not pass."""

    @pytest.fixture
    def bundle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        (tmp_path / "evals").mkdir()
        (tmp_path / "evals" / "cases.tsv").write_text("dose\t?\tnone\t·\tc\nshipping\t?\tnone\t·\tc\n")
        (tmp_path / "evals" / "questions.tsv").write_text("alias\t?\tnone\t·\tc\n")
        (tmp_path / "evals" / "flows.tsv").write_text("sale\t1\tp\tquestion\t·\tc\nsale\t2\tp\tnone\t·\tc\n")
        (tmp_path / "evals" / "flows-complex.tsv").write_text("")
        (tmp_path / "evals" / "flows-real.tsv").write_text("")
        (tmp_path / "evals" / "topics.tsv").write_text(
            "# id\ttopics\ndose\tcatalog/dose\nshipping\tcompany/shipping escalation\nalias\tcatalog/names\nsale\tconversation/sale catalog/dose\n"
        )
        monkeypatch.setattr(suite, "BUNDLE", tmp_path)
        return tmp_path

    def test_a_topic_brings_its_subtopics_and_not_lookalikes(self) -> None:
        assert suite.within("catalog/dose", "catalog") and suite.within("catalog/dose", "catalog/dose")
        assert not suite.within("catalog/dose", "catalog/do")

    def test_it_picks_by_the_main_topic(self, bundle: Path) -> None:
        """The sale flow also touches the dose, and it does not get in: running it is two turns for one that names it."""
        assert [u.id for u in suite.select(["--topic=catalog"]) or ()] == ["dose", "alias"]
        assert [u.id for u in suite.select(["--topic=escalation"]) or ()] == []
        assert [u.id for u in suite.select(["sale", "shipping"]) or ()] == ["shipping", "sale"]

    def test_with_nothing_nothing_runs(self, bundle: Path) -> None:
        assert suite.select([]) is None

    def test_without_cases_it_does_not_start_and_says_how_to_pass_them(self, bundle: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        """3.6-04: the eval requires the cases in the command. Without them it prints the tree and calls no model."""
        monkeypatch.setattr(suite, "provider", lambda: pytest.fail("started"))
        asyncio.run(suite.main([]))
        assert "pick a topic with --topic=<topic>, or cases by id" in capsys.readouterr().out

    def test_a_whole_flows_file_asks_for_all(self, bundle: Path) -> None:
        with pytest.raises(SystemExit, match="--flows <id>.*--all"):
            suite.select(["--flows"])
        assert [f.id for f in suite.select(["--flows", "--all"]) or ()] == ["sale"]
        assert [f.id for f in suite.select(["--flows", "sale"]) or ()] == ["sale"]

    def test_what_passes_the_ceiling_does_not_start(self, bundle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The estimate goes before creating the model: if it reached `provider`, the test would fail for another reason."""
        monkeypatch.setattr(suite, "PER_TURN", 0.2)
        monkeypatch.setattr(suite, "provider", lambda: pytest.fail("started"))
        with pytest.raises(SystemExit, match="is over USD 1.00"):
            asyncio.run(suite.main(["dose", "shipping", "--repeats=3"]))

    def test_the_tree_counts_turns_by_the_main_one(self, bundle: Path) -> None:
        every = suite.units()
        rows = {path: (n, turns, also) for path, n, turns, also in suite.tree(every, suite.topics(every))}

        assert rows["catalog"] == (2, 2, 1)
        assert rows["conversation/sale"] == (1, 2, 0)
        assert rows["escalation"] == (0, 0, 1)

    def test_a_case_without_a_topic_is_an_error(self, bundle: Path) -> None:
        (bundle / "evals" / "topics.tsv").write_text("dose\tcatalog/dose\n")

        with pytest.raises(SystemExit):
            suite.topics(suite.units())



class TestLogbook:
    LINE = "\t".join(["2026-09-24", "agro", "agro@abc", "catalejo@def", "okf@123", "·", "·", "gpt-6-luna", "3", "20000", "7.0", "3/3", "0", "0.011", "·"])

    def test_fill_sets_lever_arm_and_note(self) -> None:
        cells = logbook.fill(self.LINE, "judge", "new", "met 3/3").split("\t")
        assert (cells[5], cells[6], cells[14]) == ("judge", "new", "met 3/3")
        assert cells[:5] == self.LINE.split("\t")[:5]

    def test_a_note_with_tabs_or_newlines_does_not_split_the_row(self) -> None:
        cells = logbook.fill(self.LINE, "p", "a", "one\ttwo\nthree ").split("\t")
        assert len(cells) == 15 and cells[14] == "one two three"

    def test_empty_is_a_dot(self) -> None:
        assert logbook.fill(self.LINE, "p", "", "  ").split("\t")[6:7] == ["·"]

    def test_a_row_with_other_columns_is_not_written(self) -> None:
        with pytest.raises(ValueError):
            logbook.fill("a\tb", "p", "a", "n")

    def test_flags_are_not_cases(self) -> None:
        argv = ["rolls", "--repeats=3", "--lever=judge", "--note=with spaces"]
        assert logbook.without_flags(argv) == ["rolls", "--repeats=3"]
        assert logbook.flag(argv, "note") == "with spaces" and logbook.flag(argv, "arm") is None

    def test_append_adds_at_the_end_and_without_logbook_warns(self, tmp_path: Path) -> None:
        path = tmp_path / "logbook.tsv"
        assert not logbook.append(["x"], path)
        path.write_text("# header")
        assert logbook.append(["one", "two"], path)
        assert path.read_text() == "# header\none\ntwo\n"

    def test_the_logbook_is_looked_up_next_to_the_checkout_also_from_a_worktree(self, tmp_path: Path) -> None:
        repo = tmp_path / "agro"
        tree = repo / ".claude" / "worktrees" / "x"
        (repo / ".git" / "worktrees" / "x").mkdir(parents=True)
        tree.mkdir(parents=True)
        (tree / ".git").write_text(f"gitdir: {repo}/.git/worktrees/x\\n")

        assert logbook.checkout(tree) == repo.resolve()
        assert logbook.checkout(repo) == repo


class TestPrice:
    def test_luna_costs_what_gpt_6_luna_costs(self) -> None:
        """3.6-04: until Oct 14, 2026 the row said 0.20/0.02/1.20, the price of gpt-5.6-luna, and the spend came out inflated."""
        assert suite.PRICES["gpt-6-luna"][:3] == (0.10, 0.01, 0.50)

    def test_the_model_spend_comes_from_the_rate(self) -> None:
        class Usage:
            input, cached, output = 1_000_000, 400_000, 100_000

        class Model:
            model, usage = "gpt-6-luna", Usage()

        assert suite.model_usd(Model()) == pytest.approx(0.6 * 0.10 + 0.4 * 0.01 + 0.1 * 0.50)


class TestCeiling:
    """3.6-04, like 3.6-01 in agro: no run goes over USD 1. The first attempt that passes it cuts the others."""

    def test_the_cut_cancels_the_attempts_that_follow(self) -> None:
        cancelled: list[str] = []

        async def costly() -> list[Run]:
            await asyncio.sleep(0)
            raise Cut(1.2)

        async def slow() -> list[Run]:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append("slow")
                raise
            return []

        with pytest.raises(Cut) as e:
            asyncio.run(suite.capped([costly(), slow()]))
        assert e.value.spent == 1.2 and cancelled == ["slow"]

    def test_without_a_cut_it_returns_each_attempt_in_order(self) -> None:
        async def one(i: int) -> list[Run]:
            await asyncio.sleep(0.01 * (2 - i))
            return [run(True, attempt=i)]

        got = asyncio.run(suite.capped([one(0), one(1)]))
        assert [g[0].attempt for g in got] == [0, 1]


class TestSample:
    """3.6-04: n < 10 is smoke and does not work for F gate; with n ≥ 10 the summary brings n and the real USD."""

    def test_small_n_is_smoke(self) -> None:
        assert sample(1, 0.01).startswith("smoke") and "F gate" in sample(9, 0.3)

    def test_n_10_brings_n_and_usd(self) -> None:
        assert sample(10, 0.4321) == "gate: n=10, USD 0.4321 (F gate ... --n 10 --usd 0.4321)"
