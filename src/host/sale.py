"""The sale as the host sees it: the moves that travel with the client and what is read from them.

The sale plan (`core_agent.SESSION`, `course` channel) lasts the whole
conversation and this service keeps nothing between calls. So the moves
travel the way the history does: the client sends them with every request and takes back
the ones that come out. What comes out is the COMPLETE moves after the turn, not the
delta: by the fold law, `project((*before, *turn))` gives the same plan as
keeping each delta at the end of the previous one, and sending the total spares the
client from knowing about folds. It is enough for it to keep the last thing it received.

The moves are opaque to the client and the names say so: `ops` is what
gets returned as is, and everything else (`state`, `stage`, `step`, `ask`,
`pending`, `closed`, `tree`) is reading, computed here over the projected
plan with what catalejo already knows how to do, so whoever runs the
conversation decides without taking the plan apart: what to ask the customer, whether the sale
closed, which stage it is in. None of those readings goes back to the agent.

An op is encoded as the dataclass, without its empty fields, and decoded with
`PlanOp(**d)`: there is no separate schema that could drift from the type. An
unknown key is an error and is not ignored, because a client that sends
`state` where `status` goes would believe it marked something.

The one difference from the dataclass is the `padre` field, which is `parent` on the wire:
catalejo's API keeps the Spanish name, so the two functions below rename it at the edge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from catalejo.core import Plan, PlanOp, active, children, closed, pending, project
from catalejo.rlm import checklist

import core_agent

WIRE = {"padre": "parent"}
"""`PlanOp` fields whose JSON key is another name. `padre` is catalejo's API, `parent` is the wire."""

FIELDS = frozenset(WIRE.get(f.name, f.name) for f in fields(PlanOp))


def op_to_dict(op: PlanOp) -> dict[str, Any]:
    """An op as JSON: the fields with a value. All of them are strings since Sep 20, 2026 (`exige` went away)."""
    return {WIRE.get(k, k): v for k, v in asdict(op).items() if v}


def op_from_dict(d: dict[str, Any]) -> PlanOp:
    """The op back. A key `PlanOp` does not have is a `ValueError`."""
    extra = set(d) - FIELDS
    if extra:
        raise ValueError(f"op with keys that do not exist: {sorted(extra)}; the keys of an op are {sorted(FIELDS)}")
    if "verb" not in d or not isinstance(d["verb"], str) or not d["verb"]:
        raise ValueError("op without `verb`")
    clean = {k: v for k, v in d.items() if v not in (None, "", [], ())}
    if "parent" in clean:
        clean["padre"] = clean.pop("parent")
    return PlanOp(**clean)


def ops_from(raw: object) -> tuple[PlanOp, ...]:
    """A list of dicts as it comes from the JSON, or a `ValueError` saying what was wrong."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("`sale` must be a list of ops")
    ops = []
    for i, d in enumerate(raw):
        if not isinstance(d, dict):
            raise ValueError(f"sale[{i}] is not an object")
        try:
            ops.append(op_from_dict(d))
        except (ValueError, TypeError) as e:
            raise ValueError(f"sale[{i}]: {e}") from None
    return tuple(ops)


@dataclass(frozen=True, slots=True)
class NextAsk:
    """The next thing to ask the customer for: the item id and how to ask for it (`core_agent.ASKS`)."""

    id: str
    what: str


@dataclass(frozen=True, slots=True)
class SaleSummary:
    """The sale after the turn, with the moves to return and what is read from them.

    `ops` is the only thing the client has to keep and send in the next
    request. `state` is the line from `core_agent.sale_state` ("sale 3/8: next
    `quantity`"). `stage` is the active root stage (`diagnosis`, `payment`,
    `billing`) and `step` the leaf inside it; both empty when the sale
    closed. `ask` is what only the customer can close and is due to be asked now, or
    `None` if what follows is the advisor's work or nothing is left. `pending` and
    `closed` are the leaves, in plan order. `tree` is the checklist
    drawn the way the model would read it in the `todo` view, for logs and for eyes.
    `done` means no open leaf is left.
    """

    ops: tuple[PlanOp, ...]
    state: str
    stage: str
    step: str
    ask: NextAsk | None
    pending: tuple[str, ...]
    closed: tuple[str, ...]
    tree: str
    done: bool


def leaves(plan: Plan) -> Plan:
    return tuple(s for s in plan if not children(plan, s.id))


def summary(ops: tuple[PlanOp, ...]) -> SaleSummary:
    """What the host exposes of some moves: the projected plan, read."""
    plan = project(ops)
    leaf = active(plan)
    stage = ""
    if leaf is not None:
        root = leaf
        while root.padre:
            parent = next((s for s in plan if s.id == root.padre), None)
            if parent is None:
                break
            root = parent
        stage = root.id if root is not leaf else ""
    upcoming = core_agent.ask_next(plan)
    open_leaves = leaves(pending(plan))
    return SaleSummary(
        ops=ops,
        state=core_agent.sale_state(plan) if plan else "",
        stage=stage,
        step=leaf.id if leaf is not None else "",
        ask=NextAsk(upcoming.id, core_agent.ASKS[upcoming.id]) if upcoming is not None else None,
        pending=tuple(s.id for s in open_leaves),
        closed=tuple(s.id for s in leaves(plan) if closed(plan, s)),
        tree=checklist(plan) if plan else "",
        done=bool(plan) and not open_leaves,
    )


def sale_to_dict(v: SaleSummary) -> dict[str, Any]:
    """The `SaleSummary` as JSON, with the ops encoded."""
    return {
        "ops": [op_to_dict(op) for op in v.ops],
        "state": v.state,
        "stage": v.stage,
        "active": v.step,
        "asks": {"id": v.ask.id, "what": v.ask.what} if v.ask is not None else None,
        "pending": list(v.pending),
        "closed_steps": list(v.closed),
        "tree": v.tree,
        "closed": v.done,
    }
