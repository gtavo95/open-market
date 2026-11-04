"""`POST /compactar`: the compactor of `/compaction`, in the Spanish contract of the host that carries the conversation.

Knowledge posts `{memoria, max}` and reads `{nodos, fallidos, pendientes, tokens, tokens_entrada,
tokens_cacheados, tokens_salida, segundos}`. The work is `routes/compaction.py`'s, unchanged; this is
only the edge (see `routes/consultas.py` for the same idea on the turn). The auth is the same as the
rest of the service.
"""

import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from auth import authenticated
from catalejo.llm import Provider
from routes.compaction import compaction, compactor
from schemas.compaction import Compaction
from wire import to_english, to_wire

router = APIRouter(prefix="/compactar", tags=["memory"], dependencies=[Depends(authenticated)])


@router.post("", response_model=None)
async def compact(
    body: dict[str, Any] = Body(..., description="Knowledge's `{memoria, max}`."),
    model: Provider = Depends(compactor),
) -> JSONResponse:
    """The contact's memory in, the nodes that could be built out; nothing is kept here."""
    try:
        request = Compaction.model_validate(to_english("Compaction", body))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=json.loads(e.json(include_url=False, include_context=False, include_input=False))) from e
    built = await compaction(request, model)
    return JSONResponse(to_wire("CompactionOut", built.model_dump(mode="json")))
