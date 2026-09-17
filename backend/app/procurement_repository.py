"""Historical procurement transactions and the collaborative-procurement view.

Once duplicate identities are harmonized under one National Material Code, the
spend behind that code becomes visible *across* CPSEs — and so does the price
CPSEs pay for the very same item. That gap is a tender-aggregation opportunity.
"""

from collections import defaultdict

import psycopg

from .database import get_connection
from .services.classifier import fsc_meta


def insert_transactions(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO procurement_transactions
                    (material_id, order_date, quantity, unit_price_inr,
                     po_number, supplier)
                VALUES (%(material_id)s, %(order_date)s, %(quantity)s,
                        %(unit_price_inr)s, %(po_number)s, %(supplier)s)
                """,
                rows,
            )
    return len(rows)


def clear_transactions() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM procurement_transactions")
            return cur.rowcount


def count_transactions() -> int:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*)::int AS n FROM procurement_transactions"
                )
                return cur.fetchone()["n"]
    except psycopg.errors.UndefinedTable:
        return 0


_MIN_SPREAD = 1.12       # only surface a code where the price gap is real
_MIN_CPSES = 2           # collaborative = at least two buyers


def opportunities() -> list[dict]:
    """One row per National Material Code with cross-CPSE spend and price spread.

    Returns ``[]`` (not an error) when there is no procurement history yet or the
    table hasn't been migrated in.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT nm.nmc, nm.fsc,
                           m.cpse, m.description,
                           t.quantity::float8 AS quantity,
                           t.unit_price_inr::float8 AS unit_price,
                           m.uom, m.uom_code
                    FROM procurement_transactions t
                    JOIN materials m       ON m.id = t.material_id
                    JOIN nmc_crosswalk x   ON x.material_id = t.material_id
                    JOIN national_materials nm ON nm.id = x.national_material_id
                    """
                )
                rows = cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return []

    by_nmc: dict[str, list[dict]] = defaultdict(list)
    fsc_of: dict[str, str] = {}
    for r in rows:
        by_nmc[r["nmc"]].append(r)
        fsc_of[r["nmc"]] = r["fsc"]

    results: list[dict] = []
    for nmc, txns in by_nmc.items():
        cpses = sorted({t["cpse"] for t in txns})
        if len(cpses) < _MIN_CPSES:
            continue

        total_qty = sum(t["quantity"] for t in txns)
        total_value = sum(t["quantity"] * t["unit_price"] for t in txns)
        if total_qty <= 0:
            continue

        prices = [t["unit_price"] for t in txns]
        min_price, max_price = min(prices), max(prices)
        if min_price <= 0 or max_price / min_price < _MIN_SPREAD:
            continue

        weighted_avg = total_value / total_qty
        # Overpayment vs the best price any CPSE actually achieved.
        estimated_saving = sum(
            t["quantity"] * (t["unit_price"] - min_price) for t in txns
        )

        per_cpse = []
        best_cpse = None
        for cpse in cpses:
            ct = [t for t in txns if t["cpse"] == cpse]
            q = sum(t["quantity"] for t in ct)
            v = sum(t["quantity"] * t["unit_price"] for t in ct)
            avg = v / q if q else 0.0
            per_cpse.append(
                {"cpse": cpse, "quantity": round(q, 2), "avg_price": round(avg, 2)}
            )
            if best_cpse is None or avg < best_cpse["avg_price"]:
                best_cpse = per_cpse[-1]
        per_cpse.sort(key=lambda c: c["avg_price"])

        uom = next((t["uom"] for t in txns if t["uom"]), None)
        results.append(
            {
                "nmc": nmc,
                **fsc_meta(fsc_of[nmc]),
                "description": txns[0]["description"],
                "cpses": cpses,
                "cpse_count": len(cpses),
                "order_count": len(txns),
                "uom": uom,
                "total_quantity": round(total_qty, 2),
                "total_value_inr": round(total_value, 2),
                "min_unit_price": round(min_price, 2),
                "max_unit_price": round(max_price, 2),
                "avg_unit_price": round(weighted_avg, 2),
                "price_spread_ratio": round(max_price / min_price, 2),
                "best_price_cpse": best_cpse["cpse"] if best_cpse else None,
                "estimated_saving_inr": round(estimated_saving, 2),
                "per_cpse": per_cpse,
            }
        )

    results.sort(key=lambda r: r["estimated_saving_inr"], reverse=True)
    return results


def savings_summary() -> dict:
    ops = opportunities()
    return {
        "opportunities": len(ops),
        "aggregation_saving_inr": round(
            sum(o["estimated_saving_inr"] for o in ops), 2
        ),
        "spend_under_review_inr": round(
            sum(o["total_value_inr"] for o in ops), 2
        ),
    }
