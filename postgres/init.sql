CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email        TEXT UNIQUE NOT NULL,
  name         TEXT NOT NULL,
  password     TEXT NOT NULL,
  role         TEXT DEFAULT 'driver',
  vehicle_type TEXT DEFAULT 'STANDARD',
  region       TEXT NOT NULL,
  created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  token      TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS journeys (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  driver_id       TEXT NOT NULL,
  origin          TEXT NOT NULL,
  destination     TEXT NOT NULL,
  start_time      TIMESTAMP NOT NULL,
  status          TEXT DEFAULT 'PENDING',
  region          TEXT NOT NULL,
  dest_region     TEXT,
  is_cross_region BOOLEAN DEFAULT FALSE,
  vehicle_type    TEXT DEFAULT 'STANDARD',
  route_segments  JSONB DEFAULT '[]',
  route_id        TEXT,
  created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cross_region_events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  journey_id  UUID REFERENCES journeys(id),
  from_region TEXT NOT NULL,
  to_region   TEXT NOT NULL,
  event_type  TEXT NOT NULL,
  delivered   BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS road_closures (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  road_name  TEXT NOT NULL,
  region     TEXT NOT NULL,
  reason     TEXT,
  active     BOOLEAN DEFAULT TRUE,
  created_by TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journeys_region       ON journeys(region);
CREATE INDEX IF NOT EXISTS idx_journeys_status       ON journeys(status);
CREATE INDEX IF NOT EXISTS idx_journeys_driver       ON journeys(driver_id);
CREATE INDEX IF NOT EXISTS idx_journeys_vehicle_type ON journeys(vehicle_type);
CREATE INDEX IF NOT EXISTS idx_journeys_time         ON journeys(start_time);
