"""Read-only access to the event registry (config/events_registry.yaml) and the candidates' ground truth.

The registry is the single list of events: the selected events and the dropped alternative, in a fixed order that
the scripts use for their rows. Official names, coordinates and reference times stay in the hand-edited ground-truth
table (candidates_ground_truth.csv); the registry refers to its rows by the same id.

Times: `utc()` returns tz-aware UTC timestamps everywhere (callers that need naive UTC convert at the call site).
Run `python -m wildfire_central_node_placement.registry` to print the registry.
"""
import argparse

import pandas as pd
import yaml

from wildfire_central_node_placement.paths import GROUND_TRUTH_FILE, REGISTRY_FILE


def load_registry(path=REGISTRY_FILE):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def utc(value):
    """Time string or timestamp to a tz-aware UTC pandas Timestamp; None stays None."""
    if value is None:
        return None
    t = pd.Timestamp(value)
    return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")


def get_event(event_id, registry=None):
    registry = registry or load_registry()
    if event_id not in registry["events"]:
        raise KeyError(f"event '{event_id}' not in registry; available: {list(registry['events'])}")
    return registry["events"][event_id]


def get_region(region_id, registry=None):
    registry = registry or load_registry()
    if region_id not in registry["regions"]:
        raise KeyError(f"region '{region_id}' not in registry; available: {list(registry['regions'])}")
    return registry["regions"][region_id]


def region_arg():
    """--region (id from the registry `regions`) for the region-level scripts; returns (region_id, region entry)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True, help="region id from events_registry.yaml")
    region_id = parser.parse_args().region
    return region_id, get_region(region_id)


def event_arg():
    """--event (id from the registry `events`) for the per-event scripts; returns the event id."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="event id from events_registry.yaml")
    return parser.parse_args().event


# ---- event selections (registry order) ----
def all_events(registry=None):
    """Every event in the registry: the selected events and the dropped alternative."""
    return list((registry or load_registry())["events"])


def selected_events(registry=None):
    """The events of the thesis (selection: selected), in registry order."""
    registry = registry or load_registry()
    return [e for e, ev in registry["events"].items() if ev["selection"] == "selected"]


def ground_truth():
    """Hand-edited ground truth of every candidate (official time, area, location, decision), indexed by id."""
    return pd.read_csv(GROUND_TRUTH_FILE).set_index("candidate_id")


def events_in_continent(continent, events):
    """The given events whose ground-truth continent is `continent` (e.g. the GOES events of North America)."""
    gt = ground_truth()
    return [e for e in events if gt.loc[e, "continent"] == continent]


if __name__ == "__main__":
    reg = load_registry()
    print(f"registry: {REGISTRY_FILE} (schema_version {reg['schema_version']})")
    print("\ndata_window:", reg["data_window"])
    print("regions:", reg["regions"])
    print("\nconventions:")
    for k, v in reg["conventions"].items():
        print(f"  {k}: {v}")
    for eid, ev in reg["events"].items():
        print(f"\nevent '{eid}' [{ev['selection']}]")
        for k, v in ev.items():
            if k != "selection":
                print(f"  {k}: {v}")
