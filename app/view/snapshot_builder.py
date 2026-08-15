"""Build ``snapshot.json`` — the contract between engine and view (§10.1).

One self-contained document drives both the local browser UI and the
published GitHub Pages copy; there is exactly ONE implementation of matrix,
filter and color logic (the static view), fed by this snapshot.

Variants:

- ``readonly``: set for the published copy; the view disables overrides and
  editing (§10.2).
- ``include_private=False``: omit station remarks, field day remarks and
  operator notes, and override reasons from the snapshot — for publishing
  to a public page (§10.3).

Everything is plain JSON types; datetimes are ISO-8601 ``Z`` strings.
"""

from __future__ import annotations

from typing import Any

from app.core.callsign import normalize_callsign
from app.core.models import FieldDay, Station, to_iso_z, utc_now
from app.core.status import Status
from app.core.sync_engine import CellState, SyncEngine
from app.version import APP_VERSION

SCHEMA_VERSION = 1

# Default English legend labels; the view translates via i18n keys.
LEGEND: dict[str, str] = {
    Status.NOT_WORKED: "Not worked",
    Status.WORKED_BY_N1MM: "Worked (N1MM)",
    Status.MANUAL_WORKED: "Worked (manual)",
    Status.MANUAL_NOT_WORKED: "Not worked (manual)",
    Status.EXCLUDED: "Excluded",
}

_WORKED_STATUSES = {Status.WORKED_BY_N1MM, Status.MANUAL_WORKED}


def _cell_dict(cell: CellState, include_private: bool) -> dict[str, Any]:
    data: dict[str, Any] = {"status": cell.status.value}
    if cell.worked_qso is not None:
        qso = cell.worked_qso
        data["at_utc"] = to_iso_z(qso.timestamp_utc)
        data["mode"] = qso.mode
        data["freq_khz"] = qso.frequency_khz
        data["source"] = qso.source_station or qso.source.value
        data["qso_count"] = cell.qso_count
    if cell.override is not None:
        data["manual"] = True
        if include_private and cell.override.reason:
            data["reason"] = cell.override.reason
        if cell.override.set_by:
            data["set_by"] = cell.override.set_by
    return data


def _empty_band_stats() -> dict[str, int]:
    return {"total": 0, "worked": 0, "open": 0, "manual_overrides": 0, "excluded": 0}


def _station_qsos(engine: SyncEngine, normalized: str) -> list[dict[str, Any]]:
    """All qualifying QSOs for one station, oldest first (views 4 and 5)."""
    from app.core.matching import match_qso

    result: list[dict[str, Any]] = []
    for qso in engine.qsos_by_id.values():
        key, _ = match_qso(qso, engine.fieldday, engine.station_index)
        if key is None or key[0] != normalized:
            continue
        result.append(
            {
                "band": qso.band,
                "at_utc": to_iso_z(qso.timestamp_utc),
                "mode": qso.mode,
                "freq_khz": qso.frequency_khz,
                "source": qso.source_station or qso.source.value,
            }
        )
    result.sort(key=lambda entry: entry["at_utc"])
    return result


def build_snapshot(
    engine: SyncEngine,
    sources: list[dict[str, Any]] | None = None,
    *,
    readonly: bool = False,
    include_private: bool = True,
    show_station_category: bool = True,
) -> dict[str, Any]:
    """Build the snapshot document from the engine's current state."""
    fieldday: FieldDay = engine.fieldday
    bands = list(fieldday.selected_bands)

    # -- field day block --------------------------------------------------
    field_day_block: dict[str, Any] = {
        "name": fieldday.name,
        "location": fieldday.location,
        "event_callsign": fieldday.event_callsign,
        "organizer_club": fieldday.organizer_club,
        "start_utc": to_iso_z(fieldday.start_utc),
        "end_utc": to_iso_z(fieldday.end_utc),
        "display_timezone": fieldday.display_timezone,
        "bands": bands,
        "closed": fieldday.closed,
    }
    if include_private:
        field_day_block["remarks"] = fieldday.remarks
        field_day_block["operator_notes"] = fieldday.operator_notes

    # -- sources (from the UDP listener) ----------------------------------
    sources_block: list[dict[str, Any]] = []
    for source in sources or []:
        entry = dict(source)
        if "last_seen_utc" in entry and not isinstance(entry["last_seen_utc"], str):
            entry["last_seen_utc"] = to_iso_z(entry["last_seen_utc"])
        sources_block.append(entry)

    # -- stations + cells, preserving participant-list order --------------
    strict = fieldday.strict_callsign_matching
    stations_block: list[dict[str, Any]] = []
    per_band = {band: _empty_band_stats() for band in bands}
    per_category: dict[str, dict[str, int]] = {}
    stations_complete = 0
    stations_partial = 0
    stations_untouched = 0
    total_worked = 0
    total_manual = 0
    total_excluded = 0

    listed: set[str] = set()
    for station in engine.stations:
        if not station.active:
            continue
        normalized = normalize_callsign(station.original_callsign, strict=strict)
        if normalized is None or normalized in listed:
            continue
        if engine.station_index.get(normalized) is not station:
            continue  # duplicate normalization: first station won (engine rule)
        listed.add(normalized)

        cells: dict[str, Any] = {}
        worked_cells = 0
        countable_cells = 0  # cells that are not excluded
        for band in bands:
            cell = engine.get_cell(normalized, band)
            if cell is None:
                cell = CellState()
            cells[band] = _cell_dict(cell, include_private)

            band_stats = per_band[band]
            band_stats["total"] += 1
            if cell.status in _WORKED_STATUSES:
                band_stats["worked"] += 1
                worked_cells += 1
                total_worked += 1
                countable_cells += 1
            elif cell.status == Status.EXCLUDED:
                band_stats["excluded"] += 1
                total_excluded += 1
            else:
                band_stats["open"] += 1
                countable_cells += 1
            if cell.override is not None:
                band_stats["manual_overrides"] += 1
                total_manual += 1

        category = station.category or ""
        cat_stats = per_category.setdefault(
            category,
            {"stations": 0, "total": 0, "worked": 0, "open": 0,
             "manual_overrides": 0, "excluded": 0},
        )
        cat_stats["stations"] += 1
        for band in bands:
            status = Status(cells[band]["status"])
            cat_stats["total"] += 1
            if status in _WORKED_STATUSES:
                cat_stats["worked"] += 1
            elif status == Status.EXCLUDED:
                cat_stats["excluded"] += 1
            else:
                cat_stats["open"] += 1
            if cells[band].get("manual"):
                cat_stats["manual_overrides"] += 1

        if countable_cells > 0 and worked_cells == countable_cells:
            stations_complete += 1
        elif worked_cells == 0:
            stations_untouched += 1
        else:
            stations_partial += 1

        entry: dict[str, Any] = {
            "callsign": station.original_callsign,
            "normalized": normalized,
            "category": station.category,
            "section": station.section,
            "cells": cells,
            "qsos": _station_qsos(engine, normalized),
        }
        if include_private:
            entry["remarks"] = station.remarks
        stations_block.append(entry)

    total_cells = len(stations_block) * len(bands)

    stats_block: dict[str, Any] = {
        "stations_total": len(stations_block),
        "bands_total": len(bands),
        "cells_total": total_cells,
        "cells_worked": total_worked,
        "cells_open": total_cells - total_worked - total_excluded,
        "manual_overrides": total_manual,
        "cells_excluded": total_excluded,
        "stations_complete": stations_complete,
        "stations_partial": stations_partial,
        "stations_untouched": stations_untouched,
        "per_band": per_band,
        "per_category": per_category,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": to_iso_z(utc_now()),
        # Version of the application that produced this snapshot. Travels
        # with the document so the published page shows it too — handy when
        # someone reports a problem against a page you did not generate.
        "app_version": APP_VERSION,
        "readonly": readonly,
        # Display preference (§4.6): show the light-grey category line under
        # each callsign in the matrix. Travels with the snapshot so the
        # published copy renders identically to the local view.
        "show_station_category": show_station_category,
        "field_day": field_day_block,
        "sources": sources_block,
        "stations": stations_block,
        "stats": stats_block,
        "all_bands": _all_band_names(),
        "legend": {status.value: label for status, label in LEGEND.items()},
        "colors": dict(engine.fieldday.status_colors),
    }

def _all_band_names() -> list[str]:
    from app.core.band_plan import ALL_BAND_NAMES

    return list(ALL_BAND_NAMES)
