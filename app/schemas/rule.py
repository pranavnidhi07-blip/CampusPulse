from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.config import settings


class RuleCondition(BaseModel):
    kind: Literal["threshold", "window"] = "threshold"
    operator: Literal[">", "<", ">=", "<=", "=="]
    value: float
    aggregation: Optional[Literal["avg", "min", "max", "count"]] = None
    window_seconds: Optional[int] = Field(None, alias="windowSeconds", ge=5, le=86400)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_window_params(self) -> "RuleCondition":
        if self.kind == "window":
            if not self.aggregation:
                raise ValueError("aggregation ('avg', 'min', 'max', 'count') is required for window rules")
            if not self.window_seconds:
                raise ValueError("windowSeconds (e.g. 600) is required for window rules")
        return self


class RuleScope(BaseModel):
    sensor_ids: Optional[list[str]] = Field(None, alias="sensorIds")

    model_config = {"populate_by_name": True}


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    metric_type: str = Field(..., alias="metricType")
    scope: Optional[RuleScope] = None
    condition: RuleCondition
    severity: Literal["info", "warning", "high", "critical"] = "high"
    enabled: bool = True

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "name": "Library high temperature",
                "metricType": "temperature",
                "scope": {"sensorIds": ["library-floor-2"]},
                "condition": {
                    "kind": "threshold",
                    "operator": ">",
                    "value": 32.0
                },
                "severity": "high",
                "enabled": True
            }
        }
    }

    @field_validator("metric_type")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        clean_v = v.strip().lower()
        if clean_v not in settings.SUPPORTED_METRIC_TYPES:
            raise ValueError(f"Unsupported metric type '{v}'")
        return clean_v


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    metric_type: Optional[str] = Field(None, alias="metricType")
    scope: Optional[RuleScope] = None
    condition: Optional[RuleCondition] = None
    severity: Optional[Literal["info", "warning", "high", "critical"]] = None
    enabled: Optional[bool] = None

    model_config = {"populate_by_name": True}


class RuleOut(BaseModel):
    id: int
    name: str
    metric_type: str = Field(..., alias="metricType")
    scope: Optional[RuleScope] = None
    condition: RuleCondition
    severity: str
    enabled: bool
    version: int
    created_at: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}
