"""Import the participant list from Excel (.xlsx) or CSV (§7).

Column recognition is header-based, case- and whitespace-insensitive, with
synonyms (§7.1). Band columns are any header that parses as a valid band via
``band_plan.parse_band_label``; they determine the *proposal* for the field
day's ``selected_bands``, but their cell contents are never imported — the
matrix always starts empty (BR-10).

Validation (§7.2) never blocks the import: problems are reported per row in
the import report. Duplicates after normalization are reported explicitly.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.core.band_plan import parse_band_label
from app.core.callsign import normalize_callsign
from app.core.models import Station, StationSource

logger = logging.getLogger(__name__)

# Normalized header → model field. Header normalization: lowercase, trimmed,
# trailing dots removed, inner whitespace collapsed.
_HEADER_SYNONYMS: dict[str, str] = {
    "call": "callsign",
    "callsign": "callsign",
    "roepnaam": "callsign",
    "categorie": "category",
    "category": "category",
    "sectie": "section",
    "section": "section",
    "opm": "remarks",
    "opmerking": "remarks",
    "opmerkingen": "remarks",
    "remarks": "remarks",
    "name": "name",
    "naam": "name",
    "club": "club",
}


@dataclass
class RowIssue:
    """One reported problem for one input row."""

    row_number: int  # 1-based, as shown in Excel
    callsign: str
    reason: str


@dataclass
class StationImportResult:
    """Report of one import run (§7.2). Errors never block the import."""

    stations: list[Station] = field(default_factory=list)
    band_columns: list[str] = field(default_factory=list)  # proposal for selected_bands
    issues: list[RowIssue] = field(default_factory=list)
    rows_read: int = 0
    source: str = ""

    def to_report_dict(self) -> dict:
        """Summary for the sync log / UI."""
        return {
            "source": self.source,
            "rows_read": self.rows_read,
            "imported": len(self.stations),
            "band_columns": list(self.band_columns),
            "issues": [
                {"row": i.row_number, "callsign": i.callsign, "reason": i.reason}
                for i in self.issues
            ],
        }


def _normalize_header(value) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split()).strip().lower()
    return text.rstrip(".")


def _map_headers(headers: list) -> tuple[dict[int, str], list[str]]:
    """Map column index → model field, and collect band columns in order.

    Unknown columns (e.g. ``Nummer``) are ignored.
    """
    mapping: dict[int, str] = {}
    band_columns: list[str] = []
    for idx, raw in enumerate(headers):
        norm = _normalize_header(raw)
        if not norm:
            continue
        if norm in _HEADER_SYNONYMS:
            fieldname = _HEADER_SYNONYMS[norm]
            if fieldname not in mapping.values():  # first occurrence wins
                mapping[idx] = fieldname
            continue
        band = parse_band_label(str(raw))
        if band is not None and band not in band_columns:
            band_columns.append(band)
    return mapping, band_columns


def _cell_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _rows_to_result(
    rows: list[list],
    source: StationSource,
    strict: bool,
    first_data_row_number: int,
) -> StationImportResult:
    result = StationImportResult(source=source.value)
    if not rows:
        result.issues.append(RowIssue(1, "", "no data found"))
        return result

    header_map, band_columns = _map_headers(rows[0])
    result.band_columns = band_columns

    if "callsign" not in header_map.values():
        result.issues.append(
            RowIssue(1, "", "no callsign column found (expected: Call / Callsign / Roepnaam)")
        )
        return result

    seen: dict[str, tuple[int, str]] = {}  # normalized → (row_number, original)
    for offset, row in enumerate(rows[1:]):
        row_number = first_data_row_number + offset
        values = {fieldname: "" for fieldname in _HEADER_SYNONYMS.values()}
        for idx, fieldname in header_map.items():
            if idx < len(row):
                values[fieldname] = _cell_str(row[idx])

        callsign = values["callsign"]
        if not callsign and not any(values.values()):
            continue  # entirely empty row: skip silently
        result.rows_read += 1

        if not callsign:
            result.issues.append(RowIssue(row_number, "", "callsign is missing"))
            continue

        normalized = normalize_callsign(callsign, strict=strict)
        if normalized is None:
            result.issues.append(
                RowIssue(row_number, callsign, "not a plausible callsign")
            )
            continue

        if normalized in seen:
            prev_row, prev_original = seen[normalized]
            result.issues.append(
                RowIssue(
                    row_number,
                    callsign,
                    f"duplicate after normalization: same station as "
                    f"{prev_original!r} on row {prev_row} (normalized: {normalized})",
                )
            )
            continue
        seen[normalized] = (row_number, callsign)

        result.stations.append(
            Station(
                original_callsign=callsign,
                normalized_callsign=normalized,
                name=values["name"],
                club=values["club"],
                category=values["category"],
                section=values["section"],
                remarks=values["remarks"],
                source=source,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def import_stations_from_excel(
    path: Path | str,
    strict: bool = False,
    sheet_name: str | None = None,
) -> StationImportResult:
    """Import stations from an ``.xlsx`` file.

    Uses the given sheet, or the first sheet when *sheet_name* is None.
    Raises ``ValueError`` when the file cannot be opened as Excel; row-level
    problems go into the report instead.
    """
    from openpyxl import load_workbook  # imported lazily: optional at runtime

    path = Path(path)
    try:
        workbook = load_workbook(path, data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError(f"Cannot open Excel file {path.name}: {exc}") from exc

    try:
        if sheet_name is not None:
            if sheet_name not in workbook.sheetnames:
                raise ValueError(
                    f"Sheet {sheet_name!r} not found in {path.name}; "
                    f"available: {', '.join(workbook.sheetnames)}"
                )
            sheet = workbook[sheet_name]
        else:
            sheet = workbook[workbook.sheetnames[0]]

        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()

    return _rows_to_result(
        rows, StationSource.EXCEL, strict=strict, first_data_row_number=2
    )


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def import_stations_from_csv(path: Path | str, strict: bool = False) -> StationImportResult:
    """Import stations from a CSV file with the same column logic (§7.1).

    Delimiter is auto-detected (``,`` or ``;`` — Belgian Excel exports use
    ``;``); encoding UTF-8 with BOM tolerance.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # Legacy exports: fall back to Latin-1, which never fails.
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise ValueError(f"Cannot read CSV file {path.name}: {exc}") from exc

    lines = text.splitlines()
    if not lines:
        result = StationImportResult(source=StationSource.CSV.value)
        result.issues.append(RowIssue(1, "", "no data found"))
        return result

    try:
        dialect = csv.Sniffer().sniff(lines[0], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # default comma

    reader = csv.reader(lines, dialect)
    rows = [list(row) for row in reader]
    return _rows_to_result(
        rows, StationSource.CSV, strict=strict, first_data_row_number=2
    )
