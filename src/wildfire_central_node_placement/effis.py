"""EFFIS burnt-area records: command-line arguments of the per-event scripts, record sets, and the FIRMS outputs
they are checked against (read-only).

EFFIS never defines a footprint, T0 or ignition; every comparison is reported only.
"""
import argparse

import pandas as pd

from wildfire_central_node_placement.paths import event_dir, region_dir

COLS = ["latitude", "longitude", "obs_time_utc", "platform"]


def event_args():
    """Parse --event (required) and --records (user-confirmed EFFIS ids, only for events
    whose registry entry has no `effis_ids` yet) for the per-event EFFIS scripts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--records", nargs="+", default=None)
    # values not (yet) in the registry; passed explicitly, printed and proposed for the registry
    parser.add_argument("--area-refs", nargs="*", default=[], help='e.g. "Junta provisional=31500"')
    parser.add_argument("--reported-end", default=None, help="reported end of activity, ISO UTC")
    parser.add_argument("--neighbour-provinces", nargs="*", default=None)
    return parser.parse_args()


def effis_record_ids(ev, records_arg):
    """Registry `effis_ids` if present; otherwise the user-confirmed --records."""
    if ev.get("effis_ids"):
        if records_arg and sorted(records_arg) != sorted(map(str, ev["effis_ids"])):
            raise SystemExit(f"--records {records_arg} differs from registry effis_ids {ev['effis_ids']}")
        return [str(i) for i in ev["effis_ids"]], "registry effis_ids"
    if not records_arg:
        raise SystemExit(f"registry has no effis_ids (candidates: {ev.get('effis_candidate_ids')}); "
                         "pass the user-confirmed set with --records")
    return [str(i) for i in records_arg], "user-confirmed --records (registry has candidates only)"


def firms_event_file(event_id, name):
    """FIRMS per-event output (processed folder)."""
    return event_dir("firms", event_id, "processed") / name


def load_event_detections(event_id):
    """FIRMS detections around the event with an `event_member` column, and a label of the source used."""
    path = firms_event_file(event_id, "event_observations.csv")
    if not path.exists():
        raise SystemExit(f"no FIRMS members for '{event_id}': {path} missing (run the FIRMS event scripts first)")
    df = pd.read_csv(path, usecols=COLS + ["event_member"])
    # provenance label written into the EFFIS outputs (path relative to the former FIRMS folder, kept unchanged)
    source = f"FIRMS v2 events/{event_id}/processed/event_observations.csv"
    df["obs_time_utc"] = pd.to_datetime(df["obs_time_utc"], utc=True)
    df["event_member"] = df["event_member"].astype(str).str.lower().eq("true")
    return df, source


def load_event_passes(event_id):
    """FIRMS passes with at least one event member, or None if not produced yet."""
    path = firms_event_file(event_id, "event_overpasses.csv")
    return (pd.read_csv(path), path) if path.exists() else (None, path)


def firms_overpasses_file(region_id):
    """FIRMS passes over one region (event-agnostic)."""
    return region_dir("firms", region_id) / "overpasses.csv"


def load_overpasses(region_id):
    return pd.read_csv(firms_overpasses_file(region_id), parse_dates=["start_time_utc", "end_time_utc"])
