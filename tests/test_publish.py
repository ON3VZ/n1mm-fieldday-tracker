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
    puts: list[str] = []

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
        if FakeGitHub.fail_next:
            self.send_response(FakeGitHub.fail_next.pop(0))
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode())
        key = self._path_key()
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
