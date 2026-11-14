"""Map of the frozen ground segment (event-agnostic rule of 10 Nov 2026), the events and the later southern cases.

Stored-data stations (the satellites dump their recorded data there) and direct-readout stations that feed a public
near-real-time fire product, with the reception footprint of each direct-readout station: the area where a VIIRS
satellite at 830 km is above 10 deg elevation, so a fire there can be received while the satellite sees it.
Inputs: ground_stations.csv (set "real + direct readout"), the simulator events.csv,
        the candidates' ground truth (southern network cases)
Output: figures/03_ground_segment_map.png
Usage:  python pipeline/3_ground_segment/02_ground_segment_map.py
Basemap: Esri World Gray Canvas, zoom 2 (downloaded at run time; the tiles at latitudes below -66 deg are not in
the local tile cache, so this figure needs the network).
"""
import contextily as cx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from wildfire_central_node_placement.geo import merc_x, merc_y
from wildfire_central_node_placement.orbits import MIN_ELEVATION_DEG
from wildfire_central_node_placement.paths import GROUND_FIGURES, GROUND_STATIONS_FILE, SIM_INPUTS, ensure
from wildfire_central_node_placement.registry import ground_truth

R_E, ALT_KM, MASK_DEG = 6371.0, 830.0, float(MIN_ELEVATION_DEG)
COL = {"stored": "#16263d", "direct": "#2a78d6", "event": "#d9480f", "later": "#d9480f"}


def merc(lat, lon):
    """Web Mercator (x, y) in m, latitude clipped to +-84 deg."""
    return merc_x(lon), merc_y(np.clip(lat, -84, 84))


def footprint(lat, lon):
    """Circle of Earth central angle where the satellite is above the elevation mask."""
    e = np.radians(MASK_DEG)
    lam = np.arccos(R_E / (R_E + ALT_KM) * np.cos(e)) - e
    az = np.linspace(0, 2 * np.pi, 181)
    la1, lo1 = np.radians(lat), np.radians(lon)
    la2 = np.arcsin(np.sin(la1) * np.cos(lam) + np.cos(la1) * np.sin(lam) * np.cos(az))
    lo2 = lo1 + np.arctan2(np.sin(az) * np.sin(lam) * np.cos(la1), np.cos(lam) - np.sin(la1) * np.sin(la2))
    lo2 = (np.degrees(lo2) + 180) % 360 - 180
    return np.degrees(la2), lo2, np.degrees(lam) * 111.2


st = pd.read_csv(GROUND_STATIONS_FILE)
st = st[(st.station_set == "real + direct readout") & st.lat.notna()].drop_duplicates("station")
ev = pd.read_csv(SIM_INPUTS / "events.csv")
gt = ground_truth()
later = pd.DataFrame([("Eastern Cape", -31.24, 27.98), ("Ghanzi", gt.loc["ghanzi", "lat"], gt.loc["ghanzi", "lon"]),
                      ("El Questro", gt.loc["el_questro", "lat"], gt.loc["el_questro", "lon"])], columns=["name", "lat", "lon"])

fig, ax = plt.subplots(figsize=(12, 6.6))
radius_km = None
for r in st[st.link == "direct"].itertuples():
    la, lo, radius_km = footprint(r.lat, r.lon)
    for seg in np.split(np.arange(len(lo)), np.where(np.abs(np.diff(lo)) > 180)[0] + 1):   # split at the date line
        x, y = merc(la[seg], lo[seg])
        ax.fill(x, y, color=COL["direct"], alpha=0.10, lw=0)
        ax.plot(x, y, color=COL["direct"], lw=0.6, alpha=0.6)
S1_SATS = {"Suomi NPP", "NOAA-20", "NOAA-21", "Aqua", "Sentinel-3A", "Sentinel-3B"}
st["serves_s1"] = st.satellites.fillna("").str.split(";").apply(lambda v: bool(S1_SATS & set(v)))
for sel, marker, kw in [((st.link == "stored") & st.serves_s1, "s", dict(color=COL["stored"], edgecolor="white")),
                        ((st.link == "stored") & ~st.serves_s1, "s", dict(facecolor="white", edgecolor=COL["stored"])),
                        (st.link == "direct", "^", dict(color=COL["direct"], edgecolor="white"))]:
    s = st[sel]
    x, y = merc(s.lat.values, s.lon.values)
    ax.scatter(x, y, marker=marker, s=70, lw=0.9, zorder=5, **kw)
x, y = merc(ev.lat.values, ev.lon.values)
ax.scatter(x, y, marker="*", s=180, color=COL["event"], edgecolor="black", lw=0.6, zorder=6)
x, y = merc(later.lat.values, later.lon.values)
ax.scatter(x, y, marker="*", s=180, facecolor="white", edgecolor=COL["later"], lw=1.4, zorder=6)
for r in later.itertuples():
    xx, yy = merc(r.lat, r.lon)
    ax.annotate(r.name, (xx, yy), xytext=(6, -10), textcoords="offset points", fontsize=8)
x0, y0 = merc(-80, -180)
x1, y1 = merc(82, 180)
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
cx.add_basemap(ax, source=cx.providers.Esri.WorldGrayCanvas, zoom=2, attribution_size=5)
ax.set_axis_off()
handles = [Line2D([], [], marker="s", ls="", color=COL["stored"], ms=8, label="Stored-data station of the S1 satellites (Svalbard, Fairbanks, Poker Flat, McMurdo)"),
           Line2D([], [], marker="s", ls="", mfc="white", mec=COL["stored"], ms=8, label="Own stations of FY-3D (S3 sensitivity: Kiruna, Troll, China)"),
           Line2D([], [], marker="^", ls="", color=COL["direct"], ms=8, label="Direct readout feeding a public fire product"),
           plt.Rectangle((0, 0), 1, 1, color=COL["direct"], alpha=0.15,
                         label=f"Live reception area (VIIRS above 10$^\\circ$, radius about {radius_km:,.0f} km)"),
           Line2D([], [], marker="*", ls="", color=COL["event"], mec="black", ms=12, label="Selected event (S0 to S2)"),
           Line2D([], [], marker="*", ls="", mfc="white", mec=COL["later"], ms=12, label="Southern network case (before S3)")]
ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.9)
ax.set_title("Frozen ground segment: one rule everywhere, independent of the events (Terra uses only the TDRSS relay)",
             loc="left", fontsize=10)
fig.tight_layout()
fig.savefig(ensure(GROUND_FIGURES) / "03_ground_segment_map.png", dpi=220)
print(f"written; footprint radius {radius_km:.0f} km; {len(st)} stations")
