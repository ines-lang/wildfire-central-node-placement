"""Read FY-3D MERSI-II daily global fire files (GFR) and list the fire points of the data window.

Product: FY3D_MERSI_GBAL_L2_GFR_MLT_GLL_YYYYMMDD_POAD_1000M_MS.HDF (NSMC), one HDF5 file per UTC day,
dataset FIRES with 9 columns: year, MMDD, HHMM (start of the 5-min granule, UTC), lat, lon, sub-pixel fire area,
fire temperature (fixed 750 in the files checked), fire grade (binned intensity), reliability (50 / 100 / 200).
Reference: Chen et al. 2022, ESSD 14:3489. Download: NSMC FengYun data portal (account needed).

Inputs:  the FY-3D raw folder (*.HDF, or files given on the command line)
         the candidates' ground truth (event points and reference times)
Outputs: data/processed/fy3d/fy3d_fire_points.csv (all points in the window), printed first detection per event

Usage: python pipeline/0_public_record/fy3d/01_read_gfr.py [file.HDF ...]
"""
import sys
from pathlib import Path

import h5py
import pandas as pd

from wildfire_central_node_placement.geo import dist_km
from wildfire_central_node_placement.paths import FY3D_PROCESSED, FY3D_RAW
from wildfire_central_node_placement.registry import ground_truth

# ---- parameters ----
RAW, OUT_FILE = FY3D_RAW, FY3D_PROCESSED / "fy3d_fire_points.csv"
# explicit subset: the selected events of 6 Nov 2026 (the script predates silifke, added 10 Nov); kept so the printed
# table does not change. Use registry.selected_events() when the FY-3D files are downloaded again.
EVENTS = ["larouco", "molezuelas", "oimbra", "piodao", "red_canyon", "derdara"]
WINDOW = ("2025-08-08", "2025-08-17")         # data window, end exclusive
EVENT_RADIUS_KM = 25                          # fire point counts for an event within this distance of its point
COLUMNS = ["year", "mmdd", "hhmm", "latitude", "longitude", "fire_area", "fire_temperature", "fire_grade",
           "reliability"]


def read_file(path):
    with h5py.File(path, "r") as h:
        a = h["FIRES"][()]
    df = pd.DataFrame(a.reshape(-1, len(COLUMNS)), columns=COLUMNS)
    y, md, hm = df["year"].astype(int), df["mmdd"].astype(int), df["hhmm"].astype(int)
    df["obs_time_utc"] = pd.to_datetime(dict(year=y, month=md // 100, day=md % 100, hour=hm // 100, minute=hm % 100),
                                        utc=True)
    df["source_file"] = Path(path).name
    return df.drop(columns=["year", "mmdd", "hhmm"])


files = [Path(f) for f in sys.argv[1:]] or sorted(RAW.glob("FY3D_MERSI_GBAL_L2_GFR_*.HDF"))
if not files:
    raise SystemExit(f"no GFR files in {RAW} (download them from the NSMC FengYun data portal)")
fires = pd.concat([read_file(f) for f in files], ignore_index=True)
print(f"files: {len(files)}; fire points: {len(fires)}; time range {fires.obs_time_utc.min()} to {fires.obs_time_utc.max()}")
print("reliability codes:", fires["reliability"].value_counts().sort_index().to_dict())

window = fires[fires["obs_time_utc"].between(*pd.to_datetime(WINDOW, utc=True), inclusive="left")]
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
window.to_csv(OUT_FILE, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
print(f"in the data window {WINDOW[0]} to {WINDOW[1]}: {len(window)} points -> {OUT_FILE}")

# first FY-3D detection near each event, at or after its reference time
gt = ground_truth()
rows = []
for ev in EVENTS:
    e = gt.loc[ev]
    near = window[dist_km(e["lat"], e["lon"], window["latitude"], window["longitude"]) <= EVENT_RADIUS_KM]
    ref = pd.Timestamp(e["ignition_utc"])
    after = near[near["obs_time_utc"] >= ref].sort_values("obs_time_utc")
    first = after.iloc[0] if len(after) else None
    rows.append(dict(event=e["name"], reference_utc=ref, points_near=len(near),
                     first_fy3d_utc=first["obs_time_utc"] if first is not None else None,
                     hours_after_reference=round((first["obs_time_utc"] - ref).total_seconds() / 3600, 2)
                     if first is not None else None))
print(pd.DataFrame(rows).to_string(index=False))
