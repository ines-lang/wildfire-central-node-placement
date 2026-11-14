"""Figure for the progress deck: S1 last week (from the human alert) against now (from T0), with the sweep bands.

Inputs: s1_t0_variants.csv, s1_sweep.csv (06_t0_variants_and_sweep.py)
Output: s1_last_week_vs_now.png
Usage:  python pipeline/5_simulation/s1/07_compare_last_week.py
"""
import matplotlib.pyplot as plt
import pandas as pd

from wildfire_central_node_placement.paths import S1_FIGURES, S1_TABLES, ensure
from wildfire_central_node_placement.s1 import EVENT_NAMES as NAMES

var = pd.read_csv(S1_TABLES / "s1_t0_variants.csv").pivot(index="event", columns="variant", values="ground_after_t0_h")
sweep = pd.read_csv(S1_TABLES / "s1_sweep.csv").set_index("event")
var = var.sort_values("human")

fig, ax = plt.subplots(figsize=(9, 4.2))
ax.axvspan(sweep.median_h.min(), sweep.median_h.max(), color="#2a78d6", alpha=0.12, lw=0)
ax.axvspan(sweep.p90_h.min(), sweep.p90_h.max(), color="#c2410c", alpha=0.10, lw=0)
ax.text(sweep.median_h.mean(), len(var) - 0.35, "any start:\nmedian", ha="center", va="bottom", fontsize=9, color="#2a78d6")
ax.text(sweep.p90_h.mean(), len(var) - 0.35, "any start:\n90th pct", ha="center", va="bottom", fontsize=9, color="#c2410c")
for i, (ev, r) in enumerate(var.iterrows()):
    ax.plot([r.human, r.public], [i, i], color="#b7b2a6", lw=3, zorder=1)
ax.scatter(var.human, range(len(var)), s=90, color="#9aa3ad", zorder=2, label="last week: from the human alert")
ax.scatter(var.public, range(len(var)), s=90, color="#16263d", zorder=3, label="now: from T0 (first public detection)")
ax.set_yticks(range(len(var)), [NAMES[e] for e in var.index], fontsize=11)
ax.set_xlabel("hours to the first S1 data on the ground", fontsize=11)
ax.set_ylim(-0.6, len(var) + 0.6)
ax.set_xlim(0, 6.2)
ax.grid(axis="x", alpha=0.3)
ax.legend(loc="lower right", fontsize=9, framealpha=0.95)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(ensure(S1_FIGURES) / "s1_last_week_vs_now.png", dpi=200)
print(var.round(2).to_string())
