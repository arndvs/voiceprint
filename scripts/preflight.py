import argparse
import sys
from pathlib import Path

from pipeline.scripts.shared_utils import (
    REPO_ROOT,
    ensure_dir,
    load_config,
    resolve_path,
    sanitize_slug,
    validate_config,
)


def run_preflight(config_path: str) -> bool:
    print("=" * 60)
    print("Pre-flight Validation")
    print("=" * 60)

    errors = []

    try:
        config = load_config(config_path)
        validate_config(config)
        print("  [ok] Config structure valid")
    except (ValueError, FileNotFoundError) as e:
        errors.append(str(e))

    template_skill = REPO_ROOT / "skills" / "_template" / "SKILL.md"
    template_analysis = REPO_ROOT / "skills" / "_template" / "comedian-slug-style-analysis.md"
    if template_skill.exists() and template_analysis.exists():
        print("  [ok] Template present (SKILL.md + style-analysis.md)")
    else:
        errors.append("Template missing in skills/_template/ (need SKILL.md + comedian-slug-style-analysis.md)")

    source_dir = resolve_path(config.get("source_dir", "./source"), REPO_ROOT)
    ensure_dir(source_dir)
    print(f"  [ok] Source dir ready: {source_dir}")

    skills_dir = resolve_path(config.get("skills_dir", "./skills"), REPO_ROOT)
    ensure_dir(skills_dir)
    print(f"  [ok] Skills dir ready: {skills_dir}")

    writeprint = REPO_ROOT / "writeprint" / "writeprint-generator.md"
    if writeprint.exists():
        print("  [ok] Writeprint generator present")
    else:
        errors.append("writeprint/writeprint-generator.md missing — needed for analysis phase")

    import pipeline.scripts.shared_utils as su

    _ = su

    if errors:
        print("\nERRORS (must fix):")
        for e in errors:
            print(f"  [X] {e}")
        print("\nPre-flight FAILED.")
        return False
    print("\nPre-flight PASSED.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comedian voices pipeline preflight")
    parser.add_argument("--config", required=True, help="Path to config.json")
    args = parser.parse_args()
    sys.exit(0 if run_preflight(args.config) else 1)