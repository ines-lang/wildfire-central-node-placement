"""S1 figures, from s1_passes.csv and s1_validation.csv.

    s1_first_detection.png   per event: S1 data on ground (pass + station wait) and S0 data on ground (hours from reference)
    s1_time_to_ground.png    median time to ground per satellite, frozen baseline
Usage: python pipeline/5_simulation/s1/02_figures.py
"""
import matplotlib.pyplot as plt
import pandas as pd

from wildfire_central_node_placement.paths import S1_FIGURES, S1_TABLES, SIM_INPUTS, ensure
from wildfire_central_node_placement.registry import selected_events
from wildfire_central_node_placement.s1 import EVENT_NAMES as NAMES

OUT = ensure(S1_FIGURES)

val = pd.read_csv(S1_TABLES / "s1_validation.csv",
                  parse_dates=["s0_first_detection_utc", "s1_first_observation_utc", "s1_first_ground_utc"])
ref = pd.read_csv(SIM_INPUTS / "events.csv", parse_dates=["reference_utc"]).set_index("event")
val["reference_utc"] = val.event.map(ref.reference_utc)
val = val.set_index("event")
for c in ["best_observation_utc", "best_ground_utc", "s0_ground_utc"]:
    val[c] = pd.to_datetime(val[c])
    val[c + "_h"] = (val[c] - val.reference_utc).dt.total_seconds() / 3600

# ---- figure 1: how fast the data could have been on the ground, per event ----
# figure rows (top to bottom), grouped by case: every selected event, in this layout order
ORDER = ["molezuelas", "oimbra", "derdara", "silifke", "piodao", "red_canyon", "larouco"]
assert sorted(ORDER) == sorted(selected_events()), "figure rows must be the selected events"
v = val.loc[ORDER]
pass_h = v.best_observation_utc_h
ground_h = v.best_ground_utc_h - v.best_observation_utc_h
fig, ax = plt.subplots(figsize=(8, 3.6))
y = range(len(v))
ax.barh(y, pass_h, color="tab:orange", label="waiting for a satellite pass (alert to image)")
ax.barh(y, ground_h, left=pass_h, color="tab:purple", label="waiting for a ground station (image to first contact)")
# hollow, so the end of the S1 bar stays visible where S0 and S1 agree
ax.plot(v.s0_ground_utc_h, y, "D", ms=9, mfc="none", mec="black", mew=1.6, zorder=3,
        label="S0: first public fire pixel, data on ground")
for i, (h, s, x) in enumerate(zip(v.best_ground_utc_h, v.s0_ground_utc_h, v[["best_ground_utc_h", "s0_ground_utc_h"]].max(axis=1))):
    ax.text(x + 0.22, i, f"S1 {h:.1f} h / S0 {s:.1f} h", va="center", fontsize=8)
ax.set_yticks(list(y), v.index.map(NAMES))
ax.invert_yaxis()
ax.set_xlim(0, 9.6)
ax.set_xlabel("hours after the human alert (official, discovery or press time)")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=8, frameon=False)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "s1_first_detection.png", dpi=200)

# ---- figure 2: time to ground per satellite ----
p = pd.read_csv(S1_TABLES / "s1_passes.csv")
med = p.groupby("satellite").minutes_to_ground.median().sort_values()
# colour = how the satellite gets its data down (frozen ground segment)
DOWNLINK = {"Suomi NPP": "polar", "NOAA-20": "polar", "NOAA-21": "polar", "Aqua": "polar",
            "Terra": "relay", "Sentinel-3A": "svalbard", "Sentinel-3B": "svalbard"}
STYLE = {"polar": ("tab:blue", "direct readout (12 stations) or stored-data stations\n(Svalbard, McMurdo, Poker Flat, Fairbanks)"),
         "relay": ("tab:gray", "TDRSS relay, fixed 25 min"),
         "svalbard": ("tab:orange", "Svalbard only, no direct readout")}
fig, ax = plt.subplots(figsize=(7, 3.6))
bars = ax.barh(med.index, med.values, color=[STYLE[DOWNLINK[s]][0] for s in med.index])
ax.bar_label(bars, fmt="%.0f min", padding=3)
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c, _ in STYLE.values()],
          labels=[l for _, l in STYLE.values()], loc="lower right", fontsize=8, frameon=False)
ax.set_xlabel("median wait from the image to the first station contact (min)")
ax.set_xlim(0, med.max() * 1.2)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "s1_time_to_ground.png", dpi=200)
print(f"written to {OUT}")
