"""Sync engine (§9.2): compute the station×band matrix from QSOs + overrides.

Pure service: no UI dependency, no I/O. Persistence is the caller's job
(repository), presentation is the snapshot builder's job (phase 9).

Two paths, one logic:

- **Full recompute** (:meth:`SyncEngine.full_recompute`): rebuild every cell
  from all stored QSOs, returning a :class:`SyncReport`.
- **Incremental** (:meth:`upsert_qso`, :meth:`mark_deleted`,
  :meth:`set_override`, :meth:`clear_override`): recompute only the affected
  cells — using the *same* per-cell computation.

Both paths must always produce identical matrices; the regression test in
``tests/test_sync_engine.py`` asserts this over a mixed event sequence.

Status resolution (rule 7 of §9.1, BR-05): an override always beats N1MM
data. One QSO suffices (BR-09); the earliest qualifying QSO is recorded as
the cell's "worked" reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.matching import (
    CellKey,
    RejectReason,
    build_station_index,
    match_qso,
)
from app.core.models import QSO, FieldDay, Override, OverrideType, Station
from app.core.status import Status


@dataclass
class CellState:
    """Resolved state of one station+band matrix cell."""

    status: Status = Status.NOT_WORKED
    worked_qso: QSO | None = None  # earliest qualifying QSO, if any
    qso_count: int = 0             # qualifying QSOs (informational; BR-09)
    override: Override | None = None

    def semantic_tuple(self) -> tuple:
        """Comparable representation for the incremental-vs-full test."""
        return (
            self.status,
            self.worked_qso.qso_id if self.worked_qso else None,
            self.qso_count,
            self.override.override_type if self.override else None,
        )


@dataclass
class SyncReport:
    """Result of a full recompute, for the sync log and the UI."""

    qsos_total: int = 0
    qsos_matched: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    cells_worked: int = 0
    cells_total: int = 0

    def to_dict(self) -> dict:
        return {
            "qsos_total": self.qsos_total,
            "qsos_matched": self.qsos_matched,
            "rejected": dict(self.rejected),
            "cells_worked": self.cells_worked,
            "cells_total": self.cells_total,
        }


def resolve_status(worked_by_n1mm: bool, override: Override | None) -> Status:
    """Rule 7 (§9.1): override always wins over N1MM data (BR-05)."""
    if override is not None:
        if override.override_type == OverrideType.EXCLUDED:
            return Status.EXCLUDED
        if override.override_type == OverrideType.MANUAL_NOT_WORKED:
            return Status.MANUAL_NOT_WORKED
        if override.override_type == OverrideType.MANUAL_WORKED:
            return Status.MANUAL_WORKED
    return Status.WORKED_BY_N1MM if worked_by_n1mm else Status.NOT_WORKED


class SyncEngine:
    """Holds the current matrix and keeps it consistent under events."""

    def __init__(
        self,
        fieldday: FieldDay,
        stations: list[Station],
        qsos: list[QSO] | None = None,
        overrides: list[Override] | None = None,
    ) -> None:
        self.fieldday = fieldday
        self.stations = list(stations)
        self.qsos_by_id: dict[str, QSO] = {}
        for qso in qsos or []:
            self.qsos_by_id[qso.qso_id] = qso
        self.overrides_by_key: dict[CellKey, Override] = {}
        for override in overrides or []:
            self.overrides_by_key[override.key] = override

        self.station_index: dict[str, Station] = {}
        self.matrix: dict[CellKey, CellState] = {}
        self.full_recompute()

    # -- configuration changes -------------------------------------------

    def set_fieldday(self, fieldday: FieldDay) -> SyncReport:
        """Replace field day settings (period, bands, strict mode) and rebuild."""
        self.fieldday = fieldday
        return self.full_recompute()

    def set_stations(self, stations: list[Station]) -> SyncReport:
        """Replace the participant list (BR-02) and rebuild."""
        self.stations = list(stations)
        return self.full_recompute()

    # -- cell computation (the ONE shared piece of logic) -----------------

    def _all_cell_keys(self) -> list[CellKey]:
        keys: list[CellKey] = []
        for normalized in self.station_index:
            for band in self.fieldday.selected_bands:
                keys.append((normalized, band))
        return keys

    def _compute_cell(self, key: CellKey) -> CellState:
        """Compute one cell from stored QSOs + override. Used by BOTH paths."""
        worked_qso: QSO | None = None
        count = 0
        for qso in self.qsos_by_id.values():
            match_key, _ = match_qso(qso, self.fieldday, self.station_index)
            if match_key != key:
                continue
            count += 1
            if worked_qso is None or qso.timestamp_utc < worked_qso.timestamp_utc:
                worked_qso = qso
        override = self.overrides_by_key.get(key)
        return CellState(
            status=resolve_status(worked_qso is not None, override),
            worked_qso=worked_qso,
            qso_count=count,
            override=override,
        )

    # -- full path --------------------------------------------------------

    def full_recompute(self) -> SyncReport:
        """Rebuild the whole matrix from scratch; returns a report (§9.2)."""
        report = SyncReport()
        self.station_index = build_station_index(
            self.stations, self.fieldday.strict_callsign_matching
        )

        # Classify all QSOs once for the report.
        for qso in self.qsos_by_id.values():
            report.qsos_total += 1
            key, reason = match_qso(qso, self.fieldday, self.station_index)
            if key is not None:
                report.qsos_matched += 1
            else:
                report.rejected[reason.value] = report.rejected.get(reason.value, 0) + 1

        self.matrix = {key: self._compute_cell(key) for key in self._all_cell_keys()}

        report.cells_total = len(self.matrix)
        report.cells_worked = sum(
            1
            for cell in self.matrix.values()
            if cell.status in (Status.WORKED_BY_N1MM, Status.MANUAL_WORKED)
        )
        return report

    # -- incremental path -------------------------------------------------

    def _key_of(self, qso: QSO | None) -> CellKey | None:
        if qso is None:
            return None
        key, _ = match_qso(qso, self.fieldday, self.station_index)
        return key

    def _refresh_cells(self, keys: set[CellKey | None]) -> list[CellKey]:
        changed: list[CellKey] = []
        for key in keys:
            if key is None or key not in self.matrix:
                continue
            new_state = self._compute_cell(key)
            if new_state.semantic_tuple() != self.matrix[key].semantic_tuple():
                changed.append(key)
            self.matrix[key] = new_state
        return changed

    def upsert_qso(self, qso: QSO) -> list[CellKey]:
        """Insert or update a QSO by ``qso_id`` (contactinfo/contactreplace).

        On a replace where callsign or frequency changed, both the old and
        the new cell are recomputed (§5.2). Returns the changed cell keys.
        """
        previous = self.qsos_by_id.get(qso.qso_id)
        old_key = self._key_of(previous)
        self.qsos_by_id[qso.qso_id] = qso
        new_key = self._key_of(qso)
        return self._refresh_cells({old_key, new_key})

    def mark_deleted(self, qso_id: str) -> list[CellKey]:
        """Soft-delete a QSO (contactdelete); the record stays (§4.3)."""
        qso = self.qsos_by_id.get(qso_id)
        if qso is None:
            return []
        key_before = self._key_of(qso)
        qso.deleted = True
        return self._refresh_cells({key_before})

    def set_override(self, override: Override) -> list[CellKey]:
        """Set or replace the override for a cell (BR-05)."""
        self.overrides_by_key[override.key] = override
        return self._refresh_cells({override.key})

    def clear_override(self, normalized_callsign: str, band: str) -> list[CellKey]:
        """Remove an override; the automatic status applies again (§4.4)."""
        key = (normalized_callsign, band)
        if key not in self.overrides_by_key:
            return []
        del self.overrides_by_key[key]
        return self._refresh_cells({key})

    # -- accessors --------------------------------------------------------

    def get_cell(self, normalized_callsign: str, band: str) -> CellState | None:
        return self.matrix.get((normalized_callsign, band))

    def current_qsos(self) -> list[QSO]:
        """All stored QSOs (incl. deleted), e.g. for persistence."""
        return list(self.qsos_by_id.values())

    def current_overrides(self) -> list[Override]:
        return list(self.overrides_by_key.values())

    def semantic_matrix(self) -> dict[CellKey, tuple]:
        """Comparable snapshot of the whole matrix (for the equality test)."""
        return {key: cell.semantic_tuple() for key, cell in self.matrix.items()}
