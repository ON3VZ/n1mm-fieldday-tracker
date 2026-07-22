"""Cell status definitions (§4.5) and status priority (§9.1).

The priority order decides which status wins when multiple apply:

    EXCLUDED > MANUAL_NOT_WORKED > MANUAL_WORKED > WORKED_BY_N1MM > NOT_WORKED

Manual overrides therefore always beat N1MM-derived data (BR-05).
"""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    """Status of a single station+band matrix cell."""

    NOT_WORKED = "not_worked"            # empty / white
    WORKED_BY_N1MM = "worked_by_n1mm"    # green
    MANUAL_WORKED = "manual_worked"      # dark green + manual marker
    MANUAL_NOT_WORKED = "manual_not_worked"  # yellow/orange
    EXCLUDED = "excluded"                # grey


# Higher number = higher priority (§9.1). Used by the sync engine to resolve
# the final cell status.
STATUS_PRIORITY: dict[Status, int] = {
    Status.NOT_WORKED: 0,
    Status.WORKED_BY_N1MM: 1,
    Status.MANUAL_WORKED: 2,
    Status.MANUAL_NOT_WORKED: 3,
    Status.EXCLUDED: 4,
}


def status_priority(status: Status) -> int:
    """Return the numeric priority of a status (higher wins)."""
    return STATUS_PRIORITY[status]


# Default colors (§4.5); user-configurable per field day and in settings.
# The UI must additionally mark manual statuses with a non-color indicator
# (icon/corner marker) for color-blind users and sunlight readability.
DEFAULT_STATUS_COLORS: dict[str, str] = {
    Status.NOT_WORKED: "#FFFFFF",
    Status.WORKED_BY_N1MM: "#4CAF50",
    Status.MANUAL_WORKED: "#1B5E20",
    Status.MANUAL_NOT_WORKED: "#FFB300",
    Status.EXCLUDED: "#9E9E9E",
}
