"""Baseline manifest of the pipeline outputs: SHA-256 of every file in data/processed, data/simulator/inputs and results.

Gzip files are hashed after decompression (their header holds the write time). Rebuild the manifest only after a
deliberate change of an input or a method, once the differences are understood:
    python tests/manifest.py          (writes tests/baseline_manifest.csv)
"""
import csv
import gzip
import hashlib
from pathlib import Path

from wildfire_central_node_placement.paths import CODE, PROCESSED, RESULTS, SIM_INPUTS

MANIFEST = Path(__file__).with_name("baseline_manifest.csv")
ROOTS = [PROCESSED, SIM_INPUTS, RESULTS]


def file_hash(path):
    h = hashlib.sha256()
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def output_files():
    return sorted(p for root in ROOTS for p in root.rglob("*") if p.is_file())


def write_manifest():
    with open(MANIFEST, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "sha256"])
        for p in output_files():
            w.writerow([p.relative_to(CODE).as_posix(), file_hash(p)])


def read_manifest():
    with open(MANIFEST, newline="") as f:
        return {r["path"]: r["sha256"] for r in csv.DictReader(f)}


if __name__ == "__main__":
    write_manifest()
    print(f"written {MANIFEST} ({len(read_manifest())} files)")
