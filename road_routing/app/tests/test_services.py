from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.exceptions import RouteNotFoundException
from app.services.routing_service import RoutingService
from app.tests.conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
async def test_route_geocoding_cache_hit(mock_cache):
    mock_cache.set("geocode:Dublin", "10.5,-53.3")
    service = RoutingService(cache=mock_cache)

    with patch("app.services.routing_service.httpx.AsyncClient") as mock_http:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(
            return_value={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 100000.0,
                        "duration": 3600.0,
                        "legs": [{"steps": [{"name": "Main Street"}]}],
                    }
                ],
            }
        )
        mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        mock_cache.set("geocode:Cork", "12.0,-51.0")
        result = await service.get_route("Dublin", "Cork")

    assert result.origin == "Dublin"
    assert result.dest == "Cork"
    assert result.distance_m == 100000.0


@pytest.mark.asyncio
async def test_geocode_not_found(mock_cache):
    service = RoutingService(cache=mock_cache)

    with patch("app.services.routing_service.httpx.AsyncClient") as mock_http:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=[])
        mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        with pytest.raises(RouteNotFoundException):
            await service.geocode("NonExistentPlace123")
