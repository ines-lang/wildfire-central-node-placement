"""S1: observation and time to ground for each event, from the simulator run.

Inputs:  the simulator run (wildfire_central_node_placement.s1.S1Run: 02_satellite_states.csv, positions every 60 s;
         11_access_windows.csv, station contacts at elevation >= 10 deg; simulator inputs: events, sensors),
         the event-selection tables (S0 detections and first detection)
Outputs: s1_passes.csv      one row per pass with the event inside the swath
         s1_validation.csv  one row per event: S0 against S1, and the answer to the S1 question
                            (best_*: the pass after the reference time whose data reach the ground first)
Ground segment: the frozen baseline.
Usage:   python pipeline/5_simulation/s1/01_s1_latency.py
"""
import pandas as pd

from wildfire_central_node_placement.geo import haversine_km as distance_km
from wildfire_central_node_placement.paths import EVENTS_TABLES, S1_TABLES, ensure
from wildfire_central_node_placement.registry import load_registry
from wildfire_central_node_placement.s1 import S1Run

S0 = EVENTS_TABLES
OUT = ensure(S1_TABLES)
MATCH_MIN = 15

run = S1Run()
events, sensors, states, minutes_to_ground = run.events, run.sensors, run.states, run.minutes_to_ground
# observations only inside the data window; the run continues 6 h after it so that late passes get a ground contact
WINDOW_END = pd.Timestamp(load_registry()["data_window"]["end_utc"])
states = states[states.time_utc <= WINDOW_END]

# ---- 1. passes with the event inside the swath ----
passes = []
for ev in events.itertuples():
    s = states.copy()
    s["d"] = distance_km(s.lat_deg, s.lon_deg, ev.lat, ev.lon)
    s = s[s.d <= s.satellite.map(sensors.half_swath_km)]
    for sat, g in s.groupby("satellite"):
        pass_id = (g.time_utc.diff() > pd.Timedelta("5min")).cumsum()   # new pass after a gap
        for _, p in g.groupby(pass_id):
            best = p.loc[p.d.idxmin()]                                    # closest approach = observation
            passes.append(dict(event=ev.event, satellite=sat, observation_utc=best.time_utc,
                               off_track_km=round(best.d), hours_from_reference=round(
                                   (best.time_utc - ev.reference_utc).total_seconds() / 3600, 2)))
passes = pd.DataFrame(passes)
passes["minutes_to_ground"] = [minutes_to_ground(p.satellite, p.observation_utc) for p in passes.itertuples()]
passes["ground_utc"] = passes.observation_utc + pd.to_timedelta(passes.minutes_to_ground, unit="min")
passes = passes.sort_values(["event", "observation_utc"])
passes.to_csv(OUT / "s1_passes.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")

# ---- 2. validation against S0 ----
s0_first = pd.read_csv(S0 / "s0_first_detection.csv", parse_dates=["first_detection_utc"])
s0_first = s0_first[s0_first.source.isin(["FIRMS VIIRS + MODIS", "Sentinel-3 SLSTR"])]   # the S1 satellites, no GEO
s0_first = s0_first.sort_values("first_detection_utc").groupby("event").first()   # earliest of the two sources
SOURCE_SATS = {"FIRMS VIIRS + MODIS": ["Suomi NPP", "NOAA-20", "NOAA-21", "Terra", "Aqua"],
               "Sentinel-3 SLSTR": ["Sentinel-3A", "Sentinel-3B"]}
det = pd.read_csv(S0 / "candidate_detections.csv", parse_dates=["obs_time_utc"])
det = det[det.candidate_id.isin(events.event) & det.kept]
det["satellite"] = det.platform.replace({"Suomi-NPP": "Suomi NPP"})
s0_passes = det[["candidate_id", "satellite", "obs_time_utc"]].drop_duplicates()

rows = []
for ev in events.itertuples():
    sim = passes[passes.event == ev.event]
    real = s0_passes[s0_passes.candidate_id == ev.event]
    matched = sum(((sim.satellite == r.satellite)
                   & ((sim.observation_utc - r.obs_time_utc).abs() <= pd.Timedelta(minutes=MATCH_MIN))).any()
                  for r in real.itertuples())
    after = sim[sim.hours_from_reference >= -1].iloc[0]              # first opportunity, from reference - 1 h
    s0 = s0_first.loc[ev.event, "first_detection_utc"]
    best = sim[sim.hours_from_reference >= 0].sort_values("ground_utc").iloc[0]  # answer: earliest data on ground
    # ground time of the S0 first pixel: the simulated pass of the same source closest in time, with its wait
    same = sim[sim.satellite.isin(SOURCE_SATS[s0_first.loc[ev.event, "source"]])]
    s0_pass = same.loc[(same.observation_utc - s0).abs().idxmin()]
    rows.append(dict(event=ev.event, s0_passes=len(real), s0_passes_matched=matched,
                     s0_first_detection_utc=s0, s1_first_observation_utc=after.observation_utc,
                     s1_first_satellite=after.satellite, s1_first_at_or_before_s0=after.observation_utc <= s0,
                     s1_first_ground_utc=after.ground_utc, s1_minutes_to_ground=after.minutes_to_ground,
                     best_satellite=best.satellite, best_observation_utc=best.observation_utc,
                     best_ground_utc=best.ground_utc, s0_satellite=s0_pass.satellite,
                     s0_ground_utc=s0 + pd.Timedelta(minutes=s0_pass.minutes_to_ground)))
val = pd.DataFrame(rows)
val.to_csv(OUT / "s1_validation.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
print(val.to_string(index=False))
