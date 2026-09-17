from app.services.classifier import classify, fsc_meta, UNCLASSIFIED_FSC


def test_bearing_classifies_to_fsc_3110():
    c = classify("BALL BEARING DEEP GROOVE 6205 2Z 25X52X15", "Bearing")
    assert c["fsc"] == "3110"
    assert c["fsg"] == "31"
    assert c["confidence"] == "high"          # term + family agree
    assert "ball bearing" in c["basis"]


def test_valve_type_drives_class():
    powered = classify("MOTOR OPERATED GATE VALVE 200NB CL300", "Valve")
    assert powered["fsc"] == "4810"
    plain = classify("GATE VALVE 50NB CL150 CS A216 WCB", "Valve")
    assert plain["fsc"] == "4820"


def test_family_only_fallback():
    c = classify("some part with no classifying words", "Bearing")
    assert c["fsc"] == "3110"
    assert c["confidence"] == "medium"


def test_unclassified_when_nothing_matches():
    c = classify("magnesium anode 9 lb for cathodic protection")
    assert c["fsc"] == UNCLASSIFIED_FSC
    assert c["confidence"] == "none"


def test_fsc_meta_expands_group():
    meta = fsc_meta("6145")
    assert meta["fsg"] == "61"
    assert "Wire" in meta["fsc_title"]
    assert "Electric Wire" in meta["fsg_title"]
