#!/usr/bin/env python3
"""Transcribe audio/video files to timestamped text transcripts.

Standalone Whisper-based transcriber for the comedian-voices pipeline.
Config is passed via CLI flags or environment variables — no secrets or
machine-specific paths are hardcoded in this file.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import List, Optional

MEDIA_EXTS = {
    # video
    ".3g2", ".3gp", ".avi", ".f4v", ".flv", ".m2ts", ".m2v", ".m4v",
    ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".mxf", ".mts", ".ogv",
    ".webm", ".ts", ".vob", ".wmv",
    # audio
    ".aac", ".ac3", ".aif", ".aiff", ".alac", ".amr", ".au", ".dts",
    ".eac3", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav",
    ".wma",
}

_INVALID_CHARS = r'\/:*?"<>|'


def _clean_name(name: str) -> str:
    """Replace filesystem-hostile characters with underscores."""
    return "".join("_" if c in _INVALID_CHARS else c for c in name)


def _format_ts(seconds: float) -> str:
    """Format seconds as zero-padded hh:mm:ss."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def collect_media(target: Path, recursive: bool = True) -> List[Path]:
    """Return media files under `target` (or the single file itself)."""
    if target.is_file():
        return [target]
    pattern = "**/*" if recursive else "*"
    return [p for p in target.glob(pattern) if p.suffix.lower() in MEDIA_EXTS]


def media_ok(file_path: Path) -> bool:
    """True if ffprobe can read the file's first audio stream."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1",
        str(file_path),
    ]
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


class Transcriber:
    """Lazy-loaded Whisper + optional pyannote diarization."""

    def __init__(self, model: str = "turbo", diarization: bool = False,
                 diarization_model: str = "pyannote/speaker-diarization-3.1",
                 hf_token: str = "", fallback_without_diarization: bool = True):
        self.model = model
        self.diarization = diarization
        self.diarization_model = diarization_model
        self.hf_token = hf_token
        self.fallback_without_diarization = fallback_without_diarization

        self._whisper = None
        self._whisper_model = None
        self._diar_pipeline = None
        self._torch = None
        self._device_str: Optional[str] = None

    # -- device -----------------------------------------------------------
    def _get_device_str(self) -> str:
        if self._device_str is None:
            if self._torch is None:
                import torch
                self._torch = torch
            self._device_str = "cuda" if self._torch.cuda.is_available() else "cpu"
        return self._device_str

    def _get_device(self):
        self._get_device_str()
        return getattr(self._torch, "device", lambda d: d)(self._device_str)

    # -- model loading -----------------------------------------------------
    def _load_whisper_model(self):
        if self._whisper_model is None:
            if self._whisper is None:
                import whisper
                self._whisper = whisper
            device = self._get_device_str()
            print(f"[INFO] Loading Whisper model › {self.model} on {device}")
            self._whisper_model = self._whisper.load_model(self.model, device=device)
        return self._whisper_model

    def _load_diarization_pipeline(self):
        if self._diar_pipeline is None and self.diarization:
            from pyannote.audio import Pipeline  # type: ignore
            from pyannote.audio.utils.reproducibility import ReproducibilityWarning  # type: ignore

            warnings.filterwarnings("ignore", category=ReproducibilityWarning)
            warnings.filterwarnings(
                "ignore",
                message=r"std\(\).*degrees of freedom",
                category=UserWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message=r".*MPEG_LAYER_III subtype is unknown.*",
                category=UserWarning,
            )

            if self._get_device_str() == "cpu":
                print("[WARN] No GPU detected – pyannote will run on CPU and be slow.")
            if not self.hf_token:
                raise RuntimeError(
                    "Diarization requires an HF token. Set HF_TOKEN (see INSTALL.md)."
                )

            print(f"[INFO] Loading pyannote model › {self.diarization_model}")
            self._diar_pipeline = Pipeline.from_pretrained(
                self.diarization_model, use_auth_token=self.hf_token or None
            )
            self._diar_pipeline.to(self._get_device())
        return self._diar_pipeline

    # -- transcription ------------------------------------------------------
    def transcribe(self, file_path: Path) -> List[dict]:
        model = self._load_whisper_model()
        result = model.transcribe(str(file_path), word_timestamps=False, verbose=False)
        return result["segments"]

    def _ensure_wav(self, src: Path) -> Path:
        """Convert non-WAV input to mono 16kHz WAV (pyannote requirement)."""
        if src.suffix.lower() == ".wav":
            return src
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        tmp_wav = Path(tmp_path)
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-i", str(src), "-ac", "1", "-ar", "16000", str(tmp_wav),
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"[ERROR] ffmpeg failed: {exc}")
            tmp_wav.unlink(missing_ok=True)
            raise
        return tmp_wav

    def _run_diarization(self, file_path: Path):
        """Return pyannote annotation, or None on any failure."""
        if not self.diarization:
            return None
        pipeline = self._load_diarization_pipeline()
        if pipeline is None:
            return None

        wav_path = self._ensure_wav(file_path)
        try:
            print("  ↳ running speaker diarization...")
            return pipeline(str(wav_path))
        except KeyboardInterrupt:
            print(f"[WARN] Diarization interrupted for {file_path.name} – continuing without speaker labels")
            return None
        except Exception as exc:
            print(f"[WARN] Diarization failed for {file_path.name}: {exc} – continuing without speaker labels")
            return None
        finally:
            if wav_path != file_path and wav_path.exists():
                wav_path.unlink()

    def _merge_segments(self, segments: List[dict], diar_annotation) -> List[dict]:
        """Attach speaker tags via midpoint voting against diarization turns."""
        if diar_annotation is None:
            return segments

        unique_labels = sorted({lab for _, _, lab in diar_annotation.itertracks(yield_label=True)})
        label_map = {lab: f"Speaker {chr(65 + i)}" for i, lab in enumerate(unique_labels)}
        turns = [
            {"start": turn.start, "end": turn.end, "label": label_map[lab]}
            for turn, _, lab in diar_annotation.itertracks(yield_label=True)
        ]

        def speaker_for(mid: float) -> str:
            for t in turns:
                if t["start"] <= mid <= t["end"]:
                    return t["label"]
            return "Speaker ?"

        for seg in segments:
            mid = (seg["start"] + seg["end"]) / 2.0
            seg["speaker_tag"] = speaker_for(mid)
        return segments

    def segments_to_lines(self, segments: List[dict], timestamps: bool = True) -> List[str]:
        """Format segments as lines; if no timestamps+no diarization, one paragraph."""
        if not timestamps and not self.diarization:
            paragraph = "  ".join(seg["text"].strip() for seg in segments)
            return [paragraph + "\n"]

        lines = []
        for seg in segments:
            ts = f"[{_format_ts(seg['start'])}-{_format_ts(seg['end'])}] " if timestamps else ""
            spk = f"{seg.get('speaker_tag', '')}: " if self.diarization else ""
            lines.append(f"{ts}{spk}{seg['text'].strip()}")
        return lines

    def process_file(self, file_path: Path, output_dir: Path,
                     timestamps: bool = True, overwrite: bool = True) -> bool:
        """Transcribe one file to output_dir/<stem>.txt. Returns success."""
        if not media_ok(file_path):
            print(f"[ERROR] Skipping (unreadable): {file_path.name}")
            return False

        print(f"[INFO] → Processing {file_path.name}")
        try:
            segments = self.transcribe(file_path)
            diar = None
            if self.diarization:
                try:
                    diar = self._run_diarization(file_path)
                except Exception as exc:
                    if self.fallback_without_diarization:
                        print(f"[WARN] Diarization failed for {file_path.name}: {exc}")
                        print("[INFO] Continuing with transcription only...")
                    else:
                        raise
            segments = self._merge_segments(segments, diar)
            lines = self.segments_to_lines(segments, timestamps=timestamps)
        except Exception as exc:
            print(f"[ERROR] Failed on {file_path.name} → {exc}")
            return False

        out_path = output_dir / f"{_clean_name(file_path.stem)}.txt"
        if not overwrite:
            counter = 2
            while out_path.exists():
                out_path = output_dir / f"{_clean_name(file_path.stem)} ({counter}).txt"
                counter += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  ↳ saved → {out_path.resolve()}")
        return True

    def transcribe_dir(self, target: Path, output_dir: Path, recursive: bool = True,
                       timestamps: bool = True, overwrite: bool = True) -> List[Path]:
        """Transcribe every media file under `target`. Returns successful outputs."""
        files = collect_media(target, recursive=recursive)
        if not files:
            print("[ERROR] No media files found – check target path or extensions.")
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        done: List[Path] = []
        for idx, fp in enumerate(files, 1):
            print(f"[PROGRESS] {idx}/{len(files)}")
            if self.process_file(fp, output_dir, timestamps=timestamps, overwrite=overwrite):
                done.append(fp)
        print(f"[DONE] {len(done)}/{len(files)} transcribed → {output_dir.resolve()}")
        return done


def _purge_temp_wavs(max_age_h: float = 6.0) -> None:
    """Clean stale scratch WAVs older than max_age_h from the OS temp dir."""
    cutoff = time.time() - max_age_h * 3600
    tmp_dir = Path(tempfile.gettempdir())
    for p in tmp_dir.glob("tmp*.wav"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video files to text using Whisper."
    )
    parser.add_argument("target", nargs="?", type=Path, default=None,
                        help="Media file or folder to transcribe (default: ./input)")
    parser.add_argument("-o", "--output-dir", type=Path, default=None,
                        help="Where to write transcripts (default: ./output)")
    parser.add_argument("--recursive", action="store_true", default=True,
                        help="Recurse into subfolders (default: True)")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.add_argument("--no-timestamps", dest="timestamps", action="store_false", default=True)
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false", default=True)
    parser.add_argument("--model", default=os.environ.get("TRANSCRIBE_MODEL", "turbo"),
                        help="Whisper model size (default: turbo)")
    parser.add_argument("--diarize", action="store_true",
                        help="Enable pyannote speaker diarization (requires HF_TOKEN)")
    parser.add_argument("--diarization-model",
                        default="pyannote/speaker-diarization-3.1",
                        help="pyannote pipeline (default: speaker-diarization-3.1)")
    parser.add_argument("--no-fallback", dest="fallback", action="store_false", default=True,
                        help="Fail hard if diarization errors instead of continuing")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be transcribed without running the model")
    args = parser.parse_args()

    _purge_temp_wavs()

    target = args.target or Path("./input")
    output_dir = args.output_dir or Path("./output")

    if args.dry_run:
        files = collect_media(target, recursive=args.recursive)
        print(f"[DRY-RUN] {len(files)} media file(s):")
        for f in files:
            print(f"  - {f}")
        return 0 if files else 1

    transcriber = Transcriber(
        model=args.model,
        diarization=args.diarize,
        diarization_model=args.diarization_model,
        hf_token=os.environ.get("HF_TOKEN", ""),
        fallback_without_diarization=args.fallback,
    )
    transcriber.transcribe_dir(
        target, output_dir,
        recursive=args.recursive,
        timestamps=args.timestamps,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())