import logging
from typing import Any

import httpx

from shared.cache import CacheClient
from shared.exceptions import RouteNotFoundException
from shared.schemas import RouteResponse

logger = logging.getLogger(__name__)

OSRM_URL = "http://router.project-osrm.org/route/v1/driving"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "TrafficBook/1.0 (trafficbook@example.com)"
GEOCODE_CACHE_TTL = 3600  # 1 hour


class RoutingService:
    def __init__(self, cache: CacheClient) -> None:
        self._cache = cache

    async def get_route(self, origin: str, dest: str) -> RouteResponse:
        origin_lon, origin_lat = await self.geocode(origin)
        dest_lon, dest_lat = await self.geocode(dest)

        coordinates = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        url = f"{OSRM_URL}/{coordinates}?steps=true&overview=false"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise RouteNotFoundException(f"No route found between {origin} and {dest}")

        route = data["routes"][0]
        distance_m: float = route.get("distance", 0.0)
        duration_s: float = route.get("duration", 0.0)

        segments: list[str] = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                name = step.get("name", "").strip()
                if name and name not in segments:
                    segments.append(name)

        return RouteResponse(
            origin=origin,
            dest=dest,
            segments=segments,
            distance_m=distance_m,
            duration_s=duration_s,
        )

    async def geocode(self, place: str) -> tuple[float, float]:
        cache_key = f"geocode:{place}"
        cached = self._cache.get(cache_key)
        if cached:
            lon, lat = cached.split(",")
            return float(lon), float(lat)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": place, "format": "json", "limit": 1},
                headers={"User-Agent": NOMINATIM_USER_AGENT},
            )
            resp.raise_for_status()
            results = resp.json()

        if not results:
            raise RouteNotFoundException(f"Could not geocode: {place}")

        lon = float(results[0]["lon"])
        lat = float(results[0]["lat"])
        self._cache.set(cache_key, f"{lon},{lat}", GEOCODE_CACHE_TTL)
        return lon, lat
