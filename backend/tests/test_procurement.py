"""Opportunity maths — pure-function coverage that needs no database."""
import importlib


def _opportunities_from(rows):
    mod = importlib.import_module("app.procurement_repository")
    # rebuild the grouping/aggregation on an injected row set
    from collections import defaultdict
    from app.services.classifier import fsc_meta

    by_nmc = defaultdict(list)
    for r in rows:
        by_nmc[r["nmc"]].append(r)

    out = []
    for nmc, txns in by_nmc.items():
        cpses = sorted({t["cpse"] for t in txns})
        if len(cpses) < mod._MIN_CPSES:
            continue
        total_qty = sum(t["quantity"] for t in txns)
        prices = [t["unit_price"] for t in txns]
        if min(prices) <= 0 or max(prices) / min(prices) < mod._MIN_SPREAD:
            continue
        saving = sum(t["quantity"] * (t["unit_price"] - min(prices)) for t in txns)
        out.append({"nmc": nmc, "estimated_saving_inr": round(saving, 2),
                    "spread": round(max(prices) / min(prices), 2)})
    return out


def _tx(nmc, cpse, qty, price):
    return {"nmc": nmc, "cpse": cpse, "quantity": qty, "unit_price": price,
            "fsc": "3110", "description": "x", "uom": "EA", "uom_code": "EA"}


def test_single_cpse_is_not_an_opportunity():
    rows = [_tx("N1", "ONGC", 10, 100), _tx("N1", "ONGC", 5, 300)]
    assert _opportunities_from(rows) == []


def test_flat_pricing_is_not_an_opportunity():
    rows = [_tx("N1", "ONGC", 10, 100), _tx("N1", "NTPC", 10, 101)]
    assert _opportunities_from(rows) == []


def test_saving_is_gap_to_best_price():
    rows = [
        _tx("N1", "ONGC", 100, 100.0),   # best
        _tx("N1", "NTPC", 100, 150.0),   # 50 over on 100 units -> 5000
        _tx("N1", "SAIL", 100, 130.0),   # 30 over on 100 units -> 3000
    ]
    ops = _opportunities_from(rows)
    assert len(ops) == 1
    assert ops[0]["estimated_saving_inr"] == 8000.0
    assert ops[0]["spread"] == 1.5
