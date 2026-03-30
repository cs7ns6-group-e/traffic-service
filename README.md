# TrafficBook – Traffic Service

A microservices-based backend for managing journey bookings, conflict detection, notifications, road routing, and traffic authority operations.

## Architecture

The project is a monorepo composed of a shared library package and five independent FastAPI services:

| Service | Port | Responsibility |
|---|---|---|
| `journey_booking` | 8001 | Create and manage journey bookings |
| `conflict_detection` | 8002 | Detect scheduling and routing conflicts |
| `notification` | 8003 | Send and manage user notifications |
| `road_routing` | 8004 | Calculate optimal road routes |
| `traffic_authority` | 8005 | Interface with traffic authority systems |

A `shared/` package contains common models, utilities, and configuration used across all services.

## Project Structure

```
traffic-service/
├── shared/               # Shared library (models, utils, config)
├── journey_booking/      # Service: journey booking (port 8001)
│   └── app/
│       ├── routes/
│       ├── services/
│       ├── repositories/
│       └── tests/
├── conflict_detection/   # Service: conflict detection (port 8002)
├── notification/         # Service: notification (port 8003)
├── road_routing/         # Service: road routing (port 8004)
└── traffic_authority/    # Service: traffic authority (port 8005)
```

Each service follows the same internal layout:
- `app/routes/` – API route definitions
- `app/services/` – Business logic
- `app/repositories/` – Data access layer
- `app/tests/` – Pytest test suite

## Getting Started

### Prerequisites

- Python 3.10+
- [Docker](https://www.docker.com/) (optional, for containerised runs)

### Install dependencies

Each service manages its own dependencies. For example, to set up `journey_booking`:

```bash
cd journey_booking
pip install -r requirements.txt
```

Repeat for each service you need to run.

### Run a service

```bash
cd journey_booking
uvicorn app.main:app --reload --port 8001
```

### Run tests

Each service uses [pytest](https://pytest.org/) with `asyncio_mode=auto`:

```bash
cd journey_booking
pytest
```

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes and ensure all tests pass.
3. Open a pull request with a clear description of your changes.
