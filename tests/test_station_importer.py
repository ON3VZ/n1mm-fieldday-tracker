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
                ["  CALLSIGN ", "Category", "SECTION", "Opmerking", "Naam",
                 "CLUB", "40M"],
                ["ON4AA/P", "QRP", "AAA", "nota", "Jan", "UBA-AAA", ""],
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
                ["Nummer", "Call", "Willekeurig", "categorie", "sectie", "40M"],
                [1, "ON4AA/P", "x", "QRP", "AAA", ""],
            ],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 1

    def test_band_headers_detected_but_content_ignored(self, tmp_path):
        # BR-10: cell content of band columns is never imported.
        path = write_xlsx(
            tmp_path / "bands.xlsx",
            [
                ["Call", "categorie", "sectie", "40M", "80M", "2m"],
                ["ON4AA/P", "QRP", "AAA", "X", "gewerkt", "ja"],
            ],
        )
        result = import_stations_from_excel(path)
        assert result.band_columns == ["40m", "80m", "2m"]
        assert len(result.stations) == 1

    def test_missing_callsign_column_refuses_file(self, tmp_path):
        """Fase 26: geen roepnaamkolom → het hele bestand wordt geweigerd."""
        path = write_xlsx(
            tmp_path / "nocall.xlsx",
            [["Nummer", "categorie", "sectie", "40M"], [1, "QRP", "AAA", ""]],
        )
        result = import_stations_from_excel(path)
        assert result.format_ok is False
        assert result.stations == []
        assert "Call" in result.missing_columns

    def test_missing_category_and_section_refused(self, tmp_path):
        """Fase 26: vast formaat — categorie en sectie zijn verplicht."""
        path = write_xlsx(
            tmp_path / "bare.xlsx",
            [["Call", "40M"], ["ON4AA/P", ""]],
        )
        result = import_stations_from_excel(path)
        assert result.format_ok is False
        assert result.missing_columns == ["categorie", "sectie"]
        assert result.stations == []
        # De gevonden koppen komen mee terug, zodat de UI kan tonen wat er
        # wél in het bestand stond.
        assert result.found_headers == ["Call", "40M"]

    def test_missing_band_column_refused(self, tmp_path):
        path = write_xlsx(
            tmp_path / "noband.xlsx",
            [["Call", "categorie", "sectie"], ["ON4AA/P", "QRP", "AAA"]],
        )
        result = import_stations_from_excel(path)
        assert result.format_ok is False
        assert any("band" in c for c in result.missing_columns)

    def test_reference_file_matches_the_fixed_format(self):
        """De bestaande deelnemerslijst moet blijven werken."""
        result = import_stations_from_excel(REFERENCE_XLSX)
        assert result.format_ok is True
        assert result.missing_columns == []

    def test_expected_format_is_self_describing(self):
        from app.ingest.station_importer import expected_format

        spec = expected_format()
        headers = [c["header"] for c in spec["required"]]
        assert headers == ["Call", "categorie", "sectie"]
        assert spec["required_bands"]["header"].startswith("40M")
        assert spec["optional"]


# ---------------------------------------------------------------------------
# Row validation (§7.2)
# ---------------------------------------------------------------------------

class TestRowValidation:
    def test_missing_callsign_reported_with_row_number(self, tmp_path):
        path = write_xlsx(
            tmp_path / "missing.xlsx",
            [
                ["Call", "categorie", "sectie", "40M"],
                ["ON4AA/P", "QRP", "AAA", ""],
                ["", "QRP", "BBB", ""],   # rij 3: geen call, wel andere data
                ["ON4CC/P", "QRP", "CCC", ""],
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
            [["Call", "categorie", "sectie", "40M"],
             ["ON4AA/P", "QRP", "AAA", ""],
             ["JANSSENS", "QRP", "BBB", ""]],
        )
        result = import_stations_from_excel(path)
        assert len(result.stations) == 1
        assert result.issues[0].row_number == 3
        assert "plausible" in result.issues[0].reason

    def test_duplicate_after_normalization_reported(self, tmp_path):
        # §7.2 explicitly: ON4BAF and ON4BAF/P in the same list must be flagged.
        path = write_xlsx(
            tmp_path / "dup.xlsx",
            [["Call", "categorie", "sectie", "40M"],
             ["ON4BAF", "QRP", "AAA", ""],
             ["ON4BAF/P", "QRP", "AAA", ""]],
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
            [["Call", "categorie", "sectie", "40M"],
             ["ON4BAF", "QRP", "AAA", ""],
             ["ON4BAF/P", "QRP", "AAA", ""]],
        )
        result = import_stations_from_excel(path, strict=True)
        assert len(result.stations) == 2
        assert result.issues == []

    def test_fully_empty_rows_skipped_silently(self, tmp_path):
        path = write_xlsx(
            tmp_path / "empty.xlsx",
            [["Call", "categorie", "sectie", "40M"],
             ["ON4AA/P", "QRP", "AAA", ""],
             [None, None, None, None], ["", "", "", ""],
             ["ON4CC/P", "QRP", "CCC", ""]],
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
# CSV (§7.1: same column logic, and the same fixed format as Excel)
# ---------------------------------------------------------------------------

class TestCsvImport:
    def test_comma_csv(self, tmp_path):
        path = tmp_path / "list.csv"
        path.write_text(
            "callsign,categorie,sectie,40M\n"
            "ON4AA/P,QRP,AAA,\nON4BB/P,Open,BBB,\n",
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
        path.write_bytes(
            "Call,categorie,sectie,40M,Opm.\nON4AA/P,QRP,AAA,,café\n".encode("utf-8-sig")
        )
        result = import_stations_from_csv(path)
        assert result.stations[0].remarks == "café"

    def test_csv_follows_the_same_fixed_format(self, tmp_path):
        """Fase 26: CSV kan geen achterpoortje zijn om de controle te omzeilen."""
        path = tmp_path / "minimal.csv"
        path.write_text("callsign\nON4AA/P\nON4BB/P\n", encoding="utf-8")
        result = import_stations_from_csv(path)
        assert result.format_ok is False
        assert result.stations == []

    def test_empty_file_reported(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        result = import_stations_from_csv(path)
        assert result.stations == []
        assert any("no data" in i.reason for i in result.issues)

    def test_duplicate_reported_in_csv_too(self, tmp_path):
        path = tmp_path / "dup.csv"
        path.write_text(
            "Call,categorie,sectie,40M\nON4BAF/P,QRP,AAA,\non4baf,QRP,AAA,\n",
            encoding="utf-8",
        )
        result = import_stations_from_csv(path)
        assert len(result.stations) == 1
        assert "duplicate" in result.issues[0].reason
