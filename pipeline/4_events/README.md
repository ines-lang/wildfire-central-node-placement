# 4 Events and time references

Selects one wildfire per continent igniting inside the data window (8 to 16 Aug 2025) and sets the time references
(T0) of the selected events. Selection rule: among complexes passing the screen, the largest **official final burned
area** with an **official ignition time**. The events are listed in `config/events_registry.yaml`; the official
times, areas and sources of every candidate in `config/events/candidates_ground_truth.csv` (edited by hand, with the
**decision and reason**) and `config/events/ground_truth.md` (research behind each row). Tables go to
`results/4_events/tables/`, figures to `results/4_events/figures/`.

| Step | Script | What it does |
|---|---|---|
| input | `0_public_record/firms/common/02_clean.py --region world` | Global FIRMS cleaning and 1 km clusters (`data/processed/firms/world/`) |
| 0 | `00_wfigs_query.py` | Official US discovery times (NIFC WFIGS, network) -> `data/listings/wfigs/wfigs_candidates.csv` |
| 1 | `01_screen_firms.py` | One row per fire complex, FIRMS burned-area proxy, candidate matching -> `complexes.csv`, `candidate_matches.csv`, `candidate_detections.csv` (all confidences, column `kept`) |
| 2 | `02_criteria.py` | Criteria 1 to 5, funnel, ranking -> `complexes_criteria.csv`, `criteria_funnel.csv`, `ranking.csv` |
| 3 | `03_overpasses.py` | Every VIIRS / MODIS overpass of each registry event, 24 h before to 54 h after the reference time (S1 TLEs of the EO census) -> `candidate_overpasses.csv` |
| 4 | `04_figures.py` | `01` world map, `02` largest complexes per continent, `03` reference time to first detection with all overpasses, `04` official vs FIRMS area; `detection_bracket.csv` |
| 5 | `05_fire_mask_check.py catalog` / `read` | Level-2 fire masks of the empty passes before the first detection (network; Earthdata account for `read`) |
| 6 | `06_s0_first_detection.py` | First public detection per event and source inside the official perimeter -> `s0_first_detection.csv` |
| 7 | `07_selection_alternatives.py` | `candidates_official_area.png`, `selection_funnel.png` |
| 8 | `08_product_latency.py` | Measured latency of the GEO fire products (GOES, LSA SAF) -> `product_latency.csv` |
| 9 | `09_nafi_scars.py` | NAFI burnt-area check of the Oceania complexes -> `nafi_oceania.csv` |
| 10 | `10_wildfire_check.py` | Wildfire or managed burn (WorldCover read remotely, network) -> `wildfire_check.csv` |
| 11 | `11_t0_rule.py` | T0 rule of 13 Nov 2026 (`wildfire_central_node_placement.s0`) -> `t0_events.csv`, `t0_sensitivity.csv` |
| 12 | `12_s0_vs_human.py` | Public satellite record against the human alert -> `s0_vs_human.csv`, `s0_vs_human.png` (after `5_simulation/s1/06`) |

Criteria: 1 vegetation fire (< 50% flagged volcano / static), 2 onset at least 24 h after the window start,
3 FIRMS area >= 500 ha (filter only), 4 spreading (>= 5 km and >= 20 cells; removes gas flares),
5 hemisphere and continent rule (switched off: `EXCLUDE_SOUTH`, `ASIA_SIBERIA_ONLY` in `02_criteria.py`).

Figures for the report are copied by hand to `Latex/figures/event_selection_*.png`.
