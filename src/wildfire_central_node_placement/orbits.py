"""Orbit geometry shared by the space- and ground-segment scripts: swaths, passes over a point, elevation mask."""
import numpy as np
from skyfield.api import EarthSatellite, wgs84

from wildfire_central_node_placement.geo import great_circle_km

# swath half-widths (km): Month 2 Table (VIIRS, MODIS, SLSTR); MERSI-II from OSCAR
HALF_SWATH_KM = {"VIIRS": 3040 / 2, "MODIS": 2330 / 2, "SLSTR": 1400 / 2, "MERSI-II": 2900 / 2}
MIN_ELEVATION_DEG = 10           # station elevation mask (Month 2)
TERRA_RELAY_WAIT_MIN = 25        # Terra: TDRSS relay only (no direct broadcast since May 2024); mean wait, LANCE


def satellite(line1, line2, name, ts):
    return EarthSatellite(line1, line2, name, ts)


def distance_to_track_km(sat, t, lat, lon):
    """Great-circle distance (km) from (lat, lon) to the sub-satellite point at each time of t."""
    sub = wgs84.subpoint_of(sat.at(t))
    return great_circle_km(lat, lon, sub.latitude.degrees, sub.longitude.degrees)


def pass_runs(inside):
    """Label consecutive True samples of a boolean time series: 1, 2, ... per run (one run = one pass), 0 outside."""
    return np.cumsum(np.diff(np.r_[0, inside.astype(int)]) == 1) * inside
