#!/usr/bin/env bash
# Run one skill-triggering behavior test.
#
# Usage: run-test.sh <expected-skill-name> <prompt-file> [--expect-present|--expect-absent]
#
# Invokes `claude -p` headless with the prompt, captures the stream-JSON
# tool-use trail, and exits 0 iff the expectation matches:
#   --expect-present (default): the skill MUST appear in the tool-use stream
#   --expect-absent:            the skill MUST NOT appear (false-positive guard)
# See tests/skill-triggering/README.md for exit-code semantics.
set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "usage: $0 <expected-skill-name> <prompt-file> [--expect-present|--expect-absent]" >&2
  exit 2
fi

EXPECTED_SKILL="$1"
PROMPT_FILE="$2"
EXPECTATION="${3:---expect-present}"

case "$EXPECTATION" in
  --expect-present|--expect-absent) ;;
  *)
    echo "run-test: unknown expectation \`$EXPECTATION\` (use --expect-present or --expect-absent)" >&2
    exit 2
    ;;
esac

if ! command -v claude >/dev/null 2>&1; then
  echo "run-test: \`claude\` CLI not on PATH — install Claude Code or adjust PATH" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "run-test: \`jq\` not on PATH — required to filter stream-JSON" >&2
  exit 2
fi
if [ ! -r "$PROMPT_FILE" ]; then
  echo "run-test: cannot read prompt file: $PROMPT_FILE" >&2
  exit 2
fi

# Per-scenario hard cap. Most prompts get a verdict within ~30s; 90s is the
# soft upper bound before we treat the run as a timeout failure.
CLAUDE_TIMEOUT="${WARDEN_BEHAVIOR_TEST_TIMEOUT:-90}"

# Run claude headless with stream-json output. Sandbox via --dangerously-skip-permissions
# is intentionally NOT used — we want the test to reflect real-session behavior,
# including any permission prompts that would surface in normal use.
RAW_OUT="$(mktemp -t warden-skill-trigger.XXXXXX)"
trap 'rm -f "$RAW_OUT"' EXIT

# `claude -p <prompt>` reads the prompt from arg or stdin. We pipe via stdin
# so multi-line prompts work without quoting hazards.
set +e
if command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
else
  TIMEOUT_BIN=""
fi

if [ -n "$TIMEOUT_BIN" ]; then
  "$TIMEOUT_BIN" "$CLAUDE_TIMEOUT" \
    claude -p --output-format stream-json --verbose < "$PROMPT_FILE" > "$RAW_OUT"
else
  claude -p --output-format stream-json --verbose < "$PROMPT_FILE" > "$RAW_OUT"
fi
CLAUDE_EXIT=$?
set -e

if [ "$CLAUDE_EXIT" -ne 0 ]; then
  echo "run-test: claude exited $CLAUDE_EXIT (timeout or error)" >&2
  exit 3
fi

# Stream-JSON emits one event per line. Tool-use events for the Skill tool
# carry the invoked skill name in `.message.content[].input.skill` or in
# `.message.content[].name` depending on event variant. We accept any line
# that mentions the skill in a Skill tool-use context.
MATCH="$(
  jq -r --arg skill "$EXPECTED_SKILL" '
    select(
      (.type? == "assistant" and (.message?.content?[]? | select(.type? == "tool_use" and .name? == "Skill")))
      or
      (.message?.content?[]? | objects | select(.type? == "tool_use" and .name? == "Skill"))
    )
    | (.message.content[]? | select(.type? == "tool_use" and .name? == "Skill") | .input)
    | (tostring)
  ' < "$RAW_OUT" 2>/dev/null | grep -F "$EXPECTED_SKILL" | head -1 || true
)"

REL_PROMPT="${PROMPT_FILE##*/scenarios/}"

if [ "$EXPECTATION" = "--expect-present" ]; then
  if [ -n "$MATCH" ]; then
    echo "PASS  $EXPECTED_SKILL  $REL_PROMPT"
    exit 0
  fi
  echo "FAIL  $EXPECTED_SKILL  $REL_PROMPT"
  echo "       expected \`$EXPECTED_SKILL\` in tool-use stream, none seen"
  exit 1
fi

# --expect-absent: skill MUST NOT have fired
if [ -z "$MATCH" ]; then
  echo "PASS-NEG  $EXPECTED_SKILL  $REL_PROMPT"
  exit 0
fi
echo "FAIL-NEG  $EXPECTED_SKILL  $REL_PROMPT"
echo "       expected \`$EXPECTED_SKILL\` to be absent, but it was invoked"
exit 1
