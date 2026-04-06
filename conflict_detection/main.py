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

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


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
    segments: List[dict] = []
    vehicle_type: str = "STANDARD"


class CrossRegionLockRequest(BaseModel):
    origin: str
    destination: str
    start_time: str
    from_region: str


class InvalidateRequest(BaseModel):
    origin: str
    destination: str
    start_time: str


def slot_key(origin: str, destination: str, start_time: str) -> str:
    return f"lock:{origin}:{destination}:{start_time}"


@app.post("/check")
def check_conflict(req: CheckRequest):
    # Emergency vehicles always pass
    if req.vehicle_type == "EMERGENCY":
        return {"conflict": False, "reason": "Emergency vehicle — no conflict check"}

    lock_key = slot_key(req.origin, req.destination, req.start_time)

    # Check Redis ghost reservation
    if redis_client.exists(lock_key):
        return {"conflict": True, "reason": "Slot already reserved (ghost lock)"}

    # Check PostgreSQL — 30-minute window
    try:
        start = datetime.fromisoformat(req.start_time)
        window_start = start - timedelta(minutes=30)
        window_end = start + timedelta(minutes=30)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM journeys "
            "WHERE origin = %s AND destination = %s "
            "AND start_time BETWEEN %s AND %s "
            "AND status NOT IN ('CANCELLED', 'AUTHORITY_CANCELLED')",
            (req.origin, req.destination, window_start, window_end),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"conflict": True,
                    "reason": f"Journey already booked in 30-min window (id: {row[0]})"}
    except Exception as e:
        print(f"DB check error: {e}")

    # Set Redis ghost reservation (TTL 60s)
    redis_client.setex(lock_key, 60, "reserved")
    return {"conflict": False, "reason": ""}


@app.post("/cross-region", status_code=201)
def register_cross_region(req: CrossRegionLockRequest):
    lock_key = slot_key(req.origin, req.destination, req.start_time)
    redis_client.setex(lock_key, 3600, f"cross_region:{req.from_region}")
    return {"status": "registered", "key": lock_key}


@app.delete("/invalidate")
def invalidate(req: InvalidateRequest):
    lock_key = slot_key(req.origin, req.destination, req.start_time)
    redis_client.delete(lock_key)
    return {"status": "invalidated", "key": lock_key}


@app.get("/health")
def health():
    return {"status": "ok", "service": "conflict_detection", "region": REGION}
