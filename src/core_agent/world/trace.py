"""What a turn is doing while it does it, for whoever is watching. It only looks.

A turn says nothing until it ends, and it lasts 45 seconds. The page shows its steps as they happen,
so a step on screen is a step that ran: the cell started, the REPL ran that code.

`watching` opens a trace in a `ContextVar`, the way `metered` opens its counter, so it survives the
tasks of `fanout` and `asyncio.to_thread`. With nobody watching, `span` costs one lookup and
emits nothing. `observed` wraps a cell and returns its Log untouched; `repl` wraps the searcher's
REPL and returns its `Output` untouched. Nothing here decides anything, and no role reads it back: the
turn is the same with a trace open or not.

The sink may be called from any thread: it is the host's job to hand the node over safely.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from catalejo.core import Cell, Log
from catalejo.rlm import Environment

log = logging.getLogger(__name__)

Node = dict[str, Any]
"""A step as the page draws it: `id`, `parent`, `kind`, `title`, `status`, and whatever `fill` added."""
Sink = Callable[[Node], None]

CLIP = 6000
"""The characters of code or output a node carries; the page shows them in a scroll box, not whole."""

_sink: ContextVar[Sink | None] = ContextVar("trace_sink", default=None)
_parent: ContextVar[str | None] = ContextVar("trace_parent", default=None)
_ids = count(1)


@contextmanager
def watching(sink: Sink) -> Iterator[None]:
    """Everything this context runs, down to its tasks and threads, tells `sink` about its steps."""
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


@dataclass
class Span:
    """A step that is running: `fill` adds what is known of it, and it goes out when it closes."""

    node: Node = field(default_factory=dict)

    def fill(self, **detail: Any) -> None:
        self.node.update({k: clip(v) for k, v in detail.items() if v})


def clip(value: Any) -> Any:
    return value[:CLIP] if isinstance(value, str) else value


@contextmanager
def span(kind: str, title: str, **detail: Any) -> Iterator[Span]:
    """A step: it goes out as `running` on entry and as `done` or `error` on exit, under the step that opened it."""
    sink = _sink.get()
    step = Span()
    if sink is None:
        yield step
        return
    step.node.update({"id": f"s{next(_ids)}", "parent": _parent.get(), "kind": kind, "title": title, "status": "running"})
    step.fill(**detail)
    sink(dict(step.node))
    started = time.monotonic()
    token = _parent.set(step.node["id"])
    try:
        yield step
    except BaseException:
        step.node["status"] = "error"
        raise
    else:
        if step.node["status"] == "running":
            step.node["status"] = "done"
    finally:
        _parent.reset(token)
        step.node["seconds"] = round(time.monotonic() - started, 1)
        sink(dict(step.node))


def note(kind: str, title: str, *, failed: bool = False, **detail: Any) -> None:
    """A step that already happened, under the one that is open."""
    with span(kind, title, **detail) as step:
        if failed:
            step.node["status"] = "error"


def observed(kind: str, title: str, cell: Cell, detail: Callable[[Log, Log, Span], None] | None = None) -> Cell:
    """`cell`, with its step on the trace. The Log goes through as is; `detail` reads what came in and went out to fill the step."""

    async def watched(seen: Log) -> Log:
        if _sink.get() is None:
            return await cell(seen)
        with span(kind, title) as step:
            out = await cell(seen)
            if detail is not None:
                try:
                    detail(seen, out, step)
                except Exception:  # the trace observes: a step it cannot fill never fails the turn
                    log.exception("could not fill the trace of %s", kind)
            for fail in out.fails:
                note("fail", fail.who, text=fail.reason, failed=True)
            return out

    return watched


class Watched:
    """A REPL that shows each run on the trace, with the code and what it printed. The rest is the REPL's."""

    def __init__(self, env: Environment) -> None:
        self._env = env

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)

    async def run(self, code: str) -> Any:
        with span("step", first_line(code), code=code) as step:
            out = await self._env.run(code)
            step.fill(output=out.err or out.stdout)
            if out.err:
                step.node["status"] = "error"
            return out


def first_line(code: str) -> str:
    return next((line.strip() for line in code.splitlines() if line.strip()), "code")
