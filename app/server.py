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
        self._settings_cache = None

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
        stop_event = getattr(self, "_auto_publish_stop", None)
        if stop_event is not None:
            stop_event.set()

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
            snapshot = build_snapshot(self.engine, sources, readonly=False)
        if self._settings_cache is None:
            from app.storage.app_settings import load_app_settings
            self._settings_cache = load_app_settings()
        snapshot["ui_language"] = self._settings_cache.ui_language
        fieldday = self.engine.fieldday
        snapshot["tech"] = {
            "n1mm_udp_host": fieldday.n1mm_udp_host,
            "n1mm_udp_port": fieldday.n1mm_udp_port,
            "freshness_threshold_seconds": fieldday.freshness_threshold_seconds,
            "strict_callsign_matching": fieldday.strict_callsign_matching,
        }
        return snapshot

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
        self._require_open()
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
        self._require_open()
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

    def _require_open(self) -> None:
        if self.engine.fieldday.closed:
            raise ValueError("field day is closed; reopen it first")

    def add_station(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Manually add one station (+ button). Source = manual (§4.2)."""
        from app.core.callsign import normalize_callsign
        from app.core.models import Station, StationSource

        self._require_open()
        call = str(payload.get("callsign", "")).strip()
        if not call:
            raise ValueError("callsign is required")
        strict = self.engine.fieldday.strict_callsign_matching
        normalized = normalize_callsign(call, strict=strict)
        if normalized is None:
            raise ValueError(f"not a plausible callsign: {call}")
        with self._lock:
            if normalized in self.engine.station_index:
                existing = self.engine.station_index[normalized].original_callsign
                raise ValueError(
                    f"station already in the list as {existing} "
                    f"(same station after normalization)")
            station = Station(
                original_callsign=call,
                normalized_callsign=normalized,
                name=str(payload.get("name", "")),
                club=str(payload.get("club", "")),
                category=str(payload.get("category", "")),
                section=str(payload.get("section", "")),
                remarks=str(payload.get("remarks", "")),
                source=StationSource.MANUAL,
            )
            stations = self.engine.stations + [station]
            self.repo.save_stations(stations)
            self.engine.set_stations(stations)
        return {"ok": True, "normalized": normalized}

    def close_fieldday(self) -> dict[str, Any]:
        """Close the field day: viewing stays, all changes are blocked."""
        with self._lock:
            fieldday = self.engine.fieldday
            fieldday.closed = True
            self.repo.save_fieldday(fieldday)
        if self.listener is not None:
            self.listener.stop()
        return {"ok": True, "closed": True}

    def reopen_fieldday(self) -> dict[str, Any]:
        with self._lock:
            fieldday = self.engine.fieldday
            fieldday.closed = False
            self.repo.save_fieldday(fieldday)
        self.start_listener()
        return {"ok": True, "closed": False}

    # -- exports (§10.4) --------------------------------------------------

    def _export_filename(self, extension: str) -> str:
        from app.core.models import utc_now

        stamp = utc_now().strftime("%Y%m%d-%H%M%S")
        return f"{self.repo.slug}-{stamp}.{extension}"

    def _export_dir(self):
        from pathlib import Path

        if self._settings_cache is None:
            from app.storage.app_settings import load_app_settings
            self._settings_cache = load_app_settings()
        folder = self._settings_cache.export_folder.strip()
        if folder:
            path = Path(folder)
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except OSError:
                logger.warning("Export folder %s unusable; using default", folder)
        self.repo.exports_dir.mkdir(parents=True, exist_ok=True)
        return self.repo.exports_dir

    def export_csv(self) -> tuple[str, bytes]:
        from app.export.csv_exporter import build_csv

        with self._lock:
            content = build_csv(self.engine).encode("utf-8")
        name = self._export_filename("csv")
        (self._export_dir() / name).write_bytes(content)
        return name, content

    def export_pdf(self) -> tuple[str, bytes]:
        from app.export.pdf_exporter import build_pdf

        with self._lock:
            content = build_pdf(self.engine)
        name = self._export_filename("pdf")
        (self._export_dir() / name).write_bytes(content)
        return name, content

    # -- publishing (phase 16) --------------------------------------------

    def _publish_settings(self):
        from app.storage.app_settings import load_app_settings

        self._settings_cache = load_app_settings()
        return self._settings_cache.publish

    def publish_now(self) -> dict[str, Any]:
        """Publish snapshot + static view to GitHub (§10.3). Never raises."""
        import json as jsonlib
        from app.publish.credentials import get_token
        from app.publish.github_publisher import DEFAULT_API_BASE, GitHubPublisher

        publish = self._publish_settings()
        if not publish.repo:
            return {"ok": False, "error": "no repository configured"}
        token = get_token()
        if not token:
            return {"ok": False, "error": "no token configured "
                    "(store one via the Publish settings, or set "
                    "N1MM_TRACKER_GH_TOKEN)"}
        try:
            with self._lock:
                sources = (
                    self.listener.sources_status(
                        self.engine.fieldday.freshness_threshold_seconds)
                    if self.listener is not None else []
                )
                snapshot = build_snapshot(
                    self.engine, sources, readonly=True,
                    include_private=publish.include_private,
                )
            files: dict[str, bytes] = {
                "snapshot.json": jsonlib.dumps(snapshot, indent=1).encode("utf-8"),
            }
            static_dir = config.static_view_dir()
            for name in ("index.html", "app.js", "style.css"):
                path = static_dir / name
                if path.exists():
                    files[name] = path.read_bytes()

            publisher = GitHubPublisher(
                repo=publish.repo, branch=publish.branch, token=token,
                api_base=publish.api_base or DEFAULT_API_BASE,
            )
            result = publisher.publish_files(
                files, path_prefix=publish.path,
                message="field day tracker update",
            )
            payload = result.to_dict()
        except Exception as exc:  # noqa: BLE001 — publiceren mag nooit crashen
            logger.error("Publish failed: %s", exc)
            payload = {"ok": False, "uploaded": [], "skipped": [],
                       "errors": [str(exc)]}
        payload["at_utc"] = to_iso_z(utc_now())
        with self._lock:
            self._last_publish = payload
        self.repo.append_sync_log("publish", payload)
        return payload

    def publish_status(self) -> dict[str, Any]:
        from app.publish.credentials import token_configured

        publish = self._publish_settings()
        pages_url = ""
        if "/" in publish.repo:
            owner, name = publish.repo.split("/", 1)
            suffix = f"/{publish.path.strip('/')}/" if publish.path.strip("/") else "/"
            pages_url = f"https://{owner}.github.io/{name}{suffix}"
        with self._lock:
            last = getattr(self, "_last_publish", None)
        return {
            "ok": True,
            "settings": publish.to_dict(),
            "token_configured": token_configured(),
            "pages_url": pages_url,
            "last_result": last,
        }

    def store_publish_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.publish.credentials import store_token

        stored, message = store_token(str(payload.get("token", "")))
        return {"ok": stored, "message": message}

    def start_auto_publish(self) -> None:
        """Background timer: publish every N minutes when enabled (§10.3)."""
        import threading as threading_mod

        def loop() -> None:
            import time as time_mod

            last_run = 0.0
            while not self._auto_publish_stop.is_set():
                time_mod.sleep(5)
                try:
                    publish = self._publish_settings()
                    interval = publish.auto_interval_minutes
                    if (publish.enabled and publish.repo and interval > 0
                            and time_mod.monotonic() - last_run >= interval * 60):
                        last_run = time_mod.monotonic()
                        self.publish_now()
                except Exception:  # noqa: BLE001
                    logger.exception("Auto-publish iteration failed")

        self._auto_publish_stop = threading_mod.Event()
        thread = threading_mod.Thread(target=loop, name="auto-publish", daemon=True)
        thread.start()

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

        udp_changed = False
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
            # Phase 13: per-field-day technical settings.
            if "n1mm_udp_host" in payload:
                new_host = str(payload["n1mm_udp_host"]).strip()
                udp_changed = udp_changed or new_host != fieldday.n1mm_udp_host
                fieldday.n1mm_udp_host = new_host
            if "n1mm_udp_port" in payload:
                new_port = int(payload["n1mm_udp_port"])
                udp_changed = udp_changed or new_port != fieldday.n1mm_udp_port
                fieldday.n1mm_udp_port = new_port
            if "freshness_threshold_seconds" in payload:
                fieldday.freshness_threshold_seconds = int(
                    payload["freshness_threshold_seconds"]
                )
            if "strict_callsign_matching" in payload:
                fieldday.strict_callsign_matching = bool(
                    payload["strict_callsign_matching"]
                )
            if "status_colors" in payload and isinstance(payload["status_colors"], dict):
                fieldday.status_colors.update(
                    {str(k): str(v) for k, v in payload["status_colors"].items()}
                )
            fieldday.validate()
            self.repo.save_fieldday(fieldday)
            report = self.engine.set_fieldday(fieldday)
        if udp_changed and self.listener is not None:
            self.listener.stop()
            self.start_listener()
        return {"ok": True, "report": report.to_dict(), "udp_restarted": udp_changed}

    # -- app settings (phase 13) ------------------------------------------

    def get_app_settings(self) -> dict[str, Any]:
        from app.storage.app_settings import load_app_settings

        self._settings_cache = load_app_settings()
        return {"ok": True, "settings": self._settings_cache.to_dict()}

    def update_app_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.storage.app_settings import load_app_settings, save_app_settings

        settings = load_app_settings()
        if "ui_language" in payload:
            settings.ui_language = str(payload["ui_language"])
        if "n1mm_udp_host" in payload:
            settings.n1mm_udp_host = str(payload["n1mm_udp_host"])
        if "n1mm_udp_port" in payload:
            settings.n1mm_udp_port = int(payload["n1mm_udp_port"])
        if "freshness_threshold_seconds" in payload:
            settings.freshness_threshold_seconds = int(
                payload["freshness_threshold_seconds"]
            )
        if "strict_callsign_matching" in payload:
            settings.strict_callsign_matching = bool(payload["strict_callsign_matching"])
        if "default_selected_bands" in payload:
            settings.default_selected_bands = [
                str(b) for b in payload["default_selected_bands"]
            ]
        if "export_folder" in payload:
            settings.export_folder = str(payload["export_folder"])
        if "publish" in payload and isinstance(payload["publish"], dict):
            from app.core.models import PublishSettings

            merged = settings.publish.to_dict()
            merged.update(payload["publish"])
            settings.publish = PublishSettings.from_dict(merged)
        settings.validate()
        save_app_settings(settings)
        self._settings_cache = settings
        return {"ok": True, "settings": settings.to_dict()}

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

        self._require_open()
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

        self._require_open()
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

    def _send_file(self, content: bytes, filename: str, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

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
        if path == "/api/settings":
            self._send_json(state.get_app_settings())
            return
        if path == "/api/export/csv":
            name, content = state.export_csv()
            self._send_file(content, name, "text/csv; charset=utf-8")
            return
        if path == "/api/export/pdf":
            name, content = state.export_pdf()
            self._send_file(content, name, "application/pdf")
            return
        if path == "/api/publish/status":
            self._send_json(state.publish_status())
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
            elif path == "/api/settings":
                self._send_json(state.update_app_settings(payload))
            elif path == "/api/station/add":
                self._send_json(state.add_station(payload))
            elif path == "/api/fieldday/close":
                self._send_json(state.close_fieldday())
            elif path == "/api/fieldday/reopen":
                self._send_json(state.reopen_fieldday())
            elif path == "/api/publish/now":
                self._send_json(state.publish_now())
            elif path == "/api/publish/token":
                result = state.store_publish_token(payload)
                self._send_json(result, 200 if result.get("ok") else 400)
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
