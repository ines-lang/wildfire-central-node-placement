"""Step 2.11: T0 of each event from public satellite data only (decision of 13 Nov 2026).

The rule is wildfire_central_node_placement.s0.t0_rule (registry conventions.t0); in short:
  1. Detections of every public source (FIRMS VIIRS + MODIS, Sentinel-3 SL_2_FRP, SEVIRI LSA SAF, GOES ABI FDC) inside
     the official final perimeter + 2 km, static and non-vegetation sources removed (as 06_s0_first_detection.py).
  2. Episodes: the detections are split where no detection occurs for at least GAP_H hours. Earlier, separate fires
     inside the same perimeter (Piodao: Aldeia das Dez; Oimbra: the merged Gudin fire) form their own episodes.
  3. The event is the main episode, the one with most detections.
  4. T0 = the first robust detection of that episode: a polar detection, or a geostationary one confirmed by the same
     satellite within GEO_CONFIRM_MIN (registry convention: at least two consecutive SEVIRI slots).
The official or press time is NOT used to set T0; it is only compared with it (S0 question, signed difference).
Sensitivity: GAP_H in GAP_SENSITIVITY, GEO confirmation in CONFIRM_SENSITIVITY. Events: the selected events.

Output: t0_events.csv (main rule), t0_sensitivity.csv (T0 per gap), printed summary
Usage:  python pipeline/4_events/11_t0_rule.py
"""
import pandas as pd

from wildfire_central_node_placement.paths import EVENTS_TABLES
from wildfire_central_node_placement.s0 import t0_rule

det, sens, main = t0_rule()
main.reset_index().to_csv(EVENTS_TABLES / "t0_events.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
sens.to_csv(EVENTS_TABLES / "t0_sensitivity.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
pd.set_option("display.width", 250)
print(main[["t0_utc", "t0_source", "t0_platform", "human_time_utc", "human_confidence", "t0_minus_human_h", "episodes",
            "excluded_before", "t0_stable_over_gaps"]].to_string())
print("\nT0 per gap and GEO confirmation (min):\n" + sens.pivot_table(index="event", columns=["gap_h", "confirm_min"], values="t0_utc", aggfunc="first").to_string())
