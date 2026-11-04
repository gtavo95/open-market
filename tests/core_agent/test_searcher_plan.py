"""The searcher's checklist: `planned` with voice around its `drive`, over the repo's catalog and with no network."""

from __future__ import annotations

import asyncio
import time

from core_agent.roles.searcher import (
    SEARCHER,
    SEARCH_JUDGE,
    SEARCH_PLAN,
    SEARCH_ROUNDS,
    SEARCH_STEPS,
    search_catalog,
    cited,
    search_voice,
)
from core_agent.world.catalog import corpus
from catalejo.core import ZERO, Conversation, Log, Message, PlanOp, Role, project
from catalejo.llm import Reply, ScriptedModel
from catalejo.rlm import Dossier, citations


class Script(ScriptedModel):
    """A `ScriptedModel` that is also a `Provider`: it has a name and can be closed."""

    model = "script"

    async def aclose(self) -> None:
        pass


def block(code: str) -> str:
    return f"```python\n{code}\n```"


QUESTION = Log(said=(Message(Role.USER, "thrips on tomato"),))
QUERY = block("print(grep(catalog, 'thrips'))")
REPORT = "Trevalis 45 EW covers thrips and the tomato is certified."
CLOSED = f"{REPORT}\nSOURCE: products/trevalis-45-ew.md"


def said(text: str, role: Role = Role.ASSISTANT) -> Message:
    return Message(role, text)


def voices(model: Script, i: int) -> list[str]:
    """The user turns that start with `[plan]` in conversation `i` the model saw."""
    return [m.text for m in model.conversations[i] if m.role is Role.USER and m.text.startswith("[plan]")]


class TestTheChecklist:
    async def test_each_gate_has_someone_to_answer_it(self) -> None:
        names = frozenset(op.done_when for op in SEARCH_PLAN if op.done_when)

        assert (await SEARCH_JUDGE(ZERO, names)).keys() == names

    def test_cited_sources_reads_the_last_prose_like_report(self) -> None:
        """The last prose rules, and `none` is a citation; a block after it does not cover it."""
        assert cited(Log(said=(said("nothing\nSOURCE: none"),)))
        assert cited(Log(said=(said(CLOSED), said(QUERY))))
        assert not cited(Log(said=(said(REPORT),)))
        assert not cited(Log(said=(said(CLOSED), said(REPORT))))
        assert not cited(ZERO)

    def test_a_source_inside_a_print_is_not_a_close(self) -> None:
        """The `print` tic: at the step cap the last said is code with `SOURCE:` inside, and the leaf stays open."""
        tic = block(f'print("""{CLOSED}""")')

        assert not cited(Log(said=(said(QUERY), said(tic))))
        assert citations(tic), "the parser alone would see it; `cited` checks that it is prose"

    def test_the_voice_says_what_is_missing_in_the_words_of_the_contract(self) -> None:
        open_ = search_voice(project(SEARCH_PLAN))
        uncited = search_voice(project((*SEARCH_PLAN, PlanOp("mark", "run_query", status="done"))))

        assert "query the catalog" in open_ and "SOURCE" in open_
        assert "query the catalog" not in uncited and "SOURCE: none" in uncited
        assert "repeat it" in uncited


class TestThePlannedSearcher:
    async def test_one_round_when_it_queries_and_cites(self) -> None:
        dossier = Dossier()
        model = Script(QUERY, CLOSED)

        out = await search_catalog(corpus(), model, dossier=dossier)(QUESTION)

        (report,) = out.reports
        assert report.text == CLOSED and report.sources == ("products/trevalis-45-ew.md",)
        assert out.fails == () and out.steps == ()
        assert len(model.conversations) == 2

    async def test_the_model_sees_the_checklist_before_searching(self) -> None:
        model = Script(QUERY, CLOSED)

        await search_catalog(corpus(), model, dossier=Dossier())(QUESTION)

        first = model.conversations[0]
        assert first[-1].role is Role.USER and first[-1].text.startswith("[plan]")
        assert first[-2].text == SEARCHER

    async def test_without_a_source_there_is_another_round_and_the_report_is_the_second(self) -> None:
        """The round that restores the `SOURCE:` brings the whole report, and `report` takes that one."""
        dossier = Dossier()
        model = Script(QUERY, REPORT, CLOSED)

        out = await search_catalog(corpus(), model, dossier=dossier)(QUESTION)

        (report,) = out.reports
        assert report.text == CLOSED and report.sources == ("products/trevalis-45-ew.md",)
        assert out.fails == ()
        assert len(model.conversations) == 3
        (voice,) = [m.text for m in model.conversations[2][-1:]]
        assert voice.startswith("[plan]") and "SOURCE" in voice and "query the catalog" not in voice

    async def test_running_out_of_rounds_signs_the_cap_and_the_report_is_the_last_prose(self) -> None:
        """The `planned` cap travels signed; the report comes out clean because the searcher closed in prose, it was not cut off."""
        dossier = Dossier()
        model = Script(QUERY, REPORT, "still not citing")

        out = await search_catalog(corpus(), model, dossier=dossier)(QUESTION)

        (report,) = out.reports
        assert [(f.who, f.reason) for f in out.fails] == [("searcher/loop", f"step cap: {SEARCH_ROUNDS}")]
        assert report.text == "still not citing"
        assert report.sources == (), "a grep does not open the datasheet: with no citation there is no step that rescues it"
        assert len(model.conversations) == 3

    async def test_at_the_drive_cap_the_second_round_brings_the_report(self) -> None:
        """Eight blocks and none of them prose: the voice asks for the report, and the next round brings it with the cap signed."""
        dossier = Dossier()
        model = Script(*([QUERY] * SEARCH_STEPS), CLOSED)

        out = await search_catalog(corpus(), model, dossier=dossier)(QUESTION)

        (report,) = out.reports
        assert report.text == CLOSED and report.sources == ("products/trevalis-45-ew.md",)
        assert [(f.who, f.reason) for f in out.fails] == [("searcher/loop", f"step cap: {SEARCH_STEPS}")]
        assert len(model.conversations) == SEARCH_STEPS + 1
        (t,) = dossier.drain()
        voices = [m.text for m in t.said if m.text.startswith("[plan]")]
        assert len(voices) == 2 and "query the catalog" not in voices[1]

    async def test_the_deadline_covers_both_rounds(self) -> None:
        """A slow model runs out the cap in round 1; round 2 does not start it again."""

        class Slow(Script):
            async def complete(self, conv: Conversation) -> Reply:
                await asyncio.sleep(0.25)
                return await super().complete(conv)

        model = Slow(*([QUERY] * 8), CLOSED)
        cell = search_catalog(corpus(), model, dossier=Dossier(), deadline=0.6)

        started = time.monotonic()
        out = await cell(QUESTION)
        elapsed = time.monotonic() - started

        assert elapsed < 1.0, "two rounds are not two caps"
        reasons = sorted(f.reason for f in out.fails if f.who == "searcher/loop")
        assert reasons == [f"step cap: {SEARCH_ROUNDS}", "time cap: 0/0 s", "time cap: 1/1 s"], (
            "one time cap per round, the second with no time left, and the rounds cap of planned"
        )
        assert len(model.conversations) <= 3

    async def test_the_dossier_transcript_carries_the_voices(self) -> None:
        dossier = Dossier()
        model = Script(QUERY, REPORT, CLOSED)

        await search_catalog(corpus(), model, dossier=dossier)(QUESTION)

        (t,) = dossier.drain()
        assert sum(m.text.startswith("[plan]") for m in t.said if m.role is Role.USER) == 2
