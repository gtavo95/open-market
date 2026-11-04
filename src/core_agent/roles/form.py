"""The role that keeps the billing form: it fills it with what the customer said and handles what they ask about their purchase.

    orchestrate([searcher], writer, before=[sale, order, form, effects, ...], after=[sale, ...])

`Forms` is a conversation's form (`latest`), seeded with the one the host sends, and its
cell runs on the way in, after the order and before the effects, because the SAP draft
reads what it noted. With the same judgment of the turn it decides three things, each by threshold:

- `gives_billing_data`: the model reads what is noted and the conversation and writes only what changes
  (`world/form.py`). The other turns do not pay for it, and what is noted does not move.
- `asks_to_start_over`: the form stays empty and `reset` true, which the host returns
  as `restart`; the judge already emptied the order (`Judgment.reset`).
- `asks_for_order_summary`: the writer receives the `form` report, with what is noted and what
  is missing, and the summary line. The same, with the return line, if the host reported that the
  conversation resumed (`resumed`).

The model does not note `payment_method`: it is the option of the `payment_method` label that passes the threshold,
if it is one of the field's. That way the form and the sale's `method` step read the same.

`complete_invoice` (`BILLED`) is a code judge over `latest`: 1.0 if no required field is missing.
It closes the `data` leaf and the SAP draft requires it.

What it costs: nothing not already paid, except a short call to the model on the turns in which the
customer gives or corrects a piece of data. If the judge or the model fail, the form stays as it was.
"""

from __future__ import annotations

from catalejo.core import Cell, Judge, Log, Report
from catalejo.llm import Provider

from ..prompts.judge import ASKS_RESET, ASKS_SUMMARY, GIVES_DATA
from ..prompts.writer import (
    FORM_ASK,
    FORM_COMPLETE,
    FORM_CONFIRM,
    FORM_HEAD,
    FORM_ITEM,
    FORM_MISSING,
    FORM_NONE,
    FORM_WHO,
    RESET_LINE,
    RESUME_LINE,
    SUMMARY_LINE,
)
from ..world import form as forms
from ..world.form import PAYMENT, Form
from ..world.question_judge import THRESHOLD, JudgeError, QuestionJudge

BILLED = "complete_invoice"
"""That the form has all the required fields of `forms/billing.md`. Code, 1.0 or 0.0, like `ORDER_GATES`."""


def form_text(form: Form) -> str:
    """What is noted, in the form's order, and what is missing, with the bundle's labels."""
    items = [FORM_ITEM.format(label=f.get("label") or f["id"], value=form[f["id"]]) for f in forms.fields() if f["id"] in form]
    left = forms.missing(form)
    tail = FORM_MISSING.format(fields=", ".join(forms.label(k) for k in left)) if left else FORM_COMPLETE
    return "\n".join([FORM_HEAD, *items, tail] if items else [FORM_NONE, tail])


class Forms:
    """A conversation's form: `latest` is the last one, and `cell()` applies each turn's changes to it.

    `latest` starts with what the host sends (`Query.form`, the previous turn's), and
    `previous` with that of the last closed sale (`Query.previous_form`), which does not count until
    the customer confirms it. `reset`
    is whether this turn emptied it; `resumed` is set by the host on the first turn of a conversation
    the host rehydrated. `spent` are the model's tokens and `errors` the turns in which the judge or
    the model failed.
    """

    def __init__(self, seed: Form | None = None, *, resumed: bool = False, previous: Form | None = None) -> None:
        self.latest: Form = forms.check(seed or {})
        self.previous: Form = forms.check(previous or {})
        self.resumed = resumed
        self.reset = False
        self.spent = 0
        self.errors = 0

    def complete(self) -> bool:
        """Whether no required field is missing. With no form in the bundle, never: there is nothing to send SAP."""
        return bool(forms.fields()) and not forms.missing(self.latest)

    def next_ask(self) -> str:
        """What the `data` leaf asks for: the first missing required field, or to confirm those from the previous sale if it is there; empty if nothing is missing.

        `payment_method` is not confirmed: the `method` leaf asks for it.
        """
        left = forms.missing(self.latest)
        if not left:
            return ""
        known = [k for k in left if k in self.previous and k != PAYMENT]
        if left[0] in known:
            return FORM_CONFIRM.format(fields=", ".join(f"{forms.label(k)}: {self.previous[k]}" for k in known))
        return FORM_ASK.format(field=forms.label(left[0]))

    def judge(self) -> Judge:
        """`complete_invoice` over `latest`; it does not answer the other names."""

        async def judge(seen: Log, names: frozenset[str]) -> dict[str, float]:
            return {BILLED: 1.0 if self.complete() else 0.0} if BILLED in names else {}

        return judge

    def cell(self, model: Provider, question_judge: QuestionJudge | None) -> Cell:
        """On the way in: fills, empties or summarizes the form according to the turn's judgment."""

        async def cell(seen: Log) -> Log:
            self.reset = False
            if question_judge is None:
                return Log()
            try:
                p = await question_judge(seen, frozenset({GIVES_DATA, ASKS_SUMMARY, ASKS_RESET}))
                method = await question_judge.payment_method(seen)
            except JudgeError:
                self.errors += 1
                return self._report(RESUME_LINE) if self.resumed else Log()
            if p.get(ASKS_RESET, 0.0) >= THRESHOLD:
                self.latest, self.reset = {}, True
                return self._report(RESET_LINE)
            if p.get(GIVES_DATA, 0.0) >= THRESHOLD:
                try:
                    self.latest, spent = await forms.fill(model, seen, self.latest, self.previous)
                    self.spent += spent
                except Exception:
                    self.errors += 1
            self.latest = {**self.latest, **self._payment(method)}
            if self.resumed:
                return self._report(RESUME_LINE)
            if p.get(ASKS_SUMMARY, 0.0) >= THRESHOLD:
                return self._report(SUMMARY_LINE)
            return Log()

        return cell

    def _payment(self, dist: dict[str, float]) -> Form:
        """`payment_method` with the `payment_method` option that passes the threshold, if it is one of the field's; if none, nothing."""
        options = next((f.get("options", []) for f in forms.fields() if f["id"] == PAYMENT), [])
        chosen = [o for o in options if dist.get(o, 0.0) >= THRESHOLD]
        return {PAYMENT: chosen[0]} if chosen else {}

    def _report(self, line: str) -> Log:
        text = line if line == RESET_LINE else f"{form_text(self.latest)}\n\n{line}"
        return Log(reports=(Report(FORM_WHO, text, is_grounded=True),))
