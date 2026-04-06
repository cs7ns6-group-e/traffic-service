import os
import uuid
from datetime import datetime

import httpx
import psycopg2
import aio_pika
import asyncio
import json
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="journey_booking")

REGION = os.getenv("REGION", "EU")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
CONFLICT_URL = os.getenv("CONFLICT_URL", "http://conflict_detection:8002")
ROUTING_URL = os.getenv("ROUTING_URL", "http://road_routing:8004")
REGION_US_URL = os.getenv("REGION_US_URL", "http://10.0.2.11")
REGION_APAC_URL = os.getenv("REGION_APAC_URL", "http://10.0.3.11")
REGION_EU_URL = os.getenv("REGION_EU_URL", "http://10.0.1.11")

REGION_URL_MAP = {
    "EU": REGION_EU_URL,
    "US": REGION_US_URL,
    "APAC": REGION_APAC_URL,
}


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
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ── Auth ──────────────────────────────────────────────────────────────────────

def verify_token(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# ── Region detection ──────────────────────────────────────────────────────────

REGION_KEYWORDS = {
    "EU": ["ireland", "dublin", "cork", "belfast", "london", "manchester",
           "paris", "lyon", "amsterdam", "brussels", "uk", "france",
           "netherlands", "belgium", "europe"],
    "US": ["new york", "boston", "los angeles", "san francisco", "chicago",
           "detroit", "usa", "america", "united states"],
    "APAC": ["singapore", "kuala lumpur", "tokyo", "osaka", "sydney",
              "melbourne", "japan", "australia", "malaysia", "asia"],
}


def detect_region(location: str) -> str:
    loc_lower = location.lower()
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in loc_lower for kw in keywords):
            return region
    return REGION  # default to current region


async def publish_event(queue_name: str, payload: dict):
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(queue_name, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload).encode(),
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
    vehicle_type = user.get("vehicle_type", "STANDARD")
    start_time = datetime.fromisoformat(req.start_time)

    # Emergency: skip all checks, instant confirm
    if vehicle_type == "EMERGENCY":
        conn = get_conn()
        cur = conn.cursor()
        journey_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO journeys (id, driver_id, origin, destination, start_time, "
            "status, region, vehicle_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (journey_id, driver_id, req.origin, req.destination, start_time,
             "EMERGENCY_CONFIRMED", REGION, vehicle_type),
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
        return {"id": journey_id, "status": "EMERGENCY_CONFIRMED",
                "origin": req.origin, "destination": req.destination,
                "vehicle_type": "EMERGENCY", "region": REGION}

    # Get route
    route_segments = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{ROUTING_URL}/route",
                                  json={"origin": req.origin, "destination": req.destination})
            if r.status_code == 200:
                route_data = r.json()
                route_segments = route_data.get("segments", [])
    except Exception:
        pass

    # Conflict detection
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{CONFLICT_URL}/check", json={
                "origin": req.origin,
                "destination": req.destination,
                "start_time": req.start_time,
                "segments": route_segments,
                "vehicle_type": vehicle_type,
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
        "status, region, dest_region, is_cross_region, vehicle_type, route_segments, route_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (journey_id, driver_id, req.origin, req.destination, start_time,
         "CONFIRMED", REGION, dest_region, is_cross_region, vehicle_type,
         json.dumps(route_segments), req.route_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    # Cross-region: notify destination VM
    if is_cross_region and dest_region in REGION_URL_MAP:
        try:
            dest_url = REGION_URL_MAP[dest_region]
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"{dest_url}:8001/cross-region", json={
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
    }


@app.post("/cross-region", status_code=201)
def cross_region(req: CrossRegionRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        start_time = datetime.fromisoformat(req.start_time)
        cur.execute(
            "INSERT INTO journeys (id, driver_id, origin, destination, start_time, "
            "status, region, is_cross_region, vehicle_type) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            (req.journey_id, req.driver_id, req.origin, req.destination,
             start_time, "CONFIRMED", REGION, True, "STANDARD"),
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
def cancel_journey(journey_id: str, user: dict = Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT driver_id FROM journeys WHERE id = %s", (journey_id,))
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
    return {"status": "CANCELLED", "id": journey_id}


@app.get("/journeys/{journey_id}")
def get_journey(journey_id: str, user: dict = Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, driver_id, origin, destination, start_time, status, region, "
        "dest_region, is_cross_region, vehicle_type, route_id, created_at "
        "FROM journeys WHERE id = %s",
        (journey_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(404, "Journey not found")
    return dict(zip(["id", "driver_id", "origin", "destination", "start_time",
                     "status", "region", "dest_region", "is_cross_region",
                     "vehicle_type", "route_id", "created_at"], row))


@app.get("/journeys")
def list_journeys(driver_id: Optional[str] = None, user: dict = Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    if driver_id:
        cur.execute(
            "SELECT id, driver_id, origin, destination, start_time, status, region, "
            "dest_region, is_cross_region, vehicle_type, route_id, created_at "
            "FROM journeys WHERE driver_id = %s ORDER BY created_at DESC",
            (driver_id,),
        )
    else:
        cur.execute(
            "SELECT id, driver_id, origin, destination, start_time, status, region, "
            "dest_region, is_cross_region, vehicle_type, route_id, created_at "
            "FROM journeys ORDER BY created_at DESC LIMIT 100"
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = ["id", "driver_id", "origin", "destination", "start_time",
            "status", "region", "dest_region", "is_cross_region",
            "vehicle_type", "route_id", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


@app.get("/health")
def health():
    return {"status": "ok", "service": "journey_booking",
            "region": REGION, "replicas": 2}
