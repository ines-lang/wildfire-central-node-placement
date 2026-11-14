#!/bin/bash
# Whole offline pipeline, in dependency order (methodology chapters: public record, space segment, ground segment, events
# and time references, simulation and post-processing). Stops at the first failure.
# Every step reads data/ and config/ only (no network); the download and query steps are listed in README.md.
#
# Usage: bash run_all.sh            (from anywhere; about 6 min)
#        PYTHON=/path/to/python bash run_all.sh
# Each step's printed report goes to logs/<nn>_<step>.log; then run the tests: python -m pytest
set -euo pipefail
C="$(cd "$(dirname "$0")" && pwd)"                                     # the code/ folder
PY="${PYTHON:-$C/../../master-thesis/bin/python}"                      # the master-thesis venv, next to the Latex folder
LOGS="$C/logs"; mkdir -p "$LOGS"
n=0
run() {  # run <script under pipeline/> [args...]
  n=$((n + 1)); local log; log="$LOGS/$(printf '%02d' $n)_$(basename "$1" .py).log"
  echo ">>> $*"
  "$PY" "$C/pipeline/$1" "${@:2}" > "$log" 2>&1 || { echo "FAILED, see $log"; tail -20 "$log"; exit 1; }
}
EVENTS="larouco molezuelas"          # events with the per-event input steps (FIRMS, LSA SAF, EFFIS)
I="0_public_record"

# ---- 0 public record: FIRMS (Iberia region and events) ----
run $I/firms/common/00_inventory.py --region iberia
run $I/firms/common/01_merge.py
for s in 02_clean 03_overpasses 04_export; do run $I/firms/common/$s.py --region iberia; done
for e in $EVENTS; do for s in 01_select 02_products 03_figures 04_merge_check; do run $I/firms/event/$s.py --event $e; done; done
run $I/firms/event/05_gap_split.py --event larouco
run $I/firms/event/05_gap_split.py --event molezuelas --until 2025-08-12T14:57:00Z
# ---- 0 public record: LSA SAF (SEVIRI) ----
run $I/lsasaf/00_download.py --convert-only
for r in iberia anatolia; do run $I/lsasaf/common/01_region_export.py --region $r; done
run $I/lsasaf/common/02_inventory.py --region iberia
for e in $EVENTS; do run $I/lsasaf/event/01_event_seviri.py --event $e; run $I/lsasaf/event/02_event_figures.py --event $e; done
# ---- 0 public record: EFFIS (record sets and search parameters not yet in the registry are passed here) ----
run $I/effis/common/01_inspect.py
run $I/effis/common/02_standardize.py
run $I/effis/common/03_overpass_coincidence.py --region iberia
run $I/effis/event/01_effis_reference.py --event larouco
run $I/effis/event/01_effis_reference.py --event molezuelas --records 277940 --neighbour-provinces Zamora León \
  --reported-end 2025-08-22T00:00:00Z --area-refs "Junta provisional, both provinces (registry comment)=31500" \
  "media / Copernicus estimate low (registry comment)=37000" "media / Copernicus estimate high (registry comment)=38000"
run $I/effis/event/02_firms_context_figure.py --event larouco
run $I/effis/event/02_firms_context_figure.py --event molezuelas --records 277940
run $I/effis/event/04_find_records.py --event molezuelas --provinces Zamora Leon --start-from 2025-08-10T00:00:00Z \
  --start-to 2025-08-13T23:59:00Z --communes "Molezuelas de la Carballeda" "Una de Quintana" "Castrocalbon" \
  --name-parts Valderia Valduerna Jamuz
# ---- 0 public record: global FIRMS screen, GOES, Sentinel-3 SLSTR, FY-3D ----
run $I/firms/common/02_clean.py --region world
run $I/goes/02_fire_pixels.py
run $I/slstr/02_fire_points.py
if compgen -G "$C/data/raw/fy3d/FY3D_MERSI_GBAL_L2_GFR_*.HDF" > /dev/null; then run $I/fy3d/01_read_gfr.py
else echo "--- skipped fy3d/01_read_gfr.py: no FY-3D files in data/raw/fy3d"; fi

# ---- 2 space segment ----
run 2_space_segment/01_fire_analysis.py
run 2_space_segment/02_overpass_times.py
run 2_space_segment/03_nrt_latency.py --offline
run 2_space_segment/04_latency_study_window.py --offline
run 2_space_segment/05_geo_coverage.py
run 2_space_segment/06_coordination_layer_study.py      # coordination layer (S1 sensor positions from the S1 run)

# ---- 3 ground segment (02_ground_segment_map.py needs basemap tiles from the network: see README) ----
run 3_ground_segment/01_ground_contacts.py
run 5_simulation/s1/00_simulator_inputs.py

# ---- 4 events and time references ----
for s in 01_screen_firms 02_criteria 03_overpasses 04_figures 06_s0_first_detection 07_selection_alternatives \
         08_product_latency 09_nafi_scars 11_t0_rule; do run 4_events/$s.py; done

# ---- 5 simulation and post-processing (S1 run: config/simulation.yaml) ----
run 5_simulation/s1/04_extra_station_contacts.py
run 5_simulation/s1/04_extra_station_contacts.py --stations "$C/config/ground_segment/ground_stations_research.csv" \
  --out research_access_windows.csv
for s in 01_s1_latency 02_figures 03_ground_sensitivity 05_station_baseline_research 06_t0_variants_and_sweep \
         07_compare_last_week; do run 5_simulation/s1/$s.py; done
run 4_events/12_s0_vs_human.py                                        # needs the S1 T0 variants
echo "ALL OK ($n steps); logs in $LOGS. Check: $PY -m pytest $C/tests"
