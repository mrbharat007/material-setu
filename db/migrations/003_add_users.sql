-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/003_add_users.sql

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'steward', 'admin')),
    cpse TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
