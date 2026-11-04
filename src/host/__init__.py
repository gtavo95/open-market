"""The advisor host: the catalog loaded once, the agent served, and what travels with the client.

The agent does NOT live here. It lives in `core_agent/`, which is the core without HTTP. This package
is what that agent does not know how to do because
it is not its job: `catalog.py` points it at the service catalog, `agent.py` is its
lifecycle behind a server, and `sale.py` and `effects.py` are the two
channels the client keeps between calls, with what is read from each one.
None of them knows about HTTP; that is `routes/`.

Until Sep 22, 2026 `core_agent/` was a copy of
`catalejo/examples/agro/advisor/` and was not edited here; since then the agent
lives in this repo. They stay in separate packages because `core_agent/` knows nothing about
servers: the terminal (`cli.py`) and the evals (`evals/suite.py`) host it the same way.
"""

from .agent import Advisor, Answer, TurnFailed
from .catalog import Catalog, load

__all__ = ["Advisor", "Answer", "Catalog", "TurnFailed", "load"]
