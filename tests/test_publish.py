"""Tests for app.publish (phase 16): publisher against a fake GitHub API."""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.publish import credentials
from app.publish.github_publisher import (
    GitHubPublisher,
    git_blob_sha,
)


class FakeGitHub(BaseHTTPRequestHandler):
    """Minimal Contents API: GET returns sha, PUT stores content."""

    store: dict[str, bytes] = {}
    fail_next: list[int] = []  # status codes to return before succeeding
    puts: list[str] = []  # successful PUTs only
    put_attempts: list[str] = []  # every PUT received, success or not
    conflict_next_puts: int = 0  # answer this many upcoming PUTs with a 409

    def log_message(self, *args):  # quiet
        pass

    def _path_key(self) -> str:
        # /repos/owner/name/contents/<path>
        return self.path.split("/contents/", 1)[1].split("?", 1)[0]

    def do_GET(self):
        if FakeGitHub.fail_next:
            self.send_response(FakeGitHub.fail_next.pop(0))
            self.end_headers()
            return
        key = self._path_key()
        if key not in FakeGitHub.store:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"sha": git_blob_sha(FakeGitHub.store[key])}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        key = self._path_key()
        FakeGitHub.put_attempts.append(key)
        if FakeGitHub.fail_next:
            self.send_response(FakeGitHub.fail_next.pop(0))
            self.end_headers()
            return
        if FakeGitHub.conflict_next_puts > 0:
            # Simulates another publish run having changed this file
            # between our GET and our PUT (§10.3 / v1.3.3).
            FakeGitHub.conflict_next_puts -= 1
            body = json.dumps({"message": "snapshot.json does not match"}).encode()
            self.send_response(409)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode())
        existed = key in FakeGitHub.store
        FakeGitHub.store[key] = base64.b64decode(payload["content"])
        FakeGitHub.puts.append(key)
        body = json.dumps({"content": {"sha": git_blob_sha(FakeGitHub.store[key])}}).encode()
        self.send_response(200 if existed else 201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def fake_github():
    FakeGitHub.store = {}
    FakeGitHub.fail_next = []
    FakeGitHub.puts = []
    FakeGitHub.put_attempts = []
    FakeGitHub.conflict_next_puts = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


class TestPublisher:
    def _publisher(self, api_base) -> GitHubPublisher:
        return GitHubPublisher(
            repo="club/velddag-live", branch="main", token="x", api_base=api_base
        )

    def test_new_files_uploaded(self, fake_github):
        result = self._publisher(fake_github).publish_files(
            {"snapshot.json": b'{"a":1}', "index.html": b"<html>"}
        )
        assert result.ok
        assert sorted(result.uploaded) == ["index.html", "snapshot.json"]
        assert FakeGitHub.store["snapshot.json"] == b'{"a":1}'

    def test_unchanged_skipped(self, fake_github):
        publisher = self._publisher(fake_github)
        publisher.publish_files({"snapshot.json": b"same"})
        result = publisher.publish_files({"snapshot.json": b"same"})
        assert result.skipped == ["snapshot.json"]
        assert result.uploaded == []
        assert FakeGitHub.puts.count("snapshot.json") == 1

    def test_changed_updates_with_sha(self, fake_github):
        publisher = self._publisher(fake_github)
        publisher.publish_files({"snapshot.json": b"v1"})
        result = publisher.publish_files({"snapshot.json": b"v2"})
        assert result.uploaded == ["snapshot.json"]
        assert FakeGitHub.store["snapshot.json"] == b"v2"

    def test_path_prefix(self, fake_github):
        self._publisher(fake_github).publish_files(
            {"snapshot.json": b"x"}, path_prefix="velddag/2026"
        )
        assert "velddag/2026/snapshot.json" in FakeGitHub.store

    def test_retry_on_transient_500(self, fake_github, monkeypatch):
        import app.publish.github_publisher as gp

        monkeypatch.setattr(gp, "BACKOFF_SECONDS", (0, 0, 0))
        FakeGitHub.fail_next = [500]  # eerste GET faalt, retry slaagt
        result = self._publisher(fake_github).publish_files({"a.txt": b"1"})
        assert result.ok and result.uploaded == ["a.txt"]

    def test_persistent_failure_reported_not_raised(self, fake_github, monkeypatch):
        import app.publish.github_publisher as gp

        monkeypatch.setattr(gp, "BACKOFF_SECONDS", (0, 0, 0))
        FakeGitHub.fail_next = [500] * 10
        result = self._publisher(fake_github).publish_files({"a.txt": b"1"})
        assert result.ok is False
        assert result.errors and "a.txt" in result.errors[0]

    def test_invalid_repo_rejected(self):
        with pytest.raises(ValueError, match="owner/name"):
            GitHubPublisher(repo="zonderslash", branch="main", token="x")

    def test_conflict_retries_with_a_fresh_sha(self, fake_github):
        """v1.3.3: a 409 sha conflict recovers by re-fetching and retrying,
        instead of failing the whole publish (§10.3)."""
        publisher = self._publisher(fake_github)
        publisher.publish_files({"snapshot.json": b"v1"})
        FakeGitHub.put_attempts = []  # baseline write done; count only what follows
        FakeGitHub.puts = []
        FakeGitHub.conflict_next_puts = 1  # only the first PUT attempt conflicts
        result = publisher.publish_files({"snapshot.json": b"v2"})
        assert result.ok is True
        assert result.uploaded == ["snapshot.json"]
        assert FakeGitHub.store["snapshot.json"] == b"v2"
        # Two attempts reached the server: the conflicting one and the retry.
        assert FakeGitHub.put_attempts.count("snapshot.json") == 2
        assert FakeGitHub.puts.count("snapshot.json") == 1

    def test_conflict_exhausts_retries_then_reports_the_error(
        self, fake_github, monkeypatch
    ):
        import app.publish.github_publisher as gp

        monkeypatch.setattr(gp, "CONFLICT_BACKOFF_SECONDS", 0)
        publisher = self._publisher(fake_github)
        publisher.publish_files({"snapshot.json": b"v1"})
        FakeGitHub.put_attempts = []  # baseline write done; count only what follows
        FakeGitHub.conflict_next_puts = 99  # keeps conflicting
        result = publisher.publish_files({"snapshot.json": b"v2"})
        assert result.ok is False
        assert result.errors and "snapshot.json" in result.errors[0]
        assert "409" in result.errors[0]
        # Never gave up silently: it did try CONFLICT_RETRIES times.
        assert FakeGitHub.put_attempts.count("snapshot.json") == gp.CONFLICT_RETRIES


class TestCredentials:
    def test_env_fallback(self, monkeypatch):
        monkeypatch.setattr(credentials, "_keyring", lambda: None)
        monkeypatch.setenv(credentials.ENV_VAR, "tok123")
        assert credentials.get_token() == "tok123"
        assert credentials.token_configured() is True

    def test_no_token_anywhere(self, monkeypatch):
        monkeypatch.setattr(credentials, "_keyring", lambda: None)
        monkeypatch.delenv(credentials.ENV_VAR, raising=False)
        assert credentials.get_token() is None

    def test_store_without_backend_advises_env(self, monkeypatch):
        monkeypatch.setattr(credentials, "_keyring", lambda: None)
        stored, message = credentials.store_token("abc")
        assert stored is False
        assert credentials.ENV_VAR in message

    def test_empty_token_rejected(self):
        stored, message = credentials.store_token("   ")
        assert stored is False


class TestPublishFlow:
    def test_appstate_publish_now(self, fake_github, monkeypatch, tmp_path):
        from datetime import datetime, timedelta, timezone

        from app.core.models import FieldDay, Station, StationSource
        from app.server import AppState
        from app.storage.app_settings import load_app_settings, save_app_settings
        from app.storage.fieldday_repository import create_fieldday

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        monkeypatch.setenv(credentials.ENV_VAR, "tok")
        import importlib

        import app.config as config
        importlib.reload(config)

        settings = load_app_settings()
        settings.publish.repo = "club/velddag-live"
        settings.publish.include_private = False
        settings.publish.api_base = fake_github
        save_app_settings(settings)

        start = datetime.now(timezone.utc)
        fieldday = FieldDay(id="fd-pub", name="Publicatietest",
                            start_utc=start, end_utc=start + timedelta(hours=24),
                            remarks="prive-nota")
        repo = create_fieldday(fieldday, root_dir=tmp_path / "fds")
        repo.save_stations([Station(original_callsign="ON4BAF/P",
                                    normalized_callsign="ON4BAF",
                                    source=StationSource.EXCEL,
                                    remarks="geheim")])
        state = AppState(repo)
        state.engine.set_stations(repo.load_stations())

        result = state.publish_now()
        assert result["ok"] is True
        assert "snapshot.json" in result["uploaded"]
        assert "index.html" in result["uploaded"]

        # v1.3.1: the published index.html points at versioned assets, so a
        # phone cannot keep serving a cached stylesheet after an update.
        from app import config as _config
        from app.version import APP_VERSION

        index_html = FakeGitHub.store["index.html"].decode()
        assert f'href="style.css?v={APP_VERSION}"' in index_html
        assert f'src="app.js?v={APP_VERSION}"' in index_html
        # The local copy on disk stays untouched.
        local_html = (_config.static_view_dir() / "index.html").read_text(
            encoding="utf-8")
        assert 'href="style.css"' in local_html

        published = json.loads(FakeGitHub.store["snapshot.json"].decode())
        assert published["readonly"] is True
        # §10.3: privé-inhoud standaard weggelaten
        text = FakeGitHub.store["snapshot.json"].decode()
        assert "prive-nota" not in text and "geheim" not in text

        # Publish-status + Pages-URL
        status = state.publish_status()
        assert status["token_configured"] is True
        assert status["pages_url"] == "https://club.github.io/velddag-live/"
        assert status["last_result"]["ok"] is True

        # Tweede keer: statische bestanden zijn zeker ongewijzigd → geskipt.
        # (snapshot.json bevat een timestamp en kan dus wél opnieuw uploaden.)
        result2 = state.publish_now()
        assert result2["ok"] is True
        for name in ("index.html", "app.js", "style.css"):
            assert name in result2["skipped"]


class TestOfflineBehavior:
    def test_connection_error_raises_offline_not_retry_storm(self, monkeypatch):
        """No network → OfflineError immediately, no retry hammering."""
        import app.publish.github_publisher as gp

        calls = {"n": 0}

        def boom(*args, **kwargs):
            calls["n"] += 1
            raise gp.requests.ConnectionError("no route to host")

        monkeypatch.setattr(gp.requests, "request", boom)
        publisher = gp.GitHubPublisher(repo="club/live", branch="main", token="x")
        # OfflineError propagates (caller decides), and crucially only ONE
        # network call was made — no tight retry storm.
        with pytest.raises(gp.OfflineError):
            publisher.publish_files({"snapshot.json": b"x"})
        assert calls["n"] == 1

    def test_appstate_publish_now_reports_offline(self, monkeypatch, tmp_path):
        from datetime import datetime, timedelta, timezone

        from app.core.models import FieldDay
        from app.server import AppState
        from app.storage.app_settings import load_app_settings, save_app_settings
        from app.storage.fieldday_repository import create_fieldday
        import app.publish.github_publisher as gp

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        monkeypatch.setenv(credentials.ENV_VAR, "tok")
        import importlib
        import app.config as config
        importlib.reload(config)

        settings = load_app_settings()
        settings.publish.repo = "club/live"
        save_app_settings(settings)

        def boom(*args, **kwargs):
            raise gp.requests.ConnectionError("offline")

        monkeypatch.setattr(gp.requests, "request", boom)

        start = datetime.now(timezone.utc)
        fieldday = FieldDay(id="fd-off", name="Off", start_utc=start,
                            end_utc=start + timedelta(hours=24))
        repo = create_fieldday(fieldday, root_dir=tmp_path / "fds")
        state = AppState(repo)
        result = state.publish_now()
        assert result["ok"] is False
        assert result.get("offline") is True


class TestPublicationState:
    def _state_app(self, tmp_path, monkeypatch, start, end, closed=False):
        from app.core.models import FieldDay
        from app.server import AppState
        from app.storage.app_settings import load_app_settings, save_app_settings
        from app.storage.fieldday_repository import create_fieldday
        import importlib
        import app.config as config

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        monkeypatch.setenv(credentials.ENV_VAR, "tok")
        importlib.reload(config)
        settings = load_app_settings()
        settings.publish.repo = "club/live"
        save_app_settings(settings)
        fieldday = FieldDay(id="fd-state", name="StateVD",
                            start_utc=start, end_utc=end, closed=closed)
        repo = create_fieldday(fieldday, root_dir=tmp_path / "fds")
        return AppState(repo)

    def test_live_state_within_window(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        app = self._state_app(tmp_path, monkeypatch,
                              now - timedelta(hours=1), now + timedelta(hours=5))
        assert app._publication_state()["state"] == "live"

    def test_upcoming_before_start(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        app = self._state_app(tmp_path, monkeypatch,
                              now + timedelta(days=3), now + timedelta(days=3, hours=6))
        state = app._publication_state()
        assert state["state"] == "upcoming"
        assert "next_start_utc" in state

    def test_expired_after_one_week(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        app = self._state_app(tmp_path, monkeypatch,
                              now - timedelta(days=10), now - timedelta(days=9))
        assert app._publication_state()["state"] == "expired"

    def test_grace_period_still_live(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        # ended 2 days ago → within 1-week grace → still live
        app = self._state_app(tmp_path, monkeypatch,
                              now - timedelta(days=3), now - timedelta(days=2))
        assert app._publication_state()["state"] == "live"

    def test_none_when_closed(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        app = self._state_app(tmp_path, monkeypatch,
                              now - timedelta(hours=1), now + timedelta(hours=5),
                              closed=True)
        assert app._publication_state()["state"] == "none"

    def test_published_snapshot_expired_has_no_stations(self, fake_github, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone
        from app.core.models import Station, StationSource
        from app.storage.app_settings import load_app_settings, save_app_settings

        now = datetime.now(timezone.utc)
        app = self._state_app(tmp_path, monkeypatch,
                              now - timedelta(days=10), now - timedelta(days=9))
        app.repo.save_stations([Station(original_callsign="ON4BAF/P",
                                        normalized_callsign="ON4BAF",
                                        source=StationSource.EXCEL)])
        app.engine.set_stations(app.repo.load_stations())
        settings = load_app_settings()
        settings.publish.api_base = fake_github
        save_app_settings(settings)

        result = app.publish_now()
        assert result["ok"] is True
        published = json.loads(FakeGitHub.store["snapshot.json"].decode())
        assert published["publication"]["state"] == "expired"
        assert published["stations"] == []  # no data leaked on an expired page


class TestPublishConcurrency:
    """v1.3.3: an auto-publish run and a manual click must not race on
    snapshot.json (§10.3) — that race is what produced the HTTP 409 'does
    not match <sha>' seen in practice."""

    def _make_state(self, fake_github, monkeypatch, tmp_path):
        from datetime import datetime, timedelta, timezone

        from app.core.models import FieldDay, Station, StationSource
        from app.server import AppState
        from app.storage.app_settings import load_app_settings, save_app_settings
        from app.storage.fieldday_repository import create_fieldday

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        monkeypatch.setenv(credentials.ENV_VAR, "tok")
        import importlib

        import app.config as config
        importlib.reload(config)

        settings = load_app_settings()
        settings.publish.repo = "club/velddag-live"
        settings.publish.api_base = fake_github
        save_app_settings(settings)

        start = datetime.now(timezone.utc)
        fieldday = FieldDay(id="fd-lock", name="Locktest",
                            start_utc=start, end_utc=start + timedelta(hours=24))
        repo = create_fieldday(fieldday, root_dir=tmp_path / "fds")
        repo.save_stations([Station(original_callsign="ON4BAF/P",
                                    normalized_callsign="ON4BAF",
                                    source=StationSource.EXCEL)])
        state = AppState(repo)
        state.engine.set_stations(repo.load_stations())
        return state

    def test_overlapping_publish_is_turned_away_not_raced(
        self, fake_github, monkeypatch, tmp_path
    ):
        state = self._make_state(fake_github, monkeypatch, tmp_path)
        # Hold the lock as if another publish run (the auto-publish timer,
        # or a previous click) were already in flight.
        state._publish_lock.acquire()
        try:
            result = state.publish_now()
        finally:
            state._publish_lock.release()
        assert result["ok"] is False
        assert result["already_running"] is True
        # It never reached GitHub at all — no race was even possible.
        assert FakeGitHub.put_attempts == []

    def test_publish_still_works_once_the_lock_is_free(
        self, fake_github, monkeypatch, tmp_path
    ):
        state = self._make_state(fake_github, monkeypatch, tmp_path)
        result = state.publish_now()
        assert result["ok"] is True
        assert "snapshot.json" in result["uploaded"]
        # And the lock is released again afterwards for the next run.
        assert state._publish_lock.acquire(blocking=False)
        state._publish_lock.release()



    """§10.3 — the published page must pick up a new stylesheet (v1.3.1)."""

    def test_asset_links_get_the_version(self):
        from app.server import _version_asset_links
        from app.version import APP_VERSION

        html = (b'<link rel="stylesheet" href="style.css">'
                b'<script src="app.js"></script>')
        out = _version_asset_links(html).decode()
        assert f'href="style.css?v={APP_VERSION}"' in out
        assert f'src="app.js?v={APP_VERSION}"' in out

    def test_other_content_untouched(self):
        from app.server import _version_asset_links

        html = b'<a href="style.css.txt">x</a><img src="logo.png">'
        assert _version_asset_links(html) == html
