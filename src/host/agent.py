"""The agronomic advisor, served over HTTP.

The agent is the `core_agent/` package. This module is the host: it builds the agent with
`core_agent.build`, runs each turn with `core_agent.turn`, and translates the `Log` that comes out
into an `Answer`. Until Sep 20, 2026 the agent was a loop with
levers (`vista`, `orquestar`, `citas`...); the current one is built from the
primitives and without levers, and this host has the ones that remain: the slots and the
container.

The agent is a searcher that queries the catalog and brings a report with the
datasheets it cited, a writer that talks to the customer in the voice of the bundle's
`voice.md`, and outside the two, at the edge of the turn, the sale and the effects.
The sale is the `core_agent.SESSION` plan in the `course` channel, which lasts the
conversation. The effects are what the advisor proposes someone do
(send them the datasheet, send them the account, hand the conversation to a person),
in the `effects` channel. Since this
service keeps nothing between calls, both channels travel with the client
just like the history: they come in through `ask(sale=, effects=)` and go out whole
in `Answer.sale` and `Answer.effects` (see `sale.py` and `effects.py`).

The sale slots the customer closes (what they are looking for, how much product, whether
they buy, how they pay, the invoice details) are closed by a judgment and not a pattern
(`core_agent/world/question_judge.py`): the model compacts the whole conversation and TypeSafe
reads that state, from the `close_sale_steps` cell the agent carries at the edge of the
turn. The effects come out of the same judge, in the same request. That is why `Advisor`
receives `question_judge` built with the TypeSafe key, and why
`Answer.judgment` brings the state the model wrote and the probabilities:
the host next door sees why the sale asked for what it asked for.

The CLI is one process, one user and one session that dies with Ctrl-D. A server
lives for weeks and serves several at once, and that breaks two assumptions of the REPL:

1. Workspace variables persist between runs. Here each query comes
   from a different person, and a `products = [p for p in products if ...]` in the current
   one would change the catalog for the next one. The searcher builds its REPL
   per turn and rereads the index from disk every time, so that is enough; the
   agent is built per query anyway, because the `Dossier` where the searcher's
   transcript lands belongs to a turn and not to a process.
2. An `exec` cannot be interrupted from outside. With `container=True` the
   code runs in a child process (`core_agent.build(contained=True)`), and that one does get
   killed when the time cap cancels the step; in process the thread keeps going until it
   finishes, with a workspace nobody is looking at anymore.

What is shared is the model, which keeps its HTTP client open, the judge's
TypeSafe client, and the cap on queries in flight, which is `slots`. The judge's
memory is not: each query has its own (`QuestionJudge.fresh`), because it is
indexed by the customer's words and two conversations with the same lines
shared the judgment (until Oct 8, 2026).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import core_agent
from core_agent.roles.form import BILLED
from core_agent.world.order import Item
from core_agent.roles.human_handoff import sold
from core_agent.world import governance, typesafe
from core_agent.world.facts import LOG_FACTS
from core_agent.world.question_judge import ORDER_GATES, Judgment, QuestionJudge
from catalejo.core import Cell, EffectOp, Log, Memory, PlanOp, Role, Status, project
from catalejo.llm import Provider, Usage, metered
from catalejo.rlm import Dossier, Transcript
from .catalog import Catalog
from .rules import turn_rules


def citations(text: str) -> tuple[str, ...]:
    """Every path the answer declares as a source, one per `SOURCE:` line.

    The same parse as `catalejo.rlm.citations`, for the English marker: that one only reads
    `SOURCE:` lines, and the wheel is not ours to change.
    """
    return tuple(
        line.split(":", 1)[1].strip().strip("`").lstrip("/")
        for line in text.splitlines()
        if line.strip().upper().startswith("SOURCE:")
    )


def sources(text: str) -> tuple[str, ...]:
    """The files the model declared, without repeats and without the `none`.

    The lines are parsed by `citations`, the same parse the `cited` cell uses
    inside the turn: one single parser, or the citation that gets verified and the one that
    gets returned drift apart. `SOURCE: none` is a fact and not a source:
    it means the answer did not come from the catalog, and it reads as the empty
    list, which is what the client has to look at before applying anything.
    """
    seen: dict[str, None] = {}
    for line in citations(text):
        for part in line.split(","):
            path = part.strip()
            if path and path.lower() != "none":
                seen.setdefault(path, None)
    return tuple(seen)


def final(out: Log) -> str:
    """The last thing said that is not code, without its `SOURCE:` lines, or empty.

    It is `core_agent.answer` without the sentence: the CLI replaces an answer without a
    query with "I could not check the catalog", because there is a person on the
    other side; here there is an app that reads `grounded` and `nothing_to_search`, and the raw
    prose is the fact. Without prose it returns empty and not a filler, for the same reason.

    The `SOURCE:` lines are taken out of the text and end up in `sources`: they are for the
    host, not for whoever reads the WhatsApp. In round 16 (Sep 18,
    2026) "SOURCE: none" closed five out of six question turns, and the
    service served the prose as it was. `raw` is what the model said, for
    `sources` and for auditing.
    """
    return "\n\n".join(core_agent.messages(prose(raw(out))))


INLINE_SOURCE = re.compile(r"(?<=\S)[ \t]+(?=SOURCE:)", re.IGNORECASE)
"""A `SOURCE:` stuck to the end of a sentence, which `prose` and `citations` do not see."""


def raw(out: Log) -> str:
    """The last thing said that is not code, or empty, with each `SOURCE:` on its own line.

    The writer sometimes closes on the same line ("…4 to 7 business days. SOURCE:
    company_info/shipping.md", Sep 24, 2026). That way the line does not start with
    `SOURCE:`: the customer read it on WhatsApp and `sources` lost the path.
    """
    for m in reversed(out.said):
        if m.role is Role.ASSISTANT and "```" not in m.text:
            return INLINE_SOURCE.sub("\n", m.text.strip())
    return ""


def prose(text: str) -> str:
    """The text without the `SOURCE:` lines or the blank space they leave at the end."""
    lines = [
        ln for ln in text.splitlines() if not ln.strip().upper().startswith("SOURCE:")
    ]
    return "\n".join(lines).strip()


def message_count(out: Log, transcripts: tuple[Transcript, ...]) -> int:
    """How many messages the turn cost, counting the ones the searcher left in the dossier.

    Without adding them an orchestrated turn of nine messages would look like two: the
    searcher's edge takes its transcript out of the `Log` and leaves it in the
    `Dossier`.
    """
    return len(out.said) + sum(len(t.said) for t in transcripts)


def code_facts(
    out: Log, judgment: Judgment | None, before: tuple[PlanOp, ...], after: tuple[PlanOp, ...], form: core_agent.Forms | None = None
) -> dict[str, bool]:
    """The code rules of `governance/` in this turn, by the key of their row.

    The same functions that act: `LOG_FACTS` on the turn's `Log`, `ORDER_GATES` on
    the judgment's order (without a judgment there is no order, and they do not come out), and `sold` before and after
    the turn, because `sale_completed` escalates only the turn in which the sale closes, and
    `complete_invoice` on the form after the turn (`Forms.complete`).
    """
    saw = LOG_FACTS["opens_a_datasheet"](out)
    facts = {"opens_a_datasheet": saw if isinstance(saw, bool) else False}
    if judgment is not None and not judgment.error:
        facts.update({n: gate(judgment.order) for n, gate in ORDER_GATES.items()})
    facts["sale_completed"] = sold(Log(course=after)) and not sold(Log(course=before))
    if form is not None:
        facts[BILLED] = form.complete()
    return facts


@dataclass(frozen=True, slots=True)
class Answer:
    """What comes out of a query, already separated into what the client needs to look at.

    `grounded` is `reads > 0`: the model consulted the catalog at least once. It does not
    say the answer comes from what it read; it says it had somewhere to get it from. An
    answer with `grounded=False` is the model's opinion, unless
    `nothing_to_search` says this turn had nothing to query.

    `nothing_to_search` is the turn in which the right thing was to ask: the
    conversation has not yet given a pest, product or product type to search
    with, and the writer asks (the searcher runs anyway, since Sep 20,
    2026, and brings `SOURCE: none`). It is `core_agent.nothing_to_search`
    on the sale after the turn: the `pest` leaf is still open.

    Looking at the `Fail` of `grounded` instead of `reads` is not enough, and a real
    run said so: when the API went down, the agent ended with zero turns, and since
    `grounded` never got to vote, the empty answer went out marked as grounded.
    Absence of a veto is not backing.

    `fails` brings what each cell said, signed by its role: `searcher/grounding`
    is the searcher that answered without querying, `plan` is the sale (the judge that did not
    answer, a name nobody closes), `searcher/loop` the time cap.

    `cut_off` means the turn went past the time cap: the `loop` cancelled the step
    that overran and returned what it had, with a `Fail` from `loop` inside
    `fails`. The same `loop` reports the step cap (`step cap: 8`), and
    that is not `cut_off`: the turn finished whole, only without closing its
    checklist; it is told apart by the `reason`, which is the only thing that separates them.
    Until Sep 20, 2026 any `Fail` from the `loop` switched it on, and
    a 21 s turn came out "cut off". It is not a `TimeoutError` on purpose: a timeout set from outside
    throws away the whole `Log`, and what is inside (`tokens`, `turns`, the
    transcript) is exactly what we want to charge and log from a turn that
    hung. `seconds` is what the client waited, measured here around the
    turn. `turns` counts the turn's messages plus the ones the searcher left
    in its dossier, which its edge takes out of the `Log`.

    `sale` is the sale's moves after the turn, whole: what the
    client keeps and sends in the next request. `effects` is the same for the
    `effects` channel: what was proposed and what is already resolved, whole. What is left to
    do is read from there with `effects.summary`; the `done` or the `reject` are
    seeded by whoever executed, which is not this service.

    `judgment` is what the gates saw in this turn (`question_judge.Judgment`
    as a dict: `state`, the JSON the model wrote with the customer's
    words; `p`, the probability per gate that was asked; `labels`;
    `order`, the cart against the catalog, in shadow; `error` if there was no judgment). `None` if the turn asked the judge nothing (no
    customer slot was left open). `text` goes without the
    `SOURCE:` lines (see `final`).

    `messages` is `text` split the way it is sent over WhatsApp (`core_agent.messages`):
    the answer in one and the question in another. `text` is the same joined by a
    blank line, without the separator, and it is what comes back in the history.

    `tokens_input`, `tokens_cached` and `tokens_output` are the turn's tokens
    separated the way the provider charges them (`catalejo.llm.metered`), retries
    included: output is worth six times the input, cached a tenth.
    They count all the turn's calls through the OpenAI adapter, the judge and
    the summaries included, and `tokens` is their sum, input plus output. With another
    provider they stay at zero and `tokens` is the `spent` of the `Log`, which does not see the
    judge. `tokens_typesafe` is what the TypeSafe judge charged
    (`typesafe.metered`), apart because it has another price.

    `order` is the turn's order against the catalog (`Judgment.order`), or `None` if there was no
    judgment: without a reading there are no changes to return to the deal.

    `rules` is what each `governance/` rule of the bundle read in this turn, one
    entry per row, whether it fired or not (`host/rules.py`): the turn's case, the answer's
    p values and the order's gates, which `judgment` does not bring.
    """

    text: str
    sources: tuple[str, ...]
    grounded: bool
    tokens: int
    turns: int
    halt: bool
    fails: tuple[str, ...]
    seconds: float = 0.0
    cut_off: bool = False
    nothing_to_search: bool = False
    sale: tuple[PlanOp, ...] = ()
    effects: tuple[EffectOp, ...] = ()
    judgment: dict[str, Any] | None = None
    messages: tuple[str, ...] = ()
    rules: tuple[dict[str, Any], ...] = ()
    tokens_input: int = 0
    tokens_cached: int = 0
    tokens_output: int = 0
    tokens_typesafe: int = 0
    form: dict[str, str] = field(default_factory=dict)
    reset: bool = False
    order: tuple[Item, ...] | None = None


def cost(usage: Usage, judge: typesafe.Spend, spent: int) -> dict[str, int]:
    """What a turn charged, with the keys of `/queries`: the total and its breakdown.

    `tokens` is input plus output if the adapter kept count, and if not (another provider)
    the `spent` of the `Log`.
    """
    return {
        "tokens": usage.input + usage.output if usage.calls else spent,
        "tokens_input": usage.input,
        "tokens_cached": usage.cached,
        "tokens_output": usage.output,
        "tokens_typesafe": judge.tokens,
    }


class TurnFailed(Exception):
    """The turn raised halfway: `cost` is what it managed to charge (see `cost`), to bill it anyway."""

    def __init__(self, cause: BaseException, cost: dict[str, int]) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cost = cost


class Advisor:
    """The agent, alive as long as the process is. The workspace is not: one per query."""

    def __init__(
        self,
        cat: Catalog,
        model: Provider,
        *,
        question_judge: QuestionJudge,
        slots: int = 2,
        contained: bool = True,
    ) -> None:
        self.catalog = cat
        self.text = cat.text
        self.sheets = cat.sheets
        self.model = model
        self._gates = question_judge
        self._recaps = core_agent.Recaps(model)
        self._contained = contained
        self._slots = max(1, slots)
        self._sem = asyncio.Semaphore(self._slots)
        self._in_flight = 0

    @property
    def free(self) -> int:
        """Queries that can come in right now. At zero, the next one waits for one to leave."""
        return self._slots - self._in_flight

    def _build(
        self, deadline: float | None = None, gates: QuestionJudge | None = None, form: core_agent.Forms | None = None
    ) -> tuple[Cell, Dossier]:
        """The agent of this query, just as `core_agent.build` builds it for the CLI and the evals.

        `deadline` goes to each role and not to the turn: the searcher and the writer
        each have their own `loop`, so the whole turn can last up to twice
        the cap of each. That is why it gets split here: half to each, and
        the worst case is still the `timeout` that `ask` received, which is
        what the host next door expects.

        `contained` goes as is to `core_agent.build`: the searcher's REPL in a
        child process that gets killed if it takes too long. The searcher launches it when starting its
        turn and closes it when done, in a thread, so building here does not cost
        a `spawn`; it costs reading the bundle, and that is why `ask` builds in a thread.

        The `Dossier` belongs to this query: that is where the searcher's transcript lands,
        which its edge takes out of the `Log`, and `ask` drains it to count
        `turns`.
        """
        cap = deadline / 2 if deadline is not None else None
        dossier = Dossier()
        agent = core_agent.build(
            self.model,
            question_judge=gates if gates is not None else self._gates,
            dossier=dossier,
            deadline=cap,
            contained=self._contained,
            form=form,
        )
        return agent, dossier

    async def ask(
        self,
        question: str,
        history: tuple[tuple[str, str], ...] = (),
        *,
        sale: tuple[PlanOp, ...] = (),
        effects: tuple[EffectOp, ...] = (),
        timeout: float | None = None,
        payment: str = "",
        memory: Memory = (),
        form: dict[str, str] | None = None,
        resumed: bool = False,
        previous: dict[str, str] | None = None,
        closed: int | None = None,
        cart: Sequence[dict[str, Any]] | None = None,
    ) -> Answer:
        """A question, answered. The `Log` and the workspace start clean every time.

        If the turn raises, `TurnFailed` comes out with what it managed to charge.

        Only the prose of earlier answers travels. If it dragged the whole `Log`
        along, `reads` would come in above zero from the first step and `grounded`
        would never fire again: tomorrow's query could be answered from
        memory under cover of today's grep.

        `sale` and `effects` are the written exceptions: each channel's moves
        so far, which the client kept from the previous turn.
        `core_agent.turn` seeds `course` and `effects` with them and the agent
        returns only this turn's; what comes out in `Answer` is the sum,
        which is what the client sends back. Empty means the first turn:
        `seed` plants the seed and the gates close with whatever the
        history says, so a client that does not send the sale only loses what
        the advisor closes (`charge`). With the effects it would lose nothing, but it would
        propose again what was already sent: `propose_effects` skips what is in
        the channel, and the channel is the only thing that remembers the datasheet went out.

        `payment` is the state of the payment link the client looked up before the
        turn (`paid` or `pending`); empty means there is no link or it does not know.

        `memory` is the customer's memory from earlier conversations (see
        `host/memory.py`). If empty, the memory searcher does not run; it does not come back in
        `Answer` because the agent does not write it.

        `form` is the billing form the client kept from the previous turn, and
        `resumed` means the conversation was resumed in this turn (the host rehydrated it from
        Mongo): the advisor opens with what the order has and what is missing. `previous` is the form
        of the last closed sale, which the advisor confirms instead of asking again, and `closed` the
        index in `history` of that sale's last turn (see `core_agent.turn`). `cart` is the
        deal's lines: the cart starts from there and the model writes only the changes
        (`QuestionJudge.cart`); `order` in `Answer` is how it ended up.

        `timeout` is the seconds the turn may last, and it goes inside the
        loop as `deadline` (see `_build`): the query that overruns does not raise,
        it comes back `cut_off`, with what it managed to query and no prose. With
        `contained` the child that had the `exec` halfway gets killed right there and
        the slot really comes back; in process the `exec` thread keeps going until it
        finishes, with a workspace nobody is looking at anymore.
        """
        async with self._sem:
            self._in_flight += 1
            try:
                gates = self._gates.fresh(cart=cart)
                forms = core_agent.Forms(form, resumed=resumed, previous=previous)
                agent, dossier = await asyncio.to_thread(self._build, timeout, gates, forms)
                t0 = time.monotonic()
                try:
                    with metered() as usage, typesafe.metered() as judge:
                        out = await core_agent.turn(
                            agent, question, history, sale, effects, self._recaps, payment, memory, closed
                        )
                except Exception as e:
                    raise TurnFailed(e, cost(usage, judge, 0)) from e
                finally:
                    seconds = time.monotonic() - t0
            finally:
                self._in_flight -= 1

        said = raw(out)
        parts = core_agent.messages(prose(said))
        moves = () if forms.reset else (*sale, *out.course)
        judgment = gates.last(question, history)
        rules = turn_rules(
            governance.rules(),
            judgment=judgment,
            reply=gates.last_reply(question, history),
            case=gates.last_case(question, history),
            codes=code_facts(out, judgment, sale, moves, forms),
        )

        return Answer(
            text="\n\n".join(parts),
            messages=parts,
            sources=sources(said),
            grounded=out.reads > 0,
            tokens=cost(usage, judge, out.spent)["tokens"],
            turns=message_count(out, dossier.drain()),
            halt=out.vote is Status.HALT,
            fails=tuple(f"{f.who}: {f.reason}" for f in out.fails),
            seconds=seconds,
            cut_off=any(
                f.role_name == "loop" and f.reason.startswith("time cap")
                for f in out.fails
            ),
            nothing_to_search=core_agent.nothing_to_search(project(moves)),
            sale=moves,
            effects=() if forms.reset else (*effects, *out.effects),
            judgment=judgment.as_dict() if judgment is not None else None,
            rules=rules,
            tokens_input=usage.input,
            tokens_cached=usage.cached,
            tokens_output=usage.output,
            tokens_typesafe=judge.tokens,
            form=dict(forms.latest),
            reset=forms.reset,
            order=judgment.order if judgment is not None and not judgment.error else None,
        )

    async def aclose(self) -> None:
        """Closes the model's client and the judge's."""
        await self._gates.aclose()
        await self.model.aclose()
