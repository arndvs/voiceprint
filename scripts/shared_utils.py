import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

NOTE_MAX_LEN = 1200

REPO_ROOT = Path(__file__).resolve().parents[1]

SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


def resolve_path(p: str, base: Path = None) -> Path:
    base = base or REPO_ROOT
    expanded = Path(p).expanduser()
    if not expanded.is_absolute():
        expanded = base / expanded
    return expanded.resolve()


def load_config(config_path: str) -> dict:
    path = resolve_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict) -> None:
    required = {
        "source_dir": "Where raw source material lives",
        "skills_dir": "Where generated comedian skills go",
        "extraction.max_excerpts": "Max excerpts per comedian",
        "extraction.samples_per_source": "Samples per source file",
    }
    errors = []
    for key_path, hint in required.items():
        keys = key_path.split(".")
        obj = config
        for k in keys:
            if not isinstance(obj, dict) or k not in obj:
                errors.append(f"Missing config key: {key_path} — {hint}")
                break
            obj = obj[k]
        else:
            if obj in (None, ""):
                errors.append(f"Config key has empty value: {key_path} — {hint}")
    if errors:
        raise ValueError("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


def sanitize_slug(slug: str) -> str:
    import re

    slug = slug.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().isoformat()


def due_date(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")