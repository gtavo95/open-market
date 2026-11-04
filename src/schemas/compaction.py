"""The body and the answer of `POST /compaction`: the memory comes in, the new nodes come out."""

from pydantic import BaseModel, ConfigDict, Field

from schemas.queries import MemoryIn, NodeIn


class Compaction(BaseModel):
    """The contact's whole memory, with today's conversation included: the tree covers the whole log."""

    model_config = ConfigDict(extra="forbid")

    memory: MemoryIn
    max: int = Field(default=64, ge=1, le=256, description="How many nodes to build at most in this request.")


class FailedOut(BaseModel):
    l: int  # noqa: E741 — the level, as in `NodeIn`
    i: int
    error: str


class CompactionOut(BaseModel):
    """The new nodes, to keep and send back in the next request.

    `pending` is the nodes that can already be built with these stored: if it is not zero, it has to be
    called again. A failed node was not retried in this request.
    """

    nodes: list[NodeIn]
    failed: list[FailedOut]
    pending: int
    tokens: int
    tokens_input: int = 0
    tokens_cached: int = 0
    tokens_output: int = 0
    seconds: float
