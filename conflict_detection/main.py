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
def get_slots(origin: str, destination: str, date: str, driver_id: str = ""):
    """
    Returns 30-min time slots from 06:00 to 22:00 for the given route/date.
    A slot is unavailable if the driver already has a booking in that window.
    """
    try:
        base = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    slots = []
    hour = 6
    minute = 0
    while hour < 22:
        slot_dt = base.replace(hour=hour, minute=minute)
        slot_end = slot_dt + timedelta(minutes=30)
        slot_str = slot_dt.strftime("%H:%M")
        available = True
        reason = ""

        # Check Redis lock for this driver+slot
        if driver_id:
            lock_key = slot_lock_key(driver_id, origin, destination, slot_dt.isoformat())
            try:
                if redis_client.exists(lock_key):
                    available = False
                    reason = "ghost_reservation"
            except Exception:
                pass

        # Check DB for this driver on this route in this window
        if available and driver_id:
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM journeys "
                    "WHERE driver_id = %s AND origin = %s AND destination = %s "
                    "AND start_time BETWEEN %s AND %s "
                    "AND status NOT IN ('CANCELLED', 'AUTHORITY_CANCELLED')",
                    (driver_id, origin, destination, slot_dt, slot_end),
                )
                count = cur.fetchone()[0]
                cur.close()
                conn.close()
                if count > 0:
                    available = False
                    reason = "booked"
            except Exception as e:
                print(f"Slots DB error: {e}")

        entry = {"slot": slot_str, "available": available}
        if not available:
            entry["reason"] = reason
        slots.append(entry)

        minute += 30
        if minute >= 60:
            minute = 0
            hour += 1

    return slots


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
