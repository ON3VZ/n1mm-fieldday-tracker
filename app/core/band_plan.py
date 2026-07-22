"""Band plan IARU Region 1 (§8.2): frequency → band, and band-label parsing.

Band is ALWAYS derived from frequency (BR-08); the textual ``<band>`` field
from N1MM is locale-dependent (``3.5`` vs ``3,5``) and never used.

Two public functions:

- :func:`band_from_frequency_khz` — 3525.19 → ``"80m"``; outside any band → None
- :func:`parse_band_label` — for Excel column headers and ADIF ``BAND``:
  ``"40M"``, ``"70cm"``, ``"3.5"``, ``"3,5"``, ``"7"`` → canonical band name
"""

from __future__ import annotations

import re

# (canonical name, lower kHz, upper kHz) — bounds inclusive.
BAND_TABLE: list[tuple[str, float, float]] = [
    ("160m", 1810.0, 2000.0),
    ("80m", 3500.0, 3800.0),
    ("60m", 5351.5, 5366.5),
    ("40m", 7000.0, 7200.0),
    ("30m", 10100.0, 10150.0),
    ("20m", 14000.0, 14350.0),
    ("17m", 18068.0, 18168.0),
    ("15m", 21000.0, 21450.0),
    ("12m", 24890.0, 24990.0),
    ("10m", 28000.0, 29700.0),
    ("6m", 50000.0, 52000.0),
    ("4m", 70000.0, 70500.0),
    ("2m", 144000.0, 146000.0),
    ("70cm", 430000.0, 440000.0),
]

ALL_BAND_NAMES: list[str] = [name for name, _, _ in BAND_TABLE]

_CANONICAL = {name.lower(): name for name in ALL_BAND_NAMES}

# "40M", "40 m", "70cm", "70 CM"
_LABEL_RE = re.compile(r"^(\d+)\s*(M|CM)$", re.IGNORECASE)
# "3.5", "3,5", "7", "144" — a frequency in MHz
_NUMBER_RE = re.compile(r"^\d+([.,]\d+)?$")


def band_from_frequency_khz(frequency_khz: float | int | None) -> str | None:
    """Return the canonical band name for a frequency in kHz, or None.

    Frequencies outside every band return ``None``; the caller counts the
    QSO as "band not determinable" in the sync log and skips it (§8.2).
    """
    if frequency_khz is None:
        return None
    try:
        f = float(frequency_khz)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    for name, low, high in BAND_TABLE:
        if low <= f <= high:
            return name
    return None


def parse_band_label(value: str | None) -> str | None:
    """Parse a band label into a canonical band name, or None.

    Accepts:
    - wavelength labels: ``"40m"``, ``"40M"``, ``" 80 m "``, ``"70cm"``
    - frequencies in MHz with ``.`` or ``,`` as decimal separator:
      ``"3.5"``, ``"3,5"``, ``"7"``, ``"144"`` (as N1MM's band text or
      spreadsheet headers may contain)
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Wavelength label, e.g. "40M" / "70cm".
    match = _LABEL_RE.match(text)
    if match:
        candidate = (match.group(1) + match.group(2)).lower()
        return _CANONICAL.get(candidate)

    # Frequency in MHz, e.g. "3.5" or "3,5" or "7".
    if _NUMBER_RE.match(text):
        mhz = float(text.replace(",", "."))
        # Try the value itself, then band starts: "3.5" MHz = 3500 kHz which
        # is exactly the lower bound of 80m (inclusive), so this suffices.
        return band_from_frequency_khz(mhz * 1000.0)

    return None
