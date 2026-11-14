"""Account credentials: environment variables first, then the .env file (KEY=value lines, never printed or written).

The .env file is the one named by the environment variable THESIS_ENV_FILE, else <thesis folder>/master-thesis/.env
(next to the Latex folder). Variable names: see code/.env.example.
"""
import os
from pathlib import Path

from wildfire_central_node_placement.paths import THESIS

DEFAULT_ENV_FILE = THESIS / "master-thesis" / ".env"


def env_file():
    return Path(os.environ.get("THESIS_ENV_FILE", DEFAULT_ENV_FILE))


def read_env_file(path=None):
    """KEY=value pairs of the .env file ('export ' prefixes, comments and quotes removed); {} if missing."""
    path = path or env_file()
    out = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition("=")
        out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return out


def credentials(*keys):
    """Values of the given variables; stops with a message naming the missing ones."""
    values = {k: os.environ.get(k) for k in keys}
    if not all(values.values()):
        file_values = read_env_file()
        values = {k: values[k] or file_values.get(k) for k in keys}
    missing = [k for k in keys if not values[k]]
    if missing:
        raise SystemExit(f"missing {missing}: set them in the environment or in {env_file()}")
    return tuple(values[k] for k in keys)
