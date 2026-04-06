-- TrafficBook PostgreSQL Initialization Script
-- Creates all tables, enums, and indexes

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('driver', 'traffic_authority', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE vehicle_type_enum AS ENUM ('STANDARD', 'EMERGENCY', 'AUTHORITY');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE journey_status AS ENUM ('PENDING', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- Users table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email           VARCHAR(255) UNIQUE NOT NULL,
    name            VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'driver',
    vehicle_type    vehicle_type_enum NOT NULL DEFAULT 'STANDARD',
    region          VARCHAR(10) NOT NULL DEFAULT 'EU',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Refresh tokens table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id     VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(255) UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Journeys table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journeys (
    id              VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    driver_id       VARCHAR(36) NOT NULL,
    origin          VARCHAR(255) NOT NULL,
    destination     VARCHAR(255) NOT NULL,
    start_time      TIMESTAMPTZ NOT NULL,
    status          journey_status NOT NULL DEFAULT 'PENDING',
    region          VARCHAR(10) NOT NULL DEFAULT 'EU',
    vehicle_type    vehicle_type_enum NOT NULL DEFAULT 'STANDARD',
    route_segments  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Cross-region events table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cross_region_events (
    id              VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    source_region   VARCHAR(10) NOT NULL,
    target_region   VARCHAR(10) NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    payload         JSONB NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Road closures table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS road_closures (
    id              VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    region          VARCHAR(10) NOT NULL DEFAULT 'EU',
    road_name       VARCHAR(255) NOT NULL,
    reason          TEXT,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,
    created_by      VARCHAR(36),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_region ON users(region);
CREATE INDEX IF NOT EXISTS idx_users_vehicle_type ON users(vehicle_type);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token);

CREATE INDEX IF NOT EXISTS idx_journeys_region ON journeys(region);
CREATE INDEX IF NOT EXISTS idx_journeys_status ON journeys(status);
CREATE INDEX IF NOT EXISTS idx_journeys_driver_id ON journeys(driver_id);
CREATE INDEX IF NOT EXISTS idx_journeys_vehicle_type ON journeys(vehicle_type);
CREATE INDEX IF NOT EXISTS idx_journeys_start_time ON journeys(start_time);

CREATE INDEX IF NOT EXISTS idx_cross_region_events_source ON cross_region_events(source_region);
CREATE INDEX IF NOT EXISTS idx_cross_region_events_target ON cross_region_events(target_region);
CREATE INDEX IF NOT EXISTS idx_cross_region_events_status ON cross_region_events(status);

CREATE INDEX IF NOT EXISTS idx_road_closures_region ON road_closures(region);
CREATE INDEX IF NOT EXISTS idx_road_closures_start_time ON road_closures(start_time);
