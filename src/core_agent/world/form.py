"""The billing form: what the model noted from the conversation, set against `# Fields` by code.

The fields come from the bundle's `forms/billing.md`: id, label, type, whether it is
required, options and position. The form travels with the customer like the sale (`Query.form`)
and is carried turn to turn: the model reads what is noted and writes only what changes
(`FORM_PROMPT`), a value notes or corrects and a null removes. What it does not name stays as it was, so
a NIT given five turns ago does not change just because the model read it differently today.

Until Oct 8, 2026 the invoice was extracted whole from the conversation (`BILLING_PROMPT`)
in the turn in which `said_billing_data` passed the threshold, once per conversation. It is the same
pattern as stemcell's form (`world/form.py` over there), which has asked for changes since Oct 3,
2026 because rewriting it whole lost fields.
"""

from __future__ import annotations

import json
from typing import Any

from catalejo.core import Log, Message, Role
from catalejo.llm import Provider

from ..prompts.judge import FORM_CHANGES, FORM_LINE, FORM_PREVIOUS, FORM_PROMPT
from . import catalog
from .dialogue import since_sale
from .question_judge import parse_state, transcript

Form = dict[str, str]
"""A form: field → value, only those that have a value."""

FILE = ("forms", "billing.md")
"""Where the form is in the bundle."""

PAYMENT = "payment_method"
"""The field the model does not note: it comes from the judge's `payment_method` label (`roles/form.py`)."""


def fields() -> list[dict[str, Any]]:
    """The `fields` of the JSON block in `# Fields`, sorted by `order`; if it is missing or does not parse, empty."""
    path = catalog.BUNDLE.joinpath(*FILE)
    if not path.is_file():
        return []
    text = path.read_text(errors="replace")
    if "\n# Fields" not in text:
        return []
    after = text.split("\n# Fields", 1)[1]
    if after.count("```") < 2:
        return []
    try:
        data = json.loads(after.split("```", 2)[1].removeprefix("json"))
    except json.JSONDecodeError:
        return []
    raw = data.get("fields", []) if isinstance(data, dict) else []
    return sorted((f for f in raw if isinstance(f, dict) and f.get("id")), key=lambda f: f.get("order") or 0)


def title() -> str:
    """The `title` in the form's frontmatter ("Billing details"), or empty with no form."""
    path = catalog.BUNDLE.joinpath(*FILE)
    if not path.is_file():
        return ""
    text = path.read_text(errors="replace")
    head = text[4:].split("\n---\n", 1)[0] if text.startswith("---\n") else ""
    line = next((ln for ln in head.splitlines() if ln.startswith("title:")), "")
    return line.removeprefix("title:").strip().strip('"')


def schema() -> list[dict[str, Any]]:
    """The definition of each field for whoever draws the form: id, label, type, required, options and position."""
    return [
        {
            "id": f["id"],
            "label": f.get("label", ""),
            "type": f.get("type", "text"),
            "required": bool(f.get("required", False)),
            "options": list(f.get("options", [])),
            "position": f.get("order"),
        }
        for f in fields()
    ]


def label(field: str) -> str:
    """The label of a field, or its id if the bundle does not give one."""
    return next((f.get("label") or field for f in fields() if f["id"] == field), field)


def check(raw: object) -> Form:
    """What is valid in a form: only the bundle's fields, with text, and in one with options, one of them.

    It is the filter for what the model writes and for what comes in from the customer: a field the bundle no
    longer has is left out silently, and asked for again if it is required.
    """
    if not isinstance(raw, dict):
        return {}
    allowed = {f["id"]: f for f in fields()}
    out: Form = {}
    for key, value in raw.items():
        if key not in allowed or not isinstance(value, (str, int, float)) or isinstance(value, bool):
            continue
        text = str(value).strip()
        if not text:
            continue
        if allowed[key].get("options") and text not in allowed[key]["options"]:
            continue
        out[key] = text
    return out


def apply(seed: Form, raw: object) -> Form:
    """The form with the changes the model wrote: a value notes or corrects, a null removes. With no changes, the same.

    It does not touch `payment_method`: that is not the model's (see `PAYMENT`).
    """
    if not isinstance(raw, dict):
        return dict(seed)
    raw = {k: v for k, v in raw.items() if k != PAYMENT}
    removed = {k for k, v in raw.items() if v is None}
    return {**{k: v for k, v in seed.items() if k not in removed}, **check({k: v for k, v in raw.items() if v is not None})}


def missing(form: Form) -> list[str]:
    """The required fields the form does not have yet, in the order they are asked for."""
    return [f["id"] for f in fields() if f.get("required") and f["id"] not in form]


def prompt(seed: Form, previous: Form | None = None) -> str:
    """`FORM_PROMPT` with the fields the model notes and what is noted so far; with `previous`, `FORM_PREVIOUS` behind it."""
    lines = "\n".join(FORM_LINE.format(id=f["id"], label=f.get("label", "")) for f in fields() if f["id"] != PAYMENT)
    noted = json.dumps({k: v for k, v in seed.items() if k != PAYMENT}, ensure_ascii=False, indent=1)
    before = {k: v for k, v in (previous or {}).items() if k != PAYMENT and k not in seed}
    tail = FORM_PREVIOUS.format(previous=json.dumps(before, ensure_ascii=False, indent=1)) if before else ""
    return FORM_PROMPT.format(fields=lines, seed=noted) + tail


async def fill(model: Provider, seen: Log, seed: Form, previous: Form | None = None) -> tuple[Form, int]:
    """The form up to this turn: `seed` with the changes the model read (`apply`), and what it cost. One call, no REPL.

    Reads the conversation since the last closed sale (`since_sale`); the data of that sale arrives in
    `previous`, and goes in only if the customer confirms it.
    """
    question, history = since_sale(seen)
    reply = await model.complete((Message(Role.USER, prompt(seed, previous) + transcript(question, history)),))
    return apply(seed, parse_state(reply.message.text).get(FORM_CHANGES)), reply.spent
