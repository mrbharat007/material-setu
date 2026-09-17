"""Locate the published reference-standard CSVs shipped in ``db/reference/``."""

import csv
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "db" / "reference"


def load_csv(name: str) -> list[dict]:
    path = REFERENCE_DIR / name
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
