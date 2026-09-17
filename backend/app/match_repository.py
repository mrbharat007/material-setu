from psycopg.types.json import Jsonb

from .audit_repository import _write_audit
from .database import get_connection
from .services.classifier import fsc_meta

_MATCH_COLUMNS = """
    id,
    left_material_id,
    right_material_id,
    score::float8 AS score,
    explanation,
    status,
    reviewer,
    review_note,
    reviewed_at
"""


def replace_pending_matches(candidates: list[dict]) -> None:
    """Refresh the pending match queue.

    Rows that were already decided (approved/rejected) are preserved; all
    pending rows are dropped and re-created from the freshly computed
    ``candidates``. Each candidate must use a stable orientation
    (``left_material_id`` < ``right_material_id``).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM match_candidates WHERE status = 'pending'")
            for candidate in candidates:
                cur.execute(
                    """
                    INSERT INTO match_candidates (
                        left_material_id,
                        right_material_id,
                        score,
                        explanation
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (left_material_id, right_material_id)
                    DO NOTHING
                    """,
                    (
                        candidate["left_material_id"],
                        candidate["right_material_id"],
                        candidate["score"],
                        Jsonb(candidate["explanation"]),
                    ),
                )


def list_matches() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_MATCH_COLUMNS}
                FROM match_candidates
                ORDER BY score DESC, id
                """
            )
            return [dict(row) for row in cur.fetchall()]


def apply_decision(
    match_id: int,
    decision: str,
    reviewer: str,
    note: str | None,
) -> dict | None:
    """Record a steward decision and, on approval, link/create the NMC.

    Returns ``{"match": ..., "nmc": ... | None}`` or ``None`` if not found.
    Everything happens in a single transaction.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE match_candidates
                SET status = %s,
                    reviewer = %s,
                    review_note = %s,
                    reviewed_at = now()
                WHERE id = %s
                RETURNING {_MATCH_COLUMNS}
                """,
                (decision, reviewer, note, match_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            match = dict(row)

            nmc_record = None
            if decision == "approved":
                nmc_record = _link_or_create_nmc(cur, match)

            _write_audit(
                cur,
                actor=reviewer,
                action=f"match.{decision}",
                entity_type="match_candidate",
                entity_id=str(match_id),
                details={
                    "left_material_id": match["left_material_id"],
                    "right_material_id": match["right_material_id"],
                    "score": match["score"],
                    "note": note,
                    "nmc": nmc_record["nmc"] if nmc_record else None,
                },
            )
            return {"match": match, "nmc": nmc_record}


def _link_or_create_nmc(cur, match: dict) -> dict:
    left_id = match["left_material_id"]
    right_id = match["right_material_id"]

    cur.execute(
        """
        SELECT nm.id, nm.nmc, nm.canonical_material_id, nm.explanation, nm.fsc
        FROM national_materials nm
        JOIN nmc_crosswalk x ON x.national_material_id = nm.id
        WHERE x.material_id IN (%s, %s)
        LIMIT 1
        """,
        (left_id, right_id),
    )
    existing = cur.fetchone()

    if existing:
        national_id = existing["id"]
        nmc = existing["nmc"]
        canonical = existing["canonical_material_id"]
        explanation = existing["explanation"] or ""
    else:
        explanation = _join_explanation(match["explanation"])

        # Anchor the National Material Code to the canonical material's Federal
        # Supply Classification: NMC-<FSC>-<sequence within that class>.
        cur.execute("SELECT fsc FROM materials WHERE id = %s", (left_id,))
        row = cur.fetchone()
        fsc = (row["fsc"] if row else None) or "9999"

        cur.execute(
            "SELECT count(*)::int AS n FROM national_materials WHERE fsc = %s",
            (fsc,),
        )
        sequence = cur.fetchone()["n"] + 1
        nmc = f"NMC-{fsc}-{sequence:05d}"

        cur.execute(
            """
            INSERT INTO national_materials (nmc, canonical_material_id, explanation, fsc)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (nmc, left_id, explanation, fsc),
        )
        national_id = cur.fetchone()["id"]
        canonical = left_id

    for material_id in (left_id, right_id):
        cur.execute(
            """
            INSERT INTO nmc_crosswalk (national_material_id, material_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (national_id, material_id),
        )

    cur.execute(
        """
        SELECT material_id
        FROM nmc_crosswalk
        WHERE national_material_id = %s
        ORDER BY material_id
        """,
        (national_id,),
    )
    local_ids = [r["material_id"] for r in cur.fetchall()]

    cur.execute("SELECT fsc FROM national_materials WHERE id = %s", (national_id,))
    fsc = cur.fetchone()["fsc"]

    record = {
        "nmc": nmc,
        "canonical_material_id": canonical,
        "local_material_ids": local_ids,
        "explanation": explanation,
        "fsc": fsc,
    }
    record.update(fsc_meta(fsc))
    return record


def _join_explanation(explanation) -> str:
    if isinstance(explanation, list):
        return "; ".join(str(item) for item in explanation)
    return str(explanation or "")
