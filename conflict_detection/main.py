import os
import json
from datetime import datetime, timedelta

import psycopg2
import redis
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="conflict_detection")

REGION = os.getenv("REGION", "EU")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def verify_token(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


class CheckRequest(BaseModel):
    origin: str
    destination: str
    start_time: str
    segments: List[str] = []
    vehicle_type: str = "STANDARD"
    driver_id: str = ""


class CrossRegionLockRequest(BaseModel):
    origin: str
    destination: str
    start_time: str
    from_region: str


class InvalidateRequest(BaseModel):
    origin: str
    destination: str
    start_time: str


class ReserveRequest(BaseModel):
    origin: str
    destination: str
    slot: str
    driver_id: str


class ReleaseRequest(BaseModel):
    origin: str
    destination: str
    slot: str
    driver_id: str


def round_to_slot(dt: datetime) -> str:
    """Round datetime down to nearest 30-minute bucket."""
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0).isoformat()


def slot_lock_key(driver_id: str, origin: str, destination: str, slot: str) -> str:
    return f"lock:{driver_id}:{origin}:{destination}:{slot}"


@app.post("/check")
def check_conflict(req: CheckRequest):
    # Emergency vehicles always pass
    if req.vehicle_type == "EMERGENCY":
        return {"conflict": False, "reason": "Emergency vehicle — no conflict check"}

    start = datetime.fromisoformat(req.start_time)
    slot = round_to_slot(start)
    driver_id = req.driver_id or "unknown"

    lock_key = slot_lock_key(driver_id, req.origin, req.destination, slot)

    # Check Redis ghost reservation for this driver+route+slot
    try:
        if redis_client.exists(lock_key):
            return {"conflict": True, "reason": "Slot already reserved (ghost lock)"}
    except Exception as e:
        print(f"Redis check error: {e}")

    # Check PostgreSQL — same DRIVER double-booking within ±30 min window
    try:
        window_start = start - timedelta(minutes=30)
        window_end = start + timedelta(minutes=30)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM journeys "
            "WHERE driver_id = %s "
            "AND origin = %s AND destination = %s "
            "AND start_time BETWEEN %s AND %s "
            "AND status NOT IN ('CANCELLED', 'AUTHORITY_CANCELLED')",
            (driver_id, req.origin, req.destination, window_start, window_end),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "conflict": True,
                "reason": f"You already have a booking on this route in this time window (id: {row[0]})",
            }
    except Exception as e:
        print(f"DB check error: {e}")

    # Set Redis ghost reservation for this driver (TTL 60s)
    try:
        redis_client.setex(lock_key, 60, "reserved")
    except Exception as e:
        print(f"Redis set error: {e}")

    return {"conflict": False, "reason": ""}


@app.get("/slots")
def get_slots(
    origin: str,
    destination: str,
    date: str,
    driver_id: str = "",
    vehicle_type: str = "STANDARD",
):
    """
    Returns 30-min slots 06:00–22:00. Checks ALL drivers (global road capacity).
    Also checks Redis ghost holds (someone has selected but not yet booked).
    """
    # Emergency vehicles see all slots free
    if vehicle_type == "EMERGENCY":
        slots = []
        for hour in range(6, 22):
            for minute in [0, 30]:
                slots.append({
                    "slot": f"{hour:02d}:{minute:02d}",
                    "available": True,
                    "reason": "emergency_bypass",
                    "held_by_you": False,
                })
        return slots

    try:
        base_date = datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    try:
        conn = get_conn()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(503, f"DB connection failed: {e}")

    slots = []
    for hour in range(6, 22):
        for minute in [0, 30]:
            slot_str = f"{hour:02d}:{minute:02d}"
            slot_start = base_date.replace(hour=hour, minute=minute, second=0)
            slot_end = slot_start + timedelta(minutes=30)

            try:
                # CHECK 1: Any driver has a confirmed booking in this window
                cur.execute(
                    "SELECT COUNT(*) FROM journeys "
                    "WHERE origin = %s AND destination = %s "
                    "AND start_time >= %s AND start_time < %s "
                    "AND status IN ('CONFIRMED', 'EMERGENCY_CONFIRMED', 'PENDING')",
                    (origin, destination, slot_start, slot_end),
                )
                db_count = cur.fetchone()[0]
                if db_count > 0:
                    slots.append({
                        "slot": slot_str,
                        "available": False,
                        "reason": "booked",
                        "held_by_you": False,
                    })
                    continue

                # CHECK 2: Redis ghost hold (someone selected but not booked yet)
                hold_key = f"slot_hold:{origin}:{destination}:{slot_str}"
                hold_raw = redis_client.get(hold_key)
                if hold_raw:
                    try:
                        hold_data = json.loads(hold_raw)
                        held_by = hold_data.get("driver_id", "")
                        held_by_you = bool(held_by and held_by == driver_id)
                    except Exception:
                        held_by_you = False
                    slots.append({
                        "slot": slot_str,
                        "available": False,
                        "reason": "being_selected",
                        "held_by_you": held_by_you,
                    })
                    continue

                slots.append({
                    "slot": slot_str,
                    "available": True,
                    "reason": "",
                    "held_by_you": False,
                })

            except Exception as e:
                slots.append({
                    "slot": slot_str,
                    "available": True,
                    "reason": f"check_error: {e}",
                    "held_by_you": False,
                })

    cur.close()
    conn.close()
    return slots


@app.post("/reserve-slot")
def reserve_slot(req: ReserveRequest):
    """Ghost reservation — holds a slot for 120s while driver completes booking."""
    hold_key = f"slot_hold:{req.origin}:{req.destination}:{req.slot}"
    value = json.dumps({
        "driver_id": req.driver_id,
        "reserved_at": datetime.utcnow().isoformat(),
    })
    redis_client.setex(hold_key, 120, value)
    return {
        "reserved": True,
        "slot": req.slot,
        "expires_in": 120,
        "key": hold_key,
    }


@app.post("/release-slot")
def release_slot(req: ReleaseRequest):
    """Release a ghost reservation — only the holding driver can release."""
    hold_key = f"slot_hold:{req.origin}:{req.destination}:{req.slot}"
    existing = redis_client.get(hold_key)
    if existing:
        try:
            data = json.loads(existing)
            if data.get("driver_id") == req.driver_id:
                redis_client.delete(hold_key)
                return {"released": True, "key": hold_key}
            return {"released": False, "reason": "Not your hold"}
        except Exception:
            redis_client.delete(hold_key)
            return {"released": True}
    return {"released": False, "reason": "No hold found"}


@app.post("/cross-region", status_code=201)
def register_cross_region(req: CrossRegionLockRequest):
    lock_key = f"lock:cross_region:{req.origin}:{req.destination}:{req.start_time}"
    try:
        redis_client.setex(lock_key, 3600, f"cross_region:{req.from_region}")
    except Exception as e:
        print(f"Redis cross-region error: {e}")
    return {"status": "registered", "key": lock_key}


@app.delete("/invalidate")
def invalidate(req: InvalidateRequest):
    lock_key = f"lock::{req.origin}:{req.destination}:{req.start_time}"
    try:
        redis_client.delete(lock_key)
    except Exception as e:
        print(f"Redis invalidate error: {e}")
    return {"status": "invalidated", "key": lock_key}


@app.get("/health")
def health():
    return {"status": "ok", "service": "conflict_detection", "region": REGION}
