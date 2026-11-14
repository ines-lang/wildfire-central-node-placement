"""Inventory of the raw FIRMS downloads (read-only report, v1 Step 1).

For every DL_FIRE_* folder and CSV: archive or NRT, row count, date range,
lat/lon extent, columns, and counts inside the data window / region box.
Usage: python pipeline/0_public_record/firms/common/00_inventory.py --region <region_id>
"""
import pandas as pd

from wildfire_central_node_placement.geo import in_box
from wildfire_central_node_placement.paths import FIRMS_RAW
from wildfire_central_node_placement.registry import load_registry, region_arg, utc

REG = load_registry()
PERIOD_START, PERIOD_END = utc(REG["data_window"]["start_utc"]), utc(REG["data_window"]["end_utc"])
REGION_ID, REGION = region_arg()


def obs_time(df):
    hhmm = df["acq_time"].astype(str).str.zfill(4)
    return pd.to_datetime(df["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M", utc=True)


for csv in sorted(FIRMS_RAW.glob("DL_FIRE_*/*.csv")):
    df = pd.read_csv(csv, dtype={"acq_time": str})
    kind = "NRT" if "_nrt_" in csv.name else "archive" if "_archive_" in csv.name else "unknown"
    t = obs_time(df)
    in_period = t.between(PERIOD_START, PERIOD_END)
    print(f"\n=== {csv.parent.name}/{csv.name}  [{kind}]")
    print(f"rows: {len(df)}")
    print(f"time: {t.min()} to {t.max()}  (unique dates: {df['acq_date'].nunique()})")
    print(f"lat: {df['latitude'].min():.4f} to {df['latitude'].max():.4f}   "
          f"lon: {df['longitude'].min():.4f} to {df['longitude'].max():.4f}")
    print(f"columns: {list(df.columns)}")
    for col in ["satellite", "instrument", "version", "daynight", "type"]:
        if col in df.columns:
            print(f"  {col}: {dict(df[col].value_counts(dropna=False).head(8))}")
    print(f"in PERIOD: {in_period.sum()}   in PERIOD & {REGION_ID}: {(in_period & in_box(df['latitude'], df['longitude'], REGION['box'])).sum()}")
    print(f"exact duplicate rows: {df.duplicated().sum()}")
