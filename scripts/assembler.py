import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")


def render_template(text: str, slug: str, name: str) -> str:
    return (
        text.replace("{{comedian-slug}}", slug)
        .replace("{{slug}}", slug)
        .replace("{{Comedian Name}}", name)
        .replace("{{comedian-name}}", slug)
    )


def find_remaining_placeholders(text: str) -> list[str]:
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def assemble_folder(target: Path, slug: str, name: str = None) -> dict:
    name = name or slug.replace("-", " ").title()
    replaced_files = 0
    remaining = {}
    for f in target.rglob("*.md"):
        original = f.read_text(encoding="utf-8")
        rendered = render_template(original, slug, name)
        leftovers = find_remaining_placeholders(rendered)
        if leftovers:
            remaining[str(f.relative_to(target))] = leftovers
        if rendered != original:
            f.write_text(rendered, encoding="utf-8")
            replaced_files += 1
    analysis_template = target / "comedian-slug-style-analysis.md"
    if analysis_template.exists():
        analysis_target = target / f"{slug}-style-analysis.md"
        analysis_template.rename(analysis_target)
        if str(analysis_target.name) in remaining:
            remaining[str(analysis_target.name)] = remaining.pop(str(analysis_template.name))
    return {"replaced_files": replaced_files, "remaining_placeholders": remaining}


def verify_output(target: Path) -> list[str]:
    issues = []
    skill_md = target / "SKILL.md"
    if not skill_md.exists():
        issues.append("SKILL.md missing after assembly")
    analysis_files = list(target.glob("*-style-analysis.md"))
    if not analysis_files:
        issues.append("style-analysis.md missing after assembly")
    for f in target.rglob("*.md"):
        leftovers = find_remaining_placeholders(f.read_text(encoding="utf-8"))
        if leftovers:
            issues.append(f"{f.name}: unfilled placeholders {leftovers}")
    return issues