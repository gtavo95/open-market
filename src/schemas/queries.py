"""The `/queries` contract: what the client sends and what it receives.

What comes in (`Incoming`: `Query` and what it carries inside) ignores the fields it does not
know and warns about them with a WARNING. Until Oct 9, 2026 it was `extra="forbid"`, so that a
misspelled field would be a 422; that day knowledge resent the `form` that #6 had started returning and
every second turn of the customer came out 422 (agro-00120): the agent stopped answering.
What goes out (`*Out`) is what `/docs` shows. The handlers are in
`routes/queries.py`.
"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

log = logging.getLogger(__name__)


class Incoming(BaseModel):
    """A model of what comes in: what it does not know is ignored and warned about, it is not a 422."""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _warn_about_unknown(cls, data: Any) -> Any:
        if isinstance(data, dict) and (unknown := sorted(set(data) - set(cls.model_fields))):
            log.warning("/queries: %s brings fields agro does not know and ignores: %s", cls.__name__, ", ".join(map(str, unknown)))
        return data


class TurnIn(Incoming):
    question: str
    answer: str


class OpIn(Incoming):
    """A move of the sale's plan, as it came out in `sale.ops` of the previous turn.

    They are the fields of `PlanOp` (with `parent` on the wire for its `padre`); any other (`state` where `status` goes) is ignored with a WARNING.
    Only `verb` is required; the rest go if they have a value.
    """
    verb: str = Field(min_length=1)
    id: str = ""
    intent: str = ""
    status: str = ""
    done_when: str = ""
    parent: str = ""


class EffectIn(Incoming):
    """A move on the effects, as it came out in `effects.ops` of the previous turn.

    They are the fields of `EffectOp` and nothing more. The ones the client writes on its
    side are `done` and `reject` on an id that came out in `pending`, with the
    reason or the send's reference in `note`; `propose` and `resolve` are emitted by
    the advisor and sent back as they are.
    """


    verb: str = Field(min_length=1)
    id: str = ""
    kind: str = ""
    args: list[list[str]] = Field(default_factory=list)
    note: str = ""


class MessageIn(Incoming):
    """A message of the memory's log, exactly as it was said. `i` is its position in the contact's log."""


    i: int = Field(ge=0)
    kind: str = Field(min_length=1, examples=["customer"])
    text: str = Field(max_length=32000)
    date: str = Field(default="", examples=["2026-06-02T15:04:00-06:00"])


class NodeIn(Incoming):
    """A node already built in the summary tree: `(l, i)` covers the messages `[i·2^l, (i+1)·2^l)`."""


    l: int = Field(ge=0)  # noqa: E741 — the spec's `l`, the level
    i: int = Field(ge=0)
    text: str = Field(max_length=4000)


class MemoryIn(Incoming):
    """The customer's memory between sessions, as whoever carries the conversation keeps it.

    The two flows of the OptChat spec: the log and the built nodes of the tree. The view does not
    travel: the agent folds it from the tree. It is read and does not come back (see `host/memory.py`).
    """


    messages: list[MessageIn] = Field(default_factory=list, max_length=20000)
    tree: list[NodeIn] = Field(default_factory=list, max_length=40000)


class ItemDealIn(Incoming):
    """A line of the deal's cart, with the prices knowledge already charged. Empty `sku` if the datasheet has no code."""


    sku: str | None = None
    product: str
    presentation: str = ""
    quantity: float
    price: float | None = None
    subtotal: float | None = None


class FormDealIn(Incoming):
    """The deal's form: the ids are the bundle's (`forms/`). agro recomputes `missing`."""


    fields: dict[str, str] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)


class LinkDealIn(Incoming):

    url: str
    active: bool
    expires_at: str | None = None


class PaymentDealIn(Incoming):

    link: LinkDealIn | None = None
    paid: bool = False
    paid_at: str | None = None


class QuoteDealIn(Incoming):

    slot_id: str
    at: str


class EffectDealIn(Incoming):

    id: str
    kind: str
    status: str


class DealIn(Incoming):
    """The customer's open deal, as knowledge keeps it (deals doc, phase 3).

    For now it comes in and is not used: it is accepted so a route can send it without a 422.
    `version` is the order's CAS and will come back in `changes.base`; `from_turn` is the index in
    `history` of this deal's first turn, `null` if it started before the window.
    """


    id: str = Field(min_length=1)
    kind: Literal["sale", "quote"]
    stage: Literal["open", "in_payment", "won", "lost", "cancelled"]
    version: int = Field(ge=0)
    number: int | None = None
    from_turn: int | None = Field(default=None, ge=0)
    items: list[ItemDealIn] = Field(default_factory=list, max_length=200)
    total: float | None = None
    currency: str = ""
    form: FormDealIn | None = None
    payment: PaymentDealIn | None = None
    quote: QuoteDealIn | None = None
    effects: list[EffectDealIn] = Field(default_factory=list, max_length=200)
    opened_at: str | None = None
    updated_at: str | None = None


class AddressIn(Incoming):

    label: str = ""
    address: str


class CustomerIn(Incoming):
    """What remains of the customer from won deals: a suggestion the agent confirms, never a given fact."""


    name: str | None = None
    nit: str | None = None
    legal_name: str | None = None
    addresses: list[AddressIn] = Field(default_factory=list, max_length=50)
    email: str | None = None
    phone: str | None = None


class Query(Incoming):
    question: str = Field(min_length=1, max_length=32000, examples=["what do I use for thrips on tomato?"])
    history: list[TurnIn] = Field(default_factory=list, max_length=20)
    sale: list[OpIn] | None = Field(default=None, max_length=200)
    effects: list[EffectIn] | None = Field(default=None, max_length=200)
    payment: Literal["paid", "pending"] | None = None
    memory: MemoryIn | None = None
    deal: DealIn | None = None
    customer: CustomerIn | None = None
    resumption: bool = False
    interview: Any = None
    form: Any = None

    @model_validator(mode="after")
    def _deal_within_history(self) -> "Query":
        """`from_turn` equal to the length of the history is a deal that opens with this question."""
        if self.deal and self.deal.from_turn is not None and self.deal.from_turn > len(self.history):
            raise ValueError("deal.from_turn falls after the history")
        return self

    @model_validator(mode="before")
    @classmethod
    def _without_old_sale(cls, data: Any) -> Any:
        """A sale saved before Sep 23, 2026 (1f73bab) is thrown away and rebuilt from the history.

        Those moves bring `completes_when` instead of `done_when`, and also the leaf
        `doubts` (today `decision`) and `said_area` (today `said_quantity`): translating the
        key would leave a plan with conditions no judge answers. The channel
        keeps each conversation's sale, so a customer returning
        after the change got a 422 and nobody answered them. Without a sale it is
        the sale's first turn, which gets rebuilt with what the history says.
        Any other unknown key is still a 422.
        """
        if isinstance(data, dict) and isinstance(data.get("sale"), list):
            if any(isinstance(op, dict) and "completes_when" in op for op in data["sale"]):
                return {**data, "sale": None}
        return data

    @field_validator("question")
    @classmethod
    def _with_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("the question is blank")
        return v.strip()


FieldType = Literal["text", "textarea", "select", "checkbox", "email", "tel"]
"""The `type`s of `# Fields`: a closed list, the one the webapp knows how to draw (the same as stemcell)."""


class FieldOut(BaseModel):
    """The definition of a field of `forms/billing.md`, read-only.

    `position` is the place in which the advisor asks it; `options`, the values of a list (`payment_method`).
    """
    id: str
    label: str
    type: FieldType
    required: bool
    options: list[str]
    position: int | None


class FormOut(BaseModel):
    """The billing details after the turn. `fields` is what is kept and sent back; the rest is read.

    `fields` are the ones the customer gave, in their words, and `payment_method` is `link` or
    `transfer`. They carry over: a turn only changes what the customer gave or corrected. `missing`
    are the empty required ones, in the order they get asked; `form_schema`, the definition of each field
    to draw the card; `title`, its heading (the `title` of `forms/billing.md`). It does not go to the
    SAP draft from here: that goes in the args of `sap_draft`.
    """

    title: str = ""
    fields: dict[str, str]
    missing: list[str]
    form_schema: list[FieldOut]


class AskOut(BaseModel):
    id: str
    what: str


class SaleOut(BaseModel):
    """The sale after the turn. `ops` is what is kept and sent back; the rest is read.

    `state` is one line ("sale 3/8: next `quantity`"); `stage` and `active` are
    the root stage and the leaf that are open; `asks` is what has to be asked of the customer
    now, or `null` if what follows is done by the advisor; `pending` and `closed_steps`
    are the leaves; `tree` is the drawn checklist; `closed` means nothing is left
    open. `judgment` is what the gates saw this turn: `state`,
    the JSON the model wrote with the customer's words; `p`, the
    probability per gate (it closes with `p >= 0.8`); `labels`, how they said they
    pay (`payment_method`) and what they asked about the payment (`payment_request`); `order`, the products, presentations and quantities the model noted
    set against the catalog, with price and total when everything appears (in shadow:
    nothing reads it yet); `error` if there was no judgment. It is for reading why the sale asked for what it asked for; it is not sent back.
    """

    ops: list[dict[str, Any]]
    state: str
    stage: str
    active: str
    asks: AskOut | None
    pending: list[str]
    closed_steps: list[str]
    tree: str
    closed: bool
    judgment: dict[str, Any] | None = None


class PendingOut(BaseModel):
    """A send the advisor proposed and that has to be done with this message.

    `kind` is what it is: `document` the datasheet, `bank_account` the account,
    `payment_link` the payment link, `sap_draft` the draft of the order in SAP.
    `args` are the pairs the turn completed
    (for the datasheet, one `["path", ...]` for each one the answer cited; for
    the link, one `["item", "<json>"]` per line with `line`, `product`,
    `presentation`, whole `quantity`, `price`, `subtotal` and `item_code` (the SAP
    code, empty if the datasheet does not have it), plus `["currency", "GTQ"]` and `["total", "550.00"]`,
    with the datasheet's prices; for the draft, the same plus `nit`, `name`,
    `recipient`, `phone`, `address` and `payment_method`, from the form: `name` is the legal name). `executable` false means it lacks the args
    it needs, and then what gets sent back is a `reject`, not a `done`.
    """

    id: str
    kind: str
    args: list[list[str]]
    executable: bool


class EffectsOut(BaseModel):
    """The effects after the turn. `ops` is what is kept and sent back; `pending` is what has to be done.

    `state` is one line with each effect and how it ended up, for logs. The `done` or
    the `reject` of a pending one is seeded by whoever executed it, in `effects` of the
    next request: this service sends nothing.
    """

    ops: list[dict[str, Any]]
    pending: list[PendingOut]
    state: str


class LineOut(BaseModel):
    """A choice of the judge on a line of the cart: what the customer said, what stayed, and its p."""

    said: str
    option: str
    p: float | None


class RuleOut(BaseModel):
    """What a `governance/` rule read in the turn (`host/rules.py`).

    `p` is null if it was not asked this turn; `threshold` is a number, `argmax`, or null in
    a code rule; `option` is the one a `choice` without options in the question picked;
    `lines`, the choices of a `choice` per line of the cart (the datasheet, the presentation).
    """

    id: str
    p: float | None
    threshold: float | str | None
    fired: bool
    action: str
    option: str | None = None
    lines: list[LineOut] | None = None


class ItemChangeOut(BaseModel):
    """A change to a line of the deal's cart. `change` and `remove` identify it by `sku`, or by `product` and `presentation` if there is none."""

    op: Literal["add", "change", "remove"]
    sku: str | None = None
    product: str
    presentation: str = ""
    quantity: float | None = None
    price: float | None = None


class ChangesOut(BaseModel):
    """What the turn changed in the deal, as deltas: what is not mentioned does not change.

    `base` is the `deal.version` that was read: if knowledge already has another, the delta was computed
    on another cart and is not applied. `form` brings a new or corrected value, or `null` if it was
    removed. `deal` is `clear` if the customer asked to start over.
    """

    base: int
    items: list[ItemChangeOut] = []
    form: dict[str, str | None] = {}
    deal: Literal["clear"] | None = None


class AnswerOut(BaseModel):
    answer: str
    messages: list[str]
    sources: list[str]
    grounded: bool
    tokens: int
    tokens_input: int = 0
    tokens_cached: int = 0
    tokens_output: int = 0
    tokens_typesafe: int = 0
    turns: int
    halt: bool
    fails: list[str]
    seconds: float
    truncated: bool
    no_search_terms: bool
    sale: SaleOut
    effects: EffectsOut
    form: FormOut
    restart: bool = False
    changes: ChangesOut | None = None
    rules: list[RuleOut] = []


class ModelOut(BaseModel):
    """The adapter's count since the process started, if it keeps one (OpenAI yes, Gemini no).

    `attempts` minus `calls` is the POSTs that did not come back with a body: 503s,
    network cuts, httpx timeouts. `slowest` is the longest attempt, in
    seconds: near the httpx `timeout` with extra attempts it is the API
    hanging, not the model thinking. It is what makes a hang visible without
    opening the logs.
    """

    calls: int
    attempts: int
    seconds: float
    slowest: float


class CatalogOut(BaseModel):
    datasheets: int
    kb: int
    tokens_approx: int
    free_slots: int
    model: ModelOut | None = None


class FailedTurnOut(BaseModel):
    """A turn that did not answer (500, 502, 504): the reason and what it managed to charge, which is billed anyway."""

    detail: str
    tokens: int
    tokens_input: int
    tokens_cached: int
    tokens_output: int
    tokens_typesafe: int
