from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Boolean, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class AlertRule(Base, TimestampMixin):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    
    # Sensor scope: {"sensorIds": ["library-floor-2"]} or empty for all sensors
    sensor_scope: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    condition_kind: Mapped[str] = mapped_column(String(32), default="threshold", nullable=False) # "threshold" | "window"
    operator: Mapped[str] = mapped_column(String(8), nullable=False) # ">", "<", ">=", "<=", "=="
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Window aggregation
    window_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aggregation: Mapped[Optional[str]] = mapped_column(String(16), nullable=True) # "avg", "min", "max", "count"
    
    severity: Mapped[str] = mapped_column(String(16), default="high", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizers.id"), nullable=True)
