"""S1: acceptance checks of the raw simulator run, against the specification and the previous run.

Run right after a new simulator run, before the post-processing (checks S1.1 to S1.12 of
data/simulator/inputs/POSTPROCESSING_CHECKS_S1_S2.md). The previous run (config/simulation.yaml, s1_previous_run_dir)
is the regression reference: same TLEs and step, so positions and the contacts of its stations must be identical.

Inputs:  the run (paths.SIM_RUN) and the previous run (paths.SIM_RUN_PREVIOUS): files 01, 02, 06, 11;
         simulator inputs (stations.csv); extra_access_windows.csv of the previous run's post-processing, if present
Output:  run_checks.csv   one row per check: id, check, value, rule, passed
Usage:   python pipeline/5_simulation/s1/09_run_checks.py
"""
import numpy as np
import pandas as pd

from wildfire_central_node_placement.paths import S1_TABLES, SIM_INPUTS, SIM_RUN, SIM_RUN_PREVIOUS, ensure
from wildfire_central_node_placement.registry import load_registry

NEW, OLD = SIM_RUN, SIM_RUN_PREVIOUS
STEP = pd.Timedelta("60s")
RUN_END = pd.Timestamp("2025-08-17T06:00:00Z")                 # window end + 6 h of ground contacts
WINDOW_END = pd.Timestamp(load_registry()["data_window"]["end_utc"])
ALT_KM = {"AQUA": (688, 724), "TERRA": (688, 724), "NPP": (825, 860), "NOAA 20": (825, 860), "NOAA 21": (825, 860),
          "SENTINEL 3A": (802, 835), "SENTINEL 3B": (802, 835)}
PERIOD_MIN = {"AQUA": 98.55, "TERRA": 98.55, "NPP": 101.44, "NOAA 20": 101.44, "NOAA 21": 101.44,
              "SENTINEL 3A": 100.93, "SENTINEL 3B": 100.93}
STATE_COLS = ["time_utc", "satellite_id", "ecef_x_km", "ecef_y_km", "ecef_z_km", "lat_deg", "lon_deg", "alt_km"]

checks = []


def check(cid, name, value, rule, passed):
    checks.append(dict(id=cid, check=name, value=value, rule=rule, passed=bool(passed)))


def contacts(run):
    a = pd.read_csv(run / "11_access_windows.csv", parse_dates=["rise_utc", "set_utc"])
    a["station"] = a.ground_station_id.map(pd.read_csv(run / "06_ground_stations.csv").set_index("id").name)
    return a


# ---- elements and TLEs ----
el_new, el_old = pd.read_csv(NEW / "01_satellite_elements.csv"), pd.read_csv(OLD / "01_satellite_elements.csv")
m = el_new.merge(el_old, on="satellite_id", suffixes=("", "_old"))
same_tle = (m.tle_line1 == m.tle_line1_old) & (m.tle_line2 == m.tle_line2_old)
epochs = pd.to_datetime(el_new.epoch_iso)
check("S1.1", "TLEs: epoch 16 Aug 2025, same as the previous run",
      f"{same_tle.sum()}/{len(el_new)} same; epochs {epochs.min():%m-%d %H:%M} to {epochs.max():%m-%d %H:%M}",
      "7/7 same, epoch 2025-08-16", len(el_new) == 7 and same_tle.all() and (epochs.dt.strftime("%Y-%m-%d") == "2025-08-16").all())
dp = (el_new.satellite_id.map(PERIOD_MIN) - el_new.period_min).abs()
check("S1.4", "Inclination and period", f"incl {el_new.inclination_deg.min():.2f} to {el_new.inclination_deg.max():.2f} deg; "
      f"max period deviation {dp.max():.2f} min", "97.9 to 98.8 deg; period within 0.1 min",
      el_new.inclination_deg.between(97.9, 98.8).all() and (dp <= 0.1).all())

# ---- states ----
s_new = pd.read_csv(NEW / "02_satellite_states.csv", usecols=STATE_COLS, parse_dates=["time_utc"])
s_old = pd.read_csv(OLD / "02_satellite_states.csv", usecols=STATE_COLS, parse_dates=["time_utc"])
g = s_new.groupby("satellite_id")
n_expected = int((RUN_END - s_new.time_utc.min()) / STEP) + 1
gaps = int((g.time_utc.diff() > STEP).sum())
dups = int(s_new.duplicated(["satellite_id", "time_utc"]).sum())
check("S1.2", "States: one row per minute per satellite to the run end",
      f"{g.size().min()} to {g.size().max()} rows; {s_new.time_utc.min():%m-%d %H:%M} to {s_new.time_utc.max():%m-%d %H:%M}; "
      f"{gaps} gaps, {dups} duplicates", f"{n_expected} rows, 08-08 00:00 to 08-17 06:00, no gap or duplicate",
      (g.size() == n_expected).all() and s_new.time_utc.max() == RUN_END and gaps == 0 and dups == 0)
alt = g.alt_km.agg(["min", "max"])
alt_ok = all(ALT_KM[s][0] <= r["min"] and r["max"] <= ALT_KM[s][1] for s, r in alt.iterrows())
check("S1.3", "Altitude per satellite", "; ".join(f"{s} {r['min']:.0f}-{r['max']:.0f}" for s, r in alt.iterrows()),
      "MODIS 688-724, VIIRS 825-860, SLSTR 802-835 km", alt_ok)
lon = np.degrees(np.arctan2(s_new.ecef_y_km, s_new.ecef_x_km))
dlon = ((lon - s_new.lon_deg + 180) % 360 - 180).abs().max()
check("S1.5", "Longitude from ECEF against lon_deg", f"max {dlon:.4f} deg", "<= 0.01 deg", dlon <= 0.01)
j = s_new.merge(s_old, on=["satellite_id", "time_utc"], suffixes=("", "_old"))
d = np.sqrt(sum((j[f"ecef_{a}_km"] - j[f"ecef_{a}_km_old"]) ** 2 for a in "xyz"))
check("S1.6", "Positions against the previous run", f"{len(j)} of {len(s_old)} rows compared; max {d.max():.4f} km",
      "every previous row present, < 0.1 km", len(j) == len(s_old) and d.max() < 0.1)

# ---- stations and contacts ----
st = pd.read_csv(NEW / "06_ground_stations.csv")
spec = pd.read_csv(SIM_INPUTS / "stations.csv")
ms = spec.merge(st, left_on="station", right_on="name", how="left")
coord_ok = ms.lat_deg.notna().all() and ((ms.lat - ms.lat_deg).abs().max() <= 0.01) and ((ms.lon - ms.lon_deg).abs().max() <= 0.01)
check("S1.3b", "Stations: names and coordinates as specified", f"{len(st)} in the run, {ms.lat_deg.notna().sum()}/{len(spec)} matched",
      f"{len(spec)} stations, +/-0.01 deg", len(st) == len(spec) and coord_ok)
a_new, a_old = contacts(NEW), contacts(OLD)
pairs = a_new.groupby(["satellite_id", "station"]).size()
check("S1.7", "Contacts for every satellite-station pair", f"{len(pairs)} pairs, min {pairs.min()} contacts",
      f"{7 * len(st)} pairs, each >= 1", len(pairs) == 7 * len(st) and pairs.min() >= 1)
polar = pairs.loc[:, ["Svalbard (SvalSat)", "McMurdo"]]
check("S1.8", "Contacts per satellite at Svalbard and McMurdo", f"{polar.min()} to {polar.max()}", "103 to 118",
      polar.between(103, 118).all())
key = ["satellite_id", "station", "rise_utc"]
a = a_new[a_new.station.isin(a_old.station) & (a_new.set_utc < WINDOW_END)].sort_values(key).reset_index(drop=True)
b = a_old[a_old.set_utc < WINDOW_END].sort_values(key).reset_index(drop=True)
same_n = len(a) == len(b)
drift = max((a.rise_utc - b.rise_utc).dt.total_seconds().abs().max(),
            (a.set_utc - b.set_utc).dt.total_seconds().abs().max()) if same_n else np.nan
check("S1.9", "Contacts of the previous run's stations, before the window end",
      f"{len(a)} windows (previous {len(b)}); max difference {drift:.1f} s", "same windows, +/-1 s", same_n and drift <= 1)
extra_file = S1_TABLES / "extra_access_windows.csv"
if extra_file.exists() and extra_file.stat().st_size > 0 and len(pd.read_csv(extra_file)):
    ex = pd.read_csv(extra_file, parse_dates=["rise_utc", "set_utc"]).rename(columns={"ground_station_name": "station"})
    new9 = a_new[a_new.station.isin(ex.station.unique())].rename(columns={"rise_utc": "rise_n", "set_utc": "set_n"})
    mm = pd.merge_asof(ex.sort_values("rise_utc"), new9.sort_values("rise_n")[["satellite_id", "station", "rise_n", "set_n"]],
                       left_on="rise_utc", right_on="rise_n", by=["satellite_id", "station"], direction="nearest")
    inside = mm.set_utc < WINDOW_END                       # windows the previous file cut at the window end are skipped
    dr = (mm.rise_utc - mm.rise_n).dt.total_seconds().abs()[inside]
    ds = (mm.set_utc - mm.set_n).dt.total_seconds().abs()[inside]
    check("S1.10", "Contacts of the added stations against the previous 60 s file",
          f"{mm.rise_n.notna().sum()}/{len(mm)} matched; max |rise| {dr.max():.0f} s, |set| {ds.max():.0f} s",
          "all matched, within 65 s (60 s sampling + own elevation model)",
          mm.rise_n.notna().all() and dr.max() <= 65 and ds.max() <= 65)
else:
    check("S1.10", "Contacts of the added stations against the previous 60 s file", "no previous file", "skipped", True)
dur_err = ((a_new.set_utc - a_new.rise_utc).dt.total_seconds() - a_new.duration_s).abs().max()
overlaps = sum(int((w.rise_utc.values[1:] < w.set_utc.values[:-1]).sum())
               for _, w in a_new.sort_values("rise_utc").groupby(["satellite_id", "station"]))
check("S1.11", "Contact windows: durations, elevations, overlaps",
      f"duration {a_new.duration_s.min():.0f}-{a_new.duration_s.max():.0f} s; elevation {a_new.max_elevation_deg.min():.1f}-"
      f"{a_new.max_elevation_deg.max():.1f} deg; duration error {dur_err:.3f} s; {overlaps} overlaps",
      "0 < duration <= 900 s, elevation 10-90, error <= 1 s, no overlap",
      a_new.duration_s.gt(0).all() and a_new.duration_s.le(900).all() and a_new.max_elevation_deg.between(10, 90).all()
      and dur_err <= 1 and overlaps == 0)
check("S1.12", "Contacts after the window end", f"last set {a_new.set_utc.max():%m-%d %H:%M}; "
      f"{int((a_new.set_utc > WINDOW_END).sum())} windows end after the window", "last set at the run end",
      a_new.set_utc.max() == RUN_END)

out = pd.DataFrame(checks).sort_values("id", key=lambda c: c.str.replace("S1.", "").str.replace("b", ".5").astype(float))
out.to_csv(ensure(S1_TABLES) / "run_checks.csv", index=False)
print(out.to_string(index=False))
print(f"\n{out.passed.sum()}/{len(out)} passed; run {NEW.name}, previous {OLD.name}")
