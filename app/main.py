"""Application entrypoint (phase 11): engine + UDP listener + local server.

Usage:

    python -m app.main                       # open/start the last field day
    python -m app.main --import-excel L.xlsx # import the participant list
    python -m app.main --no-browser          # do not open the browser
    python -m app.main --http-port 8765 --udp-port 12060

On first run (no field day yet) a default field day is created — named
"Field Day <date>", period now → +48h, default bands — so the application
always starts. Creating and editing field days properly arrives with the
management UI (phase 12); until then --import-excel fills the participant
list from the command line.
"""

from __future__ import annotations

import argparse
import logging
import webbrowser
from datetime import timedelta

from app import config
from app.core.models import FieldDay, utc_now
from app.server import AppState, make_server
from app.storage import fieldday_repository as fieldday_repo
from app.storage.app_settings import load_app_settings, save_app_settings

logger = logging.getLogger(__name__)


def _open_or_create_repository(settings) -> fieldday_repo.FieldDayRepository:
    slug = settings.last_active_field_day
    if slug:
        repo = fieldday_repo.FieldDayRepository(slug)
        if repo.exists():
            return repo
    existing = fieldday_repo.list_fielddays()
    if existing:
        return fieldday_repo.FieldDayRepository(existing[0].id)

    start = utc_now()
    name = f"Field Day {start:%Y-%m-%d}"
    fieldday = FieldDay(
        id=fieldday_repo.unique_slug(name),
        name=name,
        start_utc=start,
        end_utc=start + timedelta(hours=48),
        n1mm_udp_host=settings.n1mm_udp_host,
        n1mm_udp_port=settings.n1mm_udp_port,
        selected_bands=list(settings.default_selected_bands),
        strict_callsign_matching=settings.strict_callsign_matching,
        freshness_threshold_seconds=settings.freshness_threshold_seconds,
    )
    print(f"No field day found; created '{name}' ({fieldday.id})")
    return fieldday_repo.create_fieldday(fieldday)


def _import_excel(state: AppState, path: str) -> None:
    from app.ingest.station_importer import (
        import_stations_from_csv,
        import_stations_from_excel,
    )

    if path.lower().endswith(".csv"):
        result = import_stations_from_csv(
            path, strict=state.engine.fieldday.strict_callsign_matching
        )
    else:
        result = import_stations_from_excel(
            path, strict=state.engine.fieldday.strict_callsign_matching
        )
    state.repo.save_stations(result.stations)
    state.engine.set_stations(result.stations)
    if result.band_columns:
        fieldday = state.engine.fieldday
        fieldday.selected_bands = result.band_columns
        state.repo.save_fieldday(fieldday)
        state.engine.set_fieldday(fieldday)
    state.repo.append_sync_log("station_import", result.to_report_dict())
    print(f"Imported {len(result.stations)} stations "
          f"({len(result.issues)} issues); bands: {result.band_columns}")
    for issue in result.issues:
        print(f"  row {issue.row_number}: {issue.callsign!r} — {issue.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="n1mm-fieldday-tracker")
    parser.add_argument("--http-host", default=config.DEFAULT_HTTP_HOST)
    parser.add_argument("--http-port", type=int, default=config.DEFAULT_HTTP_PORT)
    parser.add_argument("--udp-host", default=None, help="override field day UDP host")
    parser.add_argument("--udp-port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--import-excel", metavar="FILE",
                        help="import participant list (xlsx or csv) and exit")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config.ensure_app_dirs()

    settings = load_app_settings()
    repo = _open_or_create_repository(settings)
    if settings.last_active_field_day != repo.slug:
        settings.last_active_field_day = repo.slug
        save_app_settings(settings)

    state = AppState(repo)

    if args.import_excel:
        _import_excel(state, args.import_excel)
        return 0

    listener_ok = state.start_listener(host=args.udp_host, port=args.udp_port)
    if not listener_ok:
        print(f"WARNING: UDP listener could not start "
              f"({state.listener.bind_error}). QSOs will not arrive live; "
              f"see the troubleshooting chapter in the manual.")

    server = make_server(state, args.http_host, args.http_port)
    url = f"http://{args.http_host}:{args.http_port}/"
    fieldday = state.engine.fieldday
    print(f"Field day : {fieldday.name} ({repo.slug})")
    print(f"Stations  : {len(state.engine.stations)}  |  "
          f"Bands: {', '.join(fieldday.selected_bands)}")
    print(f"UDP       : {state.listener.host}:{state.listener.port} "
          f"({'listening' if listener_ok else 'NOT LISTENING'})")
    print(f"Web       : {url}   (Ctrl+C to stop)")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        state.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
