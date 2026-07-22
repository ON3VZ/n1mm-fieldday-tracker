"""Tests for fieldday_repository and app_settings storage — phase 4."""

from datetime import datetime, timezone

import pytest

from app.core.models import (
    QSO,
    AppSettings,
    FieldDay,
    Override,
    OverrideType,
    QsoSource,
    Station,
    StationSource,
)
from app.storage.app_settings import load_app_settings, save_app_settings
from app.storage.fieldday_repository import (
    FieldDayRepository,
    create_fieldday,
    list_fielddays,
    slugify,
    unique_slug,
)

UTC = timezone.utc


def make_fieldday(fd_id="uba-velddag-2026", name="UBA Velddag 2026") -> FieldDay:
    return FieldDay(
        id=fd_id,
        name=name,
        start_utc=datetime(2026, 6, 6, 13, 0, tzinfo=UTC),
        end_utc=datetime(2026, 6, 7, 13, 0, tzinfo=UTC),
    )


class TestSlugify:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("UBA Velddag 2026", "uba-velddag-2026"),
            ("  Velddag / Sectie WLD!  ", "velddag-sectie-wld"),
            ("Vélddàg été", "velddag-ete"),
            ("///", "fieldday"),
            ("", "fieldday"),
        ],
    )
    def test_slugify(self, name, expected):
        assert slugify(name) == expected

    def test_unique_slug_appends_counter(self, tmp_path):
        (tmp_path / "uba-velddag-2026").mkdir()
        assert unique_slug("UBA Velddag 2026", root_dir=tmp_path) == "uba-velddag-2026-2"
        (tmp_path / "uba-velddag-2026-2").mkdir()
        assert unique_slug("UBA Velddag 2026", root_dir=tmp_path) == "uba-velddag-2026-3"


class TestCreateAndLoad:
    def test_create_initializes_empty_structure(self, tmp_path):
        # BR-10: the matrix starts empty for every new field day.
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        assert repo.exists()
        assert repo.load_stations() == []
        assert repo.load_qsos() == []
        assert repo.load_overrides() == []
        assert repo.load_sync_log() == []
        assert repo.exports_dir.is_dir()

    def test_create_twice_rejected(self, tmp_path):
        create_fieldday(make_fieldday(), root_dir=tmp_path)
        with pytest.raises(ValueError, match="already exists"):
            create_fieldday(make_fieldday(), root_dir=tmp_path)

    def test_fieldday_roundtrip(self, tmp_path):
        fd = make_fieldday()
        repo = create_fieldday(fd, root_dir=tmp_path)
        loaded = repo.load_fieldday()
        assert loaded is not None
        assert loaded.id == fd.id
        assert loaded.name == fd.name
        assert loaded.start_utc == fd.start_utc

    def test_missing_fieldday_returns_none(self, tmp_path):
        repo = FieldDayRepository("nothing-here", root_dir=tmp_path)
        assert repo.load_fieldday() is None
        assert not repo.exists()


class TestStationsQsosOverrides:
    def test_stations_roundtrip(self, tmp_path):
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        stations = [
            Station(
                original_callsign="ON4BAF/P",
                normalized_callsign="ON4BAF",
                category="Open All Band Low Power",
                section="RST",
                source=StationSource.EXCEL,
            ),
            Station(original_callsign="ON4CDZ/P", normalized_callsign="ON4CDZ"),
        ]
        repo.save_stations(stations)
        loaded = repo.load_stations()
        assert [s.to_dict() for s in loaded] == [s.to_dict() for s in stations]

    def test_qsos_roundtrip(self, tmp_path):
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        qsos = [
            QSO(
                qso_id="abc123",
                original_callsign="ON4BAF/P",
                normalized_callsign="ON4BAF",
                band="80m",
                frequency_khz=3525.19,
                mode="CW",
                timestamp_utc=datetime(2026, 6, 6, 14, 0, tzinfo=UTC),
                source=QsoSource.N1MM_UDP,
            )
        ]
        repo.save_qsos(qsos)
        loaded = repo.load_qsos()
        assert [q.to_dict() for q in loaded] == [q.to_dict() for q in qsos]

    def test_overrides_roundtrip(self, tmp_path):
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        overrides = [
            Override(
                normalized_callsign="ON4BAF",
                band="40m",
                override_type=OverrideType.MANUAL_WORKED,
                reason="papieren log",
            )
        ]
        repo.save_overrides(overrides)
        loaded = repo.load_overrides()
        assert [o.to_dict() for o in loaded] == [o.to_dict() for o in overrides]

    def test_broken_entry_skipped_not_fatal(self, tmp_path):
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        st = Station(original_callsign="ON4BAF/P", normalized_callsign="ON4BAF")
        # Write one valid and one broken entry directly
        from app.storage.json_store import write_json_atomic

        write_json_atomic(
            repo.dir / "stations.json",
            [st.to_dict(), {"garbage": True}],
        )
        loaded = repo.load_stations()
        assert len(loaded) == 1
        assert loaded[0].normalized_callsign == "ON4BAF"


class TestSyncLog:
    def test_append_and_load(self, tmp_path):
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        repo.append_sync_log("adif_import", {"new": 12, "duplicates": 3})
        repo.append_sync_log("full_sync", {"cells_changed": 4})
        log = repo.load_sync_log()
        assert len(log) == 2
        assert log[0]["type"] == "adif_import"
        assert log[0]["details"] == {"new": 12, "duplicates": 3}
        assert log[0]["at_utc"].endswith("Z")

    def test_log_capped(self, tmp_path, monkeypatch):
        import app.storage.fieldday_repository as fr

        monkeypatch.setattr(fr, "MAX_SYNC_LOG_ENTRIES", 5)
        repo = create_fieldday(make_fieldday(), root_dir=tmp_path)
        for i in range(8):
            repo.append_sync_log("event", {"i": i})
        log = repo.load_sync_log()
        assert len(log) == 5
        assert log[-1]["details"] == {"i": 7}


class TestListFielddays:
    def test_lists_created_fielddays(self, tmp_path):
        create_fieldday(make_fieldday("fd-a", "Velddag A"), root_dir=tmp_path)
        create_fieldday(make_fieldday("fd-b", "Velddag B"), root_dir=tmp_path)
        names = {fd.name for fd in list_fielddays(root_dir=tmp_path)}
        assert names == {"Velddag A", "Velddag B"}

    def test_empty_root(self, tmp_path):
        assert list_fielddays(root_dir=tmp_path / "does-not-exist") == []

    def test_broken_fieldday_skipped(self, tmp_path):
        create_fieldday(make_fieldday("fd-ok", "OK"), root_dir=tmp_path)
        broken = tmp_path / "fd-broken"
        broken.mkdir()
        (broken / "fieldday.json").write_text("not json", encoding="utf-8")
        result = list_fielddays(root_dir=tmp_path)
        assert [fd.name for fd in result] == ["OK"]


class TestAppSettingsStorage:
    def test_missing_file_gives_defaults(self, tmp_path):
        settings = load_app_settings(path=tmp_path / "app_settings.json")
        assert settings.ui_language == "en"
        assert settings.n1mm_udp_port == 12060

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "app_settings.json"
        settings = AppSettings(ui_language="nl", last_active_field_day="uba-2026")
        save_app_settings(settings, path=path)
        loaded = load_app_settings(path=path)
        assert loaded.to_dict() == settings.to_dict()

    def test_corrupt_file_gives_defaults_and_backup(self, tmp_path):
        path = tmp_path / "app_settings.json"
        path.write_text("{{{", encoding="utf-8")
        settings = load_app_settings(path=path)
        assert settings.ui_language == "en"
        assert list(tmp_path.glob("app_settings.json.corrupt.*"))

    def test_semantically_invalid_gives_defaults(self, tmp_path):
        path = tmp_path / "app_settings.json"
        path.write_text('{"ui_language": "klingon"}', encoding="utf-8")
        settings = load_app_settings(path=path)
        assert settings.ui_language == "en"
