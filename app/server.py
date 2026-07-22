"""Local HTTP server + application wiring (§3.1, phase 11).

``AppState`` owns the running field day: repository, sync engine and UDP
listener, and persists changes (QSOs, overrides) atomically. The HTTP
server serves the static view plus a small JSON API:

    GET  /snapshot.json           freshly built snapshot (the view polls this)
    GET  /api/status              listener counters + per-source freshness
    POST /api/override            {normalized_callsign, band, override_type,
                                   reason?, set_by?}
    POST /api/override/clear      {normalized_callsign, band}
    POST /api/sync                full recompute; returns the report
    POST /api/station-remarks     {normalized_callsign, remarks}

Business logic stays in core/; this module only wires and persists (BR-13).
Raw UDP packets — including ignored ones — are appended to
``raw_packets.log`` in the field day directory (§5.5).
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app import config
from app.core.models import Override, utc_now, to_iso_z
from app.core.sync_engine import SyncEngine
from app.ingest.n1mm_listener import N1mmUdpListener
from app.ingest.n1mm_parser import PacketKind, ParsedPacket
from app.storage.fieldday_repository import FieldDayRepository
from app.view.snapshot_builder import build_snapshot

logger = logging.getLogger(__name__)


class AppState:
    """The running application: one active field day, engine and listener."""

    def __init__(self, repo: FieldDayRepository) -> None:
        self.repo = repo
        fieldday = repo.load_fieldday()
        if fieldday is None:
            raise ValueError(f"No field day found in {repo.dir}")
        self.engine = SyncEngine(
            fieldday,
            repo.load_stations(),
            repo.load_qsos(),
            repo.load_overrides(),
        )
        self.listener: N1mmUdpListener | None = None
        self._lock = threading.Lock()
        self._raw_log_path = repo.dir / "raw_packets.log"

    # -- listener wiring --------------------------------------------------

    def start_listener(self, host: str | None = None, port: int | None = None) -> bool:
        fieldday = self.engine.fieldday
        self.listener = N1mmUdpListener(
            self._on_packet,
            host=host if host is not None else fieldday.n1mm_udp_host,
            port=port if port is not None else fieldday.n1mm_udp_port,
        )
        return self.listener.start()

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()

    def _append_raw(self, parsed: ParsedPacket, address: tuple[str, int]) -> None:
        """§5.5: retain every raw packet, also ignored/error ones."""
        try:
            with open(self._raw_log_path, "a", encoding="utf-8") as handle:
                handle.write(
                    f"--- {to_iso_z(utc_now())} {address[0]} "
                    f"{parsed.kind.value} {parsed.reason}\n{parsed.raw}\n"
                )
        except OSError:
            logger.warning("Cannot append to raw packet log", exc_info=True)

    def _on_packet(self, parsed: ParsedPacket, address: tuple[str, int]) -> None:
        self._append_raw(parsed, address)
        if parsed.kind in (PacketKind.CONTACT, PacketKind.REPLACE):
            with self._lock:
                self.engine.upsert_qso(parsed.qso)
                self.repo.save_qsos(self.engine.current_qsos())
        elif parsed.kind == PacketKind.DELETE:
            with self._lock:
                changed = self.engine.mark_deleted(parsed.qso_id)
                if changed or parsed.qso_id in self.engine.qsos_by_id:
                    self.repo.save_qsos(self.engine.current_qsos())

    # -- API operations ---------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            sources = (
                self.listener.sources_status(
                    self.engine.fieldday.freshness_threshold_seconds
                )
                if self.listener is not None
                else []
            )
            return build_snapshot(self.engine, sources, readonly=False)

    def status(self) -> dict[str, Any]:
        listener = self.listener
        return {
            "listener_running": bool(listener and listener.running),
            "bind_error": listener.bind_error if listener else None,
            "udp": listener.stats.to_dict() if listener else {},
            "sources": [
                {**entry, "last_seen_utc": to_iso_z(entry["last_seen_utc"])}
                for entry in (
                    listener.sources_status(
                        self.engine.fieldday.freshness_threshold_seconds
                    )
                    if listener
                    else []
                )
            ],
        }

    def set_override(self, payload: dict[str, Any]) -> dict[str, Any]:
        override = Override(
            normalized_callsign=str(payload.get("normalized_callsign", "")),
            band=str(payload.get("band", "")),
            override_type=payload.get("override_type", ""),
            reason=str(payload.get("reason", "")),
            set_by=str(payload.get("set_by", "")),
        )
        with self._lock:
            changed = self.engine.set_override(override)
            self.repo.save_overrides(self.engine.current_overrides())
        return {"ok": True, "changed_cells": [list(key) for key in changed]}

    def clear_override(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            changed = self.engine.clear_override(
                str(payload.get("normalized_callsign", "")),
                str(payload.get("band", "")),
            )
            self.repo.save_overrides(self.engine.current_overrides())
        return {"ok": True, "changed_cells": [list(key) for key in changed]}

    def full_sync(self) -> dict[str, Any]:
        with self._lock:
            report = self.engine.full_recompute()
            self.repo.append_sync_log("manual_sync", report.to_dict())
        return {"ok": True, "report": report.to_dict()}

    def set_station_remarks(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = str(payload.get("normalized_callsign", ""))
        remarks = str(payload.get("remarks", ""))
        with self._lock:
            station = self.engine.station_index.get(normalized)
            if station is None:
                return {"ok": False, "error": "unknown station"}
            station.remarks = remarks
            self.repo.save_stations(self.engine.stations)
        return {"ok": True}

    # -- field day management (phase 12) ----------------------------------

    def list_fielddays(self) -> dict[str, Any]:
        from app.storage.fieldday_repository import list_fielddays

        entries = []
        for fieldday in list_fielddays(root_dir=self.repo.root_dir):
            entries.append({
                "id": fieldday.id,
                "name": fieldday.name,
                "start_utc": to_iso_z(fieldday.start_utc),
                "end_utc": to_iso_z(fieldday.end_utc),
                "bands": list(fieldday.selected_bands),
                "active": fieldday.id == self.repo.slug,
            })
        return {"ok": True, "fielddays": entries}

    def create_fieldday(self, payload: dict[str, Any]) -> dict[str, Any]:
        from datetime import datetime
        from app.core.models import FieldDay, parse_iso_z
        from app.storage.fieldday_repository import (
            FieldDayRepository, create_fieldday, unique_slug,
        )

        name = str(payload.get("name", "")).strip()
        start = parse_iso_z(payload.get("start_utc"), "start_utc")
        end = parse_iso_z(payload.get("end_utc"), "end_utc")
        if not name or start is None or end is None:
            raise ValueError("name, start_utc and end_utc are required")

        copy_from = str(payload.get("copy_from", "") or "")
        template = None
        template_stations = []
        if copy_from:
            source_repo = FieldDayRepository(copy_from, root_dir=self.repo.root_dir)
            template = source_repo.load_fieldday()
            if template is None:
                raise ValueError(f"copy_from field day not found: {copy_from}")
            template_stations = source_repo.load_stations()

        fieldday = FieldDay(
            id=unique_slug(name, root_dir=self.repo.root_dir),
            name=name,
            start_utc=start,
            end_utc=end,
            location=str(payload.get("location", "")),
            event_callsign=str(payload.get("event_callsign", "")),
            organizer_club=str(payload.get("organizer_club", "")),
            # §7.4: copied → stations, bands, colors, UDP, matching settings.
            # NOT copied → QSOs, overrides, sync log, period (matrix empty).
            selected_bands=list(payload.get("bands")
                                or (template.selected_bands if template
                                    else self.engine.fieldday.selected_bands)),
            status_colors=dict(template.status_colors) if template
            else dict(self.engine.fieldday.status_colors),
            n1mm_udp_host=template.n1mm_udp_host if template
            else self.engine.fieldday.n1mm_udp_host,
            n1mm_udp_port=template.n1mm_udp_port if template
            else self.engine.fieldday.n1mm_udp_port,
            strict_callsign_matching=template.strict_callsign_matching
            if template else self.engine.fieldday.strict_callsign_matching,
            freshness_threshold_seconds=template.freshness_threshold_seconds
            if template else self.engine.fieldday.freshness_threshold_seconds,
        )
        new_repo = create_fieldday(fieldday, root_dir=self.repo.root_dir)
        if template_stations:
            new_repo.save_stations(template_stations)
        return {"ok": True, "id": fieldday.id}

    def activate_fieldday(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.storage.app_settings import load_app_settings, save_app_settings
        from app.storage.fieldday_repository import FieldDayRepository

        slug = str(payload.get("id", ""))
        new_repo = FieldDayRepository(slug, root_dir=self.repo.root_dir)
        fieldday = new_repo.load_fieldday()
        if fieldday is None:
            return {"ok": False, "error": f"field day not found: {slug}"}

        with self._lock:
            if self.listener is not None:
                self.listener.stop()
            self.repo = new_repo
            self._raw_log_path = new_repo.dir / "raw_packets.log"
            self.engine = SyncEngine(
                fieldday,
                new_repo.load_stations(),
                new_repo.load_qsos(),
                new_repo.load_overrides(),
            )
        self.start_listener()
        try:
            settings = load_app_settings()
            settings.last_active_field_day = slug
            save_app_settings(settings)
        except Exception:  # settings persistence is best-effort here
            logger.warning("Could not persist last_active_field_day", exc_info=True)
        return {"ok": True, "id": slug}

    def update_fieldday(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.core.models import parse_iso_z

        with self._lock:
            fieldday = self.engine.fieldday
            if "name" in payload:
                fieldday.name = str(payload["name"]).strip()
            if "location" in payload:
                fieldday.location = str(payload["location"])
            if "event_callsign" in payload:
                fieldday.event_callsign = str(payload["event_callsign"])
            if "organizer_club" in payload:
                fieldday.organizer_club = str(payload["organizer_club"])
            if "remarks" in payload:
                fieldday.remarks = str(payload["remarks"])
            if "start_utc" in payload:
                fieldday.start_utc = parse_iso_z(payload["start_utc"], "start_utc")
            if "end_utc" in payload:
                fieldday.end_utc = parse_iso_z(payload["end_utc"], "end_utc")
            if "bands" in payload:
                fieldday.selected_bands = [str(b) for b in payload["bands"]]
            fieldday.validate()
            self.repo.save_fieldday(fieldday)
            report = self.engine.set_fieldday(fieldday)
        return {"ok": True, "report": report.to_dict()}

    # -- uploads (base64 JSON; local app, small files) --------------------

    @staticmethod
    def _decode_upload(payload: dict[str, Any]) -> tuple[str, bytes]:
        import base64

        filename = str(payload.get("filename", "upload"))
        content = payload.get("content_b64", "")
        try:
            return filename, base64.b64decode(content)
        except Exception as exc:
            raise ValueError(f"invalid file upload: {exc}") from exc

    def import_stations(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upload + import the participant list with the §7.3 re-import flow.

        When existing (non-manual) stations are missing from the new list
        and ``confirm_removals`` is not set, nothing is changed and the
        missing callsigns are returned for an explicit warning first.
        Manual overrides are untouched (separate file); manually added
        stations never disappear automatically; changed fields update.
        """
        import tempfile
        from pathlib import Path
        from app.ingest.station_importer import (
            import_stations_from_csv, import_stations_from_excel,
        )

        filename, blob = self._decode_upload(payload)
        confirm = bool(payload.get("confirm_removals", False))
        suffix = ".csv" if filename.lower().endswith(".csv") else ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(blob)
            tmp_path = Path(tmp.name)
        try:
            strict = self.engine.fieldday.strict_callsign_matching
            if suffix == ".csv":
                result = import_stations_from_csv(tmp_path, strict=strict)
            else:
                result = import_stations_from_excel(tmp_path, strict=strict)
        finally:
            tmp_path.unlink(missing_ok=True)

        with self._lock:
            existing = {s.normalized_callsign: s for s in self.engine.stations}
            incoming = {s.normalized_callsign: s for s in result.stations}

            missing = [
                s.original_callsign
                for key, s in existing.items()
                if key not in incoming and s.source != "manual"
            ]
            if missing and not confirm:
                return {
                    "ok": True,
                    "needs_confirmation": True,
                    "missing_stations": missing,
                    "report": result.to_report_dict(),
                }

            merged: list = []
            for station in result.stations:
                previous = existing.get(station.normalized_callsign)
                if previous is not None and previous.remarks and not station.remarks:
                    station.remarks = previous.remarks  # don't lose local notes
                merged.append(station)
            for key, station in existing.items():
                if key not in incoming and station.source == "manual":
                    merged.append(station)  # §7.3: manual stations stay

            self.repo.save_stations(merged)
            self.engine.set_stations(merged)
            if result.band_columns:
                fieldday = self.engine.fieldday
                fieldday.selected_bands = result.band_columns
                self.repo.save_fieldday(fieldday)
                self.engine.set_fieldday(fieldday)
            self.repo.append_sync_log("station_import", result.to_report_dict())
        return {
            "ok": True,
            "needs_confirmation": False,
            "imported": len(result.stations),
            "removed": missing if confirm else [],
            "report": result.to_report_dict(),
        }

    def import_adif(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.ingest.adif_importer import import_adif_text

        filename, blob = self._decode_upload(payload)
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            text = blob.decode("latin-1")

        with self._lock:
            existing_ids = set(self.engine.qsos_by_id.keys())
            new_qsos, report = import_adif_text(
                text, self.engine.fieldday, self.engine.stations,
                existing_ids, source_file=filename,
            )
            for qso in new_qsos:
                self.engine.upsert_qso(qso)
            if new_qsos:
                self.repo.save_qsos(self.engine.current_qsos())
            self.repo.append_sync_log("adif_import", report.to_dict())
        return {"ok": True, "report": report.to_dict()}


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class TrackerRequestHandler(SimpleHTTPRequestHandler):
    """Static files from the view directory + the JSON API."""

    app_state: AppState | None = None  # injected via make_server

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(config.static_view_dir()), **kwargs)

    def log_message(self, fmt: str, *args) -> None:  # quiet: log at DEBUG
        logger.debug("HTTP %s", fmt % args)

    # -- helpers ----------------------------------------------------------

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except (ValueError, OSError):
            return None

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        path = self.path.split("?", 1)[0]
        state = self.app_state
        if state is None:
            self._send_json({"ok": False, "error": "server not ready"}, 503)
            return
        if path == "/snapshot.json":
            self._send_json(state.snapshot())
            return
        if path == "/api/status":
            self._send_json(state.status())
            return
        if path == "/api/fielddays":
            self._send_json(state.list_fielddays())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        state = self.app_state
        if state is None:
            self._send_json({"ok": False, "error": "server not ready"}, 503)
            return
        payload = self._read_json_body()
        if payload is None:
            self._send_json({"ok": False, "error": "invalid JSON body"}, 400)
            return
        try:
            if path == "/api/override":
                self._send_json(state.set_override(payload))
            elif path == "/api/override/clear":
                self._send_json(state.clear_override(payload))
            elif path == "/api/sync":
                self._send_json(state.full_sync())
            elif path == "/api/station-remarks":
                result = state.set_station_remarks(payload)
                self._send_json(result, 200 if result.get("ok") else 404)
            elif path == "/api/fieldday/create":
                self._send_json(state.create_fieldday(payload))
            elif path == "/api/fieldday/activate":
                result = state.activate_fieldday(payload)
                self._send_json(result, 200 if result.get("ok") else 404)
            elif path == "/api/fieldday/update":
                self._send_json(state.update_fieldday(payload))
            elif path == "/api/import-stations":
                self._send_json(state.import_stations(payload))
            elif path == "/api/import-adif":
                self._send_json(state.import_adif(payload))
            else:
                self._send_json({"ok": False, "error": "unknown endpoint"}, 404)
        except (ValueError, TypeError) as exc:
            # Invalid override type, empty callsign, ... → clean 400.
            self._send_json({"ok": False, "error": str(exc)}, 400)
        except Exception:  # noqa: BLE001 — API bugs must not kill the server
            logger.exception("API error on %s", path)
            self._send_json({"ok": False, "error": "internal error"}, 500)


def make_server(state: AppState, host: str, port: int) -> ThreadingHTTPServer:
    handler = type(
        "BoundTrackerRequestHandler", (TrackerRequestHandler,), {"app_state": state}
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server
