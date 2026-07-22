"""Tests for app.core.models and app.core.status (phase 2)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.models import (
    QSO,
    AppSettings,
    FieldDay,
    Override,
    OverrideType,
    QsoSource,
    Station,
    StationSource,
    ensure_utc,
    parse_iso_z,
    to_iso_z,
)
from app.core.status import Status, status_priority

UTC = timezone.utc
CEST = timezone(timedelta(hours=2))  # Brussels summer time


def make_fieldday(**kwargs) -> FieldDay:
    defaults = dict(
        id="fd-2026",
        name="UBA Velddag 2026",
        start_utc=datetime(2026, 6, 6, 13, 0, tzinfo=UTC),
        end_utc=datetime(2026, 6, 7, 13, 0, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return FieldDay(**defaults)


# ---------------------------------------------------------------------------
# UTC helpers (BR-06)
# ---------------------------------------------------------------------------

class TestUtcHelpers:
    def test_naive_datetime_rejected(self):
        with pytest.raises(ValueError, match="naive"):
            ensure_utc(datetime(2026, 6, 6, 13, 0))

    def test_non_utc_converted_to_utc(self):
        local = datetime(2026, 6, 6, 15, 0, tzinfo=CEST)
        result = ensure_utc(local)
        assert result.tzinfo == UTC
        assert result.hour == 13

    def test_to_iso_z_format(self):
        dt = datetime(2026, 6, 6, 14, 32, 11, tzinfo=UTC)
        assert to_iso_z(dt) == "2026-06-06T14:32:11Z"

    def test_to_iso_z_converts_local_first(self):
        local = datetime(2026, 6, 6, 16, 32, 11, tzinfo=CEST)
        assert to_iso_z(local) == "2026-06-06T14:32:11Z"

    def test_to_iso_z_none(self):
        assert to_iso_z(None) is None

    def test_parse_iso_z_with_z_suffix(self):
        result = parse_iso_z("2026-06-06T14:32:11Z")
        assert result == datetime(2026, 6, 6, 14, 32, 11, tzinfo=UTC)

    def test_parse_iso_z_with_offset(self):
        result = parse_iso_z("2026-06-06T16:32:11+02:00")
        assert result == datetime(2026, 6, 6, 14, 32, 11, tzinfo=UTC)

    def test_parse_iso_z_without_timezone_rejected(self):
        with pytest.raises(ValueError, match="naive"):
            parse_iso_z("2026-06-06T14:32:11")

    def test_parse_iso_z_garbage_rejected(self):
        with pytest.raises(ValueError, match="invalid ISO-8601"):
            parse_iso_z("not-a-date")

    def test_parse_iso_z_none_and_empty(self):
        assert parse_iso_z(None) is None
        assert parse_iso_z("") is None

    def test_roundtrip(self):
        dt = datetime(2026, 6, 6, 14, 32, 11, tzinfo=UTC)
        assert parse_iso_z(to_iso_z(dt)) == dt


# ---------------------------------------------------------------------------
# FieldDay (§4.1)
# ---------------------------------------------------------------------------

class TestFieldDay:
    def test_roundtrip(self):
        fd = make_fieldday(location="Hoogveld", event_callsign="ON6WL/P")
        restored = FieldDay.from_dict(fd.to_dict())
        assert restored.to_dict() == fd.to_dict()

    def test_end_before_start_rejected(self):
        with pytest.raises(ValueError, match="end_utc must be after"):
            make_fieldday(
                start_utc=datetime(2026, 6, 7, 13, 0, tzinfo=UTC),
                end_utc=datetime(2026, 6, 6, 13, 0, tzinfo=UTC),
            )

    def test_end_equal_start_rejected(self):
        ts = datetime(2026, 6, 6, 13, 0, tzinfo=UTC)
        with pytest.raises(ValueError):
            make_fieldday(start_utc=ts, end_utc=ts)

    def test_naive_start_rejected(self):
        with pytest.raises(ValueError, match="naive"):
            make_fieldday(start_utc=datetime(2026, 6, 6, 13, 0))

    def test_local_times_stored_as_utc(self):
        fd = make_fieldday(
            start_utc=datetime(2026, 6, 6, 15, 0, tzinfo=CEST),
            end_utc=datetime(2026, 6, 7, 15, 0, tzinfo=CEST),
        )
        assert fd.start_utc == datetime(2026, 6, 6, 13, 0, tzinfo=UTC)

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            make_fieldday(name="   ")

    def test_multi_day_period_contains(self):
        # BR-07: a field day can span multiple calendar days; bounds inclusive.
        fd = make_fieldday()
        assert fd.contains_utc(fd.start_utc)
        assert fd.contains_utc(fd.end_utc)
        assert fd.contains_utc(datetime(2026, 6, 7, 1, 0, tzinfo=UTC))
        assert not fd.contains_utc(fd.start_utc - timedelta(seconds=1))
        assert not fd.contains_utc(fd.end_utc + timedelta(seconds=1))

    def test_defaults(self):
        fd = make_fieldday()
        assert fd.selected_bands == ["160m", "80m", "40m"]
        assert fd.n1mm_udp_host == "127.0.0.1"
        assert fd.n1mm_udp_port == 12060
        assert fd.strict_callsign_matching is False

    def test_empty_bands_rejected(self):
        with pytest.raises(ValueError, match="selected_bands"):
            make_fieldday(selected_bands=[])

    def test_invalid_port_rejected(self):
        with pytest.raises(ValueError, match="udp_port"):
            make_fieldday(n1mm_udp_port=70000)

    def test_missing_required_field(self):
        with pytest.raises(ValueError, match="start_utc"):
            FieldDay.from_dict({"id": "x", "name": "y", "end_utc": "2026-06-07T13:00:00Z"})


# ---------------------------------------------------------------------------
# Station (§4.2)
# ---------------------------------------------------------------------------

class TestStation:
    def test_roundtrip(self):
        st = Station(
            original_callsign="ON4BAF/P",
            normalized_callsign="ON4BAF",
            category="Open All Band Low Power",
            section="RST",
            source=StationSource.EXCEL,
        )
        restored = Station.from_dict(st.to_dict())
        assert restored.to_dict() == st.to_dict()

    def test_empty_callsign_rejected(self):
        with pytest.raises(ValueError, match="original_callsign"):
            Station(original_callsign="", normalized_callsign="ON4BAF")

    def test_invalid_source_rejected(self):
        with pytest.raises(ValueError, match="Station.source"):
            Station.from_dict(
                {
                    "original_callsign": "ON4BAF/P",
                    "normalized_callsign": "ON4BAF",
                    "source": "database",
                }
            )

    def test_source_serialized_as_string(self):
        st = Station(original_callsign="ON4BAF/P", normalized_callsign="ON4BAF")
        assert st.to_dict()["source"] == "manual"


# ---------------------------------------------------------------------------
# QSO (§4.3)
# ---------------------------------------------------------------------------

def make_qso(**kwargs) -> QSO:
    defaults = dict(
        qso_id="a1b2c3",
        original_callsign="ON4BAF/P",
        normalized_callsign="ON4BAF",
        band="80m",
        frequency_khz=3525.19,
        mode="CW",
        timestamp_utc=datetime(2026, 6, 6, 14, 0, tzinfo=UTC),
        source=QsoSource.N1MM_UDP,
    )
    defaults.update(kwargs)
    return QSO(**defaults)


class TestQSO:
    def test_roundtrip(self):
        q = make_qso(source_station="CONTEST-PC1", raw_message="<contactinfo>...</contactinfo>")
        restored = QSO.from_dict(q.to_dict())
        assert restored.to_dict() == q.to_dict()

    def test_deleted_flag_roundtrip(self):
        # QSOs are never hard-deleted (§4.3): the flag must survive storage.
        q = make_qso(deleted=True)
        assert QSO.from_dict(q.to_dict()).deleted is True

    def test_naive_timestamp_rejected(self):
        with pytest.raises(ValueError, match="naive"):
            make_qso(timestamp_utc=datetime(2026, 6, 6, 14, 0))

    def test_zero_frequency_rejected(self):
        with pytest.raises(ValueError, match="frequency_khz"):
            make_qso(frequency_khz=0)

    def test_invalid_source_rejected(self):
        with pytest.raises(ValueError, match="QSO.source"):
            make_qso(source="carrier_pigeon")

    def test_is_claimed_default_true(self):
        assert make_qso().is_claimed is True


# ---------------------------------------------------------------------------
# Override (§4.4)
# ---------------------------------------------------------------------------

class TestOverride:
    def test_roundtrip(self):
        ov = Override(
            normalized_callsign="ON4BAF",
            band="40m",
            override_type=OverrideType.MANUAL_WORKED,
            reason="papieren log",
            set_by="ON6WL",
        )
        restored = Override.from_dict(ov.to_dict())
        assert restored.to_dict() == ov.to_dict()

    def test_key_is_callsign_plus_band(self):
        # BR-05: override key = normalized_callsign + band
        ov = Override(
            normalized_callsign="ON4BAF",
            band="40m",
            override_type=OverrideType.EXCLUDED,
        )
        assert ov.key == ("ON4BAF", "40m")

    def test_invalid_type_rejected(self):
        with pytest.raises(ValueError, match="override_type"):
            Override(
                normalized_callsign="ON4BAF",
                band="40m",
                override_type="maybe_worked",
            )


# ---------------------------------------------------------------------------
# AppSettings (§4.6)
# ---------------------------------------------------------------------------

class TestAppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert s.ui_language == "en"  # BR-12
        assert s.n1mm_udp_host == "127.0.0.1"
        assert s.n1mm_udp_port == 12060
        assert s.publish.enabled is False

    def test_roundtrip(self):
        s = AppSettings(ui_language="nl", last_active_field_day="uba-2026")
        restored = AppSettings.from_dict(s.to_dict())
        assert restored.to_dict() == s.to_dict()

    def test_invalid_language_rejected(self):
        with pytest.raises(ValueError, match="ui_language"):
            AppSettings(ui_language="de")

    def test_from_dict_tolerates_missing_fields(self):
        # A partially written settings file must not crash the app.
        s = AppSettings.from_dict({"ui_language": "fr"})
        assert s.ui_language == "fr"
        assert s.n1mm_udp_port == 12060


# ---------------------------------------------------------------------------
# Status priority (§9.1)
# ---------------------------------------------------------------------------

class TestStatusPriority:
    def test_priority_order(self):
        ordered = sorted(Status, key=status_priority)
        assert ordered == [
            Status.NOT_WORKED,
            Status.WORKED_BY_N1MM,
            Status.MANUAL_WORKED,
            Status.MANUAL_NOT_WORKED,
            Status.EXCLUDED,
        ]

    def test_manual_beats_n1mm(self):
        # BR-05 at enum level: any manual status outranks WORKED_BY_N1MM.
        assert status_priority(Status.MANUAL_WORKED) > status_priority(Status.WORKED_BY_N1MM)
        assert status_priority(Status.MANUAL_NOT_WORKED) > status_priority(Status.WORKED_BY_N1MM)

    def test_status_values_are_snake_case_strings(self):
        assert Status.WORKED_BY_N1MM == "worked_by_n1mm"
