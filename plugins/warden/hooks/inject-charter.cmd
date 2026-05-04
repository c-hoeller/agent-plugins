: << 'CMDBLOCK'
@echo off
REM ============================================================================
REM Warden SessionStart hook — polyglot Windows .cmd / Unix shell script.
REM
REM This file is BOTH a valid Windows batch script AND a valid POSIX shell
REM script. cmd.exe runs the batch block below (between '@echo off' and the
REM matching CMDBLOCK marker). /bin/sh on Unix treats the cmd block as a
REM quoted heredoc (no expansion, no execution) and runs the shell block
REM below the marker.
REM
REM Hook contract: write build/charter.json to stdout. The file is a
REM pre-built JSON payload of the form
REM   {"hookSpecificOutput": {"hookEventName": "SessionStart",
REM    "additionalContext": "<rendered markdown>"}}
REM Claude Code parses it and injects additionalContext into the session.
REM
REM Pre-building the JSON payload avoids any runtime JSON-escaping in shell
REM (which would require awk / sed / jq — none guaranteed on Windows).
REM
REM If the payload is missing, log to stderr (visible to the user, not Claude)
REM and exit 0 so the session is never blocked.
REM ============================================================================
setlocal
set "PAYLOAD=%CLAUDE_PLUGIN_ROOT%\build\charter.json"
if exist "%PAYLOAD%" (
  type "%PAYLOAD%"
) else (
  echo warden: charter.json missing — run 'uv run poe build' 1>&2
)
exit /b 0
CMDBLOCK

# Unix block. /bin/sh consumed the cmd block above as a single-quoted heredoc
# (no parameter expansion, no command substitution).
payload="${CLAUDE_PLUGIN_ROOT}/build/charter.json"
if [ -f "$payload" ]; then
  cat "$payload"
else
  echo "warden: charter.json missing — run 'uv run poe build'" >&2
fi
exit 0
