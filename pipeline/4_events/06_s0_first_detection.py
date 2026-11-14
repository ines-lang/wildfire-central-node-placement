"""Step 2.6: preliminary S0 first detection of every event, per public source, inside the official final perimeter.

Before the new events are added to the registry and run through the per-event pipelines, this step gives one
comparable number per event and source: the first fire pixel whose centre lies inside the official final perimeter
(buffered by BUFFER_KM) at or after the reference time minus TOLERANCE_H.

Membership by the official perimeter is NOT the FIRMS-cluster rule of the pipelines (registry conventions); it is used
here because it is the same, independent footprint for every source. A perimeter can also contain an earlier,
separate fire (Piodao: Aldeia das Dez); detections in the 24 h before the window are therefore counted and reported.

Perimeters (official final footprints, registry `perimeter` of each event):
    EFFIS burnt areas 2025 (WFS modis.ba.poly.2025)   larouco, molezuelas, oimbra, piodao, derdara, silifke
    NIFC WFIGS final perimeter                         red_canyon
    BC Wildfire Service historical fire polygons       mount_underwood
Sources (wildfire_central_node_placement.s0.sources): FIRMS VIIRS + MODIS (kept detections, as in the timeline figure), Sentinel-3 SLSTR
(SL_2_FRP NTC), SEVIRI (LSA SAF FRP-PIXEL, Europe and Africa), GOES-18 and GOES-19 (ABI FDC, North America).
Events: every registry event, the dropped alternative included.

Output: s0_first_detection.csv (with the platform and sensor of each first detection, for the per-sensor study)
Usage: python pipeline/4_events/06_s0_first_detection.py
"""
import numpy as np
import pandas as pd

from wildfire_central_node_placement.paths import EVENTS_TABLES
from wildfire_central_node_placement.registry import all_events, events_in_continent, ground_truth
from wildfire_central_node_placement.s0 import inside_perimeter, outside_geo_disk, perimeters, sources

# ---- parameters ----
PROC = EVENTS_TABLES
TOLERANCE_H = 1.0               # detections up to 1 h before the reference count (registry molezuelas tolerance)
EARLIER_H = 24                  # window before that, reported as earlier activity inside the perimeter
EVENTS = all_events()
NORTH_AMERICA = set(events_in_continent("North America", EVENTS))   # GOES events; SEVIRI covers the others

gt = ground_truth()
polys = perimeters(EVENTS)
rows = []
for name, src in sources():
    src = src.copy()
    src["time_utc"] = pd.to_datetime(src["time_utc"], utc=True)
    for ev in EVENTS:
        ref = pd.Timestamp(gt.loc[ev, "ignition_utc"])
        if outside_geo_disk(name, ev in NORTH_AMERICA):
            continue                                        # outside the disk of that geostationary satellite
        inside = inside_perimeter(src, ev, gt, polys)
        h = (inside.time_utc - ref).dt.total_seconds() / 3600
        after = h[h >= -TOLERANCE_H]
        rows.append(dict(event=ev, source=name, reference_utc=ref,
                         first_detection_utc=inside.time_utc[after.idxmin()] if len(after) else pd.NaT,
                         first_detection_h=round(after.min(), 2) if len(after) else np.nan,
                         first_detection_platform=inside.platform[after.idxmin()] if len(after) else None,
                         first_detection_sensor=inside.sensor[after.idxmin()] if len(after) else None,
                         n_detections_inside=int(len(after)),
                         n_earlier_inside=int(h.between(-TOLERANCE_H - EARLIER_H, -TOLERANCE_H, inclusive="left").sum())))
out = pd.DataFrame(rows)
out.to_csv(PROC / "s0_first_detection.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
print(out.pivot(index="event", columns="source", values="first_detection_h").loc[EVENTS].to_string())
