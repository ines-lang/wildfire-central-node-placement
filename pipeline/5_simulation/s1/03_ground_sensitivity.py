"""S1: are the results sensitive to ground stations that the satellites use in reality but the baseline does not model?

The run computes the contacts with all 13 stations, so every case is a post-processing change of the station
list of the frozen baseline (wildfire_central_node_placement.s1.S1Run, as 01_s1_latency.py; no new run). Cases:
    jpss_backups     NOAA-20/21 (and Suomi NPP) also use Fairbanks (FCDAS) and Troll: JPSS backup stations
                     (Kilcoyne 2019, NTRS 20190030867; NOAA OSPO message of 17 January 2025)
    snpp_mcmurdo     Suomi NPP also at McMurdo. Not real: NOAA states Suomi NPP downlinks only at Svalbard (NESDIS 2017)
    s3_any_polar     Sentinel-3 at any polar station of the run (a supplier lists Inuvik and Matera; ESA and EUMETSAT
                     name only Svalbard)
    firms_rt         Red Canyon: the FIRMS real-time stations Monterey and Honolulu (NASA Earthdata 2022) receive a
                     direct-broadcast pass if they see the satellite (elevation >= 10 deg) at the observation time.
                     Their data arrive after the pass, i.e. a few minutes; counted as 0 min here.
Outputs: ground_sensitivity_satellites.csv  median and maximum wait per satellite and case
         ground_sensitivity_events.csv      S1 answer and S0 data on ground (h after reference) per event
Usage:   python pipeline/5_simulation/s1/03_ground_sensitivity.py   (after 01_s1_latency.py)
"""
import numpy as np
import pandas as pd

from wildfire_central_node_placement.geo import haversine_km as distance_km
from wildfire_central_node_placement.paths import S1_TABLES
from wildfire_central_node_placement.s1 import S1Run

run = S1Run()

POLAR = "Svalbard (SvalSat);McMurdo;Fairbanks (FCDAS);Troll (TrollSat);Poker Flat;Kiruna (Esrange)"
JPSS = ["Suomi NPP", "NOAA-20", "NOAA-21"]
RT_STATIONS = {"Monterey": (36.6, -121.9), "Honolulu": (21.3, -157.8)}
ALTITUDE_KM = {"Terra": 705, "Aqua": 705}                       # JPSS about 830 km
EARTH_RADIUS_KM = 6371.0

passes = pd.read_csv(S1_TABLES / "s1_passes.csv", parse_dates=["observation_utc"])
val = pd.read_csv(S1_TABLES / "s1_validation.csv", parse_dates=["s0_first_detection_utc"]).set_index("event")
reference = run.events.set_index("event").reference_utc
sensors, states = run.sensors, run.states
base = sensors.stored_data_downlink.copy(deep=True)


def waits(override):
    sensors["stored_data_downlink"] = base.copy(deep=True)
    for sat, stations in override.items():
        sensors.loc[sat, "stored_data_downlink"] = stations
    w = np.array([run.minutes_to_ground(p.satellite, p.observation_utc) for p in passes.itertuples()])
    sensors["stored_data_downlink"] = base.copy(deep=True)
    return w


def elevation_deg(sat_lat, sat_lon, st_lat, st_lon, altitude_km):
    c = distance_km(sat_lat, sat_lon, st_lat, st_lon) / EARTH_RADIUS_KM
    return np.degrees(np.arctan2(np.cos(c) - EARTH_RADIUS_KM / (EARTH_RADIUS_KM + altitude_km), np.sin(c)))


def with_firms_rt(w):
    w = w.copy()
    for i, p in passes.iterrows():
        if p.event != "red_canyon" or not sensors.loc[p.satellite, "direct_broadcast"]:
            continue
        s = states[(states.satellite == p.satellite) & (states.time_utc == p.observation_utc)]
        if not s.empty and any(elevation_deg(s.lat_deg.iloc[0], s.lon_deg.iloc[0], la, lo,
                                             ALTITUDE_KM.get(p.satellite, 830)) >= 10
                               for la, lo in RT_STATIONS.values()):
            w[i] = 0
    return w


baseline = waits({})
cases = {"baseline": baseline,
         "jpss_backups": waits({s: base[s] + ";Fairbanks (FCDAS);Troll (TrollSat)" for s in JPSS}),
         "snpp_mcmurdo": waits({"Suomi NPP": "Svalbard (SvalSat);McMurdo"}),
         "s3_any_polar": waits({"Sentinel-3A": POLAR, "Sentinel-3B": POLAR}),
         "firms_rt": with_firms_rt(baseline)}

sat_rows, ev_rows = [], []
for name, w in cases.items():
    p = passes.assign(wait=w, ground=passes.observation_utc + pd.to_timedelta(w, unit="min"))
    for sat, q in p.groupby("satellite"):
        sat_rows.append(dict(case=name, satellite=sat, median_min=round(q.wait.median(), 1), max_min=round(q.wait.max(), 1)))
    for ev in val.index:
        q = p[p.event == ev]
        s0_img = val.loc[ev, "s0_first_detection_utc"]
        s0_pass = q.iloc[(q.observation_utc - s0_img).abs().argmin()]       # same rule as 01_s1_latency.py
        h = lambda t: round((t - reference[ev]).total_seconds() / 3600, 2)
        ev_rows.append(dict(case=name, event=ev, s1_answer_h=h(q[q.hours_from_reference >= 0].ground.min()),
                            s0_on_ground_h=h(s0_img + pd.Timedelta(minutes=s0_pass.wait))))

sat_df, ev_df = pd.DataFrame(sat_rows), pd.DataFrame(ev_rows)
sat_df.to_csv(S1_TABLES / "ground_sensitivity_satellites.csv", index=False)
ev_df.to_csv(S1_TABLES / "ground_sensitivity_events.csv", index=False)
print(sat_df.pivot(index="satellite", columns="case", values=["median_min", "max_min"]).to_string())
print()
print(ev_df.assign(v=ev_df.s1_answer_h.astype(str) + " / " + ev_df.s0_on_ground_h.astype(str))
      .pivot(index="event", columns="case", values="v").to_string())
