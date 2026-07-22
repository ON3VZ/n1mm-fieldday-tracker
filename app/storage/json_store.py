"""Atomic JSON file storage with corruption recovery (§4.7).

Every write in this project goes through :func:`write_json_atomic`:

1. serialize to text (fails early on non-serializable data),
2. write to ``<name>.tmp`` in the same directory,
3. read the tmp file back and parse it as validation,
4. ``os.replace()`` — atomic on both Windows (NTFS) and Linux (POSIX).

Every read goes through :func:`read_json`: a corrupt or unreadable file is
logged, moved aside as ``<name>.corrupt.<timestamp>`` and reported as
``None`` so the caller continues with an empty structure. The application
must never crash on a damaged file (§4.7) — and never silently destroy the
damaged data either, so it can be inspected afterwards.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

JsonType = dict | list


def _corrupt_backup_path(path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.corrupt.{ts}")
    # Extremely unlikely collision (two corruptions within one second):
    counter = 1
    while candidate.exists():
        counter += 1
        candidate = path.with_name(f"{path.name}.corrupt.{ts}.{counter}")
    return candidate


def read_json(path: Path) -> JsonType | None:
    """Read and parse a JSON file.

    Returns ``None`` when the file does not exist, or when it is corrupt —
    in the latter case the damaged file is moved to
    ``<name>.corrupt.<timestamp>`` first, so the next write starts clean.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        backup = _corrupt_backup_path(path)
        logger.error("Corrupt JSON file %s (%s); moving to %s", path, exc, backup)
        try:
            os.replace(path, backup)
        except OSError as move_exc:  # even the backup failed: log, keep going
            logger.error("Could not move corrupt file %s: %s", path, move_exc)
        return None
    if not isinstance(data, (dict, list)):
        # Valid JSON but not a usable structure (e.g. a bare number).
        backup = _corrupt_backup_path(path)
        logger.error("Unexpected JSON root in %s; moving to %s", path, backup)
        try:
            os.replace(path, backup)
        except OSError as move_exc:
            logger.error("Could not move file %s: %s", path, move_exc)
        return None
    return data


def write_json_atomic(path: Path, data: JsonType) -> None:
    """Atomically write *data* as JSON to *path* (§4.7).

    Raises ``ValueError`` when *data* is not JSON-serializable, and
    propagates ``OSError`` on disk failures. On any failure the original
    file is left untouched.
    """
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Data for {path} is not JSON-serializable: {exc}") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        # Validation: read back and parse before replacing the real file.
        reread = json.loads(tmp_path.read_text(encoding="utf-8"))
        if not isinstance(reread, (dict, list)):
            raise ValueError(f"Validation of {tmp_path} failed: unexpected root type")

        os.replace(tmp_path, path)
    finally:
        # Never leave a stale tmp file behind after a failure.
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                logger.warning("Could not remove temporary file %s", tmp_path)
