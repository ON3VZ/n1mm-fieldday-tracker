"""Tests for app.core.sync_engine (§9.2) — phase 6.

Includes the project's most important regression test: process a mixed
event sequence incrementally, then do a fresh full recompute from the same
stored data, and assert the matrices are identical.
"""

from datetime import datetime, timedelta, timezone

from app.core.models import (
    QSO,
    FieldDay,
    Override,
    OverrideType,
    QsoSource,
    Station,
)
from app.core.status import Status
from app.core.sync_engine import SyncEngine, resolve_status

UTC = timezone.utc
START = datetime(2026, 6, 6, 13, 0, tzinfo=UTC)
END = datetime(2026, 6, 7, 13, 0, tzinfo=UTC)


def make_fieldday(**kwargs) -> FieldDay:
    defaults = dict(
        id="fd", name="Velddag", start_utc=START, end_utc=END,
        selected_bands=["160m", "80m", "40m"],
    )
    defaults.update(kwargs)
    return FieldDay(**defaults)


def station(call: str) -> Station:
    return Station(original_callsign=call, normalized_callsign=call.split("/")[0])


def qso(qid: str, call: str, band: str = "80m", minutes: int = 60, **kwargs) -> QSO:
    freq_by_band = {"160m": 1830.0, "80m": 3525.0, "40m": 7020.0, "20m": 14050.0}
    defaults = dict(
        qso_id=qid,
        original_callsign=call,
        normalized_callsign=call.split("/")[0],
        band=band,
        frequency_khz=freq_by_band.get(band, 3525.0),
        mode="CW",
        timestamp_utc=START + timedelta(minutes=minutes),
        source=QsoSource.N1MM_UDP,
    )
    defaults.update(kwargs)
    return QSO(**defaults)


def engine(stations=None, qsos=None, overrides=None, **fd_kwargs) -> SyncEngine:
    stations = stations if stations is not None else [station("ON4BAF/P"), station("ON4CDZ/P")]
    return SyncEngine(make_fieldday(**fd_kwargs), stations, qsos or [], overrides or [])


class TestResolveStatus:
    def test_priority_rule7(self):
        excl = Override(normalized_callsign="X", band="80m", override_type=OverrideType.EXCLUDED)
        mnw = Override(normalized_callsign="X", band="80m", override_type=OverrideType.MANUAL_NOT_WORKED)
        mw = Override(normalized_callsign="X", band="80m", override_type=OverrideType.MANUAL_WORKED)
        # BR-05: override always wins over N1MM data, both directions.
        assert resolve_status(True, mnw) == Status.MANUAL_NOT_WORKED
        assert resolve_status(False, mw) == Status.MANUAL_WORKED
        assert resolve_status(True, excl) == Status.EXCLUDED
        assert resolve_status(True, None) == Status.WORKED_BY_N1MM
        assert resolve_status(False, None) == Status.NOT_WORKED


class TestBasics:
    def test_empty_start_br10(self):
        eng = engine()
        assert len(eng.matrix) == 2 * 3
        assert all(c.status == Status.NOT_WORKED for c in eng.matrix.values())

    def test_single_qso_marks_cell(self):
        eng = engine()
        changed = eng.upsert_qso(qso("q1", "ON4BAF"))
        assert changed == [("ON4BAF", "80m")]
        cell = eng.get_cell("ON4BAF", "80m")
        assert cell.status == Status.WORKED_BY_N1MM
        assert cell.worked_qso.qso_id == "q1"
        # other cells untouched
        assert eng.get_cell("ON4BAF", "40m").status == Status.NOT_WORKED
        assert eng.get_cell("ON4CDZ", "80m").status == Status.NOT_WORKED

    def test_idempotent_br09(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF", minutes=60))
        changed = eng.upsert_qso(qso("q2", "ON4BAF", minutes=90))
        cell = eng.get_cell("ON4BAF", "80m")
        assert cell.status == Status.WORKED_BY_N1MM
        assert cell.qso_count == 2
        assert cell.worked_qso.qso_id == "q1"  # earliest wins as reference
        # second QSO changed only the count, still reported as change
        assert changed == [("ON4BAF", "80m")]

    def test_unknown_call_ignored_br03(self):
        eng = engine()
        changed = eng.upsert_qso(qso("q1", "DL1XYZ"))
        assert changed == []
        assert all(c.status == Status.NOT_WORKED for c in eng.matrix.values())
        # but the QSO is stored (raw retention, §5.5)
        assert "q1" in eng.qsos_by_id

    def test_xqso_ignored(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF", is_claimed=False))
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED

    def test_out_of_period_ignored(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF", minutes=-10))
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED


class TestDeleteAndReplace:
    def test_delete_reopens_cell(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF"))
        changed = eng.mark_deleted("q1")
        assert changed == [("ON4BAF", "80m")]
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED
        # soft delete: record remains (§4.3)
        assert eng.qsos_by_id["q1"].deleted is True

    def test_delete_with_second_qso_keeps_worked(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF", minutes=60))
        eng.upsert_qso(qso("q2", "ON4BAF", minutes=90))
        eng.mark_deleted("q1")
        cell = eng.get_cell("ON4BAF", "80m")
        assert cell.status == Status.WORKED_BY_N1MM
        assert cell.worked_qso.qso_id == "q2"

    def test_delete_unknown_id_noop(self):
        eng = engine()
        assert eng.mark_deleted("nope") == []

    def test_replace_moves_between_cells(self):
        # contactreplace with corrected callsign: same ID, new call.
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF"))
        changed = eng.upsert_qso(qso("q1", "ON4CDZ"))
        assert set(changed) == {("ON4BAF", "80m"), ("ON4CDZ", "80m")}
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED
        assert eng.get_cell("ON4CDZ", "80m").status == Status.WORKED_BY_N1MM

    def test_replace_moves_between_bands(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF", band="80m"))
        eng.upsert_qso(qso("q1", "ON4BAF", band="40m", frequency_khz=7020.0))
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED
        assert eng.get_cell("ON4BAF", "40m").status == Status.WORKED_BY_N1MM


class TestOverrides:
    def test_manual_not_worked_beats_n1mm(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF"))
        eng.set_override(
            Override(normalized_callsign="ON4BAF", band="80m",
                     override_type=OverrideType.MANUAL_NOT_WORKED)
        )
        assert eng.get_cell("ON4BAF", "80m").status == Status.MANUAL_NOT_WORKED

    def test_manual_worked_without_qso(self):
        eng = engine()
        eng.set_override(
            Override(normalized_callsign="ON4CDZ", band="40m",
                     override_type=OverrideType.MANUAL_WORKED, reason="papieren log")
        )
        cell = eng.get_cell("ON4CDZ", "40m")
        assert cell.status == Status.MANUAL_WORKED
        assert cell.worked_qso is None

    def test_excluded(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF"))
        eng.set_override(
            Override(normalized_callsign="ON4BAF", band="80m",
                     override_type=OverrideType.EXCLUDED)
        )
        assert eng.get_cell("ON4BAF", "80m").status == Status.EXCLUDED

    def test_clear_override_restores_automatic(self):
        eng = engine()
        eng.upsert_qso(qso("q1", "ON4BAF"))
        eng.set_override(
            Override(normalized_callsign="ON4BAF", band="80m",
                     override_type=OverrideType.MANUAL_NOT_WORKED)
        )
        changed = eng.clear_override("ON4BAF", "80m")
        assert changed == [("ON4BAF", "80m")]
        assert eng.get_cell("ON4BAF", "80m").status == Status.WORKED_BY_N1MM

    def test_clear_nonexistent_noop(self):
        eng = engine()
        assert eng.clear_override("ON4BAF", "80m") == []


class TestFullRecomputeReport:
    def test_report_counts(self):
        qsos = [
            qso("q1", "ON4BAF"),                          # matched
            qso("q2", "ON4BAF", minutes=90),              # matched (same cell)
            qso("q3", "DL1XYZ"),                          # unknown station
            qso("q4", "ON4CDZ", minutes=-30),             # outside period
            qso("q5", "ON4CDZ", band="20m",
                frequency_khz=14050.0),                   # band not selected
            qso("q6", "ON4CDZ", is_claimed=False),        # X-QSO
            qso("q7", "ON4CDZ", deleted=True),            # deleted
        ]
        eng = engine(qsos=qsos)
        report = eng.full_recompute()
        assert report.qsos_total == 7
        assert report.qsos_matched == 2
        assert report.rejected == {
            "unknown_station": 1,
            "outside_period": 1,
            "band_not_selected": 1,
            "not_claimed": 1,
            "deleted": 1,
        }
        assert report.cells_total == 6
        assert report.cells_worked == 1

    def test_strict_toggle_changes_result_on_resync(self):
        # Participant list has /P; QSO logged bare. Loose: worked.
        eng = engine(qsos=[qso("q1", "ON4BAF")])
        assert eng.get_cell("ON4BAF", "80m").status == Status.WORKED_BY_N1MM
        # Switch to strict and resync: bare call no longer matches /P entry.
        fd = make_fieldday(strict_callsign_matching=True)
        eng.set_fieldday(fd)
        assert eng.get_cell("ON4BAF/P", "80m").status == Status.NOT_WORKED

    def test_band_selection_change_resizes_matrix(self):
        eng = engine(qsos=[qso("q1", "ON4BAF", band="20m", frequency_khz=14050.0)])
        assert ("ON4BAF", "20m") not in eng.matrix
        fd = make_fieldday(selected_bands=["80m", "20m"])
        eng.set_fieldday(fd)
        assert eng.get_cell("ON4BAF", "20m").status == Status.WORKED_BY_N1MM
        assert ("ON4BAF", "160m") not in eng.matrix


class TestIncrementalEqualsFull:
    """§9.2: the most important regression test of the project."""

    def test_mixed_sequence(self):
        stations = [station("ON4BAF/P"), station("ON4CDZ/P"), station("OT5X/P")]
        eng = SyncEngine(make_fieldday(), stations, [], [])

        # A realistic mixed sequence: logs, edits, deletes, overrides,
        # unknown calls, X-QSOs, out-of-period, unselected bands.
        eng.upsert_qso(qso("q01", "ON4BAF", band="80m", minutes=10))
        eng.upsert_qso(qso("q02", "ON4BAF/P", band="40m", minutes=20))
        eng.upsert_qso(qso("q03", "ON4CDZ", band="160m", minutes=30))
        eng.upsert_qso(qso("q04", "DL1XYZ", band="80m", minutes=40))          # unknown
        eng.upsert_qso(qso("q05", "OT5X", band="80m", minutes=50, is_claimed=False))
        eng.upsert_qso(qso("q06", "OT5X", band="80m", minutes=-120))          # before start
        eng.upsert_qso(qso("q07", "OT5X", band="20m", minutes=60,
                           frequency_khz=14050.0))                            # not selected
        eng.upsert_qso(qso("q08", "OT5X/P", band="80m", minutes=70))
        eng.upsert_qso(qso("q01", "ON4CDZ", band="80m", minutes=10))          # replace call
        eng.mark_deleted("q02")
        eng.mark_deleted("q03")
        eng.upsert_qso(qso("q09", "ON4CDZ", band="160m", minutes=80))         # re-worked
        eng.set_override(Override(normalized_callsign="ON4BAF", band="80m",
                                  override_type=OverrideType.MANUAL_WORKED))
        eng.set_override(Override(normalized_callsign="OT5X", band="40m",
                                  override_type=OverrideType.EXCLUDED))
        eng.set_override(Override(normalized_callsign="ON4CDZ", band="160m",
                                  override_type=OverrideType.MANUAL_NOT_WORKED))
        eng.clear_override("ON4BAF", "80m")

        # Fresh engine from the incrementally-built stored state:
        fresh = SyncEngine(
            make_fieldday(),
            stations,
            eng.current_qsos(),
            eng.current_overrides(),
        )
        assert eng.semantic_matrix() == fresh.semantic_matrix()

        # Spot-check a few expectations for human confidence:
        assert eng.get_cell("ON4CDZ", "80m").status == Status.WORKED_BY_N1MM  # via replace
        assert eng.get_cell("ON4BAF", "40m").status == Status.NOT_WORKED      # deleted
        assert eng.get_cell("ON4CDZ", "160m").status == Status.MANUAL_NOT_WORKED
        assert eng.get_cell("OT5X", "40m").status == Status.EXCLUDED
        assert eng.get_cell("OT5X", "80m").status == Status.WORKED_BY_N1MM
        # q01 was replaced away from ON4BAF to ON4CDZ, so after clearing the
        # override this cell correctly falls back to NOT_WORKED.
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED

    def test_many_random_events(self):
        # Deterministic pseudo-random storm of events; equality must hold.
        import random

        rng = random.Random(42)
        calls = ["ON4BAF", "ON4CDZ", "OT5X", "DL1XYZ", "F5IN"]
        bands = ["160m", "80m", "40m", "20m"]
        stations = [station("ON4BAF/P"), station("ON4CDZ/P"), station("OT5X/P")]
        eng = SyncEngine(make_fieldday(), stations, [], [])

        for i in range(300):
            action = rng.random()
            qid = f"q{rng.randint(1, 60)}"
            call = rng.choice(calls)
            band = rng.choice(bands)
            if action < 0.6:
                eng.upsert_qso(
                    qso(qid, call, band=band, minutes=rng.randint(-200, 1600),
                        is_claimed=rng.random() > 0.1)
                )
            elif action < 0.75:
                eng.mark_deleted(qid)
            elif action < 0.9:
                eng.set_override(Override(
                    normalized_callsign=rng.choice(["ON4BAF", "ON4CDZ", "OT5X"]),
                    band=rng.choice(["160m", "80m", "40m"]),
                    override_type=rng.choice(list(OverrideType)),
                ))
            else:
                eng.clear_override(
                    rng.choice(["ON4BAF", "ON4CDZ", "OT5X"]),
                    rng.choice(["160m", "80m", "40m"]),
                )

        fresh = SyncEngine(make_fieldday(), stations,
                           eng.current_qsos(), eng.current_overrides())
        assert eng.semantic_matrix() == fresh.semantic_matrix()
