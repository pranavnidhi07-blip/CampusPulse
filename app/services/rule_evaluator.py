from datetime import timedelta
from typing import Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import AlertRule
from app.models.sensor import Reading
from app.services.alert_service import AlertService


class RuleEvaluator:
    @staticmethod
    def compare(val: float, op: str, threshold: float) -> bool:
        if op == ">":
            return val > threshold
        elif op == "<":
            return val < threshold
        elif op == ">=":
            return val >= threshold
        elif op == "<=":
            return val <= threshold
        elif op == "==":
            return abs(val - threshold) < 1e-9
        return False

    @staticmethod
    def matches_scope(rule: AlertRule, sensor_id: str) -> bool:
        if not rule.sensor_scope:
            return True
        scope_sensors = rule.sensor_scope.get("sensorIds")
        if not scope_sensors:
            return True
        return sensor_id in scope_sensors

    @classmethod
    async def evaluate_reading(
        cls,
        db: AsyncSession,
        reading: Reading
    ) -> list[int]:
        """Evaluates a reading against all matching enabled rules. Returns list of alert IDs triggered."""
        stmt = select(AlertRule).where(
            and_(
                AlertRule.metric_type == reading.metric_type,
                AlertRule.enabled == True
            )
        )
        result = await db.execute(stmt)
        rules = result.scalars().all()

        triggered_alert_ids = []

        for rule in rules:
            if not cls.matches_scope(rule, reading.sensor_id):
                continue

            if rule.condition_kind == "threshold":
                if cls.compare(reading.numeric_value, rule.operator, rule.threshold_value):
                    message = (
                        f"Threshold breached: {rule.name}. "
                        f"Observed value {reading.numeric_value} {rule.operator} {rule.threshold_value} "
                        f"on sensor {reading.sensor_id}."
                    )
                    alert = await AlertService.create_or_update_alert(
                        db=db,
                        rule_id=rule.id,
                        sensor_id=reading.sensor_id,
                        severity=rule.severity,
                        observed_value=reading.numeric_value,
                        message=message
                    )
                    triggered_alert_ids.append(alert.id)

            elif rule.condition_kind == "window":
                window_secs = rule.window_seconds or 600
                start_time = reading.event_timestamp - timedelta(seconds=window_secs)

                # Query aggregate from readings table within the window
                agg_type = (rule.aggregation or "avg").lower()
                if agg_type == "avg":
                    agg_func = func.avg(Reading.numeric_value)
                elif agg_type == "min":
                    agg_func = func.min(Reading.numeric_value)
                elif agg_type == "max":
                    agg_func = func.max(Reading.numeric_value)
                elif agg_type == "count":
                    agg_func = func.count(Reading.id)
                else:
                    continue

                agg_stmt = select(agg_func).where(
                    and_(
                        Reading.sensor_id == reading.sensor_id,
                        Reading.metric_type == reading.metric_type,
                        Reading.event_timestamp >= start_time,
                        Reading.event_timestamp <= reading.event_timestamp
                    )
                )
                agg_res = await db.execute(agg_stmt)
                agg_value = agg_res.scalar()

                if agg_value is not None:
                    agg_float = float(agg_value)
                    if cls.compare(agg_float, rule.operator, rule.threshold_value):
                        message = (
                            f"Time-window breached: {rule.name}. "
                            f"{agg_type.upper()} over {window_secs}s was {agg_float:.2f} "
                            f"{rule.operator} {rule.threshold_value} on sensor {reading.sensor_id}."
                        )
                        alert = await AlertService.create_or_update_alert(
                            db=db,
                            rule_id=rule.id,
                            sensor_id=reading.sensor_id,
                            severity=rule.severity,
                            observed_value=agg_float,
                            message=message
                        )
                        triggered_alert_ids.append(alert.id)

        return triggered_alert_ids
