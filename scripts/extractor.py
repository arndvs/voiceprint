import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.shared_utils import NOTE_MAX_LEN, ensure_dir, resolve_path

FULL_WORK_THRESHOLD_CHARS = 120_000
PAGE_MARKER_NOISE = 0.2

TEXT_EXT = {".txt", ".md", ".markdown", ".json", ".html", ".htm", ".srt", ".vtt", ".pdf", ".epub"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SKIP_EXT = {".DS_Store", ".gitkeep"}

FRONT_MATTER_RE = re.compile(r"(copyright|all rights reserved|isbn|first .* edition)", re.IGNORECASE)

TS_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})-(\d{2}):(\d{2}):(\d{2})\]\s*(?:Speaker ([A-Z?]))?:\s*(.*)$")


def _ts_to_seconds(h: int, m: int, s: int) -> int:
    return h * 3600 + m * 60 + s


@dataclass
class TranscriptSegment:
    text: str
    start_ts: str = ""
    end_ts: str = ""
    start_sec: float = 0.0
    end_sec: float = 0.0
    speaker: str = ""


@dataclass
class ExtractionResult:
    sources: list = field(default_factory=list)
    excerpts: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    usable: bool = False


class Extractor:
    def __init__(self, config: dict):
        self.max_excerpts = int(config["extraction"]["max_excerpts"])
        self.min_chars = int(config["extraction"]["excerpt_min_chars"])
        self.max_chars = int(config["extraction"]["excerpt_max_chars"])
        self.samples_per_source = int(config["extraction"]["samples_per_source"])
        self.context_lines = int(config["extraction"]["context_lines"])

    def _read_text(self, path: Path) -> str:
        if path.suffix.lower() in AUDIO_EXT | VIDEO_EXT:
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except (UnicodeDecodeError, OSError):
            try:
                return path.read_text(encoding="latin-1", errors="replace")
            except OSError:
                return ""

    def _detect_full_work(self, text: str, path: Path) -> str:
        if path.suffix.lower() in AUDIO_EXT | VIDEO_EXT:
            return "media file — transcribe to text first; the pipeline only reads text"
        head = text[:4000]
        if FRONT_MATTER_RE.search(head):
            return "front matter looks like a published book (copyright/ISBN block)"
        if len(text) > FULL_WORK_THRESHOLD_CHARS:
            return f"raw text is a full-length work ({len(text) / 1000:.0f}k chars)"
        marker_lines = sum(1 for line in text.splitlines() if re.fullmatch(r"[\s\-_*#=~.]+", line.strip()))
        if len(text.splitlines()) and marker_lines / len(text.splitlines()) > PAGE_MARKER_NOISE:
            return "high page-marker noise — looks like a scanned book, not analysis-ready excerpts"
        return ""

    def _pick_samples(self, text: str, count: int) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return []
        if len(lines) <= count:
            return lines
        step = max(1, len(lines) // count)
        return [lines[i] for i in range(0, len(lines), step)][:count]

    @staticmethod
    def parse_transcript(text: str) -> list[TranscriptSegment]:
        """Split timestamped transcript lines into structured segments."""
        segments = []
        for raw in text.splitlines():
            line = raw.strip()
            m = TS_RE.match(line)
            if not m:
                continue
            h1, m1, s1, h2, m2, s2, speaker, body = m.groups()
            body = body.strip()
            if not body:
                continue
            start_sec = _ts_to_seconds(int(h1), int(m1), int(s1))
            end_sec = _ts_to_seconds(int(h2), int(m2), int(s2))
            segments.append(TranscriptSegment(
                text=body,
                start_ts=f"{h1}:{m1}:{s1}",
                end_ts=f"{h2}:{m2}:{s2}",
                start_sec=float(start_sec),
                end_sec=float(end_sec),
                speaker=(speaker or ""),
            ))
        return segments

    def _is_transcript(self, text: str) -> bool:
        """Heuristic: at least 5 lines match the timestamp pattern."""
        hits = sum(1 for line in text.splitlines() if TS_RE.match(line.strip()))
        return hits >= 5

    def _candidate_lines(self, text: str) -> list[tuple[int, str]]:
        candidates = []
        for i, line in enumerate(text.splitlines()):
            stripped = line.strip()
            if len(stripped) < self.min_chars // 2:
                continue
            if len(stripped) > self.max_chars:
                continue
            if re.fullmatch(r"[\s\-_*#=~.]+", stripped):
                continue
            if re.fullmatch(r"\d{1,4}", stripped):
                continue
            if FRONT_MATTER_RE.search(stripped):
                continue
            if len(stripped.split()) > 90:
                continue
            candidates.append((i, stripped))
        return candidates

    def _extract_excerpts(self, text: str) -> list[dict]:
        # Timestamped transcripts: operate on structured segments (free segment boundaries)
        segments = self.parse_transcript(text)
        if segments:
            step = max(1, len(segments) // self.max_excerpts)
            chosen = []
            for i in range(0, len(segments), step):
                grp = segments[i : i + 3]
                block = " ".join(s.text for s in grp)
                if len(block) < self.min_chars:
                    continue
                chosen.append({
                    "excerpt": block[: self.max_chars],
                    "start_ts": grp[0].start_ts,
                    "end_ts": grp[-1].end_ts,
                    "start_sec": grp[0].start_sec,
                    "end_sec": grp[-1].end_sec,
                    "speaker": grp[0].speaker or "",
                    "char_count": len(block),
                    "segment_count": len(grp),
                })
                if len(chosen) >= self.max_excerpts:
                    break
            return chosen

        # Plain text: line-window extraction as before
        lines = text.splitlines()
        candidates = self._candidate_lines(text)
        if not candidates:
            return []
        step = max(1, len(candidates) // self.max_excerpts)
        chosen = []
        seen_ranges = set()
        for start_idx, _ in candidates[::step]:
            start = max(0, start_idx - self.context_lines)
            end = min(len(lines), start_idx + self.context_lines + 1)
            if (start, end) in seen_ranges:
                continue
            seen_ranges.add((start, end))
            block = "\n".join(lines[start:end]).strip()
            chosen.append({
                "excerpt": block[: self.max_chars],
                "line_start": start + 1,
                "line_end": end,
                "char_count": len(block),
            })
            if len(chosen) >= self.max_excerpts:
                break
        return chosen

    def process(self, source_dir: Path) -> ExtractionResult:
        result = ExtractionResult()
        for path in sorted(source_dir.iterdir()):
            if path.is_dir() or path.suffix.lower() in SKIP_EXT:
                continue
            text = self._read_text(path)
            flag = self._detect_full_work(text, path) if text else "unreadable file"
            src = {
                "file": path.name,
                "size_bytes": path.stat().st_size,
                "line_count": len(text.splitlines()) if text else 0,
                "samples": self._pick_samples(text, self.samples_per_source) if text and not flag else [],
                "flag": flag,
            }
            result.sources.append(src)
            if flag:
                result.flags.append({"file": path.name, "reason": flag})
            elif text:
                for e in self._extract_excerpts(text):
                    e["source"] = path.name
                    result.excerpts.append(e)
        result.usable = bool(result.excerpts) and not result.flags
        return result