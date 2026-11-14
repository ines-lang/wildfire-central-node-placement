"""Contact windows for frozen-baseline stations that were added after the simulator run (10 Nov 2026).

The run computed contacts only for its 13 stations. Stations added to the frozen baseline later (direct-readout
stations that feed a public near-real-time fire product: Alice Springs, Hartebeesthoek, Cuiaba, Cachoeira Paulista)
get their contacts here from the exported satellite positions (ECEF, every 60 s), with the run's 10 deg elevation
mask. Same columns as the run's 11_access_windows.csv; rise and set are the first and last sample above the mask
(60 s resolution, so up to 1 min later / earlier than the run's interpolated times).

Any other station list can be post-processed the same way (event-agnostic candidates, sensitivity sets):
    --stations <csv with columns station, lat, lon[, category]>   --out <file name in the S1 tables folder>
    (the research set: --stations <config>/ground_stations_research.csv --out research_access_windows.csv)
Without arguments: the frozen-baseline stations of ground_stations.csv that are not in the run.

Output: extra_access_windows.csv (station names in column ground_station_name)
Usage:  python pipeline/5_simulation/s1/04_extra_station_contacts.py [--stations FILE --out NAME]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from wildfire_central_node_placement.geo import station_ecef
from wildfire_central_node_placement.orbits import MIN_ELEVATION_DEG
from wildfire_central_node_placement.paths import GROUND_STATIONS_FILE, S1_TABLES, SIM_RUN, ensure

RUN = SIM_RUN
STATIONS = GROUND_STATIONS_FILE
GAP = pd.Timedelta("5min")

ap = argparse.ArgumentParser()
ap.add_argument("--stations", type=Path)
ap.add_argument("--out", default="extra_access_windows.csv")
args = ap.parse_args()
run_names = set(pd.read_csv(RUN / "06_ground_stations.csv").name)
if args.stations:
    st = pd.read_csv(args.stations).dropna(subset=["lat", "lon"]).drop_duplicates("station")
else:
    st = pd.read_csv(STATIONS)
    st = st[(st.station_set == "real + direct readout") & st.lat.notna() & ~st.station.isin(run_names)]
states = pd.read_csv(RUN / "02_satellite_states.csv", usecols=["time_utc", "satellite_id", "ecef_x_km", "ecef_y_km", "ecef_z_km"],
                     parse_dates=["time_utc"])
sat_xyz = states[["ecef_x_km", "ecef_y_km", "ecef_z_km"]].to_numpy()


rows = []
for s in st.itertuples():
    xyz, up = station_ecef(s.lat, s.lon)
    d = sat_xyz - xyz
    elev = np.degrees(np.arcsin((d @ up) / np.linalg.norm(d, axis=1)))
    vis = states.assign(elev=elev)[elev >= MIN_ELEVATION_DEG]
    for sat, g in vis.groupby("satellite_id"):
        for _, w in g.groupby((g.time_utc.diff() > GAP).cumsum()):
            rows.append(dict(ground_station_name=s.station, satellite_id=sat, rise_utc=w.time_utc.min(), set_utc=w.time_utc.max(),
                             duration_s=(w.time_utc.max() - w.time_utc.min()).total_seconds(), max_elevation_deg=w.elev.max()))
out = pd.DataFrame(rows)
out.to_csv(ensure(S1_TABLES) / args.out, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
print(out.groupby(["ground_station_name", "satellite_id"]).size().unstack(fill_value=0).to_string())
