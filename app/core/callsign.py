"""Callsign normalization and matching (§8.1).

Pure module, no dependencies outside the standard library, fully testable.

Two modes, selected by ``strict``:

- ``strict=False`` (default): common suffixes (``/P``, ``/M``, ``/MM``,
  ``/QRP``, ``/A``, ``/AM``, single digits, ...) and country prefixes
  (``F/ON4BAF``) must not prevent matching. The *base callsign* is extracted:
  ``ON4BAF``, ``ON4BAF/P``, ``F/ON4BAF/P`` all normalize to ``ON4BAF``.
- ``strict=True``: exact match after uppercasing and trimming only;
  ``ON4BAF/P`` stays ``ON4BAF/P``.

Normalization is applied on BOTH sides: the participant list and incoming
QSOs (BR-04). This matters for this field day: all 38 stations in the
participant list carry ``/P`` while N1MM may log them with or without it.
"""

from __future__ import annotations

import re

# Pattern of a standard amateur radio callsign: 1-3 prefix characters
# (letters, possibly a digit as in "4X" or "9A"), one digit, 1-4 suffix
# letters. Examples: ON4BAF, F5IN, 9A1A, DL1ABC, G4X.
_CALLSIGN_RE = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z]{1,4}$")

# Tokens that are known modifiers, never a base callsign by themselves.
_MODIFIER_TOKENS = {
    "P",     # portable
    "M",     # mobile
    "MM",    # maritime mobile
    "AM",    # aeronautical mobile
    "A",     # alternative location
    "QRP",   # low power
    "QRPP",
    "LGT",   # lighthouse
}


def is_plausible_callsign(value: str | None) -> bool:
    """Loose plausibility check for import validation (§7.2).

    Accepts a bare callsign or one with modifiers/prefixes attached.
    """
    if not value or not str(value).strip():
        return False
    return normalize_callsign(value, strict=False) is not None


def normalize_callsign(value: str | None, strict: bool = False) -> str | None:
    """Normalize *value* for matching (BR-04).

    Returns ``None`` when no usable callsign can be extracted (empty input,
    ``None``, or nothing that resembles a callsign).
    """
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None

    if strict:
        return text

    # Split on "/", dropping empty tokens (handles "ON4BAF//P").
    tokens = [t for t in text.split("/") if t]
    if not tokens:
        return None

    # 1. Prefer the first token that matches the standard callsign pattern
    #    and is not a pure modifier. Handles "F/ON4BAF/P" (F does not match,
    #    ON4BAF does) and "ON4BAF/M" (M is a modifier).
    candidates = [
        t for t in tokens
        if t not in _MODIFIER_TOKENS and _CALLSIGN_RE.match(t)
    ]
    if candidates:
        return candidates[0]

    # 2. Fallback for unusual but real calls that miss the strict pattern:
    #    take the longest token containing at least one digit and one letter,
    #    excluding known modifiers.
    fallback = [
        t for t in tokens
        if t not in _MODIFIER_TOKENS
        and any(c.isdigit() for c in t)
        and any(c.isalpha() for c in t)
    ]
    if fallback:
        return max(fallback, key=len)

    # 3. Nothing resembles a callsign.
    return None


def callsigns_match(a: str | None, b: str | None, strict: bool = False) -> bool:
    """True when two callsigns refer to the same station under the given mode."""
    na = normalize_callsign(a, strict=strict)
    nb = normalize_callsign(b, strict=strict)
    return na is not None and na == nb
