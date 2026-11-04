"""Who can query the advisor: the same OIDC gate that protects knowledge.

The caller requests a `client_credentials` token from `{ISSUER}/oidc/token` with its own
OIDC client (knowledge uses `knowledge`) and sends it as `Authorization: Bearer`. Here
we ask the OIDC whether that token is active (introspection, RFC 7662),
authenticating as the `demo` client with `DEMO_SECRET`. It is the protocol the host's
services use:

- no header, or a token the OIDC does not consider active: 401;
- the OIDC does not answer or answers something unreadable: 500;
- a `client_id` outside `DEMO_ALLOWED_CLIENTS`: 403. If that list is empty, any active
  client of the issuer passes;
- an active token is remembered for 60 s. A revoked one stops passing within that span at the latest.

Without `ISSUER` the gate is open: that is dev mode, the one for `uv run` on a laptop. On
Cloud Run (`K_SERVICE` is set by the platform) without `ISSUER` or without `DEMO_SECRET` it does not stay
open: it answers 503 to everything protected. That shows in the answer and not in a restart
loop, like the advisor that did not load (see `lifespan/agent.py`).

Protects `/queries` and `/a2a`. `/health`, `/docs` and the A2A card stay public: they
spend no model and show no conversations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, Request

from config import Settings, get_settings

CLIENT_ID = "demo"
"""The OIDC client this service does the introspection with (`DEMO_SECRET`)."""

TTL_S = 60.0
INTROSPECT_TIMEOUT_S = 10.0


@dataclass
class Gate:
    issuer: str
    secret: str
    allowed: frozenset[str]
    on_cloud_run: bool
    transport: httpx.AsyncBaseTransport | None = None
    _seen: dict[str, tuple[str, float]] = field(default_factory=dict)

    async def customer(self, authorization: str) -> str:
        """The caller's `client_id`, or the matching `HTTPException`. `""` in dev mode."""
        if not self.issuer or not self.secret:
            if self.on_cloud_run:
                raise HTTPException(503, "auth not configured: missing ISSUER or DEMO_SECRET")
            return ""
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Invalid or missing Authorization header")
        token = authorization.removeprefix("Bearer ")

        seen = self._seen.get(token)
        if seen is not None and time.monotonic() < seen[1]:
            client_id = seen[0]
        else:
            self._seen.pop(token, None)
            client_id = await self._introspect(token)
            self._seen[token] = (client_id, time.monotonic() + TTL_S)

        if self.allowed and client_id not in self.allowed:
            raise HTTPException(403, f"client not authorized for agro: {client_id}")
        return client_id

    async def _introspect(self, token: str) -> str:
        form = {"token": token, "client_id": CLIENT_ID, "client_secret": self.secret}
        try:
            async with httpx.AsyncClient(timeout=INTROSPECT_TIMEOUT_S, transport=self.transport) as http:
                r = await http.post(f"{self.issuer}/oidc/token/introspection", data=form)
        except httpx.HTTPError as e:
            raise HTTPException(500, f"could not validate the token: {type(e).__name__}") from e
        if r.status_code != 200:
            raise HTTPException(401, "Invalid or expired token")
        try:
            data = r.json()
        except ValueError as e:
            raise HTTPException(500, "the introspection did not return JSON") from e
        if not isinstance(data, dict) or data.get("active") is not True:
            raise HTTPException(401, "Invalid or expired token")
        return str(data.get("client_id", ""))


@lru_cache
def _gate(issuer: str, secret: str, allowed: str, on_cloud_run: bool) -> Gate:
    return Gate(
        issuer=issuer.strip().rstrip("/"),
        secret=secret,
        allowed=frozenset(c.strip() for c in allowed.split(",") if c.strip()),
        on_cloud_run=on_cloud_run,
    )


def gate(settings: Settings = Depends(get_settings)) -> Gate:
    """One per configuration, so the token memory survives between requests."""
    return _gate(settings.issuer, settings.demo_secret, settings.demo_allowed_clients, bool(settings.k_service))


async def authenticated(request: Request, p: Gate = Depends(gate)) -> str:
    """The dependency of the protected routes. Returns the caller's `client_id`."""
    return await p.customer(request.headers.get("authorization", ""))
