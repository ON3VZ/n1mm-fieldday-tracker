"""QSO → station+band matching decision (§9.1, rules 1–6).

Pure module: no I/O, no UI. Given a QSO, the field day and the participant
list, decide whether the QSO counts and for which matrix cell
(``normalized_callsign + band``, BR-04). Rejections carry a reason so the
sync log can report honestly (§5.5, §6.3).

Normalization happens HERE, at match time, from the original callsigns on
both sides, using the field day's current ``strict_callsign_matching``
setting. This way toggling the setting followed by a full resync gives
correct results without re-importing anything. The ``normalized_callsign``
stored on Station/QSO records is a convenience snapshot from ingest time and
is deliberately not trusted by the matcher.

Rule 7 (overrides, BR-05) is applied in the sync engine's status
resolution, not here: an override changes the *status* of a cell, not
whether a QSO matches it.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.callsign import normalize_callsign
from app.core.models import QSO, FieldDay, Station


class RejectReason(StrEnum):
    """Why a QSO does not count for the matrix (for sync reporting)."""

    DELETED = "deleted"                      # rule 6
    NOT_CLAIMED = "not_claimed"              # rule 5 (X-QSO)
    UNKNOWN_STATION = "unknown_station"      # rule 4 / BR-03
    OUTSIDE_PERIOD = "outside_period"        # rule 2 / BR-07
    BAND_NOT_SELECTED = "band_not_selected"  # rule 3
    NO_BAND = "no_band"                      # band could not be derived (§8.2)
    INVALID_CALLSIGN = "invalid_callsign"    # nothing normalizable in the call


CellKey = tuple[str, str]  # (normalized_callsign, band)


def build_station_index(
    stations: list[Station], strict: bool
) -> dict[str, Station]:
    """Index active stations by their match-time normalized callsign.

    Inactive stations are excluded: they do not take part (BR-02). On the
    (import-prevented) edge case of duplicates, the first station wins.
    """
    index: dict[str, Station] = {}
    for station in stations:
        if not station.active:
            continue
        normalized = normalize_callsign(station.original_callsign, strict=strict)
        if normalized is None:
            continue
        index.setdefault(normalized, station)
    return index


def match_qso(
    qso: QSO,
    fieldday: FieldDay,
    station_index: dict[str, Station],
) -> tuple[CellKey | None, RejectReason | None]:
    """Apply rules 1–6 of §9.1.

    Returns ``((normalized_callsign, band), None)`` when the QSO counts, or
    ``(None, reason)`` when it does not. Exactly one of the two is None.

    The check order determines which reason is reported when several apply;
    it runs from "record state" outward to "field day scope".
    """
    # Rule 6: deleted QSOs never count (soft delete, §4.3).
    if qso.deleted:
        return None, RejectReason.DELETED

    # Rule 5: X-QSOs (IsClaimedQso == 0) never count.
    if not qso.is_claimed:
        return None, RejectReason.NOT_CLAIMED

    # Band must exist and be derivable (BR-08 guaranteed this at ingest,
    # but the matcher stays defensive).
    band = (qso.band or "").strip()
    if not band:
        return None, RejectReason.NO_BAND

    # Rules 1 + 4: the callsign must normalize and belong to a participant.
    normalized = normalize_callsign(
        qso.original_callsign, strict=fieldday.strict_callsign_matching
    )
    if normalized is None:
        return None, RejectReason.INVALID_CALLSIGN
    if normalized not in station_index:
        # BR-03: never auto-create stations; just ignore (and count it).
        return None, RejectReason.UNKNOWN_STATION

    # Rule 2: within the field day period (inclusive, BR-07).
    if not fieldday.contains_utc(qso.timestamp_utc):
        return None, RejectReason.OUTSIDE_PERIOD

    # Rule 3: band must be among the selected bands.
    if band not in fieldday.selected_bands:
        return None, RejectReason.BAND_NOT_SELECTED

    return (normalized, band), None
