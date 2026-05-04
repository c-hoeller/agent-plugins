#!/usr/bin/env python3
"""Validate every tenet in plugins/warden/tenets/ against the spec.

Exits 0 if all tenets pass; non-zero if any error is found. Prints a
human-readable report to stdout regardless of outcome.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import warden_lib  # noqa: E402


def main() -> int:
    plugin_root = Path(__file__).resolve().parent.parent
    tenets_dir = plugin_root / "tenets"

    if not tenets_dir.is_dir():
        print(f"validate: tenets directory not found at {tenets_dir}", file=sys.stderr)
        return 2

    try:
        tenets = warden_lib.load_all(tenets_dir)
    except warden_lib.WardenError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    errors = warden_lib.validate(tenets)
    if errors:
        print(f"validate: {len(errors)} error(s) across {len(tenets)} tenet(s)\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"validate: OK ({len(tenets)} tenet(s) checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
