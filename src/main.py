"""The app. The advisor is built only once, in the `lifespan` (see `lifespan/agent.py`)."""

from fastapi import FastAPI

from config import get_settings
from lifespan.agent import lifespan
from routes import a2a_router, chat_router, compaction_router, queries_router, health_router

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.include_router(health_router)
app.include_router(queries_router)
app.include_router(a2a_router)
app.include_router(compaction_router)
app.include_router(chat_router)
