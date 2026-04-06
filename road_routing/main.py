import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="road_routing")

REGION = os.getenv("REGION", "EU")

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


class RouteRequest(BaseModel):
    origin: str
    destination: str


async def geocode(place: str) -> tuple[float, float]:
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "TrafficBook/1.0"}) as client:
        r = await client.get(NOMINATIM_URL, params={"q": place, "format": "json", "limit": 1})
        data = r.json()
        if not data:
            raise HTTPException(404, f"Cannot geocode: {place}")
        return float(data[0]["lon"]), float(data[0]["lat"])


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
        legs = route.get("legs", [])
        segments = []
        for leg in legs:
            for step in leg.get("steps", []):
                segments.append({
                    "name": step.get("name", ""),
                    "distance_m": step.get("distance", 0),
                    "duration_s": step.get("duration", 0),
                    "maneuver": step.get("maneuver", {}).get("type", ""),
                })
        return {
            "origin": req.origin,
            "destination": req.destination,
            "segments": segments,
            "distance_m": route.get("distance", 0),
            "duration_s": route.get("duration", 0),
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
