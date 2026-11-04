"""The public demo: a chat page with text, photo and voice, and the turn behind it.

`/queries` belongs to a host that keeps the conversation and authenticates. This route is that
host for a browser: it keeps each session in memory and simulates the effects with `host_sim`, as
the CLI does. So it runs on one instance, and a restart forgets the conversations.

It has no login, so `demo_turns` caps the paid turns per process.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from catalejo.core import EffectOp, PlanOp, effects_of
from catalejo.llm import ProviderError
from config import Settings, get_settings
from core_agent import host_sim
from core_agent.agent import MUSE_MODEL
from host import Advisor
from host.agent import TurnFailed
from host.perception import Perception, message
from routes.queries import advisor

PAGE = Path(__file__).resolve().parents[1] / "web" / "index.html"
SESSIONS = 200
"""The conversations kept; past that, the oldest goes."""
HISTORY = 20
"""The turns sent to the advisor, the same cap as `/queries`."""

router = APIRouter(tags=["demo"])


@dataclass
class Session:
    history: tuple[tuple[str, str], ...] = ()
    sale: tuple[PlanOp, ...] = ()
    effects: tuple[EffectOp, ...] = ()
    form: dict[str, str] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


sessions: OrderedDict[str, Session] = OrderedDict()
turns_served = 0


class ChatIn(BaseModel):
    session: str = Field(min_length=8, max_length=64)
    text: str = Field(default="", max_length=2000)
    image: str = Field(default="", max_length=8_000_000, pattern=r"^(data:image/(jpeg|png|webp);base64,.*)?$")
    audio: str = Field(default="", max_length=12_000_000)


class ChatOut(BaseModel):
    messages: list[str]
    sources: list[str]
    heard: str
    seen: str
    tokens: int
    seconds: float


def perception(settings: Settings = Depends(get_settings)) -> Perception:
    return Perception(settings.muse_api_key, settings.model or MUSE_MODEL)


def session_of(key: str) -> Session:
    s = sessions.pop(key, None) or Session()
    sessions[key] = s
    while len(sessions) > SESSIONS:
        sessions.popitem(last=False)
    return s


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def page() -> str:
    return PAGE.read_text(encoding="utf-8")


@router.post("/chat", response_model=ChatOut)
async def chat(
    body: ChatIn,
    a: Advisor = Depends(advisor),
    eyes: Perception = Depends(perception),
    settings: Settings = Depends(get_settings),
) -> ChatOut:
    global turns_served
    if not (body.text.strip() or body.image or body.audio):
        raise HTTPException(status_code=422, detail="send text, a photo or a voice note")
    if turns_served >= settings.demo_turns:
        raise HTTPException(status_code=429, detail="the demo reached its turn limit for today")
    turns_served += 1

    s = session_of(body.session)
    async with s.lock:
        try:
            heard, seen = await asyncio.gather(
                eyes.voice(body.audio) if body.audio else _nothing(),
                eyes.photo(body.image) if body.image else _nothing(),
            )
        except (httpx.HTTPError, ProviderError) as e:
            raise HTTPException(status_code=502, detail=f"could not read the attachment: {e}") from e
        said = " ".join(p for p in (body.text.strip(), heard) if p)
        question = message(said, seen)
        if not question:
            raise HTTPException(status_code=422, detail="the voice note could not be understood")

        try:
            r = await a.ask(
                question,
                s.history[-HISTORY:],
                sale=s.sale,
                effects=s.effects,
                timeout=settings.timeout_s,
                form=s.form,
            )
        except TurnFailed as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        if not r.text:
            raise HTTPException(status_code=502, detail="the advisor ended without answering")

        s.history = (*s.history, (question, r.text))
        s.sale = r.sale
        s.effects = (*r.effects, *host_sim(effects_of(r.effects)))
        s.form = r.form

    return ChatOut(
        messages=list(r.messages) or [r.text],
        sources=list(r.sources),
        heard=heard,
        seen=seen,
        tokens=r.tokens,
        seconds=round(r.seconds, 1),
    )


async def _nothing() -> str:
    return ""
