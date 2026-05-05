#!/usr/bin/env bash
# Measurement run: invoke `claude -p` against every prompt under
# measurements/<measurement-name>/<class>/*.txt, capture every Skill
# tool-use, and emit a markdown table that classifies each result.
#
# Unlike run-test.sh (pass/fail per scenario), this is a data-collection
# tool. It does not assert outcomes — it just records what happened so
# you can decide whether a force-load mechanism (or a description tweak)
# is justified by the empirical hit rate.
#
# Usage: measure.sh <measurement-name>
#
# Costs real Claude API calls (one per prompt). Run manually; not part
# of `poe ci`.
set -uo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 <measurement-name>" >&2
  exit 2
fi

MEASUREMENT="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/measurements/$MEASUREMENT"

if [ ! -d "$ROOT" ]; then
  echo "measure: no measurement directory at $ROOT" >&2
  exit 2
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "measure: \`claude\` CLI not on PATH" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "measure: \`jq\` not on PATH" >&2
  exit 2
fi

CLAUDE_TIMEOUT="${WARDEN_BEHAVIOR_TEST_TIMEOUT:-90}"
TIMEOUT_BIN=""
command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN="gtimeout"
[ -z "$TIMEOUT_BIN" ] && command -v timeout >/dev/null 2>&1 && TIMEOUT_BIN="timeout"

REPORT="$ROOT/report.md"
shopt -s nullglob

{
  echo "# Measurement report — $MEASUREMENT"
  echo ""
  echo "_Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) — one row per prompt._"
  echo ""
  echo "Each row records every Skill tool invocation observed in the"
  echo "stream-JSON output. The target skill (\`$MEASUREMENT\`) is highlighted"
  echo "separately from any other Warden et-* skills so you can see whether"
  echo "the target competed with or yielded to a more specific tenet skill."
  echo ""
  echo "| Class | Prompt | Target loaded | Other Warden skills loaded |"
  echo "|---|---|---|---|"
} > "$REPORT"

TOTAL=0
TARGET_HITS=0

for class_dir in "$ROOT"/*/; do
  class="$(basename "$class_dir")"
  [ "$class" = "report.md" ] && continue
  for prompt in "$class_dir"*.txt; do
    TOTAL=$((TOTAL + 1))
    prompt_name="$(basename "$prompt" .txt)"
    raw="$(mktemp -t warden-measure.XXXXXX)"

    set +e
    if [ -n "$TIMEOUT_BIN" ]; then
      "$TIMEOUT_BIN" "$CLAUDE_TIMEOUT" \
        claude -p --output-format stream-json --verbose < "$prompt" > "$raw" 2>/dev/null
    else
      claude -p --output-format stream-json --verbose < "$prompt" > "$raw" 2>/dev/null
    fi
    rc=$?
    set -e

    if [ "$rc" -ne 0 ]; then
      echo "| \`$class\` | \`$prompt_name\` | _claude exit $rc_ | — |" >> "$REPORT"
      rm -f "$raw"
      continue
    fi

    # Extract every Skill tool invocation as JSON, then pull skill names.
    invocations="$(
      jq -r '
        .message?.content?[]?
        | select(.type? == "tool_use" and .name? == "Skill")
        | (.input.skill // .input.name // (.input | tostring))
      ' < "$raw" 2>/dev/null || true
    )"

    target_loaded="no"
    others=""
    while IFS= read -r skill; do
      [ -z "$skill" ] && continue
      if echo "$skill" | grep -qE "(^|:)$MEASUREMENT$"; then
        target_loaded="yes"
      elif echo "$skill" | grep -qE "(^|:)et-[0-9]"; then
        if [ -z "$others" ]; then
          others="$skill"
        else
          others="$others, $skill"
        fi
      fi
    done <<< "$invocations"

    [ "$target_loaded" = "yes" ] && TARGET_HITS=$((TARGET_HITS + 1))
    [ -z "$others" ] && others="—"

    echo "| \`$class\` | \`$prompt_name\` | $target_loaded | $others |" >> "$REPORT"
    rm -f "$raw"
  done
done

{
  echo ""
  echo "**Summary**: \`$MEASUREMENT\` loaded in $TARGET_HITS / $TOTAL prompts."
} >> "$REPORT"

echo
echo "report written to: $REPORT"
echo "summary: $MEASUREMENT loaded in $TARGET_HITS / $TOTAL prompts"
