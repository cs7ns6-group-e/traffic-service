import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser, get_current_user
from shared.database import get_db
from shared.schemas import JourneyCreate, JourneyResponse

from app.services.journey_service import JourneyService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_journey_service(db: AsyncSession = Depends(get_db)) -> JourneyService:
    from app.config import get_settings
    from app.repositories.journey_repo import JourneyRepository
    from shared.messaging import EventPublisher

    settings = get_settings()
    repo = JourneyRepository()
    publisher = EventPublisher(settings.rabbitmq_url)
    return JourneyService(
        repo=repo,
        db=db,
        conflict_service_url=settings.conflict_service_url,
        routing_service_url=settings.routing_service_url,
        publisher=publisher,
        region=settings.region,
    )


@router.post("", response_model=JourneyResponse, status_code=201)
async def book_journey(
    data: JourneyCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: JourneyService = Depends(get_journey_service),
) -> JourneyResponse:
    journey = await service.book(data, current_user)
    return JourneyResponse.model_validate(journey)


@router.get("/{journey_id}", response_model=JourneyResponse)
async def get_journey(
    journey_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: JourneyService = Depends(get_journey_service),
) -> JourneyResponse:
    journey = await service.get(journey_id, current_user)
    return JourneyResponse.model_validate(journey)


@router.delete("/{journey_id}", response_model=JourneyResponse)
async def cancel_journey(
    journey_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: JourneyService = Depends(get_journey_service),
) -> JourneyResponse:
    journey = await service.cancel(journey_id, current_user)
    return JourneyResponse.model_validate(journey)


@router.get("", response_model=list[JourneyResponse])
async def list_journeys(
    driver_id: Annotated[str | None, Query()] = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: JourneyService = Depends(get_journey_service),
) -> list[JourneyResponse]:
    journeys = await service.list_for_driver(driver_id or current_user.id, current_user)
    return [JourneyResponse.model_validate(j) for j in journeys]
