"""The public demo: a photo or a voice note becomes text, and the session survives the turn."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from config import Settings, get_settings
from host.perception import Perception, message
from main import app
from routes import chat as chat_route
from routes.chat import perception
from tests.test_routes import GROUNDED, FakeAdvisor, built

PHOTO = "data:image/png;base64,iVBORw0KGgo="


class FakeEyes:
    def __init__(self, heard: str = "worms in my corn", seen: str = "A caterpillar on a corn leaf.") -> None:
        self.heard = heard
        self.seen = seen

    async def voice(self, wav_base64: str) -> str:
        return self.heard

    async def photo(self, data_url: str) -> str:
        return self.seen


@pytest.fixture
def client() -> Iterator[TestClient]:
    chat_route.sessions.clear()
    chat_route.turns_served = 0
    app.dependency_overrides[perception] = FakeEyes
    app.dependency_overrides[get_settings] = lambda: Settings(timeout_s=9, _env_file=None)
    app.state.advisor = None
    app.state.advisor_error = ""
    yield TestClient(app)
    app.dependency_overrides.clear()


def send(client: TestClient, **body: Any) -> httpx.Response:
    return client.post("/chat", json={"session": "session-1", **body})


class TestTurn:
    def test_text_goes_to_the_advisor_as_is(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)

        r = send(client, text="what do you have for thrips?")

        assert r.status_code == 200
        assert fake.calls[0][0] == "what do you have for thrips?"
        assert r.json()["heard"] == ""
        assert r.json()["seen"] == ""

    def test_a_voice_note_is_the_customers_message(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)

        r = send(client, audio="UklGRg==")

        assert fake.calls[0][0] == "worms in my corn"
        assert r.json()["heard"] == "worms in my corn"

    def test_a_photo_travels_with_what_they_wrote(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)

        send(client, text="what is this?", image=PHOTO)

        assert fake.calls[0][0].startswith("what is this?\n[The customer sent a photo.")
        assert "A caterpillar on a corn leaf." in fake.calls[0][0]

    def test_the_second_turn_carries_the_first(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)

        send(client, text="first")
        send(client, text="second")

        assert fake.calls[1][1] == (("first", GROUNDED.text),)

    def test_sessions_do_not_mix(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)

        send(client, text="first")
        client.post("/chat", json={"session": "session-2", "text": "other"})

        assert fake.calls[1][1] == ()


class TestLimits:
    def test_an_empty_turn_costs_nothing(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)

        assert send(client, text="  ").status_code == 422
        assert fake.calls == []

    def test_a_note_nobody_can_understand_does_not_reach_the_advisor(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)
        app.dependency_overrides[perception] = lambda: FakeEyes(heard="")

        assert send(client, audio="UklGRg==").status_code == 422
        assert fake.calls == []

    def test_only_images_are_taken(self, client: TestClient) -> None:
        built(client, FakeAdvisor())

        assert send(client, image="https://example.com/x.png").status_code == 422

    def test_the_cap_stops_the_paid_turns(self, client: TestClient) -> None:
        fake = FakeAdvisor()
        built(client, fake)
        app.dependency_overrides[get_settings] = lambda: Settings(demo_turns=1, _env_file=None)

        assert send(client, text="one").status_code == 200
        assert send(client, text="two").status_code == 429
        assert len(fake.calls) == 1


class TestPage:
    def test_it_needs_no_login(self, client: TestClient) -> None:
        r = client.get("/")

        assert r.status_code == 200
        assert "<title>Open Market</title>" in r.text


class TestPerception:
    async def read(self, reply: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        seen: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=reply)

        eyes = Perception("key", "muse-wonder-1.0", transport=httpx.MockTransport(handler))
        return await eyes.photo(PHOTO), seen

    async def test_the_image_goes_next_to_the_prompt(self) -> None:
        reply = {"output": [{"type": "message", "content": [{"type": "output_text", "text": " A leaf. "}]}]}

        text, seen = await self.read(reply)

        assert text == "A leaf."
        assert seen[0]["input"][0]["content"][1] == {"type": "input_image", "image_url": PHOTO}
        assert seen[0]["store"] is False


class TestMessage:
    def test_without_a_photo_it_is_what_they_said(self) -> None:
        assert message("hello", "") == "hello"

    def test_a_photo_alone_is_a_turn(self) -> None:
        assert message("", "A leaf.") == "[The customer sent a photo. It shows: A leaf.]"
