"""Tests for app.storage.json_store (§4.7) — phase 4."""

import json

import pytest

from app.storage.json_store import read_json, write_json_atomic


class TestWriteReadRoundtrip:
    def test_dict_roundtrip(self, tmp_path):
        path = tmp_path / "data.json"
        payload = {"name": "UBA Velddag", "bands": ["160m", "80m", "40m"], "n": 38}
        write_json_atomic(path, payload)
        assert read_json(path) == payload

    def test_list_roundtrip(self, tmp_path):
        path = tmp_path / "list.json"
        payload = [{"a": 1}, {"b": 2}]
        write_json_atomic(path, payload)
        assert read_json(path) == payload

    def test_unicode_preserved(self, tmp_path):
        path = tmp_path / "unicode.json"
        payload = {"remarks": "portabel opstelling — café ✎"}
        write_json_atomic(path, payload)
        assert read_json(path) == payload

    def test_overwrite_existing(self, tmp_path):
        path = tmp_path / "data.json"
        write_json_atomic(path, {"v": 1})
        write_json_atomic(path, {"v": 2})
        assert read_json(path) == {"v": 2}

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "data.json"
        write_json_atomic(path, {"ok": True})
        assert read_json(path) == {"ok": True}


class TestAtomicity:
    def test_no_tmp_file_left_after_success(self, tmp_path):
        path = tmp_path / "data.json"
        write_json_atomic(path, {"v": 1})
        assert not (tmp_path / "data.json.tmp").exists()

    def test_unserializable_raises_and_keeps_original(self, tmp_path):
        path = tmp_path / "data.json"
        write_json_atomic(path, {"v": 1})
        with pytest.raises(ValueError, match="not JSON-serializable"):
            write_json_atomic(path, {"bad": object()})
        assert read_json(path) == {"v": 1}
        assert not (tmp_path / "data.json.tmp").exists()


class TestCorruptionRecovery:
    def test_missing_file_returns_none(self, tmp_path):
        assert read_json(tmp_path / "nope.json") is None
        # and no backup should appear out of nowhere
        assert list(tmp_path.iterdir()) == []

    def test_corrupt_file_backed_up_and_none(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("{ this is not json", encoding="utf-8")
        assert read_json(path) is None
        assert not path.exists()  # moved aside
        backups = list(tmp_path.glob("data.json.corrupt.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "{ this is not json"

    def test_write_after_corruption_recovers(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("garbage", encoding="utf-8")
        assert read_json(path) is None
        write_json_atomic(path, {"fresh": True})
        assert read_json(path) == {"fresh": True}

    def test_unexpected_root_type_treated_as_corrupt(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("42", encoding="utf-8")  # valid JSON, useless root
        assert read_json(path) is None
        assert list(tmp_path.glob("data.json.corrupt.*"))

    def test_binary_garbage(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_bytes(b"\x00\xff\xfe\x00garbage")
        assert read_json(path) is None
        assert list(tmp_path.glob("data.json.corrupt.*"))

    def test_empty_file_treated_as_corrupt(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("", encoding="utf-8")
        assert read_json(path) is None


class TestOutputFormat:
    def test_output_is_readable_json(self, tmp_path):
        # The files are also a manual-inspection/debug format: keep them
        # indented and with real unicode characters.
        path = tmp_path / "data.json"
        write_json_atomic(path, {"call": "ON4BAF/P", "opm": "café"})
        text = path.read_text(encoding="utf-8")
        assert "\n" in text          # indented
        assert "café" in text        # ensure_ascii=False
        json.loads(text)
