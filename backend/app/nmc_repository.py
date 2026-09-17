from .database import get_connection
from .services.classifier import fsc_meta


def list_nmc() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    nm.nmc,
                    nm.canonical_material_id,
                    nm.explanation,
                    nm.fsc,
                    coalesce(
                        array_agg(x.material_id ORDER BY x.material_id)
                        FILTER (WHERE x.material_id IS NOT NULL),
                        '{}'
                    ) AS local_material_ids
                FROM national_materials nm
                LEFT JOIN nmc_crosswalk x ON x.national_material_id = nm.id
                GROUP BY nm.id
                ORDER BY nm.nmc
                """
            )
            records = []
            for row in cur.fetchall():
                record = dict(row)
                record["explanation"] = record["explanation"] or ""
                record.update(fsc_meta(record.get("fsc")))
                records.append(record)
            return records
