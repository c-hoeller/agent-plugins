#!/usr/bin/env python3
"""Build the Warden plugin artifacts.

Validates every tenet, then writes:

  build/charter.md             — human-readable always-on charter
  build/charter.json           — pre-built SessionStart hook payload
  build/index.md               — full tenet index for the lookup-tenet skill
  skills/et-NNNN-<slug>/SKILL.md — one auto-loadable skill per tenet

Aborts non-zero on validation errors without touching build/ or skills/.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import warden_lib  # noqa: E402


def _clean_generated_skills(skills_dir: Path) -> None:
    """Remove previously generated tenet skill directories.

    Only directories matching the generated naming convention (`et-*`) are
    removed; hand-authored skills like `lookup-tenet` are left untouched.
    """
    if not skills_dir.is_dir():
        return
    for child in skills_dir.iterdir():
        if child.is_dir() and child.name.startswith("et-"):
            shutil.rmtree(child)


def main() -> int:
    plugin_root = Path(__file__).resolve().parent.parent
    tenets_dir = plugin_root / "tenets"
    build_dir = plugin_root / "build"
    skills_dir = plugin_root / "skills"

    if not tenets_dir.is_dir():
        print(f"build: tenets directory not found at {tenets_dir}", file=sys.stderr)
        return 2

    try:
        tenets = warden_lib.load_all(tenets_dir)
    except warden_lib.WardenError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    errors = warden_lib.validate(tenets)
    if errors:
        print(f"build: aborted, {len(errors)} validation error(s):\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    build_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    charter = warden_lib.render_charter(tenets)
    charter_md = build_dir / "charter.md"
    charter_md.write_text(charter, encoding="utf-8")

    charter_json = build_dir / "charter.json"
    charter_json.write_text(warden_lib.render_tier1_hook_payload(charter), encoding="utf-8")

    index_path = build_dir / "index.md"
    index_path.write_text(warden_lib.render_index(tenets), encoding="utf-8")

    index_json_path = build_dir / "index.json"
    index_json_path.write_text(warden_lib.render_index_json(tenets), encoding="utf-8")

    _clean_generated_skills(skills_dir)
    for t in tenets:
        skill_name, content = warden_lib.render_skill_for_tenet(t)
        skill_dir = skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    tier1_count = sum(1 for t in tenets if t.tier == 1)
    print(
        f"build: OK — wrote {charter_md.name} + {charter_json.name} "
        f"(tier-1: {tier1_count}), {index_path.name} + {index_json_path.name} "
        f"({len(tenets)} total tenets), generated {len(tenets)} tenet skill(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
