"""Smoke tests for the SessionStart hook on both polyglot branches.

The hook is split across two files:
  - `hooks/run-hook.cmd`  — polyglot wrapper (cmd.exe + /bin/sh).
  - `hooks/session-start` — extensionless bash script with the actual logic.

POSIX hosts exercise the wrapper through /bin/sh (it heredoc-discards the cmd
block and exec-bashes the named script). Windows hosts exercise the wrapper
through cmd.exe (it locates bash.exe and invokes the script through it).

What this guards: any future edit to the polyglot heredoc structure, the exec
trampoline line, or the missing-payload warning that breaks one branch — fails
here before it reaches a user session.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
WRAPPER = PLUGIN_ROOT / "hooks" / "run-hook.cmd"
SCRIPT_NAME = "session-start"


def _shell_invocation() -> list[str]:
    if sys.platform == "win32":
        return ["cmd.exe", "/c", str(WRAPPER), SCRIPT_NAME]
    sh = shutil.which("sh") or "/bin/sh"
    return [sh, str(WRAPPER), SCRIPT_NAME]


def _env_with(plugin_root: Path) -> dict[str, str]:
    # Inherit the host env (Windows needs SystemRoot, ComSpec, etc.) and
    # override only the plugin-root pointer the hook reads.
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return env


def test_hook_emits_valid_session_start_payload():
    # encoding="utf-8" pins decoding of the hook's stdout. Without it,
    # subprocess.run(text=True) falls back to locale.getpreferredencoding()
    # which on Windows runners is the ANSI codepage (cp1252 etc.) — the
    # charter contains non-ASCII (em-dashes) and would silently corrupt.
    result = subprocess.run(
        _shell_invocation(),
        env=_env_with(PLUGIN_ROOT),
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    # — is EM DASH. Spelled as a unicode escape so the matched literal
    # is byte-for-byte deterministic regardless of how Python on the host
    # decodes this source file. The literal in the actual charter is the
    # same codepoint, just emitted via \xe2\x80\x94 from the JSON payload.
    assert "Warden \u2014 Engineering Charter" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_succeeds_with_missing_payload_and_warns_on_stderr(tmp_path: Path):
    # Point at a plugin root with no build/charter.json — the hook MUST
    # exit 0 (never block a session) and emit a maintainer warning to stderr.
    result = subprocess.run(
        _shell_invocation(),
        env=_env_with(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert "charter.json missing" in result.stderr
