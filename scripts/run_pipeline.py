import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from scripts.assembler import assemble_folder, verify_output
from scripts.extractor import Extractor
from scripts.session_logger import SessionLogger
from scripts.shared_utils import (
    REPO_ROOT,
    ensure_dir,
    load_config,
    validate_config,
    sanitize_slug,
)
from scripts.state_store import JsonStateStore
from scripts.transcribe import Transcriber, collect_media

PHASES = ["scaffold", "ingest", "transcribe", "extract", "analyze", "assemble", "verify"]


class Pipeline:
    def __init__(self, config: dict, state: JsonStateStore, logger: SessionLogger):
        self.config = config
        self.state = state
        self.logger = logger
        self.source_root = REPO_ROOT / config.get("source_dir", "./source")
        self.skills_root = REPO_ROOT / config.get("skills_dir", "./skills")
        self.template_dir = self.skills_root / "_template"
        self.run_dir = Path(config.get("run_dir", "./.run"))

    def _resolve_item(self, slug: str) -> dict:
        slug = sanitize_slug(slug)
        item = self.state.get_item(slug)
        if not item:
            item = {"id": slug, "status": "queued", "notes": "", "created": datetime.now().isoformat()}
        return item

    def phase_scaffold(self, item: dict) -> dict:
        slug = item["id"]
        target = self.skills_root / slug
        if not self.template_dir.exists():
            return {"skip": True, "error": f"Template dir missing: {self.template_dir}"}
        if not target.exists():
            shutil.copytree(self.template_dir, target)
        item["output_dir"] = str(target)
        item["status"] = "scaffolded"
        return {"skip": False, "target": str(target)}

    def phase_ingest(self, item: dict) -> dict:
        source_dir = self.source_root / item["id"]
        if not source_dir.exists():
            return {"skip": True, "error": f"No source dir: {source_dir}"}
        raw_dir = source_dir / "raw"
        transcripts_dir = source_dir / "transcripts"

        # Where to look for readable text: transcripts/ first, then top-level files
        text_dir = transcripts_dir if transcripts_dir.exists() else source_dir
        files = sorted(p for p in text_dir.iterdir() if p.is_file())
        sources = [{"file": p.name, "size_bytes": p.stat().st_size} for p in files]
        item["source_dir"] = str(source_dir)
        item["text_dir"] = str(text_dir)
        item["sources"] = sources
        item["has_raw_media"] = raw_dir.exists() and any(
            p.is_file() for p in raw_dir.iterdir()
        )
        return {"skip": False, "file_count": len(sources)}

    def phase_transcribe(self, item: dict) -> dict:
        """Transcribe media in source/<slug>/raw/ into source/<slug>/transcripts/."""
        source_dir = Path(item["source_dir"])
        raw_dir = source_dir / "raw"
        transcripts_dir = source_dir / "transcripts"

        if not raw_dir.exists():
            item["transcripts"] = []
            return {"skip": True, "note": "no raw/ media dir — skipping transcription"}

        media = collect_media(raw_dir)
        if not media:
            item["transcripts"] = []
            return {"skip": True, "note": "no media files in raw/"}

        existing = {p.stem for p in transcripts_dir.glob("*.txt")} if transcripts_dir.exists() else set()
        pending = [m for m in media if m.stem not in existing]
        item["transcripts_dir"] = str(transcripts_dir)
        item["transcripts"] = sorted(
            p.name for p in transcripts_dir.glob("*.txt")
        ) if transcripts_dir.exists() else []
        if not pending:
            return {"skip": False, "note": "all media already transcribed", "transcribed": 0}

        import os

        transcriber = Transcriber(
            model=self.config.get("transcription", {}).get("model", "turbo"),
            diarization=self.config.get("transcription", {}).get("diarization", False),
            hf_token=os.environ.get("HF_TOKEN", ""),
        )
        done = transcriber.transcribe_dir(
            raw_dir, transcripts_dir,
            recursive=True, timestamps=True, overwrite=False,
        )
        item["transcripts_dir"] = str(transcripts_dir)
        item["transcripts"] = sorted(p.name for p in transcripts_dir.glob("*.txt"))
        return {"skip": False, "transcribed": len(done), "total_media": len(media)}

    def phase_extract(self, item: dict) -> dict:
        text_dir = Path(item["text_dir"])
        extractor = Extractor(self.config)
        result = extractor.process(text_dir)
        item["extraction"] = {
            "usable": result.usable,
            "source_count": len(result.sources),
            "excerpt_count": len(result.excerpts),
            "flags": result.flags,
            "excerpts": result.excerpts[: self.config["extraction"]["max_excerpts"]],
            "sources": result.sources,
        }
        if result.flags:
            item["status"] = "failed"
            item["notes"] = item.get("notes", "") + " | flags: " + json.dumps(result.flags)
            return {"skip": True, "error": f"Copyright/full-work flags: {result.flags}"}
        item["status"] = "extracted"
        return {"skip": False, "excerpt_count": len(result.excerpts)}

    def phase_analyze(self, item: dict) -> dict:
        item["status"] = "analyzed"
        return {"skip": False}

    def _render(self, text: str, slug: str, name: str) -> str:
        return (
            text.replace("{{comedian-slug}}", slug)
            .replace("{{slug}}", slug)
            .replace("{{Comedian Name}}", name)
            .replace("{{comedian-name}}", slug)
        )

    def phase_assemble(self, item: dict) -> dict:
        slug = item["id"]
        name = item.get("name", slug.replace("-", " ").title())
        target = Path(item["output_dir"])
        stats = assemble_folder(target, slug, name)
        issues = verify_output(target)
        if issues:
            print(f"  [warn] output issues: {issues}")
        if stats["remaining_placeholders"]:
            item["status"] = "failed"
            return {"skip": True, "error": f"Unfilled placeholders: {stats['remaining_placeholders']}"}
        item["status"] = "assembled"
        return {"skip": False, "target": str(target), "stats": stats}

    def run_item(self, slug: str, only: str = None) -> bool:
        item = self._resolve_item(slug)
        phases = [only] if only else PHASES[: PHASES.index("analyze") + 1]
        ok = True
        for phase in phases:
            method = getattr(self, f"phase_{phase}", None)
            if not method:
                print(f"  unknown phase: {phase}")
                ok = False
                continue
            print(f"[{phase}] {slug}")
            try:
                result = method(item)
            except Exception as exc:
                self.logger.log_error(slug, exc, phase)
                item["status"] = "failed"
                self.state.upsert_item(item)
                ok = False
                print(f"  error: {exc}")
                break
            log_event = getattr(self.logger, "log_event", None)
            if log_event:
                log_event(slug, phase, result)
            if result.get("skip"):
                if result.get("error"):
                    # Hard skip — a real problem. Stop and persist failure.
                    item["status"] = "failed"
                    self.state.upsert_item(item)
                    ok = False
                    print(f"  skip: {result['error']}")
                    break
                # Soft skip — nothing to do (e.g. no raw/ media). Continue to next phase.
                print(f"  skip: {result.get('note', '')}")
                continue
        self.state.upsert_item(item)
        self.state.write_summary()
        return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Comedian voice generation pipeline")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--item", help="Comedian slug (source dir name)")
    parser.add_argument("--only", choices=PHASES, help="Run only this phase")
    args = parser.parse_args()

    config = load_config(args.config)
    validate_config(config)

    run_dir = Path(config.get("run_dir", "./pipeline"))
    ensure_dir(run_dir / "logs")
    state = JsonStateStore(str((run_dir / "state.json").resolve()))

    with SessionLogger(str((run_dir / "logs").resolve())) as logger:
        pipe = Pipeline(config, state, logger)
        if args.item:
            ok = pipe.run_item(args.item, only=args.only)
        else:
            ok = all(pipe.run_item(i["id"]) for i in state.get_pending_items())

if __name__ == "__main__":
    sys.exit(main())