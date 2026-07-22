"""Load and save global application settings (§4.6).

A missing or corrupt settings file falls back to defaults; the application
must always be able to start. The corrupt-file backup is handled by
``json_store.read_json``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app import config
from app.core.models import AppSettings
from app.storage.json_store import read_json, write_json_atomic

logger = logging.getLogger(__name__)


def load_app_settings(path: Path | None = None) -> AppSettings:
    """Load settings; return defaults when missing, corrupt or invalid."""
    settings_path = path if path is not None else config.app_settings_path()
    data = read_json(settings_path)
    if data is None or not isinstance(data, dict):
        return AppSettings()
    try:
        return AppSettings.from_dict(data)
    except (ValueError, TypeError) as exc:
        logger.error("Invalid settings in %s (%s); using defaults", settings_path, exc)
        return AppSettings()


def save_app_settings(settings: AppSettings, path: Path | None = None) -> None:
    """Persist settings atomically."""
    settings.validate()
    settings_path = path if path is not None else config.app_settings_path()
    write_json_atomic(settings_path, settings.to_dict())
