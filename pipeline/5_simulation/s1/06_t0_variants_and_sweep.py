"""S1 under the T0 rule of 13 Nov 2026, its sensitivity variants, and the ignition-independent sweep.

T0 variants per event (T0 rule: wildfire_central_node_placement.s0.t0_rule, pipeline/4_events/11_t0_rule.py):
  public   main: first robust public satellite detection of the event's main episode (no press, no window)
  human    the official or press time (reference_times_crosscheck.csv); used before 13 Nov 2026
  geo      first robust geostationary detection (SEVIRI / GOES) of the main episode: independent of the S1 satellites
For each variant: the S1 pass at or after T0 whose data reach a station of the frozen ground segment first
(passes from s1_passes.csv, with their time to ground). A 2 min tolerance keeps the pass that set T0.

Sweep: ignition (or 'first detectable') time t every SWEEP_STEP_MIN over the data window; for each t the time from t to
the first S1 data on the ground. Independent of any reported time; gives the distribution per location.

Inputs:  s1_passes.csv, t0_events.csv (4_events/11_t0_rule.py) and the T0 rule's detections
Outputs: s1_t0_variants.csv, s1_sweep.csv (per event: median, p90, max), s1_sweep.png
Usage:   python pipeline/5_simulation/s1/06_t0_variants_and_sweep.py
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from wildfire_central_node_placement.paths import EVENTS_TABLES, S1_FIGURES, S1_TABLES, ensure
from wildfire_central_node_placement.registry import selected_events
from wildfire_central_node_placement.s0 import t0_rule
from wildfire_central_node_placement.s1 import EVENT_NAMES as NAMES

TOL = pd.Timedelta(minutes=2)
SWEEP_START, SWEEP_END = pd.Timestamp("2025-08-09T00:00Z"), pd.Timestamp("2025-08-15T00:00Z")
SWEEP_STEP_MIN = 5
EVENTS = selected_events()

passes = pd.read_csv(S1_TABLES / "s1_passes.csv", parse_dates=["observation_utc", "ground_utc"])
t0 = pd.read_csv(EVENTS_TABLES / "t0_events.csv", parse_dates=["t0_utc", "human_time_utc"]).set_index("event")
det, _, _ = t0_rule()
geo = det[det.geo & det.robust].copy()
geo["episode_start"] = geo.event.map(t0.main_episode_start.pipe(pd.to_datetime))
t0["geo_utc"] = geo[geo.time_utc >= geo.episode_start].groupby("event").time_utc.min()


def best_after(ev, start):
    p = passes[(passes.event == ev) & (passes.observation_utc >= start - TOL)]
    b = p.loc[p.ground_utc.idxmin()]
    return b.satellite, b.observation_utc, b.ground_utc


rows = []
for ev in EVENTS:
    for variant, col in [("public", "t0_utc"), ("human", "human_time_utc"), ("geo", "geo_utc")]:
        start = t0.loc[ev, col]
        if pd.isna(start):
            continue
        sat, obs, ground = best_after(ev, start)
        rows.append(dict(event=ev, variant=variant, t0_utc=start, satellite=sat, observation_utc=obs, ground_utc=ground,
                         image_after_t0_h=round((obs - start).total_seconds() / 3600, 2),
                         ground_after_t0_h=round((ground - start).total_seconds() / 3600, 2)))
var = pd.DataFrame(rows)
var.to_csv(S1_TABLES / "s1_t0_variants.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")

sweep = []
times = pd.date_range(SWEEP_START, SWEEP_END, freq=f"{SWEEP_STEP_MIN}min")
for ev in EVENTS:
    p = passes[passes.event == ev].sort_values("observation_utc")
    obs = p.observation_utc.values
    ground = p.ground_utc.fillna(pd.Timestamp("2100-01-01", tz="UTC")).values   # no contact before the run end = never
    # earliest ground time among passes observed at or after t (suffix minimum)
    suffix_min = np.minimum.accumulate(ground[::-1])[::-1]
    idx = np.searchsorted(obs, times.values)
    ok = idx < len(obs)
    wait_h = (suffix_min[idx[ok]] - times.values[ok]) / np.timedelta64(1, "h")
    sweep.append(pd.DataFrame({"event": ev, "t_utc": times[ok], "ground_after_h": wait_h}))
sweep = pd.concat(sweep)
stats = sweep.groupby("event").ground_after_h.describe(percentiles=[0.5, 0.9])[["50%", "90%", "max"]].round(2)
stats.columns = ["median_h", "p90_h", "max_h"]
stats.to_csv(S1_TABLES / "s1_sweep.csv")

fig, ax = plt.subplots(figsize=(8, 3.6))
order = stats.sort_values("median_h").index
ax.boxplot([sweep[sweep.event == e].ground_after_h for e in order], vert=False, whis=(0, 100), widths=0.55,
           medianprops=dict(color="#d9480f", lw=2), boxprops=dict(color="#16263d"), whiskerprops=dict(color="#16263d"),
           capprops=dict(color="#16263d"), showfliers=False)
ax.set_yticks(range(1, len(order) + 1), [NAMES[e] for e in order])
pub = var[var.variant == "public"].set_index("event")
ax.scatter([pub.loc[e, "ground_after_t0_h"] for e in order], range(1, len(order) + 1), marker="D", color="black", zorder=5,
           label="real fire, T0 = first public detection")
ax.set_xlabel("hours from the start time to the first S1 data on the ground")
ax.set_title("S1 at the event locations: every start time in 9 to 14 Aug 2025 (box: quartiles, whiskers: range)",
             loc="left", fontsize=9)
ax.legend(loc="center right", fontsize=8, framealpha=0.95)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(ensure(S1_FIGURES) / "s1_sweep.png", dpi=200)

pd.set_option("display.width", 220)
print(var.pivot(index="event", columns="variant", values="ground_after_t0_h").to_string())
print(var[var.variant == "public"][["event", "t0_utc", "satellite", "image_after_t0_h", "ground_after_t0_h"]].to_string(index=False))
print("\nsweep:\n" + stats.to_string())
