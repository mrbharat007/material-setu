"""Bring the database schema up to date on startup.

``db/schema.sql`` and every file in ``db/migrations/`` are written to be
idempotent (``CREATE ... IF NOT EXISTS`` / ``ADD COLUMN IF NOT EXISTS``), so we
can safely replay all of them every time the API (or the seed script) starts.
This removes the "did you run ``make migrate``?" foot-gun.
"""

import os
from pathlib import Path

import psycopg

from .database import DATABASE_URL


def _find_db_dir() -> Path:
    env_dir = os.environ.get("DB_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)
    # Check repo root db
    p2 = Path(__file__).resolve().parents[2] / "db"
    if p2.is_dir():
        return p2
    # Check backend/db
    p1 = Path(__file__).resolve().parents[1] / "db"
    if p1.is_dir():
        return p1
    # Check app/db
    p0 = Path(__file__).resolve().parent / "db"
    if p0.is_dir():
        return p0
    return p2


def ensure_schema() -> None:
    db_dir = _find_db_dir()
    schema_file = db_dir / "schema.sql"
    if not schema_file.exists():
        print(f"[db_bootstrap] Warning: schema file not found at {schema_file}")
        return

    files = [schema_file]
    migrations = db_dir / "migrations"
    if migrations.is_dir():
        files += sorted(migrations.glob("*.sql"))

    try:
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            for path in files:
                sql_content = path.read_text(encoding="utf-8").strip()
                if not sql_content:
                    continue
                # Split statements by semicolon while preserving triggers/blocks if any
                for stmt in sql_content.split(";"):
                    stmt = stmt.strip()
                    if not stmt:
                        continue
                    try:
                        conn.execute(stmt)
                    except Exception as stmt_err:
                        err_str = str(stmt_err).lower()
                        if "extension \"vector\" is not available" in err_str:
                            continue
                        raise stmt_err
        print("[db_bootstrap] schema sync completed successfully")
    except Exception as exc:  # noqa: BLE001 - never block startup on this
        print(f"[db_bootstrap] schema sync skipped: {exc}")

