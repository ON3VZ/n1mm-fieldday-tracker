"""Application configuration: platform detection and filesystem locations.

This module is the single source of truth for all filesystem paths used by
the application (see project instructions §4.7). No other module may
hardcode platform-specific paths.

Layout on disk:

    <appdata>/N1MM Field Day Tracker/
    ├─ app_settings.json
    └─ fielddays/
       └─ <fieldday_slug>/
          ├─ fieldday.json
          ├─ stations.json
          ├─ received_qsos.json
          ├─ overrides.json
          ├─ sync_log.json
          └─ exports/

Where <appdata> is:
    - Windows: %LOCALAPPDATA%
    - Linux:   $XDG_DATA_HOME, falling back to ~/.local/share
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "N1MM Field Day Tracker"

# Default network settings for the N1MM UDP listener (see §5).
# The tracker runs on the same laptop as N1MM, so we bind to localhost by
# default (safe choice on untrusted networks). Users who want to receive
# broadcasts from other PCs can change this to "0.0.0.0" in the settings.
DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 12060

# Default local web server (see §3.1).
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8765


def is_windows() -> bool:
    """Return True when running on Windows."""
    return sys.platform.startswith("win")


def is_linux() -> bool:
    """Return True when running on Linux."""
    return sys.platform.startswith("linux")


def platform_name() -> str:
    """Human-readable platform name, used for logging/diagnostics."""
    if is_windows():
        return "Windows"
    if is_linux():
        return "Linux"
    # macOS and others are not officially supported (§1.2) but must not crash.
    return sys.platform


def appdata_root() -> Path:
    """Return the platform-specific base directory for application data.

    The result does NOT include the application name; see :func:`app_data_dir`.
    """
    if is_windows():
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata)
        # Extremely unusual, but never crash on a missing env var.
        return Path.home() / "AppData" / "Local"

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home)
    return Path.home() / ".local" / "share"


def app_data_dir() -> Path:
    """Directory holding all persistent data for this application."""
    return appdata_root() / APP_NAME


def app_settings_path() -> Path:
    """Path of the global settings file (see §4.6)."""
    return app_data_dir() / "app_settings.json"


def fielddays_dir() -> Path:
    """Directory containing one subdirectory per field day (BR-01)."""
    return app_data_dir() / "fielddays"


def fieldday_dir(slug: str) -> Path:
    """Directory for a single field day, identified by its slug."""
    if not slug or slug.strip() != slug or os.sep in slug or "/" in slug:
        raise ValueError(f"Invalid field day slug: {slug!r}")
    return fielddays_dir() / slug


def static_view_dir() -> Path:
    """Directory containing the static web view (index.html, app.js, ...).

    Resolves correctly both in development and inside a PyInstaller bundle
    (sys._MEIPASS, see §12.2).
    """
    if hasattr(sys, "_MEIPASS"):  # PyInstaller onefile/onedir bundle
        return Path(sys._MEIPASS) / "app" / "view" / "static"
    return Path(__file__).resolve().parent / "view" / "static"


def ensure_app_dirs() -> Path:
    """Create the base application data directories if missing.

    Returns the application data directory. Safe to call repeatedly.
    """
    data_dir = app_data_dir()
    fielddays_dir().mkdir(parents=True, exist_ok=True)
    return data_dir
