"""Tests for app.core.band_plan (§8.2) — phase 3."""

import pytest

from app.core.band_plan import (
    ALL_BAND_NAMES,
    BAND_TABLE,
    band_from_frequency_khz,
    parse_band_label,
)


class TestBandFromFrequency:
    @pytest.mark.parametrize("name,low,high", BAND_TABLE)
    def test_bounds_inclusive(self, name, low, high):
        assert band_from_frequency_khz(low) == name
        assert band_from_frequency_khz(high) == name
        assert band_from_frequency_khz((low + high) / 2) == name

    @pytest.mark.parametrize(
        "freq",
        [
            1809.9,    # just below 160m
            2000.1,    # just above 160m
            3499.9,    # just below 80m
            3800.1,    # just above 80m
            5000.0,    # between 60m and 40m... actually below 60m
            7200.1,    # just above 40m
            100.0,     # far below anything
            999999.0,  # far above anything
        ],
    )
    def test_outside_bands_returns_none(self, freq):
        assert band_from_frequency_khz(freq) is None

    def test_realistic_n1mm_value(self):
        # rxfreq 352519 (units of 10 Hz) → 3525.19 kHz → 80m.
        # The unit conversion itself happens in the parser (phase 7);
        # here we assert the kHz value maps correctly.
        assert band_from_frequency_khz(3525.19) == "80m"

    def test_60m_decimal_bounds(self):
        assert band_from_frequency_khz(5351.5) == "60m"
        assert band_from_frequency_khz(5366.5) == "60m"
        assert band_from_frequency_khz(5351.4) is None

    def test_invalid_inputs(self):
        assert band_from_frequency_khz(None) is None
        assert band_from_frequency_khz(0) is None
        assert band_from_frequency_khz(-7100) is None
        assert band_from_frequency_khz("garbage") is None

    def test_string_number_accepted(self):
        assert band_from_frequency_khz("7100") == "40m"


class TestParseBandLabel:
    @pytest.mark.parametrize(
        "label,expected",
        [
            ("40M", "40m"),
            ("40m", "40m"),
            (" 80 m ", "80m"),
            ("160M", "160m"),
            ("70cm", "70cm"),
            ("70CM", "70cm"),
            ("70 Cm", "70cm"),
            ("2m", "2m"),
            ("6M", "6m"),
        ],
    )
    def test_wavelength_labels(self, label, expected):
        assert parse_band_label(label) == expected

    @pytest.mark.parametrize(
        "label,expected",
        [
            ("3.5", "80m"),   # N1MM band text, dot locale
            ("3,5", "80m"),   # N1MM band text, comma locale
            ("1.8", None),    # 1800 kHz is below the 160m band start (1810)
            ("1,9", "160m"),
            ("7", "40m"),
            ("14", "20m"),
            ("144", "2m"),
            ("430", "70cm"),
            ("5,3515", "60m"),
        ],
    )
    def test_frequency_labels(self, label, expected):
        assert parse_band_label(label) == expected

    @pytest.mark.parametrize(
        "label",
        ["", None, "unknown", "Opm.", "Call", "categorie", "Nummer", "sectie",
         "13cm", "23M", "abc m"],
    )
    def test_non_band_labels_return_none(self, label):
        assert parse_band_label(label) is None

    def test_excel_headers_from_reference_file(self):
        # The actual band columns of deelnemerslijst_orig.xlsx (§7.1)
        assert parse_band_label("40M") == "40m"
        assert parse_band_label("80M") == "80m"
        assert parse_band_label("160M") == "160m"
        # and the non-band columns must NOT be recognized as bands
        for header in ("Nummer", "categorie", "Call", "sectie", "Opm."):
            assert parse_band_label(header) is None


class TestTable:
    def test_all_names_unique(self):
        assert len(ALL_BAND_NAMES) == len(set(ALL_BAND_NAMES))

    def test_no_overlapping_ranges(self):
        ordered = sorted(BAND_TABLE, key=lambda b: b[1])
        for (_, _, high_prev), (_, low_next, _) in zip(ordered, ordered[1:]):
            assert high_prev < low_next
