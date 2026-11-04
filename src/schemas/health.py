"""The `/health` contract. The handler is in `routes/health.py`."""

from pydantic import BaseModel


class HealthOut(BaseModel):
    """`advisor` false with `status` at `ok` is a healthy process and an unbuilt advisor; `advisor_error` says why."""

    status: str
    app: str
    env: str
    advisor: bool
    advisor_error: str
