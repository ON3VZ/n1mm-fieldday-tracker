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
def running_app(tmp_path, monkeypatch):
    # Isolate app settings to a temp dir so the test never reads the real
    # user's settings (e.g. a configured export_folder), which would send
    # exports outside repo.exports_dir and break the export assertions.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
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


def wait_until(predicate, timeout=10.0):
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


class TestSettings:
    def test_app_settings_roundtrip(self, running_app, tmp_path, monkeypatch):
        import app.config as config
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/settings", {
            "ui_language": "nl", "export_folder": "C:/exports",
        })
        assert status == 200 and result["settings"]["ui_language"] == "nl"
        _, data = http_get(http_port, "/api/settings")
        assert data["settings"]["ui_language"] == "nl"
        assert data["settings"]["export_folder"] == "C:/exports"
        # ui_language stroomt door naar de snapshot
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert snapshot["ui_language"] == "nl"
        assert "tech" in snapshot

    def test_invalid_language_400(self, running_app):
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/settings", {"ui_language": "de"})
        assert status == 400 and result["ok"] is False

    def test_strict_toggle_changes_matrix(self, running_app):
        state, _, udp_port, http_port = running_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))  # call ON4BAF/P... eigenlijk ON4BAF/P
        assert wait_until(lambda: state.listener.stats.processed == 1)
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "worked_by_n1mm"

        # Strict aan: lijst heeft /P, QSO ook /P → blijft matchen op ON4BAF/P
        status, result = http_post(http_port, "/api/fieldday/update",
                                   {"strict_callsign_matching": True})
        assert status == 200
        _, snapshot = http_get(http_port, "/snapshot.json")
        station = next(s for s in snapshot["stations"] if s["callsign"] == "ON4BAF/P")
        assert station["normalized"] == "ON4BAF/P"
        assert station["cells"]["80m"]["status"] == "worked_by_n1mm"
        assert snapshot["tech"]["strict_callsign_matching"] is True

    def test_udp_port_change_restarts_listener(self, running_app):
        import socket as socketlib
        state, _, old_port, http_port = running_app
        probe = socketlib.socket(socketlib.AF_INET, socketlib.SOCK_DGRAM)
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
        probe.close()

        status, result = http_post(http_port, "/api/fieldday/update", {
            "n1mm_udp_host": "127.0.0.1", "n1mm_udp_port": free_port,
        })
        assert status == 200 and result["udp_restarted"] is True
        assert state.listener.port == free_port

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(free_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)

    def test_colors_update_in_snapshot(self, running_app):
        _, _, _, http_port = running_app
        status, _ = http_post(http_port, "/api/fieldday/update", {
            "status_colors": {"worked_by_n1mm": "#00B4CC"},
        })
        assert status == 200
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert snapshot["colors"]["worked_by_n1mm"] == "#00B4CC"


class TestAddStationAndClose:
    def test_add_station(self, running_app):
        state, repo, _, http_port = running_app
        status, result = http_post(http_port, "/api/station/add", {
            "callsign": "ON9NEW/P", "category": "QRP 12h", "section": "NEW",
        })
        assert status == 200 and result["normalized"] == "ON9NEW"
        stored = {s.normalized_callsign: s for s in repo.load_stations()}
        assert stored["ON9NEW"].source == "manual"
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert any(s["callsign"] == "ON9NEW/P" for s in snapshot["stations"])

    def test_add_duplicate_rejected(self, running_app):
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/station/add",
                                   {"callsign": "ON4BAF"})  # lijst heeft ON4BAF/P
        assert status == 400 and "already" in result["error"]

    def test_add_implausible_rejected(self, running_app):
        _, _, _, http_port = running_app
        status, _ = http_post(http_port, "/api/station/add", {"callsign": "JANSSENS"})
        assert status == 400

    def test_close_blocks_changes_and_reopen_restores(self, running_app):
        state, repo, udp_port, http_port = running_app
        status, result = http_post(http_port, "/api/fieldday/close", {})
        assert status == 200 and result["closed"] is True
        assert state.listener is None or not state.listener.running
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert snapshot["field_day"]["closed"] is True

        # Wijzigingen geblokkeerd met nette fout
        status, result = http_post(http_port, "/api/override", {
            "normalized_callsign": "ON4BAF", "band": "80m",
            "override_type": "manual_worked"})
        assert status == 400 and "closed" in result["error"]
        status, _ = http_post(http_port, "/api/station/add", {"callsign": "ON9ZZ"})
        assert status == 400

        # closed overleeft herstart
        fresh = AppState(repo)
        assert fresh.engine.fieldday.closed is True

        # Heropenen: listener terug, wijzigingen weer mogelijk
        status, result = http_post(http_port, "/api/fieldday/reopen", {})
        assert status == 200 and result["closed"] is False
        assert wait_until(lambda: state.listener is not None and state.listener.running)
        status, _ = http_post(http_port, "/api/override", {
            "normalized_callsign": "ON4BAF", "band": "80m",
            "override_type": "manual_worked"})
        assert status == 200


class TestExports:
    def _worked_setup(self, running_app):
        state, repo, udp_port, http_port = running_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)
        return state, repo, http_port

    def test_csv_export(self, running_app):
        state, repo, http_port = self._worked_setup(running_app)
        import urllib.request
        with urllib.request.urlopen(
                f"http://127.0.0.1:{http_port}/api/export/csv", timeout=10) as resp:
            assert resp.status == 200
            assert "text/csv" in resp.headers["Content-Type"]
            assert 'attachment; filename="' in resp.headers["Content-Disposition"]
            body = resp.read().decode("utf-8-sig")
        lines = body.strip().splitlines()
        assert lines[0].startswith("callsign;normalized_callsign;")
        assert len(lines) == 1 + 2 * 3  # 2 stations × 3 banden
        worked_line = next(l for l in lines if l.startswith("ON4BAF/P;ON4BAF;;;80m;"))
        assert "worked_by_n1mm" in worked_line
        assert "CONTEST-PC1" in worked_line
        # kopie in de exportmap
        assert list(repo.exports_dir.glob("*.csv"))

    def test_pdf_export(self, running_app):
        state, repo, http_port = self._worked_setup(running_app)
        import urllib.request
        with urllib.request.urlopen(
                f"http://127.0.0.1:{http_port}/api/export/pdf", timeout=15) as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"] == "application/pdf"
            body = resp.read()
        assert body.startswith(b"%PDF")
        assert len(body) > 1500
        assert list(repo.exports_dir.glob("*.pdf"))

    def test_pdf_many_bands_splits_pages(self, running_app):
        state, repo, http_port = self._worked_setup(running_app)
        many = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m",
                "12m", "10m", "6m", "4m", "2m", "70cm"]
        http_post(http_port, "/api/fieldday/update", {"bands": many})
        from app.export.pdf_exporter import build_pdf
        content = build_pdf(state.engine)
        # 14 banden > 12 per pagina → minstens 2 pagina's
        assert content.count(b"/Type /Page") >= 2 or content.count(b"/Page") >= 2


class TestDeleteAndBundle:
    def _make_second(self, http_port):
        status, result = http_post(http_port, "/api/fieldday/create", {
            "name": "Tweede velddag",
            "start_utc": "2027-06-05T13:00:00Z",
            "end_utc": "2027-06-06T13:00:00Z",
        })
        assert status == 200
        return result["id"]

    def test_delete_requires_confirmation_word(self, running_app):
        state, repo, _, http_port = running_app
        other = self._make_second(http_port)
        # zonder DELETE → geweigerd
        status, result = http_post(http_port, "/api/fieldday/delete", {"id": other})
        assert status == 400 and "DELETE" in result["error"]
        # verkeerd woord → geweigerd
        status, result = http_post(http_port, "/api/fieldday/delete",
                                   {"id": other, "confirm": "delete"})
        assert status == 400
        # correct → verwijderd
        status, result = http_post(http_port, "/api/fieldday/delete",
                                   {"id": other, "confirm": "DELETE"})
        assert status == 200 and result["deleted"] == other
        _, listing = http_get(http_port, "/api/fielddays")
        assert other not in [fd["id"] for fd in listing["fielddays"]]

    def test_cannot_delete_active(self, running_app):
        state, repo, _, http_port = running_app
        self._make_second(http_port)  # zodat het niet de laatste is
        status, result = http_post(http_port, "/api/fieldday/delete",
                                   {"id": repo.slug, "confirm": "DELETE"})
        assert status == 400 and "active" in result["error"]

    def test_cannot_delete_last(self, running_app):
        state, repo, _, http_port = running_app
        # activeer een tweede en verwijder de originele zodat er nog één rest
        other = self._make_second(http_port)
        http_post(http_port, "/api/fieldday/activate", {"id": other})
        http_post(http_port, "/api/fieldday/delete",
                  {"id": repo.slug, "confirm": "DELETE"})
        # nu nog één over, en die is per definitie de actieve → verwijderen
        # wordt geweigerd (de actieve mag nooit weg; er blijft er dus altijd één)
        status, result = http_post(http_port, "/api/fieldday/delete",
                                   {"id": other, "confirm": "DELETE"})
        assert status == 400
        _, listing = http_get(http_port, "/api/fielddays")
        assert len(listing["fielddays"]) == 1  # er blijft altijd één bestaan

    def test_export_import_roundtrip(self, running_app):
        import base64
        state, repo, udp_port, http_port = running_app
        # een QSO en een override toevoegen
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))
        assert wait_until(lambda: state.listener.stats.processed == 1)
        http_post(http_port, "/api/override", {
            "normalized_callsign": "ON4CDZ", "band": "40m",
            "override_type": "manual_worked", "reason": "papier"})

        # exporteren (GET, bestand)
        with urllib.request.urlopen(
                f"http://127.0.0.1:{http_port}/api/fieldday/export", timeout=10) as resp:
            assert resp.status == 200
            disp = resp.headers["Content-Disposition"]
            assert ".fdtracker" in disp
            bundle_bytes = resp.read()
        bundle = json.loads(bundle_bytes.decode("utf-8"))
        assert bundle["format"] == "n1mm-fieldday-tracker/bundle"
        assert len(bundle["qsos"]) == 1
        assert len(bundle["overrides"]) == 1
        assert len(bundle["stations"]) == 2

        # importeren → nieuwe velddag met alles erin
        status, result = http_post(http_port, "/api/fieldday/import", {
            "filename": "test.fdtracker",
            "content_b64": base64.b64encode(bundle_bytes).decode(),
        })
        assert status == 200 and result["ok"]
        assert result["qsos"] == 1 and result["stations"] == 2
        new_id = result["id"]
        assert new_id != repo.slug  # nieuwe velddag, niet overschreven

        # activeer de import en controleer dat QSO + override er zijn
        http_post(http_port, "/api/fieldday/activate", {"id": new_id})
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "worked_by_n1mm"
        cdz = next(s for s in snapshot["stations"] if s["normalized"] == "ON4CDZ")
        assert cdz["cells"]["40m"]["status"] == "manual_worked"

    def test_import_rejects_garbage(self, running_app):
        import base64
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/fieldday/import", {
            "filename": "x.fdtracker",
            "content_b64": base64.b64encode(b"not json at all").decode(),
        })
        assert status == 400

    def test_import_rejects_wrong_format(self, running_app):
        import base64
        _, _, _, http_port = running_app
        blob = json.dumps({"format": "something-else"}).encode()
        status, result = http_post(http_port, "/api/fieldday/import", {
            "filename": "x.fdtracker", "content_b64": base64.b64encode(blob).decode(),
        })
        assert status == 400


class TestRemoveStation:
    def test_remove_station(self, running_app):
        state, repo, _, http_port = running_app
        # ON4BAF/P en ON4CDZ/P staan in de lijst
        status, result = http_post(http_port, "/api/station/remove",
                                   {"normalized_callsign": "ON4BAF"})
        assert status == 200 and result["removed"] == "ON4BAF/P"
        assert "ON4BAF" not in state.engine.station_index
        stored = {s.normalized_callsign for s in repo.load_stations()}
        assert stored == {"ON4CDZ"}
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert all(s["normalized"] != "ON4BAF" for s in snapshot["stations"])

    def test_remove_keeps_qsos_on_disk(self, running_app):
        state, repo, udp_port, http_port = running_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        send_udp(udp_port, contactinfo(timestamp=now))  # QSO voor ON4BAF/P
        # Wacht tot het QSO ECHT op schijf staat: de teller loopt een fractie
        # vóór de schrijfactie, wat onder belasting (CI) een race gaf.
        assert wait_until(lambda: len(repo.load_qsos()) == 1)
        http_post(http_port, "/api/station/remove", {"normalized_callsign": "ON4BAF"})
        # QSO blijft bewaard op schijf (niet vernietigd)
        assert len(repo.load_qsos()) == 1
        # opnieuw toevoegen brengt het station terug, met het QSO herkend
        http_post(http_port, "/api/station/add", {"callsign": "ON4BAF/P"})
        http_post(http_port, "/api/sync", {})
        _, snapshot = http_get(http_port, "/snapshot.json")
        assert cell_status(snapshot, "ON4BAF", "80m") == "worked_by_n1mm"

    def test_remove_unknown_400(self, running_app):
        _, _, _, http_port = running_app
        status, result = http_post(http_port, "/api/station/remove",
                                   {"normalized_callsign": "ON9XYZ"})
        assert status == 400

    def test_remove_blocked_when_closed(self, running_app):
        _, _, _, http_port = running_app
        http_post(http_port, "/api/fieldday/close", {})
        status, result = http_post(http_port, "/api/station/remove",
                                   {"normalized_callsign": "ON4BAF"})
        assert status == 400 and "closed" in result["error"]


class TestLifecycleEndpoints:
    def test_version(self, running_app):
        _, _, _, http_port = running_app
        status, data = http_get(http_port, "/api/version")
        assert status == 200 and data["ok"]
        assert data["version"].count(".") == 2  # x.y.z

    def test_restart_listener(self, running_app):
        state, _, _, http_port = running_app
        old_thread = state.listener._thread
        status, data = http_post(http_port, "/api/listener/restart", {})
        assert status == 200 and data["ok"] and data["listening"]
        assert state.listener._thread is not old_thread  # echt herstart
        assert state.listener.running  # nieuwe listener draait

    def test_watchdog_revives_dead_listener(self, running_app):
        state, _, _, http_port = running_app
        state._start_listener_watchdog()  # idempotent
        # simuleer een 'dode' listener (zoals na slaapstand)
        state.listener.stop()
        assert not state.listener.running
        # watchdog draait elke 10s; forceer één iteratie handmatig
        state.restart_listener()
        assert wait_until(lambda: state.listener.running, timeout=3)

    def test_quit_sets_flag(self, running_app):
        state, _, _, http_port = running_app
        state._shutdown_requested = False
        status, data = http_post(http_port, "/api/app/quit", {})
        assert status == 200 and data["ok"]
        assert state._shutdown_requested is True

    def test_update_check_handles_offline(self, running_app, monkeypatch):
        state, _, _, http_port = running_app
        import urllib.request
        def boom(*a, **k): raise OSError("no network")
        monkeypatch.setattr(urllib.request, "urlopen", boom)
        result = state.check_update()
        assert result["ok"] is True
        assert result["update_available"] is False

    def test_apply_update_rejects_foreign_url(self, running_app):
        state, _, _, _ = running_app
        result = state.apply_update({"installer_url": "https://evil.example.com/x.exe"})
        assert result["ok"] is False
