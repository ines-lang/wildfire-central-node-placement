"""Regression against the frozen v1 results (Larouco, Iberia), without the v1 archive.

The v1 values below were read from the v1 archives (FIRMS and EFFIS archive_v1/, moved to code-legacy on
14 Nov 2026) when they still sat next to the code; the fingerprints are SHA-256 of the v1 columns in a canonical
CSV form, and matched the current outputs on that date. Former scripts: FIRMS common/05_compare_v1.py and EFFIS
event/03_regression_check.py (code-legacy).
Run the FIRMS and EFFIS input steps for Iberia / larouco first (run_all.sh).
"""
import hashlib

import numpy as np
import pandas as pd
import pytest

from wildfire_central_node_placement.firms import read_clean
from wildfire_central_node_placement.paths import EFFIS_PROCESSED, FIRMS_PROCESSED, event_dir, region_dir
from wildfire_central_node_placement.registry import get_event

KEY = ["platform", "obs_time_utc", "latitude", "longitude"]
UNCHANGED = ["sensor", "frp", "confidence_raw", "confidence_class", "daynight", "qc_flag", "type",
             "scan", "track", "fire_cluster", "overpass_id", "pixel_size_source"]
# v1 FIRMS (Iberia) counts and fingerprints
V1_COUNTS = {"merged": 1691701, "clean": 39931, "observations_standard": 39931, "overpasses": 129,
             "fire_clusters": 500, "static_proxy_true": 237,
             "platform": {"Aqua": 2298, "NOAA-20": 12872, "NOAA-21": 9996, "Suomi-NPP": 12287, "Terra": 2478},
             "qc_flag": {"ok": 29498, "non_vegetation": 437, "type_missing": 9996}}
V1_FP_UNCHANGED = "4b7866214fd26be04896c28b243533b37e895630f515300b67283bd20b54e524"   # KEY + UNCHANGED columns
V1_FP_AREA = "cab131dde9960b5dd9eccaebe3ba2eddf1309a153c8a29bfda98cbafe173ace4"        # v1 pixel_size_km = v2 area
V1_FP_OVERPASSES = "9eead98d98ad7317a24d2b395a958cea912d936dcd009bbb52dcb2557d5b772a"
# v1 EFFIS (archive_v1/processed/larouco_reference.csv; v1 log, Step 4)
V1_EFFIS_LAROUCO = {"effis_id": "278475", "province / commune": "Ourense / Rúa, A", "start_utc": "2025-08-14T01:34:00Z",
                    "last_update_utc": "2025-08-28T02:13:00Z", "area_ha": 37179, "has_geometry": False}
V1_COINCIDENCE = {"n_used": 122, "n_within": 117}


def fingerprint(df, cols, key=KEY):
    d = df[key + cols].copy()
    if "obs_time_utc" in key:
        d["obs_time_utc"] = d["obs_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    d = d.sort_values(key).reset_index(drop=True)
    return hashlib.sha256(d.to_csv(index=False, float_format="%.10g").encode()).hexdigest()


@pytest.fixture(scope="module")
def clean():
    return read_clean("iberia")


def test_firms_counts(clean):
    merged = pd.read_csv(FIRMS_PROCESSED / "firms_merged.csv.gz", usecols=["platform"])
    assert len(merged) == V1_COUNTS["merged"]
    assert len(clean) == V1_COUNTS["clean"]
    assert clean["platform"].value_counts().to_dict() == V1_COUNTS["platform"]
    assert {f: int((clean["qc_flag"] == f).sum()) for f in V1_COUNTS["qc_flag"]} == V1_COUNTS["qc_flag"]
    assert int((clean["static_proxy"] == True).sum()) == V1_COUNTS["static_proxy_true"]  # noqa: E712
    assert clean["fire_cluster"].nunique() == V1_COUNTS["fire_clusters"]
    assert clean["overpass_id"].nunique() == V1_COUNTS["overpasses"]
    obs = pd.read_csv(region_dir("firms", "iberia") / "observations_standard.csv", usecols=["platform"])
    assert len(obs) == V1_COUNTS["observations_standard"]


def test_firms_unchanged_columns_equal_v1(clean):
    assert fingerprint(clean, UNCHANGED) == V1_FP_UNCHANGED


def test_firms_pixel_size_convention(clean):
    """v2 pixel_area_km2 = v1 pixel_size_km (scan x track); v2 pixel_size_km = its square root (side length)."""
    assert fingerprint(clean.rename(columns={"pixel_area_km2": "area"}), ["area"]) == V1_FP_AREA
    assert np.allclose(clean["pixel_size_km"], np.sqrt(clean["pixel_area_km2"]))


def test_firms_overpasses_equal_v1():
    ov = pd.read_csv(region_dir("firms", "iberia") / "overpasses.csv")
    assert len(ov) == V1_COUNTS["overpasses"]
    cols = ["overpass_id", "start_time_utc", "n_pixels", "total_frp_mw", "extent_km"]
    h = hashlib.sha256(ov[cols].sort_values("overpass_id").to_csv(index=False, float_format="%.10g").encode())
    assert h.hexdigest() == V1_FP_OVERPASSES


def test_effis_larouco_equals_v1_and_registry():
    ref = pd.read_csv(event_dir("effis", "larouco", "processed") / "effis_reference.csv", dtype={"effis_id": str})
    recs, total = ref[ref["effis_id"] != "TOTAL"], ref[ref["effis_id"] == "TOTAL"].iloc[0]
    got = {"effis_id": ";".join(recs["effis_id"]),
           "province / commune": f"{recs['province'].iloc[0]} / {recs['commune'].iloc[0]}",
           "start_utc": total["start_utc"], "last_update_utc": total["last_update_utc"],
           "area_ha": int(total["area_ha"]), "has_geometry": bool(recs["has_geometry"].iloc[0])}
    assert got == V1_EFFIS_LAROUCO
    assert total["start_utc"] == get_event("larouco")["regression_expected"]["effis_start_utc"]


def test_effis_overpass_coincidence_equals_v1():
    coin = pd.read_csv(EFFIS_PROCESSED / "effis_overpass_coincidence.csv")
    used = coin[(coin["country"] == "ES") & coin["excluded_reason"].isna()]   # v1 covered Spain only
    assert (int(used["within_window"].sum()), len(used)) == (V1_COINCIDENCE["n_within"], V1_COINCIDENCE["n_used"])
