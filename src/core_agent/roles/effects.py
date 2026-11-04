"""The role that neither writes nor searches: what the advisor proposes for the host to do.

`EFFECT_RULES` is the table, `propose_effects` proposes on the way in with the same judge as the
sale, `resolve_args` completes on the way out with what the writer cited, and the host
executes outside the turn and seeds `done` or `reject` on the next one. Inside
the turn nothing is sent: an effect executed here would be outside the laws
(`retry` would send it twice, `boundary` would drop the step with the PDF already
sent).

What it costs: no call to the model, and none to the judge the sale has not
already paid for on the same turn.

`host_sim` is the host's rule written once, for the terminal and the evals,
which have nowhere to send anything from. demo-api replaces it with the real
send.
"""

from __future__ import annotations

from catalejo.core import Args, Cell, Effect, EffectOp, Effects, Intent, Log, proposed
from catalejo.rlm import Resolver, propose_effects, existing
from catalejo.rlm import resolve_args

from ..prompts.judge import ASKED_CATALOG, ASKED_ACCOUNT, ASKED_DATASHEET, ASKED_LINK
from ..prompts.writer import EFFECT_LINES, NOT_SENT, REGISTERED, SENT, SENT_WHAT
from ..world.catalog import DATASHEETS
from ..world.facts import answer_of
from ..world.order import payment_args
from ..world.question_judge import THRESHOLD, QuestionJudge, judge
from .form import BILLED, Forms

SAP_DRAFT = "sap_draft"
"""The id of the SAP draft effect."""

DRAFT_KEYS = (("nit", "nit"), ("legal_name", "name"), ("recipient", "recipient"), ("phone", "phone"), ("address", "address"), ("payment_method", "payment_method"))
"""Each form field and its key in the draft's args, in order: the same as before the form."""

EFFECT_RULES: dict[str, Intent] = {
    "send_datasheet": Intent("document", asked=ASKED_DATASHEET),
    "send_payment_accounts": Intent("bank_account", asked=ASKED_ACCOUNT, requires=("wants_to_buy",)),
    "send_catalog": Intent("document", asked=ASKED_CATALOG),
    "send_payment_link": Intent("payment_link", asked=ASKED_LINK, requires=("wants_to_buy", "chargeable_order")),
    SAP_DRAFT: Intent(
        "sap_draft", asked=BILLED, requires=("wants_to_buy", "said_payment_method", "chargeable_order")
    ),
}
"""What the advisor can propose for the host to do, and what it asks the judge to propose it.

The datasheet is proposed if the customer asks for it. The account, if they ask for it and
want to buy: `requires` goes to the same judge, with the same threshold, so the
account does not go out to someone still comparing prices. None carries
customer arguments: the datasheet is resolved with what the writer cited (`resolvers`), and the
host knows the account.

The host's rule, for `cli.py`, `evals/suite.py` and demo-api: a proposed one with a
resolver and no args (the writer cited `none` or ran out of steps) is
`reject` with a note, not `done`; one with no resolver is `done` directly. It is in
`host_sim`, which is what the terminal runs for the host.

The payment link is proposed if the customer pays by link, wants to buy
and the order is chargeable (`chargeable_order`: everything with a price and a whole
quantity). Its args are the order set by code, from the same judgment of the turn
(`payment_args`): one JSON `item` per line, `currency` and `total`. The host builds
the payment order and the link with that; the model never sets the price. Since
Sep 25, 2026.

The catalog is a `document` like the datasheet, so the host sends it by the
same path: it looks in the org's PDF folder for the one named like the arg
(`catalog` gives `catalog.pdf`). It is proposed if the customer asks for it, with no
`requires`: asking for the catalog comes before knowing what they want.

The SAP order draft (`sap_draft`) is proposed when the customer gave the
invoice data, wants to buy, said how they pay (link or transfer) and the order is chargeable;
`complete_invoice` is that the billing form has all the required fields (`roles/form.py`,
since Oct 8, 2026). Its args are those of the link (`payment_args`, with each
line's `item_code`) plus those of the form with the old keys (`DRAFT_KEYS`): `nit`, `name` (the legal
name), `recipient`, `phone`, `address` and `payment_method`. The host secures the payment position and asks
the SAP service for the draft; the customer reads none of this, so it has no line for the
writer. It is proposed once per conversation: a piece of data corrected afterwards is fixed in the
draft, which a person reviews. Since Oct 3, 2026.
"""

SILENT = frozenset({SAP_DRAFT})
"""The effects the customer does not see: no writer line when proposed or when closed."""

CATALOG_PDF = "catalog"
"""The name of the catalog PDF in the org's documents folder, without extension."""

def effect_line(effects: Effects) -> str:
    """What the writer reads of the proposed effects, or empty."""
    return "\n".join(EFFECT_LINES[e.id] for e in effects if e.id in EFFECT_LINES)


def sent_line(effects: Effects) -> str:
    """What the writer reads of the effects the host already closed, or empty.

    A `done` says what went out with what the host returned in `result` (the URL and the
    total of the link, the PDFs that went out), so the writer can answer
    "the link did not reach me" or "how much was it?" without inventing. A `rejected` says only
    that it did not go out: the reason is the host's ("gateway down") and is not for the customer.
    The handoff is not in `SENT_WHAT`: `human_handoff` carries it. Since Sep 28,
    2026, when the fold started keeping `result`. The SAP draft
    is not either, because nothing was sent to the customer: its `done` says the order
    number (`REGISTERED`), in case they ask; with no number or rejected, nothing.
    """
    lines = []
    for e in effects:
        if e.id == SAP_DRAFT:
            number = dict(e.result).get("order") if e.status == "done" else None
            if number:
                lines.append(REGISTERED.format(order=number))
            continue
        what = SENT_WHAT.get(e.id)
        if what is None:
            continue
        if e.status == "done":
            lines.append(SENT.format(what=what, result=_written(e.result)))
        elif e.status == "rejected":
            lines.append(NOT_SENT.format(what=what))
    return "\n".join(lines)


def _written(result: Args) -> str:
    """The host's pairs as the writer reads them: ` (url: https://…, total: 598.08)`, or empty."""
    by_key: dict[str, list[str]] = {}
    for k, v in result:
        by_key.setdefault(k, []).append(v)
    if not by_key:
        return ""
    return " (" + "; ".join(k + ": " + ", ".join(vs) for k, vs in by_key.items()) + ")"


def resolvers(real: frozenset[str], question_judge: QuestionJudge | None = None, form: Forms | None = None) -> dict[str, Resolver]:
    """How each effect's args are completed, with code and from the turn's Log.

    The datasheet is the paths the answer cites that exist (`existing`, the
    same ones `report` verifies), and only those of `DATASHEETS`: the writer also
    cites `company_info/payments.md`, and that is not a datasheet. A bare `citations`
    would return `none` as one more path. The payment link is the order the
    inbound side already judged (`known_order`, without going to the network); with no judge, nothing. The SAP
    draft is that order plus the form (`form.latest`), if it is complete.
    """

    def datasheet(seen: Log) -> Args:
        return tuple(("path", p) for p in existing(answer_of(seen), real) if p.startswith(DATASHEETS))

    def catalog(seen: Log) -> Args:
        return (("path", CATALOG_PDF),)

    def payment(seen: Log) -> Args:
        return payment_args(question_judge.known_order(seen)) if question_judge is not None else ()

    def sap_draft(seen: Log) -> Args:
        if question_judge is None or form is None or not form.complete():
            return ()
        order = payment_args(question_judge.known_order(seen))
        billing = tuple((key, form.latest[field]) for field, key in DRAFT_KEYS if field in form.latest)
        return (*order, *billing) if order else ()

    return {"send_datasheet": datasheet, "send_catalog": catalog, "send_payment_link": payment, SAP_DRAFT: sap_draft}


NEEDS_ARGS = frozenset(resolvers(frozenset()))
"""The effects that do not go out without args: those that have a resolver."""


def capture_effects(question_judge: QuestionJudge | None, form: Forms | None = None) -> Cell:
    """`propose_effects` with the sale's judge and the `EFFECT_RULES` table: proposes on the way in, after `close_sale_steps`.

    It neither talks nor votes. With the judge memoizing the turn and `_read` asking for all
    the questions at once, it adds no requests to the network. Without `question_judge` it warns on every
    run about the names nobody answers, like the sale about its slots.
    """
    more = ((form if form is not None else Forms()).judge(),)
    return propose_effects(judge(question_judge, *more), EFFECT_RULES, umbral=THRESHOLD)


def fill_effect_args(real: frozenset[str], question_judge: QuestionJudge | None = None, form: Forms | None = None) -> Cell:
    """`resolve_args` with the bundle's resolvers: completes on the way out, after the writer."""
    return resolve_args(resolvers(real, question_judge, form))


def host_sim(out: Effects) -> tuple[EffectOp, ...]:
    """What a host does with a turn's proposed effects, without sending anything: the rule of `EFFECT_RULES`.

    It is for the terminal and the evals, which have no WhatsApp: it returns the `done` or
    the `reject` demo-api would seed on the next turn.
    """
    return tuple(
        EffectOp("reject", e.id, note="no args to send")
        if e.id in NEEDS_ARGS and not e.args
        else EffectOp("done", e.id, note="simulated", args=simulated_result(e))
        for e in proposed(out)
    )


SIMULATED_URL = "https://payments.example/simulated"
"""The URL `host_sim` claims to have sent: nobody's, so an eval recognizes it if the writer repeats it."""


def simulated_result(e: Effect) -> Args:
    """What the real host returns with the `done` , invented without sending anything.

    The link: the URL and the order's total. The draft: the order number. The datasheet: one `file` per path, with the
    name of the PDF it would have. The rest returns nothing, like the host.
    """
    if e.id == "send_payment_link":
        return (("url", SIMULATED_URL), *((k, v) for k, v in e.args if k in ("currency", "total")))
    if e.id == SAP_DRAFT:
        return (("order", "simulated"),)
    if e.id == "send_datasheet":
        return tuple(("file", v.rsplit("/", 1)[-1].removesuffix(".md") + ".pdf") for k, v in e.args if k == "path")
    return ()


def effects_state(effects: Effects) -> str:
    """One line for the terminal: each effect with its state and its args."""
    return "; ".join(
        f"{e.id} {e.status}" + (f" ({', '.join(v for _, v in e.args)})" if e.args else "") for e in effects
    ) or "no effects"

