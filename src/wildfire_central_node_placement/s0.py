"""S0: public detections inside each event's official final perimeter, and the T0 rule of 13 Nov 2026.

Detection sources (`sources()`): FIRMS VIIRS + MODIS (kept detections of the event-selection screen), Sentinel-3
SLSTR (SL_2_FRP NTC), SEVIRI (LSA SAF FRP-PIXEL; Europe, Africa, Turkey), GOES-18 and GOES-19 (ABI FDC; North
America). A detection belongs to an event if its centre lies inside the official final perimeter buffered by
BUFFER_KM (`inside_perimeter`). Membership by the official perimeter is NOT the FIRMS-cluster rule of the per-event
input pipelines; it is the same, independent footprint for every source.

T0 rule (`t0_rule`; registry conventions.t0):
  1. detections of every public source inside the perimeter + 2 km, static and non-vegetation sources removed;
  2. episodes: split where no detection occurs for at least GAP_H hours (earlier, separate fires inside the same
     perimeter form their own episodes: Piodao, Aldeia das Dez; Oimbra, the merged Gudin fire);
  3. the event is the main episode, the one with most detections;
  4. T0 = first robust detection of that episode: a polar detection, or a geostationary one confirmed by the same
     satellite within GEO_CONFIRM_MIN (registry convention: at least two consecutive SEVIRI slots).
The official or press time is NOT used to set T0; it is only compared with it (S0 question, signed difference).
Sensitivity: GAP_H in GAP_SENSITIVITY, GEO confirmation in CONFIRM_SENSITIVITY.
"""
import json

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape

from wildfire_central_node_placement.geo import local_km
from wildfire_central_node_placement.paths import (CROSSCHECK_FILE, EFFIS_RAW, EVENTS_TABLES, GOES_PROCESSED, PERIMETERS_RAW,
                               SLSTR_PROCESSED, region_dir)
from wildfire_central_node_placement.registry import events_in_continent, ground_truth, load_registry, selected_events

BUFFER_KM = 2.0                 # registry seviri_membership_sensitivity_km; also covers the 1 km to 2 km pixel centres
SEVIRI_REGIONS = ["iberia", "anatolia"]               # LSA SAF region exports (registry regions)
GAP_H = 12                       # twice the longest polar revisit gap at mid-latitudes (about 6 h)
GAP_SENSITIVITY = [6, 12, 24]
GEO_CONFIRM_MIN = 20             # next SEVIRI slot (15 min) or GOES scan (5 to 10 min): strict, registry convention
CONFIRM_SENSITIVITY = [20, 120]  # lenient: confirmed by the same satellite within 2 h (fire flickering at the limit)


def perimeters(events):
    """Official final perimeter of each event (registry `perimeter`: EFFIS burnt area, WFIGS or BC Wildfire Service)."""
    reg = load_registry()
    out = {}
    for ev in events:
        p = reg["events"][ev]["perimeter"]
        folder = EFFIS_RAW if p["source"] == "EFFIS" else PERIMETERS_RAW
        features = json.load(open(folder / p["file"]))["features"]
        if "effis_id" in p:      # a burnt-area file holds every record of its region; take the record's feature
            f = [f for f in features if f["properties"]["id"] == p["effis_id"]][-1]
        else:
            f = features[0]
        out[ev] = shape(f["geometry"])
    return out


def sources():
    """One table per source: time_utc, lat, lon, platform, sensor (and the event, if already cropped per event)."""
    f = pd.read_csv(EVENTS_TABLES / "candidate_detections.csv", parse_dates=["obs_time_utc"])
    f = f[f.kept.astype(bool) & ~f.non_vegetation.astype(bool)]
    yield "FIRMS VIIRS + MODIS", f.rename(columns={"obs_time_utc": "time_utc", "latitude": "lat", "longitude": "lon"})   # has platform, sensor
    s = pd.read_csv(SLSTR_PROCESSED / "slstr_fire_points.csv", parse_dates=["time_utc"])
    s["platform"] = s.platform.map({"S3A": "Sentinel-3A", "S3B": "Sentinel-3B"})
    s["sensor"] = "SLSTR"
    yield "Sentinel-3 SLSTR", s.drop(columns="event").drop_duplicates(["time_utc", "lat", "lon"])
    l = pd.concat([pd.read_csv(region_dir("lsasaf", r) / "observations_standard.csv", parse_dates=["obs_time_utc"])
                   for r in SEVIRI_REGIONS])
    l = l[(l.qc_flag == "ok") & (l.static_proxy != True)]  # noqa: E712  (column is empty or bool)
    l["platform"] = "Meteosat-10"                   # LSA SAF MSG-Disk = 0 deg SEVIRI (EO census, 10 Nov 2026)
    yield "SEVIRI (LSA SAF)", l.rename(columns={"obs_time_utc": "time_utc", "latitude": "lat", "longitude": "lon"})
    goes_file = GOES_PROCESSED / "goes_fire_pixels.csv"
    if not goes_file.exists():
        print("GOES fire pixels not processed yet: skipped")
        return
    g = pd.read_csv(goes_file, parse_dates=["scan_start_utc"])
    g = g[g.confident].rename(columns={"scan_start_utc": "time_utc"}).drop(columns="event")
    g["platform"], g["sensor"] = g.satellite, "ABI"
    for sat, gs in g.groupby("satellite"):
        yield f"{sat} (ABI FDC)", gs.drop_duplicates(["time_utc", "lat", "lon"])


def outside_geo_disk(source_name, in_north_america):
    """True if a geostationary source cannot see the event: GOES only North America, SEVIRI everywhere else."""
    return ("GOES" in source_name and not in_north_america) or ("SEVIRI" in source_name and in_north_america)


def inside_perimeter(src, ev, gt, polys):
    """Rows of src whose centre lies inside the event's perimeter buffered by BUFFER_KM (local km plane)."""
    to_km = local_km(gt.loc[ev, "lat"], gt.loc[ev, "lon"])
    zone = shapely.transform(polys[ev], lambda c: np.column_stack(to_km(c[:, 0], c[:, 1]))).buffer(BUFFER_KM)
    near = src[(src.lat - gt.loc[ev, "lat"]).abs().lt(1) & (src.lon - gt.loc[ev, "lon"]).abs().lt(1.5)]
    x, y = to_km(near.lon.values, near.lat.values)
    return near[shapely.contains_xy(zone, x, y)]


def event_detections(events):
    """Every public detection inside the perimeter of each event, sorted by event and time."""
    gt, polys = ground_truth(), perimeters(events)
    north_america = set(events_in_continent("North America", events))
    det = []
    for name, src in sources():
        src = src.copy()
        src["time_utc"] = pd.to_datetime(src["time_utc"], utc=True)
        geo = "SEVIRI" in name or "GOES" in name
        for ev in events:
            if outside_geo_disk(name, ev in north_america):
                continue
            inside = inside_perimeter(src, ev, gt, polys)
            det.append(pd.DataFrame({"event": ev, "source": name, "geo": geo, "time_utc": inside.time_utc.values,
                                     "platform": inside.platform.values, "sensor": inside.sensor.values}))
    det = pd.concat(det).sort_values(["event", "time_utc"]).reset_index(drop=True)
    det["time_utc"] = pd.to_datetime(det.time_utc, utc=True)
    return det


def robust(det, confirm_min):
    """Polar detections always; GEO only if the same platform detects again within confirm_min."""
    r = ~det.geo
    for _, g in det[det.geo].groupby(["event", "platform"]):
        t = g.time_utc.sort_values()
        times = t.drop_duplicates()
        nxt = t.map(dict(zip(times, times.shift(-1) - times)))
        r.loc[t.index] = (nxt > pd.Timedelta(0)) & (nxt <= pd.Timedelta(minutes=confirm_min))
    return r


def t0_for(det, robust_by_confirm, ev, gap_h, confirm_min=GEO_CONFIRM_MIN):
    """T0 of one event: first robust detection of its main episode (episodes split at gaps >= gap_h)."""
    d = det[det.event == ev].assign(robust=robust_by_confirm[confirm_min][det.event == ev]).sort_values("time_utc")
    episode = (d.time_utc.diff() >= pd.Timedelta(hours=gap_h)).cumsum()
    main = episode.value_counts().idxmax()
    e = d[(episode == main) & d.robust]
    first = e.iloc[0]
    return dict(event=ev, gap_h=gap_h, confirm_min=confirm_min, t0_utc=first.time_utc, t0_source=first.source, t0_platform=first.platform,
                t0_sensor=first.sensor, episodes=int(episode.max() + 1), main_episode_start=d[episode == main].time_utc.min(),
                excluded_before=int((d.time_utc < d[episode == main].time_utc.min()).sum()))


def t0_rule(events=None):
    """Apply the rule to the events (default: the selected events).

    Returns det (every detection inside a perimeter, column robust = main GEO confirmation), sens (T0 for every gap
    and confirmation variant) and main (main rule per event, with the human alert time and the signed difference).
    """
    events = events or selected_events()
    det = event_detections(events)
    robust_by_confirm = {c: robust(det, c) for c in CONFIRM_SENSITIVITY}
    det["robust"] = robust_by_confirm[GEO_CONFIRM_MIN]
    sens = pd.DataFrame([t0_for(det, robust_by_confirm, ev, g, c)
                         for ev in events for g in GAP_SENSITIVITY for c in CONFIRM_SENSITIVITY])
    main = (sens[(sens.gap_h == GAP_H) & (sens.confirm_min == GEO_CONFIRM_MIN)]
            .drop(columns=["gap_h", "confirm_min"]).set_index("event"))
    ref = pd.read_csv(CROSSCHECK_FILE).set_index("event")
    main["human_time_utc"] = pd.to_datetime(ref.loc[main.index, "utc_used"], utc=True)
    main["human_kind"] = ref.loc[main.index, "kind"]
    main["human_confidence"] = ref.loc[main.index, "confidence"]
    main["t0_minus_human_h"] = ((main.t0_utc - main.human_time_utc).dt.total_seconds() / 3600).round(2)
    stable = sens.groupby("event").t0_utc.nunique().eq(1)
    main["t0_stable_over_gaps"] = stable.loc[main.index]
    return det, sens, main
