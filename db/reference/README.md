# Reference standards

Material Setu grounds two of its harmonization steps in published international
standards rather than hand-rolled opinion.

## `unece_rec20_units.csv`

Active unit-of-measure codes from **UN/CEFACT Recommendation No. 20 — Codes for
Units of Measure Used in International Trade** (maintained by UNECE). Deprecated
(`X` / `D` status) rows are dropped.

- `code` — the Rec 20 common code (e.g. `EA`, `MTR`, `KGM`, `LTR`, `SET`, `MTK`)
- `name` — canonical unit name
- `symbol` — display symbol where defined
- `quantity` — broad quantity category

Source: <https://github.com/datasets/unece-units-of-measure> (derived from the
official UNECE Rev. 17 spreadsheet). Used by `app/services/uom_registry.py`.

## `fsc_groups.csv` / `fsc_classes.csv`

**Federal Supply Classification (FSC)** — the 2-digit group / 4-digit class
structure of the NATO Codification System (NCS). India is a Tier-2 sponsor of the
NCS through the Directorate of Standardisation, so an FSC-anchored national code
is defensible for CPSE MRO material.

`fsc_classes.csv` is a curated subset covering the industrial / MRO groups a CPSE
material master actually contains (bearings, valves, fasteners, pipe & fittings,
electrical, instruments, lubricants, metal stock, …). The full H2 handbook has
~645 classes across 78 groups.

Source: NATO Supply Classification Groups, FSC Cataloging Handbook H2
(US DoD / DLA, public domain). Used by `app/services/classifier.py`.

A published National Material Code is formatted `NMC-<FSC>-<sequence>`
(e.g. `NMC-3110-00042` = an antifriction bearing identity).
