from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """The service config. The defaults are those of the `core_agent/` package (the catalejo example).

    The field names are the environment variable names in upper case,
    so `OPENAI_API_KEY` in the `.env` fills `openai_api_key` and is validated at
    startup instead of failing on the first query. On Cloud Run that variable
    is in no file: it is a Secret Manager secret mounted as env
    (see README, Deploy).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "demo-api"
    env: str = "dev"
    debug: bool = False

    bundle_dir: Path = ROOT / "okf"

    public_url: str = ""

    provider: str = "muse"
    muse_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_workspace_id: str = ""
    model: str = ""
    thinking: str = ""
    retries: int = 4
    paid_retries: int = 1
    compactor_thinking: str = "low"

    slots: int = 20
    timeout_s: float = 90.0

    typesafe_api_key: str = ""

    container: bool = True

    issuer: str = ""
    demo_secret: str = ""
    demo_allowed_clients: str = ""
    k_service: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
