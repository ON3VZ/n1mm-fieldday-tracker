"""Parse N1MM Logger+ UDP broadcast packets (§5.2–§5.4).

Root-tag filtering is MANDATORY (§5.3): ``lookupinfo`` packets have a field
structure identical to ``contactinfo`` but are sent *before* a QSO is
logged, on the same recommended port. Only ``contactinfo``,
``contactreplace`` and ``contactdelete`` are processed; every other root tag
(``lookupinfo``, ``RadioInfo``, ``AppInfo``, ``spot``, ``dynamicresults``,
...) is reported as ignored, with its tag name, for the sync log.

Field mapping (§5.4):

- ``ID`` → ``qso_id`` (32-hex GUID; dedup and update key)
- ``timestamp`` → UTC (format ``YYYY-MM-DD HH:MM:SS``)
- ``rxfreq`` → kHz. **Units of 10 Hz**: 352519 → 3525.19 kHz.
  ``txfreq`` is the fallback when rxfreq is missing or 0.
- band is ALWAYS derived from the frequency (BR-08); the locale-dependent
  ``<band>`` text field is never used.
- ``IsClaimedQso`` 0 → X-QSO → ``is_claimed=False`` (does not count)
- ``IsOriginal`` false → forwarded via "All Computers"
- ``StationName`` → ``source_station`` (netbios name of the *sending* PC)

The parser never raises on packet content: malformed input yields an ERROR
result. A single bad packet must never stop the listener (§5.5).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from app.core.band_plan import band_from_frequency_khz
from app.core.callsign import normalize_callsign
from app.core.models import QSO, QsoSource, utc_now

PROCESSED_ROOT_TAGS = {"contactinfo", "contactreplace", "contactdelete"}


class PacketKind(StrEnum):
    CONTACT = "contact"          # contactinfo → upsert QSO
    REPLACE = "replace"          # contactreplace → upsert QSO (same ID)
    DELETE = "delete"            # contactdelete → mark deleted
    IGNORED = "ignored"          # other root tags, incl. lookupinfo
    ERROR = "error"              # unparseable or semantically unusable


@dataclass
class ParsedPacket:
    kind: PacketKind
    qso: QSO | None = None       # for CONTACT / REPLACE
    qso_id: str | None = None    # for DELETE
    root_tag: str = ""           # for IGNORED (which tag was skipped)
    reason: str = ""             # for ERROR / IGNORED
    raw: str = ""                # always: the raw packet text (§5.5)


def _decode(data: bytes | str) -> str:
    if isinstance(data, str):
        return data
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _fields(root: ET.Element) -> dict[str, str]:
    """Child tag (lowercased) → stripped text. Case-insensitive lookup."""
    result: dict[str, str] = {}
    for child in root:
        tag = child.tag.strip().lower()
        if tag not in result:  # first occurrence wins
            result[tag] = (child.text or "").strip()
    return result


def _parse_timestamp(value: str) -> datetime | None:
    """``YYYY-MM-DD HH:MM:SS`` (UTC per N1MM spec); tolerant of stray spaces."""
    text = value.strip()
    # The docs' own examples contain "16 :43:38" print artifacts; real
    # packets do not, but being tolerant costs nothing:
    text = text.replace(" :", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _frequency_khz(fields: dict[str, str]) -> float | None:
    """rxfreq in units of 10 Hz → kHz; txfreq as fallback (§5.4)."""
    for key in ("rxfreq", "txfreq"):
        raw = fields.get(key, "")
        if not raw:
            continue
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            continue
        if value > 0:
            return value / 100.0  # 10 Hz units → kHz
    return None


def _is_true(value: str, default: bool) -> bool:
    text = value.strip().lower()
    if text in ("1", "true", "yes"):
        return True
    if text in ("0", "false", "no"):
        return False
    return default


def parse_packet(data: bytes | str) -> ParsedPacket:
    """Parse one UDP payload. Never raises on content."""
    raw = _decode(data)

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return ParsedPacket(
            kind=PacketKind.ERROR, reason=f"invalid XML: {exc}", raw=raw
        )

    root_tag = root.tag.strip().lower()
    if root_tag not in PROCESSED_ROOT_TAGS:
        # §5.3: mandatory root-tag filter; count as ignored packet type.
        return ParsedPacket(
            kind=PacketKind.IGNORED,
            root_tag=root_tag,
            reason=f"ignored packet type: {root_tag}",
            raw=raw,
        )

    fields = _fields(root)

    qso_id = fields.get("id", "")
    if not qso_id:
        return ParsedPacket(
            kind=PacketKind.ERROR, reason="missing <ID>", raw=raw
        )

    if root_tag == "contactdelete":
        return ParsedPacket(kind=PacketKind.DELETE, qso_id=qso_id, raw=raw)

    # contactinfo / contactreplace share the same field structure (§5.2).
    call = fields.get("call", "")
    if not call:
        return ParsedPacket(
            kind=PacketKind.ERROR, reason="missing <call>", raw=raw
        )

    timestamp = _parse_timestamp(fields.get("timestamp", ""))
    if timestamp is None:
        return ParsedPacket(
            kind=PacketKind.ERROR,
            reason=f"invalid <timestamp>: {fields.get('timestamp', '')!r}",
            raw=raw,
        )

    frequency_khz = _frequency_khz(fields)
    if frequency_khz is None:
        return ParsedPacket(
            kind=PacketKind.ERROR, reason="missing or zero rxfreq/txfreq", raw=raw
        )

    band = band_from_frequency_khz(frequency_khz)
    if band is None:
        # §8.2: outside every band → "band not determinable", not processed.
        return ParsedPacket(
            kind=PacketKind.ERROR,
            reason=f"band not determinable for {frequency_khz} kHz",
            raw=raw,
        )

    normalized = normalize_callsign(call, strict=False)
    qso = QSO(
        qso_id=qso_id,
        original_callsign=call,
        normalized_callsign=normalized if normalized is not None else call.upper(),
        band=band,
        frequency_khz=frequency_khz,
        mode=fields.get("mode", ""),
        timestamp_utc=timestamp,
        source=QsoSource.N1MM_UDP,
        source_station=fields.get("stationname", ""),
        is_original=_is_true(fields.get("isoriginal", ""), default=True),
        is_claimed=_is_true(fields.get("isclaimedqso", ""), default=True),
        contest_name=fields.get("contestname", ""),
        raw_message=raw,
        received_at_utc=utc_now(),
    )
    kind = PacketKind.REPLACE if root_tag == "contactreplace" else PacketKind.CONTACT
    return ParsedPacket(kind=kind, qso=qso, raw=raw)
