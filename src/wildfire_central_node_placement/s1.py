"""S1 simulator run: inputs, satellite states, station contacts and the time from an observation to the ground.

The run folder is set in config/simulation.yaml (paths.SIM_RUN). Contacts of stations added to the frozen baseline
after the run come from the S1 post-processing (extra_access_windows.csv, 04_extra_station_contacts.py).
"""
import numpy as np
import pandas as pd

from wildfire_central_node_placement.orbits import TERRA_RELAY_WAIT_MIN
from wildfire_central_node_placement.paths import GROUND_STATIONS_FILE, S1_TABLES, SIM_INPUTS, SIM_RUN

# simulator name -> our name
SAT = {"AQUA": "Aqua", "TERRA": "Terra", "NPP": "Suomi NPP", "NOAA 20": "NOAA-20", "NOAA 21": "NOAA-21",
       "SENTINEL 3A": "Sentinel-3A", "SENTINEL 3B": "Sentinel-3B"}
EVENT_NAMES = {"larouco": "Larouco", "molezuelas": "Molezuelas", "oimbra": "Oímbra", "piodao": "Piódão",
               "red_canyon": "Red Canyon", "derdara": "Derdara", "silifke": "Silifke"}   # figure labels


def run_stations():
    """Station id -> name of the simulator run."""
    return pd.read_csv(SIM_RUN / "06_ground_stations.csv").set_index("id").name


def access_windows():
    """Station contacts of the run (elevation >= 10 deg), rise and set parsed."""
    return pd.read_csv(SIM_RUN / "11_access_windows.csv", parse_dates=["rise_utc", "set_utc"])


class S1Run:
    """Inputs and outputs of the S1 run, with the frozen-baseline rule for the time to ground.

    sensors.stored_data_downlink may be changed in place for sensitivity cases; minutes_to_ground reads it.
    """

    def __init__(self):
        st = pd.read_csv(GROUND_STATIONS_FILE)
        self.direct_readout = st[(st.station_set == "real + direct readout") & (st.link == "direct")].station.tolist()   # frozen baseline
        self.events = pd.read_csv(SIM_INPUTS / "events.csv", parse_dates=["reference_utc"])
        self.sensors = pd.read_csv(SIM_INPUTS / "s1_sensors.csv").set_index("satellite")
        self.states = pd.read_csv(SIM_RUN / "02_satellite_states.csv", usecols=["time_utc", "satellite_id", "lat_deg", "lon_deg"],
                                  parse_dates=["time_utc"])
        self.states["satellite"] = self.states.satellite_id.map(SAT)
        contacts = access_windows()
        contacts["satellite"] = contacts.satellite_id.map(SAT)
        contacts["station"] = contacts.ground_station_id.map(run_stations())
        extra = S1_TABLES / "extra_access_windows.csv"          # stations added after the run (04_extra_station_contacts.py)
        if extra.exists():
            e = pd.read_csv(extra, parse_dates=["rise_utc", "set_utc"]).rename(columns={"ground_station_name": "station"})
            e["satellite"] = e.satellite_id.map(SAT)
            contacts = pd.concat([contacts, e], ignore_index=True)
        self.contacts = contacts

    def minutes_to_ground(self, sat, t):
        """Wait from observation t to the first ground contact, frozen baseline rules."""
        if sat == "Terra":
            return TERRA_RELAY_WAIT_MIN
        c = self.contacts[(self.contacts.satellite == sat) & (self.contacts.set_utc >= t)]
        if self.sensors.loc[sat, "direct_broadcast"]:
            if ((c.station.isin(self.direct_readout)) & (c.rise_utc <= t)).any():
                return 0
        stored = c[c.station.isin(self.sensors.loc[sat, "stored_data_downlink"].split(";"))]
        if stored.empty:
            return np.nan                                  # no contact before the end of the run
        return max(0, (stored.rise_utc.min() - t).total_seconds() / 60)
