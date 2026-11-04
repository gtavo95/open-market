"""The trace looks and changes nothing: the same Log and the same Output, with or without someone watching."""

from __future__ import annotations

import asyncio

from catalejo.core import Fail, Log, Message, Role, then
from catalejo.rlm import FakeEnvironment
from core_agent.world import trace


async def speak(seen: Log) -> Log:
    return Log(said=(Message(Role.ASSISTANT, "hi"),))


async def stumble(seen: Log) -> Log:
    return Log(fails=(Fail("searcher/loop", "step cap: 2"),))


def watch(job) -> tuple[object, list[dict]]:
    nodes: list[dict] = []

    async def run() -> object:
        with trace.watching(nodes.append):
            return await job()

    return asyncio.run(run()), nodes


def test_the_log_goes_through_as_it_came_out() -> None:
    cell = then(trace.observed("writer", "Writing", speak))

    alone = asyncio.run(cell(Log()))
    watched, nodes = watch(lambda: cell(Log()))

    assert watched == alone
    assert [n["status"] for n in nodes] == ["running", "done"]


def test_nobody_watching_emits_nothing_and_detail_does_not_run() -> None:
    def detail(seen: Log, out: Log, step: trace.Span) -> None:
        raise AssertionError("nobody is watching")

    out = asyncio.run(trace.observed("writer", "Writing", speak, detail)(Log()))

    assert out.said[0].text == "hi"


def test_a_step_opened_inside_hangs_from_the_one_that_opened_it() -> None:
    async def inner(seen: Log) -> Log:
        trace.note("plan", "close pest")
        return Log()

    _, nodes = watch(lambda: trace.observed("judge", "Reading", inner)(Log()))

    outer = next(n for n in nodes if n["kind"] == "judge")
    child = next(n for n in nodes if n["kind"] == "plan")
    assert child["parent"] == outer["id"]


def test_a_fail_of_the_cell_is_a_failed_step() -> None:
    _, nodes = watch(lambda: trace.observed("searcher", "Searching", stumble)(Log()))

    failed = [n for n in nodes if n["kind"] == "fail" and n["status"] == "error"]
    assert failed[0]["title"] == "searcher/loop"
    assert failed[0]["text"] == "step cap: 2"


def test_a_cancelled_cell_closes_its_step_as_error_and_cancels() -> None:
    async def cut(seen: Log) -> Log:
        raise asyncio.CancelledError

    nodes: list[dict] = []

    async def run() -> None:
        with trace.watching(nodes.append):
            await trace.observed("writer", "Writing", cut)(Log())

    try:
        asyncio.run(run())
    except asyncio.CancelledError:
        pass
    assert nodes[-1]["status"] == "error"


def test_each_repl_run_shows_its_code_and_what_it_printed() -> None:
    env = trace.Watched(FakeEnvironment())

    out, nodes = watch(lambda: env.run("\nprint(products)\nmore()"))

    assert out.stdout.startswith("echo:")
    assert nodes[-1]["title"] == "print(products)"
    assert nodes[-1]["code"].strip().startswith("print(products)")
    assert nodes[-1]["output"] == out.stdout


def test_siblings_in_tasks_do_not_hang_from_each_other() -> None:
    async def both() -> None:
        async def one(title: str) -> None:
            with trace.span("read", title):
                await asyncio.sleep(0)

        await asyncio.gather(one("photo"), one("voice"))

    _, nodes = watch(both)

    assert {n["parent"] for n in nodes} == {None}


def test_a_step_it_cannot_fill_never_fails_the_turn() -> None:
    def broken(seen: Log, out: Log, step: trace.Span) -> None:
        raise ValueError("not serializable")

    out, nodes = watch(lambda: trace.observed("writer", "Writing", speak, broken)(Log()))

    assert out.said[0].text == "hi"
    assert nodes[-1]["status"] == "done"
