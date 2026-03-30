import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser, require_role
from shared.database import get_db
from shared.schemas import JourneyResponse, RoadClosureCreate, RoadClosureResponse

from app.services.authority_service import AuthorityService

logger = logging.getLogger(__name__)
router = APIRouter()

AuthorityUser = Annotated[CurrentUser, Depends(require_role("traffic_authority", "admin"))]
AdminUser = Annotated[CurrentUser, Depends(require_role("admin"))]


def get_authority_service(db: AsyncSession = Depends(get_db)) -> AuthorityService:
    from app.repositories.authority_repo import AuthorityRepository
    repo = AuthorityRepository()
    return AuthorityService(repo=repo, db=db)


@router.get("/journeys", response_model=list[JourneyResponse])
async def list_journeys(
    current_user: AuthorityUser,
    service: AuthorityService = Depends(get_authority_service),
    region: str | None = Query(default=None),
    status: str | None = Query(default=None),
    road: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JourneyResponse]:
    journeys = await service.list_journeys(
        region=region, status=status, road=road, limit=limit, offset=offset
    )
    return [JourneyResponse.model_validate(j) for j in journeys]


@router.post("/cancel/{journey_id}", response_model=JourneyResponse)
async def force_cancel(
    journey_id: str,
    current_user: AuthorityUser,
    service: AuthorityService = Depends(get_authority_service),
    reason: str = Body(..., embed=True),
) -> JourneyResponse:
    journey = await service.force_cancel(journey_id, current_user, reason)
    return JourneyResponse.model_validate(journey)


@router.post("/closure", response_model=RoadClosureResponse, status_code=201)
async def create_closure(
    data: RoadClosureCreate,
    current_user: AuthorityUser,
    service: AuthorityService = Depends(get_authority_service),
) -> RoadClosureResponse:
    closure = await service.create_closure(data, current_user)
    return RoadClosureResponse.model_validate(closure)


@router.get("/stats")
async def get_stats(
    current_user: AuthorityUser,
    service: AuthorityService = Depends(get_authority_service),
) -> dict:
    return await service.get_stats()


@router.delete("/closure/{closure_id}", status_code=204)
async def remove_closure(
    closure_id: str,
    current_user: AdminUser,
    service: AuthorityService = Depends(get_authority_service),
) -> None:
    await service.remove_closure(closure_id, current_user)
