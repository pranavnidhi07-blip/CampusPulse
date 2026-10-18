from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import Organizer
from app.models.rule import AlertRule
from app.schemas.rule import RuleCreate, RuleUpdate, RuleOut, RuleCondition, RuleScope
from app.api.deps import get_current_organizer

router = APIRouter(prefix="/rules", tags=["Alert Rules"])


def format_rule_out(r: AlertRule) -> RuleOut:
    return RuleOut(
        id=r.id,
        name=r.name,
        metricType=r.metric_type,
        scope=RuleScope(sensorIds=r.sensor_scope.get("sensorIds")) if r.sensor_scope else None,
        condition=RuleCondition(
            kind=r.condition_kind,
            operator=r.operator,
            value=r.threshold_value,
            aggregation=r.aggregation,
            windowSeconds=r.window_seconds
        ),
        severity=r.severity,
        enabled=r.enabled,
        version=r.version,
        created_at=r.created_at
    )


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_in: RuleCreate,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    scope_data = {"sensorIds": rule_in.scope.sensor_ids} if rule_in.scope and rule_in.scope.sensor_ids else None
    rule = AlertRule(
        name=rule_in.name,
        metric_type=rule_in.metric_type,
        sensor_scope=scope_data,
        condition_kind=rule_in.condition.kind,
        operator=rule_in.condition.operator,
        threshold_value=rule_in.condition.value,
        window_seconds=rule_in.condition.window_seconds,
        aggregation=rule_in.condition.aggregation,
        severity=rule_in.severity,
        enabled=rule_in.enabled,
        version=1,
        created_by=organizer.id
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return format_rule_out(rule)


@router.get("", response_model=list[RuleOut])
async def list_rules(
    metric_type: Optional[str] = Query(None, description="Filter by metric type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AlertRule)
    if metric_type:
        stmt = stmt.where(AlertRule.metric_type == metric_type.lower())
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)

    stmt = stmt.order_by(AlertRule.id.desc())
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [format_rule_out(r) for r in rules]


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(
    rule_id: int,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AlertRule).where(AlertRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")
    return format_rule_out(rule)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: int,
    patch: RuleUpdate,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AlertRule).where(AlertRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")

    if patch.name is not None:
        rule.name = patch.name
    if patch.metric_type is not None:
        rule.metric_type = patch.metric_type
    if patch.scope is not None:
        rule.sensor_scope = {"sensorIds": patch.scope.sensor_ids} if patch.scope.sensor_ids else None
    if patch.condition is not None:
        rule.condition_kind = patch.condition.kind
        rule.operator = patch.condition.operator
        rule.threshold_value = patch.condition.value
        rule.window_seconds = patch.condition.window_seconds
        rule.aggregation = patch.condition.aggregation
    if patch.severity is not None:
        rule.severity = patch.severity
    if patch.enabled is not None:
        rule.enabled = patch.enabled

    rule.version += 1
    await db.commit()
    await db.refresh(rule)
    return format_rule_out(rule)


@router.post("/{rule_id}/enable", response_model=RuleOut)
async def enable_rule(
    rule_id: int,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AlertRule).where(AlertRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")

    rule.enabled = True
    rule.version += 1
    await db.commit()
    await db.refresh(rule)
    return format_rule_out(rule)


@router.post("/{rule_id}/disable", response_model=RuleOut)
async def disable_rule(
    rule_id: int,
    organizer: Organizer = Depends(get_current_organizer),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AlertRule).where(AlertRule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")

    rule.enabled = False
    rule.version += 1
    await db.commit()
    await db.refresh(rule)
    return format_rule_out(rule)
