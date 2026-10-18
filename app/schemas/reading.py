from datetime import datetime, timezone
import math
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from app.config import settings


class ReadingCreate(BaseModel):
    sensor_id: str = Field(..., alias="sensorId", min_length=1, max_length=64)
    metric_type: str = Field(..., alias="type", min_length=1, max_length=32)
    value: float
    timestamp: datetime
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey", max_length=128)

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "sensorId": "library-floor-2",
                "type": "temperature",
                "value": 34.5,
                "timestamp": "2026-10-12T10:30:00Z"
            }
        }
    }

    @field_validator("value")
    @classmethod
    def validate_finite_number(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Numeric value must be finite (not NaN or Inf)")
        return v

    @field_validator("metric_type")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        clean_v = v.strip().lower()
        if clean_v not in settings.SUPPORTED_METRIC_TYPES:
            raise ValueError(
                f"Unsupported metric type '{v}'. Allowed types: {', '.join(settings.SUPPORTED_METRIC_TYPES)}"
            )
        return clean_v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_skew(cls, v: datetime) -> datetime:
        # Normalize to UTC
        if v.tzinfo is None:
            raise ValueError("Timestamp must include timezone information (e.g. 'Z' or '+00:00')")
        
        utc_ts = v.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        diff_seconds = (utc_ts - now).total_seconds()

        if diff_seconds > settings.MAX_FUTURE_SKEW_SECONDS:
            raise ValueError(
                f"Timestamp {v} is too far in the future (exceeds {settings.MAX_FUTURE_SKEW_SECONDS}s)"
            )
        if diff_seconds < -settings.MAX_PAST_SKEW_SECONDS:
            raise ValueError(
                f"Timestamp {v} is too far in the past (exceeds {settings.MAX_PAST_SKEW_SECONDS}s)"
            )
        return utc_ts


class BatchReadingItemError(BaseModel):
    index: int
    error: str
    item: Optional[dict[str, Any]] = None


class BatchReadingResponse(BaseModel):
    accepted: int
    rejected: int
    total: int
    errors: list[BatchReadingItemError] = Field(default_factory=list)


class ReadingOut(BaseModel):
    id: int
    sensor_id: str
    metric_type: str
    numeric_value: float
    event_timestamp: datetime
    received_at: datetime
    idempotency_key: Optional[str] = None

    model_config = {"from_attributes": True}
