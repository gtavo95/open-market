"""The role that talks to nobody: when the conversation stops being the advisor's.

The advisor is the customer's trusted source. A turn that ends in "that is not
in the datasheet", "we do not have it" or "I cannot confirm that" is not a system
error: it is a conversation left without an owner, and what pays for it is the
advisor's credibility. This role passes it to a person: it asks whether the turn left
the customer without what they asked for, and if the answer is yes it proposes the
`handoff` effect with the reason, so the host opens the case in the queue it
belongs to.

    orchestrate([search_catalog], write_reply, before=[close_sale_steps, capture_effects], after=[close_sale_steps, fill_effect_args, human_handoff])

It goes at the end of the turn, with the answer already written, and that is the only thing it looks at: the
writer's last prose with what the customer said beside it (`REPLY_QUESTIONS`). It does not
talk, does not vote, does not read the catalog. It emits a move in `effects`, the same
channel as the datasheet and the account, so the host receives it where it already receives
everything else and closes it with `done` or `reject` on the next turn.

# What it costs

No call to the model and no new request to TypeSafe. The two questions
about the answer and the reason travel in the same request as `recommended_a_product`
(see `_answers` in `world/question_judge.py`), memoized under the answer's text:
the sale in `after` runs first and pays, and the verdict reads the memory. With
`product` already closed the verdict is what pays, and it is still one request per
turn.

# The yes and the what, separately

`HANDOFF_QUESTIONS` decide WHETHER: three nouls, one per family, against a threshold, and one
is enough. `HANDOFF_REASON` decides WHAT ABOUT, and it is a `choice` among the CRM's reasons. The premise of the
second is stated inside the question ("assuming they need a
person"), so it is always answered, for free, and the code discards it when
the noul did not get there. Why not a single question with a "do not escalate" option is
written in `HANDOFF_REASON_QUESTIONS`: with eighteen options the yes gets split up and the "no" wins with
less than half.

# What the customer sees of the escalation is said by the writer

The datasheet and the account are proposed on the way in, so the writer finds out
before writing and says it in a line (`EFFECT_LINES`). The escalation is not: the
question is about the answer, and the answer does not exist yet when the
writer writes. That is why the `handoff` carries no text for the customer. When
the writer knows it cannot solve something (the catalog does not cover what they asked for) it
says so itself with the fixed phrase in `WRITER`, and
`evals/guardian.py` makes sure that phrase escalates. What the customer asks for and is
known before writing (a complaint, an order already paid, credit) does escalate on the
way in, with `asked_handoff` and the `HANDOFF_ASKED` table, and the writer says it
with the line of its reason. Until Sep 23,
2026 the case carried a `notice` the host sent as a second message, and the
customer read twice that someone was going to attend them.

# One case per conversation

`propose_handoff` skips if the id is already in the channel, proposed, done or rejected
(see `catalejo.rlm.cells.effects`). It is the limit we want: three turns
in a row with no answer are one case, not three. What is left out is the
long conversation in which a person already attended and closed, and the advisor is
left without an answer again much later; that is an id with the turn, and it is the
same next step the datasheet and the account have.
"""

from __future__ import annotations

from catalejo.core import ZERO, Args, Cell, EffectOp, Fail, Log, Report, closed, effects_of, find_effect, find_step, merge, project, proposed
from catalejo.rlm import Verdict, propose_handoff

from ..prompts.judge import HANDOFF_QUESTIONS, HANDOFF_REASON
from ..prompts.writer import HANDOFF_LINES
from ..world.question_judge import THRESHOLD, JudgeError, QuestionJudge

HANDOFF = "handoff"
"""The effect's id and kind. The id is one per conversation; the kind is how the host routes it."""

TAKEOVER = "takeover"
"""The id of the case that switches off the advisor (`TAKEN_OVER`), with the same `handoff` kind.

A separate id because the `HANDOFF` one is one per conversation: with a
`product_not_found` on turn 2, the complaint or the closed sale of turn 6 was not
proposed, the host did not switch off the advisor and the writer had already told the
customer a person was attending them. The host does not look at the id: it processes each proposed `handoff`
(`escalate`). Since Sep 28, 2026.
"""

ORIGIN: tuple[str, str] = ("origin", "requested_by_agent")
"""The origin the CRM puts on what comes out of here, and the only one this turn can emit.

The CRM's other two, payment rejection and document failure, are not escalations
the advisor proposes: they are what the host returns when it `reject`s an effect
it did propose, and they travel in the note of that `reject`. It goes as an argument and not
hard-coded in the host so demo-api stores what the turn said and not what it
assumes.
"""

ESCALATE_THRESHOLD = 0.5
"""From what probability a case is opened to a person. Looser than the sale's, and measured.

It is the only threshold in the house that is loosened, because of an asymmetry worth
having in writing: escalating too much costs someone a minute of reading a
conversation that was fine; escalating too little costs the customer being left
without an answer believing they asked, which is exactly what this role exists to
prevent. The two errors are not worth the same, so the threshold does not go in the
middle.

The number comes from the 16 of Sep 22, 2026 (see `REPLY_QUESTIONS`): the
edges ended up at 0.13 and 0.82, and any cut between the two classifies
all 16 the same. `THRESHOLD`, which is 0.8, also classifies them correctly, and it was not
chosen because it leaves 0.02 of air against the edge that matters: a refusal by
a rule softer than "transfer only" falls below and nobody finds out. 0.5 leaves
the air on the customer's side and is still four times away from the other edge.
"""


CASE_HANDOFF: dict[str, str] = {
    "not_covered": "product_not_found",
    "discontinued": "product_not_found",
    "no_data": "unverifiable_specification",
}
"""The turn's cases (`TURN_CASES`) that escalate, with their CRM reason. The table, like `HANDOFF_ASKED`.

They are the cases in which the judge already decided before writing that the advisor cannot, and the
guardian read it again in the answer. `not_covered` and `no_data` tell the customer it
escalates with an agronomist; `discontinued` says "we do not carry X" and escalates without
saying so. Since Oct 3, 2026 the case escalates by
code and the guardian stays for what the case does not see. `we_do_not_sell` is not here: that it is not sold
is the answer (Sep 28, 2026). None belongs to `TAKEN_OVER`: the advisor goes on.
A case that blew up does not escalate here, because the writer received the four lines and
chose by itself; the guardian reads it.
"""

def verdict(question_judge: QuestionJudge | None) -> Verdict:
    """The host's verdict for `propose_handoff`: the case's args, or `None` if the turn resolved itself.

    First the turn's case: if the writer received the line of a case that escalates
    (`CASE_HANDOFF`), it escalates with that reason without asking anything. If not, the three questions
    and, only if one passed the threshold, the label: the reason is discarded when it does not
    escalate, and it costs nothing because it came in the same request. Without `question_judge`
    (without `TYPESAFE_API_KEY`) it does not return `None`, it raises: a name nobody
    answers has to show as a `Fail` on every run, and not as an advisor
    that never escalates. The same if the judge went down.
    """

    async def look(seen: Log) -> Args | None:
        if question_judge is None:
            raise JudgeError("no judge: nobody answers `HANDOFF_QUESTIONS`, so it never escalates")
        case = question_judge.case_of(seen)
        if case is not None and case.case in CASE_HANDOFF:
            return (ORIGIN, ("reason", CASE_HANDOFF[case.case]))
        answers = await question_judge(seen, frozenset(HANDOFF_QUESTIONS))
        if missing := set(HANDOFF_QUESTIONS) - answers.keys():
            raise JudgeError(f"nobody answers {sorted(missing)}, so it never escalates")
        if max(answers[n] for n in HANDOFF_QUESTIONS) < ESCALATE_THRESHOLD:
            return None
        return (ORIGIN, ("reason", await question_judge.label(seen, HANDOFF_REASON)))

    return look


def human_handoff(question_judge: QuestionJudge | None) -> Cell:
    """`propose_handoff` with the judge's verdict: proposes the `handoff` at the end of the turn, after the sale.

    It skips if the inbound side already proposed the `TAKEOVER` on this turn: the writer said a person
    is attending them, and the guardian read it as one more escalation and opened a
    second case. A `TAKEOVER` already closed on a previous turn does not stop it: if
    a person reactivated the advisor, whatever is left without an answer again is another case.
    """
    propose = propose_handoff(verdict(question_judge), id=HANDOFF, kind=HANDOFF)

    async def cell(seen: Log) -> Log:
        if find_effect(proposed(effects_of(seen.effects)), TAKEOVER) is not None:
            return ZERO
        return await propose(seen)

    return cell


HANDOFF_ASKED: dict[str, str] = {
    "brings_a_complaint": "quality_complaint",
    "asks_for_return": "warranty_return",
    "asks_about_their_order": "quote_not_found",
    "corrects_an_invoice": "billing_data",
    "shipping_outside_guatemala": "out_of_coverage",
    "pays_with_credit_or_check": "card_payment",
}
"""What escalates on the way in: the name to the judge and the CRM reason the case carries. The table, like `EFFECT_RULES`.

They are things the customer asks for that the advisor does not solve no matter how well it
answers: they are known before writing, so the case opens on the way in and the
writer says it with the line of its reason (`HANDOFF_LINES`, in an `escalation` report). What is known
only with the answer (the catalog does not cover it, the datasheet does not bring the data)
stays with the outbound guardian, which skips if this one already proposed on the turn.
The reasons in this table are the ones that switch off the advisor (`TAKEN_OVER`), and that is why
they come only from here.

The questions are in `HANDOFF_ASKS` and travel with the sale, on the same
`state`; credit and check come from the `payment_method` label. With two
above the threshold the highest wins. The threshold is `THRESHOLD`, the sale's and
not the guardian's: on the way in a false yes makes the writer say
something escalates that did not need to, and the guardian stays as a net for what does not pass.

Tested on Sep 25, 2026 against 24 hand-written states, two
rounds, USD 0.003: the twelve that escalate between 0.95 and 1.00 with the correct
reason, the twelve that do not below the threshold ("does Silverstrike really kill fall armyworm?",
"better give me 3 liters", "NIT 1234567-8", "do you deliver to Cobán?", "by card", "I already
paid, when will it reach me in Chimaltenango?"). Discounts are not here: the house does not
give discounts and says so (`voice.md`), it does not check that with anyone.
Before this the writer escalated with an open rule ("what is not
agronomic and is not in the order") that already carried two exceptions.
"""


SOLD = ("decision", "method", "data")
"""The `SESSION` leaves that have to be closed for the sale to be complete. `charge` does not: it never closes."""

SOLD_REASON = "sale_completed"


def sold(seen: Log) -> bool:
    """Whether the sale is complete: they decided, said how they pay and gave the invoice data.

    It is `sale_completed`, and it is code and not a judge: the plan already says what the
    reason says ("already decided what they buy and how much"), closed by the same judge as the
    sale. It escalates only on the turn it goes from open to closed (`sale_closed`).

    It does not require a charge effect: `send_payment_accounts` goes out only if the customer asks for
    the account, and "payment by transfer" does not ask for it. On Sep 28, 2026,
    with that condition, `sale-closed` did not escalate in 0/3: the account never went out and the
    writer pasted it into the text. What is left to charge, the person does.
    """
    plan = project(seen.course)
    steps = [find_step(plan, id) for id in SOLD]
    return all(s is not None and closed(plan, s) for s in steps)


def asked_verdict(question_judge: QuestionJudge | None) -> Verdict:
    """The inbound verdict: the reason of the highest `HANDOFF_ASKED` question above the threshold, or `None`."""

    async def look(seen: Log) -> Args | None:
        if question_judge is None:
            raise JudgeError("no judge: nobody answers `HANDOFF_ASKED`, so it never escalates")
        answers = await question_judge(seen, frozenset(HANDOFF_ASKED))
        hits = [(answers.get(n, 0.0), reason) for n, reason in HANDOFF_ASKED.items()]
        p, reason = max(hits)
        return (ORIGIN, ("reason", reason)) if p >= THRESHOLD else None

    return look


ASKED_WHO = "escalation"
"""The signature of the report that tells the writer what escalates and how to say it."""


def asked_handoff(question_judge: QuestionJudge | None) -> Cell:
    """What the customer asked for, on the way in: the `escalation` report for the writer and, if there is no case, the `handoff`.

    The report goes whenever the question passes the threshold, with the case open or
    not: with one per conversation, the customer who on turn 2 says the
    order was delivered wrong already has their case from turn 1, and with no report the
    writer answered "I do not have that data" (aftersale-shipping:2 and :3, 0/2 on Sep 25,
    2026). The proposal, only if the `TAKEOVER` is not in the
    channel: a guardian `handoff` from a previous turn does not stop it. A verdict that raises is a `Fail` and does not escalate.
    If the sale closed on this turn (`sale_closed`, earlier at the boundary) it does not ask: one case per turn.
    """
    look = asked_verdict(question_judge)

    async def cell(seen: Log) -> Log:
        if find_effect(proposed(effects_of(seen.effects)), TAKEOVER) is not None:
            return ZERO
        try:
            args = await look(seen)
        except Exception as e:
            return Log(fails=(Fail("effects", f"the verdict blew up: {type(e).__name__}: {e}"),))
        if args is None:
            return ZERO
        report = Report(ASKED_WHO, HANDOFF_LINES[dict(args)["reason"]], is_grounded=True)
        if find_effect(effects_of(seen.effects), TAKEOVER) is not None:
            return Log(reports=(report,))
        return Log(effects=(EffectOp("propose", TAKEOVER, HANDOFF, args),), reports=(report,))

    return cell


def sale_closed(sale_steps: Cell) -> Cell:
    """The inbound `close_sale_steps`, and `sale_completed` if with that the sale goes from open to closed.

    It compares the plan the host seeded with the one after closing what the
    customer just said. Until Sep 28, 2026 `sold` looked only at the
    one after, and escalated every turn with the sale already closed: in prod, a
    Raíz Viva sale closed before the deploy, with no `takeover` in the channel, escalated when
    the customer asked the price of Silverstrike, and the writer confirmed the
    old order again. With the `takeover` already set, the `escalation` report went out anyway
    every turn, and after a person reactivated the agent the writer
    kept saying a person was attending them.

    With an earlier `takeover` in the channel (a person already had the case and
    reactivated the agent) it says nothing: the report without the case promises the
    customer a person nobody called.
    """

    async def cell(seen: Log) -> Log:
        out = await sale_steps(seen)
        if sold(seen) or not sold(merge(seen, out)):
            return out
        if find_effect(effects_of(seen.effects), TAKEOVER) is not None:
            return out
        report = Report(ASKED_WHO, HANDOFF_LINES[SOLD_REASON], is_grounded=True)
        args = (ORIGIN, ("reason", SOLD_REASON))
        return merge(out, Log(effects=(EffectOp("propose", TAKEOVER, HANDOFF, args),), reports=(report,)))

    return cell
