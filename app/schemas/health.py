from datetime import datetime
from pydantic import BaseModel


class HealthLiveResponse(BaseModel):
    status: str = "ok"


class HealthReadyResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
