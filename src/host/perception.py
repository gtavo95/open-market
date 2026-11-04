"""Photos and voice notes into text, with Muse Wonder, before the turn starts.

The Meta Model API takes images and audio in the same `/responses` call as text, so one model does
both. What comes back goes to the advisor as the customer's message: nothing downstream knows it
was not typed. The catalejo adapter speaks text only, so this is its own small call.
"""

from __future__ import annotations

from typing import Any

import httpx

from catalejo.llm import with_retries
from catalejo.llm.muse import BASE, TRANSIENT, MuseError, from_response
from core_agent.prompts.perception import PHOTO_PROMPT, VOICE_PROMPT

TIMEOUT = 60.0
"""A photo at low effort took 22 s in the Nov 3, 2026 probe; the rest is margin."""
RETRIES = 2
"""On Nov 3, 2026, 2 of 21 readings failed with no retry: one timed out, one came back empty."""


class Perception:
    """The two readings. `transport` is for the tests."""

    def __init__(
        self, key: str, model: str, *, thinking: str = "low", transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.key = key
        self.model = model
        self.thinking = thinking
        self.transport = transport

    async def photo(self, data_url: str) -> str:
        """What the photo shows. `data_url` is a `data:image/...;base64,` URL."""
        return await self._read(PHOTO_PROMPT, {"type": "input_image", "image_url": data_url})

    async def voice(self, wav_base64: str) -> str:
        """What the voice note says. The page sends it as WAV, whatever the browser recorded."""
        return await self._read(
            VOICE_PROMPT, {"type": "input_audio", "input_audio": {"data": wav_base64, "format": "wav"}}
        )

    async def _read(self, prompt: str, part: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": self.thinking},
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}, part]}],
        }
        headers = {"Authorization": f"Bearer {self.key}"}

        async def request() -> str:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
                try:
                    r = await client.post(f"{BASE}/responses", headers=headers, json=body)
                except httpx.TransportError as e:
                    raise MuseError(f"no answer from the API: {type(e).__name__}", transient=True) from e
            if r.status_code in TRANSIENT:
                raise MuseError(f"the API returned {r.status_code}", transient=True)
            r.raise_for_status()
            return from_response(r.json()).message.text.strip()

        return await with_retries(request, retries=RETRIES, backoff=1.0)


def message(said: str, seen: str) -> str:
    """The customer's turn: what they said, and what their photo shows if they sent one."""
    if not seen:
        return said
    photo = f"[The customer sent a photo. It shows: {seen}]"
    return f"{said}\n{photo}" if said else photo
