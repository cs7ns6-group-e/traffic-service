import logging
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser
from shared.exceptions import (
    ForbiddenException,
    JourneyConflictException,
    JourneyNotFoundException,
    RegionUnavailableException,
)
from shared.messaging import BookingEvent, EventPublisher
from shared.models import Journey
from shared.schemas import ConflictCheckRequest, JourneyCreate

from app.repositories.journey_repo import JourneyRepository

logger = logging.getLogger(__name__)

REGION_PREFIXES: dict[str, list[str]] = {
    "EU": ["Dublin", "Cork", "London", "Paris", "Berlin", "Madrid", "Rome", "Amsterdam"],
    "US": ["New York", "Boston", "Chicago", "Los Angeles", "Houston", "Miami"],
    "APAC": ["Tokyo", "Osaka", "Singapore", "Sydney", "Seoul", "Beijing", "Shanghai"],
}


def detect_region(place: str) -> str:
    for region, prefixes in REGION_PREFIXES.items():
        if any(prefix.lower() in place.lower() for prefix in prefixes):
            return region
    return "EU"


class JourneyService:
    def __init__(
        self,
        repo: JourneyRepository,
        db: AsyncSession,
        conflict_service_url: str,
        routing_service_url: str,
        publisher: EventPublisher,
        region: str,
    ) -> None:
        self._repo = repo
        self._db = db
        self._conflict_url = conflict_service_url
        self._routing_url = routing_service_url
        self._publisher = publisher
        self._region = region

    async def book(self, data: JourneyCreate, user: CurrentUser) -> Journey:
        origin_region = detect_region(data.origin)
        dest_region = detect_region(data.destination)
        is_cross_region = origin_region != dest_region

        # Get route segments
        segments: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._routing_url}/route",
                    json={"origin": data.origin, "dest": data.destination},
                )
                resp.raise_for_status()
                route_data = resp.json()
                segments = route_data.get("segments", [])
        except Exception as exc:
            logger.warning("Routing service unavailable, proceeding without segments: %s", exc)

        # Check conflicts
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._conflict_url}/check",
                    json=ConflictCheckRequest(
                        origin=data.origin,
                        dest=data.destination,
                        start_time=data.start_time.isoformat(),
                        segments=segments,
                    ).model_dump(),
                )
                resp.raise_for_status()
                conflict_data = resp.json()
                if conflict_data.get("conflict"):
                    raise JourneyConflictException(
                        conflict_data.get("reason", "Journey slot conflict")
                    )
        except JourneyConflictException:
            raise
        except Exception as exc:
            logger.warning("Conflict detection unavailable, proceeding: %s", exc)

        # Notify cross-region destination
        if is_cross_region:
            await self._notify_cross_region(data, dest_region, segments)

        journey = Journey(
            driver_id=data.driver_id,
            origin=data.origin,
            destination=data.destination,
            start_time=data.start_time,
            status="CONFIRMED",
            region=origin_region,
            route_segments=segments,
            is_cross_region=is_cross_region,
            dest_region=dest_region if is_cross_region else None,
        )
        journey = await self._repo.create(self._db, journey)

        event: BookingEvent = {
            "journey_id": journey.id,
            "driver_id": journey.driver_id,
            "status": "CONFIRMED",
            "region": journey.region,
            "is_cross_region": is_cross_region,
        }
        try:
            self._publisher.publish("booking_events", dict(event))
        except Exception as exc:
            logger.warning("Failed to publish booking event: %s", exc)

        return journey

    async def get(self, journey_id: str, user: CurrentUser) -> Journey:
        journey = await self._repo.get_by_id(self._db, journey_id)
        if not journey:
            raise JourneyNotFoundException(f"Journey {journey_id} not found")
        if not user.is_admin() and journey.driver_id != user.id:
            raise ForbiddenException("You do not have access to this journey")
        return journey

    async def cancel(self, journey_id: str, user: CurrentUser) -> Journey:
        journey = await self._repo.get_by_id(self._db, journey_id)
        if not journey:
            raise JourneyNotFoundException(f"Journey {journey_id} not found")
        if not user.is_admin() and journey.driver_id != user.id:
            raise ForbiddenException("You can only cancel your own journeys")

        journey = await self._repo.update_status(self._db, journey_id, "CANCELLED")

        event: BookingEvent = {
            "journey_id": journey.id,
            "driver_id": journey.driver_id,
            "status": "CANCELLED",
            "region": journey.region,
            "is_cross_region": journey.is_cross_region,
        }
        try:
            self._publisher.publish("booking_events", dict(event))
        except Exception as exc:
            logger.warning("Failed to publish cancellation event: %s", exc)

        return journey

    async def list_for_driver(self, driver_id: str, user: CurrentUser) -> list[Journey]:
        if not user.is_admin() and driver_id != user.id:
            raise ForbiddenException("You can only view your own journeys")
        return await self._repo.get_by_driver(self._db, driver_id)

    async def _notify_cross_region(
        self, data: JourneyCreate, dest_region: str, segments: list[str]
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        region_url_map = {
            "US": settings.region_us_url,
            "APAC": settings.region_apac_url,
        }
        url = region_url_map.get(dest_region)
        if not url:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{url}/conflicts/cross-region",
                    json={
                        "origin": data.origin,
                        "dest": data.destination,
                        "start_time": data.start_time.isoformat(),
                        "from_region": self._region,
                    },
                )
        except Exception as exc:
            logger.warning("Cross-region notification failed for %s: %s", dest_region, exc)
