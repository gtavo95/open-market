"""Effects as the host sees them: the moves that travel with the client and what is left to do.

The advisor sends nothing. It proposes: "send them the datasheet", "send them the account", as
moves in the `effects` channel (`core_agent.EFFECT_RULES`), and whoever has the WhatsApp is the one
who executes. Since Sep 22, 2026 it also proposes "hand
this conversation to a person" (`core_agent.HANDOFF`), at the end of the turn and not at
the entrance, when the answer left the customer without what they asked for; it travels the same way,
with `kind: "handoff"` and the reason in `args` (`origin`, `reason`, a key of
`core_agent.HANDOFF_REASONS`). Since Sep 28, 2026 the reasons that switch off
the advisor (`core_agent.TAKEN_OVER`) go out with another id, `core_agent.TAKEOVER`, and the same
kind. No routing happens here: `kind` is there so the client sends it to the
CRM and not over WhatsApp, and what the end customer sees of the escalation is the client's call. This service does not have it either, so it acts as a leash: the
moves come in with the request, go out accumulated the way the sale does, and the list of
what stayed PROPOSED goes out separately, with its args, so the client knows what to
send. It is the same deal as `sale.py`, and for the same reason: nothing is
kept here between calls.

Who closes an effect is whoever executed it, and that is why the `done` or the `reject`
are seeded by the client in the next request, not by this service. The rule, which
belongs to `core_agent.EFFECT_RULES` and is written the same way in `core_agent.host_sim`: a
proposed effect that needs args and arrived without them (the writer cited `none`) is a
`reject` with the reason; one that needs no args is a `done` with whatever came out
(the URL, the message id). A client that sends neither one breaks
nothing: `propose_effects` skips what is already in the channel, so the effect
stays proposed and is neither proposed nor announced again.

An op is encoded as the dataclass without its empty fields and decoded with
`EffectOp(**d)`, like the sale's: a separate schema would drift from the
type. `args` is the only thing that is not a string: `[key, value]` pairs, a list of
lists in JSON and a tuple of tuples here, because the type is `frozen` and compared
by equality.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

import core_agent
from catalejo.core import Args, Effect, EffectOp, Effects, effects_of, proposed

FIELDS = frozenset(f.name for f in fields(EffectOp))

NEEDS_ARGS = frozenset({"send_datasheet", "send_catalog", "send_payment_link", "sap_draft"})
"""The effects that cannot be executed without args, to say so in the answer.

It is the same as `NEEDS_ARGS` in `core_agent/roles/effects.py` (the intents with a resolver), written here
because `core_agent.__all__` does not export it: the package's contract is the
`EFFECT_RULES` table, and of whoever completes it with code there is nothing a host needs to
import. If the agent adds an intent with a resolver and this does not find out, the
client sees `executable: true` on an effect without args and sends it empty; the test
`tests/host/test_effects.py` pins it against `core_agent.EFFECT_RULES`.
"""


def op_to_dict(op: EffectOp) -> dict[str, Any]:
    """An op as JSON: the fields with a value. `args` as a list of pairs."""
    d = {k: v for k, v in asdict(op).items() if v}
    if "args" in d:
        d["args"] = [[k, v] for k, v in d["args"]]
    return d


def args_from(raw: object) -> Args:
    """The pairs of `args` as they come from the JSON. Any other shape is a `ValueError`."""
    if not isinstance(raw, list):
        raise ValueError("`args` must be a list of [key, value] pairs")
    pairs = []
    for i, pair in enumerate(raw):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"args[{i}] is not a [key, value] pair")
        k, v = pair
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError(f"args[{i}]: the key and the value are strings")
        pairs.append((k, v))
    return tuple(pairs)


def op_from_dict(d: dict[str, Any]) -> EffectOp:
    """The op back. A key `EffectOp` does not have is a `ValueError`."""
    extra = set(d) - FIELDS
    if extra:
        raise ValueError(f"op with keys that do not exist: {sorted(extra)}; the keys of an op are {sorted(FIELDS)}")
    if "verb" not in d or not isinstance(d["verb"], str) or not d["verb"]:
        raise ValueError("op without `verb`")
    clean = {k: v for k, v in d.items() if v not in (None, "", [], ())}
    if "args" in clean:
        clean["args"] = args_from(clean["args"])
    return EffectOp(**clean)


def ops_from(raw: object) -> tuple[EffectOp, ...]:
    """A list of dicts as it comes from the JSON, or a `ValueError` saying what was wrong."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("`effects` must be a list of ops")
    ops = []
    for i, d in enumerate(raw):
        if not isinstance(d, dict):
            raise ValueError(f"effects[{i}] is not an object")
        try:
            ops.append(op_from_dict(d))
        except (ValueError, TypeError) as e:
            raise ValueError(f"effects[{i}]: {e}") from None
    return tuple(ops)


@dataclass(frozen=True, slots=True)
class Pending:
    """A proposed effect the client has to execute now.

    `kind` is what it is (`document`, `bank_account`, `payment_link`): with that the
    client chooses how to send it. `args` is what the turn filled in, `[key, value]`
    pairs; for `send_datasheet` they are the paths (`path`) of the datasheets the
    answer cited, and for `send_payment_link` the order (`item`, `currency`,
    `total`, see `schemas.queries.PendingOut`).
    `executable` means it has what it needs: when false, the right thing is to
    return a `reject` and not a `done`.
    """

    id: str
    kind: str
    args: Args
    executable: bool


@dataclass(frozen=True, slots=True)
class EffectsSummary:
    """The effects after the turn: what is kept, what has to be done and a line for logs."""

    ops: tuple[EffectOp, ...]
    pending: tuple[Pending, ...]
    state: str


def to_pending(e: Effect) -> Pending:
    return Pending(id=e.id, kind=e.kind, args=e.args, executable=bool(e.args) or e.id not in NEEDS_ARGS)


def summary(ops: tuple[EffectOp, ...]) -> EffectsSummary:
    """What the host exposes of some moves: the fold, read."""
    folded: Effects = effects_of(ops)
    return EffectsSummary(
        ops=ops,
        pending=tuple(to_pending(e) for e in proposed(folded)),
        state=core_agent.effects_state(folded) if ops else "",
    )


def effects_to_dict(e: EffectsSummary) -> dict[str, Any]:
    """The `EffectsSummary` as JSON, with the ops encoded."""
    return {
        "ops": [op_to_dict(op) for op in e.ops],
        "pending": [
            {"id": p.id, "kind": p.kind, "args": [[k, v] for k, v in p.args], "executable": p.executable}
            for p in e.pending
        ],
        "state": e.state,
    }
