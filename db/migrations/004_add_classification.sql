-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/004_add_classification.sql

-- UN/CEFACT Rec 20 unit code + Federal Supply Classification on every material.
ALTER TABLE materials
    ADD COLUMN IF NOT EXISTS uom_code TEXT,
    ADD COLUMN IF NOT EXISTS fsc TEXT,
    ADD COLUMN IF NOT EXISTS fsc_title TEXT;

-- The FSC class a published National Material Code is anchored to.
ALTER TABLE national_materials
    ADD COLUMN IF NOT EXISTS fsc TEXT;
