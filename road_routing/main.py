import os
import json
import redis as redis_lib
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI(title="road_routing")

REGION = os.getenv("REGION", "EU")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

try:
    redis_client = redis_lib.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )
except Exception:
    redis_client = None

FAMOUS_ROUTES = [
    {"id": "eu-1", "name": "Dublin to Cork",
     "origin": "Dublin, Ireland", "destination": "Cork, Ireland",
     "region": "EU", "distance_km": 256, "duration_mins": 165},
    {"id": "eu-2", "name": "Dublin to Belfast",
     "origin": "Dublin, Ireland", "destination": "Belfast, Northern Ireland",
     "region": "EU", "distance_km": 167, "duration_mins": 105},
    {"id": "eu-3", "name": "London to Manchester",
     "origin": "London, UK", "destination": "Manchester, UK",
     "region": "EU", "distance_km": 335, "duration_mins": 195},
    {"id": "eu-4", "name": "Paris to Lyon",
     "origin": "Paris, France", "destination": "Lyon, France",
     "region": "EU", "distance_km": 465, "duration_mins": 270},
    {"id": "eu-5", "name": "Amsterdam to Brussels",
     "origin": "Amsterdam, Netherlands", "destination": "Brussels, Belgium",
     "region": "EU", "distance_km": 210, "duration_mins": 130},
    {"id": "us-1", "name": "New York to Boston",
     "origin": "New York, USA", "destination": "Boston, USA",
     "region": "US", "distance_km": 346, "duration_mins": 215},
    {"id": "us-2", "name": "LA to San Francisco",
     "origin": "Los Angeles, USA", "destination": "San Francisco, USA",
     "region": "US", "distance_km": 616, "duration_mins": 360},
    {"id": "us-3", "name": "Chicago to Detroit",
     "origin": "Chicago, USA", "destination": "Detroit, USA",
     "region": "US", "distance_km": 457, "duration_mins": 270},
    {"id": "apac-1", "name": "Singapore to KL",
     "origin": "Singapore", "destination": "Kuala Lumpur, Malaysia",
     "region": "APAC", "distance_km": 350, "duration_mins": 240},
    {"id": "apac-2", "name": "Tokyo to Osaka",
     "origin": "Tokyo, Japan", "destination": "Osaka, Japan",
     "region": "APAC", "distance_km": 508, "duration_mins": 300},
    {"id": "apac-3", "name": "Sydney to Melbourne",
     "origin": "Sydney, Australia", "destination": "Melbourne, Australia",
     "region": "APAC", "distance_km": 878, "duration_mins": 540},
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
HEADERS = {"User-Agent": "TrafficBook/1.0"}


class RouteRequest(BaseModel):
    origin: str
    destination: str


def extract_segments(route_data: dict) -> List[str]:
    """Extract clean named road segments from OSRM steps."""
    seen: set = set()
    segments: List[str] = []
    steps = (
        route_data.get("routes", [{}])[0]
        .get("legs", [{}])[0]
        .get("steps", [])
    )
    for step in steps:
        name = step.get("name", "").strip()
        if (
            name
            and name.lower() not in ("", "unnamed road")
            and len(name) > 1
            and name not in seen
        ):
            seen.add(name)
            segments.append(name.title())
        if len(segments) >= 20:
            break
    return segments


async def geocode(place: str) -> tuple:
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        r = await client.get(NOMINATIM_URL, params={"q": place, "format": "json", "limit": 1})
        data = r.json()
        if not data:
            raise HTTPException(404, f"Cannot geocode: {place}")
        return float(data[0]["lon"]), float(data[0]["lat"])


@app.get("/search")
async def search_places(q: str, limit: int = 5):
    """Nominatim autocomplete with 24-hour Redis cache."""
    cache_key = f"nominatim:{q.lower()}:{limit}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            r = await client.get(NOMINATIM_URL, params={
                "q": q,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
            })
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"Nominatim error: {e}")

    results = []
    for item in data:
        addr = item.get("address", {})
        name_parts = []
        for key in ("city", "town", "village", "county", "state", "country"):
            val = addr.get(key)
            if val and val not in name_parts:
                name_parts.append(val)
        display = item.get("display_name", q)
        results.append({
            "name": ", ".join(name_parts[:3]) if name_parts else display,
            "display_name": display,
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "type": item.get("type", "place"),
        })

    if redis_client:
        try:
            redis_client.setex(cache_key, 86400, json.dumps(results))
        except Exception:
            pass

    return results


@app.post("/route")
async def get_route(req: RouteRequest):
    try:
        orig_lon, orig_lat = await geocode(req.origin)
        dest_lon, dest_lat = await geocode(req.destination)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{OSRM_URL}/{orig_lon},{orig_lat};{dest_lon},{dest_lat}",
                params={"overview": "full", "geometries": "geojson", "steps": "true"},
            )
            data = r.json()
        if data.get("code") != "Ok":
            raise HTTPException(500, "OSRM routing failed")
        route = data["routes"][0]
        segments = extract_segments(data)
        distance_m = route.get("distance", 0)
        duration_s = route.get("duration", 0)
        return {
            "origin": req.origin,
            "destination": req.destination,
            "segments": segments,
            "distance_m": distance_m,
            "duration_s": duration_s,
            "distance_km": round(distance_m / 1000, 2) if distance_m else 0,
            "duration_mins": int(duration_s / 60) if duration_s else 0,
            "coordinates": route.get("geometry", {}).get("coordinates", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Routing error: {str(e)}")


@app.get("/routes/famous")
def famous_routes():
    return FAMOUS_ROUTES


@app.get("/health")
def health():
    return {"status": "ok", "service": "road_routing", "region": REGION}
