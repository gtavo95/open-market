"""Muse is the default model, in the API and in the CLI, and `PROVIDER` still picks another one."""

import pytest

from catalejo.llm import Muse, MuseError, OpenAI
from config import Settings
from core_agent.agent import MUSE_MODEL, MUSE_THINKING, provider as cli_provider
from lifespan.agent import CALL_TIMEOUT, provider


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type, call-arg]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PROVIDER", "MODEL", "THINKING", "MUSE_MODEL", "MUSE_API_KEY", "MODEL_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_the_api_defaults_to_wonder_with_medium_effort() -> None:
    model = provider(settings(muse_api_key="k"))
    assert isinstance(model, Muse)
    assert model.model == MUSE_MODEL == "muse-wonder-1.0"
    assert model._config["reasoning"] == {"effort": MUSE_THINKING}
    assert MUSE_THINKING == "medium"
    assert model._client.timeout.read == CALL_TIMEOUT


def test_model_and_thinking_reach_the_adapter() -> None:
    model = provider(settings(muse_api_key="k", model="other", thinking="high"))
    assert isinstance(model, Muse)
    assert model.model == "other"
    assert model._config["reasoning"] == {"effort": "high"}


def test_without_a_key_the_error_names_it() -> None:
    with pytest.raises(MuseError, match="MUSE_API_KEY"):
        provider(settings())


def test_provider_still_picks_another_one() -> None:
    assert isinstance(provider(settings(provider="openai", openai_api_key="k")), OpenAI)


def test_the_cli_defaults_to_muse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    model = cli_provider()
    assert isinstance(model, Muse)
    assert model.model == MUSE_MODEL
    assert model._config["reasoning"] == {"effort": MUSE_THINKING}


def test_muse_model_and_thinking_override_the_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_API_KEY", "k")
    monkeypatch.setenv("MUSE_MODEL", "other")
    monkeypatch.setenv("THINKING", "low")
    for model in (cli_provider(), provider(settings())):
        assert isinstance(model, Muse)
        assert model.model == "other"
        assert model._config["reasoning"] == {"effort": "low"}


def test_the_cli_rejects_an_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER", "x")
    with pytest.raises(ValueError, match="must be muse"):
        cli_provider()
