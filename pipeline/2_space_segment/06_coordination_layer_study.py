"""Space segment, coordination layer: altitude, inclination and pattern of the coordination layer (Walker t = 600, p = 20).

For each candidate, over one day (13 Aug 2025, every 2 min):
    sensor_sees_any        mean number of coordination satellites in crosslink range of an S1 sensor
    sensor_sees_cn_pct     % of time an S1 sensor has a central node in range, with one central node per plane (20), staggered along the planes
    station_*_pct          % of time a ground station sees at least one coordination satellite (elevation >= 10 deg)
    cross_plane_km         largest distance between neighbouring planes (at the equator), against the OISL range
The S1 sensors are the real positions from the S1 run. The Walker layer is propagated as circular orbits
(two-body, no J2: enough for one day of statistics).
Output: coordination_layer_candidates.csv
Usage:  python pipeline/2_space_segment/06_coordination_layer_study.py
"""
import numpy as np
import pandas as pd

from wildfire_central_node_placement.paths import SPACE_TABLES, SIM_RUN, ensure

RUN = SIM_RUN
OUT = ensure(SPACE_TABLES)

T, P = 600, 20                      # Walker satellites and planes (meeting of 27 October)
F = 1                               # phasing factor
RANGE_KM = 3500                     # optical terminal of the simulator (SCOT30, max range)
GRAZING_KM = 100                    # a link must pass at least 100 km above the Earth
MASK_DEG = 10
RE, MU = 6371.0, 398600.4418
DAY = "2025-08-13"
STATIONS = {"Svalbard": (78.23, 15.41), "McMurdo": (-77.85, 166.67), "Poker Flat": (65.12, -147.47),
            "Madison": (43.07, -89.40)}
CANDIDATES = [(h, i, pattern) for h in [550, 800, 1200]
              for i, pattern in [(53, "delta"), (70, "delta"), (80, "delta"), (87.9, "delta"), (87.9, "star"),
                                 (97.6, "delta")]]

# ---- S1 sensors: real positions from the S1 run, one day every 2 min ----
s = pd.read_csv(RUN / "02_satellite_states.csv", usecols=["time_utc", "satellite_id", "eci_x_km", "eci_y_km", "eci_z_km"],
                parse_dates=["time_utc"])
s = s[s.time_utc.dt.strftime("%Y-%m-%d") == DAY]
s = s[s.time_utc.dt.minute % 2 == 0]
times = np.sort(s.time_utc.unique())
sensors = np.stack([g.sort_values("time_utc")[["eci_x_km", "eci_y_km", "eci_z_km"]].values
                    for _, g in s.groupby("satellite_id")])                     # (7, n_times, 3)
t_s = (pd.to_datetime(times) - pd.Timestamp(DAY, tz="UTC")).total_seconds().values
jd = pd.to_datetime(times).to_julian_date().values
gmst = np.radians((280.46061837 + 360.98564736629 * (jd - 2451545)) % 360)    # checked against the run's ECEF


def walker(h, i_deg, pattern):
    """ECI positions (n_times, T, 3) of a Walker constellation, circular orbits."""
    r = RE + h
    n = np.sqrt(MU / r**3)                                                     # rad/s
    spread = 2 * np.pi if pattern == "delta" else np.pi
    j = np.repeat(np.arange(P), T // P)                                        # plane of each satellite
    k = np.tile(np.arange(T // P), P)                                          # slot in the plane
    raan = j * spread / P
    u0 = 2 * np.pi * (k / (T // P) + j * F / T)
    u = u0[None, :] + n * t_s[:, None]
    i = np.radians(i_deg)
    x = np.cos(raan) * np.cos(u) - np.sin(raan) * np.sin(u) * np.cos(i)
    y = np.sin(raan) * np.cos(u) + np.cos(raan) * np.sin(u) * np.cos(i)
    z = np.sin(u) * np.sin(i)
    cn = k == (3 * j) % (T // P)                                               # 1 central node per plane, staggered
    return r * np.stack([x, y, z], axis=-1), cn


def in_range(a, b):
    """True where a and b are within RANGE_KM and the line between them clears the Earth."""
    d = b - a
    dist = np.linalg.norm(d, axis=-1)
    t = np.clip(-(a * d).sum(-1) / dist**2, 0, 1)                              # closest point of the line to the centre
    closest = np.linalg.norm(a + t[..., None] * d, axis=-1)
    return (dist <= RANGE_KM) & (closest >= RE + GRAZING_KM)


rows = []
for h, i_deg, pattern in CANDIDATES:
    coord, is_cn = walker(h, i_deg, pattern)
    row = dict(altitude_km=h, inclination_deg=i_deg, pattern=pattern)
    # sensors to coordination layer
    seen = np.stack([in_range(sensors[m][:, None, :], coord) for m in range(len(sensors))])   # (7, n_times, T)
    row["sensor_sees_any"] = round(seen.sum(-1).mean(), 1)
    row["sensor_sees_cn_pct"] = round(100 * seen[:, :, is_cn].any(-1).mean(), 1)
    # ground stations (ECEF -> ECI with the GMST of each time)
    for name, (lat, lon) in STATIONS.items():
        la, lo = np.radians(lat), np.radians(lon) + gmst
        g = RE * np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.full_like(lo, np.sin(la))], -1)
        d = coord - g[:, None, :]
        elev = np.degrees(np.arcsin((d * g[:, None, :]).sum(-1) / (np.linalg.norm(d, axis=-1) * RE)))
        row[f"station_{name}_pct"] = round(100 * (elev >= MASK_DEG).any(-1).mean(), 1)
    # neighbour distances inside the layer (chord at the equator)
    spread = 360 if pattern == "delta" else 180
    row["in_plane_km"] = round(2 * (RE + h) * np.sin(np.radians(360 / (T // P)) / 2))
    row["cross_plane_km"] = round(2 * (RE + h) * np.sin(np.radians(spread / P) / 2))
    rows.append(row)
    print(row)

pd.DataFrame(rows).to_csv(OUT / "coordination_layer_candidates.csv", index=False)
