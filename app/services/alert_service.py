import hashlib
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.alert import Alert
from app.models.base import utc_now


class AlertService:
    @staticmethod
    def generate_deduplication_key(rule_id: int, sensor_id: str) -> str:
        return hashlib.sha256(f"{rule_id}:{sensor_id}".encode("utf-8")).hexdigest()

    @staticmethod
    async def create_or_update_alert(
        db: AsyncSession,
        rule_id: int,
        sensor_id: str,
        severity: str,
        observed_value: float,
        message: str
    ) -> Alert:
        dedup_key = AlertService.generate_deduplication_key(rule_id, sensor_id)

        # Check for existing active alert for this rule & sensor
        stmt = select(Alert).where(
            and_(
                Alert.rule_id == rule_id,
                Alert.sensor_id == sensor_id,
                Alert.status.in_(["open", "acknowledged"])
            )
        )
        result = await db.execute(stmt)
        existing_alert = result.scalar_one_or_none()

        if existing_alert:
            # Update existing active alert to avoid alert spamming
            existing_alert.observed_value = observed_value
            existing_alert.message = message
            existing_alert.triggered_at = utc_now()
            await db.flush()
            return existing_alert

        # No active alert exists, create a new one
        new_alert = Alert(
            rule_id=rule_id,
            sensor_id=sensor_id,
            deduplication_key=dedup_key,
            severity=severity,
            status="open",
            observed_value=observed_value,
            message=message,
            triggered_at=utc_now()
        )
        
        try:
            async with db.begin_nested():
                db.add(new_alert)
                await db.flush()
            return new_alert
        except IntegrityError:
            # Concurrent worker created the active alert first (caught by partial unique index)
            result = await db.execute(stmt)
            active_alert = result.scalar_one_or_none()
            if active_alert:
                active_alert.observed_value = observed_value
                active_alert.message = message
                active_alert.triggered_at = utc_now()
                await db.flush()
                return active_alert
            raise

    @staticmethod
    async def acknowledge_alert(
        db: AsyncSession,
        alert_id: int,
        organizer_id: int
    ) -> Optional[tuple[Alert, str]]:
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await db.execute(stmt)
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        if alert.status == "resolved":
            return alert, "Alert is already resolved and cannot be acknowledged."

        if alert.status == "acknowledged":
            return alert, "Alert is already acknowledged."

        alert.status = "acknowledged"
        alert.acknowledged_at = utc_now()
        alert.acknowledged_by = organizer_id
        await db.commit()
        await db.refresh(alert)
        return alert, "Alert acknowledged successfully."

    @staticmethod
    async def resolve_alert(
        db: AsyncSession,
        alert_id: int,
        organizer_id: int
    ) -> Optional[tuple[Alert, str]]:
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await db.execute(stmt)
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        if alert.status == "resolved":
            return alert, "Alert is already resolved."

        alert.status = "resolved"
        alert.resolved_at = utc_now()
        alert.resolved_by = organizer_id
        await db.commit()
        await db.refresh(alert)
        return alert, "Alert resolved successfully."
