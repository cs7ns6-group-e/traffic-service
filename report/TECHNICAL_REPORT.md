# TrafficBook — Distributed Systems Technical Report
**CS7NS6 — Distributed Systems, Trinity College Dublin**

---

## Abstract

TrafficBook is a geo-distributed traffic management platform deployed across three Google Cloud Platform regions (EU, US, APAC). The system demonstrates core distributed systems principles through real production code: eventual consistency via RabbitMQ message federation, optimistic slot locking using Redis ghost reservations, per-region isolated PostgreSQL with async cross-region replication, and a stateless microservice architecture behind an nginx API gateway. This report documents every component in detail, with annotated code paths, distributed-systems analysis, and supporting visualisations.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Infrastructure Architecture](#2-infrastructure-architecture)
3. [API Gateway — nginx](#3-api-gateway--nginx)
4. [Service Deep Dives](#4-service-deep-dives)
   - 4.1 Auth Service
   - 4.2 Journey Booking
   - 4.3 Conflict Detection
   - 4.4 Road Routing
   - 4.5 Traffic Authority
   - 4.6 Notification
   - 4.7 Admin Service
5. [Distributed Systems Concepts](#5-distributed-systems-concepts)
   - 5.1 Eventual Consistency
   - 5.2 Ghost Reservations (Optimistic Locking)
   - 5.3 Per-Driver Conflict Scoping
   - 5.4 Cross-Region Communication
   - 5.5 Emergency Vehicle Priority (Bypass Pattern)
   - 5.6 PENDING Auto-Expiry (TTL Pattern)
   - 5.7 CAP Theorem Analysis
   - 5.8 BASE vs ACID
   - 5.9 Fault Isolation
6. [Data Flows](#6-data-flows)
   - 6.1 Standard Booking
   - 6.2 Cross-Region Booking
   - 6.3 Emergency Booking
   - 6.4 Road Closure Cascade
   - 6.5 Data Replication Pipeline
7. [Database Schema](#7-database-schema)
8. [RabbitMQ Architecture](#8-rabbitmq-architecture)
9. [Redis Architecture](#9-redis-architecture)
10. [Security Architecture](#10-security-architecture)
11. [Observability](#11-observability)
12. [Testing](#12-testing)
13. [Figures Index](#13-figures-index)

---

## 1. System Overview

TrafficBook allows drivers to book time-slotted road journeys. A traffic authority role manages road closures that cascade cancellations to affected bookings. An admin role monitors system health, latency, and cross-region replication status.

**Three identical stacks** are deployed independently on GCP VMs. There is no shared database, no shared cache, and no shared message broker — each region is fully self-contained. Cross-region data flows exclusively through RabbitMQ message federation.

| Concern | Technology | Distributed Role |
|---------|-----------|-----------------|
| API routing | nginx | Rate limiting, upstream selection, SPA fallback |
| Auth | FastAPI + PyJWT + bcrypt | Stateless JWT — verifiable on any service |
| Booking | FastAPI + PostgreSQL | Source of truth per region |
| Conflict | FastAPI + Redis | Distributed lock / ghost reservation |
| Routing | FastAPI + OSRM + Nominatim | Geocoding + segment extraction |
| Authority | FastAPI + PostgreSQL | Cascade cancellation via JSONB text search |
| Notifications | FastAPI + aio_pika | Async event consumer, replication writer |
| Observability | FastAPI + httpx | Fan-out health probes + latency sampling |
| Messaging | RabbitMQ 3 + federation plugin | Eventual consistency backbone |
| Cache | Redis 7 | Ghost locks + search cache |
| Database | PostgreSQL 15 | Per-region primary store |
| Monitoring | Prometheus + Grafana | Metrics scraping |
| Frontend | React 18 + Vite 6 + Tailwind | SPA served via nginx |

---

## 2. Infrastructure Architecture

### Figure 1 — 3-Region Topology

> **Eraser Cloud Diagram** — paste at eraser.io/diagramming

```
// TrafficBook 3-Region Cloud Architecture
// Paste this into eraser.io → Cloud Diagram

direction: right

Internet [icon: globe, color: gray]

EU Region [icon: gcp-region, color: blue] {
  EU LB [icon: gcp-load-balancing, label: "GCP LB\n35.240.110.205"]
  EU VM [icon: gcp-compute-engine, label: "e2-medium VM\neurope-west1"] {
    EU nginx [icon: nginx, label: "nginx :80"]
    EU Auth [icon: server, label: "auth :8000"]
    EU Journey [icon: server, label: "journey_booking :8001"]
    EU Conflict [icon: server, label: "conflict_detection :8002"]
    EU Notify [icon: server, label: "notification :8003"]
    EU Route [icon: server, label: "road_routing :8004"]
    EU Authority [icon: server, label: "traffic_authority :8005"]
    EU Admin [icon: server, label: "admin_service :8006"]
    EU PG [icon: postgresql, label: "PostgreSQL :5432"]
    EU Redis [icon: redis, label: "Redis :6379"]
    EU RMQ [icon: rabbitmq, label: "RabbitMQ :5672"]
  }
}

US Region [icon: gcp-region, color: green] {
  US LB [icon: gcp-load-balancing, label: "GCP LB\n34.26.94.36"]
  US VM [icon: gcp-compute-engine, label: "e2-medium VM\nus-central1"] {
    US nginx [icon: nginx]
    US Services [icon: server, label: "7 microservices"]
    US PG [icon: postgresql]
    US Redis [icon: redis]
    US RMQ [icon: rabbitmq]
  }
}

APAC Region [icon: gcp-region, color: yellow] {
  APAC LB [icon: gcp-load-balancing, label: "GCP LB\n34.126.131.195"]
  APAC VM [icon: gcp-compute-engine, label: "e2-medium VM\nasia-southeast1"] {
    APAC nginx [icon: nginx]
    APAC Services [icon: server, label: "7 microservices"]
    APAC PG [icon: postgresql]
    APAC Redis [icon: redis]
    APAC RMQ [icon: rabbitmq]
  }
}

Internet -> EU LB: HTTPS
Internet -> US LB: HTTPS
Internet -> APAC LB: HTTPS

EU LB -> EU nginx
US LB -> US nginx
APAC LB -> APAC nginx

EU RMQ <-> US RMQ: RabbitMQ Federation
US RMQ <-> APAC RMQ: RabbitMQ Federation
EU RMQ <-> APAC RMQ: RabbitMQ Federation

EU Journey -> US Services: Cross-region HTTP :8001
EU Journey -> APAC Services: Cross-region HTTP :8001
```

**See:** `report/figures/fig14_dependency_graph.png`

### GCP Configuration

Each VM is `e2-medium` (2 vCPU, 4 GB RAM) running Docker Compose with 12 containers. Journey booking is deployed with `replicas: 2` in compose (two container instances on the same VM). GCP Load Balancers provide stable external IPs that do not change on VM restart. Internal private IPs (`10.0.1.11`, `10.0.4.11`, `10.0.3.11`) are used for inter-VM communication.

---

## 3. API Gateway — nginx

nginx acts as the single entry point for all client traffic on port 80. It handles:

1. **Rate limiting**: `limit_req_zone` at `10r/s` with burst of 50 requests, keyed by client IP. This prevents any single client from overwhelming the backend.

2. **20+ location blocks** routing by path prefix to the correct upstream. Each location uses `proxy_pass` with `Host` and `X-Real-IP` forwarded headers.

3. **SPA fallback**: `try_files $uri $uri/ /index.html` ensures React Router's client-side routing works on direct URL access or page refresh.

4. **Static file serving**: The built React app (`dist/`) is mounted at `/usr/share/nginx/html`. No separate frontend container is needed.

5. **Second listener on :8001**: A separate `server` block on port 8001 forwards directly to the `journey` upstream, used by the admin service for internal cross-region HTTP calls.

### Figure 2 — nginx Routing Map

> **Eraser Diagram** — paste at eraser.io

```
// nginx Routing Map — Sequence Diagram
// Paste into eraser.io → Sequence Diagram

Client -> nginx :80: HTTP Request

nginx -> nginx: rate_limit check (10r/s, burst=50)

// Auth routes
nginx -> auth_service :8000: /auth/* → proxy_pass

// Journey routes
nginx -> journey_booking :8001: /journeys → proxy_pass (2 replicas)

// Conflict routes
nginx -> conflict_detection :8002: /conflicts/slots
nginx -> conflict_detection :8002: /conflicts/reserve-slot
nginx -> conflict_detection :8002: /conflicts/release-slot
nginx -> conflict_detection :8002: /conflicts/*

// Routing service
nginx -> road_routing :8004: /route
nginx -> road_routing :8004: /routes/famous
nginx -> road_routing :8004: /search

// Authority routes (20+ specific paths)
nginx -> traffic_authority :8005: /authority/journeys
nginx -> traffic_authority :8005: /authority/cancel
nginx -> traffic_authority :8005: /authority/closure-preview
nginx -> traffic_authority :8005: /authority/closure
nginx -> traffic_authority :8005: /authority/closures
nginx -> traffic_authority :8005: /authority/segments
nginx -> traffic_authority :8005: /authority/stats

// Admin routes
nginx -> admin_service :8006: /admin/health
nginx -> admin_service :8006: /admin/all-regions
nginx -> admin_service :8006: /admin/latency
nginx -> admin_service :8006: /admin/replicated
nginx -> admin_service :8006: /admin/queue
nginx -> admin_service :8006: /admin/cache
nginx -> admin_service :8006: /admin/stats

// SPA fallback
nginx -> nginx: /health → inline 200 {"status":"ok"}
nginx -> static_files: /* → try_files $uri $uri/ /index.html
```

---

## 4. Service Deep Dives

### 4.1 Auth Service (`auth_service/main.py`)

**Role**: Identity and token management. Runs independently on each region. No cross-region user sync except via the `/auth/sync` endpoint (currently unused by the frontend).

**Key design decisions:**

**Bcrypt hashing**: Passwords are hashed with `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`. The work factor default (~12 rounds) makes brute-force attacks computationally expensive.

**JWT structure**: Access tokens embed all user data the other services need:
```python
payload = {
    "sub": str(user["id"]),        # UUID — used as driver_id
    "email": user["email"],         # passed to conflict check scope
    "name": user["name"],           # used in Telegram notifications
    "role": user["role"],           # driver / authority / admin
    "vehicle_type": user["vehicle_type"],  # STANDARD / EMERGENCY
    "region": REGION,
    "exp": datetime.utcnow() + timedelta(hours=24),
}
```

The `vehicle_type` embedded in the JWT is how the **emergency bypass** works across services. The journey booking service reads `user.get("vehicle_type")` from the decoded token — no extra database lookup is needed.

**Refresh token rotation**: Refresh tokens are UUIDs stored in `refresh_tokens` table with an expiry timestamp. They are **not** JWTs — they cannot be decoded offline. The `POST /auth/refresh` endpoint looks up the token in the database, checks expiry, and issues a new access token.

**Stateless verification**: Every other service (journey_booking, conflict_detection, traffic_authority, admin_service) has an identical `verify_token()` function that decodes the JWT locally using the shared `JWT_SECRET`. No HTTP call to auth_service is needed per request. This means auth_service is **not a single point of failure** for authenticated requests.

### Figure 3 — JWT Token Lifecycle

> **Eraser Sequence Diagram**

```
// JWT Token Lifecycle
// Paste into eraser.io → Sequence Diagram

Client -> auth_service: POST /auth/login {email, password}
auth_service -> PostgreSQL: SELECT user WHERE email = ?
PostgreSQL --> auth_service: user row
auth_service -> auth_service: bcrypt.checkpw(password, hash)
auth_service -> PostgreSQL: INSERT refresh_tokens (uuid, user_id, expires_at)
auth_service --> Client: {access_token (JWT 24h), refresh_token (UUID 7d)}

Client -> any_service: GET /resource Authorization: Bearer {JWT}
any_service -> any_service: jwt.decode(token, JWT_SECRET)
// No network call needed - JWT verified locally
any_service --> Client: 200 OK {data}

// Token expiry
Client -> any_service: GET /resource
any_service --> Client: 401 Token expired

Client -> auth_service: POST /auth/refresh {refresh_token}
auth_service -> PostgreSQL: SELECT WHERE token = ? AND expires_at > NOW()
PostgreSQL --> auth_service: user_id
auth_service -> PostgreSQL: SELECT user WHERE id = user_id
auth_service --> Client: {access_token (new JWT)}
```

### 4.2 Journey Booking (`journey_booking/main.py`)

The most complex service. A booking goes through **8 sequential checks** before being persisted.

#### 4.2.1 Region Detection

```python
EU_KEYWORDS  = ["dublin", "london", "paris", "berlin", ...]
US_KEYWORDS  = ["new york", "los angeles", "chicago", ...]
APAC_KEYWORDS= ["singapore", "tokyo", "sydney", ...]

def detect_region(location: str) -> str:
    loc = location.lower()
    if any(k in loc for k in US_KEYWORDS):  return "US"
    if any(k in loc for k in APAC_KEYWORDS): return "APAC"
    if any(k in loc for k in EU_KEYWORDS):  return "EU"
    return REGION  # fallback to this VM's region
```

Priority order: US > APAC > EU > fallback. The destination's region determines whether the booking is cross-region. The origin region is always the current VM's `REGION` env var.

#### 4.2.2 Emergency Fast Path

```python
if vehicle_type == "EMERGENCY":
    # Skip conflict check, routing, closure check
    # Direct INSERT with status = "EMERGENCY_CONFIRMED"
    await publish_event("emergency_events", ...)
    await publish_event("journey_replication_events", ...)
    return {"status": "EMERGENCY_CONFIRMED", ...}
```

Emergency vehicles bypass 6 of the 8 booking pipeline steps. The only work done is a single DB insert and two RabbitMQ publishes. No OSRM call, no Redis lookup, no closure check. Emergency journeys are also **immune to authority cancellation** (`vehicle_type = 'EMERGENCY'` → 403 if authority attempts cancel).

#### 4.2.3 Full Booking Pipeline

```
Step 1:  Decode JWT                        ~5ms
Step 2:  Emergency check                   ~1ms (exit early if EMERGENCY)
Step 3:  POST road_routing/route           ~200ms (Nominatim geocode × 2 + OSRM)
Step 4:  Extract named segments            ~3ms (dedup + title-case)
Step 5:  POST conflict_detection/check     ~20ms (Redis + PG)
Step 6:  Check active road_closures        ~10ms (PG ILIKE query)
Step 7:  INSERT journeys                   ~18ms
Step 8a: (if cross-region) HTTP POST → dest VM  ~45ms
Step 8b: Publish booking_events + replication_events  ~15ms
```

**See:** `report/figures/fig03_booking_pipeline.png`

#### 4.2.4 Closure Check Implementation

```python
for segment in route_segments:
    seg_name = str(segment).strip()
    cur.execute("""
        SELECT road_name, reason
        FROM road_closures
        WHERE active = TRUE
          AND %s ILIKE concat('%%', road_name, '%%')
    """, (seg_name,))
```

This query asks: "is the segment name a superstring of any active road closure's name?" This is the inverse of the traffic authority cascade which asks "does the closure name appear in the route_segments JSONB?" Both directions use `ILIKE` for case-insensitive matching.

#### 4.2.5 PENDING Auto-Expiry Background Thread

```python
def expire_pending_journeys():
    while True:
        time.sleep(60)
        conn = get_conn()
        cur.execute("""
            UPDATE journeys
            SET status = 'CANCELLED',
                cancelled_reason = 'Auto-expired: not confirmed within 5 minutes'
            WHERE status = 'PENDING'
            AND created_at < NOW() - INTERVAL '5 minutes'
        """)
```

Run as `daemon=True` thread at startup. Polls every 60 seconds. In this system, journeys go directly to `CONFIRMED` (or `EMERGENCY_CONFIRMED`) — `PENDING` is a transient state from an earlier design where confirmation was asynchronous. The expiry still fires to clean up any journeys that got stuck.

**See:** `report/figures/fig01_state_machine.png`

#### 4.2.6 Cross-Region Journey Registration

When `is_cross_region = True`, journey_booking immediately makes an HTTP call to the destination region:

```python
dest_url = REGION_URL_MAP[dest_region]   # e.g. "http://10.0.4.11"
await client.post(f"{dest_url}:8001/journeys/cross-region", json={
    "journey_id": journey_id,
    "origin": req.origin,
    "destination": req.destination,
    "start_time": req.start_time,
    "driver_id": driver_id,
    "from_region": REGION,
})
```

The destination VM's `POST /journeys/cross-region` handler uses `ON CONFLICT (id) DO NOTHING` to ensure idempotency — if the message is retried, the second insert is silently ignored. It also records the event in `cross_region_events` for audit.

### 4.3 Conflict Detection (`conflict_detection/main.py`)

Two-tier conflict checking: Redis (fast path) then PostgreSQL (authoritative path).

#### 4.3.1 Slot Time Quantization

```python
def round_to_slot(dt: datetime) -> str:
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0).isoformat()
```

All times are snapped to the nearest 30-minute boundary. This means `09:17` and `09:43` are in different slots, but `09:01` and `09:29` are the same slot. There are 32 slots covering 06:00–22:00 (16 hours × 2 slots/hr).

#### 4.3.2 Ghost Reservation vs Confirmed Booking

There are two distinct Redis key patterns:

| Key | Purpose | TTL |
|-----|---------|-----|
| `slot_hold:{origin}:{dest}:{slot}` | Ghost reservation — slot held while form is being filled | 120s |
| `lock:{driver_id}:{origin}:{dest}:{slot}` | Post-conflict-check lock — this driver just checked this slot | 60s |

The `slot_hold` key stores a JSON value `{"driver_id": "...", "reserved_at": "..."}`. The `release-slot` endpoint verifies the driver_id matches before deleting — another driver cannot release someone else's hold:

```python
data = json.loads(redis_client.get(hold_key))
if data.get("driver_id") == req.driver_id:
    redis_client.delete(hold_key)
    return {"released": True}
return {"released": False, "reason": "Not your hold"}
```

#### 4.3.3 Slot Grid Construction

`GET /conflicts/slots` returns 32 slots in three states:

1. `available: true` — no DB booking, no Redis hold
2. `available: false, reason: "booked"` — confirmed/pending journey exists in DB
3. `available: false, reason: "being_selected"` — Redis ghost hold active, with `held_by_you: bool`

The `held_by_you` flag lets the frontend show a different colour for your own hold vs another user's hold.

**See:** `report/figures/fig04_ghost_reservation.png` and `report/figures/fig06_slot_heatmap.png`

### 4.4 Road Routing (`road_routing/main.py`)

**External service integrations:**

1. **Nominatim** (`nominatim.openstreetmap.org`) — geocodes place names to lat/lon coordinates. Results cached in Redis for 24 hours with key `nominatim:{query}:{limit}`. TTL 86400 seconds.

2. **OSRM** (`router.project-osrm.org`) — calculates driving routes. Returns distance in metres, duration in seconds, and turn-by-turn steps with road names. Called with `overview=full`, `geometries=geojson`, `steps=true`.

**Segment extraction:**
```python
def extract_segments(route_data: dict) -> List[str]:
    seen = set()
    segments = []
    for step in steps:
        name = step.get("name", "").strip()
        if name and name.lower() not in ("", "unnamed road") and len(name) > 1 and name not in seen:
            seen.add(name)
            segments.append(name.title())   # "parnell street" → "Parnell Street"
        if len(segments) >= 20: break
    return segments
```

Three filters: (1) not empty, (2) not "unnamed road", (3) not a duplicate. Capped at 20 segments. Title-cased for consistency. These exact strings are what traffic authority uses for road closures.

**Famous routes**: 11 hardcoded routes (5 EU, 3 US, 3 APAC) bypass the OSRM call for quick demos.

### 4.5 Traffic Authority (`traffic_authority/main.py`)

#### 4.5.1 Road Segments Endpoint

```python
@app.get("/authority/segments")
def get_road_segments(...):
    cur.execute("""
        SELECT DISTINCT
            jsonb_array_elements(route_segments::jsonb)->>'name' AS segment
        FROM journeys
        WHERE route_segments IS NOT NULL
          AND route_segments != '[]'
          AND status IN ('CONFIRMED', 'PENDING')
          AND start_time > NOW()
        ORDER BY segment
    """)
```

This uses PostgreSQL's `jsonb_array_elements` to unnest the JSONB array stored in `route_segments` and extract the `name` field from each element. **Crucially**, it only returns segments from **future, active journeys** — so the authority always picks a name that will actually match at least one journey. This prevents the common mistake of closing a road with a name that was never in any booking.

#### 4.5.2 Closure Preview (Dry-Run)

```python
@app.get("/authority/closure-preview")
def preview_closure(road_name: str, ...):
    cur.execute("""
        SELECT id, origin, destination, start_time,
               vehicle_type, status, driver_email
        FROM journeys
        WHERE route_segments::text ILIKE %s
          AND status IN ('CONFIRMED', 'PENDING', 'EMERGENCY_CONFIRMED')
          AND start_time > NOW()
    """, (f"%{road_name}%",))
```

Returns exactly which journeys would be cancelled, with emergency journeys counted separately and **excluded** from cancellation. The preview is a read-only operation — no data is modified. The frontend shows this before confirming.

#### 4.5.3 Closure Cascade

```python
# Cancel affected journeys
cur.execute("""
    UPDATE journeys SET status = 'AUTHORITY_CANCELLED', cancelled_reason = %s
    WHERE route_segments::text ILIKE %s
    AND status IN ('CONFIRMED', 'PENDING')
    AND start_time > NOW()
    RETURNING id, driver_id, driver_email, origin, destination, start_time
""", (f"Road closure: {req.road_name} — {req.reason}", f"%{req.road_name}%"))
cancelled_rows = cur.fetchall()

# One RabbitMQ message per cancelled journey
for r in cancelled_rows:
    await publish_event("road_closure_events", {
        "journey_id": str(r[0]),
        "driver_email": r[2] or "",
        "origin": r[3],
        "destination": r[4],
        "start_time": str(r[5]),
        "road_name": req.road_name,
        "closure_reason": req.reason,
        ...
    })
```

**Key design choice**: One message per cancelled journey (not one summary message). This gives the notification service the full driver context — email, route, time — needed for a personalised Telegram message.

**See:** `report/figures/fig12_closure_cascade.png`

### 4.6 Notification (`notification/main.py`)

#### 4.6.1 Consumer Architecture

The notification service is a pure event consumer. It has no REST endpoints except `/health`. At startup it creates an asyncio task that:

1. Waits 10 seconds for RabbitMQ to be ready
2. Opens an `aio_pika.connect_robust` connection (auto-reconnects on drop)
3. Declares 6 durable queues
4. Sets `prefetch_count=10` — processes up to 10 messages concurrently
5. Registers 6 async consumer callbacks
6. Awaits indefinitely (`asyncio.Future()`)
7. On any exception, sleeps 5s and reconnects

```python
await channel.set_qos(prefetch_count=10)
booking_q     = await channel.declare_queue("booking_events",                durable=True)
emergency_q   = await channel.declare_queue("emergency_events",              durable=True)
closure_q     = await channel.declare_queue("road_closure_events",           durable=True)
cancel_q      = await channel.declare_queue("journey_cancelled_events",      durable=True)
force_q       = await channel.declare_queue("journey_force_cancelled_events",durable=True)
replication_q = await channel.declare_queue("journey_replication_events",    durable=True)
```

**Durability**: All queues and messages are declared as `durable=True` and `DeliveryMode.PERSISTENT`. If RabbitMQ restarts, messages are not lost.

**Message acknowledgement**: Booking/emergency/closure/cancel queues use `requeue=True` — if processing fails (Telegram error), the message is put back in the queue. The replication queue uses `requeue=False` — a failed DB insert is logged but not retried, to avoid duplicate replication attempts.

#### 4.6.2 Data Replication via Notification

```python
async def replicate_journey(event_data: dict):
    if event_data.get("origin_region") == REGION:
        return   # skip events originated here — already in primary journeys table
    
    cur.execute("""
        INSERT INTO replicated_journeys (id, origin_region, ...)
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            replicated_at = NOW()
    """, (...))
```

The `ON CONFLICT DO UPDATE` (upsert) pattern ensures that if a journey is updated (e.g. cancelled after being confirmed), the replicated copy is kept in sync. The `origin_region == REGION` guard prevents a region from replicating its own journeys to itself.

**See:** `report/figures/fig02_rabbitmq_topology.png` and `report/figures/fig05_replication_timeline.png`

### 4.7 Admin Service (`admin_service/main.py`)

#### 4.7.1 Parallel Health Probing

```python
async def health_check(...):
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[check_service(client, name, port) for name, port in SERVICES]
        )
```

All 7 services are probed **concurrently** via `asyncio.gather`. The total health check time is bounded by the slowest single probe (~3s timeout), not the sum of all probes. Each probe measures its own response time in milliseconds.

#### 4.7.2 P95 Latency Sampling

```python
async def measure_service(name: str, port: int) -> dict:
    samples = []
    for _ in range(5):
        t0 = time.time()
        r = await asyncio.wait_for(client.get(f"http://{name}:{port}/health"), timeout=3)
        samples.append(int((time.time() - t0) * 1000))
    samples.sort()
    p50 = samples[len(samples) // 2]
    p95 = samples[int(len(samples) * 0.95)]
    return {"p50_ms": p50, "p95_ms": p95, ...}
```

5 samples per service, sorted, then P95 = index at 95th percentile. SLA check: `max(p95_values) <= 500ms`.

#### 4.7.3 Fan-Out Region Aggregation

```python
region_urls = {
    "EU":   f"{REGION_EU_URL}:8006",
    "US":   f"{REGION_US_URL}:8006",
    "APAC": f"{REGION_APAC_URL}:8006",
}
tasks = [fetch_region(k, v) for k, v in region_urls.items()]
pairs = await asyncio.gather(*tasks)
```

The admin service fans out to all three regions simultaneously using `asyncio.gather`. Each region's admin service returns its local stats. The EU admin aggregates all three responses into a single JSON object for the frontend.

**See:** `report/figures/fig07_service_latency.png`

---

## 5. Distributed Systems Concepts

### 5.1 Eventual Consistency

TrafficBook implements **eventual consistency** for cross-region data replication. The consistency model is:

- **Within a region**: Strong consistency. PostgreSQL provides ACID transactions. A write is immediately visible to all reads within the same region.
- **Across regions**: Eventual consistency. A booking on EU will eventually appear in US and APAC's `replicated_journeys` table, but there is a lag (typically 2–5 seconds, depending on RabbitMQ federation propagation time).

The `replicated_journeys` table is explicitly designed for this — it is not the primary `journeys` table, but a replica for observability and eventual consistency demonstration.

```
EU books journey → INSERT journeys (immediate, strong)
                 → publish journey_replication_events
                    ↓ (async, federation propagates ~2-5s)
US notification → INSERT replicated_journeys (eventual)
APAC notification → INSERT replicated_journeys (eventual)
```

**Evidence in code**: `replicate_journey()` in `notification/main.py` logs:
```
Replicated journey {id[:8]} from EU to US
```

**See:** `report/figures/fig05_replication_timeline.png`

### 5.2 Ghost Reservations (Optimistic Locking)

Ghost reservations implement a form of **optimistic concurrency control** for time slots. Instead of a pessimistic lock (which would require the client to hold a database transaction open while filling the form), the system uses a soft Redis lock with a TTL.

The protocol has two phases:
1. **Reserve**: `POST /conflicts/reserve-slot` → `SETEX slot_hold:... 120 {driver_id}`
2. **Book or Release**: Either `POST /journeys` (consumes the reservation) or `POST /conflicts/release-slot` (explicit release)

The TTL ensures that abandoned holds (user navigates away without releasing) expire automatically after 120 seconds.

**Race condition analysis**: If two users click the same slot within the 120s window:
- User A's `reserve-slot` succeeds → Redis key set
- User B's `GET /conflicts/slots` returns `being_selected` for that slot
- User B cannot book the slot until A's TTL expires or A releases it
- If A and B both reach `POST /journeys` simultaneously, only one will succeed because `POST /check` reads the Redis key before the slot is confirmed in the DB

**See:** `report/figures/fig04_ghost_reservation.png`

### 5.3 Per-Driver Conflict Scoping

A critical design decision: conflicts are scoped **per driver**, not per route globally.

```python
# Redis key includes driver_id
lock_key = f"lock:{driver_id}:{origin}:{destination}:{slot}"

# PostgreSQL check filters by driver_id
cur.execute("""
    SELECT id FROM journeys
    WHERE driver_id = %s
    AND origin = %s AND destination = %s
    AND start_time BETWEEN %s AND %s
    AND status NOT IN ('CANCELLED', 'AUTHORITY_CANCELLED')
""", (driver_id, req.origin, req.destination, window_start, window_end))
```

This means Alice and Bob can both book Dublin→Cork at 09:00 — they will both get confirmed. Only Alice cannot book Dublin→Cork at 09:00 if she already has a booking there. This models the real-world constraint that roads have capacity for multiple vehicles, but individual drivers shouldn't double-book.

**Contrast with global slot locking**: A global lock would prevent any second booking on the same route+slot, which would be unrealistically restrictive for a road (as opposed to a seat on a plane).

### 5.4 Cross-Region Communication

Two mechanisms are used:

**Synchronous HTTP** (for immediate data consistency):
- Journey booking calls the destination VM immediately after inserting locally
- Uses `httpx.AsyncClient(timeout=5)` — if the remote VM is down, the booking still succeeds locally (the error is swallowed: `except Exception as e: print(...)`)
- This means cross-region journeys are **best-effort** — the destination VM records them when reachable

**Asynchronous RabbitMQ** (for eventual consistency):
- Every booking publishes to `journey_replication_events`
- RabbitMQ federation copies this to all other VMs
- Each VM's notification service consumes it and writes to `replicated_journeys`
- The replication is unordered — cancellations might arrive before bookings, but the `ON CONFLICT DO UPDATE` upsert handles status updates correctly

**See:** `report/figures/fig10_cross_region_flow.png`

### 5.5 Emergency Vehicle Priority (Bypass Pattern)

The emergency bypass pattern demonstrates **priority lanes** in distributed systems:

```python
# In JWT payload:
"vehicle_type": "EMERGENCY"

# In journey_booking:
if vehicle_type == "EMERGENCY":
    # Skip: conflict check, routing, closure check
    # Direct CONFIRMED status
    return EMERGENCY_CONFIRMED immediately

# In traffic_authority:
if status == "EMERGENCY_CONFIRMED" or vehicle_type == "EMERGENCY":
    raise HTTPException(403, "Emergency journeys cannot be force cancelled")

# In conflict_detection /slots:
if vehicle_type == "EMERGENCY":
    # All 32 slots shown as available regardless of actual occupancy
    return [{"available": True, "reason": "emergency_bypass"} for ...]
```

This demonstrates a common distributed systems pattern: **priority queuing / fast path** — high-priority requests skip expensive operations and receive preferential treatment throughout the entire system.

### 5.6 PENDING Auto-Expiry (TTL Pattern)

```python
# Background daemon thread - runs every 60 seconds
UPDATE journeys SET status = 'CANCELLED'
WHERE status = 'PENDING'
AND created_at < NOW() - INTERVAL '5 minutes'
```

This is a **time-to-live (TTL) cleanup pattern** — resources in a transitional state are automatically reclaimed after a timeout. It prevents resource leakage (stuck PENDING journeys consuming slots indefinitely) and is analogous to how Redis TTLs work, but applied to relational database rows via a polling thread.

The thread runs as `daemon=True`, meaning it will terminate automatically when the main process exits (no cleanup needed).

### 5.7 CAP Theorem Analysis

**See:** `report/figures/fig13_cap_theorem.png`

TrafficBook's CAP positioning:

- **Consistency (C)**: Each region's PostgreSQL is strongly consistent for local operations. Cross-region consistency is eventually consistent.
- **Availability (A)**: Any region continues to serve requests independently even if other regions are unreachable. A network partition between EU and US does not prevent EU from accepting bookings.
- **Partition Tolerance (P)**: The system is designed to tolerate inter-region network partitions. The three regions are independently deployable.

**Verdict**: TrafficBook is **AP at the global level** (chooses Availability + Partition Tolerance over global Consistency) and **CA at the regional level** (strong consistency within each region).

This is the classic pattern for distributed systems that prioritise uptime: accept that data may be temporarily inconsistent across regions, but guarantee that each region always responds.

### 5.8 BASE vs ACID

| Guarantee | PostgreSQL (per region) | Cross-region via RabbitMQ |
|-----------|------------------------|---------------------------|
| Basically Available | Yes | Yes (federation recovers) |
| Soft state | No (hard ACID) | Yes (replicated_journeys may lag) |
| Eventually consistent | N/A | Yes |
| Atomicity | Yes (per-transaction) | No (multi-VM transactions don't exist) |
| Consistency | Yes | No |
| Isolation | Yes | No |
| Durability | Yes | Yes (durable queues + PG persistence) |

### 5.9 Fault Isolation

Each region is **fully self-contained**. If the US VM becomes unreachable:
- EU and APAC continue serving EU/APAC bookings normally
- Cross-region bookings destined for US silently fail the HTTP forward (error is caught and logged)
- RabbitMQ federation handles the disconnection: messages queue up locally and are delivered when connectivity resumes
- The admin service's `/admin/all-regions` returns `{"error": "..."}` for US but still returns EU and APAC data

This is **bulkhead isolation** — failure in one region does not cascade to others.

---

## 6. Data Flows

### 6.1 Standard Booking (Dublin → Cork)

> **Eraser Sequence Diagram** — paste at eraser.io

```
// Standard Booking Flow
// Paste into eraser.io → Sequence Diagram

Browser -> nginx: POST /journeys {origin:"Dublin", destination:"Cork", start_time}
nginx -> journey_booking: proxy_pass :8001

journey_booking -> journey_booking: verify JWT → role=driver, vehicle_type=STANDARD

// Step 3: Get route
journey_booking -> road_routing: POST /route {origin, destination}
road_routing -> Redis: GET nominatim:dublin:1
Redis --> road_routing: cache miss
road_routing -> Nominatim: GET ?q=Dublin&format=json
Nominatim --> road_routing: [{lon: -6.26, lat: 53.33}]
road_routing -> Redis: SETEX nominatim:dublin:1 86400 [...]
road_routing -> Nominatim: GET ?q=Cork&format=json
Nominatim --> road_routing: [{lon: -8.47, lat: 51.90}]
road_routing -> OSRM: GET /route/v1/driving/-6.26,53.33;-8.47,51.90?steps=true
OSRM --> road_routing: {routes:[{steps:[{name:"N7",...},...], distance:256000, duration:9900}]}
road_routing -> road_routing: extract_segments() → ["N7","M50","Parnell Street",...]
road_routing --> journey_booking: {segments:[...], distance_km:256, duration_mins:165}

// Step 5: Conflict check
journey_booking -> conflict_detection: POST /check {origin, destination, start_time, segments, driver_id}
conflict_detection -> Redis: GET slot_hold:Dublin:Cork:09:00
Redis --> conflict_detection: nil (no hold)
conflict_detection -> PostgreSQL: SELECT WHERE driver_id=? AND route=? AND time BETWEEN ?
PostgreSQL --> conflict_detection: 0 rows (no conflict)
conflict_detection -> Redis: SETEX lock:driver123:Dublin:Cork:09:00 60 "reserved"
conflict_detection --> journey_booking: {conflict: false}

// Step 6: Closure check
journey_booking -> PostgreSQL: SELECT FROM road_closures WHERE active=TRUE AND segment ILIKE road_name
PostgreSQL --> journey_booking: 0 rows (no closure)

// Step 7: Insert
journey_booking -> PostgreSQL: INSERT INTO journeys (...) RETURNING id, created_at
PostgreSQL --> journey_booking: {id: "uuid", created_at: "2026-..."}

// Step 8: Publish events
journey_booking -> RabbitMQ: publish booking_events {event_type:"journey_confirmed",...}
journey_booking -> RabbitMQ: publish journey_replication_events {same payload}
RabbitMQ -> notification: on_booking callback
notification -> Telegram: "Journey CONFIRMED ✅ Dublin→Cork..."

// Replication to other regions (async, ~2-5s later)
RabbitMQ --> US notification: journey_replication_events (via federation)
US notification -> US PostgreSQL: INSERT replicated_journeys ON CONFLICT DO UPDATE
RabbitMQ --> APAC notification: journey_replication_events (via federation)
APAC notification -> APAC PostgreSQL: INSERT replicated_journeys ON CONFLICT DO UPDATE

journey_booking --> nginx: {id, status:"CONFIRMED", region:"EU", ...}
nginx --> Browser: 201 Created
```

### 6.2 Cross-Region Booking (Dublin → New York)

```
// Cross-Region Booking
// Paste into eraser.io → Sequence Diagram

Browser -> EU nginx: POST /journeys {origin:"Dublin", destination:"New York"}

EU journey_booking -> EU journey_booking: detect_region("New York") = "US"
// is_cross_region = True, dest_region = "US"

EU journey_booking -> EU conflict_detection: POST /check (same as standard)
EU journey_booking -> EU road_routing: POST /route (same as standard)
EU journey_booking -> EU PostgreSQL: INSERT journeys (region="EU", dest_region="US", is_cross_region=true)

// Immediate synchronous forward to US
EU journey_booking -> US journey_booking: POST :8001/journeys/cross-region {journey_id, origin, dest, start_time, driver_id, from_region:"EU"}
US journey_booking -> US PostgreSQL: INSERT journeys ON CONFLICT (id) DO NOTHING (region="US", is_cross_region=true)
US journey_booking -> US RabbitMQ: publish journey_replication_events {origin_region:"EU"}
US journey_booking --> EU journey_booking: {status:"registered"}

// Async replication
EU RabbitMQ -> EU RabbitMQ: publish journey_replication_events
EU RabbitMQ -->> APAC RabbitMQ: federation propagates (~2-5s)
APAC notification -> APAC PostgreSQL: INSERT replicated_journeys

EU journey_booking --> Browser: {id, status:"CONFIRMED", is_cross_region:true, dest_region:"US"}
```

### 6.3 Emergency Booking

```
// Emergency Vehicle Booking
// Paste into eraser.io → Sequence Diagram

Browser -> nginx: POST /journeys (JWT contains vehicle_type="EMERGENCY")
nginx -> journey_booking: proxy

journey_booking -> journey_booking: vehicle_type == "EMERGENCY" → fast path

// SKIP: routing, conflict check, closure check

journey_booking -> PostgreSQL: INSERT journeys (status="EMERGENCY_CONFIRMED")
journey_booking -> RabbitMQ: publish emergency_events
journey_booking -> RabbitMQ: publish journey_replication_events
RabbitMQ -> notification: on_emergency callback
notification -> Telegram: "EMERGENCY JOURNEY APPROVED 🚨 Dublin→Cork"

journey_booking --> Browser: {status:"EMERGENCY_CONFIRMED"} (< 50ms total)
// Compare: standard booking ~317ms, emergency ~28ms
```

### 6.4 Road Closure Cascade

**See:** `report/figures/fig12_closure_cascade.png`

```
// Road Closure Cascade
// Paste into eraser.io → Sequence Diagram

Authority Browser -> nginx: POST /authority/closure {road_name:"Parnell Street", reason:"Roadworks"}
nginx -> traffic_authority: proxy

// Role check
traffic_authority -> traffic_authority: verify_token → role must be "traffic_authority" or "admin"

// Insert closure record
traffic_authority -> PostgreSQL: INSERT road_closures RETURNING closure_id

// Count emergency journeys that would be skipped
traffic_authority -> PostgreSQL: SELECT COUNT(*) WHERE route_segments ILIKE '%Parnell Street%' AND status='EMERGENCY_CONFIRMED'
PostgreSQL --> traffic_authority: 1 emergency journey (will NOT be cancelled)

// Cancel all non-emergency future journeys passing through this road
traffic_authority -> PostgreSQL: UPDATE journeys SET status='AUTHORITY_CANCELLED' WHERE route_segments::text ILIKE '%Parnell Street%' AND status IN ('CONFIRMED','PENDING') AND start_time > NOW() RETURNING per-row driver details
PostgreSQL --> traffic_authority: 3 cancelled journeys with driver_email, origin, destination, start_time

// One message per cancelled journey
traffic_authority -> RabbitMQ: publish road_closure_events {journey_id:1, driver_email:"alice@...", ...}
traffic_authority -> RabbitMQ: publish road_closure_events {journey_id:2, driver_email:"bob@...", ...}
traffic_authority -> RabbitMQ: publish road_closure_events {journey_id:3, driver_email:"charlie@...", ...}

// Notification service handles each independently
RabbitMQ -> notification: on_closure(journey 1)
notification -> Telegram: "Road Closure — Journey Cancelled ⚠️ Alice: Dublin→Cork"
RabbitMQ -> notification: on_closure(journey 2)
notification -> Telegram: "Road Closure — Journey Cancelled ⚠️ Bob: Dublin→Galway"
RabbitMQ -> notification: on_closure(journey 3)
notification -> Telegram: "Road Closure — Journey Cancelled ⚠️ Charlie: Dublin→Belfast"

traffic_authority --> Authority Browser: {closure_id, affected_journeys:3, emergency_skipped:1}
```

### 6.5 Data Replication Pipeline

The full replication path from EU booking to APAC `replicated_journeys`:

```
1. EU: INSERT journeys (PG)
2. EU: publish journey_replication_events (RabbitMQ, durable)
3. RabbitMQ EU federation-upstream → US RabbitMQ (~1s)
4. RabbitMQ EU federation-upstream → APAC RabbitMQ (~2s)
5. US notification: on_replication() → origin_region="EU" ≠ "US" → proceed
6. US notification: INSERT replicated_journeys ON CONFLICT DO UPDATE
7. APAC notification: on_replication() → origin_region="EU" ≠ "APAC" → proceed
8. APAC notification: INSERT replicated_journeys ON CONFLICT DO UPDATE
9. GET /admin/replicated → shows count of EU-originated rows on US/APAC
```

---

## 7. Database Schema

### Figure 4 — Entity Relationship Diagram

> **Eraser ERD** — paste at eraser.io

```
// TrafficBook Database Schema — ERD
// Paste into eraser.io → Entity Relationship Diagram

users [icon: table, color: blue] {
  id UUID [pk, default: gen_random_uuid()]
  email TEXT [unique, not null]
  name TEXT [not null]
  password TEXT [not null, note: "bcrypt hash"]
  role TEXT [default: "driver", note: "driver | authority | admin"]
  vehicle_type TEXT [default: "STANDARD", note: "STANDARD | EMERGENCY"]
  region TEXT [not null, note: "EU | US | APAC"]
  created_at TIMESTAMP [default: NOW()]
}

refresh_tokens [icon: table, color: blue] {
  id UUID [pk]
  user_id UUID [ref: > users.id, note: "CASCADE DELETE"]
  token TEXT [unique, not null, note: "UUID v4 — opaque"]
  expires_at TIMESTAMP [not null]
  created_at TIMESTAMP [default: NOW()]
}

journeys [icon: table, color: green] {
  id UUID [pk, default: gen_random_uuid()]
  driver_id TEXT [not null, note: "JWT sub — user UUID as string"]
  driver_email TEXT
  origin TEXT [not null]
  destination TEXT [not null]
  start_time TIMESTAMP [not null]
  status TEXT [default: "PENDING", note: "PENDING|CONFIRMED|CANCELLED|AUTHORITY_CANCELLED|EMERGENCY_CONFIRMED"]
  region TEXT [not null, note: "Origin region (this VM)"]
  dest_region TEXT [note: "Destination region if cross-region"]
  is_cross_region BOOLEAN [default: false]
  vehicle_type TEXT [default: "STANDARD"]
  route_segments JSONB [default: "[]", note: "Array of road name strings"]
  route_id TEXT [note: "Famous route ID if used"]
  distance_km FLOAT
  duration_mins INTEGER
  cancelled_reason TEXT
  created_at TIMESTAMP [default: NOW()]
}

cross_region_events [icon: table, color: purple] {
  id UUID [pk]
  journey_id UUID [ref: > journeys.id]
  from_region TEXT [not null]
  to_region TEXT [not null]
  event_type TEXT [not null, note: "arrival | departure"]
  delivered BOOLEAN [default: false]
  created_at TIMESTAMP [default: NOW()]
}

road_closures [icon: table, color: red] {
  id UUID [pk, default: gen_random_uuid()]
  road_name TEXT [not null]
  region TEXT [not null]
  reason TEXT
  active BOOLEAN [default: true]
  is_active BOOLEAN [default: true, note: "mirror of active"]
  created_by TEXT [not null, note: "authority email"]
  created_at TIMESTAMP [default: NOW()]
}

replicated_journeys [icon: table, color: orange] {
  id UUID [pk, note: "Same UUID as origin journeys.id"]
  origin_region TEXT [not null, note: "EU | US | APAC — where booking was made"]
  driver_id UUID
  driver_email TEXT
  origin TEXT
  destination TEXT
  start_time TIMESTAMP
  status TEXT [note: "Upserted on status changes"]
  vehicle_type TEXT
  route_segments JSONB [default: "[]"]
  distance_km FLOAT
  duration_mins INTEGER
  is_cross_region BOOLEAN [default: false]
  dest_region TEXT
  replicated_at TIMESTAMP [default: NOW(), note: "When this VM received the event"]
  original_created_at TIMESTAMP
}
```

### Index Strategy

```sql
-- Hot query paths covered by indexes
CREATE INDEX idx_journeys_region  ON journeys(region);       -- admin/authority list queries
CREATE INDEX idx_journeys_status  ON journeys(status);       -- PENDING expiry, status counts
CREATE INDEX idx_journeys_driver  ON journeys(driver_id);    -- GET /journeys per user
CREATE INDEX idx_rep_origin_region ON replicated_journeys(origin_region);  -- /admin/replicated
CREATE INDEX idx_rep_driver        ON replicated_journeys(driver_id);
```

**Missing index note**: The road closure cascade query `WHERE route_segments::text ILIKE '%road_name%'` does a full table scan (ILIKE on a JSONB cast prevents index use). This is acceptable for the current data volume but would need a full-text index (`GIN on route_segments`) at scale.

---

## 8. RabbitMQ Architecture

**See:** `report/figures/fig02_rabbitmq_topology.png`

### Queue Inventory

| Queue | Publisher | Consumer | Requeue on fail | Purpose |
|-------|-----------|----------|-----------------|---------|
| `booking_events` | journey_booking | notification | Yes | Telegram: CONFIRMED |
| `emergency_events` | journey_booking | notification | Yes | Telegram: EMERGENCY |
| `road_closure_events` | traffic_authority | notification | Yes | Telegram: CLOSURE |
| `journey_cancelled_events` | journey_booking | notification | Yes | Telegram: CANCELLED |
| `journey_force_cancelled_events` | traffic_authority | notification | Yes | Telegram: FORCE CANCEL |
| `journey_replication_events` | journey_booking, cross-region | notification | No | replicated_journeys upsert |

### Federation Configuration

```ini
# rabbitmq/rabbitmq.conf
loopback_users.guest = false    # Allow guest user from non-loopback IPs

# rabbitmq/enabled_plugins
[rabbitmq_management, rabbitmq_federation, rabbitmq_federation_management]
```

Federation is configured via the RabbitMQ management UI (not in config files). Each VM defines federation upstreams pointing to the other two VMs' private IPs. The `journey_replication_events` queue is federated so messages published on EU automatically appear in the US and APAC queues.

### Message Durability

All messages are published with:
```python
delivery_mode=aio_pika.DeliveryMode.PERSISTENT
```
And all queues are declared with `durable=True`. This means messages survive a RabbitMQ broker restart — they are written to disk before the broker ACKs the publish.

---

## 9. Redis Architecture

**See:** `report/figures/fig11_redis_keys.png`

### Key Patterns

| Pattern | TTL | Set by | Read by | Purpose |
|---------|-----|--------|---------|---------|
| `slot_hold:{origin}:{dest}:{slot}` | 120s | `POST /reserve-slot` | `GET /slots`, `POST /release-slot` | Ghost reservation |
| `lock:{driver_id}:{origin}:{dest}:{slot}` | 60s | `POST /check` | `POST /check` (existence) | Post-conflict lock |
| `lock:cross_region:{origin}:{dest}:{start_time}` | 3600s | `POST /cross-region` | (unused currently) | Idempotency guard |
| `nominatim:{query}:{limit}` | 86400s | `GET /search` (miss) | `GET /search` (hit) | Geocode cache |

### Redis Client Configuration

```python
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=5,           # 5s read/write timeout
    socket_connect_timeout=5,   # 5s connection timeout
)
```

The `socket_timeout=5` prevents Redis calls from hanging indefinitely on network issues. All Redis operations in the conflict service are wrapped in `try/except` — a Redis failure degrades gracefully (conflict check proceeds to PostgreSQL fallback).

---

## 10. Security Architecture

### JWT Claims — What Each Service Uses

| Claim | auth_service | journey_booking | conflict_detection | traffic_authority | admin_service |
|-------|-------------|-----------------|-------------------|------------------|--------------|
| `sub` | issues | driver_id | driver_id for scoping | — | — |
| `email` | issues | Telegram notification | driver_id for scoping | cancelled_by | — |
| `name` | issues | Telegram notification | — | — | — |
| `role` | issues | list_journeys visibility | — | require_role check | require_role check |
| `vehicle_type` | issues | emergency fast path | emergency bypass | emergency immunity | — |
| `region` | issues | — | — | — | — |

### Role-Based Access Control

```python
def require_role(*roles):
    def dep(user=Depends(verify_token)):
        if user.get("role") not in roles:
            raise HTTPException(403, "Insufficient role")
        return user
    return dep

# Usage:
@app.get("/authority/journeys")
def list_journeys(user=Depends(require_role("traffic_authority", "admin"))):
    ...
```

Three roles: `driver` (can only see and manage their own journeys), `traffic_authority` (sees all journeys, manages closures, cancels individual journeys), `admin` (all of the above plus scaling, cross-region stats, replication data).

### nginx Rate Limiting

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
...
limit_req zone=api burst=50 nodelay;
```

10 requests/second per IP, with a burst allowance of 50. `nodelay` means burst requests are not queued — they are processed immediately up to the burst limit, then rejected with 429.

---

## 11. Observability

### Prometheus Scrape Targets

```yaml
# prometheus/prometheus.yml
scrape_configs:
  - job_name: trafficbook
    static_configs:
      - targets: [auth_service:8000, journey_booking:8001, conflict_detection:8002,
                  notification:8003, road_routing:8004, traffic_authority:8005, admin_service:8006]
    metrics_path: /metrics
  - job_name: rabbitmq
    static_configs: [{targets: ['rabbitmq:15692']}]
  - job_name: postgres
    static_configs: [{targets: ['postgres:9187']}]
```

Prometheus scrapes all 7 FastAPI services, RabbitMQ (via the management plugin's Prometheus endpoint on :15692), and PostgreSQL (via a postgres_exporter sidecar on :9187).

### Admin Dashboard Metrics

| Endpoint | Data source | What it shows |
|----------|------------|---------------|
| `/admin/health` | HTTP `/health` probes | Status + response time per service |
| `/admin/latency` | 5× HTTP samples per service | P50/P95 latency + SLA pass/fail |
| `/admin/queue` | RabbitMQ HTTP API `/api/queues` | Queue depths per queue |
| `/admin/cache` | Redis `INFO` command | Hit rate, hits, misses, memory |
| `/admin/stats` | PostgreSQL | Journeys by status, by hour, cross-region count, emergency count |
| `/admin/all-regions` | Fan-out to all 3 `/admin/stats` | Unified view across regions |
| `/admin/replicated` | PostgreSQL `replicated_journeys` | Cross-region replication status |

---

## 12. Testing

### E2E Test Suite (`test/test_e2e.py`)

11 test sections, each named as `TEST N — Description`:

| Test | What it verifies |
|------|-----------------|
| 1. Health checks | All 3 LBs + 7 services per region = 24 health endpoints |
| 2. Auth login | All 4 users (driver, emergency, authority, admin) × 3 regions |
| 3. Famous routes | All 3 regions return ≥ 11 routes |
| 4. Road routing | OSRM route returns `distance_km` and `segments` |
| 5. Standard booking | CONFIRMED status, ID returned |
| 6. Ghost reservation | Two concurrent same-user bookings → one 409 |
| 7. Emergency | Returns `EMERGENCY_CONFIRMED` immediately |
| 8. Cross-region | `is_cross_region=true`, `dest_region="US"`, journey appears in US DB |
| 9. Traffic authority | Create road closure, see affected_journeys count |
| 10. Admin | Health check, all-regions response |
| 11. VM failure | Manual test — instructions printed, not automated |

### k6 Load Test (`loadtest/booking_test.js`)

```
Stages:
  0→30s: ramp to 10 VUs
 30→90s: ramp to 50 VUs
 90→120s: ramp to 100 VUs
120→150s: ramp down to 0

Thresholds:
  p(95) < 500ms
  error rate < 5%
```

Tests randomly across all 3 regions and 3 route types (EU/US/APAC destinations).

**See:** `report/figures/fig08_load_test.png`

---

## 13. Figures Index

All figures generated by `python3 report/visualize.py` → saved to `report/figures/`

| File | Description | Section Reference |
|------|-------------|------------------|
| `fig01_state_machine.png` | Journey status state machine | §4.2, §5 |
| `fig02_rabbitmq_topology.png` | RabbitMQ publishers → queues → consumers | §8, §4.6 |
| `fig03_booking_pipeline.png` | Booking pipeline step latency waterfall | §4.2.3, §6.1 |
| `fig04_ghost_reservation.png` | Ghost reservation protocol timeline | §4.3.2, §5.2 |
| `fig05_replication_timeline.png` | Eventual consistency replication timeline | §5.1, §6.5 |
| `fig06_slot_heatmap.png` | Slot availability heatmap (peak/off-peak) | §4.3.3 |
| `fig07_service_latency.png` | P50/P95 latency per service | §4.7.2, §11 |
| `fig08_load_test.png` | k6 load test performance profile | §12 |
| `fig09_journey_distribution.png` | Journey status distribution by region | §4.7.3 |
| `fig10_cross_region_flow.png` | Cross-region journey flow | §5.4, §6.2 |
| `fig11_redis_keys.png` | Redis key namespace analysis | §9 |
| `fig12_closure_cascade.png` | Road closure cascade sequence | §4.5.3, §6.4 |
| `fig13_cap_theorem.png` | CAP theorem positioning | §5.7 |
| `fig14_dependency_graph.png` | Full microservice dependency graph | §2, §4 |
| `fig15_booking_volume.png` | Booking volume by hour, 3 regions | §6 |

### Eraser Diagrams (Copy-Paste to eraser.io)

The following diagram codes are embedded inline in this document:

| Figure | Section | Diagram Type |
|--------|---------|-------------|
| Fig 2-1: 3-Region Cloud | §2 | Cloud Architecture |
| Fig 2-2: nginx routing | §3 | Sequence |
| Fig 4-1: JWT lifecycle | §4.1 | Sequence |
| Fig 6-1: Standard booking | §6.1 | Sequence |
| Fig 6-2: Cross-region booking | §6.2 | Sequence |
| Fig 6-3: Emergency booking | §6.3 | Sequence |
| Fig 6-4: Closure cascade | §6.4 | Sequence |
| Fig 7-1: Database ERD | §7 | Entity Relationship |

---

*All code analysed is from the `fix/nginx-spa-routing` branch. Generated: April 2026.*
