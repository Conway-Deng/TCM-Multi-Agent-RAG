from __future__ import annotations

import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from .schemas import CrossPerspectiveConsultRequest, CrossPerspectiveConsultResponse
from .service import CrossPerspectiveRunError, CrossPerspectiveService, NutritionUnavailableError


router = APIRouter(prefix="/api/cross-perspective", tags=["cross-perspective-development"])


@lru_cache(maxsize=1)
def get_cross_perspective_service() -> CrossPerspectiveService:
    return CrossPerspectiveService()


@router.post(
    "/consult",
    response_model=CrossPerspectiveConsultResponse,
    summary="Run the development-only TCM/Western cross-perspective prototype",
    description=(
        "DEVELOPMENT PROTOTYPE — NOT FORMAL EXPERIMENT. Preserves perspective identity and provenance; "
        "it does not provide medical advice."
    ),
)
async def cross_perspective_consult(
    request: CrossPerspectiveConsultRequest,
) -> CrossPerspectiveConsultResponse:
    if os.getenv("RENDER_API_CONTROL_PLANE_ONLY", "").strip().casefold() in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=503, detail="Cross-perspective development execution is local-only.")
    try:
        return await get_cross_perspective_service().consult(request)
    except NutritionUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CrossPerspectiveRunError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": str(exc),
                "run_id": exc.trace.run_id,
                "failed_roles": exc.trace.failed_roles,
            },
        ) from exc
