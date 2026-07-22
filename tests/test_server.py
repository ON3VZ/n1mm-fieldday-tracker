"""Integration tests for app.server (phase 11).

These start a real HTTP server and a real UDP listener on ephemeral ports
and exercise the whole chain: UDP packet → engine → persisted files →
snapshot endpoint → override API → manual sync.
"""

import json
import socket
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from app.core.models import FieldDay, Station, StationSource
from app.server import AppState, make_server
from app.storage.fieldday_repository import create_fieldday
from tests.test_n1mm_parser import CONTACTDELETE, GUID, contactinfo

UTC = timezone.utc


@pytest.fixture()
def running_app(tmp_path):
    start = datetime.now(UTC) - timedelta(hours=1)
    fieldday = FieldDay(
        id="fd-int", name="Integratietest",
        start_utc=start, end_utc=start + timedelta(hours=26),
        selected_bands=["160m", "80m", "40m"],
    )
    repo = create_fieldday(fieldday, root_dir=tmp_path)
    repo.save_stations([
        Station(original_callsign="ON4BAF/P", normalized_callsign="ON4BAF",
                source=StationSource.EXCEL),
        Station(original_callsign="ON4CDZ/P", normalized_callsign="ON4CDZ",
                source=StationSource.EXCEL),
    ])
    state = AppState(repo)
    state.engine.set_stations(repo.load_stations())
    assert state.start_listener(host="127.0.0.1", port=0)
    udp_port = state.listener._socket.getsockname()[1]

    server = make_server(state, "127.0.0.1", 0)
    http_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, repo, udp_port, http_port
    finally:
        server.shutdown()
        server.server_close()
        state.stop()


def http_get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def http_post(port, path, payload):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def send_udp(port, payload: str):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload.encode("utf-8"), ("127.0.0.1", port))


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def cell_status(snapshot, callsign, band):
    station = next(s for s in snapshot["stations"] if s["normalized"] == callsign)
    return station["cells"][band]["status"]


class TestChain:
    def test_udp_to_snapshot_and_persistence(self, running_app):
        state, repo, udp_port, http_port = running_app
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))

        assert wait_until(lambda: state.listener.stats.processed == 1)
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "worked_by_n1mm"
        # Persisted on disk:
        assert len(repo.load_qsos()) == 1
        # Raw log written (§5.5):
        raw = (repo.dir / "raw_packets.log").read_text(encoding="utf-8")
        assert "contactinfo" in raw

    def test_edit_and_delete_flow(self, running_app):
        state, repo, udp_port, http_port = running_app
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)

        # N1MM edit: contactdelete + contactreplace with a new callsign
        delete = CONTACTDELETE.replace("2026-06-06 14:43:38", now)
        send_udp(udp_port, delete)
        send_udp(udp_port, contactinfo(tag="contactreplace", call="ON4CDZ/P",
                                       timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 3)
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "not_worked"
        assert cell_status(snapshot, "ON4CDZ", "80m") == "worked_by_n1mm"

    def test_lookupinfo_ignored_and_logged_raw(self, running_app):
        state, repo, udp_port, http_port = running_app
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(tag="lookupinfo", timestamp=now))
        assert wait_until(lambda: state.listener.stats.ignored == 1)
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "not_worked"
        raw = (repo.dir / "raw_packets.log").read_text(encoding="utf-8")
        assert "lookupinfo" in raw

    def test_override_api(self, running_app):
        state, repo, udp_port, http_port = running_app
        status, result = http_post(http_port, "/api/override", {
            "normalized_callsign": "ON4CDZ", "band": "40m",
            "override_type": "manual_worked", "reason": "papieren log",
            "set_by": "ON6WL",
        })
        assert status == 200 and result["ok"]
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4CDZ", "40m") == "manual_worked"
        assert len(repo.load_overrides()) == 1

        status, result = http_post(http_port, "/api/override/clear", {
            "normalized_callsign": "ON4CDZ", "band": "40m",
        })
        assert status == 200 and result["ok"]
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4CDZ", "40m") == "not_worked"
        assert repo.load_overrides() == []

    def test_invalid_override_clean_400(self, running_app):
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/override", {
            "normalized_callsign": "ON4CDZ", "band": "40m",
            "override_type": "maybe",
        })
        assert status == 400
        assert result["ok"] is False

    def test_manual_sync_endpoint(self, running_app):
        state, repo, udp_port, http_port = running_app
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)

        status, result = http_post(http_port, "/api/sync", {})
        assert status == 200 and result["ok"]
        assert result["report"]["qsos_matched"] == 1
        assert repo.load_sync_log()[-1]["type"] == "manual_sync"

    def test_station_remarks(self, running_app):
        state, repo, _, http_port = running_app
        status, result = http_post(http_port, "/api/station-remarks", {
            "normalized_callsign": "ON4BAF", "remarks": "komt pas zaterdag",
        })
        assert status == 200 and result["ok"]
        stored = {s.normalized_callsign: s for s in repo.load_stations()}
        assert stored["ON4BAF"].remarks == "komt pas zaterdag"

        status, _ = http_post(http_port, "/api/station-remarks", {
            "normalized_callsign": "DL1XYZ", "remarks": "x",
        })
        assert status == 404

    def test_status_endpoint(self, running_app):
        state, _, udp_port, http_port = running_app
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)
        _, status_payload = http_get(http_port, "/api/status")
        assert status_payload["listener_running"] is True
        assert status_payload["udp"]["processed"] == 1
        assert status_payload["sources"][0]["name"] == "CONTEST-PC1"

    def test_static_view_served(self, running_app):
        _, _, _, http_port = running_app
        with urllib.request.urlopen(
            f"http://127.0.0.1:{http_port}/index.html", timeout=5
        ) as resp:
            assert resp.status == 200
            assert b"Field Day Tracker" in resp.read()

    def test_restart_recovers_state(self, running_app, tmp_path):
        state, repo, udp_port, http_port = running_app
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)
        http_post(http_port, "/api/override", {
            "normalized_callsign": "ON4CDZ", "band": "40m",
            "override_type": "excluded",
        })
        # "Restart": a fresh AppState from the same repository (§11.1 slot).
        fresh = AppState(repo)
        assert fresh.engine.get_cell("ON4BAF", "80m").status.value == "worked_by_n1mm"
        assert fresh.engine.get_cell("ON4CDZ", "40m").status.value == "excluded"


class TestFieldDayManagement:
    def test_list_create_activate(self, running_app):
        state, repo, _, http_port = running_app
        _, listing = http_get(http_port, "/api/fielddays")
        assert listing["fielddays"][0]["active"] is True

        status, result = http_post(http_port, "/api/fieldday/create", {
            "name": "Velddag 2027",
            "start_utc": "2027-06-05T13:00:00Z",
            "end_utc": "2027-06-06T13:00:00Z",
            "copy_from": repo.slug,
        })
        assert status == 200 and result["ok"]
        new_id = result["id"]

        status, result = http_post(http_port, "/api/fieldday/activate", {"id": new_id})
        assert status == 200 and result["ok"]
        # §7.4: stations gekopieerd, QSO's/overrides niet; matrix leeg
        assert len(state.engine.stations) == 2
        assert len(state.engine.qsos_by_id) == 0
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert snapshot["field_day"]["name"] == "Velddag 2027"
        assert snapshot["stats"]["cells_worked"] == 0

        # Terugwisselen: originele data intact
        http_post(http_port, "/api/fieldday/activate", {"id": repo.slug})
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert snapshot["field_day"]["name"] == "Integratietest"

    def test_update_fieldday_bands(self, running_app):
        state, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/fieldday/update", {
            "bands": ["80m", "40m", "20m"],
        })
        assert status == 200 and result["ok"]
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert snapshot["field_day"]["bands"] == ["80m", "40m", "20m"]
        assert snapshot["all_bands"][0] == "160m"

    def test_invalid_period_clean_400(self, running_app):
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/fieldday/update", {
            "start_utc": "2027-06-06T13:00:00Z",
            "end_utc": "2027-06-05T13:00:00Z",
        })
        assert status == 400 and result["ok"] is False


class TestUploads:
    def _b64(self, path):
        import base64
        return base64.b64encode(open(path, "rb").read()).decode()

    def test_station_upload_with_reimport_flow(self, running_app, tmp_path):
        state, repo, _, http_port = running_app
        # Nieuwe lijst mist ON4CDZ → eerst waarschuwing (§7.3)
        csv = tmp_path / "list.csv"
        csv.write_text("Call;sectie\nON4BAF/P;RST\nOT5X/P;CRD\n", encoding="utf-8")
        status, result = http_post(http_port, "/api/import-stations", {
            "filename": "list.csv", "content_b64": self._b64(csv),
            "confirm_removals": False,
        })
        assert status == 200
        assert result["needs_confirmation"] is True
        assert result["missing_stations"] == ["ON4CDZ/P"]
        # Nog niets gewijzigd:
        assert {s.normalized_callsign for s in state.engine.stations} == {"ON4BAF", "ON4CDZ"}

        # Bevestigen → verwijderd en nieuwe lijst actief
        status, result = http_post(http_port, "/api/import-stations", {
            "filename": "list.csv", "content_b64": self._b64(csv),
            "confirm_removals": True,
        })
        assert status == 200 and result["needs_confirmation"] is False
        assert result["removed"] == ["ON4CDZ/P"]
        assert {s.normalized_callsign for s in state.engine.stations} == {"ON4BAF", "OT5X"}
        assert repo.load_sync_log()[-1]["type"] == "station_import"

    def test_adif_upload(self, running_app):
        import base64
        state, repo, _, http_port = running_app
        from datetime import timedelta as _td
        ts = state.engine.fieldday.start_utc + _td(minutes=30)
        adif = (f"<CALL:8>ON4BAF/P <QSO_DATE:8>{ts:%Y%m%d} "
                f"<TIME_ON:4>{ts:%H%M} <FREQ:7>3.52519 <MODE:2>CW <EOR>")
        status, result = http_post(http_port, "/api/import-adif", {
            "filename": "log.adi",
            "content_b64": base64.b64encode(adif.encode()).decode(),
        })
        assert status == 200 and result["report"]["imported"] == 1
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "worked_by_n1mm"
        assert len(repo.load_qsos()) == 1
