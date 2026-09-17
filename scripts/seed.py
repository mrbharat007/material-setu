"""Seed the Material Setu database with a realistic multi-CPSE dataset.

Runs the same code path as the API (standardization, attribute extraction,
explainable matching) directly against the database, then plays a few steward
decisions so every screen of the dashboard has real content.

Usage:
    DATABASE_URL=postgresql://material_setu:material_setu_dev@127.0.0.1:5433/material_setu \\
        python scripts/seed.py --reset

Flags:
    --reset          truncate all tables first
    --threshold F    matching threshold (default 0.60)
    --no-decisions   ingest + match only, leave every candidate pending
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import auth, procurement_repository, user_repository  # noqa: E402
from app.database import get_connection  # noqa: E402
from app.db_bootstrap import ensure_schema  # noqa: E402
from app.main import decide, ingest, run_matching  # noqa: E402
from app.material_repository import get_all_materials  # noqa: E402
from app.schemas import DecisionIn, MaterialIn, MatchStatus  # noqa: E402

DEMO_USERS = [
    ("admin@material-setu.gov.in", "NUMM Administrator", "materialsetu", "admin"),
    ("steward@material-setu.gov.in", "A. Krishnan · NUMM Steward", "materialsetu", "steward"),
]

CSV_PATH = ROOT / "sample_data" / "materials.csv"

REVIEWERS = [
    "A. Krishnan · NUMM Steward",
    "S. Rao · Category Lead (Rotating Equipment)",
    "M. Iyer · Materials Engineer",
    "P. Banerjee · Steward (Electrical)",
]


def reset_database() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE audit_log, nmc_crosswalk, national_materials,
                         match_candidates, procurement_transactions, materials
                         RESTART IDENTITY CASCADE
                """
            )
    print("· database reset")


def seed_users() -> int:
    created = 0
    for email, name, password, role in DEMO_USERS:
        if user_repository.get_user_by_email(email):
            continue
        user_repository.create_user(
            email=email,
            name=name,
            password_hash=auth.hash_password(password),
            role=role,
        )
        created += 1
    return created


_BASE_PRICE_TERMS = [
    # (keyword in normalized description, base unit price INR)
    ("22217", 2600), ("nu320", 3800), ("nu 320", 3800), ("6309", 720),
    ("6004", 260), ("6205", 320),
    ("stud bolt", 240), ("hex bolt", 18), ("hexagon head", 18),
    ("spring washer", 6), ("hex nut", 6), ("hexagon nut", 6),
    ("11 kv", 850), ("11kv", 850), ("control cable", 115),
    ("3.5 core 240", 620), ("3.5c x 240", 620), ("acsr", 210),
    ("bronze gate valve", 1900), ("bronze gate", 1900), ("bronze", 1900),
    ("gate valve", 4200), ("valve gate", 4200),
    ("globe valve", 3800), ("valve globe", 3800),
    ("ball valve", 9500), ("valve ball", 9500),
    ("motor operated", 45000),
    ("seamless pipe", 1250), ("gi pipe", 145), ("g.i. pipe", 145),
    ("15 kw", 42000), ("15kw", 42000), ("5.5 kw", 19500), ("5.5kw", 19500),
    ("boiler quality", 82000), ("ms plate", 68000), ("steel plate", 68000),
    ("spiral wound", 480), ("gasket", 120),
    ("grease", 340), ("turbine oil", 210), ("methanol", 62),
    ("pressure transmitter", 34000), ("pressure gauge", 1250),
    ("mccb", 6800), ("circuit breaker", 145000), ("contactor", 2400),
    ("cable gland", 210),
    ("welding electrode", 240), ("refractory brick", 85),
    ("rock bit", 320000), ("tricone", 320000), ("get adapter", 18000),
    ("otr tyre", 850000), ("tyre", 850000),
    ("v belt", 420), ("sprocket", 1600),
    ("hydraulic hose", 380), ("hydraulic return line filter", 4200),
    ("led flood light", 3200), ("primer", 340), ("o ring", 45),
    ("conveyor belt", 2100), ("disc insulator", 1450),
]
_BASE_PRICE_FSC = {
    "3110": 500, "3120": 900, "5305": 12, "5306": 18, "5307": 240, "5310": 6,
    "6145": 300, "4820": 4500, "4810": 45000, "4730": 850, "4710": 600,
    "4720": 380, "6105": 30000, "9515": 68000, "9510": 62000, "9520": 65000,
    "9150": 340, "9140": 95, "6685": 5000, "6680": 22000, "5330": 120,
    "5331": 45, "5925": 9000, "6110": 2400, "6120": 380000, "3439": 240,
    "9350": 85, "9330": 900, "3820": 120000, "2610": 850000, "3030": 420,
    "3020": 1600, "8010": 340, "6210": 3200, "5970": 1450,
}


def _base_price(normalized: str, fsc: str | None) -> float:
    for term, price in _BASE_PRICE_TERMS:
        if term in normalized:
            return float(price)
    return float(_BASE_PRICE_FSC.get(fsc or "", 500))


def _cpse_bias(cpse: str) -> float:
    """Deterministic 0.82x–1.55x buyer price factor — models the fragmented,
    non-benchmarked procurement the platform is meant to expose."""
    h = int(hashlib.sha1(cpse.encode()).hexdigest(), 16)
    return 0.82 + (h % 74) / 100.0


def seed_procurement() -> int:
    from datetime import date, timedelta

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*)::int AS n FROM procurement_transactions")
            if cur.fetchone()["n"] > 0:
                return 0
            cur.execute(
                "SELECT id, cpse, description, normalized_description, fsc, uom "
                "FROM materials ORDER BY id"
            )
            materials = cur.fetchall()

    rows: list[dict] = []
    for m in materials:
        rng = random.Random(f"proc-{m['id']}")
        base = _base_price(m["normalized_description"] or "", m["fsc"])
        price0 = base * _cpse_bias(m["cpse"])
        n_orders = rng.randint(2, 5)
        target_line_value = rng.uniform(90_000, 450_000)
        for k in range(n_orders):
            unit_price = round(price0 * rng.uniform(0.90, 1.14), 2)
            qty = max(1, round((target_line_value / max(unit_price, 1)) * rng.uniform(0.6, 1.5)))
            days_ago = rng.randint(30, 1000)
            rows.append(
                {
                    "material_id": m["id"],
                    "order_date": date.today() - timedelta(days=days_ago),
                    "quantity": qty,
                    "unit_price_inr": unit_price,
                    "po_number": f"{m['cpse']}/PO/{2026 - days_ago // 365}/{rng.randint(1000, 9999)}",
                    "supplier": None,
                }
            )
    return procurement_repository.insert_transactions(rows)


def backfill_classification() -> int:
    """Classify / unit-resolve any rows that predate the reference-data step."""
    from app.services.classifier import classify
    from app.services.uom_registry import uom_code

    updated = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, description, material_family, uom "
                "FROM materials WHERE fsc IS NULL OR uom_code IS NULL"
            )
            targets = cur.fetchall()
            for row in targets:
                c = classify(row["description"], row["material_family"])
                cur.execute(
                    "UPDATE materials SET fsc = %s, fsc_title = %s, uom_code = %s "
                    "WHERE id = %s",
                    (c["fsc"], c["fsc_title"], uom_code(row["uom"]), row["id"]),
                )
                updated += 1
    return updated


def load_items() -> list[MaterialIn]:
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    return [
        MaterialIn(
            cpse=row["cpse"].strip(),
            sector=(row.get("sector") or "").strip() or None,
            local_code=row["local_code"].strip(),
            description=row["description"].strip(),
            material_family=(row.get("material_family") or "").strip() or None,
            manufacturer=(row.get("manufacturer") or "").strip() or None,
            manufacturer_part_no=(row.get("manufacturer_part_no") or "").strip()
            or None,
            uom=(row.get("uom") or "").strip() or None,
        )
        for row in rows
    ]


def _is_duplicate_error(exc: Exception) -> bool:
    detail = str(getattr(exc, "detail", exc))
    return "Duplicate" in detail


def ingest_items(items: list[MaterialIn]) -> int:
    try:
        created = ingest(items, user=None)
        return len(created)
    except Exception as exc:  # noqa: BLE001 - FastAPI HTTPException on duplicate
        if not _is_duplicate_error(exc):
            raise

    # Some rows already exist: ingest the remainder one at a time.
    created = 0
    for item in items:
        try:
            ingest([item], user=None)
            created += 1
        except Exception as exc:  # noqa: BLE001
            if not _is_duplicate_error(exc):
                raise
    return created


def _is_clean(match: dict) -> bool:
    """A candidate a steward can approve on sight: strong text match, at least
    one corroborating attribute and no flagged engineering conflict."""
    if match["score"] < 0.82:
        return False
    lines = match["explanation"]
    if any(line.startswith("conflict in") or "score reduced" in line for line in lines):
        return False
    if not any(line.startswith("same ") for line in lines):
        return False
    # Leave roughly a third of the clean candidates pending for the live demo.
    return (match["left_material_id"] + match["right_material_id"]) % 3 != 0


def play_decisions(matches: list[dict]) -> tuple[int, int]:
    local_code = {m["id"]: m["local_code"] for m in get_all_materials()}

    def touches(match: dict, code: str) -> bool:
        return code in (
            local_code.get(match["left_material_id"], ""),
            local_code.get(match["right_material_id"], ""),
        )

    ordered = sorted(matches, key=lambda m: m["score"], reverse=True)

    # A genuine near-miss: same bore / rating / type as the carbon-steel gate
    # valves, but a bronze body. The model proposes it; the steward declines.
    rejected = [m for m in ordered if touches(m, "HP-GV-50-BRZ")][:2]
    rejected_ids = {m["id"] for m in rejected}

    approved = [
        m
        for m in ordered
        if m["id"] not in rejected_ids and _is_clean(m)
    ]

    for i, match in enumerate(approved):
        decide(
            match["id"],
            DecisionIn(
                decision=MatchStatus.approved,
                reviewer=REVIEWERS[i % len(REVIEWERS)],
                note="Confirmed same material identity across CPSEs.",
            ),
            user=None,
        )

    for match in rejected:
        decide(
            match["id"],
            DecisionIn(
                decision=MatchStatus.rejected,
                reviewer=REVIEWERS[1],
                note="Body material differs (bronze vs carbon steel) — distinct materials.",
            ),
            user=None,
        )

    return len(approved), len(rejected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.60)
    parser.add_argument("--no-decisions", action="store_true")
    args = parser.parse_args()

    ensure_schema()
    print("· schema synced (base + migrations)")

    if args.reset:
        reset_database()

    new_users = seed_users()
    print(
        f"· demo users: {new_users} created "
        f"({len(DEMO_USERS) - new_users} already present) — "
        "password for all: materialsetu"
    )

    items = load_items()
    created = ingest_items(items)
    print(
        f"· ingested {created} new materials "
        f"({len(items) - created} already present, {len(items)} in file)"
    )

    backfilled = backfill_classification()
    if backfilled:
        print(f"· classified {backfilled} pre-existing rows (FSC + Rec 20 unit)")

    tx = seed_procurement()
    if tx:
        print(f"· procurement history: {tx} representative PO lines generated")

    matches = run_matching(threshold=args.threshold, user=None)
    print(
        f"· matching run: {len(matches)} candidate pairs at "
        f"threshold {args.threshold:.2f}"
    )

    if args.no_decisions or not matches:
        print("done.")
        return

    approved, rejected = play_decisions(matches)
    print(f"· steward decisions: {approved} approved, {rejected} rejected")
    print("done.")


if __name__ == "__main__":
    main()
