#!/usr/bin/env bash
# Run every behavior-test scenario under tests/skill-triggering/scenarios/.
#
# Each scenario directory's name is the expected skill; each .txt file under
# its `positive/` subdirectory is a separate prompt. The suite invokes
# run-test.sh for each prompt and returns non-zero if any scenario fails.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCENARIO_ROOT="$SCRIPT_DIR/scenarios"

if [ ! -d "$SCENARIO_ROOT" ]; then
  echo "run-suite: no scenarios/ directory at $SCENARIO_ROOT" >&2
  exit 2
fi

shopt -s nullglob
TOTAL=0
FAILED=0
SKIPPED=0

for skill_dir in "$SCENARIO_ROOT"/*/; do
  expected_skill="$(basename "$skill_dir")"
  positive_dir="${skill_dir}positive"
  [ -d "$positive_dir" ] || continue

  for prompt in "$positive_dir"/*.txt; do
    TOTAL=$((TOTAL + 1))
    set +e
    "$SCRIPT_DIR/run-test.sh" "$expected_skill" "$prompt"
    rc=$?
    set -e
    case "$rc" in
      0)  ;;
      1)  FAILED=$((FAILED + 1)) ;;
      2)  SKIPPED=$((SKIPPED + 1)) ;;
      3)  FAILED=$((FAILED + 1)) ;;
      *)  FAILED=$((FAILED + 1)) ;;
    esac
  done
done

echo
echo "behavior-test suite: $TOTAL scenarios, $FAILED failed, $SKIPPED skipped (env)"
if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
if [ "$TOTAL" -eq 0 ]; then
  echo "behavior-test suite: no scenarios discovered" >&2
  exit 2
fi
exit 0
