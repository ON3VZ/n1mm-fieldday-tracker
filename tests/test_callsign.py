"""Tests for app.core.callsign (§8.1) — phase 3."""

import pytest

from app.core.callsign import callsigns_match, is_plausible_callsign, normalize_callsign


class TestNormalizeLoose:
    """Default mode: suffixes and prefixes must not prevent matching."""

    # The mandatory cases from §8.1:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ON4BAF", "ON4BAF"),
            ("ON4BAF/P", "ON4BAF"),
            ("on4baf/p", "ON4BAF"),
            (" ON4BAF/P ", "ON4BAF"),
            ("ON4BAF/QRP", "ON4BAF"),
            ("F/ON4BAF/P", "ON4BAF"),
            ("ON4BAF/MM", "ON4BAF"),
            ("ON4BAF//P", "ON4BAF"),
        ],
    )
    def test_mandatory_cases(self, raw, expected):
        assert normalize_callsign(raw) == expected

    def test_empty_string(self):
        assert normalize_callsign("") is None

    def test_none(self):
        assert normalize_callsign(None) is None

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ON4BAF/M", "ON4BAF"),
            ("ON4BAF/A", "ON4BAF"),
            ("ON4BAF/AM", "ON4BAF"),
            ("ON4BAF/3", "ON4BAF"),      # digit area suffix
            ("DL/ON4BAF", "ON4BAF"),     # two-letter country prefix
            ("EA8/ON4BAF/P", "ON4BAF"),  # prefix with digit + suffix
            ("ON6WL/P", "ON6WL"),
            ("9A1A", "9A1A"),            # digit-leading prefix
            ("F5IN", "F5IN"),
        ],
    )
    def test_additional_cases(self, raw, expected):
        assert normalize_callsign(raw) == expected

    def test_whitespace_only(self):
        assert normalize_callsign("   ") is None

    def test_slashes_only(self):
        assert normalize_callsign("//") is None

    def test_pure_modifier_is_not_a_callsign(self):
        assert normalize_callsign("/P") is None
        assert normalize_callsign("QRP") is None

    def test_number_input(self):
        # Defensive: non-string input via str() coercion path
        assert normalize_callsign("12345") is None


class TestNormalizeStrict:
    """Strict mode: exact match after uppercasing and trimming."""

    def test_suffix_preserved(self):
        assert normalize_callsign("ON4BAF/P", strict=True) == "ON4BAF/P"

    def test_uppercased_and_trimmed(self):
        assert normalize_callsign(" on4baf/p ", strict=True) == "ON4BAF/P"

    def test_bare_call(self):
        assert normalize_callsign("ON4BAF", strict=True) == "ON4BAF"

    def test_empty_and_none(self):
        assert normalize_callsign("", strict=True) is None
        assert normalize_callsign(None, strict=True) is None

    def test_strict_differs_from_loose(self):
        # The reason the toggle exists: /P differs in strict mode only.
        assert normalize_callsign("ON4BAF/P", strict=True) != normalize_callsign(
            "ON4BAF", strict=True
        )
        assert normalize_callsign("ON4BAF/P", strict=False) == normalize_callsign(
            "ON4BAF", strict=False
        )


class TestCallsignsMatch:
    def test_loose_match_with_suffix(self):
        # The core field-day scenario: list has /P, N1MM logs without.
        assert callsigns_match("ON4BAF/P", "ON4BAF")
        assert callsigns_match("on4baf", " ON4BAF/P ")

    def test_strict_no_match_with_suffix(self):
        assert not callsigns_match("ON4BAF/P", "ON4BAF", strict=True)

    def test_strict_match_identical(self):
        assert callsigns_match("ON4BAF/P", "on4baf/p", strict=True)

    def test_different_stations_never_match(self):
        assert not callsigns_match("ON4BAF", "ON4CDZ")
        assert not callsigns_match("ON4BAF/P", "ON4CDZ/P")

    def test_none_never_matches(self):
        assert not callsigns_match(None, None)
        assert not callsigns_match("", "")
        assert not callsigns_match("ON4BAF", None)


class TestPlausibility:
    def test_valid(self):
        assert is_plausible_callsign("ON4BAF/P")
        assert is_plausible_callsign("9A1A")

    def test_invalid(self):
        assert not is_plausible_callsign("")
        assert not is_plausible_callsign(None)
        assert not is_plausible_callsign("///")
        assert not is_plausible_callsign("JANSSENS")  # a name, not a call
