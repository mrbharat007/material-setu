-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/006_add_material_attachments.sql

-- Datasheets, drawings and photos attached to a local material record —
-- images, PDF and PPTX, stored inline (bytea) since there's no object store.
CREATE TABLE IF NOT EXISTS material_attachments (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    data BYTEA NOT NULL,
    uploaded_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_material_attachments_material_id
    ON material_attachments (material_id);
