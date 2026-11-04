"""The customer's memory as it comes in the request, turned into catalejo's `memory` channel.

Whoever runs the conversation generates and keeps it, in the shape of the
OptChat spec: the log's messages as they are and the already built nodes of the summary tree. Here it is only
read: the agent does not write it and it does not come back in the answer (logbook todo #24).

    {"messages": [{"i": 0, "kind": "customer", "text": "…", "date": "2026-06-02T15:04:00-06:00"}],
     "tree":    [{"l": 1, "i": 0, "text": "customer: …"}]}

`/queries` validates it with `schemas.queries.MemoryIn`; A2A brings it in the metadata without a
schema, and that is why both go through `memory_from`, which says what was wrong.
"""

from __future__ import annotations

from typing import Any

from catalejo.core import Entry, Memory, Node, join


def _int(d: dict[str, Any], key: str, where: str) -> int:
    v = d.get(key)
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise ValueError(f"{where}.{key} must be an integer from 0 up")
    return v


def _str(d: dict[str, Any], key: str, where: str, *, required: bool = True) -> str:
    v = d.get(key, None if required else "")
    if not isinstance(v, str):
        raise ValueError(f"{where}.{key} must be text")
    return v


def memory_from(raw: object) -> Memory:
    """The `memory` object of the JSON as `Memory`, or a `ValueError` saying what was wrong. Absent means empty."""
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ValueError("`memory` must be an object with `messages` and `tree`")
    unknown = set(raw) - {"messages", "tree"}
    if unknown:
        raise ValueError(f"`memory` does not take {', '.join(sorted(unknown))}")
    items: list[Entry | Node] = []
    for name in ("messages", "tree"):
        rows = raw.get(name) or []
        if not isinstance(rows, list):
            raise ValueError(f"memory.{name} must be a list")
        for k, d in enumerate(rows):
            where = f"memory.{name}[{k}]"
            if not isinstance(d, dict):
                raise ValueError(f"{where} is not an object")
            if name == "messages":
                items.append(
                    Entry(_int(d, "i", where), _str(d, "kind", where), _str(d, "text", where), _str(d, "date", where, required=False))
                )
            else:
                items.append(Node(_int(d, "l", where), _int(d, "i", where), _str(d, "text", where)))
    return join((), tuple(items))
