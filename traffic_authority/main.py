import os
import json
from datetime import datetime

import psycopg2
import aio_pika
import asyncio
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="traffic_authority")

REGION = os.getenv("REGION", "EU")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS road_closures (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            road_name  TEXT NOT NULL,
            region     TEXT NOT NULL,
            reason     TEXT,
            active     BOOLEAN DEFAULT TRUE,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
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


def require_role(*roles):
    def dep(user=Depends(verify_token)):
        if user.get("role") not in roles:
            raise HTTPException(403, "Insufficient role")
        return user
    return dep


# ── Schemas ───────────────────────────────────────────────────────────────────

class CancelRequest(BaseModel):
    reason: str


class ClosureRequest(BaseModel):
    road_name: str
    reason: str
    region: str


async def publish_event(queue_name: str, payload: dict):
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(queue_name, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode(),
                                 delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=queue_name,
            )
    except Exception as e:
        print(f"RabbitMQ publish error: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/authority/journeys")
def list_journeys(
    region: Optional[str] = None,
    status: Optional[str] = None,
    road: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    user=Depends(require_role("traffic_authority", "admin")),
):
    conn = get_conn()
    cur = conn.cursor()
    query = ("SELECT id, driver_id, origin, destination, start_time, status, "
             "region, vehicle_type, is_cross_region, created_at FROM journeys WHERE 1=1")
    params = []
    if region:
        query += " AND region = %s"
        params.append(region)
    if status:
        query += " AND status = %s"
        params.append(status)
    if road:
        query += " AND (origin ILIKE %s OR destination ILIKE %s)"
        params.extend([f"%{road}%", f"%{road}%"])
    if vehicle_type:
        query += " AND vehicle_type = %s"
        params.append(vehicle_type)
    query += " ORDER BY created_at DESC LIMIT 200"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = ["id", "driver_id", "origin", "destination", "start_time",
            "status", "region", "vehicle_type", "is_cross_region", "created_at"]
    journeys = []
    for r in rows:
        j = dict(zip(cols, r))
        if j["vehicle_type"] == "EMERGENCY":
            j["badge"] = "EMERGENCY"
        journeys.append(j)
    return journeys


@app.post("/authority/cancel/{journey_id}")
async def cancel_journey(
    journey_id: str,
    req: CancelRequest,
    user=Depends(require_role("traffic_authority", "admin")),
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM journeys WHERE id = %s", (journey_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(404, "Journey not found")
    cur.execute(
        "UPDATE journeys SET status = 'AUTHORITY_CANCELLED' WHERE id = %s",
        (journey_id,),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "AUTHORITY_CANCELLED", "id": journey_id, "reason": req.reason}


@app.post("/authority/closure", status_code=201)
async def create_closure(
    req: ClosureRequest,
    user=Depends(require_role("traffic_authority", "admin")),
):
    conn = get_conn()
    cur = conn.cursor()

    # Insert closure
    cur.execute(
        "INSERT INTO road_closures (road_name, region, reason, created_by) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (req.road_name, req.region, req.reason, user["email"]),
    )
    closure_id = cur.fetchone()[0]

    # Cancel affected journeys
    cur.execute(
        "UPDATE journeys SET status = 'AUTHORITY_CANCELLED' "
        "WHERE status = 'CONFIRMED' AND start_time > NOW() "
        "AND (origin ILIKE %s OR destination ILIKE %s) "
        "RETURNING id",
        (f"%{req.road_name}%", f"%{req.road_name}%"),
    )
    cancelled_ids = [r[0] for r in cur.fetchall()]
    conn.commit()
    cur.close()
    conn.close()

    # Publish road closure event
    await publish_event("road_closure_events", {
        "closure_id": str(closure_id),
        "road_name": req.road_name,
        "reason": req.reason,
        "region": req.region,
        "cancelled_journeys": [str(i) for i in cancelled_ids],
    })

    return {
        "id": str(closure_id),
        "road_name": req.road_name,
        "region": req.region,
        "reason": req.reason,
        "cancelled_journeys": len(cancelled_ids),
    }


@app.delete("/authority/closure/{closure_id}")
def delete_closure(
    closure_id: str,
    user=Depends(require_role("admin")),
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE road_closures SET active = FALSE WHERE id = %s RETURNING id",
        (closure_id,),
    )
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(404, "Closure not found")
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "removed", "id": closure_id}


@app.get("/authority/stats")
def stats(user=Depends(require_role("traffic_authority", "admin"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM journeys GROUP BY status")
    by_status = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute("SELECT COUNT(*) FROM journeys WHERE region = %s", (REGION,))
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"region": REGION, "total": total, "by_status": by_status}


@app.get("/authority/emergency")
def emergency_vehicles(user=Depends(require_role("traffic_authority", "admin"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, driver_id, origin, destination, start_time, status, region, created_at "
        "FROM journeys WHERE vehicle_type = 'EMERGENCY' AND status = 'EMERGENCY_CONFIRMED' "
        "ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = ["id", "driver_id", "origin", "destination",
            "start_time", "status", "region", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


@app.get("/health")
def health():
    return {"status": "ok", "service": "traffic_authority", "region": REGION}
