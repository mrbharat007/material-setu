-- Apply to an existing database (the base schema.sql only runs on first init).
--   docker compose exec -T db psql -U material_setu -d material_setu < db/migrations/007_remove_viewer_role.sql
--
-- Drops the read-only "viewer" role: it's now steward or admin. Existing
-- viewers are promoted to steward so nobody is locked out.

UPDATE users SET role = 'steward' WHERE role = 'viewer';

ALTER TABLE users ALTER COLUMN role SET DEFAULT 'steward';
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('steward', 'admin'));
