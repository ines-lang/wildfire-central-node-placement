"""Step 5: input files for the S1 run of the network simulator.

Writes into the simulator input folder (paths.SIM_INPUTS):
    s1_tle.txt          three-line TLEs of the seven S1 satellites as used by the simulator run (Space-Track, 16 Aug 2025)
    s1_sensors.csv      satellite, NORAD id, instrument, swath half-width, direct broadcast, stored-data stations
    stations.csv        every ground station any station set may need (superset), with coordinates, link type,
                        the satellites it serves and the station sets it belongs to
    events.csv          the seven S1 events (registry, selected): location and reference time
    study_window.csv    start and end of the simulation, elevation mask, time step
The prompt for the simulator (S1_SIMULATOR_PROMPT.md, same folder) describes these files; it is written by hand.

Inputs: eo_census.csv, ground_stations.csv, the candidates' ground truth, the registry (events, data window)
Usage: python pipeline/5_simulation/s1/00_simulator_inputs.py
"""
import pandas as pd

from wildfire_central_node_placement.orbits import HALF_SWATH_KM, MIN_ELEVATION_DEG
from wildfire_central_node_placement.paths import GROUND_STATIONS_FILE, SIM_INPUTS, SIM_RUN, SPACE_TABLES, ensure
from wildfire_central_node_placement.registry import ground_truth, load_registry, selected_events
from wildfire_central_node_placement.s1 import SAT

OUT = SIM_INPUTS

# ---- parameters ----
EVENTS = selected_events()       # Mount Underwood dropped (8 Nov 2026)
DIRECT_BROADCAST = {"Suomi NPP": True, "NOAA-20": True, "NOAA-21": True, "Terra": False, "Aqua": True,
                    "Sentinel-3A": False, "Sentinel-3B": False}                   # SLSTR has none; Terra direct broadcast off since 11 May 2024 (NASA via SSEC forum, Nov 2024)
STEP_S = 30
SET_LABEL = {"month2": "month2", "real + direct readout": "frozen_baseline", "real": "real_no_direct_readout"}

ensure(OUT)
reg = load_registry()

# ---- satellites ----
# The simulator does not accept user TLEs: it fetches the Space-Track TLE of the closest day to 16 Aug 2025 itself.
# The TLE file and the epochs therefore record the TLEs of the run (01_satellite_elements.csv), not those of the census.
census = pd.read_csv(SPACE_TABLES / "eo_census.csv")
s1 = census[census.role == "S1 EO layer"].sort_values("mission")
run_el = pd.read_csv(SIM_RUN / "01_satellite_elements.csv")
run_el["mission"] = run_el.satellite_id.map(SAT)
run_el = run_el.set_index("mission").loc[s1.mission]
s1 = s1.assign(line1=run_el.tle_line1.values, line2=run_el.tle_line2.values,
               epoch_utc=pd.to_datetime(run_el.epoch_iso.values).strftime("%Y-%m-%dT%H:%M:%SZ"))
with open(OUT / "s1_tle.txt", "w") as f:
    for r in s1.itertuples():
        f.write(f"{r.mission}\n{r.line1}\n{r.line2}\n")
st = pd.read_csv(GROUND_STATIONS_FILE)
real = st[st.station_set == "real"]
sensors = pd.DataFrame({
    "satellite": s1.mission, "norad_id": s1.norad_id, "instrument": s1.instrument,
    "tle_epoch_utc": s1.epoch_utc, "half_swath_km": s1.instrument.map(HALF_SWATH_KM),
    "direct_broadcast": s1.mission.map(DIRECT_BROADCAST),
    "stored_data_downlink": [";".join(real[real.satellites.str.split(";").apply(lambda s, m=m: m in s)
                                           & real.link.isin(["stored", "relay"])].station) for m in s1.mission]})
sensors.to_csv(OUT / "s1_sensors.csv", index=False)

# ---- stations: one row per physical station, with every set it belongs to ----
geo = st[st.link != "relay"]
rows = []
s1_names = set(s1.mission)
for name, g in geo.groupby("station", sort=False):
    # a station belongs to a set only if it serves an S1 satellite there ("all" in the Month 2 set);
    # stations that serve only FY-3D belong to the S3 sensitivity case, not to the frozen baseline
    serves_s1 = g.satellites.apply(lambda v: v == "all" or bool(set(v.split(";")) & s1_names))
    sets = sorted({SET_LABEL[s] for s in g[serves_s1].station_set}
                  | ({"s3_sensitivity_fy3d"} if "FY-3D" in ";".join(g.satellites) else set()))
    sats = sorted({s for v in g.satellites for s in v.split(";")} - {"all"})
    rows.append(dict(station=name, lat=g.lat.iloc[0], lon=g.lon.iloc[0], altitude_m=0,
                     link=g[g.station_set != "month2"].link.iloc[0] if (g.station_set != "month2").any() else "stored",
                     serves_in_real_sets=";".join(sats) if sats else "none (Month 2 set only)",
                     station_sets=";".join(sets), coordinates_level=g.level.iloc[-1], source=g.source.iloc[-1]))
stations = pd.DataFrame(rows)
stations.to_csv(OUT / "stations.csv", index=False)

# ---- events and window ----
gt = ground_truth()
ev = gt.loc[EVENTS, ["name", "lat", "lon", "ignition_utc", "ignition_kind"]].rename(
    columns={"ignition_utc": "reference_utc", "ignition_kind": "reference_kind"})
ev.index.name = "event"
ev.to_csv(OUT / "events.csv")
w = reg["data_window"]
pd.DataFrame([dict(start_utc=w["start_utc"], end_utc=w["end_utc"], firms_data_end_utc=w["firms_data_end_utc"],
                   min_elevation_deg=MIN_ELEVATION_DEG, max_time_step_s=STEP_S)]).to_csv(OUT / "study_window.csv",
                                                                                      index=False)
print(f"{len(s1)} satellites, {len(stations)} stations, {len(ev)} events written to {OUT}")
print(stations[["station", "link", "station_sets"]].to_string(index=False))
