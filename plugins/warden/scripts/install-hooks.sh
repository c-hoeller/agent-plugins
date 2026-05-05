#!/usr/bin/env bash
# Install a local git pre-commit hook that runs `uv run poe ci` against the
# Warden plugin whenever a commit touches plugins/warden/**.
#
# Why this exists: the build-check CI gate (validate + format-check + lint +
# mypy + build-check + tests) catches drift between tenets/ and the committed
# build/ + skills/et-*/. Running it pre-commit fails fast on the dev's machine
# instead of after a push lands and CI rejects it minutes later.
#
# One-time setup:
#   bash plugins/warden/scripts/install-hooks.sh
#
# The hook is local to your clone (.git/hooks/pre-commit is not versioned).
# Anyone who hasn't run this script falls back to the GitHub-side warden-ci
# workflow as the safety net.
set -euo pipefail

# Resolve the repo root from this script's location: plugins/warden/scripts/.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
HOOK_DIR="$REPO_ROOT/.git/hooks"
HOOK_PATH="$HOOK_DIR/pre-commit"

mkdir -p "$HOOK_DIR"

# If a pre-commit hook already exists and isn't ours, refuse to overwrite —
# the dev may have their own customisation we'd otherwise clobber.
if [ -e "$HOOK_PATH" ] && ! grep -q "warden-pre-commit-hook-marker" "$HOOK_PATH" 2>/dev/null; then
    echo "install-hooks: refusing to overwrite existing $HOOK_PATH" >&2
    echo "  manually merge or remove it, then re-run this script." >&2
    exit 1
fi

cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
# warden-pre-commit-hook-marker — installed by plugins/warden/scripts/install-hooks.sh
#
# Runs `uv run poe ci` on plugins/warden when the pending commit touches it.
# Skipped otherwise so non-Warden commits stay fast.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PLUGIN_DIR="$REPO_ROOT/plugins/warden"

# Diff scope: staged changes only. We don't care about working-tree noise.
if ! git diff --cached --name-only --diff-filter=ACMRT | grep -q '^plugins/warden/'; then
    exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "warden pre-commit: \`uv\` not on PATH — skipping (install uv to enable)." >&2
    exit 0
fi

echo "warden pre-commit: running \`uv run poe ci\` on plugins/warden ..."
cd "$PLUGIN_DIR"
uv run poe ci
HOOK

chmod +x "$HOOK_PATH"
echo "install-hooks: installed $HOOK_PATH"
echo "  the hook runs \`uv run poe ci\` on plugins/warden/ before each commit"
echo "  that touches it. Bypass once with \`git commit --no-verify\` (discouraged)."
