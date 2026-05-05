#!/usr/bin/env python3
"""Build (or check) the Warden plugin artifacts.

Default mode writes:

  build/charter.md             — human-readable always-on charter
  build/charter.json           — pre-built SessionStart hook payload
  build/index.json             — structured tenet metadata for lookup-tenet
  skills/et-NNNN-<slug>/SKILL.md — one auto-loadable skill per tenet

With `--check`, no files are written: every artifact is rendered in memory
and compared against the committed copy. Exits non-zero on the first
mismatch with a unified diff so the failing artifact is obvious in CI logs.
This guards the README's "installable on git clone without a build step"
contract — a tenet edit without `poe build` would otherwise silently ship
stale generated skills to consumers.
"""

from __future__ import annotations

import argparse
import difflib
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


def _diff(label: str, expected: str, actual: str) -> str:
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{label} (committed)",
            tofile=f"{label} (would be regenerated)",
        )
    )


def _check(plugin_root: Path, tenets: list[warden_lib.Tenet]) -> int:
    """Compare every committed artifact against what build would emit.

    Returns 0 on match, 1 on any mismatch. Mismatches are printed as unified
    diffs (or a one-line message for missing/orphan files).
    """
    build_dir = plugin_root / "build"
    skills_dir = plugin_root / "skills"
    preamble = warden_lib.read_charter_preamble(plugin_root)

    mismatches: list[str] = []

    expected_charter = warden_lib.render_charter(tenets, preamble)
    actual_charter = (build_dir / "charter.md").read_text(encoding="utf-8")
    if actual_charter != expected_charter:
        mismatches.append(_diff("build/charter.md", expected_charter, actual_charter))

    expected_payload = warden_lib.render_tier1_hook_payload(expected_charter)
    actual_payload = (build_dir / "charter.json").read_text(encoding="utf-8")
    if actual_payload != expected_payload:
        mismatches.append(_diff("build/charter.json", expected_payload, actual_payload))

    expected_index_json = warden_lib.render_index_json(tenets)
    actual_index_json = (build_dir / "index.json").read_text(encoding="utf-8")
    if actual_index_json != expected_index_json:
        mismatches.append(_diff("build/index.json", expected_index_json, actual_index_json))

    expected_skill_dirs: set[str] = set()
    for t in tenets:
        skill_name, expected_content = warden_lib.render_skill_for_tenet(t)
        expected_skill_dirs.add(skill_name)
        skill_path = skills_dir / skill_name / "SKILL.md"
        if not skill_path.is_file():
            mismatches.append(
                f"missing generated skill file: {skill_path.relative_to(plugin_root)}"
            )
            continue
        actual_content = skill_path.read_text(encoding="utf-8")
        if actual_content != expected_content:
            mismatches.append(
                _diff(str(skill_path.relative_to(plugin_root)), expected_content, actual_content)
            )

    # Detect orphan generated skill dirs (a tenet was renamed/removed but the
    # old skill dir wasn't cleaned up).
    if skills_dir.is_dir():
        for child in skills_dir.iterdir():
            if (
                child.is_dir()
                and child.name.startswith("et-")
                and child.name not in expected_skill_dirs
            ):
                mismatches.append(
                    f"orphan generated skill dir: skills/{child.name}/ (no matching tenet)"
                )

    if mismatches:
        print(
            "build --check: build/ or skills/et-*/ are out of date — "
            "run 'uv run poe build' and commit:\n"
        )
        for m in mismatches:
            print(m)
            print()
        return 1

    print(f"build --check: OK ({len(tenets)} tenet(s), all generated artifacts match)")
    return 0


def _write(plugin_root: Path, tenets: list[warden_lib.Tenet]) -> int:
    build_dir = plugin_root / "build"
    skills_dir = plugin_root / "skills"
    preamble = warden_lib.read_charter_preamble(plugin_root)

    build_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    charter = warden_lib.render_charter(tenets, preamble)
    charter_md = build_dir / "charter.md"
    charter_md.write_text(charter, encoding="utf-8")

    charter_json = build_dir / "charter.json"
    charter_json.write_text(warden_lib.render_tier1_hook_payload(charter), encoding="utf-8")

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
        f"(tier-1: {tier1_count}), {index_json_path.name} "
        f"({len(tenets)} total tenets), generated {len(tenets)} tenet skill(s)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed artifacts match what build would emit (no writes)",
    )
    args = parser.parse_args()

    plugin_root = Path(__file__).resolve().parent.parent
    tenets_dir = plugin_root / "tenets"

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
        label = "build --check" if args.check else "build"
        print(f"{label}: aborted, {len(errors)} validation error(s):\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    return _check(plugin_root, tenets) if args.check else _write(plugin_root, tenets)


if __name__ == "__main__":
    raise SystemExit(main())
