from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class JourneyStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    AUTHORITY_CANCELLED = "AUTHORITY_CANCELLED"


class JourneyCreate(BaseModel):
    driver_id: str
    origin: str
    destination: str
    start_time: datetime
    region: str = "EU"

    @field_validator("start_time")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        # Normalize to UTC-aware for comparison
        if v.tzinfo is None:
            from datetime import timezone as tz
            v = v.replace(tzinfo=tz.utc)
        if v <= now:
            raise ValueError("start_time must be in the future")
        return v


class JourneyResponse(BaseModel):
    id: str
    driver_id: str
    origin: str
    destination: str
    start_time: datetime
    status: str
    region: str
    is_cross_region: bool
    route_segments: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConflictCheckRequest(BaseModel):
    origin: str
    dest: str
    start_time: str
    segments: list[str] = []


class ConflictCheckResponse(BaseModel):
    conflict: bool
    reason: str | None = None


class RouteRequest(BaseModel):
    origin: str
    dest: str


class RouteResponse(BaseModel):
    origin: str
    dest: str
    segments: list[str]
    distance_m: float
    duration_s: float


class HealthResponse(BaseModel):
    service: str
    status: str
    region: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    error: str
    message: str


class RoadClosureCreate(BaseModel):
    road_name: str
    reason: str | None = None
    region: str


class RoadClosureResponse(BaseModel):
    id: str
    road_name: str
    region: str
    reason: str | None
    active: bool
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
