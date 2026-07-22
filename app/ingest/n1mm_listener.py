"""UDP listener for N1MM Logger+ broadcasts (§5.5).

Transport layer only: receives datagrams, parses them via
:mod:`n1mm_parser`, keeps statistics and per-source freshness, and hands
every parsed packet to an injected handler callback. What happens with the
packet (feeding the sync engine, persisting the raw message) is the
caller's responsibility — that wiring arrives with the server (phase 11).

Guarantees:

- Runs in its own daemon thread; non-blocking shutdown via :meth:`stop`.
- Any exception while handling one packet is logged and NEVER stops the
  listener (§5.5).
- Per ``source_station`` (fallback: sender IP) the timestamp of the last
  received packet is tracked; :meth:`sources_status` reports freshness
  against a threshold — the most valuable diagnostic in the field.
- Counters: received, processed, ignored, errors.
"""

from __future__ import annotations

import logging
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from app.core.models import utc_now
from app.ingest.n1mm_parser import PacketKind, ParsedPacket, parse_packet

logger = logging.getLogger(__name__)

BUFFER_SIZE = 65535
_SOCKET_TIMEOUT_S = 0.5  # poll interval for clean shutdown

# Handler signature: (parsed_packet, sender_address) -> None
PacketHandler = Callable[[ParsedPacket, tuple[str, int]], None]


@dataclass
class ListenerStats:
    received: int = 0
    processed: int = 0   # contact / replace / delete
    ignored: int = 0     # other root tags, incl. lookupinfo
    errors: int = 0      # parse errors + handler exceptions

    def to_dict(self) -> dict:
        return {
            "received": self.received,
            "processed": self.processed,
            "ignored": self.ignored,
            "errors": self.errors,
        }


@dataclass
class SourceInfo:
    name: str
    last_seen_utc: datetime
    packet_count: int = 0
    last_address: str = ""


class N1mmUdpListener:
    """Threaded UDP listener. Start with :meth:`start`, stop with :meth:`stop`."""

    def __init__(
        self,
        handler: PacketHandler,
        host: str,
        port: int,
    ) -> None:
        self._handler = handler
        self.host = host
        self.port = port
        self.stats = ListenerStats()
        self.sources: dict[str, SourceInfo] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self.bind_error: str | None = None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        """Bind and start the receive thread. Returns False on bind failure."""
        if self._thread is not None:
            return True
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(_SOCKET_TIMEOUT_S)
        except OSError as exc:
            # Port conflict with another N1MM plugin is a documented
            # field problem (§12.3): report, do not crash.
            self.bind_error = str(exc)
            logger.error("Cannot bind UDP %s:%s: %s", self.host, self.port, exc)
            return False

        self._socket = sock
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="n1mm-udp-listener", daemon=True
        )
        self._thread.start()
        logger.info("N1MM UDP listener started on %s:%s", self.host, self.port)
        return True

    def stop(self) -> None:
        """Signal the thread to stop and wait for it (clean shutdown)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=_SOCKET_TIMEOUT_S * 4)
            self._thread = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- receive loop -----------------------------------------------------

    def _run(self) -> None:
        assert self._socket is not None
        while not self._stop_event.is_set():
            try:
                data, address = self._socket.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break  # socket closed during shutdown
            try:
                self._handle_datagram(data, address)
            except Exception:  # noqa: BLE001 — §5.5: never stop the listener
                with self._lock:
                    self.stats.errors += 1
                logger.exception("Unexpected error handling UDP packet")

    def _handle_datagram(self, data: bytes, address: tuple[str, int]) -> None:
        parsed = parse_packet(data)

        source_name = ""
        if parsed.qso is not None:
            source_name = parsed.qso.source_station
        if not source_name:
            source_name = address[0]

        with self._lock:
            self.stats.received += 1
            if parsed.kind in (PacketKind.CONTACT, PacketKind.REPLACE, PacketKind.DELETE):
                self.stats.processed += 1
            elif parsed.kind == PacketKind.IGNORED:
                self.stats.ignored += 1
            else:
                self.stats.errors += 1

            info = self.sources.get(source_name)
            if info is None:
                self.sources[source_name] = SourceInfo(
                    name=source_name,
                    last_seen_utc=utc_now(),
                    packet_count=1,
                    last_address=address[0],
                )
            else:
                info.last_seen_utc = utc_now()
                info.packet_count += 1
                info.last_address = address[0]

        try:
            self._handler(parsed, address)
        except Exception:  # noqa: BLE001 — handler bugs must not kill the loop
            with self._lock:
                self.stats.errors += 1
            logger.exception("Packet handler raised")

    # -- diagnostics ------------------------------------------------------

    def sources_status(self, freshness_threshold_seconds: int) -> list[dict]:
        """Per-source freshness report (§5.5): stale sources surface here."""
        now = utc_now()
        threshold = timedelta(seconds=freshness_threshold_seconds)
        with self._lock:
            return [
                {
                    "name": info.name,
                    "last_seen_utc": info.last_seen_utc,
                    "packet_count": info.packet_count,
                    "last_address": info.last_address,
                    "fresh": (now - info.last_seen_utc) <= threshold,
                }
                for info in sorted(self.sources.values(), key=lambda s: s.name)
            ]
