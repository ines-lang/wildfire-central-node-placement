"""Geostationary coverage of the selected events and the later southern-hemisphere network cases.

GEO imagers stay census only (S0 alert / T0 reference), so they are the only satellites whose coverage depends on
the region. For each GEO in fire_capability.csv with an orbit in window_payloads.csv, the
sub-satellite longitude on 13 Aug 2025 12:00 UTC (SGP4) and the viewing zenith angle (VZA) to each site.
VZA above about 65 deg is too oblique for fire detection (pixel growth); 999 = not visible.

Sites: the eight events (registry and ground-truth file) plus the later network cases of 10 Nov 2026
(Africa: Eastern Cape and Ghanzi; Australia: El Questro).
Output: geo_coverage.csv
Usage: python pipeline/2_space_segment/05_geo_coverage.py
"""
import numpy as np
import pandas as pd
from sgp4.api import Satrec, jday

from wildfire_central_node_placement.paths import FIRE_CAPABILITY_FILE, SPACE_TABLES, WINDOW_PAYLOADS_FILE
from wildfire_central_node_placement.registry import ground_truth, selected_events

R_GEO, R_E = 42164.0, 6371.0
EVENTS = selected_events()
LATER = {"eastern_cape": ("Eastern Cape (ZA), cluster 215", -31.24, 27.98), "ghanzi": None, "el_questro": None}

cap = pd.read_csv(FIRE_CAPABILITY_FILE)
win = pd.read_csv(WINDOW_PAYLOADS_FILE)
geo = win[win.orbit_family.eq("GEO")].merge(cap[["norad_id", "mission", "public_fire_product", "status_aug2025"]], on="norad_id")
gt = ground_truth()
sites = {e: (gt.loc[e, "name"], gt.loc[e, "lat"], gt.loc[e, "lon"]) for e in EVENTS}
for k, v in LATER.items():
    sites[k] = v or (gt.loc[k, "name"], gt.loc[k, "lat"], gt.loc[k, "lon"])

jd, fr = jday(2025, 8, 13, 12, 0, 0)
d = jd + fr - 2451545.0
gmst = np.radians((280.46061837 + 360.98564736629 * d) % 360)
rows = []
for g in geo.itertuples():
    _, p, _ = Satrec.twoline2rv(g.line1, g.line2).sgp4(jd, fr)
    lon0 = (np.degrees(np.arctan2(p[1], p[0]) - gmst) + 180) % 360 - 180
    for sid, (name, lat, lon) in sites.items():
        c = np.cos(np.radians(lat)) * np.cos(np.radians(lon - lon0))
        vza = np.degrees(np.arctan2(np.sqrt(1 - c * c) * R_GEO, R_GEO * c - R_E)) if c > R_E / R_GEO else 999.0
        rows.append(dict(mission=g.mission, sub_lon_deg=round(lon0, 1), site=sid, site_name=name, vza_deg=round(vza, 1),
                         status_aug2025=g.status_aug2025, public_fire_product=g.public_fire_product))
out = pd.DataFrame(rows)
out.to_csv(SPACE_TABLES / "geo_coverage.csv", index=False)
pd.set_option("display.width", 250)
print(out.pivot(index="mission", columns="site", values="vza_deg").replace(999.0, np.nan).round(0).to_string())
