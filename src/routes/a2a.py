"""The advisor spoken over A2A, so another agent can query it.

# Against which contract

It targets the JSON-RPC binding this ecosystem already speaks, the one documented by
`v1/effect/internal/mechanism/CONTRACT.md` and the `platform-webapp` connector:
method `message/send`, blocking, and the `result` is a **Message** (`kind:"message"`,
`role:"agent"`) whose `parts` are the text followed by 0..N `parts` of `kind:"data"`.
The request's `contextId` and `messageId` are echoed without regenerating them.

The public specification has already published a 1.0 with another shape (`SendMessage`,
`ROLE_USER`, `supportedInterfaces`). That is not the one that runs here. Today this route has no
caller: the host calls `POST /queries`. `message/send` was
used by an A2A connector, a legacy system since 2026-09-25.

# What this agent does NOT do

There is no `message/stream` and no `tasks/get`. Both ask for state on the server side
and this service keeps nothing: it answers in 12 to 22 seconds and returns the
whole answer in the same call. Both answer `-32004
UnsupportedOperationError`, which is the code the client can read to
choose another path, and the card declares it with `streaming: false`. If tomorrow
stream is needed, what has to be added first is the task store.

# The bridge with the host's guardrails

When the answer is not grounded, an event goes out in `result.metadata.guardrails`
with the shape `platform-webapp/src/lib/integrations/guardrails.ts` already normalizes.
Without touching a line of the client, the operator sees the alert that this dose did not come
from the catalog.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from catalejo.core import EffectOp, Memory, PlanOp
from auth import authenticated
from config import Settings, get_settings
from host import Advisor, Answer
from host.effects import effects_to_dict
from host.memory import memory_from
from host.effects import ops_from as effect_ops_from
from host.effects import summary as effects_summary
from host.sale import ops_from, sale_to_dict, summary

from .queries import TURNS, advisor

router = APIRouter(tags=["a2a"])

PROTOCOL = "0.3.0"
ROUTE = "/a2a"

PARSE = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL = -32603
UNSUPPORTED_OPERATION = -32004
CONTENT_TYPE_NOT_SUPPORTED = -32005
INVALID_AGENT_RESPONSE = -32006


class RPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _envelope(request_id: Any, result: Any = None, error: RPCError | None = None) -> JSONResponse:
    """The JSON-RPC envelope. Always HTTP 200.

    A JSON-RPC error is not an HTTP error: the transport worked, the
    request arrived, and what failed is inside the body. A client that retries
    by HTTP code goes crazy if you return 500 for a method that does not exist.
    """
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        body["error"] = {"code": error.code, "message": error.message}
        if error.data is not None:
            body["error"]["data"] = error.data
    else:
        body["result"] = result
    return JSONResponse(body)


def _text(parts: list[Any]) -> str:
    """The message's text, joining the text parts.

    It accepts `{"kind":"text","text":...}` and also a bare `{"text":...}`, because
    there are clients that do not send the discriminator, and rejecting for that is fighting
    with whoever wants to talk to you.
    """
    pieces = [
        p["text"]
        for p in parts
        if isinstance(p, dict) and p.get("kind", "text") == "text" and isinstance(p.get("text"), str)
    ]
    return "\n".join(t for t in pieces if t.strip()).strip()


def _datum(key: str, parts: list[Any], metadata: dict[str, Any]) -> Any:
    """A piece of data the client brings: in a `part` of `kind:"data"`, or in `params.metadata`.

    Both ways, in that order, because they are the two forms A2A gives for sending
    something that is not text, and a client that builds the message by hand usually has
    the parts closer at hand. `contextId` is NOT enough for either: it groups the
    conversation on the client's side, and this server has nowhere to look up what
    was said before.
    """
    for p in parts:
        if isinstance(p, dict) and p.get("kind") == "data" and isinstance(p.get("data"), dict):
            if key in p["data"]:
                return p["data"][key]
    return metadata.get(key)


def _history(parts: list[Any], metadata: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """The previous turns, which the client has to bring because they are not kept here."""
    raw = _datum("history", parts, metadata)
    if not isinstance(raw, list):
        return ()
    turns = []
    for t in raw[-TURNS:]:
        if isinstance(t, dict) and isinstance(t.get("question"), str) and isinstance(t.get("answer"), str):
            turns.append((t["question"], t["answer"]))
    return tuple(turns)


def _payment(parts: list[Any], metadata: dict[str, Any]) -> str:
    """The state of the payment link the client looked up (`paid` or `pending`), or empty. Any other value is empty."""
    raw = _datum("payment", parts, metadata)
    return raw if raw in ("paid", "pending") else ""


def _memory(parts: list[Any], metadata: dict[str, Any]) -> Memory:
    """The customer's memory from earlier conversations, as in `/queries`; malformed is `INVALID_PARAMS`."""
    try:
        return memory_from(_datum("memory", parts, metadata))
    except ValueError as e:
        raise RPCError(INVALID_PARAMS, str(e)) from None


def _sale(parts: list[Any], metadata: dict[str, Any]) -> tuple[PlanOp, ...]:
    """The sale's moves so far, as they came out in `agro_evidence.sale.ops`.

    A malformed op is `INVALID_PARAMS` with the index and the reason, and not a
    half plan: the sale that follows from a misread plan would ask for what was already
    asked.
    """
    raw = _datum("sale", parts, metadata)
    if isinstance(raw, dict) and "ops" in raw:
        raw = raw["ops"]
    try:
        return ops_from(raw)
    except ValueError as e:
        raise RPCError(INVALID_PARAMS, str(e)) from None


def _effects(parts: list[Any], metadata: dict[str, Any]) -> tuple[EffectOp, ...]:
    """The effects' moves so far, as they came out in `agro_evidence.effects.ops`.

    With the `done` or the `reject` of each pending one the client executed. A
    malformed op is `INVALID_PARAMS`, as in the sale: a channel read halfway
    would make the advisor propose again what was already sent.
    """
    raw = _datum("effects", parts, metadata)
    if isinstance(raw, dict) and "ops" in raw:
        raw = raw["ops"]
    try:
        return effect_ops_from(raw)
    except ValueError as e:
        raise RPCError(INVALID_PARAMS, str(e)) from None


def _guardrails(r: Answer) -> list[dict[str, Any]]:
    """The event the host already knows how to show, and only when there is something to alert.

    `applied` false: nothing was blocked, the answer went out anyway. It is an alert
    to the operator, not a veto, which is exactly what `grounded` does. The turn
    with nothing to search does not query and is not an opinion: it does not alert.
    """
    backed = r.grounded or r.nothing_to_search
    if backed and not r.fails:
        return []
    return [
        {
            "name": "grounding",
            "stage": "after_answer",
            "outcome": "no_evidence" if not backed else "incomplete",
            "reasonCode": "did_not_query_catalog" if not backed else "run_with_failures",
            "applied": False,
            "detail": "; ".join(r.fails) or "the agent ran no query against the catalog",
        }
    ]


async def _message_send(params: dict[str, Any], a: Advisor, settings: Settings) -> dict[str, Any]:
    message = params.get("message")
    if not isinstance(message, dict):
        raise RPCError(INVALID_PARAMS, "missing `params.message`")
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RPCError(INVALID_PARAMS, "`message.parts` must be a list with at least one part")
    question = _text(parts)
    if not question:
        raise RPCError(
            CONTENT_TYPE_NOT_SUPPORTED,
            "this agent only reads text parts and none came with content",
        )

    metadata = params.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    history = _history(parts, metadata)
    sale = _sale(parts, metadata)
    effects = _effects(parts, metadata)

    memory = _memory(parts, metadata)

    r = await a.ask(
        question,
        history,
        sale=sale,
        effects=effects,
        timeout=settings.timeout_s,
        payment=_payment(parts, metadata),
        memory=memory,
    )
    if r.cut_off and not r.text:
        raise RPCError(INTERNAL, "; ".join(r.fails))
    if not r.text:
        raise RPCError(
            INVALID_AGENT_RESPONSE,
            "; ".join(r.fails) or "the agent ended without answering",
        )

    output: dict[str, Any] = {
        "kind": "message",
        "role": "agent",
        "messageId": uuid.uuid4().hex,
        "parts": [
            {"kind": "text", "text": r.text},
            {
                "kind": "data",
                "data": {
                    "kind": "agro_evidence",
                    "messages": list(r.messages) or [r.text],
                    "sources": list(r.sources),
                    "grounded": r.grounded,
                    "tokens": r.tokens,
                    "turns": r.turns,
                    "halt": r.halt,
                    "fails": list(r.fails),
                    "seconds": r.seconds,
                    "truncated": r.cut_off,
                    "no_search_terms": r.nothing_to_search,
                    "sale": {**sale_to_dict(summary(r.sale)), "judgment": r.judgment},
                    "effects": effects_to_dict(effects_summary(r.effects)),
                },
            },
        ],
    }
    for field in ("contextId", "taskId"):
        if isinstance(message.get(field), str) and message[field]:
            output[field] = message[field]
    alerts = _guardrails(r)
    if alerts:
        output["metadata"] = {"guardrails": alerts}
    return output


@router.post(ROUTE, dependencies=[Depends(authenticated)])
async def rpc(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """The only JSON-RPC endpoint. The body is parsed by hand to be able to answer -32700."""
    try:
        payload = await request.json()
    except Exception:
        return _envelope(None, error=RPCError(PARSE, "the body is not JSON"))
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or "id" not in payload:
        return _envelope(None, error=RPCError(INVALID_REQUEST, "missing `jsonrpc: \"2.0\"` or `id`"))

    pid = payload.get("id")
    method = payload.get("method")
    params = payload.get("params")
    if not isinstance(params, dict):
        params = {}

    try:
        if method == "message/send":
            a = advisor(request)
            return _envelope(pid, await _message_send(params, a, settings))
        if method in ("message/stream", "tasks/get", "tasks/cancel", "tasks/resubscribe"):
            raise RPCError(
                UNSUPPORTED_OPERATION,
                f"`{method}` is not available: this agent answers whole in `message/send` and does "
                f"not keep tasks. The card declares it in `capabilities`.",
            )
        if isinstance(method, str) and method.startswith("tasks/pushNotificationConfig"):
            raise RPCError(UNSUPPORTED_OPERATION, "no push notifications")
        raise RPCError(METHOD_NOT_FOUND, f"unknown method: {method!r}")
    except RPCError as e:
        return _envelope(pid, error=e)


def _card(request: Request, settings: Settings) -> dict[str, Any]:
    base = (settings.public_url or str(request.base_url)).rstrip("/")
    return {
        "protocolVersion": PROTOCOL,
        "name": "agronomic-advisor",
        "description": (
            "Sales advisor over the Agroinsumos Ceiba bioinputs catalog: which product works "
            "for a pest on a crop, with the dose exactly as registered, the route, the "
            "water volume and the safety restrictions, and it carries the sale (pest, product, "
            "quantity, purchase, payment, invoice) asking for one thing per turn. Each answer declares "
            "which datasheet each fact came from, and if it did not check the catalog it says so."
        ),
        "url": f"{base}{ROUTE}",
        "preferredTransport": "JSONRPC",
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "agronomic_query",
                "name": "Agronomic query",
                "description": (
                    "One question per call. This agent keeps no state between calls: to "
                    "chain turns, send the earlier ones in a part of kind 'data' with "
                    "{\"history\": [{\"question\", \"answer\"}]} or in params.metadata.history, "
                    "the sale with {\"sale\": <ops>} and the effects with {\"effects\": <ops>} in the "
                    "same place, where each <ops> is 'agro_evidence.sale.ops' and "
                    "'agro_evidence.effects.ops' of the previous answer, as is. The answer "
                    "brings a text part and a data part with kind 'agro_evidence': 'sources' "
                    "are the cited files, 'grounded' says whether the answer came from the catalog, "
                    "'no_search_terms' that this turn only had to ask, and 'sale' the state "
                    "of the sale (state, stage, asks, pending, closed) plus the 'ops' to send back "
                    "and 'judgment', what the advisor understood from the customer so far (state) and with "
                    "what probability they already said each thing the sale needs (p). "
                    "'effects.pending' is the only thing that asks for an action: sends the advisor "
                    "proposed and this agent cannot make (kind 'document' with the paths of the "
                    "datasheets in args, kind 'bank_account' the account). Whoever sends them adds "
                    "{\"verb\": \"done\", \"id\": ..., \"note\": ...} to 'effects.ops' in the "
                    "next request, or 'reject' with the reason if 'executable' came false."
                ),
                "tags": ["agro", "catalog", "dose", "pests", "bioinputs"],
                "examples": [
                    "what do I use for thrips on tomato?",
                    "whitefly on bell pepper, what dose?",
                    "does the product for weevil on banana have a pre-harvest interval?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            }
        ],
    }


@router.get("/.well-known/agent-card.json", include_in_schema=False)
def agent_card(request: Request, settings: Settings = Depends(get_settings)) -> JSONResponse:
    return JSONResponse(_card(request, settings))


@router.get("/.well-known/agent.json", include_in_schema=False)
def agent_card_old(request: Request, settings: Settings = Depends(get_settings)) -> JSONResponse:
    """The name 0.2 used. Two lines, and an old client finds the agent."""
    return JSONResponse(_card(request, settings))
