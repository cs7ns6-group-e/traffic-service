import os
import uuid
import time
import threading
from datetime import datetime

import httpx
import psycopg2
import aio_pika
import asyncio
import json
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="journey_booking")

REGION = os.getenv("REGION", "EU")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
CONFLICT_URL = os.getenv("CONFLICT_URL", "http://conflict_detection:8002")
ROUTING_URL = os.getenv("ROUTING_URL", "http://road_routing:8004")
REGION_US_URL = os.getenv("REGION_US_URL", "http://10.0.4.11")
REGION_APAC_URL = os.getenv("REGION_APAC_URL", "http://10.0.3.11")
REGION_EU_URL = os.getenv("REGION_EU_URL", "http://10.0.1.11")

REGION_URL_MAP = {
    "EU": REGION_EU_URL,
    "US": REGION_US_URL,
    "APAC": REGION_APAC_URL,
}

EU_KEYWORDS = [
    "dublin", "london", "paris", "berlin", "amsterdam", "brussels",
    "cork", "belfast", "manchester", "lyon", "frankfurt", "madrid",
    "rome", "vienna", "warsaw", "prague", "budapest", "ireland",
    "uk", "france", "germany", "netherlands", "belgium", "europe",
]
US_KEYWORDS = [
    "new york", "los angeles", "chicago", "boston", "houston", "seattle",
    "miami", "denver", "atlanta", "san francisco", "washington", "toronto",
    "vancouver", "montreal", "detroit", "usa", "america", "united states",
    "canada", "california", "texas", "florida",
]
APAC_KEYWORDS = [
    "singapore", "tokyo", "osaka", "sydney", "melbourne", "kuala lumpur",
    "bangkok", "hong kong", "taipei", "seoul", "mumbai", "delhi",
    "beijing", "shanghai", "jakarta", "japan", "australia", "malaysia",
    "india", "china", "korea", "thailand", "taiwan", "asia",
]


def detect_region(location: str) -> str:
    loc = location.lower()
    if any(k in loc for k in US_KEYWORDS):
        return "US"
    if any(k in loc for k in APAC_KEYWORDS):
        return "APAC"
    if any(k in loc for k in EU_KEYWORDS):
        return "EU"
    return REGION


def extract_segments(route_data: dict) -> List[str]:
    """Extract clean named road segments from OSRM response."""
    seen = set()
    segments = []
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


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS journeys (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_id       TEXT NOT NULL,
            origin          TEXT NOT NULL,
            destination     TEXT NOT NULL,
            start_time      TIMESTAMP NOT NULL,
            status          TEXT DEFAULT 'PENDING',
            region          TEXT NOT NULL,
            dest_region     TEXT,
            is_cross_region BOOLEAN DEFAULT FALSE,
            vehicle_type    TEXT DEFAULT 'STANDARD',
            route_segments  JSONB DEFAULT '[]',
            route_id        TEXT,
            distance_km     FLOAT,
            duration_mins   INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS cross_region_events (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            journey_id  UUID REFERENCES journeys(id),
            from_region TEXT NOT NULL,
            to_region   TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            delivered   BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE journeys ADD COLUMN IF NOT EXISTS distance_km FLOAT;
        ALTER TABLE journeys ADD COLUMN IF NOT EXISTS duration_mins INTEGER;
        ALTER TABLE journeys ADD COLUMN IF NOT EXISTS cancelled_reason TEXT;
    """)
    conn.commit()
    cur.close()
    conn.close()


def expire_pending_journeys():
    """Background thread: auto-cancel PENDING journeys older than 5 minutes."""
    while True:
        time.sleep(60)
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                UPDATE journeys
                SET status = 'CANCELLED',
                    cancelled_reason = 'Auto-expired: not confirmed within 5 minutes'
                WHERE status = 'PENDING'
                AND created_at < NOW() - INTERVAL '5 minutes'
            """)
            expired = cur.rowcount
            conn.commit()
            if expired > 0:
                print(f"Auto-expired {expired} pending journeys")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Expire error: {e}")


@app.on_event("startup")
def startup():
    init_db()
    threading.Thread(target=expire_pending_journeys, daemon=True).start()


# ── Auth ──────────────────────────────────────────────────────────────────────

def verify_token(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


async def publish_event(queue_name: str, payload: dict):
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(queue_name, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload, default=str).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=queue_name,
            )
    except Exception as e:
        print(f"RabbitMQ publish error: {e}")


# ── Schemas ───────────────────────────────────────────────────────────────────

class JourneyRequest(BaseModel):
    origin: str
    destination: str
    start_time: str
    route_id: Optional[str] = None


class CrossRegionRequest(BaseModel):
    journey_id: str
    origin: str
    destination: str
    start_time: str
    driver_id: str
    from_region: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/journeys", status_code=201)
async def book_journey(req: JourneyRequest, user: dict = Depends(verify_token)):
    driver_id = user["sub"]
    driver_email = user.get("email", driver_id)
    vehicle_type = user.get("vehicle_type", "STANDARD")
    start_time = datetime.fromisoformat(req.start_time)

    # Emergency: skip all checks, instant confirm
    if vehicle_type == "EMERGENCY":
        conn = get_conn()
        cur = conn.cursor()
        journey_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO journeys (id, driver_id, origin, destination, start_time, "
            "status, region, vehicle_type, route_segments) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (journey_id, driver_id, req.origin, req.destination, start_time,
             "EMERGENCY_CONFIRMED", REGION, vehicle_type, json.dumps([])),
        )
        conn.commit()
        cur.close()
        conn.close()
        await publish_event("emergency_events", {
            "journey_id": journey_id,
            "origin": req.origin,
            "destination": req.destination,
            "driver_id": driver_id,
            "region": REGION,
            "vehicle_type": "EMERGENCY",
        })
        return {
            "id": journey_id,
            "status": "EMERGENCY_CONFIRMED",
            "origin": req.origin,
            "destination": req.destination,
            "start_time": req.start_time,
            "vehicle_type": "EMERGENCY",
            "region": REGION,
            "dest_region": None,
            "is_cross_region": False,
            "route_segments": [],
            "distance_km": None,
            "duration_mins": None,
            "created_at": datetime.utcnow().isoformat(),
        }

    # Get route
    route_segments = []
    distance_km = None
    duration_mins = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{ROUTING_URL}/route",
                                  json={"origin": req.origin, "destination": req.destination})
            if r.status_code == 200:
                route_data = r.json()
                route_segments = extract_segments(route_data)
                raw_dist = route_data.get("distance_m", 0)
                raw_dur = route_data.get("duration_s", 0)
                if raw_dist:
                    distance_km = round(raw_dist / 1000, 2)
                if raw_dur:
                    duration_mins = int(raw_dur / 60)
    except Exception as e:
        print(f"Routing error: {e}")

    # Conflict detection — scoped to this driver
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{CONFLICT_URL}/check", json={
                "origin": req.origin,
                "destination": req.destination,
                "start_time": req.start_time,
                "segments": route_segments,
                "vehicle_type": vehicle_type,
                "driver_id": driver_email,
            })
            if r.status_code == 200 and r.json().get("conflict"):
                raise HTTPException(409, r.json().get("reason", "Journey conflict detected"))
    except HTTPException:
        raise
    except Exception:
        pass

    # Detect regions
    dest_region = detect_region(req.destination)
    is_cross_region = dest_region != REGION

    conn = get_conn()
    cur = conn.cursor()
    journey_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO journeys (id, driver_id, origin, destination, start_time, "
        "status, region, dest_region, is_cross_region, vehicle_type, route_segments, "
        "route_id, distance_km, duration_mins) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, created_at",
        (journey_id, driver_id, req.origin, req.destination, start_time,
         "CONFIRMED", REGION, dest_region, is_cross_region, vehicle_type,
         json.dumps(route_segments), req.route_id, distance_km, duration_mins),
    )
    row = cur.fetchone()
    created_at = row[1] if row else datetime.utcnow()
    conn.commit()
    cur.close()
    conn.close()

    # Cross-region: notify destination VM
    if is_cross_region and dest_region in REGION_URL_MAP:
        try:
            dest_url = REGION_URL_MAP[dest_region]
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{dest_url}:8001/journeys/cross-region", json={
                    "journey_id": journey_id,
                    "origin": req.origin,
                    "destination": req.destination,
                    "start_time": req.start_time,
                    "driver_id": driver_id,
                    "from_region": REGION,
                })
        except Exception as e:
            print(f"Cross-region call failed: {e}")

    # Publish booking event
    await publish_event("booking_events", {
        "journey_id": journey_id,
        "origin": req.origin,
        "destination": req.destination,
        "start_time": req.start_time,
        "status": "CONFIRMED",
        "driver_id": driver_id,
        "region": REGION,
        "is_cross_region": is_cross_region,
        "dest_region": dest_region,
    })

    return {
        "id": journey_id,
        "origin": req.origin,
        "destination": req.destination,
        "start_time": req.start_time,
        "status": "CONFIRMED",
        "region": REGION,
        "dest_region": dest_region,
        "is_cross_region": is_cross_region,
        "vehicle_type": vehicle_type,
        "route_segments": route_segments,
        "distance_km": distance_km,
        "duration_mins": duration_mins,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
    }


@app.post("/journeys/cross-region", status_code=201)
def cross_region(req: CrossRegionRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        start_time = datetime.fromisoformat(req.start_time)
        cur.execute(
            "INSERT INTO journeys (id, driver_id, origin, destination, start_time, "
            "status, region, is_cross_region, vehicle_type, route_segments) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            (req.journey_id, req.driver_id, req.origin, req.destination,
             start_time, "CONFIRMED", REGION, True, "STANDARD", json.dumps([])),
        )
        if cur.rowcount > 0:
            cur.execute(
                "INSERT INTO cross_region_events (journey_id, from_region, to_region, event_type) "
                "VALUES (%s,%s,%s,%s)",
                (req.journey_id, req.from_region, REGION, "arrival"),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return {"status": "registered", "journey_id": req.journey_id}


@app.delete("/journeys/{journey_id}")
async def cancel_journey(journey_id: str, user: dict = Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT driver_id, origin, destination FROM journeys WHERE id = %s",
        (journey_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(404, "Journey not found")
    if row[0] != user["sub"] and user.get("role") not in ("admin", "traffic_authority"):
        cur.close()
        conn.close()
        raise HTTPException(403, "Cannot cancel another driver's journey")
    cur.execute("UPDATE journeys SET status='CANCELLED' WHERE id = %s", (journey_id,))
    conn.commit()
    cur.close()
    conn.close()
    await publish_event("journey_cancelled_events", {
        "journey_id": journey_id,
        "origin": row[1],
        "destination": row[2],
        "reason": "Cancelled by driver",
    })
    return {"status": "CANCELLED", "id": journey_id}


@app.get("/journeys/{journey_id}")
def get_journey(journey_id: str, user: dict = Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, driver_id, origin, destination, start_time, status, region, "
        "dest_region, is_cross_region, vehicle_type, route_segments, route_id, "
        "distance_km, duration_mins, created_at "
        "FROM journeys WHERE id = %s",
        (journey_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(404, "Journey not found")
    cols = ["id", "driver_id", "origin", "destination", "start_time",
            "status", "region", "dest_region", "is_cross_region",
            "vehicle_type", "route_segments", "route_id",
            "distance_km", "duration_mins", "created_at"]
    return dict(zip(cols, row))


@app.get("/journeys")
def list_journeys(driver_id: Optional[str] = None, user: dict = Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    cols = ["id", "driver_id", "origin", "destination", "start_time",
            "status", "region", "dest_region", "is_cross_region",
            "vehicle_type", "route_segments", "route_id",
            "distance_km", "duration_mins", "created_at"]
    select = (
        "SELECT id, driver_id, origin, destination, start_time, status, region, "
        "dest_region, is_cross_region, vehicle_type, route_segments, route_id, "
        "distance_km, duration_mins, created_at FROM journeys"
    )
    if driver_id:
        cur.execute(select + " WHERE driver_id = %s ORDER BY created_at DESC", (driver_id,))
    else:
        cur.execute(select + " ORDER BY created_at DESC LIMIT 100")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


@app.get("/health")
def health():
    return {"status": "ok", "service": "journey_booking", "region": REGION, "replicas": 2}
