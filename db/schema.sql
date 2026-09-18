CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'steward'
        CHECK (role IN ('steward', 'admin')),
    cpse TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS materials (
    id BIGSERIAL PRIMARY KEY,
    cpse TEXT NOT NULL,
    sector TEXT,
    local_code TEXT NOT NULL,
    description TEXT NOT NULL,
    normalized_description TEXT NOT NULL,
    material_family TEXT,
    manufacturer TEXT,
    manufacturer_part_no TEXT,
    uom TEXT,
    uom_code TEXT,                 -- UN/CEFACT Rec 20 common code (EA, MTR, KGM ...)
    fsc TEXT,                      -- Federal Supply Classification 4-digit class
    fsc_title TEXT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cpse, local_code)
);

CREATE TABLE IF NOT EXISTS match_candidates (
    id BIGSERIAL PRIMARY KEY,
    left_material_id BIGINT NOT NULL REFERENCES materials(id),
    right_material_id BIGINT NOT NULL REFERENCES materials(id),
    score NUMERIC(6,5) NOT NULL,
    explanation JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    reviewer TEXT,
    review_note TEXT,
    reviewed_at TIMESTAMPTZ,
    UNIQUE (left_material_id, right_material_id)
);

CREATE TABLE IF NOT EXISTS national_materials (
    id BIGSERIAL PRIMARY KEY,
    nmc TEXT NOT NULL UNIQUE,
    canonical_material_id BIGINT NOT NULL REFERENCES materials(id),
    explanation TEXT,
    fsc TEXT,                      -- FSC class the National Material Code is anchored to
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nmc_crosswalk (
    national_material_id BIGINT NOT NULL REFERENCES national_materials(id),
    material_id BIGINT NOT NULL REFERENCES materials(id),
    PRIMARY KEY (national_material_id, material_id)
);

CREATE TABLE IF NOT EXISTS procurement_transactions (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    order_date DATE NOT NULL,
    quantity NUMERIC(14,3) NOT NULL,
    unit_price_inr NUMERIC(14,2) NOT NULL,
    po_number TEXT NOT NULL,
    supplier TEXT
);

CREATE INDEX IF NOT EXISTS idx_proc_tx_material
    ON procurement_transactions (material_id);

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

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
