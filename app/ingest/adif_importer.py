"""ADIF import — the safety net for logs that did not arrive live (§6).

Handles real-world ADIF: an optional header terminated by ``<EOH>``, records
terminated by ``<EOR>``, field length notation (``<CALL:6>ON4BAF``), optional
type suffixes (``<FREQ:5:N>``), case-insensitive tags, and an incomplete
last record at EOF (processed when complete enough, otherwise counted as
unparseable — never a crash).

Mapping (§6.1): CALL; QSO_DATE+TIME_ON (ADIF is UTC by definition);
FREQ in **MHz** → ×1000 kHz, with BAND as fallback when FREQ is missing;
MODE; STATION_CALLSIGN or OPERATOR → source_station; CONTEST_ID.

Dedup (§6.2): ADIF records have no GUID. The ``qso_id`` is a hash of
``normalized_callsign + band + timestamp rounded to the minute + mode``.
Normalization for the hash always uses loose mode, so the hash is stable
regardless of the field day's strict-matching setting. An existing id means
the record is skipped and counted as duplicate. Because worked-status is
idempotent (BR-09), any residual double counting is functionally harmless —
but the report must be honest about the numbers.

Classification (unknown station, outside period) reuses the SAME matching
module as the sync engine — no second implementation of those rules.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.core.band_plan import band_from_frequency_khz, parse_band_label
from app.core.callsign import normalize_callsign
from app.core.matching import RejectReason, build_station_index, match_qso
from app.core.models import QSO, FieldDay, QsoSource, Station, utc_now

# <TAG:length> or <TAG:length:type>, plus bare <EOR>/<EOH>
_TAG_RE = re.compile(r"<(?P<name>[A-Za-z0-9_]+)(?::(?P<len>\d+)(?::[^>]*)?)?>")


@dataclass
class AdifImportReport:
    """Honest numbers for the sync log and the UI (§6.3)."""

    records_read: int = 0
    imported: int = 0
    duplicates: int = 0
    outside_period: int = 0
    unknown_station: int = 0      # ignored (BR-03)
    unparseable: int = 0
    no_band: int = 0              # neither usable FREQ nor BAND
    band_not_selected: int = 0    # stored, but currently outside selected bands
    source_file: str = ""

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "records_read": self.records_read,
            "imported": self.imported,
            "duplicates": self.duplicates,
            "outside_period": self.outside_period,
            "unknown_station": self.unknown_station,
            "unparseable": self.unparseable,
            "no_band": self.no_band,
            "band_not_selected": self.band_not_selected,
        }


def adif_qso_id(normalized_callsign: str, band: str, ts: datetime, mode: str) -> str:
    """Deterministic dedup key (§6.2); timestamp rounded to the minute."""
    minute = ts.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
    payload = f"{normalized_callsign}|{band}|{minute}|{mode.strip().upper()}"
    return "adif-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Low-level record scanning
# ---------------------------------------------------------------------------

def _split_records(text: str) -> tuple[list[dict[str, str]], int]:
    """Return (records, unparseable_count).

    A record is a dict of lowercase field name → value. The header (before
    ``<EOH>``) is skipped when present. A trailing record without ``<EOR>``
    is kept when it contains any fields.
    """
    # Skip header if an <EOH> exists (case-insensitive).
    eoh = re.search(r"<EOH>", text, re.IGNORECASE)
    body = text[eoh.end():] if eoh else text

    records: list[dict[str, str]] = []
    unparseable = 0
    current: dict[str, str] = {}
    pos = 0
    while True:
        match = _TAG_RE.search(body, pos)
        if match is None:
            break
        name = match.group("name").lower()
        length = match.group("len")
        if name == "eor" and length is None:
            if current:
                records.append(current)
                current = {}
            pos = match.end()
            continue
        if name == "eoh" and length is None:
            pos = match.end()  # stray header end inside body: skip
            continue
        if length is None:
            # A field tag without a length is not valid ADIF data; skip it.
            pos = match.end()
            continue
        n = int(length)
        value = body[match.end(): match.end() + n]
        if len(value) < n:
            # Truncated file: value shorter than declared. Take what's there
            # but remember this record may be incomplete.
            value = body[match.end():]
        if name not in current:
            current[name] = value.strip()
        pos = match.end() + n

    if current:
        # Incomplete last record (no <EOR> at EOF): keep it — completeness
        # is judged by the field checks later.
        records.append(current)

    return records, unparseable


def _parse_timestamp(fields: dict[str, str]) -> datetime | None:
    date = fields.get("qso_date", "")
    time_on = fields.get("time_on", "")
    if not re.fullmatch(r"\d{8}", date):
        return None
    if re.fullmatch(r"\d{6}", time_on):
        fmt_time = time_on
    elif re.fullmatch(r"\d{4}", time_on):
        fmt_time = time_on + "00"
    else:
        return None
    try:
        return datetime.strptime(date + fmt_time, "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _frequency_and_band(fields: dict[str, str]) -> tuple[float, str] | None:
    """FREQ (MHz) is authoritative; BAND is the fallback (§6.1).

    When only BAND is usable, the band's lower bound serves as the
    representative frequency (the model requires one; the matrix only cares
    about the band).
    """
    freq_raw = fields.get("freq", "")
    if freq_raw:
        try:
            # Round to 1 Hz (3 decimals in kHz) to avoid float artifacts
            # from the MHz→kHz multiplication (3.52519 × 1000 = 3525.1899…).
            khz = round(float(freq_raw.replace(",", ".")) * 1000.0, 3)
        except ValueError:
            khz = None
        if khz is not None and khz > 0:
            band = band_from_frequency_khz(khz)
            if band is not None:
                return khz, band

    band = parse_band_label(fields.get("band", ""))
    if band is not None:
        from app.core.band_plan import BAND_TABLE

        for name, low, _high in BAND_TABLE:
            if name == band:
                return low, band
    return None


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_adif_text(
    text: str,
    fieldday: FieldDay,
    stations: list[Station],
    existing_qso_ids: set[str],
    source_file: str = "",
) -> tuple[list[QSO], AdifImportReport]:
    """Parse *text* and return (new QSOs, report).

    Stored: records for known participants inside the field day period —
    including ones on currently unselected bands (a later band-selection
    change plus resync will pick those up). Not stored: duplicates, unknown
    stations (BR-03), records outside the period, unparseable records.
    """
    report = AdifImportReport(source_file=source_file)
    station_index = build_station_index(
        stations, fieldday.strict_callsign_matching
    )

    records, pre_unparseable = _split_records(text)
    report.unparseable += pre_unparseable

    new_qsos: list[QSO] = []
    seen_ids = set(existing_qso_ids)

    for fields in records:
        report.records_read += 1

        call = fields.get("call", "")
        timestamp = _parse_timestamp(fields)
        if not call or timestamp is None:
            report.unparseable += 1
            continue

        freq_band = _frequency_and_band(fields)
        if freq_band is None:
            report.no_band += 1
            continue
        frequency_khz, band = freq_band

        mode = fields.get("mode", "")
        hash_normalized = normalize_callsign(call, strict=False) or call.upper()
        qso_id = adif_qso_id(hash_normalized, band, timestamp, mode)

        if qso_id in seen_ids:
            report.duplicates += 1
            continue

        qso = QSO(
            qso_id=qso_id,
            original_callsign=call,
            normalized_callsign=hash_normalized,
            band=band,
            frequency_khz=frequency_khz,
            mode=mode,
            timestamp_utc=timestamp,
            source=QsoSource.ADIF,
            source_station=fields.get("station_callsign", "")
            or fields.get("operator", ""),
            contest_name=fields.get("contest_id", ""),
            raw_message="",  # set below to the reconstructed record
            received_at_utc=utc_now(),
        )
        qso.raw_message = " ".join(
            f"<{k.upper()}:{len(v)}>{v}" for k, v in fields.items()
        ) + " <EOR>"

        # Classify with the SAME rules as the sync engine.
        key, reason = match_qso(qso, fieldday, station_index)
        if reason == RejectReason.UNKNOWN_STATION:
            report.unknown_station += 1
            continue
        if reason == RejectReason.OUTSIDE_PERIOD:
            report.outside_period += 1
            continue
        if reason == RejectReason.BAND_NOT_SELECTED:
            report.band_not_selected += 1
            # stored anyway: a later band-selection change + resync counts it

        seen_ids.add(qso_id)
        new_qsos.append(qso)
        report.imported += 1

    return new_qsos, report


def import_adif_file(
    path: Path | str,
    fieldday: FieldDay,
    stations: list[Station],
    existing_qso_ids: set[str],
) -> tuple[list[QSO], AdifImportReport]:
    """Read an ADIF file (tolerant encoding) and import it."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise ValueError(f"Cannot read ADIF file {path.name}: {exc}") from exc
    return import_adif_text(
        text, fieldday, stations, existing_qso_ids, source_file=path.name
    )


def import_adif_to_repository(path: Path | str, repo) -> AdifImportReport:
    """Convenience: import a file into a field day repository (§6.3).

    Loads the field day, stations and existing QSOs, imports, persists the
    new QSOs and writes the report to ``sync_log.json``. Raises ValueError
    when the repository has no field day.
    """
    fieldday = repo.load_fieldday()
    if fieldday is None:
        raise ValueError("Repository has no field day")
    stations = repo.load_stations()
    existing = repo.load_qsos()
    existing_ids = {q.qso_id for q in existing}

    new_qsos, report = import_adif_file(path, fieldday, stations, existing_ids)
    if new_qsos:
        repo.save_qsos(existing + new_qsos)
    repo.append_sync_log("adif_import", report.to_dict())
    return report
