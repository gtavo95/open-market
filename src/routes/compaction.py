"""The compactor of the customer's memory, as a stateless service (logbook todo #24).

Whoever carries the conversation keeps the log and the nodes; here the memory comes in
as it is and the nodes that could be built come out, with `catalejo.rlm.compact`. It is called
outside the turn, after answering: whatever is not built shows up on the next turn in the
view as unsummarized, and the searcher opens it with `zoom`.

The model is the advisor's with its own effort (`COMPACTOR_THINKING`), built in the
`lifespan`. The prompt is `prompts.memory.COMPACTOR`.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import authenticated
from catalejo.core import join
from catalejo.llm import Provider, metered
from catalejo.rlm import compact, pending
from core_agent.prompts.memory import COMPACTOR
from host.memory import memory_from
from schemas.compaction import Compaction, CompactionOut, FailedOut
from schemas.queries import NodeIn

router = APIRouter(prefix="/compaction", tags=["memory"], dependencies=[Depends(authenticated)])


def compactor(request: Request) -> Provider:
    model: Provider | None = getattr(request.app.state, "compactor", None)
    if model is None:
        reason = getattr(request.app.state, "advisor_error", "") or "the compactor is not built"
        raise HTTPException(status_code=503, detail=reason)
    return model


@router.post("", response_model=CompactionOut)
async def compaction(body: Compaction, model: Provider = Depends(compactor)) -> CompactionOut:
    try:
        memory = memory_from(body.memory.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    start = time.perf_counter()
    with metered() as usage:
        built = await compact(model, memory, prompt=COMPACTOR, max_nodes=body.max)
    return CompactionOut(
        nodes=[NodeIn(l=n.l, i=n.i, text=n.text) for n in built.nodes],
        failed=[FailedOut(l=l, i=i, error=e) for l, i, e in built.failed],
        pending=len(pending(join(memory, built.nodes))),
        tokens=usage.input + usage.output if usage.calls else built.spent,
        tokens_input=usage.input,
        tokens_cached=usage.cached,
        tokens_output=usage.output,
        seconds=round(time.perf_counter() - start, 1),
    )
