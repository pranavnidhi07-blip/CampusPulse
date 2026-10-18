from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, utc_now


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    deduplication_key: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True, nullable=False)  # open, acknowledged, resolved
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizers.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizers.id"), nullable=True)

    __table_args__ = (
        Index("idx_alerts_status_triggered", "status", "triggered_at"),
        Index(
            "idx_unique_active_alert_per_episode",
            "rule_id",
            "sensor_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'acknowledged')"),
            sqlite_where=text("status IN ('open', 'acknowledged')")
        ),
    )
