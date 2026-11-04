import asyncio

from catalejo.core import Entry, Log, Message, Report, Role

from core_agent.prompts.memory import MEMORY_WHO
from core_agent.roles.searcher import with_memory

QUESTION = Message(Role.USER, "I want the same as last time")
MEMORY = Report(MEMORY_WHO, "2 containers of 1 L of Zelvora 45 SC, Jun 2", (), False)
SEEDED = Log(said=(QUESTION,), memory=(Entry(1, "customer", "2 of 1 L of Zelvora"),))


def memories(seconds: float = 0.0):
    async def cell(seen: Log) -> Log:
        await asyncio.sleep(seconds)
        return Log(reports=(MEMORY,))

    return cell


def searcher(seen_calls: list[tuple[float | None, Log]]):
    def build(left: float | None):
        async def cell(seen: Log) -> Log:
            seen_calls.append((left, seen))
            return Log(reports=(Report("searcher", "Zelvora 45 SC", ("products/zelvora-45-sc.md",), True),))

        return cell

    return build


class TestWithMemory:
    async def test_the_searcher_reads_the_memory_report_after_the_question(self) -> None:
        seen_calls: list[tuple[float | None, Log]] = []

        out = await with_memory(memories(), searcher(seen_calls), None)(SEEDED)

        said = seen_calls[0][1].said
        assert said[0] == QUESTION and said[-1].role is Role.USER and "Zelvora 45 SC" in said[-1].text
        assert out.said == () and [r.who for r in out.reports] == [MEMORY_WHO, "searcher"]

    async def test_the_searcher_has_what_memory_left_of_the_cap(self) -> None:
        seen_calls: list[tuple[float | None, Log]] = []

        await with_memory(memories(0.05), searcher(seen_calls), 10.0)(SEEDED)

        left = seen_calls[0][0]
        assert left is not None and 9.0 < left <= 9.95


class TestWithoutMemory:
    async def test_the_searcher_sees_the_same_with_the_whole_cap_and_memory_does_not_run(self) -> None:
        seen_calls: list[tuple[float | None, Log]] = []
        seen = Log(said=(QUESTION,))

        out = await with_memory(memories(), searcher(seen_calls), 10.0)(seen)

        assert seen_calls == [(10.0, seen)] and [r.who for r in out.reports] == ["searcher"]
