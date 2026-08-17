"""Publish files to a GitHub repository via the Contents API (§10.3).

- ``PUT /repos/{repo}/contents/{path}`` with the existing ``sha`` on update
- Unchanged files are skipped: the git blob sha of the local content is
  compared against the remote sha, saving API calls and commits
- Transient failures (network, 5xx, 403 rate limit) retry with backoff;
  the tracker itself is never blocked — the caller runs this off the UI path
- The token only ever appears in the Authorization header
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.github.com"


class OfflineError(RuntimeError):
    """Raised when there is no network connection at all."""
RETRIES = 3
BACKOFF_SECONDS = (1, 3, 6)
TIMEOUT_S = 12
# Separate from RETRIES/BACKOFF_SECONDS above: those retry a single request
# on transient network/server errors. This retries the GET-sha+PUT pair on
# an HTTP 409 sha conflict, which needs a fresh sha each time, not the same
# request repeated.
CONFLICT_RETRIES = 3
CONFLICT_BACKOFF_SECONDS = 0.5


def git_blob_sha(content: bytes) -> str:
    """The sha GitHub reports for a file: sha1 over 'blob <len>\\0<content>'."""
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


@dataclass
class PublishResult:
    ok: bool = True
    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "uploaded": list(self.uploaded),
            "skipped": list(self.skipped),
            "errors": list(self.errors),
        }


class GitHubPublisher:
    def __init__(
        self,
        repo: str,                # "owner/name"
        branch: str,
        token: str,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        if "/" not in repo:
            raise ValueError("repo must be 'owner/name'")
        self.repo = repo
        self.branch = branch or "main"
        self.api_base = api_base.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # -- low level with retry ---------------------------------------------

    def _request(self, method: str, url: str, **kwargs):
        last_error: Exception | None = None
        for attempt in range(RETRIES):
            try:
                response = requests.request(
                    method, url, headers=self._headers, timeout=TIMEOUT_S, **kwargs
                )
                if response.status_code in (500, 502, 503, 504, 403, 429):
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                else:
                    return response
            except (requests.ConnectionError, requests.exceptions.Timeout) as exc:
                # No internet / DNS failure / timeout: retrying in a tight loop
                # is pointless and wastes time. Stop immediately with a clear
                # signal so the caller reports "offline" and does not hammer.
                raise OfflineError(
                    "no network connection — publishing skipped"
                ) from exc
            except requests.RequestException as exc:
                last_error = exc
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
        raise RuntimeError(f"GitHub request failed after {RETRIES} attempts: {last_error}")

    # -- publishing --------------------------------------------------------

    def _remote_sha(self, path: str) -> str | None:
        url = f"{self.api_base}/repos/{self.repo}/contents/{path}"
        response = self._request("GET", url, params={"ref": self.branch})
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                return data.get("sha")
        return None

    def publish_file(self, path: str, content: bytes, message: str) -> str:
        """Upload one file; returns 'uploaded' or 'skipped'.

        Retries on an HTTP 409 sha conflict (§10.3): if this file was
        updated on GitHub between our GET and our PUT — most commonly the
        auto-publish timer and a manual click overlapping — GitHub rejects
        the PUT with "does not match <sha>". ``snapshot.json`` changes on
        every publish and can therefore never take the "content unchanged"
        skip shortcut below, which is what leaves it uniquely exposed to
        this race (the static assets are normally byte-identical between
        two overlapping runs, so the second one just skips them instead of
        conflicting). Re-fetching the current sha and retrying recovers
        automatically instead of failing the whole publish.
        """
        for attempt in range(CONFLICT_RETRIES):
            remote = self._remote_sha(path)
            if remote is not None and remote == git_blob_sha(content):
                return "skipped"
            payload = {
                "message": message,
                "content": base64.b64encode(content).decode("ascii"),
                "branch": self.branch,
            }
            if remote is not None:
                payload["sha"] = remote
            url = f"{self.api_base}/repos/{self.repo}/contents/{path}"
            response = self._request("PUT", url, json=payload)
            if response.status_code in (200, 201):
                return "uploaded"
            if response.status_code == 409 and attempt < CONFLICT_RETRIES - 1:
                logger.info(
                    "Publish conflict for %s (attempt %d/%d), retrying with "
                    "a fresh sha", path, attempt + 1, CONFLICT_RETRIES,
                )
                time.sleep(CONFLICT_BACKOFF_SECONDS)
                continue
            raise RuntimeError(
                f"PUT {path} failed: HTTP {response.status_code} "
                f"{response.text[:200]}"
            )
        raise RuntimeError(f"PUT {path} failed: exhausted conflict retries")

    def publish_files(
        self, files: dict[str, bytes], path_prefix: str = "", message: str = ""
    ) -> PublishResult:
        """Publish a set of files; continues after individual failures."""
        result = PublishResult()
        prefix = path_prefix.strip("/")
        for rel_path, content in files.items():
            path = f"{prefix}/{rel_path}" if prefix else rel_path
            try:
                outcome = self.publish_file(
                    path, content, message or f"tracker update: {rel_path}"
                )
                (result.uploaded if outcome == "uploaded" else result.skipped).append(path)
            except OfflineError:
                raise  # stop the whole publish; no point trying more files
            except Exception as exc:
                result.ok = False
                result.errors.append(f"{path}: {exc}")
                logger.error("Publish failed for %s: %s", path, exc)
        return result
