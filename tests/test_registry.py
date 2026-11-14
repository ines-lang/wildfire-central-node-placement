"""Consistency of the event registry with the ground-truth table and the raw perimeters."""
from wildfire_central_node_placement.paths import EFFIS_RAW, PERIMETERS_RAW
from wildfire_central_node_placement.registry import all_events, ground_truth, load_registry, selected_events
from wildfire_central_node_placement.s0 import perimeters


def test_events_in_ground_truth():
    gt = ground_truth()
    for e in all_events():
        assert e in gt.index, e
    sel = set(gt.index[gt["decision"] == "selected"])
    assert set(selected_events()) == sel


def test_selection_values_and_order():
    reg = load_registry()
    assert {ev["selection"] for ev in reg["events"].values()} <= {"selected", "dropped"}
    assert all_events()[0] == "larouco" and len(selected_events()) == 7
    assert all("dropped" in ev for ev in reg["events"].values() if ev["selection"] == "dropped")


def test_perimeters_exist():
    reg = load_registry()
    for e in all_events():
        p = reg["events"][e]["perimeter"]
        assert ((EFFIS_RAW if p["source"] == "EFFIS" else PERIMETERS_RAW) / p["file"]).exists(), e
    assert set(perimeters(all_events())) == set(all_events())
