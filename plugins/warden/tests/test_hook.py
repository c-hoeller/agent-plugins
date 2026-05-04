"""Smoke test for hooks/inject-charter.cmd on both polyglot branches.

The hook is a polyglot script: cmd.exe runs the batch block, /bin/sh runs
the shell block. Each test platform exercises the branch native to its
shell — POSIX hosts run the sh branch, Windows runs the cmd.exe branch.
Both must produce the same JSON-shaped SessionStart payload.

What this guards: any future edit to the polyglot heredoc structure that
breaks one branch — e.g. accidentally consuming the heredoc marker,
leaving an unquoted variable, or rewording the missing-payload warning —
fails here before it reaches a user session.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOK = PLUGIN_ROOT / "hooks" / "inject-charter.cmd"


def _shell_invocation() -> list[str]:
    if sys.platform == "win32":
        return ["cmd.exe", "/c", str(HOOK)]
    sh = shutil.which("sh") or "/bin/sh"
    return [sh, str(HOOK)]


def _env_with(plugin_root: Path) -> dict[str, str]:
    # Inherit the host env (Windows needs SystemRoot, ComSpec, etc.) and
    # override only the plugin-root pointer the hook reads.
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return env


def test_hook_emits_valid_session_start_payload():
    result = subprocess.run(
        _shell_invocation(),
        env=_env_with(PLUGIN_ROOT),
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Warden — Engineering Charter" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_succeeds_with_missing_payload_and_warns_on_stderr(tmp_path: Path):
    # Point at a plugin root with no build/charter.json — the hook MUST
    # exit 0 (never block a session) and emit a maintainer warning to stderr.
    result = subprocess.run(
        _shell_invocation(),
        env=_env_with(tmp_path),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert "charter.json missing" in result.stderr
