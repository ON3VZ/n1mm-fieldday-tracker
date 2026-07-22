"""Tests for app.ingest.n1mm_listener (§5.5) — phase 7.

These tests send real UDP datagrams over localhost to an ephemeral port.
"""

import socket
import time

from app.ingest.n1mm_listener import N1mmUdpListener
from app.ingest.n1mm_parser import PacketKind

from tests.test_n1mm_parser import CONTACTDELETE, contactinfo


def start_listener(handler):
    listener = N1mmUdpListener(handler, host="127.0.0.1", port=0)
    assert listener.start()
    # port 0 → OS-assigned; fetch the actual port
    port = listener._socket.getsockname()[1]
    return listener, port


def send(port: int, payload: bytes | str) -> None:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data, ("127.0.0.1", port))


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class TestListener:
    def test_receives_and_dispatches(self):
        received = []
        listener, port = start_listener(lambda p, addr: received.append(p))
        try:
            send(port, contactinfo())
            assert wait_until(lambda: len(received) == 1)
            assert received[0].kind == PacketKind.CONTACT
            assert received[0].qso.original_callsign == "ON4BAF/P"
            assert listener.stats.processed == 1
        finally:
            listener.stop()

    def test_garbage_does_not_stop_listener(self):
        received = []
        listener, port = start_listener(lambda p, addr: received.append(p))
        try:
            send(port, b"\x00\xff garbage")
            send(port, "<half><xml>")
            send(port, contactinfo())
            assert wait_until(lambda: len(received) == 3)
            assert listener.running
            assert listener.stats.received == 3
            assert listener.stats.errors == 2
            assert listener.stats.processed == 1
        finally:
            listener.stop()

    def test_handler_exception_does_not_stop_listener(self):
        calls = []

        def bad_handler(parsed, addr):
            calls.append(parsed)
            if len(calls) == 1:
                raise RuntimeError("boom")

        listener, port = start_listener(bad_handler)
        try:
            send(port, contactinfo())
            send(port, contactinfo(qso_id="a" * 32))
            assert wait_until(lambda: len(calls) == 2)
            assert listener.running
            assert listener.stats.errors == 1  # the handler crash
            assert listener.stats.processed == 2
        finally:
            listener.stop()

    def test_lookupinfo_counted_as_ignored(self):
        received = []
        listener, port = start_listener(lambda p, addr: received.append(p))
        try:
            send(port, contactinfo(tag="lookupinfo"))
            send(port, "<RadioInfo><app>N1MM</app></RadioInfo>")
            assert wait_until(lambda: listener.stats.received == 2)
            assert listener.stats.ignored == 2
            assert listener.stats.processed == 0
        finally:
            listener.stop()

    def test_delete_packet_dispatched(self):
        received = []
        listener, port = start_listener(lambda p, addr: received.append(p))
        try:
            send(port, CONTACTDELETE)
            assert wait_until(lambda: len(received) == 1)
            assert received[0].kind == PacketKind.DELETE
        finally:
            listener.stop()

    def test_sources_freshness(self):
        listener, port = start_listener(lambda p, addr: None)
        try:
            send(port, contactinfo())  # StationName CONTEST-PC1
            packet2 = contactinfo().replace("CONTEST-PC1", "CONTEST-PC2")
            send(port, packet2)
            assert wait_until(lambda: listener.stats.received == 2)

            status = listener.sources_status(freshness_threshold_seconds=300)
            names = [s["name"] for s in status]
            assert names == ["CONTEST-PC1", "CONTEST-PC2"]
            assert all(s["fresh"] for s in status)
            assert all(s["last_address"] == "127.0.0.1" for s in status)

            # With an absurdly small threshold everything is stale.
            time.sleep(0.05)
            stale = listener.sources_status(freshness_threshold_seconds=0)
            assert all(not s["fresh"] for s in stale)
        finally:
            listener.stop()

    def test_source_fallback_to_ip_when_no_stationname(self):
        listener, port = start_listener(lambda p, addr: None)
        try:
            send(port, "<RadioInfo><app>N1MM</app></RadioInfo>")  # no parsed QSO
            assert wait_until(lambda: listener.stats.received == 1)
            status = listener.sources_status(300)
            assert status[0]["name"] == "127.0.0.1"
        finally:
            listener.stop()

    def test_clean_stop(self):
        listener, port = start_listener(lambda p, addr: None)
        assert listener.running
        listener.stop()
        assert not listener.running

    def test_bind_conflict_reported_not_crash(self):
        listener1, port = start_listener(lambda p, addr: None)
        try:
            # SO_REUSEADDR maakt dubbel binden op sommige platformen mogelijk;
            # forceer het conflict daarom met een expliciet niet-beschikbaar adres.
            listener2 = N1mmUdpListener(lambda p, addr: None, host="203.0.113.1", port=12060)
            assert listener2.start() is False
            assert listener2.bind_error is not None
            assert not listener2.running
        finally:
            listener1.stop()

    def test_multiple_pcs_one_listener(self):
        # Scenario 2 uit §5.1: losse logs per PC, allemaal naar één listener.
        received = []
        listener, port = start_listener(lambda p, addr: received.append(p))
        try:
            for pc in ("PC-160M", "PC-80M", "PC-40M"):
                send(port, contactinfo().replace("CONTEST-PC1", pc)
                     .replace(GUID_PLACEHOLDER, f"{hash(pc) & 0xffffffff:032x}"))
            assert wait_until(lambda: len(received) == 3)
            assert {s["name"] for s in listener.sources_status(300)} == {
                "PC-160M", "PC-80M", "PC-40M"
            }
        finally:
            listener.stop()


GUID_PLACEHOLDER = "f9ffac4fcd3e479ca86e137df1338531"
