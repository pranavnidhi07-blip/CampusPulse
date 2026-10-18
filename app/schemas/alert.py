from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    id: int
    rule_id: int
    sensor_id: str
    severity: str
    status: str
    observed_value: float
    message: str
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None

    model_config = {"from_attributes": True}


class AlertActionResponse(BaseModel):
    alert: AlertOut
    message: str
