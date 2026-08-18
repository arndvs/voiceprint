import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.assembler import assemble_folder, find_remaining_placeholders, render_template  # noqa: E402


def test_render_template_fills_mechanical_tokens():
    text = "{{slug}} and {{name}} and {{comedian-slug}} and {{Comedian Name}}"
    rendered = render_template(text, "jerry-seinfeld", "Jerry Seinfeld")
    assert rendered == "jerry-seinfeld and Jerry Seinfeld and jerry-seinfeld and Jerry Seinfeld"


def test_render_template_defaults_name_from_slug():
    assert render_template("{{name}}", "louis-ck", None) == "Louis Ck"


def test_find_remaining_placeholders_sorted_unique():
    assert find_remaining_placeholders("{{b}} {{a}} {{b}}") == ["{{a}}", "{{b}}"]
    assert find_remaining_placeholders("no tokens") == []


def test_assemble_renames_generic_analysis_file(tmp_path):
    """Any <x>-style-analysis.md must rename to <slug>-style-analysis.md (S3 generic templates)."""
    target = tmp_path / "out"
    target.mkdir()
    (target / "SKILL.md").write_text("Style of {{name}}\n", encoding="utf-8")
    (target / "author-style-analysis.md").write_text(
        "# {{name}} analysis\n— written by the agent\nslug: {{slug}}\n", encoding="utf-8"
    )

    stats = assemble_folder(target, "hemingway", "Ernest Hemingway")

    renamed = target / "hemingway-style-analysis.md"
    assert renamed.exists()
    assert not (target / "author-style-analysis.md").exists()
    text = renamed.read_text(encoding="utf-8")
    assert "Ernest Hemingway analysis" in text
    assert "slug: hemingway" in text


def test_assemble_rename_preserves_unfilled_placeholder_tracking():
    """Content gaps (agent-fill {{{{...}}}}) survive the rename and stay tracked under the new name."""
    target = Path(__file__).resolve().parents[1] / "templates" / "personal"
    out = Path(__file__).resolve().parents[1] / ".run" / "asm-test"
    import shutil

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(target, out)

    stats = assemble_folder(out, "aaron", "Aaron")
    renamed = out / "aaron-style-analysis.md"
    assert renamed.exists(), "personal template must rename to slug file"

    rel = str(renamed.relative_to(out))
    assert rel in stats["remaining_placeholders"], f"rename must re-key tracking: {stats['remaining_placeholders']}"
    assert "{{The Sign}}" in stats["remaining_placeholders"][rel]
    assert "{{The Sign}}" in renamed.read_text(encoding="utf-8")

    import shutil as sh

    sh.rmtree(Path(__file__).resolve().parents[1] / ".run" / "asm-test")