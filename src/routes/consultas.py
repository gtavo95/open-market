"""`POST /consultas`: the turn of `/queries`, in the Spanish contract of the host that carries the conversation.

Knowledge (`services/knowledge`, `contrato/` in its repo) speaks Spanish and posts here; the interior
speaks English and stays that way. This route is the edge between them and does no more than that:
`wire.to_english` turns the request into a `Query`, `run_query` (the `/queries` handler, unchanged)
answers it, and `wire.to_wire` turns the `AnswerOut` into a `Respuesta`. The fields knowledge sends that
the interior has no use for (`traza`, `turnId`, `conversationId`, `adjuntos`, `aviso`, `cerrados`) are
accepted and dropped, not a 422.

A turn the host opens with no customer text (a blank `pregunta` with `aviso`, or with a `done`
or a `reject` in `efectos`, as agro's `Consulta._con_texto`) never reaches the advisor: it is
answered 200 with no messages, echoing the sale, the effects and the form as they came.

With `Accept: application/x-ndjson` the answer is a stream of lines (what knowledge asks for, so a long
turn is not read as a dead one): an empty line every `HEARTBEAT` seconds while the turn runs, then
`{"fin": {"status": N, "body": {...}}}` with the status and the body the plain answer would have had.
A stream that ends without `fin` is a 502 for knowledge, so `fin` is always written, also when the turn
failed. The `{"paso": {...}}` lines of the steps are NOT sent: catalejo has no live feed of them yet
(`Live` is not in the catalejo version this service pins), so the console sees the heartbeats and the end.

What the `Respuesta` has that this route does not fill, and why, is said in `answer_of`.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Coroutine
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError

from auth import authenticated
from catalejo.llm import Provider
from config import Settings, get_settings
from core_agent.agent import CLAUDE_THINKING, GEMINI_THINKING, MUSE_THINKING, OPENAI_THINKING
from host import Advisor
from host.effects import effects_to_dict
from host.effects import op_from_dict as effect_op_from_dict
from host.effects import summary as effects_summary
from host.form import form_from, form_to_dict
from host.sale import op_from_dict, sale_to_dict, summary
from routes.queries import advisor, run_query
from schemas.queries import AnswerOut, EffectsOut, FormOut, Query, SaleOut
from wire import to_english, to_wire

log = logging.getLogger(__name__)

router = APIRouter(prefix="/consultas", tags=["consultas"], dependencies=[Depends(authenticated)])

NDJSON = "application/x-ndjson"
HEARTBEAT = 20.0
"""Seconds of silence before an empty line goes out. Knowledge resets a 60 s timer with every line."""

EFFORT = {"muse": MUSE_THINKING, "openai": OPENAI_THINKING, "anthropic": CLAUDE_THINKING, "gemini": GEMINI_THINKING}
"""The effort each provider runs with when `THINKING` is empty: those of `lifespan.agent.provider`."""


def llm_of(model: Provider | None, s: Settings) -> dict[str, str]:
    """Which model answered, as `Respuesta.llm` says it (`provider`, `model`, `effort`, English until `to_wire`).

    The provider and the effort are the service's settings; the model is what the live adapter says it is
    talking to, which is the truth even when `MODEL` is empty and the adapter picked its own default.
    """
    return {
        "provider": s.provider,
        "model": str(getattr(model, "model", "") or s.model),
        "effort": s.thinking or EFFORT.get(s.provider, ""),
    }


def query_of(body: dict[str, Any]) -> Query:
    """The request in the interior's English, or a 422 that names the field the way the interior calls it."""
    try:
        return Query.model_validate(to_english("Query", body))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=json.loads(e.json(include_url=False, include_context=False, include_input=False))) from e


HOST_QUESTION = "host"
"""The `pregunta` a host-opened turn validates with: the turn carries no customer text, so the blank
goes in as this and is never read (only the sale, the effects and the deal are)."""


def host_opened(body: dict[str, Any]) -> bool:
    """Whether the host opened this turn with no customer text: a blank `pregunta` with `aviso`, or
    with a `done` or a `reject` in `efectos`.

    The same condition as agro's `Consulta._con_texto`: the host reporting what it executed, or its
    notice, opens a turn with an empty question. Anything else blank is still a 422, and a missing
    `pregunta` is not blank.
    """
    question = body.get("pregunta")
    if not isinstance(question, str) or question.strip():
        return False
    if body.get("aviso") is not None:
        return True
    effects = body.get("efectos")
    return isinstance(effects, list) and any(isinstance(op, dict) and op.get("verb") in ("done", "reject") for op in effects)


async def empty_answer_of(query: Query, a: Advisor, settings: Settings) -> tuple[int, dict[str, Any]]:
    """The host's turn answered: no customer text in, no messages out, and the advisor never runs.

    The sale, the effects and the form come back as they came (nothing moved: there was no turn),
    with the readings recomputed over them; the tokens are zero and there is no judgment, no rules
    and no changes. `llm` goes as always: it says which model would have answered.
    """
    sale = tuple(op_from_dict(op.model_dump()) for op in query.sale or [])
    effects = tuple(effect_op_from_dict(op.model_dump()) for op in query.effects or [])
    seed = form_from(query.deal.form.fields if query.deal and query.deal.form else None)
    out = AnswerOut(
        answer="",
        messages=[],
        sources=[],
        grounded=False,
        tokens=0,
        tokens_input=0,
        tokens_cached=0,
        tokens_output=0,
        tokens_typesafe=0,
        turns=0,
        halt=False,
        fails=[],
        seconds=0.0,
        truncated=False,
        no_search_terms=False,
        sale=SaleOut(**sale_to_dict(summary(sale))),
        effects=EffectsOut(**effects_to_dict(effects_summary(effects))),
        form=FormOut(**form_to_dict(seed)),
        restart=False,
        changes=None,
        rules=[],
    )
    llm = llm_of(getattr(a, "model", None), settings)
    return 200, to_wire("AnswerOut", {**out.model_dump(mode="json"), "llm": llm})


async def answer_of(query: Query, a: Advisor, settings: Settings) -> tuple[int, dict[str, Any]]:
    """The turn as knowledge reads it: the status and the `Respuesta` (or, when it failed, what it charged).

    A failed turn carries its tokens and the `llm` because knowledge bills it anyway. `modelo` (the
    adapter's counter since the process started, not the turn's), `traza` and `opted_out` are not filled:
    the interior does not keep a per-turn model count or a trace to give, and says nothing about opt-out.
    """
    r = await run_query(query, a, settings)
    llm = llm_of(getattr(a, "model", None), settings)
    if isinstance(r, AnswerOut):
        return 200, to_wire("AnswerOut", {**r.model_dump(mode="json"), "llm": llm})
    failed: dict[str, Any] = {**json.loads(bytes(r.body)), "llm": llm}
    return r.status_code, to_wire("FailedTurnOut", failed)


def line(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False) + "\n"


async def live(turn: Coroutine[Any, Any, tuple[int, dict[str, Any]]]) -> AsyncGenerator[str, None]:
    """The turn as NDJSON: a heartbeat while it runs, then `fin`. The turn is cancelled if the client goes away."""
    work = asyncio.ensure_future(turn)
    try:
        while not work.done():
            done, _ = await asyncio.wait({work}, timeout=HEARTBEAT)
            if not done:
                yield "\n"
        try:
            status, body = work.result()
        except Exception as e:
            log.exception("/consultas: the turn blew up")
            status, body = 500, {"detail": f"{type(e).__name__}: {e}"}
        yield line({"fin": {"status": status, "body": body}})
    finally:
        work.cancel()


@router.post("", response_model=None, responses={s: {"description": "A turn that did not answer, with what it charged."} for s in (500, 502, 504)})
async def consult(
    request: Request,
    body: dict[str, Any] = Body(..., description="Knowledge's `Consulta`."),
    a: Advisor = Depends(advisor),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Knowledge's `Consulta` in, its `Respuesta` out; a stream of lines if it asks for `application/x-ndjson`."""
    if host_opened(body):
        query = query_of({**body, "pregunta": HOST_QUESTION})
        turn = empty_answer_of(query, a, settings)
    else:
        query = query_of(body)
        turn = answer_of(query, a, settings)
    log.info("/consultas: conversation=%s turn=%s", body.get("conversationId", ""), body.get("turnId", ""))
    if NDJSON in request.headers.get("accept", ""):
        return StreamingResponse(live(turn), media_type=NDJSON)
    status, answer = await turn
    return JSONResponse(status_code=status, content=answer)
