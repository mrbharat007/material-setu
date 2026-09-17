from psycopg.types.json import Jsonb

from .database import get_connection
from .services.classifier import fsc_meta


def _enrich(row: dict) -> dict:
    """Add derived supply-group fields (fsg, fsg_title) from the stored fsc."""
    meta = fsc_meta(row.get("fsc"))
    row["fsg"] = meta["fsg"]
    row["fsg_title"] = meta["fsg_title"]
    if not row.get("fsc_title"):
        row["fsc_title"] = meta["fsc_title"]
    return row

_COLUMNS = """
    id,
    cpse,
    sector,
    local_code,
    description,
    normalized_description,
    material_family,
    manufacturer,
    manufacturer_part_no,
    uom,
    uom_code,
    fsc,
    fsc_title,
    attributes,
    extracted_attributes
"""


def insert_material(record: dict) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO materials (
                    cpse,
                    sector,
                    local_code,
                    description,
                    normalized_description,
                    material_family,
                    manufacturer,
                    manufacturer_part_no,
                    uom,
                    uom_code,
                    fsc,
                    fsc_title,
                    attributes,
                    extracted_attributes
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING {_COLUMNS}
                """,
                (
                    record["cpse"],
                    record.get("sector"),
                    record["local_code"],
                    record["description"],
                    record["normalized_description"],
                    record.get("material_family"),
                    record.get("manufacturer"),
                    record.get("manufacturer_part_no"),
                    record.get("uom"),
                    record.get("uom_code"),
                    record.get("fsc"),
                    record.get("fsc_title"),
                    Jsonb(record.get("attributes", {})),
                    Jsonb(record.get("extracted_attributes", {})),
                ),
            )

            return _enrich(dict(cur.fetchone()))


def get_material(material_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM materials WHERE id = %s",
                (material_id,),
            )
            row = cur.fetchone()
            return _enrich(dict(row)) if row else None


def get_material_by_cpse_code(cpse: str, local_code: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} FROM materials
                WHERE lower(cpse) = lower(%s) AND lower(local_code) = lower(%s)
                """,
                (cpse, local_code),
            )
            row = cur.fetchone()
            return _enrich(dict(row)) if row else None


def get_all_materials() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS}
                FROM materials
                ORDER BY id
                """
            )

            return [_enrich(dict(row)) for row in cur.fetchall()]
