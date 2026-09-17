from .database import get_connection

_META_COLUMNS = """
    id, material_id, filename, content_type, size_bytes, uploaded_by, created_at
"""


def insert_attachment(
    material_id: int,
    filename: str,
    content_type: str,
    data: bytes,
    uploaded_by: str | None,
) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO material_attachments (
                    material_id, filename, content_type, size_bytes, data, uploaded_by
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING {_META_COLUMNS}
                """,
                (material_id, filename, content_type, len(data), data, uploaded_by),
            )
            return dict(cur.fetchone())


def list_for_material(material_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_META_COLUMNS}
                FROM material_attachments
                WHERE material_id = %s
                ORDER BY id
                """,
                (material_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_attachment(attachment_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, material_id, filename, content_type, size_bytes,
                       data, uploaded_by, created_at
                FROM material_attachments
                WHERE id = %s
                """,
                (attachment_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def delete_attachment(attachment_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM material_attachments WHERE id = %s",
                (attachment_id,),
            )
            return cur.rowcount > 0
