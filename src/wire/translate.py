"""The walker: a payload and the name of its shape in, the same payload in the other tongue out.

One function per direction and one implementation under both, so a pair of the tables in
`tables.py` is read the same way going out and coming back. `to_wire` turns the interior's English
into what knowledge speaks; `to_english` is the reverse, for what knowledge sends.

What the walker does with what it does not find:

- A key the shape does not know crosses as it is and logs a WARNING (the shapes in `OPEN` are the
  exception: they are the interior's own opaque moves). A new field in either tongue shows up in the
  logs the day it appears, and a test over the real payloads turns it red before that.
- A value a table does not know crosses as it is and logs a WARNING. The worst this does is that the
  other side does not recognise it (a handoff reason it does not have collapses to `otro` there); it
  never loses the turn.
- An empty string, a number, a boolean, `None`: nothing to translate, nothing to say.

Nothing here looks at what a customer wrote. It moves names, and the values that are names.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .tables import KEYED, OPEN, SHAPES, VALUES, Field

log = logging.getLogger(__name__)


def _inverse(name: str, table: dict[str, str]) -> dict[str, str]:
    back = {spanish: english for english, spanish in table.items()}
    if len(back) != len(table):
        raise ValueError(f"wire table {name!r} is not one to one: two English values share a Spanish one")
    return back


BACKWARD: dict[str, dict[str, str]] = {name: _inverse(name, table) for name, table in VALUES.items()}
"""Each `VALUES` table read from the Spanish side."""

_OUT: dict[str, dict[str, tuple[str, Field]]] = {shape: {en: (f.wire, f) for en, f in fields.items()} for shape, fields in SHAPES.items()}
_IN: dict[str, dict[str, tuple[str, Field]]] = {shape: {f.wire: (en, f) for en, f in fields.items()} for shape, fields in SHAPES.items()}
for _shape, _fields in SHAPES.items():
    if len(_IN[_shape]) != len(_fields):
        raise ValueError(f"wire shape {_shape!r} is not one to one: two English fields share a wire name")


def to_wire(shape: str, data: Any) -> Any:
    """The interior's payload as knowledge reads it. `shape` is a key of `SHAPES` (`"AnswerOut"`, `"Compaction"`, ...)."""
    return _object(shape, data, outbound=True, extras=True, where=shape)


def to_english(shape: str, data: Any, *, extras: bool = False) -> Any:
    """What knowledge sent, as the interior reads it.

    The fields knowledge sends and the interior has no use for (`extra` in the tables: its `traza`, its
    `adjuntos`, ...) are dropped, so what comes out validates against the schema without a WARNING for each.
    `extras=True` keeps them under their English names; it is how a test proves nothing was lost.
    """
    return _object(shape, data, outbound=False, extras=extras, where=shape)


def _object(shape: str, data: Any, *, outbound: bool, extras: bool, where: str) -> Any:
    if not isinstance(data, dict):
        return data
    known = (_OUT if outbound else _IN)[shape]
    out: dict[str, Any] = {}
    for key, value in data.items():
        hit = known.get(key)
        if hit is None:
            if shape not in OPEN:
                log.warning("wire: %s has no field %r in either tongue; it goes through unchanged", where, key)
            out[key] = value
            continue
        other, field = hit
        if field.extra and not outbound and not extras:
            continue
        out[other] = _value(field, value, outbound=outbound, extras=extras, where=f"{where}.{key}")
    return out


def _value(field: Field, value: Any, *, outbound: bool, extras: bool, where: str) -> Any:
    kind = field.kind
    if kind == "scalar":
        return _word(field.table, value, outbound=outbound, where=where) if field.table else value
    if kind == "object":
        return _object(field.shape, value, outbound=outbound, extras=extras, where=where)
    if kind == "list":
        if not isinstance(value, list):
            return value
        return [_object(field.shape, x, outbound=outbound, extras=extras, where=f"{where}[]") for x in value]
    if kind == "scalars":
        if not field.table or not isinstance(value, list):
            return value
        return [_word(field.table, x, outbound=outbound, where=f"{where}[]") for x in value]
    if kind == "map":
        return _map(field, value, outbound=outbound, extras=extras, where=where)
    if kind == "args":
        return _args(value, outbound=outbound, where=where)
    return value


def _word(table: str, value: Any, *, outbound: bool, where: str) -> Any:
    """One value through a `VALUES` table, or untouched (with a WARNING if it is a word the table lacks)."""
    if not isinstance(value, str) or not value:
        return value
    side = VALUES[table] if outbound else BACKWARD[table]
    if value in side:
        return side[value]
    log.warning("wire: %s: %.80r is not in the %s table; it goes through unchanged", where, value, table)
    return value


def _map(field: Field, value: Any, *, outbound: bool, extras: bool, where: str) -> Any:
    """A dict: the keys through `field.table`, each value through the nested shape or the table `field.keyed` picks for its key."""
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        other = _word(field.table, key, outbound=outbound, where=f"{where}.{key}") if field.table else key
        english = key if outbound else other
        if field.shape:
            out[other] = _object(field.shape, item, outbound=outbound, extras=extras, where=f"{where}.{key}")
        elif field.keyed and (table := KEYED[field.keyed].get(english)):
            out[other] = _word(table, item, outbound=outbound, where=f"{where}.{key}")
        else:
            out[other] = item
    return out


def _args(value: Any, *, outbound: bool, where: str) -> Any:
    """The `[key, value]` pairs of an effect: the key through `args_key`, and the value through what its key says.

    A pair that is not two strings crosses as it is: knowledge's `Values` skips it the same way. The value of
    `item` is a JSON object in a string, and the names inside it are translated too.
    """
    if not isinstance(value, list):
        return value
    out: list[Any] = []
    for pair in value:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2 and isinstance(pair[0], str)):
            out.append(pair)
            continue
        key, item = pair
        other = _word("args_key", key, outbound=outbound, where=f"{where}.{key}")
        english = key if outbound else other
        if english == "item":
            out.append([other, _item(item, outbound=outbound, where=f"{where}.{key}")])
        elif table := KEYED["args_value"].get(english):
            out.append([other, _word(table, item, outbound=outbound, where=f"{where}.{key}")])
        else:
            out.append([other, item])
    return out


def _item(text: Any, *, outbound: bool, where: str) -> Any:
    """A line of the payment link: a JSON object in a string, written the way the interior writes it (`order.payment_args`)."""
    if not isinstance(text, str):
        return text
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        log.warning("wire: %s: an `item` that is not a JSON object goes through unchanged", where)
        return text
    return json.dumps(_object("ArgsItem", parsed, outbound=outbound, extras=True, where=where), ensure_ascii=False)
