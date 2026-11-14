"""Step 2.10: wildfire or managed burn? Screen of the largest southern-hemisphere complexes (criteria 1 to 4).

Two indicators per complex, from data that need no official record:
  1. Land cover under the kept FIRMS detections: ESA WorldCover 2021 v200 (10 m), read remotely from its public
     cloud-optimised GeoTIFFs at the 80 m overview (no download). Shares of tree cover, shrub + grassland,
     cropland, built-up and other.
  2. Fire behaviour from FIRMS, on 1 km cells (the clustering grid):
     - share_cells_one_day: share of cells detected on one day only. A spreading front burns a cell once and moves
       on (high share); pile, field or clearing burns light the same spots again and again (low share).
     - front_km_per_day: largest distance of a detection from the first-day detections, divided by the active days.
     - first_day_share: share of detections on the first day (many scattered starts at once = lit burning).
Rule of thumb, reported, not a filter: wildfire-like = mostly tree/shrub/grass, little cropland, a moving front.
Caveats: WorldCover is 2021 (fires on land cleared since show as tree cover); in African and Australian savannas
most fires are lit by people, so "wildfire" here means an uncontrolled spreading vegetation fire.

Output: wildfire_check.csv
Usage: python pipeline/4_events/10_wildfire_check.py
"""
import math

import numpy as np
import pandas as pd
import rasterio

from wildfire_central_node_placement.geo import local_km
from wildfire_central_node_placement.paths import EVENTS_TABLES, region_dir

FIRMS = region_dir("firms", "world") / "firms_clean.csv"
OUT = EVENTS_TABLES
TOP_N = {"Africa": 15, "South America": 10, "Oceania": 10}
WC_URL = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
WC_OVERVIEW = 2                       # overview index 2 = factor 8, about 80 m
CLASSES = {"tree": [10, 95], "shrub_grass": [20, 30], "cropland": [40], "built": [50], "other": [60, 70, 80, 90, 100]}
CELL_DEG = 0.01

cx = pd.read_csv(OUT / "complexes_criteria.csv")
cx = cx[cx.c1_vegetation & cx.c2_onset_in_window & cx.c3_size & cx.c4_spreading & (cx.lat < 0)]
cx = pd.concat([g.nlargest(TOP_N[c], "firms_area_ha") for c, g in cx.groupby("continent") if c in TOP_N])
names = pd.read_csv(OUT / "candidate_matches.csv")[["candidate_id", "cluster_id"]].dropna()
det = pd.read_csv(FIRMS, usecols=["latitude", "longitude", "obs_time_utc", "fire_cluster", "qc_flag"])
det = det[det.fire_cluster.isin(cx.cluster_id) & det.qc_flag.isin(["ok", "type_missing"])]
det["day"] = pd.to_datetime(det.obs_time_utc).dt.floor("D")


def tile(lat, lon):
    la, lo = math.floor(lat / 3) * 3, math.floor(lon / 3) * 3
    return f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"


def land_cover(d):
    codes = []
    for t, g in d.groupby(d.apply(lambda r: tile(r.latitude, r.longitude), axis=1)):
        with rasterio.open(WC_URL.format(t), OVERVIEW_LEVEL=WC_OVERVIEW) as src:
            codes += [v[0] for v in src.sample(zip(g.longitude, g.latitude))]
    codes = np.array(codes)
    return {k: round(np.isin(codes, v).mean(), 2) for k, v in CLASSES.items()}


def km(lat1, lon1, lat2, lon2):
    return np.hypot(*local_km(lat1, lon1)(lon2, lat2))


rows = []
for r in cx.itertuples():
    d = det[det.fire_cluster == r.cluster_id].copy()
    d["cell"] = (d.latitude // CELL_DEG).astype(int).astype(str) + "_" + (d.longitude // CELL_DEG).astype(int).astype(str)
    days_per_cell = d.groupby("cell").day.nunique()
    first = d[d.day == d.day.min()]
    reach = max(km(first.latitude.mean(), first.longitude.mean(), d.latitude, d.longitude))
    lc = land_cover(d)
    rows.append({"continent": r.continent, "cluster_id": int(r.cluster_id), "lat": round(r.lat, 2), "lon": round(r.lon, 2),
                 "firms_area_ha": r.firms_area_ha, "first_utc": r.first_utc, "active_days": d.day.nunique(),
                 **{f"lc_{k}": v for k, v in lc.items()},
                 "share_cells_one_day": round((days_per_cell == 1).mean(), 2),
                 "front_km_per_day": round(reach / max(1, d.day.nunique() - 1), 1),
                 "first_day_share": round(len(first) / len(d), 2)})
res = pd.DataFrame(rows).merge(names, on="cluster_id", how="left")
res["wildfire_like"] = ((res.lc_tree + res.lc_shrub_grass >= 0.7) & (res.lc_cropland <= 0.15)
                        & (res.share_cells_one_day >= 0.6))
res.to_csv(OUT / "wildfire_check.csv", index=False)
pd.set_option("display.width", 250)
print(res.drop(columns=["first_utc"]).to_string(index=False))
