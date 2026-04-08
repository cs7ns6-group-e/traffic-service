import os
import asyncio
import time
from datetime import datetime

import httpx
import psycopg2
import redis as redis_lib
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends

app = FastAPI(title="admin_service")

REGION = os.getenv("REGION", "EU")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
RABBITMQ_URL_HTTP = "http://rabbitmq:15672"
REGION_EU_URL = os.getenv("REGION_EU_URL", "http://10.0.1.11")
REGION_US_URL = os.getenv("REGION_US_URL", "http://10.0.2.11")
REGION_APAC_URL = os.getenv("REGION_APAC_URL", "http://10.0.3.11")

redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)

SERVICES = [
    ("auth_service", 8000),
    ("journey_booking", 8001),
    ("conflict_detection", 8002),
    ("notification", 8003),
    ("road_routing", 8004),
    ("traffic_authority", 8005),
    ("admin_service", 8006),
]


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


def require_role(*roles):
    def dep(user=Depends(verify_token)):
        if user.get("role") not in roles:
            raise HTTPException(403, "Insufficient role")
        return user
    return dep


async def check_service(client: httpx.AsyncClient, name: str, port: int) -> dict:
    start = time.time()
    try:
        r = await client.get(f"http://{name}:{port}/health", timeout=3)
        elapsed = int((time.time() - start) * 1000)
        return {"name": name, "port": port,
                "status": "healthy" if r.status_code == 200 else "degraded",
                "response_time_ms": elapsed}
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return {"name": name, "port": port, "status": "down",
                "response_time_ms": elapsed, "error": str(e)}


@app.get("/admin/health")
async def health_check(user=Depends(verify_token)):
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[check_service(client, name, port) for name, port in SERVICES]
        )
    return {"services": list(results), "region": REGION, "timestamp": datetime.utcnow().isoformat()}


@app.get("/admin/latency")
async def latency_check(user=Depends(require_role("admin", "traffic_authority"))):
    """Measure P50/P95 latency for all services by sampling /health 5 times each."""
    async def measure_service(name: str, port: int) -> dict:
        samples = []
        last_status = "unknown"
        async with httpx.AsyncClient() as client:
            for _ in range(5):
                t0 = time.time()
                try:
                    r = await asyncio.wait_for(
                        client.get(f"http://{name}:{port}/health"),
                        timeout=3,
                    )
                    elapsed_ms = int((time.time() - t0) * 1000)
                    samples.append(elapsed_ms)
                    last_status = "ok" if r.status_code == 200 else "degraded"
                except Exception:
                    elapsed_ms = int((time.time() - t0) * 1000)
                    samples.append(elapsed_ms)
                    last_status = "down"
        samples.sort()
        n = len(samples)
        p50 = samples[n // 2] if samples else 0
        p95 = samples[int(n * 0.95)] if samples else 0
        return {
            "name": name,
            "p50_ms": p50,
            "p95_ms": p95,
            "last_response_ms": samples[-1] if samples else 0,
            "status": last_status,
        }

    results = await asyncio.gather(
        *[measure_service(name, port) for name, port in SERVICES]
    )
    results_list = list(results)
    all_p95 = [r["p95_ms"] for r in results_list if r["status"] != "down"]
    max_p95 = max(all_p95) if all_p95 else 0
    return {
        "region": REGION,
        "timestamp": datetime.utcnow().isoformat(),
        "services": results_list,
        "sla": {
            "target_p95_ms": 500,
            "passing": max_p95 <= 500,
        },
    }


@app.get("/admin/stats")
def stats(user=Depends(verify_token)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM journeys")
    total = cur.fetchone()[0]
    cur.execute("SELECT status, COUNT(*) FROM journeys GROUP BY status")
    by_status = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute(
        "SELECT DATE_TRUNC('hour', created_at) AS hour, COUNT(*) "
        "FROM journeys GROUP BY hour ORDER BY hour DESC LIMIT 24"
    )
    by_hour = [{"hour": str(r[0]), "count": r[1]} for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) FROM journeys WHERE is_cross_region = TRUE")
    cross_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM journeys WHERE vehicle_type = 'EMERGENCY'")
    emerg_count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {
        "total_journeys": total,
        "by_status": by_status,
        "by_hour": by_hour,
        "cross_region_count": cross_count,
        "emergency_count": emerg_count,
        "region": REGION,
    }


@app.get("/admin/queue")
async def queue_stats(user=Depends(verify_token)):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{RABBITMQ_URL_HTTP}/api/queues",
                auth=("guest", "guest"),
            )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@app.get("/admin/cache")
def cache_stats(user=Depends(verify_token)):
    try:
        info = redis_client.info()
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        hit_rate = round(hits / total * 100, 2) if total > 0 else 0
        return {
            "hit_rate": hit_rate,
            "hits": hits,
            "misses": misses,
            "memory_used": info.get("used_memory_human", "?"),
            "connected_clients": info.get("connected_clients", 0),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/admin/replication-lag")
def replication_lag(user=Depends(verify_token)):
    return {
        "mode": "isolated",
        "message": "Per-region isolated DB — no replication",
        "region": REGION,
    }


@app.get("/admin/all-regions")
async def all_regions(user=Depends(require_role("admin"))):
    region_urls = {
        "EU": f"{REGION_EU_URL}:8006",
        "US": f"{REGION_US_URL}:8006",
        "APAC": f"{REGION_APAC_URL}:8006",
    }
    token = f"Bearer internal"
    results = {}

    async def fetch_region(name: str, base_url: str):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{base_url}/admin/stats",
                                     headers={"Authorization": token})
                return name, r.json()
        except Exception as e:
            return name, {"error": str(e)}

    tasks = [fetch_region(k, v) for k, v in region_urls.items()]
    pairs = await asyncio.gather(*tasks)
    for name, data in pairs:
        results[name] = data
    return {"regions": results, "timestamp": datetime.utcnow().isoformat()}


@app.get("/admin/emergency-vehicles")
def emergency_vehicles(user=Depends(require_role("traffic_authority", "admin"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, driver_id, origin, destination, start_time, status, region, created_at "
        "FROM journeys WHERE vehicle_type = 'EMERGENCY' ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    cols = ["id", "driver_id", "origin", "destination",
            "start_time", "status", "region", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


@app.get("/health")
def health():
    return {"status": "ok", "service": "admin_service", "region": REGION}
