"""Tests for app.ingest.station_importer (§7) — phase 5.

Runs against the real reference file ``deelnemerslijst_orig.xlsx`` (fixture
copy) plus synthetic Excel/CSV variants for edge cases.
"""

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.ingest.station_importer import (
    import_stations_from_csv,
    import_stations_from_excel,
)

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_XLSX = FIXTURES / "deelnemerslijst_orig.xlsx"


def write_xlsx(path: Path, rows: list[list]) -> Path:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# The real reference file (§7.1)
# ---------------------------------------------------------------------------

class TestReferenceFile:
    def test_reference_file_present(self):
        assert REFERENCE_XLSX.exists(), "fixture deelnemerslijst_orig.xlsx missing"

    def test_all_38_stations_imported(self):
        result = import_stations_from_excel(REFERENCE_XLSX)
        assert result.rows_read == 38
        assert len(result.stations) == 38
        assert result.issues == []

    def test_band_columns_proposed(self):
        # Headers 40M / 80M / 160M → proposal for selected_bands
        result = import_stations_from_excel(REFERENCE_XLSX)
        assert set(result.band_columns) == {"40m", "80m", "160m"}

    def test_known_stations_mapped_correctly(self):
        result = import_stations_from_excel(REFERENCE_XLSX)
        by_original = {s.original_callsign: s for s in result.stations}
        st = by_original["ON4BAF/P"]
        assert st.normalized_callsign == "ON4BAF"  # /P stripped (loose mode)
        assert st.category == "Open All Band Low Power"
        assert st.section == "RST"
        assert st.source == "excel"

        st2 = by_original["ON4CDZ/P"]
        assert st2.category == "Restricted 12h"
        assert st2.section == "CDZ"

    def test_all_normalized_without_suffix(self):
        # Every participant carries /P; loose normalization must strip it.
        result = import_stations_from_excel(REFERENCE_XLSX)
        for st in result.stations:
            assert st.original_callsign.endswith("/P")
            assert "/" not in st.normalized_callsign

    def test_no_duplicates_in_reference(self):
        result = import_stations_from_excel(REFERENCE_XLSX)
        normalized = [s.normalized_callsign for s in result.stations]
        assert len(normalized) == len(set(normalized))

    def test_strict_mode_keeps_suffix(self):
        result = import_stations_from_excel(REFERENCE_XLSX, strict=True)
        st = next(s for s in result.stations if s.original_callsign == "ON4BAF/P")
        assert st.normalized_callsign == "ON4BAF/P"

    def test_report_dict(self):
        report = import_stations_from_excel(REFERENCE_XLSX).to_report_dict()
        assert report["imported"] == 38
        assert report["rows_read"] == 38
        assert report["issues"] == []
        assert report["source"] == "excel"


# ---------------------------------------------------------------------------
# Header recognition (§7.1)
# ---------------------------------------------------------------------------

class TestHeaderRecognition:
    def test_synonyms_and_case_insensitivity(self, tmp_path):
        path = write_xlsx(
            tmp_path / "syn.xlsx",
            [
                ["  CALLSIGN ", "Category", "SECTION", "Opmerking", "Naam", "CLUB"],
                ["ON4AA/P", "QRP", "AAA", "nota", "Jan", "UBA-AAA"],
            ],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 1
        st = result.stations[0]
        assert st.original_callsign == "ON4AA/P"
        assert st.category == "QRP"
        assert st.section == "AAA"
        assert st.remarks == "nota"
        assert st.name == "Jan"
        assert st.club == "UBA-AAA"

    def test_unknown_columns_ignored(self, tmp_path):
        path = write_xlsx(
            tmp_path / "extra.xlsx",
            [
                ["Nummer", "Call", "Willekeurig"],
                [1, "ON4AA/P", "x"],
            ],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 1

    def test_band_headers_detected_but_content_ignored(self, tmp_path):
        # BR-10: cell content of band columns is never imported.
        path = write_xlsx(
            tmp_path / "bands.xlsx",
            [
                ["Call", "40M", "80M", "2m"],
                ["ON4AA/P", "X", "gewerkt", "ja"],
            ],
        )
        result = import_stations_from_excel(path)
        assert result.band_columns == ["40m", "80m", "2m"]
        assert len(result.stations) == 1

    def test_missing_callsign_column_reported(self, tmp_path):
        path = write_xlsx(
            tmp_path / "nocall.xlsx",
            [["Nummer", "categorie"], [1, "QRP"]],
        )
        result = import_stations_from_excel(path)
        assert result.stations == []
        assert any("no callsign column" in i.reason for i in result.issues)


# ---------------------------------------------------------------------------
# Row validation (§7.2)
# ---------------------------------------------------------------------------

class TestRowValidation:
    def test_missing_callsign_reported_with_row_number(self, tmp_path):
        path = write_xlsx(
            tmp_path / "missing.xlsx",
            [
                ["Call", "sectie"],
                ["ON4AA/P", "AAA"],
                ["", "BBB"],          # row 3: missing call, other data present
                ["ON4CC/P", "CCC"],
            ],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 2
        assert len(result.issues) == 1
        assert result.issues[0].row_number == 3
        assert "missing" in result.issues[0].reason

    def test_implausible_callsign_reported(self, tmp_path):
        path = write_xlsx(
            tmp_path / "implausible.xlsx",
            [["Call"], ["ON4AA/P"], ["JANSSENS"]],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 1
        assert result.issues[0].row_number == 3
        assert "plausible" in result.issues[0].reason

    def test_duplicate_after_normalization_reported(self, tmp_path):
        # §7.2 explicitly: ON4BAF and ON4BAF/P in the same list must be flagged.
        path = write_xlsx(
            tmp_path / "dup.xlsx",
            [["Call"], ["ON4BAF"], ["ON4BAF/P"]],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 1
        assert result.stations[0].original_callsign == "ON4BAF"
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.row_number == 3
        assert "duplicate" in issue.reason
        assert "ON4BAF" in issue.reason

    def test_duplicates_allowed_in_strict_mode(self, tmp_path):
        # In strict mode ON4BAF and ON4BAF/P are different stations.
        path = write_xlsx(
            tmp_path / "dupstrict.xlsx",
            [["Call"], ["ON4BAF"], ["ON4BAF/P"]],
        )
        result = import_stations_from_excel(path, strict=True)
        assert len(result.stations) == 2
        assert result.issues == []

    def test_fully_empty_rows_skipped_silently(self, tmp_path):
        path = write_xlsx(
            tmp_path / "empty.xlsx",
            [["Call"], ["ON4AA/P"], [None], [""], ["ON4CC/P"]],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 2
        assert result.rows_read == 2
        assert result.issues == []

    def test_unreadable_file_raises(self, tmp_path):
        bogus = tmp_path / "not_excel.xlsx"
        bogus.write_text("this is not a zip", encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot open Excel"):
            import_stations_from_excel(bogus)

    def test_missing_sheet_raises(self):
        with pytest.raises(ValueError, match="not found"):
            import_stations_from_excel(REFERENCE_XLSX, sheet_name="Bestaat Niet")

    def test_explicit_sheet_name_works(self):
        result = import_stations_from_excel(REFERENCE_XLSX, sheet_name="Blad1")
        assert len(result.stations) == 38


# ---------------------------------------------------------------------------
# CSV (§7.1: same column logic; only callsign is required)
# ---------------------------------------------------------------------------

class TestCsvImport:
    def test_comma_csv(self, tmp_path):
        path = tmp_path / "list.csv"
        path.write_text(
            "callsign,categorie,sectie\nON4AA/P,QRP,AAA\nON4BB/P,Open,BBB\n",
            encoding="utf-8",
        )
        result = import_stations_from_csv(path)
        assert len(result.stations) == 2
        assert result.stations[0].category == "QRP"
        assert result.stations[0].source == "csv"

    def test_semicolon_csv_belgian_excel_export(self, tmp_path):
        path = tmp_path / "list.csv"
        path.write_text(
            "Call;categorie;sectie;40M;80M;160M;Opm.\n"
            "ON4AA/P;QRP;AAA;;;;\n",
            encoding="utf-8",
        )
        result = import_stations_from_csv(path)
        assert len(result.stations) == 1
        assert result.band_columns == ["40m", "80m", "160m"]

    def test_utf8_bom_tolerated(self, tmp_path):
        path = tmp_path / "bom.csv"
        path.write_bytes("Call,Opm.\nON4AA/P,café\n".encode("utf-8-sig"))
        result = import_stations_from_csv(path)
        assert result.stations[0].remarks == "café"

    def test_only_callsign_column_required(self, tmp_path):
        path = tmp_path / "minimal.csv"
        path.write_text("callsign\nON4AA/P\nON4BB/P\n", encoding="utf-8")
        result = import_stations_from_csv(path)
        assert len(result.stations) == 2
        assert result.stations[0].category == ""

    def test_empty_file_reported(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        result = import_stations_from_csv(path)
        assert result.stations == []
        assert any("no data" in i.reason for i in result.issues)

    def test_duplicate_reported_in_csv_too(self, tmp_path):
        path = tmp_path / "dup.csv"
        path.write_text("Call\nON4BAF/P\non4baf\n", encoding="utf-8")
        result = import_stations_from_csv(path)
        assert len(result.stations) == 1
        assert "duplicate" in result.issues[0].reason
