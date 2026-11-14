"""Event-agnostic ground segment from the station research of 10 Nov 2026: effect on S1, in post-processing.

Stations: ground_stations_research.csv (48 stations; category, satellites that really use each one,
level of evidence). Contacts: research_access_windows.csv (04_extra_station_contacts.py --stations ...).
Two station sets, same rules as the frozen baseline (01_s1_latency.py):
  current   the frozen baseline of Month 3 (stored: Svalbard, McMurdo, Poker Flat; direct: the 3 US URT stations
            and the 4 southern stations added on 10 Nov)
  proposed  every station the research puts in the event-agnostic baseline: stored-data stations the satellite really
            uses, and direct-readout stations that feed a public near-real-time fire product (PROPOSED below)
Wait from observation t: 0 if a direct-readout station serving the satellite sees it at t; else until the first rise
of a stored-data station serving the satellite; Terra a fixed 25 min (TDRSS, no direct broadcast since May 2024).

Output: station_baseline_research.csv (per event: best time to ground in both sets)
Usage:  python pipeline/5_simulation/s1/05_station_baseline_research.py
"""
import numpy as np
import pandas as pd

from wildfire_central_node_placement.orbits import TERRA_RELAY_WAIT_MIN as TERRA_RELAY_MIN
from wildfire_central_node_placement.paths import GROUND_STATIONS_RESEARCH_FILE, S1_TABLES, SIM_INPUTS
from wildfire_central_node_placement.s1 import SAT

RES = pd.read_csv(GROUND_STATIONS_RESEARCH_FILE)
CONTACTS = pd.read_csv(S1_TABLES / "research_access_windows.csv", parse_dates=["rise_utc", "set_utc"])
PASSES = pd.read_csv(S1_TABLES / "s1_passes.csv", parse_dates=["observation_utc"])
EVENTS = pd.read_csv(SIM_INPUTS / "events.csv", parse_dates=["reference_utc"]).set_index("event")

DIRECT_PROPOSED = ["Madison WI (SSEC, 2 antennas)", "Hampton VA", "Mayaguez PR (UPRM)", "Monterey CA", "Honolulu HI (Univ. Hawaii)",
                   "Fairbanks AK (UAF GINA/ASF antennas)", "Alice Springs (Geoscience Australia)",
                   "Perth (Landgate, Murdoch X/L-band antenna)", "Cuiaba (INPE)", "Cachoeira Paulista (INPE)",
                   "Shadnagar (NRSC/ISRO)", "Parepare (BRIN)"]
STORED_PROPOSED = ["Svalbard (SvalSat, KSAT)", "McMurdo (NOAA MGS)", "Fairbanks (NOAA FCDAS, Gilmore Creek)",
                   "Poker Flat / Alaska (NASA EOS polar ground station)"]
DIRECT_CURRENT = ["Madison WI (SSEC, 2 antennas)", "Hampton VA", "Mayaguez PR (UPRM)", "Alice Springs (Geoscience Australia)",
                  "Hartebeesthoek (SANSA)", "Cuiaba (INPE)", "Cachoeira Paulista (INPE)"]
STORED_CURRENT = {"Suomi NPP": ["Svalbard (SvalSat, KSAT)"], "NOAA-20": ["Svalbard (SvalSat, KSAT)", "McMurdo (NOAA MGS)"],
                  "NOAA-21": ["Svalbard (SvalSat, KSAT)", "McMurdo (NOAA MGS)"],
                  "Aqua": ["Svalbard (SvalSat, KSAT)", "Poker Flat / Alaska (NASA EOS polar ground station)"],
                  "Sentinel-3A": ["Svalbard (SvalSat, KSAT)"], "Sentinel-3B": ["Svalbard (SvalSat, KSAT)"]}

serves = {r.station: set(str(r.satellites).split(";")) for r in RES.itertuples()}
CONTACTS["satellite"] = CONTACTS.satellite_id.map(SAT)
CONTACTS = CONTACTS.rename(columns={"ground_station_name": "station"})
DR_SATS = {"Suomi NPP", "NOAA-20", "NOAA-21", "Aqua"}          # direct-readout satellites of the frozen baseline
CURRENT_SETS = ({s: (DIRECT_CURRENT if s in DR_SATS else []) for s in SAT.values()}, STORED_CURRENT)
PROPOSED_SETS = ({s: [d for d in DIRECT_PROPOSED if s in serves[d]] for s in SAT.values()},
                 {s: [d for d in STORED_PROPOSED if s in serves[d]] for s in SAT.values()})


def wait_min(sat, t, sets):
    if sat == "Terra":
        return TERRA_RELAY_MIN
    direct, stored = sets[0].get(sat, []), sets[1].get(sat, [])
    c = CONTACTS[(CONTACTS.satellite == sat) & (CONTACTS.set_utc >= t)]
    if ((c.station.isin(direct)) & (c.rise_utc <= t)).any():
        return 0.0
    s = c[c.station.isin(stored)]
    return np.nan if s.empty else max(0.0, (s.rise_utc.min() - t).total_seconds() / 60)


p = PASSES.copy()
for name, sets in [("current", CURRENT_SETS), ("proposed", PROPOSED_SETS)]:
    p[f"wait_{name}"] = [wait_min(r.satellite, r.observation_utc, sets) for r in p.itertuples()]
    p[f"ground_{name}"] = p.observation_utc + pd.to_timedelta(p[f"wait_{name}"], unit="min")
rows = []
for ev, g in p.groupby("event"):
    ref = EVENTS.loc[ev, "reference_utc"]
    g = g[g.observation_utc >= ref]
    row = {"event": ev}
    for name in ["current", "proposed"]:
        b = g.loc[g[f"ground_{name}"].idxmin()]
        row |= {f"{name}_satellite": b.satellite, f"{name}_image_h": round((b.observation_utc - ref).total_seconds() / 3600, 2),
                f"{name}_wait_min": round(b[f"wait_{name}"], 1), f"{name}_ground_h": round((b[f"ground_{name}"] - ref).total_seconds() / 3600, 2)}
    rows.append(row)
out = pd.DataFrame(rows)
out.to_csv(S1_TABLES / "station_baseline_research.csv", index=False)
pd.set_option("display.width", 250)
print(out.to_string(index=False))
print("\nmedian wait per satellite (all passes), current -> proposed")
print(p.groupby("satellite")[["wait_current", "wait_proposed"]].median().round(1).to_string())
