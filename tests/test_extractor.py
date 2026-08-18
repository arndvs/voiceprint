import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.scripts.extractor import Extractor, TranscriptSegment, TS_RE  # noqa: E402

CONFIG = {
    "extraction": {
        "max_excerpts": 40,
        "excerpt_min_chars": 40,
        "excerpt_max_chars": 400,
        "samples_per_source": 12,
        "context_lines": 3,
    }
}

SAMPLE_TRANSCRIPT = """\
[00:00:00-00:00:02] Speaker A: Welcome back.
[00:00:02-00:00:04] Speaker A: Tonight we talk about the thing.
[00:00:04-00:00:07] Speaker B: The thing nobody wants to mention.
[00:00:07-00:00:10] Speaker A: Exactly. And that is the problem.
[00:00:10-00:00:13] Speaker A: Nobody ever says it out loud.
[00:00:13-00:00:16] Speaker B: Until now.
[00:00:16-00:00:19] Speaker A: Until now. That is the whole bit.
"""


def test_ts_re_matches_timestamp_line():
    m = TS_RE.match("[00:00:02-00:00:04] Speaker A: Tonight we talk about the thing.")
    assert m is not None
    h1, m1, s1, h2, m2, s2, speaker, body = m.groups()
    assert (h1, m1, s1) == ("00", "00", "02")
    assert (h2, m2, s2) == ("00", "00", "04")
    assert speaker == "A"
    assert body == "Tonight we talk about the thing."


def test_parse_transcript_returns_segments():
    segs = Extractor(CONFIG).parse_transcript(SAMPLE_TRANSCRIPT)
    assert len(segs) == 7
    assert segs[0].start_sec == 0.0
    assert segs[0].end_sec == 2.0
    assert segs[0].speaker == "A"
    assert segs[2].speaker == "B"
    assert segs[2].text == "The thing nobody wants to mention."


def test_parse_transcript_ignores_non_timestamp_lines():
    text = "Some prose paragraph.\n\n[00:00:00-00:00:01] Speaker A: Hi there.\n"
    segs = Extractor(CONFIG).parse_transcript(text)
    assert len(segs) == 1
    assert segs[0].text == "Hi there."


def test_extract_excerpts_from_transcript_carries_ts():
    excerpts = Extractor(CONFIG)._extract_excerpts(SAMPLE_TRANSCRIPT)
    assert excerpts
    first = excerpts[0]
    assert "start_ts" in first and "end_ts" in first
    assert first["start_sec"] < first["end_sec"]
    assert first["speaker"] == "A"
    assert first["segment_count"] >= 1


def test_extract_excerpts_plain_text_still_works():
    text = "\n".join(f"This is ordinary line number {i} with enough words to count." for i in range(30))
    excerpts = Extractor(CONFIG)._extract_excerpts(text)
    assert excerpts
    # plain-text excerpts do NOT carry ts metadata
    assert "start_ts" not in excerpts[0]
