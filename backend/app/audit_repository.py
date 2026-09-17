from typing import Any

from psycopg.types.json import Jsonb

from .database import get_connection


def _write_audit(
    cur,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
) -> None:
    """Write one audit row using an existing cursor (same transaction)."""
    cur.execute(
        """
        INSERT INTO audit_log (actor, action, entity_type, entity_id, details)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (actor, action, entity_type, str(entity_id), Jsonb(details)),
    )


def write_audit(
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write one audit row in its own transaction."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            _write_audit(cur, actor, action, entity_type, entity_id, details or {})


def list_audit(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, actor, action, entity_type, entity_id, details, created_at
                FROM audit_log
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
