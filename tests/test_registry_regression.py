"""Per-event results against the registry `regression_expected` values (FIRMS and SEVIRI event steps)."""
import json

import pytest

from wildfire_central_node_placement.paths import event_dir
from wildfire_central_node_placement.registry import load_registry

REG = load_registry()
WITH_EXPECTED = [e for e, ev in REG["events"].items() if ev.get("regression_expected")]


@pytest.mark.parametrize("event_id", WITH_EXPECTED)
def test_firms_event_summary(event_id):
    s = json.loads((event_dir("firms", event_id, "processed") / "event_summary.json").read_text())
    assert s["regression_check"], "no registry value checked"
    assert all(c["match"] for c in s["regression_check"]), s["regression_check"]


@pytest.mark.parametrize("event_id", WITH_EXPECTED)
def test_seviri_event_summary(event_id):
    exp = REG["events"][event_id]["regression_expected"]
    s = json.loads((event_dir("lsasaf", event_id, "processed") / "seviri_event_summary.json").read_text())
    assert s["slots_with_detection_in_search_box"] == exp["lsasaf_slots_with_detection_in_search_box"]
    assert s["rules"]["primary"]["first_detection_utc"] == exp["first_seviri_event_pixel_utc"]
