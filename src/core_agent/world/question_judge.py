"""The sale's gates as a judge for `close_steps` and `propose_effects`: TypeSafe reads the conversation.

Ten things close sale steps, and the model closes none of them. Five are
closed by what the customer said: whether they already said what they are looking for, how much product they want, whether
they want to buy, how they pay and whose name the invoice goes in. Four are closed by
what the model did on the turn: it queried the catalog, opened a datasheet, read the
payment methods, read the accounts. One is closed by what the advisor answered: whether
it recommended a concrete product. And two more, since Sep 21,
2026, do not close steps but propose effects: whether the customer asked for the datasheet
and whether they asked for the account (`propose_effects`, with `EFFECT_RULES` in `roles/effects.py`). And one
more, since Sep 22, 2026, does not close anything either: whether the answer left the
customer without what they asked for and a person is needed (`propose_handoff`, with the verdict
of `roles/human_handoff.py`). All thirteen come in through the same door, a `Judge` from
`catalejo.core`; `close_steps` asks the ones that close, `propose_effects` the ones that propose
and the escalation its own.

# Thirteen names, one label, two judges

A `Judge` is `(Log, names) -> probability per name`: it answers what it knows
and omits what it does not. Here there are two. `LOG_FACTS` are the four facts of the turn as
predicates on the Log, and `facts(LOG_FACTS)` turns them into a judge: 1.0 if the fact
is there, 0.0 if not. `QuestionJudge` is the network judge: it answers the seven of
`SALE_QUESTIONS` about what the customer said and the two of `REPLY_QUESTIONS` about what the
advisor answered, with TypeSafe. `judge(question_judge)` chains them, the facts first
because they cost nothing, and that is the one `close_sale_steps` passes to the sale's `planner` (`roles/sale.py`).
The texts the model and TypeSafe read, the questions with their examples and the
compaction request, live in `prompts/judge.py`; here is how they are requested.

The label is not one more name and that is why it is counted apart: `HANDOFF_REASON_QUESTIONS` is what
is asked with a `choice`, what the escalation is about, and what comes back is an
option and not a probability. It comes out through `QuestionJudge.label`, not through the `Judge`, and
travels in the same request as the answer's noul.

What is asked is not here: the plan, the intents table and the
escalation verdict say it. `close_steps` gathers the `done_when` of the open
steps, `propose_effects` the `asked` and `requires` of the missing intents, the
verdict asks for `HANDOFF_QUESTIONS` and, if any passed the threshold, the label; and those names
are the ones that arrive. With
`pest` closed nobody asks `has_search_terms` again. And a name that
neither judge answers is a `Fail` on every run, so a
misspelled gate shows on the first turn. What TypeSafe receives is something
else: `_read` sends it all of `SALE_QUESTIONS` the turn's memory does not
have, not only those this cell asked for, because they are independent over the
same conversation and the conversation is what is charged; that way `close_steps` and `propose_effects` are one
request per turn and not two.

Until Sep 20, 2026 the network's five entered the plan
disguised as predicates: `registry()` wrapped each question in a
`Log -> bool`, `advance` asked them at every step of the loop, and that is why this
module memoized with futures and the host pre-judged in `turn` before seeding.
With `close_sale_steps` in the wiring each is asked once per place, and memory remains
for what remains: that `before` and `after` do not pay twice for the same turn.

# How what the customer said is judged

TypeSafe reads the conversation (`spoken`: the envelope's customer/advisor pairs, with the
long answers summarized, and the last message) and answers the questions it was
asked, each one a `noul`, the probability of a yes, in a single request. Separately, the
model compacts: it reads the whole conversation and writes a JSON with what the customer
said, in their words and with the fields it chooses (`compact`), and in two other
calls, in parallel, the `cart` (`cart`) and what the advisor already said (`said_before`). The state is for the host and the `context` report,
and the cart for the order report; the gates read neither. `close_steps` decides with `p >= threshold`; the threshold is its own
(`THRESHOLD` is the one that was measured) and not this module's.

Until Sep 28, 2026 the gates read the compacted state: it separated
what the customer said (the model wrote it, quoting them) from what follows for the sale (the
judge answered it). But compaction loses what the customer accepted from the advisor
("Silverstrike in 1 L" and a "yes") and the payment method that changed from transfer to link.
Over 29 turns, of 464 gates 20 crossed the threshold differently and the conversation
got 18 right, the state 1; in the A/B of flows-real at n=2, `met` 30/38 on both
sides and 10% fewer tokens. That the model proposes the state and not a fixed schema is on
purpose: a schema is another list, and the list is what did not work. Until Sep 18, 2026 they were regexes
over the customer's words, and "leafcutter ants in the coffee" was in none of them.

Tested live before building it, on the raw conversation, 10 cases, USD
0.0004: leafcutter ants 0.93 and "water treatment" 0.80 against "I have a problem on
the tomato" 0.04 and a greeting 0.04; area 0.87 and 0.95 against "it's a lot of land"
0.06; buying 0.99 against "how much is it?" 0.03; payment 0.98; invoice 0.99.

# How what the advisor answered is judged

One step: TypeSafe reads the turn's answer, the assistant's last prose in
`said`, with what the customer said alongside, and answers `REPLY_QUESTIONS` and `HANDOFF_REASON_QUESTIONS` in
the same request. It does not go through compaction because that belongs to the customer, and it does not go
through the turn's memory because the sale of `before` and that of `after` see
different answers: none, and the writer's. It is memoized under the text
of the answer, with the noul and the labels together, so whoever asks
second does not go back to the network.

The answer's two questions look at the same thing from both sides: whether
it recommended a product (closes `product`) and whether it left the customer without what they asked for
(opens the escalation). One is not the negation of the other, and that is why there are two: the
turn that asks the customer what pest they see recommends nothing and does not leave
them without anything either, because asking for a detail is moving forward.

# When it fails

If the model or TypeSafe do not answer, the judgment stays with `error` and memoized
all the same, so the turn's second run does not hit a downed
service again. The judge raises `JudgeError`, `close_steps` records it as a plan `Fail`
and closes nothing: the safe side is to keep asking. The searcher does not depend
on the judge: it runs every turn.

# What it costs

Compaction and the cart are two short calls to the model (the conversation plus a
paragraph), at once, and the judgment about a thousand TypeSafe tokens, USD 0.00004, with the seven questions
inside: `propose_effects`, which runs after `close_steps` on the same turn, comes from
memory without going to the network. The advisor's answer
is another thousand TypeSafe tokens per turn, no model, with the two questions and
the reason inside: since the escalation is asked every turn, that
request stopped depending on `product` staying open, and it is still one. They are counted apart from what the loop spends: `model_tokens`
for the model, `tokens` and `cost` for TypeSafe.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from catalejo.core import Judge, Log, Message, Role, chain, effects_of, facts
from catalejo.llm import Provider

from ..prompts.judge import (
    REPLY_QUESTIONS,
    SAID,
    SAID_PROMPT,
    ASKED_ACCOUNT,
    ASKED_DATASHEET,
    AGAIN,
    OPEN,
    CART,
    CART_CHANGES,
    CART_CHANGES_PROMPT,
    CART_EMPTY,
    CART_PROMPT,
    ASKS_RESET,
    PAYMENT_METHOD,
    PRESENTATION,
    PRODUCT,
    presentation_question,
    product_question,
    COMPACT,
    HANDOFF_REASON,
    HANDOFF_REASON_QUESTIONS,
    LABEL_GATES,
    SALE_LABELS,
    SALE_QUESTIONS,
    HANDOFF_REASONS,
    RECOMMENDED,
    HANDOFF_ASKS,
    ALERT_ASKS,
    TURN_CASE,
    TURN_CASE_QUESTIONS,
)
from .dialogue import History, conversation, customer_words, since_sale, wrap
from .facts import LOG_FACTS, answer_of
from .order import Item, billable, choose, has_quantities, order_dict, price_order, remember, said_products, sheets, titled
from .typesafe import Client, Response, TypeSafeError

THRESHOLD = 0.8
"""From what probability a gate is met. Strict on purpose.

A slot that closes too eagerly drags through the whole conversation: the sale moves
on to asking for the area when the pest is not clear, and no later turn
undoes it. One that closes too little costs one extra question. It starts on the
side that costs a question and is loosened with the judgments saved in the
eval captures, which carry each turn's probabilities.

It is the one `close_sale_steps` passes to the `planner` as `umbral=THRESHOLD`. Until Sep 20,
2026 it also turned the searcher off with `p < 1 - THRESHOLD`; today the searcher runs
every turn.
"""


ORDER_GATES = {"order_with_quantities": has_quantities, "chargeable_order": billable}
"""The gates the order answers and not TypeSafe: 1.0 or 0.0, from the same judgment of the turn.

`order_with_quantities` has closed `quantity` since Sep 25, 2026
(`roles/sale.py`). `said_quantity` is still answered because plans the
host seeded earlier have it as `done_when`. `chargeable_order` is asked for by the
payment link (`send_payment_link` in `roles/effects.py`), since the same day.
"""


STATE_QUESTIONS: dict[str, dict[str, Any]] = {**SALE_QUESTIONS, **HANDOFF_ASKS, **ALERT_ASKS}
"""Everything asked about what the customer said (`spoken`), in one request: the sale and what escalates on the way in.

`HANDOFF_ASKS` has been here since Sep 25, 2026 (`roles/human_handoff.py`,
`asked_handoff`): they are questions about what the customer said, like the sale's, so they
travel in the same request and do not cost a separate one. `ALERT_ASKS` likewise, since Sep 26,
2026 (`roles/alerts.py`).
"""


FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class JudgeError(RuntimeError):
    """The turn's judgment is missing: the model failed while compacting or TypeSafe while reading."""


@dataclass(frozen=True, slots=True)
class Judgment:
    """What is known about the customer on a turn: the state the model wrote and what the judge read.

    `state` is the compaction's JSON as it stands; `p` is probability per
    gate, those asked so far on this turn; `labels` the
    `SALE_LABELS` labels (how they said they pay) and `dist` their distribution per
    option, which is where those of `LABEL_GATES` come from; `order` the order the
    model recorded in `cart`, put against the catalog (`world/order.py`), in
    shadow, empty on the turn the customer asked to start from scratch (`reset`); `error` is why there is no
    judgment, and with an error `p` is empty. `spent` is the model's tokens
    compacting and `tokens` TypeSafe's reading, summed.
    """

    state: dict[str, Any]
    p: dict[str, float]
    error: str = ""
    spent: int = 0
    tokens: int = 0
    labels: dict[str, str] = field(default_factory=dict)
    dist: dict[str, dict[str, float]] = field(default_factory=dict)
    order: tuple[Item, ...] = ()
    said: tuple[str, ...] = ()
    again: tuple[str, ...] = ()
    unanswered: frozenset[str] = frozenset()
    picks: dict[str, tuple[Pick, ...]] = field(default_factory=dict)

    @property
    def reset(self) -> bool:
        """Whether the customer asked in this message to empty the order and start from scratch (`ASKS_RESET` above the threshold)."""
        return self.p.get(ASKS_RESET, 0.0) >= THRESHOLD

    def as_dict(self) -> dict[str, Any]:
        """For the eval capture and for the host: state, probabilities, labels, order and the error if there was one.

        `order.restarted` is `reset`: the host reads it to empty the cart card.
        """
        return {
            "state": self.state,
            "p": dict(self.p),
            "labels": dict(self.labels),
            "order": {**order_dict(self.order), "restarted": self.reset},
            "already_said": list(self.said),
            "asks_again": list(self.again),
            "unanswered": sorted(self.unanswered),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class Answered:
    """What was judged about an advisor answer, in one request: the probabilities and the labels.

    `p` is the noul of `REPLY_QUESTIONS` and `labels` the options of `HANDOFF_REASON_QUESTIONS`, which are not
    probabilities and that is why they do not come in through the `Judge`; `label_p` is the probability of the
    chosen option, for the turn's record, and is missing if TypeSafe did not bring the distribution.
    Empty means this turn has not answered yet, not that it was judged and came out no.
    """

    p: dict[str, float]
    labels: dict[str, str]
    label_p: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Pick:
    """What a `choice` picked for a cart line (`PRODUCT`, `PRESENTATION`), for the turn's record.

    `said` is what the customer said; `option`, what remained (the title or the presentation, or the
    option as it stands if it was none on the list); `p`, the probability of that option, or `None`
    if TypeSafe did not bring the distribution. It decides nothing: the code already took the line.
    """

    said: str
    option: str
    p: float | None


@dataclass(frozen=True, slots=True)
class TurnCase:
    """The turn's case (`TURN_CASES`) with its distribution, or why there was none: then the writer received the four lines."""

    case: str
    p: dict[str, float]
    error: str = ""


EMPTY = Answered({}, {})
"""What is known about a turn with no answer: nothing, and without going to the network."""


def key_of(question: str, history: History) -> str:
    """The key of a turn: the customer's words as `customer_words` takes them from the envelope."""
    return customer_words(Log(said=(Message(Role.USER, wrap(question, history)),)))


def distribution(reading: Response, key: str) -> dict[str, float]:
    """A `choice`'s rounded distribution, or empty if TypeSafe did not bring it: it is for the record, it decides nothing."""
    try:
        return {o: round(v, 2) for o, v in reading.probabilities(key).items()}
    except TypeSafeError:
        return {}


def chosen_p(reading: Response, labels: dict[str, str]) -> dict[str, float]:
    """The probability of the chosen option in each label, those that bring it."""
    out = {}
    for n, label in labels.items():
        if label in (dist := distribution(reading, n)):
            out[n] = dist[label]
    return out


def transcript(question: str, history: History) -> str:
    """The whole conversation for the model, with nothing cut, from oldest to now."""
    lines = []
    for p, r in history:
        lines.append(f"Customer: {p}")
        lines.append(f"Advisor: {r}")
    lines.append(f"Customer: {question}")
    return "\n\n".join(lines)


def parse_state(text: str) -> dict[str, Any]:
    """The JSON of the model's answer, with or without a code fence; if there is no JSON, the text in `text`."""
    candidates = [text.strip()]
    fence_match = FENCE.search(text)
    if fence_match:
        candidates.insert(0, fence_match.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for c in candidates:
        try:
            value = json.loads(c)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return {"text": text.strip()}


def spoken(seen: Log) -> dict[str, Any]:
    """What TypeSafe reads for the customer's gates: the conversation in order and the last message.

    The advisor's long answers go summarized, as in the envelope. Until Sep 28,
    2026 it read the compacted `state`, which loses what the
    customer accepted from the advisor ("Silverstrike in 1 L") and the payment method that changed:
    over 29 turns of flows-real and a prod sale, of 464 gates 20
    crossed the threshold differently, and the conversation got 18 right, the state 1, one doubtful.

    Since Oct 8, 2026 without the turns of a sale already closed (`since_sale`), like the
    cart and the form: the next purchase starts from scratch, and the "I want it" or the "I'll pay by
    link" of the previous one does not close it.
    """
    question, history = since_sale(seen)
    return {"conversation": [{"customer": p, "advisor": r} for p, r in history], "last_message": question}


def quoted(seen: Log) -> tuple[tuple[str, str], ...]:
    """The args of the last payment link that went out in the conversation and was not rejected, or empty. It is the cart's memory."""
    links = [e for e in effects_of(seen.effects) if e.id == "send_payment_link" and e.args and e.status != "rejected"]
    return links[-1].args if links else ()


async def compact(model: Provider, question: str, history: History) -> tuple[dict[str, Any], int]:
    """The state written by the model, and what it cost. One call, no REPL."""
    reply = await model.complete((Message(Role.USER, COMPACT + transcript(question, history)),))
    return parse_state(reply.message.text), reply.spent


Row = dict[str, Any]
"""A raw cart line, as the model writes it and `price_order` reads it: `product`, `presentation`, `quantity`."""


def cart_lines(seed: Sequence[Row]) -> str:
    """What is recorded, one line per number, as `CART_CHANGES_PROMPT` reads it."""
    if not seed:
        return CART_EMPTY
    def shown(v: Any) -> str:
        return f"{v:g}" if isinstance(v, float) else str(v if v not in (None, "") else "?")
    return "\n".join(f"{n}. {shown(r.get('product'))} · {shown(r.get('presentation'))} · {shown(r.get('quantity'))}" for n, r in enumerate(seed, 1))


def apply_cart(seed: Sequence[Row], raw: object) -> list[Row]:
    """What is recorded with the model's changes: `add` adds a line, `change` overwrites what is not null, `remove` takes it out.

    A line is named by its number in `cart_lines`; one that does not exist, or a malformed change,
    moves nothing. What the model does not name stays as it came.
    """
    rows: list[Row | None] = [{"product": r.get("product"), "presentation": r.get("presentation"), "quantity": r.get("quantity")} for r in seed]
    added: list[Row] = []
    for change in raw if isinstance(raw, list) else ():
        if not isinstance(change, dict):
            continue
        op, line = change.get("op"), change.get("line")
        if op == "add" and change.get("product"):
            added.append({k: change.get(k) for k in ("product", "presentation", "quantity")})
            continue
        if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(rows) or rows[line - 1] is None:
            continue
        if op == "remove":
            rows[line - 1] = None
        elif op == "change":
            row = rows[line - 1]
            rows[line - 1] = {**row, **{k: change[k] for k in ("presentation", "quantity") if change.get(k) is not None}}
    return [r for r in rows if r is not None] + added


async def cart(model: Provider, question: str, history: History, seed: Sequence[Row] | None = None) -> tuple[Any, int]:
    """The cart written by the model, raw for `price_order`, and what it cost. One call, no REPL.

    With `seed` (the deal's lines) the model writes only the changes and the cart is what is
    recorded with those changes (`apply_cart`); without it, the whole cart of the conversation.
    """
    if seed is None:
        reply = await model.complete((Message(Role.USER, CART_PROMPT + transcript(question, history)),))
        return parse_state(reply.message.text).get(CART), reply.spent
    prompt = CART_CHANGES_PROMPT.replace("{cart}", cart_lines(seed))
    reply = await model.complete((Message(Role.USER, prompt + transcript(question, history)),))
    return apply_cart(seed, parse_state(reply.message.text).get(CART_CHANGES)), reply.spent


async def said_before(
    model: Provider, question: str, history: History
) -> tuple[tuple[str, ...], tuple[str, ...], frozenset[str], int]:
    """What the advisor already said or asked, what the customer asks for again, the leaves asked for with no answer, and what it cost. No history, nothing and no call."""
    if not history:
        return (), (), frozenset(), 0
    reply = await model.complete((Message(Role.USER, SAID_PROMPT + transcript(question, history)),))
    said = parse_state(reply.message.text)
    return _lines(said.get(SAID)), _lines(said.get(AGAIN)), frozenset(_lines(said.get(OPEN))), reply.spent


def _lines(value: Any) -> tuple[str, ...]:
    """A list of lines from the model's JSON, without empties; anything else, nothing."""
    return tuple(str(v).strip() for v in value if str(v).strip()) if isinstance(value, list) else ()


class QuestionJudge:
    """The network judge: it answers `SALE_QUESTIONS`, `REPLY_QUESTIONS` and `HANDOFF_REASON_QUESTIONS` with TypeSafe, and memoizes what was judged.

    Two doors, because there are two forms of answer. As a `Judge`,
    `await question_judge(seen, names)` returns `p` per name, only for those that are
    in `STATE_QUESTIONS` or in `REPLY_QUESTIONS`, and omits the rest: `close_steps`,
    `propose_effects` and the escalation verdict call it. As a labeler,
    `await question_judge.label(seen, name)` returns the option a `choice`
    of `HANDOFF_REASON_QUESTIONS` picked: only the verdict calls that, and it comes from the same request.

    Two memories. That of `SALE_QUESTIONS` is per turn, under the customer's words
    (`customer_words`), which are the same string from any Log of the same
    turn: it keeps the compacted state and the answers it already has, and a
    second call on the same turn with new names compacts zero times and
    asks only what is missing. That of the answer is per answer, under its
    text, and keeps the noul and the labels together: the sale of `before` has no
    answer and does not ask, and in `after` the sale, the escalation and the
    reason are a single request. `keep` bounds both: a host that lives for weeks
    cannot keep every conversation it judged.
    """

    def __init__(self, client: Client, model: Provider, *, keep: int = 256, cart: Sequence[Row] | None = None) -> None:
        self._client = client
        self._model = model
        self._keep = keep
        self.cart = cart
        """The deal's lines, if there is one: the cart starts from there and the model writes the changes (`CART_CHANGES_PROMPT`)."""
        self._done: OrderedDict[str, Judgment] = OrderedDict()
        self._pending: dict[str, asyncio.Future[Judgment]] = {}
        self._answered: OrderedDict[str, Answered] = OrderedDict()
        self._cases: OrderedDict[tuple[str, str], TurnCase] = OrderedDict()
        self._replies: OrderedDict[str, Answered] = OrderedDict()
        self._turn_cases: OrderedDict[str, TurnCase] = OrderedDict()
        self.model_tokens = 0
        """What the model spent compacting, building the cart and listing what was already said, summed."""
        self.errors = 0
        """How many turns were left without a judgment."""

    def fresh(self, cart: Sequence[Row] | None = None) -> QuestionJudge:
        """A new one with the same TypeSafe client and the same model, and empty memory: the one for a query.

        Memory is indexed by the customer's words (`key_of`), which do not say which
        conversation they are from: with one judge per process, two conversations with the same lines ("hi",
        "yes") shared the judgment, and one's cart (what its advisor offered, its payment link)
        came out in the other. The host builds one per query since Oct 8, 2026; memory
        still serves what it is for, that `before` and `after` of the same turn do not pay twice.
        There is no need to close it: the client belongs to the judge it came from. `cart` is the lines of
        this query's deal, if one arrived.
        """
        return type(self)(self._client, self._model, keep=self._keep, cart=cart)

    @classmethod
    def from_env(cls, model: Provider) -> QuestionJudge | None:
        """The gates if `TYPESAFE_API_KEY` is in the environment; if not, `None`."""
        client = Client.from_env()
        return cls(client, model) if client is not None else None

    @property
    def calls(self) -> int:
        return self._client.calls

    @property
    def tokens(self) -> int:
        return self._client.tokens

    @property
    def cost(self) -> float:
        return self._client.cost

    def last(self, question: str, history: History) -> Judgment | None:
        """The judgment already made for that turn, if it is in memory. Does not go to the network. It is for the eval."""
        return self._done.get(key_of(question, history))

    def read(self, seen: Log) -> Judgment | None:
        """The judgment of the turn in `seen`, if it is in memory. Does not go to the network. It is for the trace."""
        return self._done.get(customer_words(seen))

    def last_reply(self, question: str, history: History) -> Answered | None:
        """What was judged about that turn's answer, if it was judged. Does not go to the network. It is for `Answer.rules`."""
        return self._replies.get(key_of(question, history))

    def last_case(self, question: str, history: History) -> TurnCase | None:
        """That turn's case, or the error if there was none, if it was asked. Does not go to the network. It is for `Answer.rules`."""
        return self._turn_cases.get(key_of(question, history))

    def case_of(self, seen: Log) -> TurnCase | None:
        """The case the writer read on this turn, if it was asked. Does not go to the network. It is for the guardian."""
        return self._turn_cases.get(customer_words(seen))

    def _keep_last(self, memo: OrderedDict[Any, Any], key: Any, value: Any) -> None:
        """Keeps `value` in `memo` as the most recent, without exceeding `keep`."""
        memo[key] = value
        memo.move_to_end(key)
        while len(memo) > self._keep:
            memo.popitem(last=False)

    async def __call__(self, seen: Log, names: frozenset[str]) -> dict[str, float]:
        """`Judge`: the probability of each requested name that is in `STATE_QUESTIONS`, `ORDER_GATES` or `REPLY_QUESTIONS`. No judgment, `JudgeError`."""
        out: dict[str, float] = {}
        asked = frozenset(n for n in names if n in STATE_QUESTIONS or n in LABEL_GATES)
        ordered = frozenset(n for n in names if n in ORDER_GATES)
        if asked or ordered:
            judgment = await self._judge(customer_words(seen), seen, asked or frozenset(STATE_QUESTIONS))
            if judgment.error:
                raise JudgeError(judgment.error)
            out.update({n: judgment.p[n] for n in asked if n in judgment.p})
            out.update({n: 1.0 if ORDER_GATES[n](judgment.order) else 0.0 for n in ordered})
        wanted = frozenset(n for n in names if n in REPLY_QUESTIONS)
        if wanted:
            read = await self._answers(seen)
            out.update({n: read.p.get(n, 0.0) for n in wanted})
        return out

    async def label(self, seen: Log, name: str) -> str:
        """The label a `choice` of `HANDOFF_REASON_QUESTIONS` puts on the turn's answer. It comes from the same request as the noul.

        It is not a `Judge`: a label is not a probability. The escalation
        verdict (`roles/human_handoff.py`) asks for it after the noul
        passed the threshold, so the turn's memory already has it and does not go back to
        the network. No answer to label is an error and not a default
        label: nobody has to guess what an escalation is about.
        """
        if name not in HANDOFF_REASON_QUESTIONS:
            raise JudgeError(f"nobody answers `{name}`")
        read = await self._answers(seen)
        if name not in read.labels:
            raise JudgeError(f"no answer to label: `{name}` is about what the advisor answered")
        return read.labels[name]

    async def order(self, seen: Log) -> tuple[Item, ...]:
        """The turn's order, from the same judgment as the gates. No judgment, `JudgeError`.

        It asks for the judgment even if the sale has no open gates: with everything
        closed nobody would compact, and the order would stop following a customer
        who adds a product after giving the invoice. If the sale already
        asked for it, it comes from memory.
        """
        judgment = await self._judge(customer_words(seen), seen, frozenset(STATE_QUESTIONS))
        if judgment.error:
            raise JudgeError(judgment.error)
        return judgment.order

    async def state(self, seen: Log) -> dict[str, Any]:
        """The turn's compacted state, from the same judgment as the gates. No judgment, `JudgeError`."""
        judgment = await self._judge(customer_words(seen), seen, frozenset(STATE_QUESTIONS))
        if judgment.error:
            raise JudgeError(judgment.error)
        return judgment.state

    async def already(self, seen: Log) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """The turn's already-said and what the customer asks for again, from the same judgment as the gates. No judgment, `JudgeError`."""
        judgment = await self._judge(customer_words(seen), seen, frozenset(STATE_QUESTIONS))
        if judgment.error:
            raise JudgeError(judgment.error)
        return judgment.said, judgment.again

    async def unanswered(self, seen: Log) -> frozenset[str]:
        """The sale's leaves the advisor already asked for and the customer did not answer, from the same judgment. No judgment, `JudgeError`."""
        judgment = await self._judge(customer_words(seen), seen, frozenset(STATE_QUESTIONS))
        if judgment.error:
            raise JudgeError(judgment.error)
        return judgment.unanswered

    async def payment_method(self, seen: Log) -> dict[str, float]:
        """The turn's `payment_method` distribution, from the same judgment as the gates. No judgment, `JudgeError`."""
        judgment = await self._judge(customer_words(seen), seen, frozenset(STATE_QUESTIONS))
        if judgment.error:
            raise JudgeError(judgment.error)
        return dict(judgment.dist.get(PAYMENT_METHOD, {}))

    def known_order(self, seen: Log) -> tuple[Item, ...]:
        """The turn's order if it was already judged, without going to the network; empty if not. It is for the resolvers, which do not wait."""
        done = self._done.get(customer_words(seen))
        return done.order if done is not None and not done.error else ()

    async def _answers(self, seen: Log) -> Answered:
        """Everything asked about the turn's answer, in one request, memoized by its text.

        The noul of `REPLY_QUESTIONS` and the labels of `HANDOFF_REASON_QUESTIONS` together, for the same reason
        `_read` asks for all of `SALE_QUESTIONS`: they are independent over the
        same conversation and the conversation is what is charged. That way the sale and the escalation
        are one request per turn and not two. With no answer (the sale of `before`,
        or a turn that went down) it returns empty without going to the network, and whoever
        asks reads 0.0: this turn has not answered yet, it closes nothing and escalates
        nothing. Until Sep 22, 2026 this was `_recommended`
        and asked a single question.
        """
        answer = answer_of(seen)
        if not answer:
            return EMPTY
        if (read := self._answered.get(answer)) is not None:
            self._answered.move_to_end(answer)
            self._keep_last(self._replies, customer_words(seen), read)
            return read
        question, history = conversation(seen)
        state = {"customer": [q for q, _ in history] + [question], "last_message": question, "advisor": answer}
        try:
            reply_reading = await self._client.ask(state, {**REPLY_QUESTIONS, **HANDOFF_REASON_QUESTIONS})
            labels = {n: reply_reading.choice(n) for n in HANDOFF_REASON_QUESTIONS}
            read = Answered(
                p={n: round(reply_reading.noul(n), 2) for n in REPLY_QUESTIONS},
                labels=labels,
                label_p=chosen_p(reply_reading, labels),
            )
        except Exception as e:
            self.errors += 1
            raise JudgeError(f"reading the answer: {type(e).__name__}: {e}") from e
        self._keep_last(self._answered, answer, read)
        self._keep_last(self._replies, customer_words(seen), read)
        return read

    async def turn_case(self, seen: Log, report: str) -> str:
        """The turn's case (`TURN_CASES`), from the question and the searcher's report, memoized. No judgment, `JudgeError`.

        What came out, or the error, stays per turn for `last_case`: without it nobody knew which
        line the writer received, or that it received all four because the judge went down.
        """
        question = conversation(seen)[0]
        key, turn = (question, report), customer_words(seen)
        if (read := self._cases.get(key)) is None:
            try:
                reading = await self._client.ask({"last_message": question, "report": report}, TURN_CASE_QUESTIONS)
                case = reading.choice(TURN_CASE)
            except Exception as e:
                self.errors += 1
                self._keep_last(self._turn_cases, turn, TurnCase("", {}, error=f"{type(e).__name__}: {e}"))
                raise JudgeError(f"reading the case: {type(e).__name__}: {e}") from e
            read = TurnCase(case, distribution(reading, TURN_CASE))
        self._keep_last(self._cases, key, read)
        self._keep_last(self._turn_cases, turn, read)
        return read.case

    async def _judge(self, key: str, seen: Log, asked: frozenset[str]) -> Judgment:
        """The turn's judgment with at least `asked` answered: memory, or compact and read. Never raises.

        Two requests for the same turn at once share the compaction: the
        second waits for the first's future and then asks for what it is missing.
        """
        while (pending := self._pending.get(key)) is not None:
            await pending
        done = self._done.get(key)
        if done is not None:
            self._done.move_to_end(key)
            missing = asked - done.p.keys()
            if done.error or not missing:
                return done
        future: asyncio.Future[Judgment] = asyncio.get_running_loop().create_future()
        self._pending[key] = future
        try:
            judgment = await self._read(done, seen, asked)
        except BaseException as e:
            future.set_exception(e)
            raise
        finally:
            del self._pending[key]
        future.set_result(judgment)
        self._done[key] = judgment
        while len(self._done) > self._keep:
            self._done.popitem(last=False)
        return judgment

    async def _read(self, done: Judgment | None, seen: Log, asked: frozenset[str]) -> Judgment:
        """Compacts if needed and asks TypeSafe everything of `STATE_QUESTIONS` and `SALE_LABELS` that is missing.

        The gates of `LABEL_GATES` come from their label's distribution, in the same request.

        Everything, and not only what is missing from `asked`: the questions are independent
        over the same conversation, go in parallel in one request, and what is
        charged is the conversation. That way the turn's second cell (`propose_effects` after
        `close_steps`) finds its own in memory and does not pay for the state again.
        Until Sep 21, 2026 it asked only for `asked`, when `close_steps`
        was the only one asking.
        """
        if done is None:
            question, history = since_sale(seen)
            try:
                (state, spent), (items, carted), (said, again, unanswered, recalled) = await asyncio.gather(
                    compact(self._model, question, history),
                    cart(self._model, question, history, self.cart),
                    said_before(self._model, question, history),
                )
            except Exception as e:
                self.errors += 1
                return Judgment({}, {}, error=f"compacting: {type(e).__name__}: {e}")
            spent += carted + recalled
            self.model_tokens += spent
            state.pop(CART, None)
            named, read, products = await self._products(items)
            order, picked, presentations = await self._presentations(price_order(items, named=named))
            order = remember(order, quoted(seen))
            picks = {k: v for k, v in ((PRODUCT, products), (PRESENTATION, presentations)) if v}
            done = Judgment(state, {}, spent=spent, tokens=read + picked, order=order, said=said, again=again, unanswered=unanswered, picks=picks)
        missing = sorted(STATE_QUESTIONS.keys() - done.p.keys())
        unlabeled = sorted(SALE_LABELS.keys() - done.labels.keys())
        try:
            state_reading = await self._client.ask(
                spoken(seen),
                {**{n: STATE_QUESTIONS[n] for n in missing}, **{n: SALE_LABELS[n] for n in unlabeled}},
            )
            p = {n: round(state_reading.noul(n), 2) for n in missing}
            labels = {n: state_reading.choice(n) for n in unlabeled}
            dists = {n: distribution(state_reading, n) for n in unlabeled}
            for gate, (label, options) in LABEL_GATES.items():
                if label in unlabeled:
                    dist = state_reading.probabilities(label)
                    p[gate] = round(min(1.0, sum(dist.get(o, 0.0) for o in options)), 2)
        except Exception as e:
            self.errors += 1
            return replace(done, p={}, error=f"reading: {type(e).__name__}: {e}")
        done = replace(
            done,
            p={**done.p, **p},
            labels={**done.labels, **labels},
            dist={**done.dist, **dists},
            tokens=done.tokens + state_reading.tokens,
        )
        return replace(done, order=()) if done.reset else done

    async def _products(self, raw: object) -> tuple[dict[str, str], int, tuple[Pick, ...]]:
        """For each cart name that is not a title as it stands, the title the judge chose, what it cost and each pick with its p.

        A name the judge reads as several or none does not go in: the line stays without a datasheet.
        A downed judge leaves the name without a datasheet, and it is counted in `errors`.
        """
        found = sheets()
        names = [n for n in said_products(raw) if n and titled(n, found) is None]
        if not names:
            return {}, 0, ()
        titles = tuple(t for t, _ in found)
        question = product_question(titles)
        readings = await asyncio.gather(*(self._client.ask({"product": n}, question) for n in names), return_exceptions=True)
        named: dict[str, str] = {}
        picks: list[Pick] = []
        tokens = 0
        for n, reading in zip(names, readings):
            if isinstance(reading, BaseException):
                self.errors += 1
                continue
            tokens += reading.tokens
            try:
                option = reading.choice(PRODUCT)
            except TypeSafeError:
                self.errors += 1
                continue
            k = int(option[1:]) - 1 if option[:1] == "f" and option[1:].isdigit() else -1
            if 0 <= k < len(titles):
                named[n] = titles[k]
            picks.append(Pick(n, titles[k] if 0 <= k < len(titles) else option, distribution(reading, PRODUCT).get(option)))
        return named, tokens, tuple(picks)

    async def _presentations(self, items: tuple[Item, ...]) -> tuple[tuple[Item, ...], int, tuple[Pick, ...]]:
        """The order with the presentation the judge chose in each line that needs it, what it cost and each pick with its p.

        The one that needs it has a product, several presentations and something said that is not one of
        them as it stands. With nothing said it is not asked: it stays unchosen and the order asks for it. A
        downed judge leaves the line as it was, and it is counted in `errors`.
        """
        asks = [i for i in items if i.options and i.said_presentation and i.sold]
        if not asks:
            return items, 0, ()
        readings = await asyncio.gather(
            *(
                self._client.ask(
                    {"product": i.product, "asked": {"presentation": i.said_presentation, "quantity": i.quantity}},
                    presentation_question(i.options),
                )
                for i in asks
            ),
            return_exceptions=True,
        )
        chosen: dict[int, Item] = {}
        picks: list[Pick] = []
        tokens = 0
        for i, reading in zip(asks, readings):
            if isinstance(reading, BaseException):
                self.errors += 1
                continue
            tokens += reading.tokens
            try:
                option = reading.choice(PRESENTATION)
            except TypeSafeError:
                self.errors += 1
                continue
            n = int(option[1:]) - 1 if option[:1] == "p" and option[1:].isdigit() else -1
            label = i.options[n] if 0 <= n < len(i.options) else option
            chosen[id(i)] = choose(i, label)
            picks.append(Pick(f"{i.product}: {i.said_presentation}", label, distribution(reading, PRESENTATION).get(option)))
        return tuple(chosen.get(id(i), i) for i in items), tokens, tuple(picks)

    async def aclose(self) -> None:
        """Closes the TypeSafe client. The model belongs to whoever passed it."""
        await self._client.aclose()


def judge(question_judge: QuestionJudge | None, *more: Judge) -> Judge:
    """The sale's judge: the turn's four facts, the code ones that come in `more` and, if there are any, the network's.

    The facts go first because they cost nothing and do not fail; the network one
    answers what remains. `more` is the form's (`Forms.judge`, `complete_invoice`).
    Without `question_judge` (without `TYPESAFE_API_KEY`) the names of
    `SALE_QUESTIONS` and `REPLY_QUESTIONS` stay unanswered and `close_steps` says so on every
    run: the sale without judgment is not a sale with regexes, it is a sale that warns.
    """
    return chain(facts(LOG_FACTS), *more, *((question_judge,) if question_judge is not None else ()))
