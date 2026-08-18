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


TEMPLATES_REGISTRY_PATH = REPO_ROOT / "templates.registry.json"


def load_templates_registry() -> dict:
    """Load templates.registry.json — the map of template_type → template dir + contract."""
    if not TEMPLATES_REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Templates registry missing: {TEMPLATES_REGISTRY_PATH}")
    with TEMPLATES_REGISTRY_PATH.open(encoding="utf-8") as f:
        registry = json.load(f)
    if not isinstance(registry, dict) or "types" not in registry:
        raise ValueError(f"Invalid templates registry: {TEMPLATES_REGISTRY_PATH}")
    return registry


def resolve_template_dir(template_type: str) -> Path:
    """Return the template directory for a template_type, validating it against the registry."""
    registry = load_templates_registry()
    types = registry.get("types", {})
    if template_type not in types:
        known = ", ".join(sorted(types)) or "(none)"
        raise ValueError(f"Unknown template_type: {template_type!r} — known: {known}")
    spec = types[template_type]
    template_dir = REPO_ROOT / registry.get("templates_dir", "templates") / spec["dir"]
    if not template_dir.is_dir():
        raise FileNotFoundError(f"Template dir for {template_type!r} missing: {template_dir}")
    return template_dir


def validate_config(config: dict) -> None:
    required = {
        "source_dir": "Where raw source material lives",
        "skills_dir": "Where generated skills go",
        "template_type": "Which template family to scaffold (comedian, author, personal)",
        "extraction.max_excerpts": "Max excerpts per voice",
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