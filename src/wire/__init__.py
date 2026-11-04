"""The Spanish wire of the host that carries the conversation, translated at the edge.

The interior (`core_agent/`, `host/`, `schemas/`) is English. Knowledge speaks Spanish
(`contrato/` in its repo). This package is the only place where the two meet: `tables.py` says,
as data, which Spanish name or value is which English one, and `translate.py` walks a payload with
those tables in either direction. Nothing in here reads a customer's words: it moves names.
"""

from .translate import to_english, to_wire

__all__ = ["to_english", "to_wire"]
