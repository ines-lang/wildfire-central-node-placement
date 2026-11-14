"""Boxes, distances, clustering and map projection.

Several distance formulas are used on purpose (each result was produced with one of them; they differ in the last
decimals). Pick the one named in the method:
    dist_km          equirectangular, 111.2 km per degree (FIRMS event selection, clustering, FY-3D matching)
    local_km         local plane around a point, 111.32 / 110.57 km per degree (S0 perimeters)
    great_circle_km  spherical law of cosines, R = 6371.0 km (overpass geometry, Level-2 fire mask)
    haversine_km     haversine, radius given (S1 passes: 6371 km; SEVIRI membership: mean radius 6371.0088 km)
"""
import numpy as np
import pandas as pd

KM_PER_DEG_LAT = 111.2
EARTH_RADIUS_KM = 6371.0
EARTH_MEAN_RADIUS_KM = 6371.0088          # IUGG mean radius
WEB_MERCATOR_RADIUS_M = 6378137.0         # Web Mercator sphere (map tiles)
WGS84_A_KM, WGS84_F = 6378.137, 1 / 298.257223563


# ---- boxes ----
def in_box(lat, lon, box, margin=0.0):
    """True where (lat, lon) lies inside the box {lat_min, lat_max, lon_min, lon_max} grown by margin degrees."""
    return (lat.between(box["lat_min"] - margin, box["lat_max"] + margin)
            & lon.between(box["lon_min"] - margin, box["lon_max"] + margin))


def grow_box(box, margin_deg):
    return {"lat_min": box["lat_min"] - margin_deg, "lat_max": box["lat_max"] + margin_deg,
            "lon_min": box["lon_min"] - margin_deg, "lon_max": box["lon_max"] + margin_deg}


# ---- distances ----
def dist_km(lat, lon, lats, lons):
    """Equirectangular distance in km from one point to arrays of points (fine at fire scale)."""
    dy = (lats - lat) * KM_PER_DEG_LAT
    dx = (lons - lon) * KM_PER_DEG_LAT * np.cos(np.radians(lat))
    return np.hypot(dx, dy)


def extent_km(lats, lons):
    """Diagonal of the bounding box of the detections, in km (equirectangular)."""
    dy = (lats.max() - lats.min()) * KM_PER_DEG_LAT
    dx = (lons.max() - lons.min()) * KM_PER_DEG_LAT * np.cos(np.radians(lats.mean()))
    return float(np.hypot(dx, dy))


def local_km(lat0, lon0):
    """Function (lon, lat) -> (x, y) in km on a local plane centred at (lat0, lon0)."""
    k = np.cos(np.radians(lat0))
    return lambda x, y: ((np.asarray(x) - lon0) * 111.32 * k, (np.asarray(y) - lat0) * 110.57)


def great_circle_km(lat1, lon1, lat2, lon2):
    """Great-circle distance (spherical law of cosines), R = 6371.0 km."""
    p1, p2, dl = np.radians(lat1), np.radians(lat2), np.radians(lon2 - lon1)
    return EARTH_RADIUS_KM * np.arccos(np.clip(np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl), -1, 1))


def haversine_km(lat1, lon1, lat2, lon2, radius_km=EARTH_RADIUS_KM):
    """Great-circle distance (haversine), degrees in, km out; broadcasts."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * radius_km * np.arcsin(np.sqrt(a))


def min_distance_km(lat, lon, ref_lat, ref_lon, chunk=2000):
    """Haversine distance (mean Earth radius) from every (lat, lon) to the nearest reference point."""
    lat, lon = np.asarray(lat)[:, None], np.asarray(lon)[:, None]
    ref_lat, ref_lon = np.asarray(ref_lat)[None, :], np.asarray(ref_lon)[None, :]
    out = np.empty(len(lat))
    for i in range(0, len(lat), chunk):
        d = haversine_km(lat[i:i + chunk], lon[i:i + chunk], ref_lat, ref_lon, EARTH_MEAN_RADIUS_KM)
        out[i:i + chunk] = d.min(axis=1)
    return out


def hull_area_km2(x, y):
    """Convex hull area of planar points in km (monotone chain + shoelace)."""
    pts = sorted(set(zip(x, y)))

    def half(points):
        h = []
        for p in points:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        return h[:-1]

    hull = np.array(half(pts) + half(pts[::-1]))
    hx, hy = hull[:, 0], hull[:, 1]
    return 0.5 * abs(np.dot(hx, np.roll(hy, 1)) - np.dot(hy, np.roll(hx, 1)))


# ---- clustering ----
def grid_clusters(lats, lons, cell_km):
    """Put detections on a grid of about cell_km x cell_km and label connected groups of
    occupied cells (8 neighbours). All times pooled: a cluster is the footprint of one
    fire (or of fires that touched) over the whole period. Labels 1, 2, ... by size."""
    ci = np.floor(lats * KM_PER_DEG_LAT / cell_km).astype(int)
    cj = np.floor(lons * KM_PER_DEG_LAT * np.cos(np.radians(lats)) / cell_km).astype(int)
    cells = set(zip(ci, cj))
    cell_label, n = {}, 0
    for start in cells:
        if start in cell_label:
            continue
        n += 1
        cell_label[start] = n
        stack = [start]
        while stack:
            i, j = stack.pop()
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    nb = (i + di, j + dj)
                    if nb in cells and nb not in cell_label:
                        cell_label[nb] = n
                        stack.append(nb)
    labels = np.array([cell_label[c] for c in zip(ci, cj)])
    by_size = pd.Series(labels).value_counts().index          # relabel: 1 = most detections
    return pd.Series(labels).map({old: new for new, old in enumerate(by_size, start=1)}).to_numpy()


# ---- projection and Earth geometry ----
def merc_x(lon):
    """Longitude (deg) to Web Mercator x (m), the projection of the map tiles."""
    return WEB_MERCATOR_RADIUS_M * np.radians(lon)


def merc_y(lat):
    return WEB_MERCATOR_RADIUS_M * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def station_ecef(lat, lon):
    """WGS84 ECEF position (km, on the ellipsoid) and local up vector of a ground station."""
    la, lo = np.radians(lat), np.radians(lon)
    e2 = WGS84_F * (2 - WGS84_F)
    n = WGS84_A_KM / np.sqrt(1 - e2 * np.sin(la) ** 2)
    xyz = np.array([n * np.cos(la) * np.cos(lo), n * np.cos(la) * np.sin(lo), n * (1 - e2) * np.sin(la)])
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    return xyz, up
