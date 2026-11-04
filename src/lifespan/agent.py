"""The advisor that lives as long as the process: how it is built, and the `lifespan` that opens and closes it.

Loading the catalog and building the pool costs seconds and does not depend on the request,
so it goes in the `lifespan` and not in the request. The model too: its httpx
client keeps connections open, and one per query pays for TLS every time.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core_agent.agent import (
    CLAUDE_MODEL,
    CLAUDE_THINKING,
    GEMINI_THINKING,
    MUSE_MODEL,
    MUSE_THINKING,
    OPENAI_MODEL,
    OPENAI_THINKING,
    TIMEOUT,
)
from core_agent.world.question_judge import QuestionJudge
from core_agent.world.typesafe import Client
from catalejo.llm import Claude, Gemini, Muse, OpenAI, Provider
from catalejo.llm.gemini import MODEL as GEMINI_MODEL
from config import Settings, get_settings
from host import Advisor, load

CALL_TIMEOUT = TIMEOUT
"""The seconds of each provider call, those of `core_agent.provider()`: 40 since Sep 22.

Below the per-role cap (45 s with `TIMEOUT_S=90`), so a hung call
retries instead of eating the whole role. In round 16 that happened four
times in 60 turns with the default of 120 s.
"""


def provider(s: Settings) -> Provider:
    """The root model, and which provider it talks to. One `if`, as in the CLI.

    Empty `MODEL` and `THINKING` are those of `core_agent.provider`: Wonder 1.0
    with `medium` on Muse, gpt-6-luna with `medium` on OpenAI, the adapter default with `low` on Gemini, Haiku 5.5 with
    `medium` on Anthropic.
    """
    if s.provider == "muse":
        return Muse(
            s.model or os.environ.get("MUSE_MODEL") or MUSE_MODEL,
            thinking=s.thinking or MUSE_THINKING,
            retries=s.retries,
            paid_retries=s.paid_retries,
            api_key=s.muse_api_key or None,
            timeout=CALL_TIMEOUT,
        )
    if s.provider == "openai":
        return OpenAI(
            s.model or OPENAI_MODEL,
            thinking=s.thinking or OPENAI_THINKING,
            retries=s.retries,
            paid_retries=s.paid_retries,
            api_key=s.openai_api_key or None,
            timeout=CALL_TIMEOUT,
        )
    if s.provider == "anthropic":
        return Claude(
            s.model or CLAUDE_MODEL,
            thinking=s.thinking or CLAUDE_THINKING,
            retries=s.retries,
            paid_retries=s.paid_retries,
            api_key=s.anthropic_api_key or None,
            workspace=s.anthropic_workspace_id or None,
            timeout=CALL_TIMEOUT,
        )
    if s.provider != "gemini":
        raise ValueError(f"PROVIDER={s.provider!r}: must be muse, gemini, openai or anthropic")
    return Gemini(
        s.model or GEMINI_MODEL,
        thinking=s.thinking or GEMINI_THINKING,
        retries=s.retries,
        paid_retries=s.paid_retries,
        api_key=s.gemini_api_key or None,
        timeout=CALL_TIMEOUT,
    )


def question_judge(s: Settings, model: Provider) -> QuestionJudge:
    """The sale gates with their judge. Without a key it does not start (see `Settings.typesafe_api_key`)."""
    if not s.typesafe_api_key:
        raise ValueError("the sale closes its slots with a judgment and TYPESAFE_API_KEY is missing")
    return QuestionJudge(Client(s.typesafe_api_key), model)


def build_advisor(s: Settings) -> Advisor:
    model = provider(s)
    return Advisor(
        load(s.bundle_dir),
        model,
        question_judge=question_judge(s, model),
        slots=s.slots,
        contained=s.container,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Builds the advisor, and if it cannot, leaves word of why.

    Without an API key or a bundle the app starts anyway and `/queries` answers 503 with
    the reason. This is on purpose: dying at boot leaves the container in a restart
    loop where the error only shows in the logs, and here it can be read over HTTP
    at `/health`. The rest of the endpoints do not depend on the advisor.
    """
    app.state.advisor = None
    app.state.advisor_error = ""
    app.state.compactor = None
    s = get_settings()
    try:
        app.state.advisor = build_advisor(s)
        app.state.compactor = provider(s.model_copy(update={"thinking": s.compactor_thinking}))
    except Exception as e:
        app.state.advisor_error = f"{type(e).__name__}: {e}"
    yield
    if app.state.advisor is not None:
        await app.state.advisor.aclose()
    if app.state.compactor is not None:
        await app.state.compactor.aclose()
