import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.shared_utils import (  # noqa: E402
    REPO_ROOT,
    load_templates_registry,
    resolve_template_dir,
    validate_config,
)


def test_registry_lists_known_types():
    registry = load_templates_registry()
    assert set(registry["types"]) >= {"comedian", "author", "personal"}


def test_registry_entries_have_dir_and_suffix():
    registry = load_templates_registry()
    for name, spec in registry["types"].items():
        assert spec["dir"], f"{name} missing dir"
        assert spec["analysis_suffix"], f"{name} missing analysis_suffix"


def test_resolve_template_dir_returns_existing_dir():
    for template_type in ("comedian", "author", "personal"):
        resolved = resolve_template_dir(template_type)
        assert resolved.is_dir(), f"{template_type} template dir missing: {resolved}"
        assert (resolved / "SKILL.md").exists(), f"{template_type} missing SKILL.md"


def test_resolve_template_dir_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown template_type"):
        resolve_template_dir("politician")


def test_resolve_template_dir_missing_dir_raises(tmp_path, monkeypatch):
    registry = {"templates_dir": "templates", "types": {"ghost": {"dir": "ghost"}}}
    import json

    reg_path = tmp_path / "templates.registry.json"
    reg_path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr("scripts.shared_utils.TEMPLATES_REGISTRY_PATH", reg_path)
    monkeypatch.setattr("scripts.shared_utils.REPO_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="Template dir"):
        resolve_template_dir("ghost")


def test_config_requires_template_type():
    with pytest.raises(ValueError, match="template_type"):
        validate_config(
            {
                "source_dir": "./source",
                "skills_dir": "./skills",
                "extraction": {"max_excerpts": 40, "samples_per_source": 12},
            }
        )


def test_each_template_dir_is_a_valid_scaffold():
    """Scaffolding contract: every template dir needs SKILL.md and an analysis template."""
    registry = load_templates_registry()
    for template_type, spec in registry["types"].items():
        template_dir = resolve_template_dir(template_type)
        md_files = {p.name for p in template_dir.glob("*.md")}
        assert "SKILL.md" in md_files, f"{template_type} missing SKILL.md"
        assert any("style-analysis" in f for f in md_files), f"{template_type} missing analysis file"