import os
import json
import uuid
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

CANCELABLE_STATUSES = {"CONFIRMED", "PENDING"}
ALREADY_DONE_STATUSES = {"CANCELLED", "AUTHORITY_CANCELLED"}


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
        ALTER TABLE journeys ADD COLUMN IF NOT EXISTS cancelled_reason TEXT;
        ALTER TABLE journeys ADD COLUMN IF NOT EXISTS driver_email TEXT;
        ALTER TABLE road_closures ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
        UPDATE road_closures SET is_active = active WHERE is_active IS NULL;
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
                aio_pika.Message(
                    body=json.dumps(payload, default=str).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
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
    query = (
        "SELECT id, driver_id, origin, destination, start_time, status, "
        "region, vehicle_type, is_cross_region, created_at FROM journeys WHERE 1=1"
    )
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
        if j["status"] == "EMERGENCY_CONFIRMED":
            j["cancellable"] = False
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
    cur.execute(
        "SELECT id, status, origin, destination, driver_id, vehicle_type "
        "FROM journeys WHERE id = %s",
        (journey_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(404, "Journey not found")

    j_id, status, origin, destination, driver_id, vehicle_type = row

    # Block EMERGENCY_CONFIRMED
    if status == "EMERGENCY_CONFIRMED" or vehicle_type == "EMERGENCY":
        cur.close()
        conn.close()
        raise HTTPException(403, "Emergency journeys cannot be force cancelled")

    # Already done
    if status in ALREADY_DONE_STATUSES:
        cur.close()
        conn.close()
        raise HTTPException(400, f"Journey is already {status}")

    # Only cancel if in a cancelable state
    if status not in CANCELABLE_STATUSES:
        cur.close()
        conn.close()
        raise HTTPException(400, f"Journey status '{status}' is not cancellable")

    cur.execute(
        "UPDATE journeys SET status = 'AUTHORITY_CANCELLED', cancelled_reason = %s WHERE id = %s",
        (req.reason, journey_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    await publish_event("journey_force_cancelled_events", {
        "event_type": "journey_force_cancelled",
        "journey_id": str(j_id),
        "driver_id": driver_id,
        "origin": origin,
        "destination": destination,
        "reason": req.reason,
        "cancelled_by": user.get("email", "authority"),
        "region": REGION,
    })

    return {
        "journey_id": str(j_id),
        "status": "AUTHORITY_CANCELLED",
        "reason": req.reason,
        "cancelled_by": user.get("email", "authority"),
    }


@app.post("/authority/closure", status_code=201)
async def create_closure(
    req: ClosureRequest,
    user=Depends(require_role("traffic_authority", "admin")),
):
    conn = get_conn()
    cur = conn.cursor()

    # Insert closure record
    cur.execute(
        "INSERT INTO road_closures (road_name, region, reason, created_by) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (req.road_name, req.region, req.reason, user["email"]),
    )
    closure_id = str(cur.fetchone()[0])

    # Count emergency journeys that would be skipped
    cur.execute(
        "SELECT COUNT(*) FROM journeys "
        "WHERE route_segments::text ILIKE %s "
        "AND status = 'EMERGENCY_CONFIRMED' "
        "AND start_time > NOW()",
        (f"%{req.road_name}%",),
    )
    emergency_skipped = cur.fetchone()[0]

    # Find and cancel affected non-emergency journeys via route_segments JSONB
    cur.execute(
        "UPDATE journeys SET status = 'AUTHORITY_CANCELLED', cancelled_reason = %s "
        "WHERE route_segments::text ILIKE %s "
        "AND status IN ('CONFIRMED', 'PENDING') "
        "AND start_time > NOW() "
        "RETURNING id, driver_id, driver_email, origin, destination, start_time",
        (f"Road closure: {req.road_name} — {req.reason}", f"%{req.road_name}%"),
    )
    cancelled_rows = cur.fetchall()
    conn.commit()
    cur.close()
    conn.close()

    cancelled_ids = [str(r[0]) for r in cancelled_rows]
    authority_email = user.get("email", "authority")

    # Publish one road_closure_events per cancelled journey with full driver detail
    for r in cancelled_rows:
        j_id, j_driver_id, j_driver_email, j_origin, j_destination, j_start_time = r
        j_driver_email = j_driver_email or ""
        await publish_event("road_closure_events", {
            "event_type": "road_closure",
            "journey_id": str(j_id),
            "driver_id": str(j_driver_id),
            "driver_email": j_driver_email,
            "driver_name": j_driver_email or "Driver",
            "origin": j_origin,
            "destination": j_destination,
            "start_time": str(j_start_time) if j_start_time else "",
            "road_name": req.road_name,
            "closure_reason": req.reason,
            "reason": req.reason,
            "region": req.region,
            "cancelled_by": authority_email,
        })

    return {
        "closure_id": closure_id,
        "road_name": req.road_name,
        "affected_journeys": len(cancelled_ids),
        "cancelled_journey_ids": cancelled_ids,
        "emergency_skipped": emergency_skipped,
    }


@app.get("/authority/segments")
def get_road_segments(user=Depends(require_role("traffic_authority", "admin"))):
    """Return unique OSRM road segment names from active future journeys.
    Used by frontend as a dropdown so authority picks a real name that will match.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Segments are stored as plain strings ["Naas Road", ...]
        # in new journeys (via road_routing extract_segments), and as objects
        # {"name":"...", "maneuver":"..."} in old journeys.
        # COALESCE: try ->>'name' (objects), fall back to #>>'{}'  (strings).
        cur.execute("""
            SELECT DISTINCT
                COALESCE(
                    elem->>'name',
                    elem #>> '{}'
                ) AS segment
            FROM journeys,
                 jsonb_array_elements(route_segments::jsonb) AS elem
            WHERE route_segments IS NOT NULL
              AND route_segments::text != '[]'
              AND route_segments::text != 'null'
              AND status IN ('CONFIRMED', 'PENDING')
              AND start_time > NOW()
            ORDER BY segment
        """)
        rows = cur.fetchall()
        segments = [r[0] for r in rows if r[0] and r[0].strip()]
        return {
            "segments": segments,
            "count": len(segments),
            "note": "Exact OSRM road names from active future journeys",
        }
    except Exception as e:
        return {"segments": [], "error": str(e)}
    finally:
        cur.close()
        conn.close()


@app.get("/authority/closure-preview")
def preview_closure(
    road_name: str,
    user=Depends(require_role("traffic_authority", "admin")),
):
    """Show which journeys would be cancelled before actually creating a closure."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, origin, destination, start_time,
                   vehicle_type, status, driver_email
            FROM journeys
            WHERE route_segments::text ILIKE %s
              AND status IN ('CONFIRMED', 'PENDING', 'EMERGENCY_CONFIRMED')
              AND start_time > NOW()
        """, (f"%{road_name}%",))
        rows = cur.fetchall()
        journeys = []
        emergency_count = 0
        for r in rows:
            if r[4] == "EMERGENCY" or r[5] == "EMERGENCY_CONFIRMED":
                emergency_count += 1
                continue
            journeys.append({
                "id": str(r[0])[:8],
                "origin": r[1],
                "destination": r[2],
                "start_time": str(r[3]),
                "vehicle_type": r[4],
                "status": r[5],
                "driver_email": r[6] or "",
            })
        return {
            "road_name": road_name,
            "will_cancel": len(journeys),
            "emergency_skipped": emergency_count,
            "affected_journeys": journeys[:10],
        }
    finally:
        cur.close()
        conn.close()


@app.get("/authority/closures")
def list_closures(
    region: Optional[str] = None,
    active: bool = True,
    user=Depends(require_role("traffic_authority", "admin")),
):
    conn = get_conn()
    cur = conn.cursor()
    query = (
        "SELECT id, road_name, region, reason, active, created_by, created_at "
        "FROM road_closures WHERE 1=1"
    )
    params = []
    if active:
        query += " AND active = TRUE"
    region_filter = region or REGION
    query += " AND region = %s ORDER BY created_at DESC"
    params.append(region_filter)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = ["id", "road_name", "region", "reason", "active", "created_by", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


@app.delete("/authority/closure/{closure_id}")
def delete_closure(closure_id: str, user=Depends(require_role("admin"))):
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
