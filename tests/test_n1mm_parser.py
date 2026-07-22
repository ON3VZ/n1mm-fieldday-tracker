"""Tests for app.ingest.n1mm_parser (§5.2–§5.4) — phase 7.

Fixtures mirror the real packet examples from the N1MM Logger+ documentation
appendix "External UDP Messages" (ID GUID format, rxfreq in 10 Hz units,
lookupinfo structurally identical to contactinfo).
"""

from datetime import datetime, timezone

from app.ingest.n1mm_parser import PacketKind, parse_packet

UTC = timezone.utc

GUID = "f9ffac4fcd3e479ca86e137df1338531"


def contactinfo(
    tag: str = "contactinfo",
    call: str = "ON4BAF/P",
    rxfreq: str = "352519",
    txfreq: str = "352519",
    band: str = "3.5",
    qso_id: str = GUID,
    is_claimed: str = "1",
    is_original: str = "True",
    timestamp: str = "2026-06-06 14:43:38",
    extra: str = "",
) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<{tag}>
<app>N1MM</app>
<contestname>FDREG1</contestname>
<contestnr>73</contestnr>
<timestamp>{timestamp}</timestamp>
<mycall>ON6WL/P</mycall>
<band>{band}</band>
<rxfreq>{rxfreq}</rxfreq>
<txfreq>{txfreq}</txfreq>
<operator>OP1</operator>
<mode>CW</mode>
<call>{call}</call>
<snt>599</snt>
<rcv>599</rcv>
<exchangel></exchangel>
<section></section>
<StationName>CONTEST-PC1</StationName>
<ID>{qso_id}</ID>
<IsClaimedQso>{is_claimed}</IsClaimedQso>
<IsOriginal>{is_original}</IsOriginal>
<NetworkedCompNr>1</NetworkedCompNr>
<oldtimestamp>{timestamp}</oldtimestamp>
<oldcall>{call}</oldcall>
{extra}
</{tag}>"""


CONTACTDELETE = f"""<?xml version="1.0" encoding="utf-8"?>
<contactdelete>
<app>N1MM</app>
<timestamp>2026-06-06 14:43:38</timestamp>
<mycall>ON6WL/P</mycall>
<band>3.5</band>
<call>ON4BAF/P</call>
<contestnr>73</contestnr>
<StationName>CONTEST-PC1</StationName>
<ID>{GUID}</ID>
</contactdelete>"""


class TestContactInfo:
    def test_full_mapping(self):
        result = parse_packet(contactinfo())
        assert result.kind == PacketKind.CONTACT
        qso = result.qso
        assert qso.qso_id == GUID
        assert qso.original_callsign == "ON4BAF/P"
        assert qso.normalized_callsign == "ON4BAF"
        assert qso.frequency_khz == 3525.19       # 352519 × 10 Hz → kHz
        assert qso.band == "80m"                  # derived from frequency
        assert qso.mode == "CW"
        assert qso.timestamp_utc == datetime(2026, 6, 6, 14, 43, 38, tzinfo=UTC)
        assert qso.source == "n1mm_udp"
        assert qso.source_station == "CONTEST-PC1"
        assert qso.is_original is True
        assert qso.is_claimed is True
        assert qso.contest_name == "FDREG1"
        assert qso.raw_message.startswith("<?xml")

    def test_bytes_input(self):
        result = parse_packet(contactinfo().encode("utf-8"))
        assert result.kind == PacketKind.CONTACT

    def test_band_text_field_never_used_br08(self):
        # Lying/locale <band> text ("7,0") must not matter: rxfreq says 80m.
        result = parse_packet(contactinfo(band="7,0"))
        assert result.qso.band == "80m"
        # And comma-locale band text with matching freq also fine:
        result2 = parse_packet(contactinfo(band="3,5"))
        assert result2.qso.band == "80m"

    def test_txfreq_fallback_when_rxfreq_zero(self):
        result = parse_packet(contactinfo(rxfreq="0", txfreq="702000"))
        assert result.qso.frequency_khz == 7020.0
        assert result.qso.band == "40m"

    def test_txfreq_fallback_when_rxfreq_missing(self):
        packet = contactinfo().replace("<rxfreq>352519</rxfreq>", "")
        result = parse_packet(packet)
        assert result.qso.frequency_khz == 3525.19

    def test_xqso_not_claimed(self):
        result = parse_packet(contactinfo(is_claimed="0"))
        assert result.kind == PacketKind.CONTACT
        assert result.qso.is_claimed is False

    def test_forwarded_all_computers(self):
        result = parse_packet(contactinfo(is_original="False"))
        assert result.qso.is_original is False

    def test_other_contest_still_parsed(self):
        # §5.4: deviations from FDREG1 are logged but not blocked.
        packet = contactinfo().replace("FDREG1", "CQWW")
        result = parse_packet(packet)
        assert result.kind == PacketKind.CONTACT
        assert result.qso.contest_name == "CQWW"


class TestContactReplaceAndDelete:
    def test_replace(self):
        result = parse_packet(contactinfo(tag="contactreplace", call="ON4CDZ/P"))
        assert result.kind == PacketKind.REPLACE
        assert result.qso.qso_id == GUID
        assert result.qso.original_callsign == "ON4CDZ/P"

    def test_delete(self):
        result = parse_packet(CONTACTDELETE)
        assert result.kind == PacketKind.DELETE
        assert result.qso_id == GUID
        assert result.qso is None


class TestRootTagFilter:
    def test_lookupinfo_ignored(self):
        # §5.3: identical structure to contactinfo — MUST be ignored.
        result = parse_packet(contactinfo(tag="lookupinfo"))
        assert result.kind == PacketKind.IGNORED
        assert result.root_tag == "lookupinfo"
        assert result.qso is None

    def test_other_broadcasts_ignored(self):
        for tag in ("RadioInfo", "AppInfo", "spot", "dynamicresults"):
            packet = f"<{tag}><app>N1MM</app><StationName>PC1</StationName></{tag}>"
            result = parse_packet(packet)
            assert result.kind == PacketKind.IGNORED
            assert result.root_tag == tag.lower()

    def test_raw_preserved_even_when_ignored(self):
        # §5.5: raw packets must be retained, also when ignored.
        packet = contactinfo(tag="lookupinfo")
        result = parse_packet(packet)
        assert result.raw == packet


class TestRobustness:
    def test_garbage_is_error_not_exception(self):
        result = parse_packet(b"\x00\xffthis is not xml at all")
        assert result.kind == PacketKind.ERROR
        assert "invalid XML" in result.reason

    def test_truncated_xml(self):
        result = parse_packet(contactinfo()[:120])
        assert result.kind == PacketKind.ERROR

    def test_empty_packet(self):
        assert parse_packet(b"").kind == PacketKind.ERROR

    def test_missing_id(self):
        packet = contactinfo().replace(f"<ID>{GUID}</ID>", "")
        result = parse_packet(packet)
        assert result.kind == PacketKind.ERROR
        assert "ID" in result.reason

    def test_missing_call(self):
        packet = contactinfo().replace("<call>ON4BAF/P</call>", "")
        result = parse_packet(packet)
        assert result.kind == PacketKind.ERROR
        assert "call" in result.reason

    def test_invalid_timestamp(self):
        result = parse_packet(contactinfo(timestamp="gisteren"))
        assert result.kind == PacketKind.ERROR
        assert "timestamp" in result.reason

    def test_frequency_outside_all_bands(self):
        # 5000 kHz = 500000 in 10 Hz units → no band → not processed (§8.2)
        result = parse_packet(contactinfo(rxfreq="500000", txfreq="500000"))
        assert result.kind == PacketKind.ERROR
        assert "band not determinable" in result.reason

    def test_zero_frequencies(self):
        result = parse_packet(contactinfo(rxfreq="0", txfreq="0"))
        assert result.kind == PacketKind.ERROR
        assert "rxfreq" in result.reason

    def test_docs_print_artifact_timestamp_tolerated(self):
        # The docs examples contain "16 :43:38"; tolerate it.
        result = parse_packet(contactinfo(timestamp="2026-06-06 14 :43:38"))
        assert result.kind == PacketKind.CONTACT
        assert result.qso.timestamp_utc.minute == 43

    def test_case_insensitive_tags(self):
        packet = contactinfo().replace("<ID>", "<id>").replace("</ID>", "</id>")
        result = parse_packet(packet)
        assert result.kind == PacketKind.CONTACT
        assert result.qso.qso_id == GUID


class TestParserToEngineChain:
    """End-to-end: parsed packets feeding the sync engine (§5.2 edit flow)."""

    def _engine(self):
        from datetime import datetime, timezone
        from app.core.models import FieldDay, Station
        from app.core.sync_engine import SyncEngine

        fd = FieldDay(
            id="fd", name="Velddag",
            start_utc=datetime(2026, 6, 6, 13, 0, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 7, 13, 0, tzinfo=timezone.utc),
            selected_bands=["160m", "80m", "40m"],
        )
        stations = [
            Station(original_callsign="ON4BAF/P", normalized_callsign="ON4BAF"),
            Station(original_callsign="ON4CDZ/P", normalized_callsign="ON4CDZ"),
        ]
        return SyncEngine(fd, stations, [], [])

    def _apply(self, engine, packet: str):
        result = parse_packet(packet)
        if result.kind in (PacketKind.CONTACT, PacketKind.REPLACE):
            engine.upsert_qso(result.qso)
        elif result.kind == PacketKind.DELETE:
            engine.mark_deleted(result.qso_id)
        return result

    def test_log_edit_delete_flow(self):
        from app.core.status import Status

        eng = self._engine()
        # 1. QSO gelogd (zonder /P — normalisatie moet matchen)
        self._apply(eng, contactinfo(call="ON4BAF"))
        assert eng.get_cell("ON4BAF", "80m").status == Status.WORKED_BY_N1MM

        # 2. Bewerking in N1MM: eerst contactdelete, dan contactreplace
        #    met gecorrigeerde callsign (§5.2, volgorde gegarandeerd verwerkt)
        self._apply(eng, CONTACTDELETE)
        self._apply(eng, contactinfo(tag="contactreplace", call="ON4CDZ/P"))
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED
        assert eng.get_cell("ON4CDZ", "80m").status == Status.WORKED_BY_N1MM

        # 3. Definitieve delete: cel gaat weer open
        self._apply(eng, CONTACTDELETE)
        assert eng.get_cell("ON4CDZ", "80m").status == Status.NOT_WORKED

    def test_lookupinfo_does_not_touch_matrix(self):
        from app.core.status import Status

        eng = self._engine()
        self._apply(eng, contactinfo(tag="lookupinfo"))
        assert eng.get_cell("ON4BAF", "80m").status == Status.NOT_WORKED
