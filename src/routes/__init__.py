from .a2a import router as a2a_router
from .chat import router as chat_router
from .compaction import router as compaction_router
from .queries import router as queries_router
from .health import router as health_router

__all__ = ["a2a_router", "chat_router", "compaction_router", "queries_router", "health_router"]
