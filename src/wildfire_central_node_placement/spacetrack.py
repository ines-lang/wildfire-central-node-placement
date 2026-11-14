"""Space-Track session (EO census download). Credentials: SPACETRACK_USERNAME, SPACETRACK_PASSWORD."""
import json
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

from wildfire_central_node_placement.credentials import credentials

BASE = "https://www.space-track.org"


def session():
    """Logged-in opener; call query(opener, path) with it, then logout(opener)."""
    user, password = credentials("SPACETRACK_USERNAME", "SPACETRACK_PASSWORD")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    with opener.open(f"{BASE}/ajaxauth/login", timeout=60,
                     data=urllib.parse.urlencode({"identity": user, "password": password}).encode()) as r:
        if b"Failed" in r.read():
            raise SystemExit("Space-Track login failed (check the credentials)")
    return opener


def query(opener, path):
    """GET BASE/basicspacedata/query/<path> as JSON."""
    with opener.open(f"{BASE}/basicspacedata/query/{path}", timeout=300) as r:
        return json.load(r)


def logout(opener):
    opener.open(f"{BASE}/ajaxauth/logout", timeout=60)
