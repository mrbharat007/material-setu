from . import procurement_repository
from .database import get_connection
from .services.classifier import fsc_meta


def get_stats() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*)::int AS n FROM materials")
            materials = cur.fetchone()["n"]

            cur.execute("SELECT count(DISTINCT cpse)::int AS n FROM materials")
            cpses = cur.fetchone()["n"]

            cur.execute(
                """
                SELECT coalesce(sector, 'Unclassified') AS name, count(*)::int AS n
                FROM materials
                GROUP BY 1
                ORDER BY n DESC, name
                """
            )
            by_sector = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT cpse AS name, count(*)::int AS n
                FROM materials
                GROUP BY 1
                ORDER BY n DESC, name
                """
            )
            by_cpse = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT coalesce(material_family, 'Unclassified') AS name,
                       count(*)::int AS n
                FROM materials
                GROUP BY 1
                ORDER BY n DESC, name
                """
            )
            by_family = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT coalesce(fsc, '9999') AS fsc, count(*)::int AS n
                FROM materials
                GROUP BY 1
                """
            )
            group_counts: dict[str, int] = {}
            for r in cur.fetchall():
                meta = fsc_meta(r["fsc"])
                label = f"{meta['fsg']} · {meta['fsg_title']}"
                group_counts[label] = group_counts.get(label, 0) + r["n"]
            by_supply_group = [
                {"name": name, "n": n}
                for name, n in sorted(
                    group_counts.items(), key=lambda kv: (-kv[1], kv[0])
                )
            ]

            cur.execute(
                "SELECT status, count(*)::int AS n FROM match_candidates GROUP BY 1"
            )
            status = {r["status"]: r["n"] for r in cur.fetchall()}

            cur.execute("SELECT count(*)::int AS n FROM national_materials")
            nmc_count = cur.fetchone()["n"]

            cur.execute(
                "SELECT count(DISTINCT material_id)::int AS n FROM nmc_crosswalk"
            )
            linked_materials = cur.fetchone()["n"]

            cur.execute(
                """
                SELECT coalesce(sum(c - 1), 0)::int AS n
                FROM (
                    SELECT count(*) AS c
                    FROM nmc_crosswalk
                    GROUP BY national_material_id
                ) t
                """
            )
            master_reduction = cur.fetchone()["n"]

            cur.execute(
                """
                SELECT coalesce(max(cnt), 0)::int AS n
                FROM (
                    SELECT x.national_material_id,
                           count(DISTINCT m.cpse) AS cnt
                    FROM nmc_crosswalk x
                    JOIN materials m ON m.id = x.material_id
                    GROUP BY 1
                ) t
                """
            )
            max_cpses_linked = cur.fetchone()["n"]

    procurement = procurement_repository.savings_summary()

    return {
        "materials": materials,
        "cpses": cpses,
        "by_sector": by_sector,
        "by_cpse": by_cpse,
        "by_family": by_family,
        "by_supply_group": by_supply_group,
        "matches_pending": status.get("pending", 0),
        "matches_approved": status.get("approved", 0),
        "matches_rejected": status.get("rejected", 0),
        "nmc_count": nmc_count,
        "linked_materials": linked_materials,
        "master_record_reduction": master_reduction,
        "max_cpses_linked": max_cpses_linked,
        "procurement_opportunities": procurement["opportunities"],
        "aggregation_saving_inr": procurement["aggregation_saving_inr"],
    }
