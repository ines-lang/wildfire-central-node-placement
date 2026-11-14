"""Export the event-agnostic <region_id>/observations_standard.csv (data/processed/firms) in shared schema v2.

Usage: python pipeline/0_public_record/firms/common/04_export.py --region <region_id>
"""
from wildfire_central_node_placement.firms import read_clean
from wildfire_central_node_placement.paths import region_dir
from wildfire_central_node_placement.registry import region_arg
from wildfire_central_node_placement.schema import SCHEMA_V2, check_and_write, firms_to_schema

if __name__ == "__main__":
    region_id, _ = region_arg()
    OUT_FILE = region_dir("firms", region_id) / "observations_standard.csv"
    df = read_clean(region_id)
    obs = firms_to_schema(df).sort_values(["obs_time_utc", "platform", "latitude", "longitude"]).reset_index(drop=True)
    check_and_write(obs, OUT_FILE)
    print(f"{OUT_FILE.name}: {len(obs)} rows, columns = schema v2: {list(obs.columns) == SCHEMA_V2}")
    print(obs.groupby(["sensor", "platform", "role"]).size().to_string())
    print("qc_flag:", obs["qc_flag"].value_counts().to_dict())
    print("static_proxy:", obs["static_proxy"].value_counts().to_dict())
    print(f"time range: {obs['obs_time_utc'].min()} to {obs['obs_time_utc'].max()}")
