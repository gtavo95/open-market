"""The Muse adapter of the vendored wheel, against a fake transport."""


import json
from typing import Any

import httpx
import pytest

from catalejo.core import Message, Role
from catalejo.llm import Muse, MuseError
from catalejo.llm.muse import from_response, to_request

OK: dict[str, Any] = {
    "status": "completed",
    "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "content": [{"type": "output_text", "text": "lis"}, {"type": "output_text", "text": "to"}]},
    ],
    "usage": {"input_tokens": 30, "output_tokens": 12, "total_tokens": 42,
              "output_tokens_details": {"reasoning_tokens": 5}},
}


def client_with(*replies: httpx.Response) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return replies[min(len(seen) - 1, len(replies) - 1)]

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


class TestToRequest:
    def test_the_system_goes_in_instructions(self) -> None:
        out = to_request((Message(Role.SYSTEM, "a"), Message(Role.SYSTEM, "b"), Message(Role.USER, "hello")))

        assert out == {"instructions": "a\n\nb", "input": "hello"}

    def test_several_turns_go_as_a_list(self) -> None:
        out = to_request((Message(Role.USER, "p"), Message(Role.ASSISTANT, "r"), Message(Role.USER, "q")))

        assert out["input"] == [{"role": "user", "content": "p"}, {"role": "assistant", "content": "r"},
                                {"role": "user", "content": "q"}]

    def test_no_turns_is_an_error(self) -> None:
        with pytest.raises(MuseError, match="without turns"):
            to_request((Message(Role.SYSTEM, "solo"),))


class TestFromResponse:
    def test_joins_the_output_text_and_ignores_the_reasoning(self) -> None:
        reply = from_response(OK)

        assert reply.message == Message(Role.ASSISTANT, "listo")
        assert reply.spent == 42

    def test_incomplete_is_not_retried(self) -> None:
        with pytest.raises(MuseError, match="max_output_tokens") as e:
            from_response({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}})
        assert not e.value.transient

    def test_empty_is_retried_and_was_billed(self) -> None:
        with pytest.raises(MuseError, match="empty") as e:
            from_response({"status": "completed", "output": [{"type": "reasoning"}]})
        assert e.value.transient and e.value.billed

    def test_error_in_the_body(self) -> None:
        with pytest.raises(MuseError, match="model does not exist"):
            from_response({"error": {"message": "model does not exist"}})


class TestComplete:
    async def test_hits_responses_with_the_key_and_counts_usage(self) -> None:
        client, seen = client_with(httpx.Response(200, json=OK))
        muse = Muse("m", api_key="secret", client=client)

        reply = await muse.complete((Message(Role.SYSTEM, "s"), Message(Role.USER, "hello")))

        body = json.loads(seen[0].content)
        assert str(seen[0].url) == "https://api.meta.ai/v1/responses"
        assert seen[0].headers["authorization"] == "Bearer secret"
        assert body["instructions"] == "s" and body["input"] == "hello" and body["store"] is False
        assert body["reasoning"] == {"effort": "low"}
        assert reply.spent == 42
        assert (muse.usage.input, muse.usage.output, muse.usage.reasoning, muse.usage.calls) == (30, 12, 5, 1)

    async def test_retries_a_503(self) -> None:
        client, seen = client_with(httpx.Response(503, text="x"), httpx.Response(200, json=OK))
        muse = Muse(api_key="k", client=client, backoff=0)

        assert (await muse.complete((Message(Role.USER, "hello"),))).message.text == "listo"
        assert len(seen) == 2

    async def test_a_400_is_not_retried(self) -> None:
        client, seen = client_with(httpx.Response(400, text="malo"))
        muse = Muse(api_key="k", client=client, backoff=0)

        with pytest.raises(MuseError, match="HTTP 400"):
            await muse.complete((Message(Role.USER, "hello"),))
        assert len(seen) == 1

    def test_no_key_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k in ("MUSE_API_KEY", "MODEL_API_KEY"):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(MuseError, match="missing MUSE_API_KEY"):
            Muse()

    def test_meets_the_wide_port(self) -> None:
        from catalejo.llm import Provider
        m: Provider = Muse(api_key="k")
        assert m.model
