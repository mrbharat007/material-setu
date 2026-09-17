-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/002_add_material_sector.sql

ALTER TABLE materials
    ADD COLUMN IF NOT EXISTS sector TEXT;
