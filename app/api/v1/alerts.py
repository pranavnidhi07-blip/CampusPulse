from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import Organizer
from app.models.alert import Alert
from app.schemas.alert import AlertOut, AlertActionResponse
from app.services.alert_service import AlertService
from app.api.deps import get_current_organizer

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (open, acknowledged, resolved)"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor key"),
    rule_id: Optional[int] = Query(None, description="Filter by rule ID"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    from_time: Optional[datetime] = Query(None, description="Triggered on or after UTC"),
    to_time: Optional[datetime] = Query(None, description="Triggered on or before UTC"),
    limit: int = Query(100, ge=1, le=500, description="Max alerts to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Alert)
    filters = []

    if status_filter:
        filters.append(Alert.status == status_filter.lower())
    if sensor_id:
        filters.append(Alert.sensor_id == sensor_id)
    if rule_id:
        filters.append(Alert.rule_id == rule_id)
    if severity:
        filters.append(Alert.severity == severity.lower())
    if from_time:
        filters.append(Alert.triggered_at >= from_time)
    if to_time:
        filters.append(Alert.triggered_at <= to_time)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(Alert.triggered_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: int,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertActionResponse)
async def acknowledge_alert(
    alert_id: int,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    result = await AlertService.acknowledge_alert(db, alert_id=alert_id, organizer_id=organizer.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")
    alert, msg = result
    return AlertActionResponse(alert=AlertOut.model_validate(alert), message=msg)


@router.post("/{alert_id}/resolve", response_model=AlertActionResponse)
async def resolve_alert(
    alert_id: int,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    result = await AlertService.resolve_alert(db, alert_id=alert_id, organizer_id=organizer.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")
    alert, msg = result
    return AlertActionResponse(alert=AlertOut.model_validate(alert), message=msg)
