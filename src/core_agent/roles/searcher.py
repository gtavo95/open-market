"""The role that searches: its REPL, its checklist and its cell.

It reads the catalog by writing code and comes out through the boundary as a `Report` with its
prose and its sources. It does not talk to the customer and does not vote: what crosses is the
report, not the transcript.

What it costs: up to `SEARCH_STEPS` calls to the model per round and up to
`SEARCH_ROUNDS` rounds; none to the judge, because the two leaves of its checklist
are closed by facts of the Log (`SEARCH_JUDGE`).

What the model reads (the contract, `SCHEMA` and the checklist's voice) lives in
`prompts/searcher.py`, and changing it gets measured. Here stay the caps, the table and
its judge (`SEARCH_PLAN`, `SEARCH_JUDGE`, `search_voice`), and at the end the cell.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from catalejo.core import (
    Cell,
    Judge,
    Log,
    Message,
    Plan,
    PlanOp,
    Role,
    boundary,
    facts,
    merge,
    pending,
    then,
)
from catalejo.llm import Provider
from catalejo.rlm import (
    Container,
    Dossier,
    Handle,
    Workspace,
    citations,
    drive,
    extract_code,
    has_memory,
    paths,
    planned,
    planner,
    report,
)

from ..prompts.memory import MEMORY_FOR_SEARCH, MEMORY_WHO
from ..prompts.searcher import SCHEMA, VOICE, contract
from ..world.catalog import PRODUCT_NOTES, VOCABULARY_NOTES, targets, products, product_types
from ..world.fields import describe
from ..world.facts import LOG_FACTS

SEARCH_STEPS = 8

SEARCH_ROUNDS = 2
"""The searcher's rounds per turn, at most: the first and one more if its checklist stayed open (`SEARCH_PLAN`)."""

def indent(text: str) -> str:
    return "\n".join("  " + line for line in text.splitlines())


def repl_variables() -> str:
    """What the contract says about the REPL, taken from the same data `workshop` loads for it.

    The shape of each record is written by `describe` reading the records; the
    only thing written by hand is the notes in `world/catalog.py`. A new field in
    `record` shows up here without touching the prompt.
    """
    records = products()
    return "\n".join(
        (
            "- `targets`: the closed vocabulary of pests and diseases. A list of dicts:",
            indent(describe(targets(), VOCABULARY_NOTES)),
            "- `product_types`: the one of product types (sticker, water conditioner, rooter…),",
            "  with the same shape as `targets`.",
            f"- `products`: one entry per datasheet, already parsed ({len(records)} in total). Each one:",
            indent(describe(records, PRODUCT_NOTES)),
            "  Do not print the whole list or a complete entry: print the fields you need.",
            "- `notes`: an empty list for your findings.",
        )
    )


SEARCHER = contract(SEARCH_STEPS, repl_variables())
"""The contract with this role's cap: what `say` puts in front of the `drive`.

It is built at import, with the catalog of `BUNDLE`: the same one `workshop` reads
on each turn, and the same text on all turns, which is what lets
the prompt be cached.
"""


def say(text: str) -> Cell:
    """The cell that adds `text` as a user turn and nothing else: that is how each role says its contract."""
    message = Message(Role.USER, text)

    async def cell(seen: Log) -> Log:
        return Log(said=(message,))

    return cell


def workshop(text: str, *, contained: bool = False) -> Workspace | Container:
    """The searcher's REPL, freshly built: the catalog in `catalog` and the indexes parsed from disk.

    It is a function and not an object because it is built per turn (see `search_catalog`), and
    the indexes are reread each time on purpose: they are lists, and a
    `products.clear()` by the model on one turn cannot change the catalog
    for the next. `contained` runs it in a child process (`Container`): a
    `while True` by the model is killed at the time cap instead of leaving a
    live thread until the process dies. It is what a server wants; the CLI
    runs in-process.
    """
    extra: dict[str, Any] = {
        "targets": targets(),
        "product_types": product_types(),
        "products": products(),
        "notes": [],
    }
    if contained:
        return Container(text, var="catalog", extra=extra)
    return Workspace(text, var="catalog", extra=extra)


SEARCH_PLAN = (
    PlanOp(
        "add_step",
        "run_query",
        "query the catalog before giving an opinion",
        done_when="queried_the_catalog",
    ),
    PlanOp(
        "add_step",
        "cite",
        "close with one `SOURCE: <path>` line per file that answers, or `SOURCE: none`",
        done_when="cited_sources",
    ),
)
"""The searcher's checklist on a turn, in the `steps` channel: what its contract asks for and no cell of the step requires.

Two leaves, both closed by facts of the Log, with no network. `run_query` is the
same fact as `product` in the sale; inside the step `grounded` warns once
and then lets it pass, and from outside the planner insists one more round.
`cite` is what `report` rescues by tiers when it is missing (what was printed, what was
read whole): in the round of Sep 16, 2026 three payment reports
came out without `SOURCE:` and all three lost (see `cells/report.py`). With an
open leaf the searcher takes `search_voice` and one more round to close
properly, up to `SEARCH_ROUNDS`.

It goes in `planned` around the `drive` (see `search_catalog`), with `SEARCH_JUDGE` as
judge. `report` leaves `steps` inside the boundary, so the orchestrator does not see it.
"""


def cited(log: Log) -> bool:
    """Whether the searcher closed in prose with `SOURCE:` lines; `none` counts too.

    It looks at the last prose, the one `report` takes as the report, and only prose: a
    `SOURCE:` inside a `print` is the tic `report` rescues by tiers,
    not the closing the contract asks for. At the step cap with no prose the leaf stays
    open, and the voice asks for the whole report.
    """
    spoken = [m.text.strip() for m in log.said if m.role is Role.ASSISTANT]
    clean = [t for t in spoken if not extract_code(t)]
    return bool(clean) and bool(citations(clean[-1]))


SEARCH_JUDGE: Judge = facts({**LOG_FACTS, "cited_sources": cited})
"""The searcher's judge: the sale's facts plus the citation one. Predicates on the Log, so it costs nothing."""


def search_voice(plan: Plan) -> str:
    """What the planner tells the searcher with the checklist open: before searching and after each round.

    The text is `VOICE`, with the pending leaves in the contract's words.
    """
    return VOICE.format(left="; ".join(s.intent for s in pending(plan)))


def search_catalog(
    text: str,
    model: Provider,
    *,
    dossier: Dossier,
    deadline: float | None = None,
    contained: bool = False,
) -> Cell:
    """The one that searches: `planned` with its checklist around a `drive` over the catalog, and it comes out as a `Report`.

    Its transcript does not cross the boundary; `dossier` keeps it for whoever wants to
    read it. What crosses is the report with its prose and its canonical sources, plus
    `spent`, `reads` and its signed `fails`.

    The planner (`SEARCH_PLAN`, `SEARCH_JUDGE`, `search_voice`) seeds the
    checklist and says it before searching; after each round of the `drive` the
    judge closes what happened, and with something open the searcher takes the voice and
    another round, up to `SEARCH_ROUNDS`. Exhausting them is a `Fail("loop", "step
    cap: 2")` signed `searcher/loop`; the `drive`'s says `8`.

    `deadline` is the cap of the whole searcher, rounds included: each round
    builds its `drive` with what is left of the cap, and the second with what the
    first left, which may be nothing. It goes in the `drive` and not in the `loop` of
    `planned` on purpose: two equal nested caps fire together, and the
    outer one wins and drops the whole round with its good steps, which is what
    the `drive`'s `deadline` protects. Without this, two rounds were two caps, and the
    host that splits its time among the roles went over its own.

    The REPL is built when the turn starts and closed when it ends (`workshop`):
    `notes` starts empty as the contract promises, and with `contained` the child
    does not outlive the turn. Building and closing it goes in a thread because launching a
    process and waiting for it to die block the loop; in-process they cost nothing.
    """
    keep, collapse = dossier.keep("searcher"), report("searcher", paths(text))

    async def cell(seen: Log) -> Log:
        ws = await asyncio.to_thread(workshop, text, contained=contained)
        started = time.monotonic()
        try:
            handle = Handle(
                var=ws.var, schema=SCHEMA, size=f"{len(text) // 1000} KB", tools=ws.tools
            )

            async def turn(seen: Log) -> Log:
                left = None if deadline is None else max(deadline - (time.monotonic() - started), 0.0)
                step = drive(
                    model,
                    handle,
                    ws,
                    keep_recent=6,
                    keep_first=2,
                    max_steps=SEARCH_STEPS,
                    deadline=left,
                )
                return await step(seen)

            search = then(
                say(SEARCHER),
                planned(
                    planner(SEARCH_JUDGE, seed_ops=SEARCH_PLAN, voice=search_voice),
                    turn,
                    rounds=SEARCH_ROUNDS,
                ),
            )
            return await boundary(search, lambda log: collapse(keep(log)))(seen)
        finally:
            await asyncio.to_thread(ws.close)

    return cell


def with_memory(recall: Cell, search: Callable[[float | None], Cell], deadline: float | None) -> Cell:
    """The memory and then the catalog searcher, which reads its report, both within `deadline`.

    With no memory seeded (`has_memory`) it is `search(deadline)` as is. With it,
    `recall` runs (built with half the cap, in `agent.build`) and the searcher
    builds its `drive` with what is left, which is the other half or more. The `memory`
    report reaches it as one more customer turn, after the question; what to
    do with it is said by `MEMORY_FOR_SEARCH`. It moves text from one role to another and does not
    read it. The note stays inside the searcher, because a cell returns only
    its own, and the `memory` report goes out for the writer.

    Until Oct 7, 2026 they ran in parallel and the catalog did not know what to
    search for with "the same as last time". One after the other with a cap each,
    `memory-returning-customer` went from 18-39 s to 63-74 s, and the worst case
    (45 + 45 + the writer) went past the 110 s at which the host cuts. With the shared
    cap (`memory-*` probes, luna, n=3, 45 s per role): recovered 8/9,
    met 9/9, maximum 67 s; what failed was the catalog cut at 35 s
    (`memory-before-catalog` in the logbook).
    """

    async def cell(seen: Log) -> Log:
        if not has_memory(seen):
            return await search(deadline)(seen)
        started = time.monotonic()
        recalled = await recall(seen)
        left = None if deadline is None else max(deadline - (time.monotonic() - started), 0.0)
        memory = "\n\n".join(r.text for r in recalled.reports if r.who == MEMORY_WHO)
        note = (Message(Role.USER, MEMORY_FOR_SEARCH.format(memory=memory)),) if memory else ()
        return merge(recalled, await search(left)(merge(merge(seen, recalled), Log(said=note))))

    return cell
