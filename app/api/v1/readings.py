from datetime import datetime
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import SensorClient, Organizer
from app.models.sensor import Reading
from app.schemas.reading import (
    ReadingCreate,
    ReadingOut,
    BatchReadingResponse
)
from app.api.deps import get_sensor_client, get_current_organizer
from app.services.ingestion_service import IngestionService
from app.config import settings

router = APIRouter(prefix="/readings", tags=["Readings"])


@router.post("", response_model=ReadingOut, status_code=status.HTTP_201_CREATED)
async def submit_single_reading(
    reading_in: ReadingCreate,
    sensor_client: SensorClient = Depends(get_sensor_client),
    db: AsyncSession = Depends(get_db)
):
    reading, is_new = await IngestionService.ingest_single(db, reading_in, sync_evaluate=True)
    return reading


@router.post("/batch", response_model=BatchReadingResponse, status_code=status.HTTP_200_OK)
async def submit_batch_readings(
    payload: list[dict[str, Any]],
    sensor_client: SensorClient = Depends(get_sensor_client),
    db: AsyncSession = Depends(get_db)
):
    if len(payload) > settings.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size {len(payload)} exceeds maximum allowed batch limit of {settings.MAX_BATCH_SIZE}"
        )

    response = await IngestionService.ingest_batch(db, payload, sync_evaluate=True)
    return response


@router.get("", response_model=list[ReadingOut])
async def query_readings(
    sensor_id: Optional[str] = Query(None, description="Filter by sensor key"),
    metric_type: Optional[str] = Query(None, description="Filter by metric type"),
    from_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    to_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    limit: int = Query(100, ge=1, le=500, description="Max readings to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Reading)
    filters = []

    if sensor_id:
        filters.append(Reading.sensor_id == sensor_id)
    if metric_type:
        filters.append(Reading.metric_type == metric_type.lower())
    if from_time:
        filters.append(Reading.event_timestamp >= from_time)
    if to_time:
        filters.append(Reading.event_timestamp <= to_time)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(Reading.event_timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()
