-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/005_add_procurement.sql

-- Historical procurement transactions per local material — powers the
-- collaborative-procurement (price spread / tender aggregation) view.
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
