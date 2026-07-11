"""On-disk configuration for connecting to a Toon.

Stores the Toon's host and SSH password in a per-user config file (NOT in the
repo). Resolution order for every value: explicit argument > environment
variable > config file > built-in default.

    TOON_HOST      overrides the host
    TOON_SSH_PASS  overrides the SSH password

Config file location:
    Windows : %APPDATA%\\toon-remote\\config.json
    other   : $XDG_CONFIG_HOME/toon-remote/config.json  (default ~/.config)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "toon"  # the well-known rooted-Toon factory password


def config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "toon-remote" / "config.json"


def load() -> dict:
    try:
        return json.loads(config_path().read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save(host: str, password: str = DEFAULT_PASSWORD,
         username: str = DEFAULT_USERNAME) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"host": host, "username": username, "password": password},
                   indent=2),
        "utf-8",
    )
    try:  # best-effort: keep the password file private on POSIX
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def get_host(explicit: Optional[str] = None) -> Optional[str]:
    return explicit or os.environ.get("TOON_HOST") or load().get("host")


def get_password(explicit: Optional[str] = None) -> str:
    return (explicit or os.environ.get("TOON_SSH_PASS")
            or load().get("password") or DEFAULT_PASSWORD)


def get_username(explicit: Optional[str] = None) -> str:
    return explicit or load().get("username") or DEFAULT_USERNAME


def require_host(explicit: Optional[str] = None) -> str:
    host = get_host(explicit)
    if not host:
        raise SystemExit(
            "No Toon host configured. Pass --host, set TOON_HOST, or run the "
            "app's config screen / edit " + str(config_path())
        )
    return host
