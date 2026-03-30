import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from shared.auth import CurrentUser, get_current_user
from shared.schemas import RouteRequest, RouteResponse

from app.services.routing_service import RoutingService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_routing_service() -> RoutingService:
    from app.config import get_settings
    from shared.cache import CacheClient

    settings = get_settings()
    cache = CacheClient(settings.redis_url)
    return RoutingService(cache=cache)


@router.post("/route", response_model=RouteResponse)
async def get_route(
    request: RouteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: RoutingService = Depends(get_routing_service),
) -> RouteResponse:
    return await service.get_route(request.origin, request.dest)
