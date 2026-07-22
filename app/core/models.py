"""Domain data models (§4) with UTC handling and JSON (de)serialization.

Rules enforced here:

- BR-06: all timestamps are stored and compared in UTC. Naive datetimes are
  rejected with a ValueError; tz-aware non-UTC datetimes are converted to UTC.
- Serialization is ISO-8601 with a ``Z`` suffix, e.g. ``2026-06-06T14:32:11Z``.
- ``from_dict`` is defensive: missing required fields or invalid enum values
  raise ``ValueError`` with the field name, so corrupt files surface clearly.

These models contain no I/O and no business decisions beyond field-level
validation; matching and status resolution live in ``matching.py`` and
``sync_engine.py`` (later phases).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from app.config import DEFAULT_UDP_HOST, DEFAULT_UDP_PORT
from app.core.status import DEFAULT_STATUS_COLORS

# Default bands for a new field day (§8.2), matching the existing Excel.
DEFAULT_SELECTED_BANDS: list[str] = ["160m", "80m", "40m"]

# Default freshness threshold (§5.5). N1MM only broadcasts on logged
# contacts, so quiet periods are normal; 300 s is a starting point and is
# user-configurable.
DEFAULT_FRESHNESS_THRESHOLD_SECONDS = 300


# ---------------------------------------------------------------------------
# UTC helpers (BR-06)
# ---------------------------------------------------------------------------

def ensure_utc(value: datetime, field_name: str = "timestamp") -> datetime:
    """Validate that *value* is tz-aware and return it converted to UTC.

    Naive datetimes are rejected: silently assuming a timezone is exactly
    the class of bug BR-06 exists to prevent.
    """
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name}: expected datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name}: naive datetime not allowed; tzinfo must be set")
    return value.astimezone(timezone.utc)


def to_iso_z(value: datetime | None) -> str | None:
    """Serialize a datetime as ISO-8601 UTC with ``Z`` suffix (or None)."""
    if value is None:
        return None
    utc = ensure_utc(value)
    return utc.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def parse_iso_z(value: str | None, field_name: str = "timestamp") -> datetime | None:
    """Parse an ISO-8601 string into a UTC datetime (or None).

    Accepts a ``Z`` suffix or an explicit offset. A string without any
    timezone information is rejected (BR-06).
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: expected string, got {type(value).__name__}")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name}: invalid ISO-8601 datetime {value!r}") from exc
    return ensure_utc(parsed, field_name)


def utc_now() -> datetime:
    """Current time in UTC (single point of truth, easy to mock in tests)."""
    return datetime.now(timezone.utc)


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data or data[key] is None:
        raise ValueError(f"Missing required field: {key!r}")
    return data[key]


# ---------------------------------------------------------------------------
# Enums for source/type fields
# ---------------------------------------------------------------------------

class StationSource(StrEnum):
    EXCEL = "excel"
    CSV = "csv"
    MANUAL = "manual"


class QsoSource(StrEnum):
    N1MM_UDP = "n1mm_udp"
    ADIF = "adif"


class OverrideType(StrEnum):
    MANUAL_WORKED = "manual_worked"
    MANUAL_NOT_WORKED = "manual_not_worked"
    EXCLUDED = "excluded"


def _parse_enum(enum_cls: type[StrEnum], value: Any, field_name: str) -> StrEnum:
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise ValueError(
            f"{field_name}: invalid value {value!r}; allowed: {allowed}"
        ) from None


# ---------------------------------------------------------------------------
# FieldDay (§4.1) — fieldday.json
# ---------------------------------------------------------------------------

@dataclass
class FieldDay:
    id: str
    name: str
    start_utc: datetime
    end_utc: datetime
    location: str = ""
    event_callsign: str = ""
    organizer_club: str = ""
    display_timezone: str = "Europe/Brussels"
    selected_bands: list[str] = field(default_factory=lambda: list(DEFAULT_SELECTED_BANDS))
    n1mm_udp_host: str = DEFAULT_UDP_HOST
    n1mm_udp_port: int = DEFAULT_UDP_PORT
    freshness_threshold_seconds: int = DEFAULT_FRESHNESS_THRESHOLD_SECONDS
    strict_callsign_matching: bool = False
    status_colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_STATUS_COLORS))
    last_sync_utc: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    remarks: str = ""
    operator_notes: str = ""
    closed: bool = False  # closed field day: viewing only, no changes

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("FieldDay.id must not be empty")
        if not self.name or not self.name.strip():
            raise ValueError("FieldDay.name must not be empty")
        self.start_utc = ensure_utc(self.start_utc, "FieldDay.start_utc")
        self.end_utc = ensure_utc(self.end_utc, "FieldDay.end_utc")
        if self.end_utc <= self.start_utc:
            raise ValueError("FieldDay.end_utc must be after start_utc")
        if self.last_sync_utc is not None:
            self.last_sync_utc = ensure_utc(self.last_sync_utc, "FieldDay.last_sync_utc")
        self.created_at = ensure_utc(self.created_at, "FieldDay.created_at")
        self.updated_at = ensure_utc(self.updated_at, "FieldDay.updated_at")
        if not isinstance(self.selected_bands, list) or not self.selected_bands:
            raise ValueError("FieldDay.selected_bands must be a non-empty list")
        if not (1 <= int(self.n1mm_udp_port) <= 65535):
            raise ValueError("FieldDay.n1mm_udp_port must be 1..65535")
        if int(self.freshness_threshold_seconds) <= 0:
            raise ValueError("FieldDay.freshness_threshold_seconds must be > 0")

    def contains_utc(self, ts: datetime) -> bool:
        """True when *ts* falls inside the field day period (BR-07, inclusive)."""
        ts = ensure_utc(ts, "timestamp")
        return self.start_utc <= ts <= self.end_utc

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "event_callsign": self.event_callsign,
            "organizer_club": self.organizer_club,
            "start_utc": to_iso_z(self.start_utc),
            "end_utc": to_iso_z(self.end_utc),
            "display_timezone": self.display_timezone,
            "selected_bands": list(self.selected_bands),
            "n1mm_udp_host": self.n1mm_udp_host,
            "n1mm_udp_port": self.n1mm_udp_port,
            "freshness_threshold_seconds": self.freshness_threshold_seconds,
            "strict_callsign_matching": self.strict_callsign_matching,
            "status_colors": dict(self.status_colors),
            "last_sync_utc": to_iso_z(self.last_sync_utc),
            "created_at": to_iso_z(self.created_at),
            "updated_at": to_iso_z(self.updated_at),
            "remarks": self.remarks,
            "operator_notes": self.operator_notes,
            "closed": self.closed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldDay":
        return cls(
            id=str(_require(data, "id")),
            name=str(_require(data, "name")),
            start_utc=parse_iso_z(_require(data, "start_utc"), "FieldDay.start_utc"),
            end_utc=parse_iso_z(_require(data, "end_utc"), "FieldDay.end_utc"),
            location=str(data.get("location", "")),
            event_callsign=str(data.get("event_callsign", "")),
            organizer_club=str(data.get("organizer_club", "")),
            display_timezone=str(data.get("display_timezone", "Europe/Brussels")),
            selected_bands=list(data.get("selected_bands") or DEFAULT_SELECTED_BANDS),
            n1mm_udp_host=str(data.get("n1mm_udp_host", DEFAULT_UDP_HOST)),
            n1mm_udp_port=int(data.get("n1mm_udp_port", DEFAULT_UDP_PORT)),
            freshness_threshold_seconds=int(
                data.get("freshness_threshold_seconds", DEFAULT_FRESHNESS_THRESHOLD_SECONDS)
            ),
            strict_callsign_matching=bool(data.get("strict_callsign_matching", False)),
            status_colors=dict(data.get("status_colors") or DEFAULT_STATUS_COLORS),
            last_sync_utc=parse_iso_z(data.get("last_sync_utc"), "FieldDay.last_sync_utc"),
            created_at=parse_iso_z(data.get("created_at"), "FieldDay.created_at") or utc_now(),
            updated_at=parse_iso_z(data.get("updated_at"), "FieldDay.updated_at") or utc_now(),
            remarks=str(data.get("remarks", "")),
            operator_notes=str(data.get("operator_notes", "")),
            closed=bool(data.get("closed", False)),
        )


# ---------------------------------------------------------------------------
# Station (§4.2) — stations.json
# ---------------------------------------------------------------------------

@dataclass
class Station:
    original_callsign: str
    normalized_callsign: str
    name: str = ""
    club: str = ""
    category: str = ""
    section: str = ""
    remarks: str = ""
    source: StationSource = StationSource.MANUAL
    added_at: datetime = field(default_factory=utc_now)
    active: bool = True

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.original_callsign or not self.original_callsign.strip():
            raise ValueError("Station.original_callsign must not be empty")
        if not self.normalized_callsign or not self.normalized_callsign.strip():
            raise ValueError("Station.normalized_callsign must not be empty")
        self.source = _parse_enum(StationSource, self.source, "Station.source")
        self.added_at = ensure_utc(self.added_at, "Station.added_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_callsign": self.original_callsign,
            "normalized_callsign": self.normalized_callsign,
            "name": self.name,
            "club": self.club,
            "category": self.category,
            "section": self.section,
            "remarks": self.remarks,
            "source": self.source.value,
            "added_at": to_iso_z(self.added_at),
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Station":
        return cls(
            original_callsign=str(_require(data, "original_callsign")),
            normalized_callsign=str(_require(data, "normalized_callsign")),
            name=str(data.get("name", "")),
            club=str(data.get("club", "")),
            category=str(data.get("category", "")),
            section=str(data.get("section", "")),
            remarks=str(data.get("remarks", "")),
            source=_parse_enum(StationSource, data.get("source", "manual"), "Station.source"),
            added_at=parse_iso_z(data.get("added_at"), "Station.added_at") or utc_now(),
            active=bool(data.get("active", True)),
        )


# ---------------------------------------------------------------------------
# QSO (§4.3) — received_qsos.json
# ---------------------------------------------------------------------------

@dataclass
class QSO:
    qso_id: str
    original_callsign: str
    normalized_callsign: str
    band: str
    frequency_khz: float
    mode: str
    timestamp_utc: datetime
    source: QsoSource
    source_station: str = ""
    is_original: bool = True
    is_claimed: bool = True
    contest_name: str = ""
    raw_message: str = ""
    received_at_utc: datetime = field(default_factory=utc_now)
    deleted: bool = False

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.qso_id or not str(self.qso_id).strip():
            raise ValueError("QSO.qso_id must not be empty")
        if not self.original_callsign or not self.original_callsign.strip():
            raise ValueError("QSO.original_callsign must not be empty")
        if not self.normalized_callsign or not self.normalized_callsign.strip():
            raise ValueError("QSO.normalized_callsign must not be empty")
        if not self.band or not self.band.strip():
            raise ValueError("QSO.band must not be empty")
        if float(self.frequency_khz) <= 0:
            raise ValueError("QSO.frequency_khz must be > 0")
        self.source = _parse_enum(QsoSource, self.source, "QSO.source")
        self.timestamp_utc = ensure_utc(self.timestamp_utc, "QSO.timestamp_utc")
        self.received_at_utc = ensure_utc(self.received_at_utc, "QSO.received_at_utc")

    def to_dict(self) -> dict[str, Any]:
        return {
            "qso_id": self.qso_id,
            "original_callsign": self.original_callsign,
            "normalized_callsign": self.normalized_callsign,
            "band": self.band,
            "frequency_khz": self.frequency_khz,
            "mode": self.mode,
            "timestamp_utc": to_iso_z(self.timestamp_utc),
            "source": self.source.value,
            "source_station": self.source_station,
            "is_original": self.is_original,
            "is_claimed": self.is_claimed,
            "contest_name": self.contest_name,
            "raw_message": self.raw_message,
            "received_at_utc": to_iso_z(self.received_at_utc),
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QSO":
        return cls(
            qso_id=str(_require(data, "qso_id")),
            original_callsign=str(_require(data, "original_callsign")),
            normalized_callsign=str(_require(data, "normalized_callsign")),
            band=str(_require(data, "band")),
            frequency_khz=float(_require(data, "frequency_khz")),
            mode=str(data.get("mode", "")),
            timestamp_utc=parse_iso_z(_require(data, "timestamp_utc"), "QSO.timestamp_utc"),
            source=_parse_enum(QsoSource, _require(data, "source"), "QSO.source"),
            source_station=str(data.get("source_station", "")),
            is_original=bool(data.get("is_original", True)),
            is_claimed=bool(data.get("is_claimed", True)),
            contest_name=str(data.get("contest_name", "")),
            raw_message=str(data.get("raw_message", "")),
            received_at_utc=parse_iso_z(data.get("received_at_utc"), "QSO.received_at_utc")
            or utc_now(),
            deleted=bool(data.get("deleted", False)),
        )


# ---------------------------------------------------------------------------
# Override (§4.4) — overrides.json; key = normalized_callsign + band
# ---------------------------------------------------------------------------

@dataclass
class Override:
    normalized_callsign: str
    band: str
    override_type: OverrideType
    reason: str = ""
    set_by: str = ""
    set_at_utc: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.normalized_callsign or not self.normalized_callsign.strip():
            raise ValueError("Override.normalized_callsign must not be empty")
        if not self.band or not self.band.strip():
            raise ValueError("Override.band must not be empty")
        self.override_type = _parse_enum(
            OverrideType, self.override_type, "Override.override_type"
        )
        self.set_at_utc = ensure_utc(self.set_at_utc, "Override.set_at_utc")

    @property
    def key(self) -> tuple[str, str]:
        """The (normalized_callsign, band) key this override applies to (BR-05)."""
        return (self.normalized_callsign, self.band)

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_callsign": self.normalized_callsign,
            "band": self.band,
            "override_type": self.override_type.value,
            "reason": self.reason,
            "set_by": self.set_by,
            "set_at_utc": to_iso_z(self.set_at_utc),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Override":
        return cls(
            normalized_callsign=str(_require(data, "normalized_callsign")),
            band=str(_require(data, "band")),
            override_type=_parse_enum(
                OverrideType, _require(data, "override_type"), "Override.override_type"
            ),
            reason=str(data.get("reason", "")),
            set_by=str(data.get("set_by", "")),
            set_at_utc=parse_iso_z(data.get("set_at_utc"), "Override.set_at_utc") or utc_now(),
        )


# ---------------------------------------------------------------------------
# AppSettings (§4.6) — app_settings.json (storage layer follows in phase 4)
# ---------------------------------------------------------------------------

@dataclass
class PublishSettings:
    enabled: bool = False
    repo: str = ""
    branch: str = "main"
    path: str = ""
    auto_interval_minutes: int = 0     # 0 = manual publishing only
    include_private: bool = False      # §10.3: remarks/notes weglaten = default
    api_base: str = ""                 # leeg = api.github.com (tests overschrijven)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "repo": self.repo,
            "branch": self.branch,
            "path": self.path,
            "auto_interval_minutes": self.auto_interval_minutes,
            "include_private": self.include_private,
            "api_base": self.api_base,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PublishSettings":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            repo=str(data.get("repo", "")),
            branch=str(data.get("branch", "main")),
            path=str(data.get("path", "")),
            auto_interval_minutes=int(data.get("auto_interval_minutes", 0)),
            include_private=bool(data.get("include_private", False)),
            api_base=str(data.get("api_base", "")),
        )


@dataclass
class AppSettings:
    ui_language: str = "nl"  # default UI language: Dutch (Flemish)
    n1mm_udp_host: str = DEFAULT_UDP_HOST
    n1mm_udp_port: int = DEFAULT_UDP_PORT
    freshness_threshold_seconds: int = DEFAULT_FRESHNESS_THRESHOLD_SECONDS
    auto_sync_enabled: bool = True
    strict_callsign_matching: bool = False
    default_selected_bands: list[str] = field(
        default_factory=lambda: list(DEFAULT_SELECTED_BANDS)
    )
    status_colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_STATUS_COLORS))
    export_folder: str = ""
    last_active_field_day: str = ""
    publish: PublishSettings = field(default_factory=PublishSettings)

    def validate(self) -> None:
        if self.ui_language not in ("nl", "en", "fr"):
            raise ValueError("AppSettings.ui_language must be one of: nl, en, fr")
        if not (1 <= int(self.n1mm_udp_port) <= 65535):
            raise ValueError("AppSettings.n1mm_udp_port must be 1..65535")
        if int(self.freshness_threshold_seconds) <= 0:
            raise ValueError("AppSettings.freshness_threshold_seconds must be > 0")

    def __post_init__(self) -> None:
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ui_language": self.ui_language,
            "n1mm_udp_host": self.n1mm_udp_host,
            "n1mm_udp_port": self.n1mm_udp_port,
            "freshness_threshold_seconds": self.freshness_threshold_seconds,
            "auto_sync_enabled": self.auto_sync_enabled,
            "strict_callsign_matching": self.strict_callsign_matching,
            "default_selected_bands": list(self.default_selected_bands),
            "status_colors": dict(self.status_colors),
            "export_folder": self.export_folder,
            "last_active_field_day": self.last_active_field_day,
            "publish": self.publish.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppSettings":
        data = data or {}
        return cls(
            ui_language=str(data.get("ui_language", "nl")),
            n1mm_udp_host=str(data.get("n1mm_udp_host", DEFAULT_UDP_HOST)),
            n1mm_udp_port=int(data.get("n1mm_udp_port", DEFAULT_UDP_PORT)),
            freshness_threshold_seconds=int(
                data.get("freshness_threshold_seconds", DEFAULT_FRESHNESS_THRESHOLD_SECONDS)
            ),
            auto_sync_enabled=bool(data.get("auto_sync_enabled", True)),
            strict_callsign_matching=bool(data.get("strict_callsign_matching", False)),
            default_selected_bands=list(
                data.get("default_selected_bands") or DEFAULT_SELECTED_BANDS
            ),
            status_colors=dict(data.get("status_colors") or DEFAULT_STATUS_COLORS),
            export_folder=str(data.get("export_folder", "")),
            last_active_field_day=str(data.get("last_active_field_day", "")),
            publish=PublishSettings.from_dict(data.get("publish")),
        )
