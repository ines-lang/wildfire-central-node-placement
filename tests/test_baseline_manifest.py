"""Every output equals the frozen baseline (tests/baseline_manifest.csv, verified on 14 Nov 2026 against the
pre-refactor results). Run run_all.sh first; see tests/manifest.py to rebuild the manifest after a deliberate change."""
import pytest

from conftest import HAVE_PROCESSED
from manifest import file_hash, output_files, read_manifest
from wildfire_central_node_placement.paths import CODE

BASELINE = read_manifest()


@pytest.mark.parametrize("path", sorted(BASELINE))
def test_output_equals_baseline(path):
    p = CODE / path
    if not p.exists() and not HAVE_PROCESSED:
        pytest.skip("not published (clean clone without data/)")
    assert p.exists(), f"missing output {path}"
    assert file_hash(p) == BASELINE[path], f"{path} differs from the baseline"


def test_no_unexpected_outputs():
    new = sorted(p.relative_to(CODE).as_posix() for p in output_files())
    assert [p for p in new if p not in BASELINE] == []
