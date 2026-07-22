"""GitHub token storage (§10.3).

Order of truth:

1. OS keyring (Windows Credential Manager; Secret Service/KWallet on Linux)
2. Environment variable ``N1MM_TRACKER_GH_TOKEN`` (headless fallback)

The token is NEVER written to a config file, never embedded in the
executable, and never logged. Functions below therefore never include the
token value in exceptions or log messages.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

SERVICE_NAME = "n1mm-fieldday-tracker"
ACCOUNT_NAME = "github-token"
ENV_VAR = "N1MM_TRACKER_GH_TOKEN"


def _keyring():
    try:
        import keyring
        from keyring.errors import KeyringError  # noqa: F401
        return keyring
    except Exception:  # pragma: no cover - import environment dependent
        return None


def get_token() -> str | None:
    """Return the token, or None when not configured anywhere."""
    backend = _keyring()
    if backend is not None:
        try:
            token = backend.get_password(SERVICE_NAME, ACCOUNT_NAME)
            if token:
                return token
        except Exception:
            logger.warning("Keyring unavailable; falling back to environment")
    token = os.environ.get(ENV_VAR, "").strip()
    return token or None


def store_token(token: str) -> tuple[bool, str]:
    """Store the token in the keyring.

    Returns (stored_in_keyring, message_key). When no keyring backend is
    available the caller should instruct the user to use the environment
    variable instead — we deliberately never write tokens to disk.
    """
    token = token.strip()
    if not token:
        return False, "empty token"
    backend = _keyring()
    if backend is None:
        return False, f"no keyring backend; set the {ENV_VAR} environment variable"
    try:
        backend.set_password(SERVICE_NAME, ACCOUNT_NAME, token)
        return True, "stored in OS keyring"
    except Exception:
        logger.warning("Keyring store failed")
        return False, f"keyring unavailable; set the {ENV_VAR} environment variable"


def delete_token() -> None:
    backend = _keyring()
    if backend is None:
        return
    try:
        backend.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        pass


def token_configured() -> bool:
    return get_token() is not None
