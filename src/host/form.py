"""The billing form as it travels with the client: the fields that come in, the ones that go out and what is missing.

The form (`core_agent.Forms.latest`, a `dict[str, str]`) belongs to one conversation, and this
service keeps nothing between calls. It travels like the sale: the client sends it with every request
(`Query.form`) and takes back the one from after the turn. Unlike the sale, the one coming in
does rule: the turn only changes what the customer gave or corrected (`world/form.py`).

What comes in goes through `world.form.check`, the same filter as what the model writes: a field
the bundle no longer has, or a `payment_method` outside its options, is silently left out and
is not a 422. This service wrote it in an earlier turn; if the bundle changed between the two,
the conversation goes on and the field gets asked for again.
"""

from __future__ import annotations

from typing import Any

from core_agent.world.form import Form, check, missing, schema, title


def form_from(raw: dict[str, str] | None) -> Form:
    """The fields as they come in the request, filtered by the bundle."""
    return check(raw or {})


def suggestion_from(customer: dict[str, Any] | None) -> Form:
    """What remains of the customer from won deals, as form fields: the advisor confirms it, does not take it as given.

    Keys named the same as a field pass as they are; `addresses` is a list and
    goes whole into `address`, for the advisor to offer them. `name` is not `recipient`: whoever
    receives may be someone else, and that gets asked.
    """
    customer = customer or {}
    raw = {k: v for k, v in customer.items() if isinstance(v, str)}
    places = [d.get("address", "") for d in customer.get("addresses") or [] if d.get("address")]
    if places:
        raw["address"] = " or ".join(places)
    raw.pop("name", None)
    return check(raw)


def form_changes(seed: Form, latest: Form) -> dict[str, str | None]:
    """What the turn changed in the form: a new or corrected value, or `None` if it was removed."""
    changes: dict[str, str | None] = {k: v for k, v in latest.items() if seed.get(k) != v}
    changes.update({k: None for k in seed if k not in latest})
    return changes


def form_to_dict(form: Form) -> dict[str, Any]:
    """The form as JSON: `fields` is what gets returned; `title`, `missing` and `form_schema` are read and do not come back."""
    return {"title": title(), "fields": dict(form), "missing": missing(form), "form_schema": schema()}
