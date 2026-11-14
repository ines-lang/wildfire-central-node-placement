# Wildfire detection latency from EO satellites: thesis code

Repository: https://github.com/ines-lang/wildfire-central-node-placement

Code, inputs and results of the master thesis (TUM). The folders follow the chapters of the methodology
(chapter 1, Approach, has no code): 0 public record (the public fire products of S0), 2 space segment,
3 ground segment, 4 events and time references, 5 simulation and post-processing. Times are UTC.

```
config/      events_registry.yaml (the events, conventions, T0 rule), simulation.yaml (S1 run folder),
             events/ (ground truth of the candidates), space_segment/ (fire capability, sensors),
             ground_segment/ (stations)                                      hand-edited
src/wildfire_central_node_placement/   shared package: paths, registry, geometry, plotting, schema, S0 / T0 rule, S1 run, credentials
pipeline/    0_public_record/{firms,lsasaf,effis,goes,slstr,fy3d}  2_space_segment  3_ground_segment  4_events
             5_simulation/s1 (one folder per scenario run: s1 now, s2 to s4 later)     scripts, numbered in run order
data/        raw/ (downloads), listings/ (catalogue queries as fetched), processed/ (input products),
             simulator/ (simulator inputs and run), cache/ (map tiles)
results/     tables and figures of each step (0_public_record figures; 2 to 5 tables/ and figures/)
tests/       regression tests and the baseline manifest
run_all.sh   the whole offline pipeline
```

## Setup

Python 3.14. In the thesis venv (or any venv):

```bash
uv pip install --python <venv>/bin/python -e ".[test]"      # or: pip install -e ".[test]"
```

Dependencies are pinned in `pyproject.toml` to the versions that produced the results.
Credentials (download steps only): `.env.example` lists the variable names; values come from the environment or from
the `.env` file named by `THESIS_ENV_FILE` (default `<thesis folder>/master-thesis/.env`).

## Run

```bash
bash run_all.sh                  # every offline step in dependency order (about 6 min), logs in logs/
python -m pytest tests           # regression against v1, the registry and the baseline manifest
```

The events come from `config/events_registry.yaml` (seven selected events and the dropped alternative Mount
Underwood); their official times, areas and locations from `config/events/candidates_ground_truth.csv`.
The per-event input steps (FIRMS, LSA SAF, EFFIS) cover Larouco and Molezuelas, as listed in `run_all.sh`.

## Downloads and steps that need the network

`run_all.sh` reads only `data/`. These steps fetch data (accounts in brackets) and are run by hand:

| Source | Script | Output |
|---|---|---|
| NASA FIRMS (manual archive and NRT requests, 4 Oct 2026) | none | `data/raw/firms/DL_FIRE_*` |
| LSA SAF FRP-PIXEL (LSA SAF account) | `0_public_record/lsasaf/00_download.py` | `data/raw/lsasaf/`, then `--convert-only` |
| EFFIS burnt areas (request to JRC; WFS polygons) | none | `data/raw/effis/` |
| GOES ABI FDC (NOAA open data, AWS) | `0_public_record/goes/01_download.py` | `data/raw/goes/` |
| Sentinel-3 SL_2_FRP (CDSE account) | `0_public_record/slstr/01_download.py` | `data/raw/slstr/`, `data/listings/slstr/` |
| FY-3D MERSI-II GFR (NSMC portal account) | none (manual) | `data/raw/fy3d/` (empty: files not downloaded) |
| Space-Track orbits (account) | `2_space_segment/00_fetch_window.py` | `data/listings/space_track/` |
| NRT file listings (LANCE, CDSE, NOAA AWS) | `2_space_segment/03_nrt_latency.py`, `04_latency_study_window.py` (without `--offline`) | `data/listings/nrt/` |
| NIFC WFIGS discovery times | `4_events/00_wfigs_query.py` | `data/listings/wfigs/` |
| Level-2 fire masks (CMR; Earthdata account) | `4_events/05_fire_mask_check.py catalog` then `read` | `results/4_events/tables/fire_mask_*.csv` |
| NAFI fire scars (rasters cached in `data/raw/nafi/`) | `4_events/09_nafi_scars.py` | runs offline while the cache is complete |
| ESA WorldCover (read remotely) | `4_events/10_wildfire_check.py` | `results/4_events/tables/wildfire_check.csv` |
| Esri basemap tiles below 66 deg S (not in the tile cache) | `3_ground_segment/02_ground_segment_map.py` | `results/3_ground_segment/figures/03_ground_segment_map.png` |
| Official perimeters (WFIGS, BC Wildfire Service; manual) | none | `data/raw/perimeters/` |

The listings in `data/listings/` are kept as fetched: a new fetch gives the state of that day, not the one used.

## Notes

- T0 (decided 13 Nov 2026): first robust public satellite detection of the event's main episode inside the official
  perimeter (`config/events_registry.yaml` conventions.t0, `src/wildfire_central_node_placement/s0.py`). The FIRMS event summaries still
  report the earlier rule (`t0_until_13nov2026`) as their regression reference.
- The S1 run of the NeuralAgent network simulator is in `data/simulator/runs/` (set in `config/simulation.yaml`); its
  inputs are written by `5_simulation/s1/00_simulator_inputs.py`.
- Superseded code, frozen v1 copies and work notes are kept outside the repository, in `code-legacy/`.

## Not in the public repository

- `data/`: raw downloads come from the providers (table above); the processed products will be archived on Zenodo.
- Results computed from the NeuralAgent simulator run (`results/5_simulation/`, `coordination_layer_candidates.csv`,
  `s0_vs_human.*`); the scripts that compute them are included.
- `eo_census.csv` and `eo_layer_proposal.csv`: they hold Space-Track TLEs, which may not be redistributed; rebuild them
  with `2_space_segment/00_fetch_window.py` (Space-Track account) and `01_fire_analysis.py`.
- The large event-selection tables (`complexes.csv`, `complexes_criteria.csv`, `candidate_detections.csv`).

Without `data/`, the tests that need it are skipped; the published results are still checked against the baseline.

## Licence

Code: MIT (`LICENSE`). Data and products of NASA FIRMS, EUMETSAT LSA SAF, Copernicus EFFIS and Sentinel-3, NOAA GOES,
NIFC WFIGS and the other sources keep their providers' terms; cite them as listed in the thesis.
