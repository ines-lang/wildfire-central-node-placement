"""S0 against S1, step by step: from the human alert to a public fire product, per event.

Each event has two rows, both from the human alert (0 h):
  S0 (what happened)   the public record. The image is observed; the time from image to public product is measured for
                       the geostationary products (GOES 3 min, SEVIRI 17.5 min, product_latency.csv) and taken from the
                       measured on the NRT files for the polar ones (nrt_latency.csv, same source as S1): downlink and processing together.
                       The row follows the detection that was published first (it can come after T0, which is marked).
  S1 (what could be)   the open satellites in the simulator: the pass (simulated orbits), the wait for a station
                       (simulated contacts, frozen ground segment), the downlink itself instant, then processing and
                       publishing = the median measured on the NRT files online in Oct-Nov 2026 (nrt_latency.csv), an
                       estimate not simulated. The pass is the one whose data reach the ground first (the S1 result).

Inputs:  s0_vs_human.csv (4_events/12_s0_vs_human.py), s1_t0_variants.csv (s1/06), nrt_latency.csv (2_space_segment/03),
         s1_sensors.csv (simulator inputs)
Output:  s1_pipeline_per_event.png (thesis), s1_pipeline_per_event_slide.png (same, larger text)
Usage:   python pipeline/5_simulation/s1/08_pipeline_per_event.py
"""
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

from wildfire_central_node_placement.paths import EVENTS_TABLES, S1_FIGURES, S1_TABLES, SIM_INPUTS, SPACE_TABLES, ensure
from wildfire_central_node_placement.s1 import EVENT_NAMES as NAMES

OUT = ensure(S1_FIGURES)
PASS, STATION, PROC, BOTH = "#eb6834", "#6250d6", "#1baf7a", "#a3a29b"
INK, MUTED = "#0b0b0b", "#52514e"

h = pd.read_csv(EVENTS_TABLES / "s0_vs_human.csv",
                parse_dates=["human_time_utc", "t0_utc", "first_published_utc"]).set_index("event")
s1 = pd.read_csv(S1_TABLES / "s1_t0_variants.csv", parse_dates=["observation_utc", "ground_utc"])
s1 = s1[s1.variant == "human"].set_index("event")
proc = pd.read_csv(SPACE_TABLES / "nrt_latency.csv").set_index("satellite").processing_median_min
instrument = pd.read_csv(SIM_INPUTS / "s1_sensors.csv").set_index("satellite").instrument


def hours(t, ev):
    return (t - h.loc[ev, "human_time_utc"]).total_seconds() / 3600


ORDER = ["molezuelas", "derdara", "silifke", "oimbra", "red_canyon", "larouco", "piodao"]


def draw(name, figsize, fs, detail):
    """fs: base font size; detail: thesis labels (ground time, full legend) or short slide labels."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.axvline(0, color=MUTED, lw=1)
    ticks, labels = [], []
    kw = dict(height=0.62, edgecolor="white", linewidth=1.5)
    ms = 7 * fs / 8
    for i, ev in enumerate(ORDER):
        y0, y1 = 3 * i, 3 * i + 1
        # ---- S0: the detection published first ----
        src = h.loc[ev, "first_published_source"]
        delay = h.loc[ev, "first_published_delay_min"]                  # as in 4_events/12
        pub = hours(h.loc[ev, "first_published_utc"], ev)
        img = pub - delay / 60
        geo = "SEVIRI" in src or "GOES" in src
        if img > 0:
            ax.barh(y0, img, color=PASS, **kw)
        ax.barh(y0, max(pub - img, 0.04), left=img, color=PROC if geo else BOTH, hatch=None if geo else "///", **kw)
        t0 = hours(h.loc[ev, "t0_utc"], ev)
        if abs(t0 - img) > 0.05:                                     # T0 came from another, slower-published source
            ax.plot(t0, y0, "o", ms=ms, mfc="white", mec=INK, mew=1.4 * fs / 8, zorder=4)
        ax.text(max(pub, 0) + 0.12, y0, f"{pub:.1f} h · {h.loc[ev, 'first_published_platform']} ({h.loc[ev, 'first_published_sensor']})", va="center", fontsize=fs, color=INK)
        # ---- S1: pass, wait for a station, processing and publishing ----
        r = s1.loc[ev]
        o, g = hours(r.observation_utc, ev), hours(r.ground_utc, ev)
        p = g + proc[r.satellite] / 60
        ax.barh(y1, o, color=PASS, **kw)
        ax.barh(y1, g - o, left=o, color=STATION, **kw)
        ax.barh(y1, p - g, left=g, color=PROC, hatch="///", **kw)
        ax.text(p + 0.12, y1, f"{p:.1f} h · {r.satellite} ({instrument[r.satellite]})" + (f" (on ground {g:.1f} h)" if detail else ""),
                va="center", fontsize=fs, color=INK)
        ticks += [y0, y1]
        labels += [f"{NAMES[ev]}   S0", "S1"]
    ax.set_yticks(ticks, labels, fontsize=fs + 1)
    for t in ax.get_yticklabels()[1::2]:
        t.set_color(MUTED)
    ax.tick_params(axis="x", labelsize=fs + 1)
    ax.invert_yaxis()
    ax.set_xlim(-0.6, 10.6 if detail else 11)
    ax.set_xlabel("hours after the human alert" + (" (official, discovery or press time)" if detail else ""), fontsize=fs + 1)
    ax.grid(axis="x", alpha=0.3)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.text(-0.1, -1.2, "satellite first", ha="right", fontsize=fs, color=MUTED)
    ax.text(0.1, -1.2, "people first", ha="left", fontsize=fs, color=MUTED)
    long = [("wait for the satellite pass (until the image)", "wait for the pass (until the image)"),
            ("S1 only: wait for a ground station (simulated)", "S1: wait for a ground station"),
            ("processing + publishing, measured (GEO, S0)", "processing + publishing, measured (GEO)"),
            ("processing + publishing, estimate (polar, S1)", "processing + publishing, estimate (S1)"),
            ("station + processing + publishing, measured (polar, S0)", "station + processing, measured (S0 polar)"),
            ("S0: first public image (T0), if not the bar's image", "S0: first public image (T0)")]
    lab = [a if detail else b for a, b in long]
    handles = [Patch(color=PASS, label=lab[0]), Patch(color=STATION, label=lab[1]),
               Patch(facecolor=PROC, edgecolor="white", label=lab[2]),
               Patch(facecolor=PROC, edgecolor="white", hatch="///", label=lab[3]),
               Patch(facecolor=BOTH, edgecolor="white", hatch="///", label=lab[4]),
               plt.Line2D([], [], marker="o", ls="", ms=ms, mfc="white", mec=INK, mew=1.4 * fs / 8, label=lab[5])]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.1 if detail else -0.12), ncol=2,
              fontsize=fs - 0.5, frameon=False, columnspacing=1.2, handlelength=2.2)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    print(f"written to {OUT / name}")


draw("s1_pipeline_per_event.png", (9, 6.2), 8, True)          # thesis
draw("s1_pipeline_per_event_slide.png", (9.5, 6.8), 13, False)  # slide: larger text, shorter labels
