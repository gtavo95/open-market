from fastapi import APIRouter, Depends, Request

from config import Settings, get_settings
from schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(request: Request, settings: Settings = Depends(get_settings)) -> HealthOut:
    """Alive, and whether the advisor got built.

    They go separately because they are two different failures: the process can be healthy and
    the catalog may not have loaded. With a single boolean, a deploy without an API key
    answers 200 and looks fine until the first query.
    """
    advisor = getattr(request.app.state, "advisor", None)
    return HealthOut(
        status="ok",
        app=settings.app_name,
        env=settings.env,
        advisor=advisor is not None,
        advisor_error=getattr(request.app.state, "advisor_error", ""),
    )
