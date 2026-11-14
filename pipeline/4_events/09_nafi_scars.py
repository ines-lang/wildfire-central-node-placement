"""Step 2.9: NAFI burnt-area check of the Oceania complexes (criteria 1 to 4).

NAFI (North Australia & Rangelands Fire Information, Charles Darwin University) maps burnt areas at 250 m from
MODIS, one value per pixel = month of burning in the year (1 to 12). It is the operational fire-scar product used
by Bushfires NT and the WA / Qld rangeland agencies, so it is the closest thing to an official burned area there.
It has no ignition time. Coverage: lat -34.5 to -9.3, lon 112.9 to 154.0.

For each complex the 2025 month raster (WCS layer public:fsm2025) is downloaded for its bounding box + MARGIN_DEG.
August scar of the complex = the 8-connected August patches that contain at least one kept FIRMS detection of the
cluster. Reported: that area, the share of detections on August / earlier-month / unburnt pixels, and the month mix.
Caveats: scar_touches_box_edge = True means the scar continues beyond the download box (area is a lower bound).\nAugust includes burning after the FIRMS data end (15 Aug) up to 31 Aug, and touching August fires merge.

Output: nafi_oceania.csv; rasters cached in the NAFI raw folder (downloaded only if missing)
Usage: python pipeline/4_events/09_nafi_scars.py
"""
from collections import deque

import numpy as np
import pandas as pd
import rasterio
import requests

from wildfire_central_node_placement.paths import EVENTS_TABLES, NAFI_RAW, ensure, region_dir

FIRMS = region_dir("firms", "world") / "firms_clean.csv"
RAW, OUT = ensure(NAFI_RAW), EVENTS_TABLES
WCS = "https://firenorth.org.au/geoserver/public/wcs"
MARGIN_DEG = 0.15
AUGUST = 8

cx = pd.read_csv(OUT / "complexes_criteria.csv")
cx = cx[(cx.continent == "Oceania") & cx.c1_vegetation & cx.c2_onset_in_window & cx.c3_size & cx.c4_spreading]
cx = cx[(cx.lat_min >= -34.5) & (cx.lat_max <= -9.3) & (cx.lon_min >= 112.9) & (cx.lon_max <= 154.0)]
names = pd.read_csv(OUT / "candidate_matches.csv")[["candidate_id", "cluster_id"]].dropna()
det = pd.read_csv(FIRMS, usecols=["latitude", "longitude", "fire_cluster", "qc_flag"])
det = det[det.fire_cluster.isin(cx.cluster_id) & det.qc_flag.isin(["ok", "type_missing"])]


def raster(row):
    f = RAW / f"fsm2025_cluster{int(row.cluster_id)}.tif"
    if not f.exists():
        w, e = row.lon_min - MARGIN_DEG, row.lon_max + MARGIN_DEG
        s, n = row.lat_min - MARGIN_DEG, row.lat_max + MARGIN_DEG
        r = requests.get(WCS, params=[("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"),
                                      ("coverageId", "public__fsm2025"), ("format", "image/tiff"),
                                      ("subset", f"Long({w},{e})"), ("subset", f"Lat({s},{n})")], timeout=120)
        r.raise_for_status()
        f.write_bytes(r.content)
    with rasterio.open(f) as src:
        return src.read(1), src.transform


def flood(mask, seeds):
    """8-connected patches of mask that contain a seed pixel."""
    out = np.zeros_like(mask, dtype=bool)
    q = deque((r, c) for r, c in seeds if mask[r, c])
    for r, c in q:
        out[r, c] = True
    while q:
        r, c = q.popleft()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                y, x = r + dr, c + dc
                if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and mask[y, x] and not out[y, x]:
                    out[y, x] = True
                    q.append((y, x))
    return out


rows = []
for row in cx.itertuples():
    a, tr = raster(row)
    d = det[det.fire_cluster == row.cluster_id]
    rr, cc = rasterio.transform.rowcol(tr, d.longitude.values, d.latitude.values)
    rr, cc = np.clip(rr, 0, a.shape[0] - 1), np.clip(cc, 0, a.shape[1] - 1)
    month_at = a[rr, cc]
    scar = flood(a == AUGUST, zip(rr, cc))
    px_km2 = abs(tr.a * tr.e) * (111.32 ** 2) * np.cos(np.radians(row.lat))
    aug_ha = scar.sum() * px_km2 * 100
    rows.append({"cluster_id": int(row.cluster_id), "lat": row.lat, "lon": row.lon, "firms_area_ha": row.firms_area_ha,
                 "first_utc": row.first_utc, "nafi_august_scar_ha": round(aug_ha),
                 "share_det_on_august": round((month_at == AUGUST).mean(), 3),
                 "share_det_on_earlier_month": round(((month_at > 0) & (month_at < AUGUST)).mean(), 3),
                 "share_det_unburnt": round((month_at == 0).mean(), 3),
                 "scar_touches_box_edge": bool(scar[0].any() or scar[-1].any() or scar[:, 0].any() or scar[:, -1].any())})
res = pd.DataFrame(rows).merge(names, on="cluster_id", how="left").sort_values("nafi_august_scar_ha", ascending=False)
res.to_csv(OUT / "nafi_oceania.csv", index=False)
pd.set_option("display.width", 220)
print(res.head(15).to_string(index=False))
