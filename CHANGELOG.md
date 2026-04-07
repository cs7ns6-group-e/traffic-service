# TrafficBook — CHANGELOG

Maintained automatically. Updated on every significant change.

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
