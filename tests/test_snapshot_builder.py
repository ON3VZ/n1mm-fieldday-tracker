"""Tests for app.view.snapshot_builder (§10.1) — phase 9."""

import json
from datetime import datetime, timezone

from app.core.models import (
    QSO,
    FieldDay,
    Override,
    OverrideType,
    QsoSource,
    Station,
)
from app.core.sync_engine import SyncEngine
from app.view.snapshot_builder import SCHEMA_VERSION, build_snapshot

UTC = timezone.utc
START = datetime(2026, 6, 6, 13, 0, tzinfo=UTC)
END = datetime(2026, 6, 7, 13, 0, tzinfo=UTC)


def make_fieldday(**kwargs) -> FieldDay:
    defaults = dict(
        id="fd", name="UBA Velddag 2026", location="Hoogveld",
        event_callsign="ON6WL/P", organizer_club="WLD",
        start_utc=START, end_utc=END,
        selected_bands=["160m", "80m", "40m"],
        remarks="interne nota", operator_notes="wachtwoord poort: 1234",
    )
    defaults.update(kwargs)
    return FieldDay(**defaults)


def station(call: str, category="Open", section="RST", remarks="") -> Station:
    return Station(
        original_callsign=call, normalized_callsign=call.split("/")[0],
        category=category, section=section, remarks=remarks,
    )


def qso(qid, call, band="80m", minutes=60, **kwargs) -> QSO:
    freq = {"160m": 1830.0, "80m": 3525.19, "40m": 7020.0}[band]
    defaults = dict(
        qso_id=qid, original_callsign=call,
        normalized_callsign=call.split("/")[0], band=band,
        frequency_khz=freq, mode="CW",
        timestamp_utc=START.replace(hour=14, minute=minutes % 60),
        source=QsoSource.N1MM_UDP, source_station="CONTEST-PC1",
    )
    defaults.update(kwargs)
    return QSO(**defaults)


def make_engine() -> SyncEngine:
    stations = [
        station("ON4BAF/P", category="Open", remarks="komt later"),
        station("ON4CDZ/P", category="Restricted 12h"),
        station("OT5X/P", category="Open"),
    ]
    qsos = [
        qso("q1", "ON4BAF", band="160m"),
        qso("q2", "ON4BAF", band="80m"),
        qso("q3", "ON4BAF", band="40m"),   # ON4BAF: volledig
        qso("q4", "ON4CDZ", band="80m"),   # ON4CDZ: gedeeltelijk
    ]
    overrides = [
        Override(normalized_callsign="OT5X", band="40m",
                 override_type=OverrideType.EXCLUDED, reason="eigen station"),
        Override(normalized_callsign="ON4CDZ", band="160m",
                 override_type=OverrideType.MANUAL_WORKED,
                 reason="papieren log", set_by="ON6WL"),
    ]
    return SyncEngine(make_fieldday(), stations, qsos, overrides)


class TestSchema:
    def test_top_level_shape_and_serializable(self):
        snapshot = build_snapshot(make_engine())
        assert snapshot["schema_version"] == SCHEMA_VERSION
        assert snapshot["generated_at_utc"].endswith("Z")
        assert snapshot["readonly"] is False
        for key in ("field_day", "sources", "stations", "stats", "legend", "colors"):
            assert key in snapshot
        json.dumps(snapshot)  # must be fully JSON-serializable

    def test_field_day_block(self):
        fd_block = build_snapshot(make_engine())["field_day"]
        assert fd_block["name"] == "UBA Velddag 2026"
        assert fd_block["event_callsign"] == "ON6WL/P"
        assert fd_block["bands"] == ["160m", "80m", "40m"]
        assert fd_block["start_utc"] == "2026-06-06T13:00:00Z"
        assert fd_block["display_timezone"] == "Europe/Brussels"

    def test_station_order_preserved(self):
        snapshot = build_snapshot(make_engine())
        assert [s["callsign"] for s in snapshot["stations"]] == [
            "ON4BAF/P", "ON4CDZ/P", "OT5X/P"
        ]

    def test_legend_and_colors_present(self):
        snapshot = build_snapshot(make_engine())
        assert set(snapshot["legend"]) == {
            "not_worked", "worked_by_n1mm", "manual_worked",
            "manual_not_worked", "excluded",
        }
        assert snapshot["colors"]["worked_by_n1mm"].startswith("#")


class TestCells:
    def _cells(self, callsign: str) -> dict:
        snapshot = build_snapshot(make_engine())
        return next(s for s in snapshot["stations"] if s["callsign"] == callsign)[
            "cells"
        ]

    def test_worked_cell_details(self):
        cell = self._cells("ON4BAF/P")["80m"]
        assert cell["status"] == "worked_by_n1mm"
        assert cell["at_utc"].endswith("Z")
        assert cell["mode"] == "CW"
        assert cell["freq_khz"] == 3525.19
        assert cell["source"] == "CONTEST-PC1"
        assert cell["qso_count"] == 1

    def test_not_worked_cell_minimal(self):
        cell = self._cells("OT5X/P")["80m"]
        assert cell == {"status": "not_worked"}

    def test_manual_worked_cell(self):
        cell = self._cells("ON4CDZ/P")["160m"]
        assert cell["status"] == "manual_worked"
        assert cell["manual"] is True
        assert cell["reason"] == "papieren log"
        assert cell["set_by"] == "ON6WL"

    def test_excluded_cell(self):
        cell = self._cells("OT5X/P")["40m"]
        assert cell["status"] == "excluded"
        assert cell["manual"] is True


class TestStats:
    def test_totals(self):
        stats = build_snapshot(make_engine())["stats"]
        assert stats["stations_total"] == 3
        assert stats["bands_total"] == 3
        assert stats["cells_total"] == 9
        # worked: ON4BAF×3 + ON4CDZ 80m + ON4CDZ 160m(manual) = 5
        assert stats["cells_worked"] == 5
        assert stats["cells_excluded"] == 1
        assert stats["cells_open"] == 3
        assert stats["manual_overrides"] == 2

    def test_station_classification(self):
        stats = build_snapshot(make_engine())["stats"]
        assert stats["stations_complete"] == 1    # ON4BAF
        assert stats["stations_partial"] == 1     # ON4CDZ
        assert stats["stations_untouched"] == 1   # OT5X (excluded telt niet mee)

    def test_per_band(self):
        per_band = build_snapshot(make_engine())["stats"]["per_band"]
        assert per_band["80m"] == {
            "total": 3, "worked": 2, "open": 1,
            "manual_overrides": 0, "excluded": 0,
        }
        assert per_band["40m"]["excluded"] == 1
        assert per_band["160m"]["manual_overrides"] == 1

    def test_per_category(self):
        per_cat = build_snapshot(make_engine())["stats"]["per_category"]
        assert per_cat["Open"]["stations"] == 2
        assert per_cat["Restricted 12h"]["stations"] == 1
        assert per_cat["Restricted 12h"]["worked"] == 2  # 80m + manual 160m


class TestVariants:
    def test_readonly_flag(self):
        snapshot = build_snapshot(make_engine(), readonly=True)
        assert snapshot["readonly"] is True

    def test_private_content_omitted_for_publishing(self):
        snapshot = build_snapshot(make_engine(), include_private=False)
        text = json.dumps(snapshot)
        # §10.3: remarks and operator notes must be omittable
        assert "interne nota" not in text
        assert "wachtwoord poort" not in text
        assert "komt later" not in text          # station remark
        assert "papieren log" not in text        # override reason
        assert "remarks" not in snapshot["field_day"]
        # But the matrix itself is complete:
        assert snapshot["stats"]["cells_worked"] == 5

    def test_private_content_present_locally(self):
        snapshot = build_snapshot(make_engine(), include_private=True)
        assert snapshot["field_day"]["remarks"] == "interne nota"
        st = next(s for s in snapshot["stations"] if s["callsign"] == "ON4BAF/P")
        assert st["remarks"] == "komt later"


class TestSources:
    def test_sources_serialized(self):
        listener_style = [{
            "name": "CONTEST-PC1",
            "last_seen_utc": datetime(2026, 6, 6, 14, 32, 11, tzinfo=UTC),
            "packet_count": 142,
            "last_address": "192.168.1.10",
            "fresh": True,
        }]
        snapshot = build_snapshot(make_engine(), sources=listener_style)
        source = snapshot["sources"][0]
        assert source["name"] == "CONTEST-PC1"
        assert source["last_seen_utc"] == "2026-06-06T14:32:11Z"
        assert source["fresh"] is True
        json.dumps(snapshot)

    def test_no_sources(self):
        assert build_snapshot(make_engine())["sources"] == []


class TestInactiveStations:
    def test_inactive_station_absent(self):
        stations = [station("ON4BAF/P"), station("ON4CDZ/P")]
        stations[1].active = False
        engine = SyncEngine(make_fieldday(), stations, [], [])
        snapshot = build_snapshot(engine)
        assert [s["callsign"] for s in snapshot["stations"]] == ["ON4BAF/P"]
        assert snapshot["stats"]["stations_total"] == 1


class TestStationQsos:
    def test_qso_list_per_station(self):
        snapshot = build_snapshot(make_engine())
        baf = next(s for s in snapshot["stations"] if s["callsign"] == "ON4BAF/P")
        assert len(baf["qsos"]) == 3
        assert {q["band"] for q in baf["qsos"]} == {"160m", "80m", "40m"}
        assert all(q["source"] == "CONTEST-PC1" for q in baf["qsos"])
        assert baf["qsos"] == sorted(baf["qsos"], key=lambda q: q["at_utc"])

    def test_untouched_station_empty_list(self):
        snapshot = build_snapshot(make_engine())
        ot5x = next(s for s in snapshot["stations"] if s["callsign"] == "OT5X/P")
        assert ot5x["qsos"] == []


def test_snapshot_carries_show_station_category():
    """Fase 25: default aan; uitgezet reist de vlag mee naar de view."""
    engine = SyncEngine(make_fieldday(), [station("ON4BAF/P")], [], [])
    assert build_snapshot(engine)["show_station_category"] is True
    assert build_snapshot(engine, show_station_category=False)[
        "show_station_category"
    ] is False
