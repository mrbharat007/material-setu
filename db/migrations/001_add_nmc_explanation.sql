-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/001_add_nmc_explanation.sql

ALTER TABLE national_materials
    ADD COLUMN IF NOT EXISTS explanation TEXT;
