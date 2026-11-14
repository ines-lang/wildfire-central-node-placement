"""Step 4: downlink latency of the S1 EO layer over the selected events, per ground-station set.

For every S1 satellite, every pass with the event inside the instrument swath (reference time to +24 h) is found;
for each pass, the time to the first contact (elevation >= MIN_ELEVATION_DEG) with a station of each set is
computed. The rule depends on the link type of the station (column link):
  stored  the satellite records the data and dumps them at the first contact after the observation;
  direct  direct readout: the station only receives what the satellite observes while in view, so it counts
          (latency 0) only if it sees the satellite at the observation time;
  relay   TDRSS relay (Terra): no direct-view geometry; fixed wait RELAY_WAIT_MIN.
Inputs:  eo_census.csv (S1 TLEs), ground_stations.csv (station sets; column satellites = the
         satellites a station serves, "all" for every satellite; column link = stored, direct or relay),
         the candidates' ground truth (event location and reference time); events: the selected events
Outputs: ground_contacts.csv (one row per pass and station set), 02_downlink_latency.png (results/3_ground_segment)

Usage: python pipeline/3_ground_segment/01_ground_contacts.py
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from skyfield.api import load, wgs84

from wildfire_central_node_placement.orbits import (HALF_SWATH_KM, MIN_ELEVATION_DEG, TERRA_RELAY_WAIT_MIN as RELAY_WAIT_MIN,
                                distance_to_track_km, pass_runs, satellite)
from wildfire_central_node_placement.paths import GROUND_FIGURES, GROUND_STATIONS_FILE, GROUND_TABLES, SPACE_TABLES, ensure
from wildfire_central_node_placement.registry import ground_truth, selected_events

# ---- parameters ----
EVENTS = selected_events()
HORIZON_H = 24                      # passes from the reference time to +24 h
LOOKAHEAD_H = 6                     # search window for the next ground contact after a pass
STEP_S = 30
DPI = 300

ts = load.timescale()
census = pd.read_csv(SPACE_TABLES / "eo_census.csv")
s1 = census[census["role"] == "S1 EO layer"]
stations = pd.read_csv(GROUND_STATIONS_FILE)
gt = ground_truth()

rows = []
for ev in EVENTS:
    e = gt.loc[ev]
    t_ref = pd.Timestamp(e["ignition_utc"])
    secs = np.arange(0, (HORIZON_H + LOOKAHEAD_H) * 3600, STEP_S)
    t = ts.from_datetimes((t_ref + pd.to_timedelta(secs, unit="s")).to_pydatetime())
    for sat_row in s1.itertuples():
        sat = satellite(sat_row.line1, sat_row.line2, sat_row.mission, ts)
        d = distance_to_track_km(sat, t, e["lat"], e["lon"])
        inside = (d <= HALF_SWATH_KM[sat_row.instrument]) & (secs <= HORIZON_H * 3600)
        if not inside.any():
            continue
        # passes = runs of consecutive samples inside the swath; observation = closest approach of the run
        run_id = pass_runs(inside)
        elev = {st.station: (sat - wgs84.latlon(st.lat, st.lon)).at(t).altaz()[0].degrees
                for st in stations[stations["link"] != "relay"].drop_duplicates("station").itertuples()}
        for r in np.unique(run_id[run_id > 0]):
            idx = np.flatnonzero(run_id == r)
            i_obs = idx[np.argmin(d[idx])]
            for set_name, members in stations.groupby("station_set", sort=False):
                serves = members["satellites"].eq("all") | members["satellites"].str.split(";").apply(
                    lambda sats: sat_row.mission in sats)
                best = None                 # (latency in minutes, station)
                for st in members[serves].itertuples():
                    if st.link == "relay":
                        cand = RELAY_WAIT_MIN
                    elif st.link == "direct":
                        cand = 0.0 if elev[st.station][i_obs] >= MIN_ELEVATION_DEG else None
                    else:
                        vis = np.flatnonzero(elev[st.station][i_obs:] >= MIN_ELEVATION_DEG)
                        cand = vis[0] * STEP_S / 60 if vis.size else None
                    if cand is not None and (best is None or cand < best[0]):
                        best = (cand, st.station)
                rows.append(dict(event=ev, satellite=sat_row.mission, instrument=sat_row.instrument,
                                 obs_utc=t_ref + pd.Timedelta(seconds=int(secs[i_obs])),
                                 hours_after_reference=round(secs[i_obs] / 3600, 2),
                                 off_track_km=round(float(d[i_obs]), 0), station_set=set_name,
                                 first_station=best[1] if best else None,
                                 latency_min=round(best[0], 1) if best else np.nan))
gc = pd.DataFrame(rows)
gc.to_csv(ensure(GROUND_TABLES) / "ground_contacts.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")

# ---- report: per event and set, first observation and its latency, and the median over all passes ----
first = gc.sort_values("hours_after_reference").groupby(["event", "station_set"]).first()
summ = gc.groupby(["event", "station_set"])["latency_min"].agg(passes="size", median="median", max="max")
print(first[["satellite", "hours_after_reference", "latency_min", "first_station"]].join(summ).round(1).to_string())

# ---- figure: downlink latency of every pass, per event and station set ----
sets = list(stations["station_set"].unique())
fig_w = 9
fig, ax = plt.subplots(figsize=(fig_w, 3.8))
colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
for k, s in enumerate(sets):
    for j, ev in enumerate(EVENTS):
        v = gc[(gc.event == ev) & (gc.station_set == s)]["latency_min"].dropna()
        x = j + (k - (len(sets) - 1) / 2) * 0.25
        ax.scatter(np.full(len(v), x), v, s=12, color=colors[k], alpha=0.7, label=s if j == 0 else None)
        ax.plot([x - 0.08, x + 0.08], [v.median()] * 2, color=colors[k], lw=2)
ax.set_xticks(range(len(EVENTS)), [gt.loc[e, "name"].split(",")[0] for e in EVENTS], fontsize=7)
ax.set_ylabel("Observation to first\nground contact (min)")
ax.set_title(f"S1 passes over each event (reference to +{HORIZON_H} h; Terra via TDRSS: fixed {RELAY_WAIT_MIN} min): downlink latency "
             f"per station set (elevation >= {MIN_ELEVATION_DEG} deg; line = median)", loc="left", fontsize=8)
ax.legend(fontsize=7, frameon=False)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(ensure(GROUND_FIGURES) / "02_downlink_latency.png", dpi=DPI)
plt.close(fig)
print(f"\nwritten: {GROUND_TABLES / 'ground_contacts.csv'}, {GROUND_FIGURES / '02_downlink_latency.png'}")
