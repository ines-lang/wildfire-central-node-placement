"""Step 2.8: measured product latency of the geostationary fire products (detection to product).

The files record both times, so the latency is measured, not assumed:
    GOES ABI FDC   file name: s<scan start> ... c<file creation>   (YYYYDDDHHMMSSs)
    LSA SAF FRP    HDF5 attributes IMAGE_ACQUISITION_TIME (slot start) and NOMINAL_PRODUCT_TIME
The polar products cannot be measured this way: FIRMS publishes no production time, and only the reprocessed
(NTC) Sentinel-3 products remain archived. Their latency is the downlink wait (ground segment ground_contacts.csv)
plus a processing time stated by the providers (under 3 h), not measured here.

Output: product_latency.csv   one row per product and file
Usage: python pipeline/4_events/08_product_latency.py
"""
import h5py
import pandas as pd

from wildfire_central_node_placement.paths import EVENTS_TABLES, GOES_RAW, LSASAF_RAW

OUT = EVENTS_TABLES / "product_latency.csv"

rows = []
for sat in ["goes18", "goes19"]:
    for p in sorted((GOES_RAW / sat).glob("*.nc")):
        parts = p.stem.split("_")                       # OR, ABI-L2-FDCC-M6, G19, s..., e..., c...
        start = pd.to_datetime(parts[3][1:14], format="%Y%j%H%M%S")
        created = pd.to_datetime(parts[5][1:14], format="%Y%j%H%M%S")
        rows.append(dict(product=f"GOES ABI FDC ({sat.upper().replace('GOES', 'GOES-')})", file=p.name,
                         observation_utc=start, product_utc=created))
for p in sorted(LSASAF_RAW.glob("HDF5_LSASAF_*")):
    with h5py.File(p) as f:
        rows.append(dict(product="LSA SAF FRP-PIXEL (SEVIRI)", file=p.name,
                         observation_utc=pd.to_datetime(f.attrs["IMAGE_ACQUISITION_TIME"].decode()),
                         product_utc=pd.to_datetime(f.attrs["NOMINAL_PRODUCT_TIME"].decode())))
d = pd.DataFrame(rows)
d["latency_min"] = ((d.product_utc - d.observation_utc).dt.total_seconds() / 60).round(1)
d.to_csv(OUT, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
print(d.groupby("product").latency_min.describe(percentiles=[0.5, 0.95])[["count", "50%", "95%", "max"]].round(1))
