"""Admin Service — Observability and monitoring dashboard."""

import asyncio
import os
from datetime import datetime, timezone

import httpx
import jwt
import pika
import redis
from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "changeme")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://trafficbook:trafficbook@postgres:5432/trafficbook"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
REGION = os.environ.get("REGION", "EU")
REGION_US_URL = os.environ.get("REGION_US_URL", "")
REGION_APAC_URL = os.environ.get("REGION_APAC_URL", "")

SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ---------------------------------------------------------------------------
# Service endpoints for health checks
# ---------------------------------------------------------------------------
SERVICE_ENDPOINTS = [
    ("auth_service", "http://auth_service:8000/health"),
    ("journey_booking", "http://journey_booking:8001/health"),
    ("conflict_detection", "http://conflict_detection:8002/health"),
    ("notification", "http://notification:8003/health"),
    ("road_routing", "http://road_routing:8004/health"),
    ("traffic_authority", "http://traffic_authority:8005/health"),
    ("admin_service", "http://localhost:8006/health"),
]

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def decode_token(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    token = authorization.removeprefix("Bearer ")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin_or_authority(user: dict = Depends(decode_token)) -> dict:
    role = user.get("role", "")
    if role not in ("admin", "traffic_authority"):
        raise HTTPException(status_code=403, detail="Admin or traffic_authority role required")
    return user


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="TrafficBook Admin Service", version="1.0.0")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "healthy", "service": "admin_service"}


@app.get("/admin/health")
async def admin_health(user: dict = Depends(require_admin_or_authority)):
    """Check health of all services concurrently."""
    results = {}

    async def check_service(name: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                results[name] = {"status": "healthy", "http_status": resp.status_code}
        except Exception as e:
            results[name] = {"status": "unhealthy", "error": str(e)}

    tasks = [check_service(name, url) for name, url in SERVICE_ENDPOINTS]
    await asyncio.gather(*tasks)

    # Check Redis
    try:
        r = redis.from_url(REDIS_URL, socket_timeout=3)
        r.ping()
        results["redis"] = {"status": "healthy"}
    except Exception as e:
        results["redis"] = {"status": "unhealthy", "error": str(e)}

    all_healthy = all(v.get("status") == "healthy" for v in results.values())
    return {"overall": "healthy" if all_healthy else "degraded", "services": results}


@app.get("/admin/stats")
def admin_stats(user: dict = Depends(require_admin_or_authority), db: Session = Depends(get_db)):
    """Journey counts by status and by hour."""
    try:
        # Counts by status
        status_rows = db.execute(
            text("SELECT status, COUNT(*) as count FROM journeys GROUP BY status")
        ).fetchall()
        by_status = {row[0]: row[1] for row in status_rows}

        # Counts by hour (last 24h)
        hourly_rows = db.execute(
            text(
                """
                SELECT date_trunc('hour', start_time) AS hour, COUNT(*) AS count
                FROM journeys
                WHERE start_time >= NOW() - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour DESC
                """
            )
        ).fetchall()
        by_hour = [{"hour": str(row[0]), "count": row[1]} for row in hourly_rows]

        return {"by_status": by_status, "by_hour": by_hour, "region": REGION}
    except Exception:
        return {"error": "Failed to fetch journey stats", "region": REGION}


@app.get("/admin/queue")
def admin_queue(user: dict = Depends(require_admin_or_authority)):
    """RabbitMQ queue depths."""
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        queues_info = {}
        for queue_name in ["booking_events"]:
            try:
                result = channel.queue_declare(queue=queue_name, passive=True)
                queues_info[queue_name] = {
                    "message_count": result.method.message_count,
                    "consumer_count": result.method.consumer_count,
                }
            except Exception:
                queues_info[queue_name] = {"error": "Queue not found"}

        connection.close()
        return {"queues": queues_info, "status": "connected"}
    except Exception:
        return {"queues": {}, "status": "error", "error": "Failed to connect to RabbitMQ"}


@app.get("/admin/cache")
def admin_cache(user: dict = Depends(require_admin_or_authority)):
    """Redis hit rate and memory usage."""
    try:
        r = redis.from_url(REDIS_URL, socket_timeout=3)
        info = r.info()

        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        hit_rate = round(hits / total * 100, 2) if total > 0 else 0.0

        return {
            "hit_rate_percent": hit_rate,
            "keyspace_hits": hits,
            "keyspace_misses": misses,
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
            "total_keys": r.dbsize(),
        }
    except Exception:
        return {"error": "Failed to fetch Redis cache stats"}


@app.get("/admin/all-regions")
async def admin_all_regions(user: dict = Depends(require_admin_or_authority)):
    """Aggregate stats from EU, US, and APAC regions."""
    token = jwt.encode(
        {"sub": user["sub"], "role": user["role"], "exp": user["exp"]},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    headers = {"Authorization": f"Bearer {token}"}

    regions = {"EU": f"http://localhost:8006/admin/stats"}
    if REGION_US_URL:
        regions["US"] = f"{REGION_US_URL}/admin/stats"
    if REGION_APAC_URL:
        regions["APAC"] = f"{REGION_APAC_URL}/admin/stats"

    results = {}

    async def fetch_region(name: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                results[name] = resp.json()
        except Exception as e:
            results[name] = {"error": str(e)}

    tasks = [fetch_region(name, url) for name, url in regions.items()]
    await asyncio.gather(*tasks)
    return {"regions": results}


@app.get("/admin/emergency")
def admin_emergency(user: dict = Depends(require_admin_or_authority), db: Session = Depends(get_db)):
    """Active emergency vehicle journeys."""
    try:
        rows = db.execute(
            text(
                """
                SELECT j.id, j.driver_id, j.origin, j.destination,
                       j.start_time, j.status, j.region, j.vehicle_type
                FROM journeys j
                WHERE j.vehicle_type = 'EMERGENCY'
                  AND j.status IN ('PENDING', 'CONFIRMED', 'IN_PROGRESS')
                ORDER BY j.start_time DESC
                """
            )
        ).fetchall()

        journeys = [
            {
                "id": str(row[0]),
                "driver_id": str(row[1]),
                "origin": row[2],
                "destination": row[3],
                "start_time": str(row[4]),
                "status": row[5],
                "region": row[6],
                "vehicle_type": row[7],
            }
            for row in rows
        ]
        return {"active_emergency_journeys": journeys, "count": len(journeys)}
    except Exception:
        return {"active_emergency_journeys": [], "count": 0, "error": "Failed to fetch emergency journeys"}
