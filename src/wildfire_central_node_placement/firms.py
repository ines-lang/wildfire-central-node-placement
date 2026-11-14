"""FIRMS clean tables and the per-event FIRMS selection.

Event rule (registry conventions, v1 Larouco method), used by the per-event FIRMS scripts:
1. seed = first detection at or after (ignition_utc - ignition_tolerance_min) within seed_radius_km
   of reference_point (ties at the same minute: closest to the reference point);
2. event = the seed's FIRMS fire cluster (event_member);
3. first polar member = first VIIRS/MODIS event member at or after (ignition_utc - ignition_tolerance_min).
   This is the T0 of the first rule (registry conventions.t0_until_13nov2026), kept as `t0_utc` in the FIRMS
   event summary and its regression check; the T0 of the thesis is the rule of 13 Nov 2026 (wildfire_central_node_placement.s0).
"""
import pandas as pd

from wildfire_central_node_placement.geo import dist_km, grow_box, in_box
from wildfire_central_node_placement.paths import ensure, event_dir, region_dir
from wildfire_central_node_placement.registry import get_event, load_registry, utc

PYTHON_DTYPES = {"acq_time": str, "version": str, "request_id": str, "confidence": str, "confidence_raw": str}
ROW_MARGIN_DEG = 0.5          # event_observations rows: search box plus this margin (strategy v2.1)
BASELINE_SENSORS = ["VIIRS", "MODIS"]
SENSING_LAYER = ["Suomi-NPP", "NOAA-20", "NOAA-21", "Terra", "Aqua"]


def read_clean(region_id):
    """<region_id>/firms_clean.csv (data/processed/firms) with times parsed and static_proxy as True / False / missing."""
    df = pd.read_csv(region_dir("firms", region_id) / "firms_clean.csv", dtype={**PYTHON_DTYPES, "static_proxy": str})
    df["obs_time_utc"] = pd.to_datetime(df["obs_time_utc"], utc=True)
    # static_proxy: True/False for type_missing rows, empty otherwise (read as text, never bool("False"))
    df["static_proxy"] = df["static_proxy"].map({"True": True, "False": False}).astype("object")
    return df


def event_dirs(event_id):
    """FIRMS per-event output folders (processed, figures, notes), created if missing."""
    return {k: ensure(event_dir("firms", event_id, k)) for k in ["processed", "figures", "notes"]}


def select_event(event_id, df=None, cluster_col="fire_cluster"):
    """Return a dict with the registry entry, the clean table with event columns, seed and first polar member."""
    reg = load_registry()
    ev = get_event(event_id, reg)
    df = read_clean(ev["region"]) if df is None else df.copy()
    ignition = utc(ev["ignition_utc"])
    earliest = ignition - pd.Timedelta(minutes=ev["ignition_tolerance_min"])
    ref = ev["reference_point"]

    df["dist_ref_km"] = dist_km(ref["lat"], ref["lon"], df["latitude"].to_numpy(), df["longitude"].to_numpy())
    cand = df[(df["obs_time_utc"] >= earliest) & (df["dist_ref_km"] <= ev["seed_radius_km"])]
    if cand.empty:
        raise ValueError(f"{event_id}: no detection within {ev['seed_radius_km']} km after {earliest}")
    seed = cand.sort_values(["obs_time_utc", "dist_ref_km"]).iloc[0]
    cluster_id = int(seed[cluster_col])

    df["event_id"] = event_id
    df["in_search_box"] = in_box(df["latitude"], df["longitude"], ev["search_box"])
    df["event_member"] = df[cluster_col] == cluster_id
    df["event_member_sensitivity"] = df["event_member"]          # FIRMS: identical to event_member
    members = df[df["event_member"]]
    t0_rows = members[(members["obs_time_utc"] >= earliest) & members["sensor"].isin(BASELINE_SENSORS)]
    t0 = t0_rows.sort_values(["obs_time_utc", "dist_ref_km"]).iloc[0]
    return {"registry": reg, "event": ev, "df": df, "seed": seed, "cluster_id": cluster_id,
            "ignition": ignition, "earliest": earliest, "t0": t0,
            "n_members_before_earliest": int((members["obs_time_utc"] < earliest).sum()),
            "row_box": grow_box(ev["search_box"], ROW_MARGIN_DEG)}
