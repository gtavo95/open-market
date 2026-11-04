"""The advisor quality suite: the bundle cases, run and graded by the citation.

    uv run python -m evals                     the topic tree, with how many turns each one costs; runs nothing
    uv run python -m evals --topic=company/shipping   the cases of a topic and its subtopics (`<bundle>/evals/topics.tsv`)
    uv run python -m evals <id> <id>           cases or flows by id, from any file
    uv run python -m evals <id>                a single one, with the whole transcript
    uv run python -m evals --flows <id>        conversations from flows.tsv by id, turn by turn
    uv run python -m evals --flows --all       the whole file: it is not a gate for a feature
    uv run python -m evals --flows=complex --all  the one in flows-complex.tsv
    uv run python -m evals --repeats=3         each case three times, to see which one flips
    ... --lever=<p> [--arm=<a>] [--note=<t>]   also records the row in the logbook (`evals/logbook.py`)

The whole suite is not run: each case measures a different edge, and a change is
measured with the topics it touches. That is why without arguments it prints the tree and spends nothing, and a
whole flows file asks for `--all`.

No run goes over USD 1 (`CEILING` in `evals/ab.py`): before starting it estimates with
`PER_TURN` and does not run if it does not fit, and while it runs it adds up model and judges and cuts on passing it
(`capped`). At the end it says whether the sample works as a gate: n < 10 is smoke (`sample`).

    python -m evals.ab <A> <B> <case>          a probe case against two versions, side by side (`evals/ab.py`)
    python -m evals.criterion <run.jsonl>      judges the criterion of saved runs again

It runs `build`/`turn` from the `core_agent/` package as cli.py runs them: a new agent per
run, so the searcher's REPL does not carry variables from one case to the
next, and the `Dossier` drained each turn, so the searcher's
transcript stays in the capture instead of getting lost in stdout.

The machine grades three things per turn, and the three come out separately:

- `cited`: whether the answer names one of the `pages` (`is_hit`). A cheap floor.
- `retrieved`: whether the searcher brought one of the `pages` in the sources of its
  report (`retrieved`). It is what a change to the bundle or the searcher moves.
- `met`: whether the answer does what the `criterion` says, read by TypeSafe
  (`evals/criterion.py`). It is what a change to the writer moves. Without
  `TYPESAFE_API_KEY` nothing is judged and the column comes out empty.

And the invented paths (`phantoms`). The report prints the criterion and the
answer of each case that fails in any of the three.

Two columns look at what the turn proposes to the host and not at what it says: `escalates`
(whether it opens a case for a person) and `effects` (which sends it proposes and which it does
not, and with what reason it escalates; see `effects_expected`). And `order` looks at the
cart the judge built in the turn, set against the catalog (see `order_expected`), and
`form` at the billing form after the turn (see `form_expected`). `resumption`
seeds the form of the first turn and says that the conversation was resumed, as
the host does after the session expires.

The cases live in `<bundle>/evals/` and not here: see the `evals` skill. The ids
name a customer's products, so they do not go in this file either. `okf/`
does not bring `evals/` (see `okf/ (the bundle lives in the repo)`): it runs with the live bundle,
`uv run python -m evals`.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import subprocess
import sys
import time
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core_agent import (
    BUNDLE,
    EFFECT_RULES,
    HANDOFF,
    HANDOFF_REASONS,
    QuestionJudge,
    answer,
    build,
    corpus,
    host_sim,
    provider,
    turn,
)

try:
    from core_agent import Forms
except ImportError:
    Forms = None

item_changes: Callable[..., list[dict[str, Any]]] | None
try:
    from host.deal import item_changes
except ImportError:
    item_changes = None

try:
    from core_agent import Recaps
except ImportError:
    Recaps = None
memory_from: Callable[[object], Memory] | None
try:
    from host.memory import memory_from
except ImportError:
    memory_from = None
from core_agent.world.dialogue import History, wrap
from core_agent.world.order import Item, order_dict
from catalejo.core import EffectOp, Log, Memory, Message, PlanOp, Role, effects_of
from catalejo.llm import Provider
from catalejo.rlm import Dossier, Transcript, paths, phantoms
from core_agent.world.typesafe import Client

from evals import criterion as crit
from evals.ab import CEILING, PER_TURN, SPENT, Cut, sample
from evals.logbook import LOGBOOK, append, fill, flag, without_flags

NOTICE = re.compile(r"\[(\w+)\]")

ASK_BACK = "question"
"""In `pages`: the correct answer of this turn is to ask the customer something."""

KEEP_HISTORY = 3
"""How many (question, answer) pairs travel to the next turn of a flow, as in `old/agro.py`."""


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    question: str
    pages: tuple[str, ...]
    section: str
    criterion: str
    conditions: str = ""
    """The optional `conditions` column, raw: see `evals/criterion.py`."""
    history: History = ()
    """The optional `history` column of a probe: what was said before, already written (see `history_of`)."""
    escalates: bool | None = None
    """The optional `escalates` column: whether the turn has to open a case for a person. `None` does not look at it."""
    effects: tuple[Expected, ...] = ()
    """The optional `effects` column: what the turn has to propose, or not, to the host. Empty does not look at it."""
    order: tuple[Line, ...] | None = None
    """The optional `order` column: the cart of the turn. `None` does not look at it; empty means there has to be nothing."""
    memory: Memory = ()
    """The optional `memory` column: the customer's memory from earlier conversations (see `memory_of`)."""
    form: dict[str, str | bool | None] | None = None
    """The optional `form` column: what the form has to hold after the turn (see `form_expected`)."""
    resume: dict[str, str] | None = None
    """The optional `resumption` column: the form the host rehydrates the conversation with, and that it was resumed (see `resume_of`)."""
    closes: bool = False
    """The optional `closes` column: `yes` means that after this turn the sale closes, as when the operator marks it or the payment is confirmed."""


@dataclass(frozen=True, slots=True)
class Line:
    """A line of the `order` column: the product as its title starts, and the presentation and the quantity or `None` if they do not matter."""

    product: str
    presentation: str | None
    quantity: float | None
    no_presentation: bool = False
    """`-` in the presentation: the line has to stay without one chosen."""

    def __str__(self) -> str:
        shown = "-" if self.no_presentation else (self.presentation or "?")
        return f"{self.product}:{shown}:{'?' if self.quantity is None else f'{self.quantity:g}'}"

    def matches(self, item: Item) -> bool:
        if item.product is None or not item.product.lower().startswith(self.product.lower()):
            return False
        if self.no_presentation and item.presentation is not None:
            return False
        if self.presentation and (item.presentation is None or self.presentation.lower() not in item.presentation.lower()):
            return False
        return self.quantity is None or item.quantity == self.quantity


@dataclass(frozen=True, slots=True)
class Expected:
    """An effect of the `effects` column: its id, whether it has to come out or not, and the reason if it is `handoff`."""

    id: str
    wanted: bool = True
    reason: str | None = None

    def __str__(self) -> str:
        return f"{'' if self.wanted else '-'}{self.id}{f':{self.reason}' if self.reason else ''}"


def expected(pages: str) -> tuple[str, ...]:
    """The `pages` column as a tuple: empty is `none`, `question` stays as it is."""
    return () if pages.strip() == "none" else tuple(pages.split())


def rows(tsv: str) -> list[list[str]]:
    out = []
    for row in (BUNDLE / "evals" / tsv).read_text().splitlines():
        if row.strip() and not row.startswith("#"):
            out.append(row.split("\t"))
    return out


TURNS = " || "
SAYS = " >> "


def history_of(column: str) -> History:
    """`history`: `customer >> advisor` pairs separated by ` || `, from oldest to newest.

    It is the probe of a failure that only appears with conversation ahead of it, like
    maiz-hierro-y-cogollero:4 (the customer gives the invoice details and the
    writer escalated how it is registered): it did not reproduce from a standalone turn, and
    the whole flow costs four turns. With the history written it costs one, and
    A and B read the same conversation, which in the flow changes with each run.
    What does not travel is the sale or the effects of those turns: it is what was said.
    """
    if column.strip() in ("", "·"):
        return ()
    pairs = []
    for part in column.split(TURNS):
        question, sep, reply = part.partition(SAYS)
        if not sep or not question.strip() or not reply.strip():
            raise ValueError(f"history: each turn is `customer{SAYS}advisor`, and got {part!r}")
        pairs.append((question.strip(), reply.strip()))
    return tuple(pairs)


def memory_of(column: str) -> Memory:
    """`memory`: the same JSON the host sends to `/queries`, `{"messages": [...], "tree": [...]}`, in one line.

    It is the probe of the returning customer (logbook todo #24): the memory is built by
    the host, and here it goes written by hand so that A and B read the same one. An arm from
    before Oct 5, 2026 does not have `host.memory` and ignores it: it is the side without memory.
    """
    if column.strip() in ("", "·") or memory_from is None:
        return ()
    try:
        return memory_from(json.loads(column))
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"memory: {e}") from None


def escalates_of(column: str) -> bool | None:
    """`escalates`: `yes` or `no`; empty or `·` means the case does not look at it."""
    value = column.strip().lower()
    if value in ("", "·"):
        return None
    if value in ("yes", "no"):
        return value != "no"
    raise ValueError(f"escalates: `yes`, `no` or `·`, and got {column!r}")


EFFECT_IDS = (*EFFECT_RULES, HANDOFF)
"""The ids the `effects` column can name: the sends of `EFFECT_RULES` and the escalation."""


def effects_expected(column: str) -> tuple[Expected, ...]:
    """`effects`: ids separated by space. `send_datasheet` has to come out, `-send_payment_link` must not, and
    `handoff:card_payment` has to escalate with that reason. What is not named is not looked at; empty or `·`, nothing.
    `handoff` is the kind and not the id: it also covers the `takeover` that turns the advisor off.

    Until Sep 27, 2026 no case looked at the effects: they stayed in
    the JSONL and only `handoff` was compared, without a reason (todo 12). An id or a
    reason that does not exist is a TSV error and not a case that never passes.
    """
    if column.strip() in ("", "·"):
        return ()
    out = []
    for token in column.split():
        wanted = not token.startswith("-")
        id_, _, reason = token.lstrip("-").partition(":")
        if id_ not in EFFECT_IDS:
            raise ValueError(f"effects: {id_!r} is not an effect ({', '.join(EFFECT_IDS)})")
        if reason and (id_ != HANDOFF or reason not in HANDOFF_REASONS):
            raise ValueError(f"effects: {token!r}: only `{HANDOFF}` takes a reason, one of `HANDOFF_REASONS`")
        out.append(Expected(id_, wanted, reason or None))
    return tuple(out)


EMPTY_ORDER = "empty"


def order_expected(column: str) -> tuple[Line, ...] | None:
    """`order`: `Product:presentation:quantity` lines separated by ` + `; `empty` is the cart with nothing.

    The product is the start of the catalog title (`Roycel` is `Roycel 25 EW`), the
    presentation a piece of the `# Presentations` label (`1 L`, `Amarillo 0.15`),
    `?` does not look at it and `-` asks for it to stay unchosen; the quantity is a number or `?`. The
    cart has to bring those lines and no others. Since Sep 28,
    2026, when the compaction lost the presentation of a sale already paid (todo 22).
    """
    column = column.strip()
    if column in ("", "·"):
        return None
    if column == EMPTY_ORDER:
        return ()
    out = []
    for part in column.split(" + "):
        bits = [b.strip() for b in part.split(":")]
        if len(bits) != 3 or not bits[0]:
            raise ValueError(f"order: each line is `Product:presentation:quantity`, and got {part!r}")
        product, shown, amount = bits
        try:
            quantity = None if amount == "?" else float(amount)
        except ValueError:
            raise ValueError(f"order: the quantity of {part!r} is a number or `?`") from None
        out.append(Line(product, None if shown in ("?", "-") else shown, quantity, shown == "-"))
    return tuple(out)


def order_misses_of(wanted: tuple[Line, ...], items: tuple[Item, ...]) -> tuple[str, ...]:
    """What the cart does not meet of the `order` column: missing lines and extra lines."""
    left = list(items)
    misses = []
    for w in wanted:
        hit = next((i for i in left if w.matches(i)), None)
        if hit is None:
            misses.append(f"missing {w}")
        else:
            left.remove(hit)
    misses += [f"extra {i.product or i.said_product}:{i.presentation or '-'}:{'?' if i.quantity is None else f'{i.quantity:g}'}" for i in left]
    return tuple(misses)


RESET = "_restarts"
"""In `form`: whether the turn has to empty the order and start from scratch (`Forms.reset`)."""


def form_expected(column: str) -> dict[str, str | bool | None] | None:
    """`form`: a JSON object. Each field with a text has to contain it (case-insensitive), with `null` it has
    to be missing; `_restarts` is whether the turn started from scratch. Fields it does not name are not looked at. Empty looks at nothing.
    Since Oct 8, 2026, with the billing form."""
    column = column.strip()
    if column in ("", "·"):
        return None
    value = json.loads(column)
    if not isinstance(value, dict):
        raise ValueError(f"form: it takes a JSON object, and got {column!r}")
    return value


def resume_of(column: str) -> dict[str, str] | None:
    """`resumption`: the fields the form comes in with on that turn (`{}` if none), and that the conversation was resumed. Empty, nothing."""
    column = column.strip()
    if column in ("", "·"):
        return None
    value = json.loads(column)
    if not isinstance(value, dict):
        raise ValueError(f"resumption: it takes a JSON object with the fields, and got {column!r}")
    return {str(k): str(v) for k, v in value.items()}


def form_misses_of(wanted: dict[str, str | bool | None], form: dict[str, str], reset: bool) -> tuple[str, ...]:
    """What the form of the turn does not meet of the `form` column."""
    misses = []
    for k, v in wanted.items():
        if k == RESET:
            if bool(v) != reset:
                misses.append("started from scratch and should not have" if reset else "did not start from scratch")
        elif v is None:
            if k in form:
                misses.append(f"{k} is {form[k]!r} and should be missing")
        elif str(v).lower() not in form.get(k, "").lower():
            misses.append(f"{k} is {form.get(k)!r} and should have {v!r}")
    return tuple(misses)


def cases(tsv: str) -> list[Case]:
    """The optional columns go in order, after `criterion`: `conditions`, `history`, `escalates`, `effects`, `order`, `memory`, `form`, `resumption`, `closes`."""
    return [case(id_, question, pages, section, criterion, extra) for id_, question, pages, section, criterion, *extra in rows(tsv)]


def case(id_: str, question: str, pages: str, section: str, criterion: str, extra: Sequence[str]) -> Case:
    """A row with its optional columns, the same in the standalone cases and in the flows."""
    conditions, history, escalates, effects, order, memory, form, resume, closes = (*extra, "", "", "", "", "", "", "", "", "")[:9]
    return Case(
        id_, question, expected(pages), section, criterion, conditions,
        history_of(history), escalates_of(escalates), effects_expected(effects), order_expected(order),
        memory_of(memory), form_expected(form), resume_of(resume), closes.strip() == "yes",
    )


@dataclass(frozen=True, slots=True)
class Flow:
    """A conversation: its turns in order, each one a `Case` with id `flow:n`."""

    id: str
    turns: tuple[Case, ...]


def flows(tsv: str) -> list[Flow]:
    """`flows.tsv`: one row per turn, with the flow first and the turn number.

    The number is in the file so that a row reads on its own, and it is verified:
    a turn 3 without a turn 2 is a TSV error, not a short conversation.
    """
    by_flow: dict[str, list[Case]] = {}
    for flow, turn, question, pages, section, criterion, *extra in rows(tsv):
        seen = by_flow.setdefault(flow, [])
        if turn != str(len(seen) + 1):
            raise SystemExit(f"{tsv}: flow {flow} has turn {turn} after {len(seen)}")
        seen.append(case(f"{flow}:{turn}", question, pages, section, criterion, extra))
    return [Flow(id_, tuple(turns)) for id_, turns in by_flow.items()]


SINGLE = ("cases.tsv", "questions.tsv")
"""The standalone cases: one turn each, of the agro advisor."""
CHATS = ("flows.tsv", "flows-complex.tsv", "flows-real.tsv", "flows-cart.tsv", "flows-form.tsv")
"""The conversations: a flow goes whole, its turns are not run on their own."""
TOPICS = "topics.tsv"


def units() -> list[Flow]:
    """Everything that can be run, each standalone case as a one-turn flow. An id repeated across files is an error."""
    chats = [tsv for tsv in CHATS if (BUNDLE / "evals" / tsv).exists()]
    every = [Flow(c.id, (c,)) for tsv in SINGLE for c in cases(tsv)] + [f for tsv in chats for f in flows(tsv)]
    seen: set[str] = set()
    for u in every:
        if u.id in seen:
            raise SystemExit(f"the id {u.id} is in two files of evals/")
        seen.add(u.id)
    return every


def topics(every: Sequence[Flow]) -> dict[str, tuple[str, ...]]:
    """`topics.tsv`: id → topics, the first one the main one. It fails if a case ends up without a topic or a topic names an id that does not exist."""
    table = {row[0]: tuple(row[1].split()) for row in rows(TOPICS) if len(row) > 1 and row[1].strip()}
    ids = {u.id for u in every}
    missing = [i for i in ids if i not in table]
    unknown = [i for i in table if i not in ids]
    if missing or unknown:
        raise SystemExit(f"{TOPICS}: no topic {sorted(missing)}; ids that do not exist {sorted(unknown)}")
    return table


def within(topic: str, wanted: str) -> bool:
    """`catalog/dose` is inside `catalog` and itself, not inside `catalog/do`."""
    return topic == wanted or topic.startswith(wanted.rstrip("/") + "/")


def select(argv: Sequence[str]) -> list[Flow] | None:
    """What the command line asked for. `None` means it asked for nothing: the tree is printed and nothing runs.

    `--topic=` picks by the main topic, the first of the row: the others say what else
    the case touches, and counting them would put whole flows in `catalog` for one turn that
    names a datasheet. The ids search in all the files; `--flows` without ids or topic is a
    whole file and asks for `--all`, so it does not get run by accident as a gate.
    """
    asked = [a for a in argv if not a.startswith("-")]
    wanted = [a.removeprefix("--topic=") for a in argv if a.startswith("--topic=")]
    if any(a.startswith("--flows") for a in argv) and not wanted:
        if not asked and "--all" not in argv:
            raise SystemExit(
                f"--flows without ids runs the whole of {tsv_of(argv)}: pass the ids (`--flows <id> <id>`) or a "
                "--topic=<topic>; the whole file goes with --all and does not work as a gate for a feature"
            )
        return [f for f in flows(tsv_of(argv)) if not asked or f.id in asked]
    if not asked and not wanted:
        return None
    every = units()
    table = topics(every)
    return [u for u in every if u.id in asked or any(within(table[u.id][0], w) for w in wanted)]


def tree(every: Sequence[Flow], table: dict[str, tuple[str, ...]]) -> list[tuple[str, int, int, int]]:
    """(topic, cases, turns, cases that also touch it) for each topic and each parent. Cases and turns go by the main topic, which is what `--topic=` runs."""
    paths = sorted({"/".join(t.split("/")[: i + 1]) for ts in table.values() for t in ts for i in range(len(t.split("/")))})
    out = []
    for path in paths:
        mine = [u for u in every if within(table[u.id][0], path)]
        also = [u for u in every if u not in mine and any(within(t, path) for t in table[u.id][1:])]
        out.append((path, len(mine), sum(len(u.turns) for u in mine), len(also)))
    return out


def final_text(out: Log) -> str:
    """The last thing the writer said in prose, RAW.

    It is different on purpose from `core_agent.answer`, which replaces an ungrounded
    answer with an "I could not check the catalog". Here the text as it
    came out is the data: it is what gets printed under `answered:` when a case
    fails. An exam runner that cleans what it measures is no use for
    diagnosing.
    """
    for m in reversed(out.said):
        if m.role is Role.ASSISTANT and "```" not in m.text:
            return m.text.strip()
    return "(no prose answer)"


def is_hit(case: Case, text: str) -> bool:
    """Whether it cited the page the eval expects.

    With `none` the hit is saying there is none. With `question` the hit is
    having asked, and it is read from the sign. It is a floor: an answer that
    recommends three products and closes with "which one do you want?" passes, and the row's
    criterion is what says whether that was right.
    """
    lowered = text.lower()
    if case.pages == (ASK_BACK,):
        return "?" in text
    if not case.pages:
        return "none" in lowered
    return any(p.lower() in lowered for p in case.pages)


def retrieved(case: Case, out: Log) -> bool | None:
    """Whether the searcher brought one of the `pages` in the sources of some report. With no pages to look for, `None`."""
    if not case.pages or case.pages == (ASK_BACK,):
        return None
    sources = {s.lower() for r in out.reports for s in r.sources}
    return any(p.lower() in sources for p in case.pages)


@dataclass(frozen=True, slots=True)
class Run:
    """What a run of a case left, already graded. Pure data, to test the arithmetic without a network."""

    case: Case
    attempt: int
    out: Log
    reply: str
    secs: float
    ok: bool
    ghosts: tuple[str, ...] = ()
    transcripts: tuple[Transcript, ...] = ()
    """What the searcher said in this turn, emptied from the `Dossier`."""
    found: bool | None = None
    """`retrieved`: whether the searcher brought the page. `None` if the case does not expect one."""
    met: float | None = None
    """The `p` that it met the criterion. `None` if there was no judge or it did not answer."""
    unmet: tuple[str, ...] = ()
    """The atomic conditions that failed, if the row has them."""
    order: tuple[Item, ...] | None = None
    """The cart the judge built in this turn, set against the catalog. `None` if there was no judgment."""
    form: dict[str, str] | None = None
    """The billing form after the turn."""
    reset: bool = False
    """Whether the turn started from scratch."""

    @property
    def complied(self) -> bool | None:
        return None if self.met is None else self.met >= crit.THRESHOLD

    @property
    def escalated(self) -> bool:
        """Whether the turn proposed the case for a person (`handoff`). The text does not say so: the guardian escalates without the customer reading it."""
        return any(e.kind == "handoff" for e in effects_of(self.out.effects))

    @property
    def escalation_ok(self) -> bool | None:
        return None if self.case.escalates is None else self.escalated == self.case.escalates

    @property
    def effect_misses(self) -> tuple[str, ...]:
        """What of the `effects` column the turn did not meet, worded for the report."""
        proposed = {(HANDOFF if e.kind == HANDOFF else e.id): dict(e.args) for e in effects_of(self.out.effects)}
        misses = []
        for x in self.case.effects:
            if not x.wanted:
                if x.id in proposed:
                    misses.append(f"proposed {x.id} and should not have")
            elif x.id not in proposed:
                misses.append(f"did not propose {x.id}")
            elif x.reason and proposed[x.id].get("reason") != x.reason:
                misses.append(f"{x.id} with reason {proposed[x.id].get('reason')}, and the row says {x.reason}")
        return tuple(misses)

    @property
    def effects_ok(self) -> bool | None:
        return None if not self.case.effects else not self.effect_misses

    @property
    def order_misses(self) -> tuple[str, ...]:
        """What of the `order` column the cart of the turn did not meet."""
        if self.case.order is None:
            return ()
        if self.order is None:
            return ("no judgment: no cart",)
        return order_misses_of(self.case.order, self.order)

    @property
    def order_ok(self) -> bool | None:
        return None if self.case.order is None else not self.order_misses

    @property
    def form_misses(self) -> tuple[str, ...]:
        """What of the `form` column the form of the turn did not meet."""
        if self.case.form is None:
            return ()
        return form_misses_of(self.case.form, self.form or {}, self.reset)

    @property
    def form_ok(self) -> bool | None:
        return None if self.case.form is None else not self.form_misses

    @property
    def lost(self) -> bool:
        """The provider did not answer, so this sample says nothing about quality.

        It is recognized by `Fail.role_name == "model"`, whether it comes from the writer or the
        searcher (`searcher/model`). The `loop` fails (it ran out of steps) and
        the `grounding` ones (it answered without looking) are results, and they count.
        """
        return any(f.role_name == "model" for f in self.out.fails)

    @property
    def messages(self) -> int:
        """The messages of the whole turn, searcher included: that is where the spend comes from."""
        return len(self.out.said) + sum(len(t.said) for t in self.transcripts)


@dataclass(frozen=True, slots=True)
class Summary:
    n: int
    cases: int
    stable: tuple[str, ...]
    flippers: tuple[str, ...]
    fallen: tuple[str, ...]
    mute_ones: tuple[str, ...]
    ghosts: dict[str, tuple[str, ...]]
    hits: int
    alive_ones: int
    lost_count: int
    spent: int
    spent_all: int
    turns: float
    reads: int
    notices: dict[str, int]
    secs: float = 0.0
    secs_p95: float = 0.0
    found: tuple[int, int] = (0, 0)
    """Live turns where the searcher brought the page, over those that expected one."""
    met: tuple[int, int] = (0, 0)
    """Live turns that met the criterion, over those judged."""
    slowest: tuple[str, float] = ("", 0.0)


def notices(runs: Sequence[Run]) -> dict[str, int]:
    """How many times each cell spoke, by its prefix (`[grounding]`, `[citation]`), in the writer and in the searcher. `[repl]` is output and not a notice."""
    tally: dict[str, int] = {}
    for c in runs:
        said = [*c.out.said, *(m for t in c.transcripts for m in t.said)]
        for m in said:
            m_ = NOTICE.match(m.text) if m.role is Role.USER else None
            if m_ and m_.group(1) != "repl":
                tally[m_.group(1)] = tally.get(m_.group(1), 0) + 1
    return tally


def percentile(values: Sequence[float], p: int) -> float:
    """The value that leaves `p` percent of the sample below it, by nearest rank. Empty is zero."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(math.ceil(len(ordered) * p / 100) - 1, 0)]


def summarize(runs: Sequence[Run], n: int) -> Summary:
    """The report arithmetic, apart so it can be tested without spending a cent.

    A run that died from an empty provider turn is a LOST
    SAMPLE: it leaves the denominator and is reported separately. `stable` is the case
    that hit in all its live runs; `flipper` the one that hit in some,
    and it is the list of what to dig into; `fallen` the one that hit in none;
    `mute` the one that did not leave a live sample. The mean spend and time go
    over the live ones; the billed total and the maximum, over all of them, because a
    lost sample gets paid for and waited for all the same.
    """
    by_case: dict[str, list[Run]] = {}
    for c in runs:
        by_case.setdefault(c.case.id, []).append(c)

    stable, flippers, fallen, mute_ones = [], [], [], []
    ghosts: dict[str, tuple[str, ...]] = {}
    for case_id, group in by_case.items():
        alive = [c for c in group if not c.lost]
        ok = sum(1 for c in alive if c.ok)
        if not alive:
            mute_ones.append(case_id)
        elif ok == len(alive):
            stable.append(case_id)
        elif ok == 0:
            fallen.append(case_id)
        else:
            flippers.append(case_id)
        bad = tuple(sorted({r for c in group for r in c.ghosts}))
        if bad:
            ghosts[case_id] = bad

    alive_ones = [c for c in runs if not c.lost]
    floor = max(len(alive_ones), 1)
    slowest = max(runs, key=lambda c: c.secs, default=None)
    return Summary(
        n=n,
        cases=len(by_case),
        stable=tuple(stable),
        flippers=tuple(flippers),
        fallen=tuple(fallen),
        mute_ones=tuple(mute_ones),
        ghosts=ghosts,
        hits=sum(1 for c in alive_ones if c.ok),
        alive_ones=len(alive_ones),
        lost_count=len(runs) - len(alive_ones),
        spent=sum(c.out.spent for c in alive_ones) // floor,
        spent_all=sum(c.out.spent for c in runs),
        turns=sum(c.messages for c in alive_ones) / floor,
        reads=sum(c.out.reads for c in runs),
        notices=notices(runs),
        secs=sum(c.secs for c in alive_ones) / floor,
        secs_p95=percentile([c.secs for c in alive_ones], 95),
        slowest=(f"{slowest.case.id} #{slowest.attempt + 1}", slowest.secs) if slowest else ("", 0.0),
        found=(sum(1 for c in alive_ones if c.found), sum(1 for c in alive_ones if c.found is not None)),
        met=(sum(1 for c in alive_ones if c.complied), sum(1 for c in alive_ones if c.complied is not None)),
    )


def grade(
    case: Case,
    attempt: int,
    out: Log,
    secs: float,
    real: frozenset[str],
    transcripts: tuple[Transcript, ...] = (),
) -> Run:
    """The `Run` of a turn: the raw answer, whether it hit and what it invented."""
    reply = final_text(out)
    return Run(case, attempt, out, reply, secs, is_hit(case, reply), phantoms(reply, real), transcripts, retrieved(case, out))


async def run_flow(
    flow: Flow,
    attempt: int,
    model: Provider,
    real: frozenset[str],
    question_judge: QuestionJudge | None = None,
    judge: Client | None = None,
    deal: bool = False,
) -> list[Run]:
    """A whole conversation with a single agent, as cli.py runs it.

    A standalone case is a one-turn flow. The history carries what the customer
    saw (`answer`), not the raw prose, and it is trimmed to `KEEP_HISTORY` pairs;
    the sale (`course`) and the effects (`effects`) travel whole, and the eval acts
    as host for the effects with `host_sim`: without that each turn would start with
    the channel empty and `propose_effects` would propose the same thing in all of them. The `Dossier` is
    drained per turn, so each `Run` keeps what the searcher said in that turn
    and nothing else. With `judge`, each turn is judged against its criterion with the
    same history the agent saw.

    With `deal` (`--deal`) the eval also acts as knowledge with the cart: each turn the judge
    starts from the lines of the deal (`QuestionJudge.cart`) and what it returns (`item_changes`) is
    applied for the next turn, with a judge of the flow's own. An arm without a deal ignores it. If the
    flow brings the history written, the deal starts with what those turns asked for (`written_cart`).
    """
    seed: list[dict[str, Any]] | None = None
    if deal and question_judge is not None and item_changes is not None and hasattr(question_judge, "cart"):
        seed = await written_cart(question_judge, flow.turns[0].history if flow.turns else ())
        question_judge = question_judge.fresh(cart=[])
    dossier = Dossier()
    form = Forms() if Forms is not None else None
    agent = build(model, question_judge=question_judge, dossier=dossier, **({"form": form} if form is not None else {}))
    recaps = Recaps(model) if Recaps is not None else None
    history: History = flow.turns[0].history if flow.turns else ()
    course: tuple[PlanOp, ...] = ()
    effects: tuple[EffectOp, ...] = ()
    closed: int | None = None
    done: list[Run] = []
    for case in flow.turns:
        t0 = time.monotonic()
        if seed is not None:
            question_judge.cart = seed
        if form is not None:
            form.resumed = case.resume is not None
            if case.resume is not None:
                form.latest = Forms(case.resume).latest
        if closed is not None:
            out = await turn(agent, case.question, history, course, effects, recaps, memory=case.memory, closed=closed)
        elif case.memory:
            out = await turn(agent, case.question, history, course, effects, recaps, memory=case.memory)
        else:
            out = await (turn(agent, case.question, history, course, effects, recaps) if recaps else turn(agent, case.question, history, course, effects))
        run = grade(case, attempt, out, time.monotonic() - t0, real, dossier.drain())
        judged = question_judge.last(case.question, history) if question_judge is not None else None
        if judged is not None and not judged.error:
            run = replace(run, order=judged.order)
            if seed is not None:
                seed = applied(seed, item_changes(seed, judged.order))
        if form is not None:
            run = replace(run, form=dict(form.latest), reset=form.reset)
        if judge is not None and not run.lost:
            v = await crit.judge(judge, case.criterion, case.conditions, case.question, run.reply, history)
            run = replace(run, met=v.p, unmet=v.unmet)
        done.append(run)
        if form is not None and form.reset:
            history, course, effects, closed = ((case.question, answer(out)),), (), (), None
            seed = [] if seed is not None else None
            continue
        grown = (*history, (case.question, answer(out)))
        history = grown[-KEEP_HISTORY:]
        course = (*course, *out.course)
        effects = (*effects, *out.effects, *host_sim(effects_of((*effects, *out.effects))))
        if closed is not None:
            closed = closed - (len(grown) - len(history))
            closed = closed if closed >= 0 else None
        if case.closes and form is not None:
            form.previous, form.latest = dict(form.latest), {}
            course, effects, closed = (), (), len(history) - 1
            seed = [] if seed is not None else None
    return done


async def written_cart(question_judge: QuestionJudge, history: History) -> list[dict[str, Any]]:
    """What knowledge would already have noted from a written history: the whole cart of those turns.

    Without this a flow with written history starts with the deal empty, and since Oct 8, 2026
    (76e6c4e) the changes model does not rebuild from the history what the deal does not have:
    `carrito-retomado:1` and `carrito-resumen-no-vacia:1` came out with the order empty 0/2.
    """
    if not history:
        return []
    *before, (question, _) = history
    order = await question_judge.fresh().order(Log(said=(Message(Role.USER, wrap(question, tuple(before))),)))
    return applied([], item_changes([], order))


def applied(seed: list[dict[str, Any]], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What knowledge does with `changes.items`: the line by product and presentation, and the rest as it was."""
    rows = {(r["product"], r["presentation"]): r for r in seed}
    for c in changes:
        key = (c["product"], c["presentation"])
        if c["op"] == "remove":
            rows.pop(key, None)
        else:
            rows[key] = {k: c[k] for k in ("sku", "product", "presentation", "quantity", "price")}
    return list(rows.values())


RUNS_DIR = Path(__file__).resolve().parent / "runs"
"""Where the transcript of each run goes. Ephemeral, out of git (`evals/runs/` in `.gitignore`)."""


def save(runs: Sequence[Run], argv: Sequence[str], model: str, folder: Path = RUNS_DIR) -> Path:
    """One run per line, JSONL, with the writer and the searcher whole: what the report summarizes."""
    folder.mkdir(exist_ok=True)
    flags = "_".join(a.lstrip("-").replace("=", "-").replace("/", "-") for a in without_flags(argv) if a.startswith("-")) or "default"
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S}_{flags}.jsonl"
    with path.open("w") as f:
        for c in runs:
            f.write(
                json.dumps(
                    {
                        "case": c.case.id,
                        "attempt": c.attempt + 1,
                        "model": model,
                        "ok": c.ok,
                        "retrieved": c.found,
                        "met": c.met,
                        "unmet": list(c.unmet),
                        "escalated": c.escalated,
                        "escalation_ok": c.escalation_ok,
                        "effects_ok": c.effects_ok,
                        "effects_wrong": list(c.effect_misses),
                        "order_ok": c.order_ok,
                        "order_wrong": list(c.order_misses),
                        "form_ok": c.form_ok,
                        "form_wrong": list(c.form_misses),
                        "form": c.form,
                        "order": None if c.order is None else order_dict(c.order),
                        "lost": c.lost,
                        "phantoms": list(c.ghosts),
                        "spent": c.out.spent,
                        "reads": c.out.reads,
                        "secs": round(c.secs, 1),
                        "fails": [f"{x.who}: {x.reason}" for x in c.out.fails],
                        "effects": [
                            {"id": e.id, "kind": e.kind, "state": e.status, "args": list(e.args), "note": e.note}
                            for e in effects_of(c.out.effects)
                        ],
                        "answer": c.reply,
                        "reports": [{"who": r.who, "sources": list(r.sources), "text": r.text} for r in c.out.reports],
                        "searcher": [
                            {"who": t.who, "said": [{"role": m.role.value, "text": m.text} for m in t.said]}
                            for t in c.transcripts
                        ],
                        "writer": [{"role": m.role.value, "text": m.text} for m in c.out.said],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def sha(where: Path | None = None) -> str:
    """The short commit of `where` (this repo if not), with `-dirty` if the tree was not clean.

    In this repo `evals/` does not count: it is the exam and not what gets measured, and
    `evals.ab` copies it over each side, so a clean HEAD would come out dirty.
    """
    git = ["git", "-C", str(where)] if where else ["git"]
    exam = [] if where else [":!evals"]
    try:
        head = subprocess.run([*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run([*git, "status", "--porcelain", ".", *exam], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"
    return f"{head}-dirty" if dirty else head


def origin(file: Path) -> str:
    """The commit a sync script left in `file`, short, or `·`. `sin comitear` is the literal the external script writes."""
    try:
        first, *rest = file.read_text().splitlines()
    except (OSError, ValueError):
        return "·"
    head = first.split()[0][:7] if first.strip() else "·"
    return f"{head}-dirty" if any("sin comitear" in r for r in rest) else head


def bundle() -> str:
    """Which okf commit the data is from: the bundle itself if it is a checkout, otherwise its `ORIGEN`."""
    if (BUNDLE / "ORIGEN").exists():
        return f"okf@{origin(BUNDLE / 'ORIGEN')}"
    return f"okf@{sha(BUNDLE)}"


def row(r: Summary, model: str, usd: float | None) -> str:
    """The logbook row already built. `lever`, `arm` and `note` come out as `·`: the one who ran it knows those (`logbook.fill`)."""
    return "\t".join(
        [
            date.today().isoformat(),
            "agro",
            f"agro@{sha()}",
            f"catalejo@{origin(Path('vendor/ORIGEN'))}",
            bundle(),
            "·",
            "·",
            model,
            str(r.n),
            str(r.spent),
            f"{r.turns:.1f}",
            f"{len(r.stable)}/{r.cases}",
            str(r.lost_count),
            "·" if usd is None else f"{usd:.3f}",
            "·",
        ]
    )


def line(c: Run, n: int) -> str:
    """A run in one line of the report, as it comes out."""
    mark = "···" if c.lost else ("ok " if c.ok else "BAD")
    which = f" #{c.attempt + 1}" if n > 1 else ""
    found = {None: "  ·", True: "yes", False: " NO"}[c.found]
    met = "   ·" if c.met is None else f"{c.met:4.2f}" + ("" if c.complied else "!")
    esc = {None: "", True: "  escalated ok", False: "  escalated BAD"}[c.escalation_ok]
    eff = {None: "", True: "  effects ok", False: "  effects BAD"}[c.effects_ok]
    cart = {None: "", True: "  order ok", False: "  order BAD"}[c.order_ok]
    billing = {None: "", True: "  form ok", False: "  form BAD"}[c.form_ok]
    return (
        f"  {mark} {c.case.id:30s}{which}  retrieved {found}  met {met:5s}{esc}{eff}{cart}{billing}"
        f" {c.out.spent:>7,} tok  {c.secs:5.1f}s  {c.messages:2d} messages"
    )


def transcript(c: Run) -> None:
    for t in c.transcripts:
        for m in t.said:
            print(f"\n\033[1m[{t.who}/{m.role.value}]\033[0m {m.text.strip()[:2000]}")
    for m in c.out.said:
        print(f"\n\033[1m[writer/{m.role.value}]\033[0m {m.text.strip()[:2000]}")


def repeats(argv: Sequence[str]) -> int:
    """`--repeats=N`, with an equals sign and not a space: a bare `3` would be a case id."""
    for a in argv:
        if a.startswith("--repeats="):
            value = a.removeprefix("--repeats=")
            if not value.isdigit() or int(value) < 1:
                raise SystemExit(f"--repeats takes a positive integer, not {value!r}")
            return int(value)
    return 1


def tsv_of(argv: Sequence[str]) -> str:
    """Which file of `<bundle>/evals/` runs: `cases.tsv` unless `--flows` or `--flows=<name>`."""
    for a in argv:
        if a == "--flows":
            return "flows.tsv"
        if a.startswith("--flows="):
            return f"flows-{a.removeprefix('--flows=')}.tsv"
    return "cases.tsv"


PRICES: dict[str, tuple[float, float, float, float]] = {
    "gpt-6-luna": (0.10, 0.01, 0.50, 0.0),
    "claude-haiku-5-5": (0.10, 0.01, 0.50, 0.125),
}
"""Dollars per million by model: uncached input, cached input, output, cache write.

gpt-6-luna, developers.openai.com/api/docs/models/gpt-6-luna on Oct 14, 2026, prompts of
up to 272k tokens. Until that day the row said 0.20/0.02/1.20, the price of gpt-5.6-luna: the
luna USD in the logbook since Sep 24 are worth between 0.42 and 0.50 of what they say.
OpenAI's cache write does not come in the `usage`, so it is not counted. Haiku 5.5, the one for
prompts of up to 100k tokens, Oct 7, 2026: above that everything costs five times more.
"""


def model_usd(model: Any) -> float | None:
    """What the model has spent so far at the `PRICES` rate, or `None` if it keeps no count or has no rate."""
    if (usage := getattr(model, "usage", None)) is None or (price := PRICES.get(model.model)) is None:
        return None
    written = getattr(usage, "written", 0)
    return float((usage.input - usage.cached - written) * price[0] + usage.cached * price[1] + usage.output * price[2] + written * price[3]) / 1e6


async def capped(jobs: Sequence[Coroutine[Any, Any, list[Run]]]) -> list[list[Run]]:
    """Runs the attempts together; the first that raises `Cut` cancels the others and `Cut` comes out."""
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(j) for j in jobs]
    except* Cut as cuts:
        raise max((c for c in cuts.exceptions if isinstance(c, Cut)), key=lambda c: c.spent) from None
    return [t.result() for t in tasks]


async def main(argv: list[str]) -> None:
    n = repeats(argv)
    chosen = select(argv)
    if not chosen:
        every = units()
        if chosen is not None:
            print(f"nothing with {[a for a in argv if a != '--yes']}\n")
        print("the whole suite is not run: pick a topic with --topic=<topic>, or cases by id. Per run:\n")
        for path, count, turns_, also in tree(every, topics(every)):
            depth = path.count("/")
            extra = f"  (+{also} that also touch it)" if also else ""
            print(f"  {'  ' * depth}{path.split('/')[-1]:{24 - 2 * depth}s} {count:3d} cases {turns_:4d} turns  ~USD {turns_ * PER_TURN:.2f}{extra}")
        return
    chats = any(":" in t.id for e in chosen for t in e.turns)
    turns = [t for e in chosen for t in e.turns]
    if (estimate := len(turns) * n * PER_TURN) > CEILING:
        raise SystemExit(f"~USD {estimate:.2f} ({len(turns)} turns, n={n}) is over USD {CEILING:.2f}, the ceiling of any run: shrink the cases (n does not go down)")

    text = corpus()
    real = paths(text)
    model = provider()
    question_judge = QuestionJudge.from_env(model)
    judge_ = Client.from_env()
    how_many = f"{len(chosen)} flows, {len(turns)} turns" if chats else f"{len(turns)} cases"
    judge = "with judge" if question_judge is not None else "without judge"
    print(f"corpus: {len(text):,} characters (~{len(text) // 4:,} tokens), {how_many}, n={n} · {model.model}, {judge}")
    sem = asyncio.Semaphore(4)
    solo = len(chosen) == 1 and n == 1

    async def one(flow: Flow, attempt: int) -> list[Run]:
        async with sem:
            done = await run_flow(flow, attempt, model, real, question_judge, judge_, deal="--deal" in argv)
        for c in done:
            print(line(c, n), flush=True)
            if solo:
                transcript(c)
        usd = (model_usd(model) or 0.0) + (judge_.cost if judge_ is not None else 0.0) + (question_judge.cost if question_judge is not None else 0.0)
        print(f"{SPENT}{usd:.5f}", flush=True)
        if usd > CEILING:
            raise Cut(usd)
        return done

    try:
        groups = await capped([one(e, i) for e in chosen for i in range(n)])
    except Cut as cut:
        raise SystemExit(f"cut: USD {cut.spent:.4f} spent, passed the ceiling of USD {CEILING:.2f}") from None
    finally:
        if question_judge is not None:
            await question_judge.aclose()
        if judge_ is not None:
            await judge_.aclose()
        await model.aclose()
    order = {c.id: i for i, c in enumerate(turns)}
    done = sorted((c for g in groups for c in g), key=lambda c: (order[c.case.id], c.attempt))
    r = summarize(done, n)

    print("\n\033[1m[result]\033[0m")
    title = "cited the correct page" if n == 1 else f"correct all {n}"
    print(f"  {title:25s} {len(r.stable)}/{r.cases} cases")
    if r.flippers:
        print(f"  flip                      {len(r.flippers)}  {', '.join(r.flippers)}")
    if r.fallen:
        print(f"  always fail               {len(r.fallen)}  {', '.join(r.fallen)}")
    if r.mute_ones:
        print(f"  no live sample            {len(r.mute_ones)}  {', '.join(r.mute_ones)}")
    print(f"  cited                     {r.hits}/{r.alive_ones} live runs")
    print(f"  retrieved                 {r.found[0]}/{r.found[1]} turns that expected a page")
    if judge_ is not None:
        print(f"  met the criterion         {r.met[0]}/{r.met[1]} turns judged, USD {judge_.cost:.5f}")
    watched = [c for c in done if not c.lost and c.escalation_ok is not None]
    if watched:
        print(f"  escalated as expected     {sum(1 for c in watched if c.escalation_ok)}/{len(watched)} turns with `escalates`")
    proposing = [c for c in done if not c.lost and c.effects_ok is not None]
    if proposing:
        print(f"  effects as expected       {sum(1 for c in proposing if c.effects_ok)}/{len(proposing)} turns with `effects`")
    carted = [c for c in done if not c.lost and c.order_ok is not None]
    if carted:
        print(f"  order as expected         {sum(1 for c in carted if c.order_ok)}/{len(carted)} turns with `order`")
    billed = [c for c in done if not c.lost and c.form_ok is not None]
    if billed:
        print(f"  form as expected          {sum(1 for c in billed if c.form_ok)}/{len(billed)} turns with `form`")
    if r.lost_count:
        print(f"  lost samples              {r.lost_count}  (empty turn, out of the denominator)")
    print(f"  cited a nonexistent path  {len(r.ghosts)}/{r.cases}  {r.ghosts or ''}")
    if chats:
        for flow in chosen:
            mine = [c for c in done if c.case.id.startswith(f"{flow.id}:")]
            by_attempt = [[c for c in mine if c.attempt == i] for i in range(n)]
            alive = [g for g in by_attempt if g and not any(c.lost for c in g)]
            whole = sum(1 for g in alive if all(c.ok for c in g))
            spent_ = sum(c.out.spent for g in alive for c in g) // max(len(alive), 1)
            print(f"  {flow.id:26s}{whole}/{len(alive)} whole conversations, {spent_:,} tok per conversation")
    print(f"  tokens                    {r.spent:,} mean per turn, {r.spent_all:,} billed")
    usd = model_usd(model)
    if usd is not None and (usage := getattr(model, "usage", None)) is not None:
        per_turn = usd * r.spent / r.spent_all if r.spent_all else 0.0
        print(
            f"  model                     USD {usd:.4f} the run, {per_turn:.4f} per turn "
            f"({usage.input:,} input, {usage.cached:,} cached, {usage.output:,} output)"
        )
    print(f"  time                      {r.secs:.1f} s mean per turn, p95 {r.secs_p95:.1f} s, max {r.slowest[1]:.1f} s ({r.slowest[0]})")
    print(f"  corpus queries            {r.reads}")
    paid = (usd or 0.0) + (judge_.cost if judge_ is not None else 0.0) + (question_judge.cost if question_judge is not None else 0.0)
    print(f"  sample                    {sample(n, paid)}")
    if question_judge is not None:
        print(f"  judge                     {question_judge.calls} calls, USD {question_judge.cost:.4f}, {question_judge.errors} turns without judgment")
    if r.notices:
        print(f"  cell notices              {', '.join(f'[{who}] {k}' for who, k in sorted(r.notices.items()))}")
    line_ = row(r, model.model, usd)
    print(f"\n  for {LOGBOOK}, with your lever, arm and note:\n  {line_}")
    if (lever := flag(argv, "lever")) is not None:
        ids = " ".join(a for a in without_flags(argv) if not a.startswith("-") or a.startswith("--topic="))
        note = f"{ids or tsv_of(argv)} n={n}, met {r.met[0]}/{r.met[1]}. {flag(argv, 'note') or ''}"
        append([fill(line_, lever, flag(argv, "arm") or "·", note)])
    print(f"  transcripts: {save(done, argv, model.model).relative_to(Path.cwd())}")

    for case in turns:
        group = [c for c in done if c.case.id == case.id]
        if all(
            c.ok and c.found is not False and c.complied is not False and c.escalation_ok is not False
            and c.effects_ok is not False and c.order_ok is not False and c.form_ok is not False
            and not c.out.fails and not c.ghosts
            for c in group
        ):
            continue
        print(f"\n  \033[1m{case.id}\033[0m  expected {case.pages or ('none',)}")
        print(f"    criterion: {case.criterion}")
        bad = [c for c in group if c.complied is False] or [c for c in group if not c.ok] or group
        print(f"    answered: {bad[0].reply[:600]}")
        for c in group:
            for u in c.unmet:
                print(f"    #{c.attempt + 1} failed: {u}")
            if c.escalation_ok is False:
                print(f"    #{c.attempt + 1} escalated: {'yes' if c.escalated else 'no'}, and the row says {'yes' if case.escalates else 'no'}")
            for m in c.effect_misses:
                print(f"    #{c.attempt + 1} effects: {m}")
            for m in c.order_misses:
                print(f"    #{c.attempt + 1} order: {m}")
            for m in c.form_misses:
                print(f"    #{c.attempt + 1} form: {m}")
            if c.out.fails:
                print(f"    #{c.attempt + 1} fails: {[f.reason for f in c.out.fails]}")

