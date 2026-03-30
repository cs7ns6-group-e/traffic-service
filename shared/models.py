from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    driver_id: Mapped[str]
    origin: Mapped[str]
    destination: Mapped[str]
    start_time: Mapped[datetime]
    end_time: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="PENDING")
    region: Mapped[str]
    route_segments: Mapped[dict] = mapped_column(JSON, default=lambda: [])
    is_cross_region: Mapped[bool] = mapped_column(default=False)
    dest_region: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class RoadClosure(Base):
    __tablename__ = "road_closures"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    road_name: Mapped[str]
    region: Mapped[str]
    reason: Mapped[str | None] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
