#!/usr/bin/env python3
"""CI gate: assert that build/ and skills/et-*/ match what build.py would emit.

Renders every artifact in memory from the current tenets/ source and compares
against the committed files. Exits non-zero on the first mismatch with a
unified diff so the failing artifact is obvious in CI logs.

This guards the README's "installable on git clone without a build step"
contract: a tenet edit without `poe build` would otherwise silently ship
stale generated skills to consumers.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import warden_lib  # noqa: E402


def _diff(label: str, expected: str, actual: str) -> str:
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{label} (committed)",
            tofile=f"{label} (would be regenerated)",
        )
    )


def main() -> int:
    plugin_root = Path(__file__).resolve().parent.parent
    tenets_dir = plugin_root / "tenets"
    build_dir = plugin_root / "build"
    skills_dir = plugin_root / "skills"

    if not tenets_dir.is_dir():
        print(f"build-check: tenets directory not found at {tenets_dir}", file=sys.stderr)
        return 2

    try:
        tenets = warden_lib.load_all(tenets_dir)
    except warden_lib.WardenError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    errors = warden_lib.validate(tenets)
    if errors:
        print(f"build-check: validation failed ({len(errors)} error(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1

    mismatches: list[str] = []

    expected_charter = warden_lib.render_charter(tenets)
    actual_charter = (build_dir / "charter.md").read_text(encoding="utf-8")
    if actual_charter != expected_charter:
        mismatches.append(_diff("build/charter.md", expected_charter, actual_charter))

    expected_payload = warden_lib.render_tier1_hook_payload(expected_charter)
    actual_payload = (build_dir / "charter.json").read_text(encoding="utf-8")
    if actual_payload != expected_payload:
        mismatches.append(_diff("build/charter.json", expected_payload, actual_payload))

    expected_index = warden_lib.render_index(tenets)
    actual_index = (build_dir / "index.md").read_text(encoding="utf-8")
    if actual_index != expected_index:
        mismatches.append(_diff("build/index.md", expected_index, actual_index))

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
            "build-check: build/ or skills/et-*/ are out of date — run 'uv run poe build' and commit:\n"
        )
        for m in mismatches:
            print(m)
            print()
        return 1

    print(f"build-check: OK ({len(tenets)} tenet(s), all generated artifacts match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
