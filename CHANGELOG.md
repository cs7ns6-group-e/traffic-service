# TrafficBook — CHANGELOG

Maintained automatically. Updated on every significant change.

---

## [2026-04-08] — fix/trafficbook-complete

### What changed
- **conflict_detection**: scope changed to per-driver — same driver cannot double-book same route+slot; other drivers unaffected
- **conflict_detection**: added GET /slots — 32 x 30-min slots (06:00–22:00) showing availability per driver
- **conflict_detection**: Redis client now uses socket_timeout=5 to prevent hangs
- **journey_booking**: route segments extracted as clean road name strings (not raw OSRM dicts)
- **journey_booking**: distance_km and duration_mins saved to DB and returned in response
- **journey_booking**: PENDING journeys auto-expire after 5 min via background thread
- **journey_booking**: driver email passed to conflict check for per-driver scoping
- **journey_booking**: full response fields (route_segments, distance_km, duration_mins, created_at)
- **traffic_authority**: force cancel checks status — blocks EMERGENCY_CONFIRMED, handles already-done
- **traffic_authority**: road closure cascade uses route_segments::text ILIKE (not origin/destination)
- **traffic_authority**: publishes journey_force_cancelled_events per affected journey
- **traffic_authority**: added GET /authority/closures endpoint
- **traffic_authority**: response fields corrected (closure_id, affected_journeys, emergency_skipped)
- **notification**: Gmail/SMTP removed entirely — Telegram only
- **notification**: added handlers for journey_cancelled and journey_force_cancelled queues
- **notification**: Telegram placeholder token → log-only mode (no crash)
- **road_routing**: added GET /search for Nominatim autocomplete with 24h Redis cache
- **road_routing**: POST /route returns distance_km, duration_mins, coordinates for Leaflet
- **road_routing**: segment extraction returns clean named strings, filtered and deduplicated
- **admin_service**: added GET /admin/latency with P50/P95 per-service metrics and SLA check
- **nginx**: added /search → road_routing proxy route

### Files modified
- conflict_detection/main.py
- journey_booking/main.py
- traffic_authority/main.py
- notification/main.py
- road_routing/main.py
- admin_service/main.py
- nginx/nginx.conf

---

## [Current] — April 7, 2026

### Infrastructure
- US VM recreated in us-central1-a (Iowa) — us-east1 exhausted
- US private IP changed: 10.0.2.11 → 10.0.4.11
- US external IP changed: 34.139.161.185 → 136.111.143.185
- US LB IP changed: 34.26.94.36 → 34.10.45.241
- New subnet: tb-subnet-us-central (10.0.4.0/24)

### Auth
- Keycloak replaced with simple JWT auth_service
- PyJWT HS256 + bcrypt password hashing
- Refresh tokens stored in PostgreSQL

### Services
- admin_service added (port 8006)
- Emergency vehicle support added
- Famous routes added (11 routes)

### Frontend
- React frontend served as static files from nginx
- All 8 pages wired to real backend APIs
- No separate frontend Docker container

### CI/CD
- deploy.yml uses git reset --hard (never git pull)
- Cloud Shell pushes branches only — never to main
- Frontend builds via node:20-alpine on each deploy

### Database
- Per-region isolated PostgreSQL (no cross-VM replication)
- Supabase removed

---

## [Previous] — April 6, 2026

### Initial deployment
- 3 GCP VMs created across EU, US, APAC
- 8 microservices deployed
- RabbitMQ federation configured
- GitHub Actions CI/CD set up
