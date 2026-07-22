"""Repository for a single field day's data on disk (§3.3, §4.7).

One directory per field day (BR-01):

    <root>/<slug>/
    ├─ fieldday.json
    ├─ stations.json
    ├─ received_qsos.json
    ├─ overrides.json
    ├─ sync_log.json
    └─ exports/

The repository is pure persistence: it loads and saves domain objects and
appends to the sync log. It contains no matching or status logic — that
lives in the sync engine (phase 6). The root directory is injectable for
testability; by default it is :func:`app.config.fielddays_dir`.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from app import config
from app.core.models import QSO, FieldDay, Override, Station, to_iso_z, utc_now
from app.storage.json_store import read_json, write_json_atomic

FIELDDAY_FILE = "fieldday.json"
STATIONS_FILE = "stations.json"
QSOS_FILE = "received_qsos.json"
OVERRIDES_FILE = "overrides.json"
SYNC_LOG_FILE = "sync_log.json"
EXPORTS_DIR = "exports"

# Keep the sync log from growing without bound during a long field day.
MAX_SYNC_LOG_ENTRIES = 5000


def slugify(name: str) -> str:
    """Turn a field day name into a filesystem-safe directory name."""
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "fieldday"


class FieldDayRepository:
    """Persistence for one field day directory."""

    def __init__(self, slug: str, root_dir: Path | None = None) -> None:
        self.slug = slug
        self.root_dir = root_dir if root_dir is not None else config.fielddays_dir()
        self.dir = self.root_dir / slug

    # -- paths ------------------------------------------------------------

    def _path(self, filename: str) -> Path:
        return self.dir / filename

    @property
    def exports_dir(self) -> Path:
        return self.dir / EXPORTS_DIR

    def exists(self) -> bool:
        return self._path(FIELDDAY_FILE).exists()

    # -- field day --------------------------------------------------------

    def load_fieldday(self) -> FieldDay | None:
        data = read_json(self._path(FIELDDAY_FILE))
        if data is None or not isinstance(data, dict):
            return None
        try:
            return FieldDay.from_dict(data)
        except ValueError:
            # Structurally valid JSON but semantically broken: treat like
            # corruption — do not crash, report as missing.
            return None

    def save_fieldday(self, fieldday: FieldDay) -> None:
        fieldday.updated_at = utc_now()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self._path(FIELDDAY_FILE), fieldday.to_dict())

    # -- stations ---------------------------------------------------------

    def load_stations(self) -> list[Station]:
        data = read_json(self._path(STATIONS_FILE))
        if not isinstance(data, list):
            return []
        stations: list[Station] = []
        for entry in data:
            try:
                stations.append(Station.from_dict(entry))
            except (ValueError, TypeError):
                continue  # skip broken entries, keep the rest
        return stations

    def save_stations(self, stations: list[Station]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            self._path(STATIONS_FILE), [s.to_dict() for s in stations]
        )

    # -- QSOs -------------------------------------------------------------

    def load_qsos(self) -> list[QSO]:
        data = read_json(self._path(QSOS_FILE))
        if not isinstance(data, list):
            return []
        qsos: list[QSO] = []
        for entry in data:
            try:
                qsos.append(QSO.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return qsos

    def save_qsos(self, qsos: list[QSO]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self._path(QSOS_FILE), [q.to_dict() for q in qsos])

    # -- overrides --------------------------------------------------------

    def load_overrides(self) -> list[Override]:
        data = read_json(self._path(OVERRIDES_FILE))
        if not isinstance(data, list):
            return []
        overrides: list[Override] = []
        for entry in data:
            try:
                overrides.append(Override.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return overrides

    def save_overrides(self, overrides: list[Override]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            self._path(OVERRIDES_FILE), [o.to_dict() for o in overrides]
        )

    # -- sync log ---------------------------------------------------------

    def load_sync_log(self) -> list[dict[str, Any]]:
        data = read_json(self._path(SYNC_LOG_FILE))
        return data if isinstance(data, list) else []

    def append_sync_log(self, event_type: str, details: dict[str, Any]) -> None:
        """Append one event to the sync log (import reports, sync results...)."""
        log = self.load_sync_log()
        log.append(
            {
                "at_utc": to_iso_z(utc_now()),
                "type": event_type,
                "details": details,
            }
        )
        if len(log) > MAX_SYNC_LOG_ENTRIES:
            log = log[-MAX_SYNC_LOG_ENTRIES:]
        self.dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self._path(SYNC_LOG_FILE), log)


# ---------------------------------------------------------------------------
# Repository management: create / list / open
# ---------------------------------------------------------------------------

def unique_slug(name: str, root_dir: Path | None = None) -> str:
    """Slug for *name*, made unique within *root_dir* by numeric suffix."""
    root = root_dir if root_dir is not None else config.fielddays_dir()
    base = slugify(name)
    slug = base
    counter = 1
    while (root / slug).exists():
        counter += 1
        slug = f"{base}-{counter}"
    return slug


def create_fieldday(fieldday: FieldDay, root_dir: Path | None = None) -> FieldDayRepository:
    """Create the directory structure for a new field day and persist it.

    The matrix starts empty (BR-10): stations, QSOs and overrides files are
    initialized as empty lists.
    """
    repo = FieldDayRepository(fieldday.id, root_dir=root_dir)
    if repo.exists():
        raise ValueError(f"Field day directory already exists: {repo.dir}")
    repo.save_fieldday(fieldday)
    repo.save_stations([])
    repo.save_qsos([])
    repo.save_overrides([])
    write_json_atomic(repo._path(SYNC_LOG_FILE), [])
    return repo


def list_fielddays(root_dir: Path | None = None) -> list[FieldDay]:
    """All field days found on disk, newest created first.

    Unreadable directories are skipped silently — one broken field day must
    never make the whole application unusable.
    """
    root = root_dir if root_dir is not None else config.fielddays_dir()
    if not root.exists():
        return []
    result: list[FieldDay] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        fd = FieldDayRepository(entry.name, root_dir=root).load_fieldday()
        if fd is not None:
            result.append(fd)
    result.sort(key=lambda fd: fd.created_at, reverse=True)
    return result
