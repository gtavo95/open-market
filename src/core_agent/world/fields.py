"""The description of a REPL variable, taken from its data and not written by hand.

A contract that describes the fields of `products` by hand drifts out of sync with the
code that builds them: on Sep 23, 2026 it said "certified `crops`"
and was missing six fields, and the searcher compensated by
printing all of `products[0]` every turn. `describe` walks the
records the REPL really has and says which fields there are, of what type and with
an example, so a new or renamed field shows up in the prompt by itself.

What the data does not say is the meaning: that `doses.for` names pests and
not crops cannot be deduced from a `target_ids`. That goes in `notes`, one note per
field path, and `unknown` says which notes point at a field that is gone,
so a test sees it before the model does.

It knows nothing about agro: it takes a list of dicts and returns text. Another agent
with another catalog uses it the same way.
"""

from __future__ import annotations

from typing import Any

ENUM = 4
"""Up to how many distinct values are all enumerated; with more, an example goes."""

EXAMPLE = 40
"""Up to how many characters of a text example are shown."""


def describe(records: list[dict[str, Any]], notes: dict[str, str] | None = None) -> str:
    """One line per field of `records`, in the order they appear, with its note if it has one."""
    notes = notes or {}
    lines = []
    for key, values in _fields(records).items():
        note = notes.get(key)
        lines.append(f"- `{key}`: {_kind(values, key, notes, top=True)}" + (f" — {note}" if note else ""))
    return "\n".join(lines)


def paths(records: list[dict[str, Any]]) -> set[str]:
    """All the field paths of `records`, with a dot for what is nested (`doses.for.target_ids`)."""
    out: set[str] = set()
    for key, values in _fields(records).items():
        out.add(key)
        out |= {f"{key}.{p}" for p in paths(_nested(values))}
    return out


def unknown(records: list[dict[str, Any]], notes: dict[str, str]) -> set[str]:
    """The notes that point at a field `records` does not have."""
    return set(notes) - paths(records)


def _fields(records: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Each field with all its observed values, in order of first appearance."""
    out: dict[str, list[Any]] = {}
    for r in records:
        for k, v in r.items():
            out.setdefault(k, []).append(v)
    return out


def _nested(values: list[Any]) -> list[dict[str, Any]]:
    """The dicts inside these values: the values that are dicts and the dicts in the lists."""
    out = [v for v in values if isinstance(v, dict)]
    out += [i for v in values if isinstance(v, list) for i in v if isinstance(i, dict)]
    return out


def _kind(values: list[Any], path: str, notes: dict[str, str], *, top: bool) -> str:
    present = [v for v in values if v not in (None, "", [], {})]
    if not present:
        return "empty"
    if not all(isinstance(v, (str, list, dict)) for v in present) and not all(
        isinstance(v, (int, float, bool)) for v in present
    ):
        return "value of variable type"
    if all(isinstance(v, bool) for v in present):
        return "yes/no"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "number"
    if all(isinstance(v, str) for v in present):
        return "text" + (_examples(present) if top else "")
    if all(isinstance(v, dict) for v in present):
        return "dict with " + _inline(present, path, notes)
    if all(isinstance(v, list) for v in present):
        items = [i for v in present for i in v]
        if items and all(isinstance(i, str) for i in items):
            return "list of texts" + (_examples(items) if top else "")
        if items and all(isinstance(i, dict) for i in items):
            return "list of dicts with " + _inline(items, path, notes)
        return "list"
    groups: list[list[Any]] = [
        [v for v in present if isinstance(v, str)],
        [v for v in present if isinstance(v, list)],
        [v for v in present if isinstance(v, dict)],
    ]
    return " or ".join(_kind(g, path, notes, top=top) for g in groups if g)


def _inline(records: list[dict[str, Any]], path: str, notes: dict[str, str]) -> str:
    """The fields of some nested dicts on one line: plain `k` if it is text, `k` (type) if not."""
    parts = []
    for key, values in _fields(records).items():
        sub = f"{path}.{key}"
        kind = _kind(values, sub, notes, top=False)
        note = notes.get(sub)
        detail = "; ".join(x for x in (kind if kind != "text" else "", note or "") if x)
        parts.append(f"`{key}`" + (f" ({detail})" if detail else ""))
    return ", ".join(parts)


def _examples(values: list[str]) -> str:
    distinct = list(dict.fromkeys(values))
    if len(distinct) <= ENUM:
        return ": " + " or ".join(f'"{v}"' for v in distinct)
    return ", e.g. " + ", ".join(f'"{_cut(v)}"' for v in distinct[:2])


def _cut(text: str) -> str:
    return text if len(text) <= EXAMPLE else text[: EXAMPLE - 1] + "…"
