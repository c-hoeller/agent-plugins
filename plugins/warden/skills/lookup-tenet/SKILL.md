---
name: lookup-tenet
description: Use when an Engineering Tenet might apply to the work but no `et-NNNN-*` skill auto-loaded — e.g. when reviewing a diff in an unfamiliar area, when the user asks "is this allowed?", when verifying an Exception clause before invoking it, or when looking up a tenet by ID.
---

# Looking Up an Engineering Tenet

The Warden Charter (auto-injected at session start) lists every Tier 1
tenet by ID and points at its `et-NNNN-*` skill. Each tenet's full
content lives in that skill and auto-loads when the skill's `triggers`
match the work being done. This `lookup-tenet` skill is the **manual
fallback** for the cases where auto-loading is not enough.

## When to use this skill

- You are reviewing a diff or proposed change in an area where no
  tenet skill auto-loaded, but you suspect one might apply.
- The user asks "is X allowed?" and you want to scan the catalog.
- You are about to invoke an `Exceptions` clause and want to read the
  full tenet to verify the exception covers your situation.
- You need to find a tenet by tag, topic, or partial title.

## How to look one up

The Warden plugin sets the `CLAUDE_PLUGIN_ROOT` environment variable
when its hooks fire, but this variable is **not guaranteed** inside
auto-loaded skill tool calls. Resolve the plugin root once at the
start of the lookup and reuse it:

```bash
# Prefer the env var when available (set by Claude Code for plugin tooling).
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"

# Fallback: search common install roots for a warden plugin directory that
# carries a build/ folder (the marker that distinguishes it from a stub).
if [ -z "$PLUGIN_ROOT" ] || [ ! -d "$PLUGIN_ROOT/build" ]; then
  PLUGIN_ROOT="$(
    for root in \
        "$HOME/.claude/plugins" \
        "$HOME/.config/claude-code/plugins" \
        "./plugins" "."; do
      [ -d "$root" ] || continue
      find "$root" -maxdepth 4 -type d -name warden 2>/dev/null \
        | while read -r d; do [ -d "$d/build" ] && echo "$d" && break; done
    done | head -1
  )"
fi
```

Once `$PLUGIN_ROOT` is known, two index forms are available:

- `$PLUGIN_ROOT/build/index.md` — one-line-per-tenet, human-scannable.
- `$PLUGIN_ROOT/build/index.json` — structured. Use this for any
  query that involves filtering by tag, language, framework, or tier.
  As the catalog grows past ~15 tenets, the markdown index is no
  longer scan-friendly; the JSON index is.

### Discovery patterns

Every query below assumes `INDEX="$PLUGIN_ROOT/build/index.json"` and
that `jq` is on PATH (Claude Code ships with it).

```bash
# By tag — "tenets that touch testing"
jq -r '.tenets[] | select(.tags | index("testing")) | .id + " — " + .title' "$INDEX"

# By language — "tenets that apply to TypeScript code"
jq -r '.tenets[]
  | select(.applies_to == "any" or .applies_to.language == "TypeScript")
  | .id + " — " + .title' "$INDEX"

# By tier — "all tier 1 tenets, listed in the always-on charter"
jq -r '.tenets[] | select(.tier == 1) | .id + " — " + .title' "$INDEX"

# Find a specific tenet by ID and print its skill name
jq -r '.tenets[] | select(.id == "ET-0001") | .skill' "$INDEX"

# Free-text search across titles and tags
jq -r --arg q "validation" '
  .tenets[]
  | select((.title | ascii_downcase | contains($q)) or (.tags | index($q)))
  | .id + " — " + .title' "$INDEX"
```

If `jq` is unavailable for some reason, fall back to grepping
`build/index.md`:

```bash
grep -E "tags:.*testing" "$PLUGIN_ROOT/build/index.md"
```

### Reading the full tenet body

Once you have an ID, read either:

- `$PLUGIN_ROOT/tenets/<ID>-*.md` — the source file, with full
  `Rule` / `Why` / `Bad Example` / `Good Example` / `Exceptions`,
  `triggers`, and any `Rationalizations`.
- `$PLUGIN_ROOT/skills/et-<id-lower>-*/SKILL.md` — the rendered skill
  form, identical content with a generated marker on top.

## Applying a tenet

Treat the `Rule` as binding for the change you are making. Before
claiming an `Exception` applies, verify the exception text covers
your situation — exceptions are scoped, not blanket waivers.

If a tenet's `related` frontmatter lists other tenets, read those too;
related tenets often interact (e.g. one tenet's exception is governed
by another tenet's rule).

## When NOT to use this skill

- A `et-NNNN-*` skill already auto-loaded — apply it directly, no
  lookup needed.
- The user is explicitly asking you to violate a tenet — surface the
  violation and the affected tenet ID before complying or pushing back.
