from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.base import utc_now
from app.schemas.health import HealthLiveResponse, HealthReadyResponse

router = APIRouter(tags=["Health"])


@router.get("/health/live", response_model=HealthLiveResponse, status_code=status.HTTP_200_OK)
async def health_live() -> HealthLiveResponse:
    return HealthLiveResponse(status="ok")


@router.get("/health/ready", response_model=HealthReadyResponse)
async def health_ready(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return HealthReadyResponse(
            status="ready",
            database="connected",
            timestamp=utc_now()
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "database": f"error: {str(e)}",
                "timestamp": utc_now().isoformat()
            }
        )
