from app.services.uom_registry import resolve_uom, canonical_uom, uom_code


def test_local_variants_map_to_rec20_each():
    for raw in ("EA", "NOS", "No.", "PC", "Nr", "pieces"):
        r = resolve_uom(raw)
        assert r["code"] == "EA"
        assert r["name"] == "each"
        assert r["matched"] is True


def test_indian_shorthand():
    assert uom_code("MT") == "TNE"          # metric tonne, not the registry "MT"
    assert uom_code("Kgs") == "KGM"         # not kilogram-per-second (KGS)
    assert uom_code("RMT") == "MTR"         # running metre
    assert uom_code("SQMM") == "MMK"
    assert canonical_uom("Ltr") == "litre"


def test_bulk_packaging_counts_as_each():
    assert uom_code("drum") == "EA"
    assert uom_code("Roll") == "EA"


def test_unknown_unit_is_not_matched():
    r = resolve_uom("frobnicate")
    assert r["matched"] is False
    assert r["code"] is None


def test_empty():
    assert resolve_uom(None) is None
    assert resolve_uom("   ") is None
