"""Every input and output location of the pipeline, in one place.

Scripts import the paths they need from here and never build paths from their own location, so the folder layout
can change without touching them. Folders that outputs are written to are created by the scripts (`ensure`).

    config/          registry, simulation settings and the hand-edited tables (ground truth, stations, sensors)
    data/raw/        bulky downloads (re-downloadable; not published)
    data/listings/   catalogue queries and file listings as fetched (small; published, a new fetch gives today's state)
    data/processed/  per-source products of the public-record step (0_public_record)
    data/simulator/  inputs written for the network simulator and the report folder of its runs
    data/cache/      basemap tiles
    results/         tables and figures of each methodology step (0_public_record figures, 2 to 5 tables and figures)
"""
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parents[2]                    # .../Latex/code
THESIS = CODE.parents[1]                                       # .../My Master Thesis

# ---- configuration and hand-edited inputs ----
CONFIG = CODE / "config"
SIMULATION_CONFIG = CONFIG / "simulation.yaml"
REGISTRY_FILE = CONFIG / "events_registry.yaml"
GROUND_TRUTH_FILE = CONFIG / "events" / "candidates_ground_truth.csv"
CROSSCHECK_FILE = CONFIG / "events" / "reference_times_crosscheck.csv"
FIRE_CAPABILITY_FILE = CONFIG / "space_segment" / "fire_capability.csv"
GROUND_STATIONS_FILE = CONFIG / "ground_segment" / "ground_stations.csv"
GROUND_STATIONS_RESEARCH_FILE = CONFIG / "ground_segment" / "ground_stations_research.csv"

DATA = CODE / "data"
RAW = DATA / "raw"
LISTINGS = DATA / "listings"
PROCESSED = DATA / "processed"
RESULTS = CODE / "results"
TILE_CACHE = DATA / "cache" / "tile_cache"                    # basemap tiles (contextily / joblib cache)

# ---- 0 public record (S0 inputs: the public fire products) ----
FIRMS_RAW = RAW / "firms"                                      # holds the DL_FIRE_* download folders
FIRMS_PROCESSED = PROCESSED / "firms"
FIRMS_EVENTS = FIRMS_PROCESSED / "events"

LSASAF_RAW = RAW / "lsasaf"
LSASAF_PROCESSED = PROCESSED / "lsasaf"
LSASAF_FULL_DISK_CSV = LSASAF_PROCESSED / "lsasaf_frp_pixels_20250808_20250816.csv"
LSASAF_FIGURES = RESULTS / "0_public_record" / "lsasaf"
LSASAF_EVENTS = LSASAF_PROCESSED / "events"

EFFIS_RAW = RAW / "effis"
EFFIS_PROCESSED = PROCESSED / "effis"
EFFIS_EVENTS = EFFIS_PROCESSED / "events"

GOES_RAW = RAW / "goes"
GOES_PROCESSED = PROCESSED / "goes"
SLSTR_RAW = RAW / "slstr"
SLSTR_PROCESSED = PROCESSED / "slstr"
SLSTR_PRODUCTS_FILE = LISTINGS / "slstr" / "slstr_products.csv"   # catalogue listing written by the download
FY3D_RAW = RAW / "fy3d"
FY3D_PROCESSED = PROCESSED / "fy3d"

# ---- 2 space segment and 3 ground segment ----
SPACE_TABLES = RESULTS / "2_space_segment" / "tables"
SPACE_FIGURES = RESULTS / "2_space_segment" / "figures"
WINDOW_PAYLOADS_FILE = LISTINGS / "space_track" / "window_payloads.csv"   # Space-Track download
NRT_LISTINGS = LISTINGS / "nrt"                                # NRT file listings (LANCE, CDSE, NOAA) as fetched
GROUND_TABLES = RESULTS / "3_ground_segment" / "tables"
GROUND_FIGURES = RESULTS / "3_ground_segment" / "figures"

# ---- 4 events and time references ----
EVENTS_TABLES = RESULTS / "4_events" / "tables"
EVENTS_FIGURES = RESULTS / "4_events" / "figures"
WFIGS_FILE = LISTINGS / "wfigs" / "wfigs_candidates.csv"       # NIFC WFIGS query
L2_FIRE_MASK_RAW = RAW / "l2_fire_mask"
NAFI_RAW = RAW / "nafi"
PERIMETERS_RAW = RAW / "perimeters"

# ---- 5 simulation and post-processing ----
SIM_INPUTS = DATA / "simulator" / "inputs"
S1_TABLES = RESULTS / "5_simulation" / "s1" / "tables"
S1_FIGURES = RESULTS / "5_simulation" / "s1" / "figures"


def _sim_run(key="s1_run_dir"):
    with open(SIMULATION_CONFIG, encoding="utf-8") as f:
        return CODE / yaml.safe_load(f)[key]


SIM_RUN = _sim_run()                                           # the simulator report folder of the S1 run
SIM_RUN_PREVIOUS = _sim_run("s1_previous_run_dir")             # the first S1 run, regression reference


def ensure(path):
    """Create the folder (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def event_dir(source, event_id, kind):
    """Per-event folder of an input source ('firms', 'lsasaf', 'effis').

    kind 'processed' and 'notes': data/processed/<source>/events/<event_id>/ (tables and text reports);
    kind 'figures': results/0_public_record/<source>/<event_id>/.
    """
    if kind == "figures":
        return RESULTS / "0_public_record" / source / event_id
    base = {"firms": FIRMS_EVENTS, "lsasaf": LSASAF_EVENTS, "effis": EFFIS_EVENTS}[source]
    return base / event_id


def region_dir(source, region_id):
    """Region-level processed folder of an input source ('firms', 'lsasaf')."""
    return {"firms": FIRMS_PROCESSED, "lsasaf": LSASAF_PROCESSED}[source] / region_id
