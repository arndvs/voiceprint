import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.scripts.transcribe import (  # noqa: E402
    Transcriber,
    _clean_name,
    _format_ts,
    collect_media,
    media_ok,
)


def test_clean_name():
    assert _clean_name('a/b:c*d?e"f<g>h|i.txt') == "a_b_c_d_e_f_g_h_i.txt"
    assert _clean_name("normal.mp4") == "normal.mp4"


def test_format_ts():
    assert _format_ts(0) == "00:00:00"
    assert _format_ts(3661.4) == "01:01:01"
    assert _format_ts(3661.6) == "01:01:01"  # truncation, not rounding


def test_collect_media_single_file(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    assert collect_media(f) == [f]


def test_collect_media_recursive(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "one.mkv").write_bytes(b"x")
    (tmp_path / "two.mp3").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("nope")
    found = collect_media(tmp_path, recursive=True)
    assert sorted(p.name for p in found) == ["one.mkv", "two.mp3"]


def test_collect_media_non_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "one.mkv").write_bytes(b"x")
    (tmp_path / "two.mp3").write_bytes(b"x")
    found = collect_media(tmp_path, recursive=False)
    assert [p.name for p in found] == ["two.mp3"]


def test_segments_to_lines_plain_paragraph():
    t = Transcriber()
    segs = [{"start": 0.0, "end": 1.0, "text": " hello "}, {"start": 1.0, "end": 2.0, "text": "world"}]
    lines = t.segments_to_lines(segs, timestamps=False)
    assert lines == ["hello  world\n"]


def test_segments_to_lines_timestamps():
    t = Transcriber()
    segs = [{"start": 0.0, "end": 2.0, "text": "hi"}]
    lines = t.segments_to_lines(segs, timestamps=True)
    assert lines == ["[00:00:00-00:00:02] hi"]


def test_segments_to_lines_diarization():
    t = Transcriber(diarization=True)
    segs = [{"start": 0.0, "end": 2.0, "text": "hi", "speaker_tag": "Speaker A"}]
    lines = t.segments_to_lines(segs, timestamps=True)
    assert lines == ["[00:00:00-00:00:02] Speaker A: hi"]


def test_media_ok_returns_false_for_text_file(tmp_path):
    f = tmp_path / "notmedia.txt"
    f.write_text("hello")
    assert media_ok(f) is False