from .a2a import router as a2a_router
from .chat import router as chat_router
from .compactar import router as compactar_router
from .compaction import router as compaction_router
from .consultas import router as consultas_router
from .queries import router as queries_router
from .health import router as health_router

__all__ = ["a2a_router", "chat_router", "compactar_router", "compaction_router", "consultas_router", "queries_router", "health_router"]
