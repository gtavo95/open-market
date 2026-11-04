"""The TypeSafe client, over httpx and with no SDK, like the `catalejo.llm` adapters.

A single endpoint, `POST /v1/systemone`: a `state` (string, dict or list, up to
32k tokens) and a map of typed questions, and back comes a map of answers with
the same keys. It does not generate text: a `noul` is the probability of a yes, a
`choice` brings the option and the distribution, a `score` the position in levels.
It charges only for input, and this client keeps the count.

It lives in the agent and not in `catalejo/`: the sale's
gates (`question_judge.py`) use it as a judge, and the library does not know TypeSafe
exists. The model is pinned by version and not by alias: an
alias that moves on its own changes what each threshold means without anyone touching
a file.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import httpx

from catalejo.llm import ProviderError, with_retries

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
PRICE = 0.042
"""Dollars per million input tokens. Output is not charged."""

TRANSIENT = frozenset({429, 500, 502, 503, 504, 529})


@dataclass
class Spend:
    """What TypeSafe charged inside a `metered()` block: input tokens and requests."""

    tokens: int = 0
    calls: int = 0


_metered: ContextVar[Spend | None] = ContextVar("typesafe_metered", default=None)


@contextmanager
def metered() -> Iterator[Spend]:
    """A `Spend` of what TypeSafe charges inside the block, like `catalejo.llm.metered`.

    The `Client` is one per process and is shared by the turns running at once, so its
    `tokens` does not say what belonged to each one. The host opens the block around a turn and each
    request that turn originates adds up here. It travels in a `ContextVar`, which tasks and
    `asyncio.to_thread` copy.
    """
    spend = Spend()
    token = _metered.set(spend)
    try:
        yield spend
    finally:
        _metered.reset(token)


def charge(tokens: int) -> None:
    """Adds a charged request to the open `metered()` block, if there is one."""
    spend = _metered.get()
    if spend is not None:
        spend.tokens += tokens
        spend.calls += 1


class TypeSafeError(ProviderError):
    """What came back from TypeSafe is no use as an answer."""


@dataclass(frozen=True, slots=True)
class Response:
    """The answers of a request, by key, and what it cost."""

    answers: dict[str, Any]
    tokens: int
    model: str

    def noul(self, key: str) -> float:
        """The probability of a `noul`, or `TypeSafeError` if the key does not bring one."""
        try:
            p = float(self.answers[key]["noul"])
        except (KeyError, TypeError, ValueError) as e:
            raise TypeSafeError(f"no noul in {key!r}: {self.answers.get(key)!r:.200}") from e
        if not 0.0 <= p <= 1.0:
            raise TypeSafeError(f"noul outside [0, 1] in {key!r}: {p}")
        return p

    def choice(self, key: str) -> str:
        """The chosen option of a `choice`, or `TypeSafeError` if the key does not bring one.

        Only the option: the distribution and the confidence are in `answers` for
        whoever measures, but what comes out of here is the label, which is what a
        host stores. A `choice` always chooses, so there is no empty case to
        handle; empty means the service answered something else.
        """
        try:
            option = str(self.answers[key]["choice"])
        except (KeyError, TypeError) as e:
            raise TypeSafeError(f"no choice in {key!r}: {self.answers.get(key)!r:.200}") from e
        if not option:
            raise TypeSafeError(f"empty choice in {key!r}")
        return option


    def probabilities(self, key: str) -> dict[str, float]:
        """The distribution of a `choice` by option, or `TypeSafeError` if the key does not bring it."""
        try:
            return {str(k): float(v) for k, v in self.answers[key]["probabilities"].items()}
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise TypeSafeError(f"no probabilities in {key!r}: {self.answers.get(key)!r:.200}") from e


def parse(body: dict[str, Any]) -> Response:
    """The `Response` of an already decoded body, or `TypeSafeError` if it does not have the shape."""
    try:
        answers = dict(body["answers"])
        tokens = int(body["usage"]["input_tokens"])
        model = str(body.get("model", MODEL))
    except (KeyError, TypeError, ValueError) as e:
        raise TypeSafeError(f"answer without shape: {body!r:.300}") from e
    return Response(answers=answers, tokens=tokens, model=model)


class Client:
    """One client per run; `aclose()` when done. Works for concurrent calls."""

    def __init__(self, api_key: str, *, model: str = MODEL, retries: int = 3, backoff: float = 1.0) -> None:
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=60.0,
        )
        self.model = model
        self._retries = retries
        self._backoff = backoff
        self.calls = 0
        self.tokens = 0

    @classmethod
    def from_env(cls) -> Client | None:
        """The client if there is a `TYPESAFE_API_KEY`; otherwise `None`."""
        key = os.environ.get("TYPESAFE_API_KEY", "")
        return cls(key) if key else None

    @property
    def cost(self) -> float:
        return self.tokens / 1_000_000 * PRICE

    async def ask(self, state: Any, questions: dict[str, Any]) -> Response:
        payload = {"model": self.model, "state": state, "questions": questions}

        async def request() -> Response:
            try:
                r = await self._client.post(URL, json=payload)
            except httpx.HTTPError as e:
                raise TypeSafeError(f"{type(e).__name__}: {e}", transient=True) from e
            if r.status_code != 200:
                raise TypeSafeError(f"HTTP {r.status_code}: {r.text[:300]}", transient=r.status_code in TRANSIENT)
            return parse(r.json())

        out = await with_retries(request, retries=self._retries, backoff=self._backoff)
        self.calls += 1
        self.tokens += out.tokens
        charge(out.tokens)
        return out

    async def aclose(self) -> None:
        await self._client.aclose()
