"""CSV export of the full station×band matrix (§10.4).

One row per station+band combination, with the columns from the spec.
Written with UTF-8 BOM and semicolons so Belgian Excel opens it correctly
with one double-click.
"""

from __future__ import annotations

import csv
import io

from app.core.status import Status
from app.core.sync_engine import SyncEngine

COLUMNS = [
    "callsign", "normalized_callsign", "category", "section", "band",
    "status", "source", "source_station", "mode", "frequency_khz",
    "worked_timestamp_utc", "manual_override", "remarks",
]


def build_csv(engine: SyncEngine) -> str:
    """Return the CSV content as text (caller writes/streams it)."""
    from app.core.models import to_iso_z

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(COLUMNS)

    strict = engine.fieldday.strict_callsign_matching
    from app.core.callsign import normalize_callsign

    for station in engine.stations:
        if not station.active:
            continue
        normalized = normalize_callsign(station.original_callsign, strict=strict)
        if normalized is None or engine.station_index.get(normalized) is not station:
            continue
        for band in engine.fieldday.selected_bands:
            cell = engine.get_cell(normalized, band)
            if cell is None:
                continue
            qso = cell.worked_qso
            writer.writerow([
                station.original_callsign,
                normalized,
                station.category,
                station.section,
                band,
                cell.status.value,
                qso.source.value if qso else "",
                qso.source_station if qso else "",
                qso.mode if qso else "",
                qso.frequency_khz if qso else "",
                to_iso_z(qso.timestamp_utc) if qso else "",
                cell.override.override_type.value if cell.override else "",
                station.remarks,
            ])
    return "\ufeff" + buffer.getvalue()  # BOM: Excel opent dit correct
