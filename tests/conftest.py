"""Tests that need the pipeline data are skipped when data/ is absent (a clean clone of the public repository,
where data/ is not published). With data/ present, a missing file is a failure, never a skip."""
import pytest

from wildfire_central_node_placement.paths import PROCESSED, RAW

HAVE_PROCESSED = PROCESSED.exists()
HAVE_RAW = RAW.exists()

NEEDS_PROCESSED = {"test_v1_regression.py", "test_registry_regression.py"}
NEEDS_RAW = {"test_perimeters_exist"}


def pytest_collection_modifyitems(config, items):
    for item in items:
        if not HAVE_PROCESSED and item.path.name in NEEDS_PROCESSED:
            item.add_marker(pytest.mark.skip(reason="data/processed not present (clean clone)"))
        if not HAVE_RAW and item.name in NEEDS_RAW:
            item.add_marker(pytest.mark.skip(reason="data/raw not present (clean clone)"))
