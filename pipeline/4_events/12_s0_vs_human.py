"""S0 question (13 Nov 2026): did the public satellite record beat the human alert?

For each event: the human alert time (official or press, config/events/reference_times_crosscheck.csv, with its confidence)
against the public satellite record of the event's main episode (T0 rule, wildfire_central_node_placement.s0.t0_rule):
  image        T0 = first robust public detection (observation time)
  publication  earliest time a public product showed the fire: each robust detection + its delay to publication
               (GOES 3 min, SEVIRI 17.5 min measured in product_latency.csv; polar: the measured median from
               observation to published NRT file of that satellite, nrt_latency.csv, 69 to 151 min, decided with the
               supervisor in Nov 2026 in place of the literature's 2.5 to 3 h; FIRMS within 1 min where a US
               ultra-real-time station received the pass live), minimum over all detections
Signed differences in hours: negative = the satellite record was earlier than the human alert.
Caveat: the human times are of different kinds (official start, declaration, discovery, press).

Inputs: the T0 rule, the S1 run (URT contacts), S1 s1_t0_variants.csv (run S1 06_t0_variants_and_sweep.py first),
        nrt_latency.csv (2_space_segment/03_nrt_latency.py)
Output: s0_vs_human.csv, figure s0_vs_human.png
Usage:  python pipeline/4_events/12_s0_vs_human.py
"""
import pandas as pd

from wildfire_central_node_placement.paths import EVENTS_FIGURES, EVENTS_TABLES, S1_TABLES, SPACE_TABLES
from wildfire_central_node_placement.s0 import t0_rule
from wildfire_central_node_placement.s1 import EVENT_NAMES as NAMES, access_windows, run_stations

GEO_PUBLICATION_MIN = {"GOES": 3.0, "SEVIRI": 17.5}
POLAR_PUBLICATION_MIN = (pd.read_csv(SPACE_TABLES / "nrt_latency.csv").set_index("satellite").latency_median_min
                         .rename({"Suomi NPP": "Suomi-NPP"}))      # observation to published file, per satellite

det, _, t0 = t0_rule()
det = det[det.robust].copy()
det["episode_start"] = det.event.map(pd.to_datetime(t0.main_episode_start))
det = det[det.time_utc >= det.episode_start]
det["delay_min"] = [next((v for k, v in GEO_PUBLICATION_MIN.items() if k in s), None) or POLAR_PUBLICATION_MIN[p]
                    for s, p in zip(det.source, det.platform)]
# FIRMS ultra-real-time (URT, US): a detection is public within URT_MIN if a URT direct-readout station was in contact
# with the satellite at the observation time (contacts of the S1 run; Terra has no direct broadcast since May 2024)
URT_STATIONS = ["Madison WI (SSEC)", "Hampton VA", "Mayaguez PR"]
URT_MIN = 1.0
SIM_NAME = {"Suomi-NPP": "NPP", "NOAA-20": "NOAA 20", "NOAA-21": "NOAA 21", "Aqua": "AQUA"}
gs = run_stations()
acc = access_windows()
acc = acc[acc.ground_station_id.map(gs).isin(URT_STATIONS)]


def urt(row):
    sat = SIM_NAME.get(row.platform)
    if "FIRMS" not in row.source or sat is None:
        return False
    a = acc[acc.satellite_id == sat]
    return bool(((a.rise_utc <= row.time_utc) & (a.set_utc >= row.time_utc)).any())


det["urt"] = det.apply(urt, axis=1)
det.loc[det.urt, "delay_min"] = URT_MIN
det["published_utc"] = det.time_utc + pd.to_timedelta(det.delay_min, unit="min")
first_pub = det.loc[det.groupby("event").published_utc.idxmin()].set_index("event")

out = t0[["human_time_utc", "human_kind", "human_confidence", "t0_utc", "t0_source", "t0_platform", "t0_sensor"]].copy()
out["image_minus_human_h"] = ((out.t0_utc - out.human_time_utc).dt.total_seconds() / 3600).round(2)
out["first_published_utc"] = first_pub.published_utc
out["first_published_source"] = first_pub.source
out["first_published_platform"] = first_pub.platform
out["first_published_sensor"] = first_pub.sensor
out["first_published_delay_min"] = first_pub.delay_min
out["published_minus_human_h"] = ((out.first_published_utc - out.human_time_utc).dt.total_seconds() / 3600).round(2)
out.reset_index().to_csv(EVENTS_TABLES / "s0_vs_human.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
pd.set_option("display.width", 220)
print("FIRMS detections published via URT:", det.groupby("event").urt.sum().loc[lambda x: x > 0].to_dict())
print(out[["human_confidence", "t0_source", "image_minus_human_h", "first_published_source", "published_minus_human_h"]].to_string())

# ---- figure: human alert at 0, public satellite image and publication ----
import matplotlib.pyplot as plt  # noqa: E402

# S1 from the human alert (last week's result): first open-satellite data on the ground, before processing
s1 = pd.read_csv(S1_TABLES / "s1_t0_variants.csv")
out["s1_ground_minus_human_h"] = s1[s1.variant == "human"].set_index("event").ground_after_t0_h
out.reset_index().to_csv(EVENTS_TABLES / "s0_vs_human.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
o = out.sort_values("published_minus_human_h")
fig, ax = plt.subplots(figsize=(8.5, 4.3))
y = range(len(o))
ax.axvline(0, color="#5b6573", lw=1)
ax.hlines(list(y), o.image_minus_human_h, o.published_minus_human_h, color="#c9c8c1", lw=3)
ax.scatter(o.image_minus_human_h, list(y), color="#2a78d6", zorder=3, label="S0 did: first public satellite image (T0)")
ax.scatter(o.published_minus_human_h, list(y), color="#d9480f", marker="D", zorder=3, label="S0 did: first public product published")
ax.scatter(o.s1_ground_minus_human_h, list(y), s=70, facecolor="white", edgecolor="#16263d", lw=1.6, zorder=4,
           label="S1 could: open-satellite data on the ground (before processing)")
ax.set_yticks(list(y), [f"{NAMES[e]} ({c})" for e, c in zip(o.index, o.human_confidence)])
ax.set_xlabel("hours after the human alert (official or press time; confidence in brackets)")
ax.text(-0.1, len(o) - 0.4, "satellite first", ha="right", fontsize=8, color="#5b6573")
ax.text(0.1, len(o) - 0.4, "people first", ha="left", fontsize=8, color="#5b6573")
ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2, fontsize=8, frameon=False)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(EVENTS_FIGURES / "s0_vs_human.png", dpi=200)
