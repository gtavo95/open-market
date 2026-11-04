"""The endpoint that queries the agronomic catalog.

It is stateless: the history, the sale and the effects are sent by the client in the
body. The CLI keeps them in a tuple because there is a single user; here
keeping them on the server side would be inventing sessions for something the client
already has, and on top of that it ties the answer to whichever instance served you. The sale is
the plan's moves (`sale.ops` in the answer) and the effects those of the
`effects` channel (`effects.ops`), which are sent back as they are in the next request; the
rest of both is reading for whoever carries the conversation (see
`host/sale.py` and `host/effects.py`).

`effects.pending` is the only thing in the answer that asks for an action: they are the
sends the advisor proposed and this service cannot make because it does not have
the WhatsApp. Whoever has it sends what each one says and adds a `done` or a
`reject` to `ops` in the next request.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from catalejo.llm import Usage
from auth import authenticated
from config import Settings, get_settings
from schemas.queries import (
    ChangesOut,
    CatalogOut,
    Query,
    DealIn,
    EffectsOut,
    FormOut,
    FailedTurnOut,
    ModelOut,
    RuleOut,
    AnswerOut,
    SaleOut,
)
from host import Advisor, Answer, TurnFailed
from host.memory import memory_from
from host.effects import effects_to_dict
from host.effects import op_from_dict as effect_op_from_dict
from host.effects import summary as effects_summary
from host.deal import item_changes
from host.form import form_changes, form_from, form_to_dict, suggestion_from
from host.sale import op_from_dict, sale_to_dict, summary

router = APIRouter(
    prefix="/queries", tags=["queries"], dependencies=[Depends(authenticated)]
)

TURNS = 6


def advisor(request: Request) -> Advisor:
    a: Advisor | None = getattr(request.app.state, "advisor", None)
    if a is None:
        reason = (
            getattr(request.app.state, "advisor_error", "")
            or "the advisor is not built"
        )
        raise HTTPException(status_code=503, detail=reason)
    return a


def cost_of(r: Answer) -> dict[str, int]:
    """What the turn charged, with the keys of `AnswerOut`."""
    return {
        "tokens": r.tokens,
        "tokens_input": r.tokens_input,
        "tokens_cached": r.tokens_cached,
        "tokens_output": r.tokens_output,
        "tokens_typesafe": r.tokens_typesafe,
    }


def failed(status: int, detail: str, cost: dict[str, int]) -> JSONResponse:
    """A turn that did not answer, with what it charged next to the `detail`: the client bills it anyway."""
    return JSONResponse(status_code=status, content={"detail": detail, **cost})


@router.post(
    "",
    response_model=AnswerOut,
    responses={s: {"model": FailedTurnOut} for s in (500, 502, 504)},
)
async def run_query(
    body: Query,
    a: Advisor = Depends(advisor),
    settings: Settings = Depends(get_settings),
) -> AnswerOut | JSONResponse:

    history = tuple((t.question, t.answer) for t in body.history[-TURNS:])
    deal = body.deal
    since = deal.from_turn if deal else None
    closed = since - 1 - (len(body.history) - len(history)) if since else None
    seed = form_from(deal.form.fields if deal and deal.form else None)
    sale = tuple(op_from_dict(op.model_dump()) for op in body.sale or [])
    effects = tuple(effect_op_from_dict(op.model_dump()) for op in body.effects or [])

    try:
        r = await a.ask(
            body.question,
            history,
            sale=sale,
            effects=effects,
            timeout=settings.timeout_s,
            payment=body.payment or "",
            memory=memory_from(body.memory.model_dump()) if body.memory else (),
            form=seed,
            resumed=body.resumption,
            previous=suggestion_from(body.customer.model_dump() if body.customer else None),
            closed=closed if closed is not None and closed >= 0 else None,
            cart=[i.model_dump() for i in deal.items] if deal else None,
        )
    except TurnFailed as e:
        return failed(500, str(e), e.cost)
    if r.cut_off and not r.text:
        return failed(504, "; ".join(r.fails), cost_of(r))

    if not r.text:
        return failed(502, "; ".join(r.fails) or "the agent ended without answering", cost_of(r))

    return AnswerOut(
        answer=r.text,
        messages=list(r.messages) or [r.text],
        sources=list(r.sources),
        grounded=r.grounded,
        **cost_of(r),
        turns=r.turns,
        halt=r.halt,
        fails=list(r.fails),
        seconds=r.seconds,
        truncated=r.cut_off,
        no_search_terms=r.nothing_to_search,
        sale=SaleOut(**sale_to_dict(summary(r.sale)), judgment=r.judgment),
        effects=EffectsOut(**effects_to_dict(effects_summary(r.effects))),
        form=FormOut(**form_to_dict(r.form)),
        restart=r.reset,
        changes=changes(deal, seed, r) if deal else None,
        rules=[RuleOut(**e) for e in r.rules],
    )


def changes(deal: DealIn, seed: dict[str, str], r: Answer) -> ChangesOut | None:
    """What the turn changed in the deal that came in, or `None` if nothing.

    With `clear` no lines or fields go: knowledge cancels the deal and the next product opens
    another. Without a judgment of the order (`order` at `None`) no lines go: what changed was not read.
    """
    if r.reset:
        return ChangesOut(base=deal.version, deal="clear")
    items = item_changes([i.model_dump() for i in deal.items], r.order) if r.order is not None else []
    form = form_changes(seed, r.form)
    if not items and not form:
        return None
    return ChangesOut(base=deal.version, items=items, form=form)


def model_usage(model: Any) -> ModelOut | None:
    """The adapter's `Usage` as `ModelOut`, or `None` if the model keeps no count."""
    usage = getattr(model, "usage", None)
    if not isinstance(usage, Usage):
        return None
    return ModelOut(
        calls=usage.calls,
        attempts=usage.attempts,
        seconds=round(usage.seconds, 1),
        slowest=round(usage.slowest, 1),
    )


@router.get("/catalog", response_model=CatalogOut)
def catalog(a: Advisor = Depends(advisor)) -> CatalogOut:
    return CatalogOut(
        datasheets=a.sheets,
        kb=len(a.text) // 1000,
        tokens_approx=len(a.text) // 4000 * 1000,
        free_slots=a.free,
        model=model_usage(getattr(a, "model", None)),
    )
