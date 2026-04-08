# TrafficBook

> A geo-distributed traffic management platform spanning three GCP regions, built as a practical study of distributed systems concepts — eventual consistency, cross-region conflict detection, RabbitMQ federation, and multi-region API routing.

**Course**: CS7NS6 Distributed Systems — Trinity College Dublin

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Live Regions](#live-regions)
3. [Microservices](#microservices)
4. [Data Flow](#data-flow)
5. [Key Distributed Systems Concepts](#key-distributed-systems-concepts)
6. [Frontend](#frontend)
7. [API Reference](#api-reference)
8. [Database Schema](#database-schema)
9. [Running Locally](#running-locally)
10. [Deployment](#deployment)
11. [Load Testing](#load-testing)
12. [End-to-End Tests](#end-to-end-tests)
13. [Environment Variables](#environment-variables)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                               │
│                   React 18 + Vite + Tailwind                        │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     NGINX (port 80)                                 │
│  Rate limiting · SPA fallback · Upstream routing per path prefix    │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬────────────────────────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
 :8000  :8001  :8002  :8003  :8004  :8005  :8006
  Auth Journey Conflict Notif  Route  Auth  Admin
              Detect          Routing ority
   │      │      │      │      │      │      │
   └──────┴──────┴──────┴──────┴──────┴──────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
          PostgreSQL   Redis    RabbitMQ
          (per-region) (cache)  (federation)
```

Three identical stacks deployed independently across GCP regions. RabbitMQ federation federates queues between VMs so events published in EU flow to US and APAC consumers without shared infrastructure.

```
  EU VM (europe-west1)          US VM (us-central1)         APAC VM (asia-southeast1)
  35.240.110.205                34.26.94.36                 34.126.131.195
  ┌─────────────────┐           ┌─────────────────┐         ┌─────────────────┐
  │  All 7 services │ ◄──────►  │  All 7 services │ ◄────►  │  All 7 services │
  │  PostgreSQL     │  RabbitMQ │  PostgreSQL     │         │  PostgreSQL     │
  │  Redis          │ federation│  Redis          │         │  Redis          │
  └─────────────────┘           └─────────────────┘         └─────────────────┘
```

---

## Live Regions

| Region | Load Balancer | Location |
|--------|--------------|----------|
| EU | `http://35.240.110.205` | europe-west1 (Belgium) |
| US | `http://34.26.94.36` | us-central1 (Iowa) |
| APAC | `http://34.126.131.195` | asia-southeast1 (Singapore) |

The frontend auto-detects your region from the journey origin/destination text — Dublin routes EU, New York routes US, Singapore routes APAC.

---

## Microservices

### `auth_service` — port 8000

Handles registration, login, and JWT lifecycle.

- HS256 JWTs, 30-minute access token + long-lived refresh token
- Passwords hashed with bcrypt
- Refresh tokens persisted in PostgreSQL with expiry
- Roles: `driver`, `authority`, `admin`

### `journey_booking` — port 8001

The core booking engine.

- Detects destination region from location keywords (EU / US / APAC)
- Calls `conflict_detection` to check for slot conflicts before saving
- Checks active road closures — returns `409 route_blocked` if the route crosses a closed segment
- Publishes `journey_events` to RabbitMQ on every state change
- Publishes `journey_replication_events` so other regions receive a copy
- Cross-region journeys are forwarded to the remote region via internal HTTP
- PENDING journeys auto-expire after 5 minutes via a background thread
- Emergency vehicles (`EMERGENCY` type) bypass conflict checks and close instantly as `EMERGENCY_CONFIRMED`

### `conflict_detection` — port 8002

Prevents double-booking using Redis.

- 32 half-hour time slots (06:00–22:00), scoped **per driver** (not system-wide)
- Ghost reservation: `POST /conflicts/reserve-slot` holds a slot optimistically while the user fills the form; released on deselect or navigation away
- Redis keys expire automatically — no manual cleanup needed
- `GET /conflicts/slots` returns the full slot grid with per-driver availability

### `notification` — port 8003

Telegram notifications via RabbitMQ consumers.

- Consumes: `journey_events`, `journey_cancelled`, `journey_force_cancelled`, `road_closure_events`, `journey_replication_events`
- Sends rich Telegram messages with driver name, route, distance, road segments, and journey ID
- Falls back to log-only mode if `TELEGRAM_BOT_TOKEN` is not configured
- Also writes incoming `journey_replication_events` from other regions into the local `replicated_journeys` table (eventual consistency demonstration)

### `road_routing` — port 8004

Route calculation and place search.

- Integrates with OSRM for turn-by-turn routing
- Returns `distance_km`, `duration_mins`, coordinates for the Leaflet map, and named road segments
- `GET /routes/famous` returns 11 pre-defined routes across all 3 regions
- `GET /search` — Nominatim autocomplete with 24-hour Redis cache
- Named segments are deduplicated and filtered (unnamed roads excluded) so traffic authority road closures match real street names

### `traffic_authority` — port 8005

Road closure management and journey oversight.

- `GET /authority/segments` — returns the exact OSRM segment names appearing in **active future journeys**, so authorities pick names that will actually match
- `GET /authority/closure-preview` — dry-run: shows exactly which journeys would be cancelled before committing
- `POST /authority/closure` — creates a closure and cascades cancellations; publishes one `road_closure_events` message per affected journey
- `POST /authority/cancel/{id}` — force-cancel a single journey with a reason
- Emergency-confirmed journeys are immune to authority cancellation
- `GET /authority/stats` — total journeys, active closures, pending count

### `admin_service` — port 8006

System-wide observability.

- `GET /admin/health` — per-service status + replica count
- `GET /admin/all-regions` — journey counts aggregated per region (fan-out to all 3 VMs)
- `GET /admin/latency` — P50 / P95 response times per service with SLA pass/fail
- `GET /admin/queue` — RabbitMQ queue depth
- `GET /admin/cache` — Redis hit rate
- `GET /admin/replicated` — cross-region replication status: count of replicated records per origin region + lag estimate
- `POST /admin/replicated` — triggers a test replication cycle

---

## Data Flow

### Standard journey booking

```
Browser → nginx → journey_booking
  │
  ├─► conflict_detection  (check slot — Redis)
  │     └─► reserve_slot  (ghost reservation)
  │
  ├─► road_routing         (OSRM route + segments)
  │
  ├─► closure check        (local DB: active road_closures)
  │     └─► 409 if blocked
  │
  ├─► INSERT journeys (PostgreSQL)
  │
  ├─► RabbitMQ: journey_events         → notification (Telegram)
  └─► RabbitMQ: journey_replication_events → other regions' notification consumers
                                              → replicated_journeys table
```

### Cross-region journey

```
Browser (origin: Dublin, destination: New York)
  → journey_booking EU
    → detect_region("New York") = "US"
    → conflict_detection EU  (check EU slot)
    → INSERT journey EU (region=EU, dest_region=US, is_cross_region=true)
    → HTTP POST → journey_booking US  (forward booking)
      → INSERT journey US (is_cross_region=true)
    → RabbitMQ federation propagates events to US + APAC
```

### Road closure cascade

```
Authority UI → POST /authority/closure
  → closure-preview shown first (dry-run)
  → INSERT road_closures
  → SELECT journeys WHERE route_segments::text ILIKE '%{road_name}%'
      AND status IN ('CONFIRMED','PENDING')
      AND vehicle_type != 'EMERGENCY'
  → UPDATE journeys SET status = 'AUTHORITY_CANCELLED'
  → FOR EACH cancelled journey:
      → RabbitMQ: road_closure_events (with driver email, start_time)
        → notification → Telegram message to driver
```

---

## Key Distributed Systems Concepts

### Eventual Consistency

Each region has its own isolated PostgreSQL instance — there is no shared database or synchronous replication. Cross-region data arrives **asynchronously** via RabbitMQ federation:

1. A booking on EU publishes to `journey_replication_events`
2. RabbitMQ federation forwards the message to US and APAC
3. The notification consumer on each remote VM writes to `replicated_journeys`
4. `GET /admin/replicated` shows how many records each region has received from other regions

This is a textbook demonstration of BASE (Basically Available, Soft state, Eventually consistent) vs ACID.

### Ghost Reservations (Optimistic Locking)

The slot grid uses a two-phase reservation pattern to prevent lost updates:

```
User hovers/clicks slot
  → POST /conflicts/reserve-slot  (soft lock in Redis, TTL 5 min)
  → Slot shown as "held" to this user only

User submits booking form
  → conflict_detection validates the reservation is still held
  → Reservation converted to confirmed booking

User navigates away / deselects
  → POST /conflicts/release-slot  (lock released immediately)
```

This prevents the situation where two users see the same slot as available and race to book it.

### Per-Driver Conflict Scoping

Slot conflicts are scoped to the **individual driver**, not the system. Two different drivers can book the same route at the same time — only the same driver cannot double-book the same slot. This is enforced via Redis key namespacing:

```
conflict:{driver_id}:{date}:{slot_index}
```

### RabbitMQ Federation

RabbitMQ federation is configured between all three VMs so queues are shared without clustering:

```
rabbitmq.conf:
  federation-upstream = eu_upstream  → amqp://10.0.1.11:5672
  federation-upstream = us_upstream  → amqp://10.0.4.11:5672
  federation-upstream = apac_upstream → amqp://10.0.3.11:5672
```

Events published on any VM propagate to the other two. This allows the notification service to receive and log all cross-region bookings without any synchronous inter-service coupling.

---

## Frontend

React 18 + TypeScript + Vite 6 + Tailwind CSS 4 + shadcn/ui

Served as static files from nginx — no separate frontend container.

### Pages

| Page | Route | Role |
|------|-------|------|
| Login / Register | `/login` | All |
| Driver Dashboard | `/dashboard` | Driver |
| Book Journey | `/book` | Driver |
| Journey Detail | `/journeys/:id` | Driver |
| Notifications | `/notifications` | Driver |
| Traffic Authority | `/authority` | Authority |
| Admin Dashboard | `/admin` | Admin |
| Settings | `/settings` | All |

### Book Journey — notable features

- **Place search**: Nominatim autocomplete with debounce (cached in Redis on backend)
- **Interactive map**: Leaflet renders the full OSRM route with start/end markers
- **Slot grid**: 32 half-hour slots, real-time availability, ghost reservation on click
- **Famous routes**: 11 pre-configured routes across EU/US/APAC for quick demo booking
- **Route blocked modal**: 409 responses from a closed road show the road name and reason before the user tries again

### Traffic Authority Dashboard — notable features

- Journey list sorted by emergency status (EMERGENCY_CONFIRMED always first)
- Road closure form with real segment dropdown (only segments from live journeys)
- Preview step before confirming — shows exact journeys that will be cancelled
- Active closures list with affected journey count

### Admin Dashboard — notable features

- Service health with live P95 latency vs SLA badge
- Replica scaling (+/−) that persists across the 30-second auto-refresh
- Per-region journey stats (unavailable regions shown as compact rows, not broken cards)
- RabbitMQ queue depth + Redis hit rate
- Data replication table: per-region record counts, lag indicator (Low / Medium / High), last sync time
- Trigger test replication button with before/after delta

---

## API Reference

### Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | `{email, password, name, region, vehicle_type}` | Create account |
| POST | `/auth/login` | `{email, password}` | Returns `access_token` + `refresh_token` |
| POST | `/auth/refresh` | `{refresh_token}` | Rotate tokens |
| GET | `/auth/me` | — | Current user profile |

### Journeys

| Method | Path | Description |
|--------|------|-------------|
| POST | `/journeys` | Book a journey |
| GET | `/journeys` | List your journeys |
| GET | `/journeys/{id}` | Journey detail |
| DELETE | `/journeys/{id}` | Cancel a journey |

**POST /journeys** request body:
```json
{
  "origin": "Dublin, Ireland",
  "destination": "Cork, Ireland",
  "start_time": "2026-05-01T09:00:00",
  "vehicle_type": "STANDARD",
  "slot_index": 6
}
```

### Conflict Detection

| Method | Path | Description |
|--------|------|-------------|
| GET | `/conflicts/slots` | 32-slot grid for a route+date |
| POST | `/conflicts/reserve-slot` | Ghost reservation |
| POST | `/conflicts/release-slot` | Release ghost reservation |

### Road Routing

| Method | Path | Description |
|--------|------|-------------|
| POST | `/route` | OSRM route (coords + segments + distance) |
| GET | `/routes/famous` | 11 pre-defined routes |
| GET | `/search?q=Dublin` | Nominatim place autocomplete |

### Traffic Authority *(requires `authority` role)*

| Method | Path | Description |
|--------|------|-------------|
| GET | `/authority/journeys` | All journeys in region |
| POST | `/authority/cancel/{id}` | Force-cancel a journey |
| GET | `/authority/segments` | Segment names from live journeys |
| GET | `/authority/closure-preview?road_name=...` | Dry-run closure |
| POST | `/authority/closure` | Create closure + cascade cancel |
| GET | `/authority/closures` | Active closures |
| GET | `/authority/stats` | Aggregate stats |

### Admin *(requires `admin` role)*

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/health` | Per-service health + replicas |
| GET | `/admin/all-regions` | Journey counts fan-out |
| GET | `/admin/latency` | P50/P95 per service |
| GET | `/admin/queue` | RabbitMQ depth |
| GET | `/admin/cache` | Redis hit rate |
| GET | `/admin/replicated` | Cross-region replication status |
| POST | `/admin/replicated` | Trigger test replication |

---

## Database Schema

```sql
-- Users and auth
users            (id, email, name, password, role, vehicle_type, region, created_at)
refresh_tokens   (id, user_id, token, expires_at, created_at)

-- Core booking
journeys         (id, driver_id, origin, destination, start_time, status,
                  region, dest_region, is_cross_region, vehicle_type,
                  route_segments JSONB, route_id, cancelled_reason,
                  driver_email, created_at)

-- Distributed systems tracking
cross_region_events  (id, journey_id, from_region, to_region, event_type,
                      delivered, created_at)
replicated_journeys  (id, origin_region, driver_id, driver_email, origin,
                      destination, start_time, status, vehicle_type,
                      route_segments JSONB, distance_km, duration_mins)

-- Authority
road_closures    (id, road_name, region, reason, active, is_active,
                  created_by, created_at)
```

Journey statuses: `PENDING` → `CONFIRMED` | `CANCELLED` | `AUTHORITY_CANCELLED` | `EMERGENCY_CONFIRMED`

---

## Running Locally

**Prerequisites**: Docker, Docker Compose, Node 20+

```bash
# 1. Clone and install frontend deps
git clone <repo>
cd traffic-service
npm install

# 2. Create .env (see Environment Variables section)
cp .env.example .env

# 3. Start all backend services
docker compose up --build

# 4. Dev frontend (proxies /auth, /journeys, etc. to localhost backend)
npm run dev
# → http://localhost:5173

# 5. Production build
npm run build
# Static files → dist/  (served by nginx in production)
```

**Default test accounts** (seeded by init.sql or register manually):

| Email | Password | Role |
|-------|----------|------|
| `driver@trafficbook.com` | `Driver123!` | driver |
| `authority@trafficbook.com` | `Auth123!` | authority |
| `admin@trafficbook.com` | `Admin123!` | admin |

---

## Deployment

Each region runs an identical Docker Compose stack on a GCP e2-medium VM.

```bash
# On each VM — deploy latest from a branch
git fetch origin
git reset --hard origin/fix/nginx-spa-routing

# Rebuild and restart
docker compose up --build -d

# Check all containers healthy
docker compose ps

# Tail service logs
docker compose logs -f journey_booking
```

GitHub Actions (`deploy.yml`) automates this on push to the deploy branch. The workflow SSHs into each VM, pulls the branch, builds, and restarts. It uses `git reset --hard` (never `git pull`) to guarantee a clean state.

**nginx serves the React SPA from the same VM** — the built `dist/` directory is copied into the nginx container image at build time. No separate CDN or frontend host.

---

## Load Testing

Uses [k6](https://k6.io). Tests ramp from 10 to 100 virtual users.

**Thresholds**: P95 response time < 500ms, error rate < 5%

```bash
# Install k6
brew install k6  # macOS
# or: https://k6.io/docs/getting-started/installation/

# Booking load test (hits all 3 regions randomly)
k6 run loadtest/booking_test.js \
  -e EU_LB=http://35.240.110.205 \
  -e US_LB=http://34.26.94.36 \
  -e APAC_LB=http://34.126.131.195

# Health endpoint test
k6 run loadtest/health_test.js
```

---

## End-to-End Tests

Python test suite covering the full booking lifecycle across all 3 regions.

```bash
pip install requests
python3 test/test_e2e.py
```

Covers:
- Auth: register, login, refresh
- Journey: book, list, cancel, cross-region
- Conflict detection: slot availability, double-booking rejection
- Road routing: route calculation, famous routes, place search
- Authority: closure preview, create closure, cascade cancellation
- Admin: health, stats, replication
- Emergency vehicle bypass

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/trafficbook
POSTGRES_USER=trafficbook
POSTGRES_PASSWORD=...
POSTGRES_DB=trafficbook

# Auth
JWT_SECRET=...

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
RABBITMQ_ERLANG_COOKIE=...

# Redis
REDIS_URL=redis://redis:6379

# Region identity (EU | US | APAC)
REGION=EU

# Cross-region internal URLs
REGION_EU_URL=http://10.0.1.11
REGION_US_URL=http://10.0.4.11
REGION_APAC_URL=http://10.0.3.11

# Notifications
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Observability
GRAFANA_ADMIN_PASSWORD=...
```

---

## Observability

| Tool | URL | What it shows |
|------|-----|--------------|
| Prometheus | `:9090` | Metrics scrape targets |
| Grafana | `:3000` | Service dashboards (login: admin / `$GRAFANA_ADMIN_PASSWORD`) |
| RabbitMQ Management | `:15672` | Queue depths, federation links, message rates |
| Admin Dashboard | `/admin` (in-app) | Health, latency, replication, cache, queue |

---

## Project Structure

```
traffic-service/
├── auth_service/          FastAPI — JWT auth
├── journey_booking/       FastAPI — core booking engine
├── conflict_detection/    FastAPI — Redis slot locking
├── notification/          FastAPI — RabbitMQ consumer + Telegram
├── road_routing/          FastAPI — OSRM + Nominatim
├── traffic_authority/     FastAPI — closures + authority actions
├── admin_service/         FastAPI — observability aggregator
├── nginx/                 nginx.conf — reverse proxy + SPA
├── postgres/              init.sql — schema + indexes
├── rabbitmq/              rabbitmq.conf + enabled_plugins
├── prometheus/            prometheus.yml
├── loadtest/              k6 scripts
├── test/                  Python e2e suite
├── src/
│   └── app/
│       ├── api/           client.ts (fetch wrapper + token refresh)
│       │                  config.ts (endpoint constants + region IPs)
│       ├── components/    Shared UI (RouteMap, SlotGrid, StatusBadge…)
│       └── pages/         8 page components
├── docker-compose.yml
├── vite.config.ts
└── package.json
```

---

*Built for CS7NS6 Distributed Systems, Trinity College Dublin, 2026.*
