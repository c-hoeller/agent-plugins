#!/usr/bin/env bash
# Run every behavior-test scenario under tests/skill-triggering/scenarios/.
#
# Each scenario directory's name is the expected skill; each .txt file under
# its `positive/` subdirectory is a separate prompt. The suite invokes
# run-test.sh for each prompt and returns non-zero if any scenario fails.
#
# Set WARDEN_BEHAVIOR_TEST_PARALLEL=N to run up to N scenarios concurrently
# (default 4). N=1 reproduces the original strictly-sequential behavior.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCENARIO_ROOT="$SCRIPT_DIR/scenarios"

if [ ! -d "$SCENARIO_ROOT" ]; then
  echo "run-suite: no scenarios/ directory at $SCENARIO_ROOT" >&2
  exit 2
fi

PARALLEL="${WARDEN_BEHAVIOR_TEST_PARALLEL:-4}"
case "$PARALLEL" in
  ''|*[!0-9]*)
    echo "run-suite: WARDEN_BEHAVIOR_TEST_PARALLEL must be a positive integer (got '$PARALLEL')" >&2
    exit 2
    ;;
esac
if [ "$PARALLEL" -lt 1 ]; then
  echo "run-suite: WARDEN_BEHAVIOR_TEST_PARALLEL must be >= 1 (got '$PARALLEL')" >&2
  exit 2
fi

shopt -s nullglob

# Collect every (expected_skill, prompt, flag) triple as a NUL-separated job
# list, then dispatch via xargs -P. We avoid arrays-of-tuples bash gymnastics
# by streaming the jobs through a tab-separated record per line and letting
# a small worker function parse them.
JOB_LIST="$(mktemp -t warden-suite-jobs.XXXXXX)"
RESULT_LOG="$(mktemp -t warden-suite-results.XXXXXX)"
trap 'rm -f "$JOB_LIST" "$RESULT_LOG"' EXIT

emit_jobs() {
  local skill_dir expected_skill flag prompt class_dir_flag class_dir
  for skill_dir in "$SCENARIO_ROOT"/*/; do
    expected_skill="$(basename "$skill_dir")"
    for class_dir_flag in "positive:--expect-present" "negative:--expect-absent"; do
      class_dir="${class_dir_flag%%:*}"
      flag="${class_dir_flag##*:}"
      [ -d "${skill_dir}${class_dir}" ] || continue
      for prompt in "${skill_dir}${class_dir}"/*.txt; do
        # Tab-separated fields, NUL terminator. NUL works with both BSD
        # (macOS) and GNU xargs via -0; the GNU-only -d '\n' does not.
        printf '%s\t%s\t%s\0' "$expected_skill" "$prompt" "$flag"
      done
    done
  done
}

emit_jobs > "$JOB_LIST"

# Count NUL-terminated records.
TOTAL="$(tr -cd '\0' < "$JOB_LIST" | wc -c | tr -d ' ')"
if [ "$TOTAL" -eq 0 ]; then
  echo "behavior-test suite: no scenarios discovered" >&2
  exit 2
fi

export SCRIPT_DIR
export RESULT_LOG

# xargs -0 -P N -I {} dispatches each NUL-terminated tab-separated record to
# a fresh `bash -c`. The worker is inlined (not `export -f`'d) because
# function-export through xargs is fragile across bash versions and BSD/GNU
# xargs differ in how they pass empty replacement strings. NUL-separated
# records work on BSD xargs (macOS) and GNU xargs alike; `-d '\n'` is GNU-only.
#
# Each worker prints its verdict line atomically (single short write) so
# concurrent verdicts don't interleave on stdout.
xargs -0 -P "$PARALLEL" -I {} bash -c '
  record="$1"
  skill=$(printf "%s" "$record" | cut -f1)
  prompt=$(printf "%s" "$record" | cut -f2)
  flag=$(printf "%s" "$record" | cut -f3)
  out=$("$SCRIPT_DIR/run-test.sh" "$skill" "$prompt" "$flag" 2>&1)
  rc=$?
  printf "%s\n" "$out"
  # Tally record: rc + first verdict line. run-test.sh prints multi-line
  # output on FAIL (verdict + "expected ..." detail); we only want the
  # verdict line in the tally so the line-based reader cannot mis-parse
  # detail lines as separate records.
  verdict=$(printf "%s\n" "$out" | head -n 1)
  printf "%d\t%s\n" "$rc" "$verdict" >> "$RESULT_LOG"
' _ {} < "$JOB_LIST" || true

# Tally from the result log. Exit codes follow run-test.sh:
#   0 = pass, 1 = expectation violated, 2 = env/skip, 3 = claude error/timeout.
FAILED=0
SKIPPED=0
while IFS=$'\t' read -r rc _; do
  case "$rc" in
    0)  ;;
    2)  SKIPPED=$((SKIPPED + 1)) ;;
    *)  FAILED=$((FAILED + 1)) ;;
  esac
done < "$RESULT_LOG"

echo
if [ "$FAILED" -gt 0 ]; then
  echo "Failures:"
  awk -F'\t' '$1 != "0" && $1 != "2" { print "  " $2 }' "$RESULT_LOG"
  echo
fi

echo "behavior-test suite: $TOTAL scenarios, $FAILED failed, $SKIPPED skipped (parallel=$PARALLEL)"
if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
exit 0
