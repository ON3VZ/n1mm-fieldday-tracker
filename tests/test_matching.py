"""Tests for app.core.matching (§9.1, rules 1–6) — phase 6."""

from datetime import datetime, timezone

from app.core.matching import RejectReason, build_station_index, match_qso
from app.core.models import QSO, FieldDay, QsoSource, Station

UTC = timezone.utc


def make_fieldday(**kwargs) -> FieldDay:
    defaults = dict(
        id="fd",
        name="Velddag",
        start_utc=datetime(2026, 6, 6, 13, 0, tzinfo=UTC),
        end_utc=datetime(2026, 6, 7, 13, 0, tzinfo=UTC),
        selected_bands=["160m", "80m", "40m"],
    )
    defaults.update(kwargs)
    return FieldDay(**defaults)


def make_station(call="ON4BAF/P") -> Station:
    return Station(original_callsign=call, normalized_callsign=call.split("/")[0])


def make_qso(**kwargs) -> QSO:
    defaults = dict(
        qso_id="q1",
        original_callsign="ON4BAF",
        normalized_callsign="ON4BAF",
        band="80m",
        frequency_khz=3525.0,
        mode="CW",
        timestamp_utc=datetime(2026, 6, 6, 14, 0, tzinfo=UTC),
        source=QsoSource.N1MM_UDP,
    )
    defaults.update(kwargs)
    return QSO(**defaults)


def index_for(fieldday: FieldDay, stations: list[Station]):
    return build_station_index(stations, fieldday.strict_callsign_matching)


class TestMatchAccepts:
    def test_basic_match(self):
        fd = make_fieldday()
        idx = index_for(fd, [make_station("ON4BAF/P")])
        key, reason = match_qso(make_qso(), fd, idx)
        assert reason is None
        assert key == ("ON4BAF", "80m")

    def test_suffix_mismatch_still_matches_loose(self):
        # The core scenario: list has /P, N1MM logs bare (or vice versa).
        fd = make_fieldday()
        idx = index_for(fd, [make_station("ON4BAF/P")])
        key, _ = match_qso(make_qso(original_callsign="ON4BAF"), fd, idx)
        assert key == ("ON4BAF", "80m")
        key2, _ = match_qso(make_qso(original_callsign="on4baf/qrp"), fd, idx)
        assert key2 == ("ON4BAF", "80m")

    def test_period_bounds_inclusive(self):
        fd = make_fieldday()
        idx = index_for(fd, [make_station()])
        key, _ = match_qso(make_qso(timestamp_utc=fd.start_utc), fd, idx)
        assert key is not None
        key2, _ = match_qso(make_qso(timestamp_utc=fd.end_utc), fd, idx)
        assert key2 is not None


class TestMatchRejects:
    def test_deleted(self):
        fd = make_fieldday()
        idx = index_for(fd, [make_station()])
        key, reason = match_qso(make_qso(deleted=True), fd, idx)
        assert key is None
        assert reason == RejectReason.DELETED

    def test_not_claimed_xqso(self):
        fd = make_fieldday()
        idx = index_for(fd, [make_station()])
        _, reason = match_qso(make_qso(is_claimed=False), fd, idx)
        assert reason == RejectReason.NOT_CLAIMED

    def test_unknown_station_br03(self):
        fd = make_fieldday()
        idx = index_for(fd, [make_station("ON4BAF/P")])
        _, reason = match_qso(make_qso(original_callsign="DL1XYZ"), fd, idx)
        assert reason == RejectReason.UNKNOWN_STATION

    def test_outside_period(self):
        fd = make_fieldday()
        idx = index_for(fd, [make_station()])
        _, reason = match_qso(
            make_qso(timestamp_utc=datetime(2026, 6, 6, 12, 59, 59, tzinfo=UTC)),
            fd,
            idx,
        )
        assert reason == RejectReason.OUTSIDE_PERIOD

    def test_band_not_selected(self):
        fd = make_fieldday(selected_bands=["40m"])
        idx = index_for(fd, [make_station()])
        _, reason = match_qso(make_qso(band="80m"), fd, idx)
        assert reason == RejectReason.BAND_NOT_SELECTED

    def test_inactive_station_ignored(self):
        fd = make_fieldday()
        st = make_station()
        st.active = False
        idx = index_for(fd, [st])
        _, reason = match_qso(make_qso(), fd, idx)
        assert reason == RejectReason.UNKNOWN_STATION


class TestStrictMode:
    def test_strict_requires_exact(self):
        fd = make_fieldday(strict_callsign_matching=True)
        idx = index_for(fd, [make_station("ON4BAF/P")])
        # Bare call no longer matches the /P entry.
        _, reason = match_qso(make_qso(original_callsign="ON4BAF"), fd, idx)
        assert reason == RejectReason.UNKNOWN_STATION
        # Exact (case-insensitive) does.
        key, _ = match_qso(make_qso(original_callsign="on4baf/p"), fd, idx)
        assert key == ("ON4BAF/P", "80m")

    def test_matcher_renormalizes_from_originals(self):
        # Stored normalized_callsign snapshots are deliberately not trusted:
        # feed inconsistent snapshots and verify matching still works.
        fd = make_fieldday()
        st = Station(original_callsign="ON4BAF/P", normalized_callsign="WRONG1")
        idx = index_for(fd, [st])
        qso = make_qso(original_callsign="ON4BAF/M", normalized_callsign="WRONG2")
        key, reason = match_qso(qso, fd, idx)
        assert reason is None
        assert key == ("ON4BAF", "80m")


class TestBuildStationIndex:
    def test_duplicate_first_wins(self):
        a = make_station("ON4BAF/P")
        b = make_station("ON4BAF")
        idx = build_station_index([a, b], strict=False)
        assert idx["ON4BAF"] is a

    def test_strict_keeps_both(self):
        a = make_station("ON4BAF/P")
        b = make_station("ON4BAF")
        idx = build_station_index([a, b], strict=True)
        assert set(idx) == {"ON4BAF/P", "ON4BAF"}
