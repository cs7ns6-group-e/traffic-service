# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `traffic-service/`:

```bash
# Install dependencies for all services
make install

# Run all tests (requires 70% coverage)
make test

# Run tests for a single service
cd journey_booking && pytest app/tests/ -v
cd conflict_detection && pytest app/tests/ -v

# Run a single test file
cd journey_booking && pytest app/tests/test_routes.py -v

# Lint (ruff) + type check (mypy)
make lint

# Start all services (Docker)
make up

# Stop all services
make down

# View logs
make logs

# Run database migrations
make migrate
```

Each service runs independently with uvicorn:
```bash
cd journey_booking && uvicorn app.main:app --reload --port 8001
```

## Architecture

This is a Python/FastAPI microservices monorepo. The `shared/` package is imported by all five services and contains the ORM models, Pydantic schemas, database setup, messaging, caching, and auth utilities.

### Services

| Service | Port | Role |
|---|---|---|
| `journey_booking` | 8001 | User-facing booking API; orchestrates other services |
| `conflict_detection` | 8002 | Detects scheduling/routing conflicts; Redis-cached |
| `notification` | 8003 | Event-driven only — no HTTP routes, consumes RabbitMQ |
| `road_routing` | 8004 | Route calculation and optimization; Redis-cached |
| `traffic_authority` | 8005 | Road closures and authority-directed journey cancellation |

### Data Flow

```
User → journey_booking (8001)
          ├── HTTP → conflict_detection (8002)
          ├── HTTP → road_routing (8004)
          └── RabbitMQ publish → notification (8003) → email/Telegram
```

All user requests enter through `journey_booking`. It makes synchronous HTTP calls to `conflict_detection` and `road_routing`, then publishes `BookingEvent` messages to RabbitMQ. The `notification` service runs a background consumer thread and never exposes HTTP endpoints.

### Internal Structure (all services follow this pattern)

```
app/
  main.py          # FastAPI app, lifespan (DB init, consumer start)
  config.py        # Service-specific settings (extends shared/config.py)
  routes/          # HTTP endpoint handlers
  services/        # Business logic
  repositories/    # Database queries (SQLAlchemy async)
  tests/
```

### Shared Package Key Files

- `shared/models.py` — SQLAlchemy ORM: `Journey` (driver_id, origin, destination, start_time, status, region, route_segments) and `RoadClosure`
- `shared/schemas.py` — Pydantic v2 request/response models
- `shared/messaging.py` — `EventPublisher` and `EventConsumer` for RabbitMQ (pika)
- `shared/database.py` — Async SQLAlchemy engine + session factory
- `shared/auth.py` — Keycloak JWT token verification

### Infrastructure

- **Database**: PostgreSQL (Supabase) via async SQLAlchemy + asyncpg
- **Cache**: Redis (conflict detection, routing results)
- **Message queue**: RabbitMQ (`booking_events` queue)
- **Auth**: Keycloak (JWT)
- **API gateway**: Nginx on port 80 — rate-limited at 30 req/min/IP, routes to all services

### Cross-Region Support

Region is derived from origin/destination city names (EU, US, APAC). Cross-region journeys require HTTP coordination with remote regional service instances. The `conflict_detection` service has a `/cross-region` endpoint for this.

### Tests

Tests use `pytest-asyncio` with `asyncio_mode = auto` (set in each service's `pytest.ini`). Fixtures are in `tests/conftest.py` per service. CI enforces 70% coverage minimum.

### CI/CD

GitHub Actions (`.github/workflows/ci.yml`): lint → test → build Docker images → deploy to Azure VM (EU region). Deployment results are sent to Telegram.
