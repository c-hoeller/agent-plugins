# Warden

> Senior coding standards as **Engineering Tenets**, auto-loaded into
> every Claude Code session. Capabilities come from elsewhere; Warden
> makes sure those capabilities don't ship junior-level code.

Warden ships a curated knowledge base of coding best-practices and
anti-patterns. A small **always-on charter** is injected into every
session via a `SessionStart` hook, and each individual tenet ships as
its own **auto-loadable skill** that triggers when its description
matches the work the agent is doing. The full catalog is also
browsable on demand via the `lookup-tenet` skill.

> Working on Warden itself? See [CONTRIBUTING.md](CONTRIBUTING.md) for
> the build pipeline, dev tooling, and CI gate.

## What's an Engineering Tenet?

An **Engineering Tenet** (`ET-NNNN`) is a structured record of one
binding coding standard. Each tenet has:

- a one-sentence imperative `Rule`
- a `Why` explaining root cause and consequence
- minimal `Bad Example` / `Good Example` code pairs
- explicit `Exceptions` — when the tenet legitimately does not apply
- a list of `triggers` — short phrases describing the situations where
  the tenet should auto-load (these become the skill's `description`)

Tenets are not advice. They are non-negotiable defaults; deviations
require an explicit invocation of the `Exceptions` clause or a
maintainer-approved override.

## How tenets reach the agent

Two complementary mechanisms, with bounded always-on cost:

| Mechanism                | What it loads                                  | When                             |
|--------------------------|------------------------------------------------|----------------------------------|
| `SessionStart` hook      | The Charter (~1 KB): protocol + Tier 1 index   | Every session, unconditionally   |
| Auto-loaded tenet skills | Full Rule / Why / Examples / Exceptions        | When the skill's triggers match  |
| `lookup-tenet` skill     | Browse the index, read any tenet by ID / topic | When the agent (or user) asks    |

The Charter never grows with the catalog beyond a small per-tenet
index line, so adding tenets does not balloon the always-on context
budget. Per-tenet detail lives in skills and only enters context when
relevant.

**Tier 1** = universal principles. Listed in the Charter index.
`paths:` is optional — add it only when the principle is universal but
only applies to languages that have the relevant feature (e.g. access
modifiers exist in TS / Java / C# but not in Python or JS).
**Tier 2** = language- or framework-specific. Not listed in the
Charter; auto-loads via skill triggers gated by a **required** `paths:`
glob. Validation rejects tier 2 without `paths:` — an unscoped tier 2
tenet would compete in the global description-match pool against every
other skill and break the budget once the catalog grows.

The `SessionStart` hook is split across two files:
[`hooks/run-hook.cmd`](hooks/run-hook.cmd) is a polyglot Windows-`.cmd`
/ POSIX-shell wrapper, and [`hooks/session-start`](hooks/session-start)
is the extensionless bash script with the actual logic. On POSIX,
`/bin/sh` heredoc-discards the cmd block in the wrapper and exec-bashes
`session-start` directly. On Windows, `cmd.exe` runs the batch block,
locates `bash.exe` (Git for Windows / MSYS2 / Cygwin), and invokes
`session-start` through it. JSON escaping is done at build time, so no
shell-side escaping ever runs.

## Repository layout

```text
plugins/warden/
├── .claude-plugin/plugin.json    # Claude Code plugin manifest
├── hooks/                        # SessionStart hook + registration
├── skills/
│   ├── lookup-tenet/             # hand-authored catalog browser
│   └── et-NNNN-<slug>/           # generated: one auto-loadable skill per tenet
├── tenets/                       # source of truth — one file per tenet
├── templates/ET-NNNN-template.md # starting point for a new tenet
├── build/                        # generated, committed (charter.md, charter.json, index.json)
├── scripts/                      # build/validation tooling — see CONTRIBUTING.md
├── tests/                        # pytest suite
└── pyproject.toml                # uv-managed deps + tool config
```

The `skills/et-*/` directories and `build/` are **fully generated**
by `uv run poe build` from `tenets/`. They are committed so the
plugin is installable on `git clone` without a build step.
The hand-authored `lookup-tenet` skill lives alongside and is never
touched by the build.

## Authoring a tenet

1. Copy the template, picking the next free `NNNN` and a gerund-style
   slug (see "Naming a tenet file" below):

   ```bash
   cp templates/ET-NNNN-template.md tenets/ET-0042-keeping-something-private.md
   ```

2. Edit the new file. The template's inline comments document every
   field — required: `id`, `title`, `type`, `tier`, `applies-to`,
   `since`, `triggers`; optional: `paths`, `tags`, `related`. Body
   sections, in order: `Rule`, `Why`, `Bad Example`,
   `Good Example`, `Exceptions`, optionally `Rationalizations`.

3. Run `uv run poe build` to regenerate `build/` and the per-tenet
   `skills/et-*/SKILL.md`. **All generated artifacts must be committed
   alongside the source tenet** — the plugin must be installable on
   `git clone` without a build step. CI fails on drift.

For the full set of build/test/lint commands, the local check gate,
and CI configuration, see [CONTRIBUTING.md](CONTRIBUTING.md).

### Writing good `triggers`

Triggers become the skill's `description`, which is what Claude Code
matches against to auto-invoke the skill. Three rules:

1. **Action-shaped, not topic-labeled.** Describe the situation the
   agent or user is in, not the abstract subject. "keeping a member
   private when a test wants to call it directly" beats "encapsulation
   in tests".
2. **Positive framing, even when the rule is negative.** Triggers
   describe the *situation* that activates the tenet, and situations
   read more naturally in positive form ("when about to X") than as
   negated ones ("never X"). The Rule body itself can — and should — be
   a hard "Never"; only the triggers shift. Skill descriptions read as
   "when to use" prose; the imperative belongs in the Rule.
3. **Front-load the strongest trigger.** Skill `description` (combined
   with `when_to_use` if present) is capped at 1,536 characters in the
   global skill listing (see [Claude Code Skills docs][skills]); when
   the trigger list grows or the shared budget tightens, the first
   trigger is the one that survives any truncation. Put the situation
   that most directly activates this tenet first.

[skills]: https://code.claude.com/docs/en/skills

Example:

```yaml
triggers:
  - keeping a member private when a test wants to call it directly
  - testing a class whose helper is private/protected/internal and the test cannot reach it
  - reviewing a diff that widens an access modifier with a justification referencing tests
```

A single tenet typically needs 3–5 triggers covering the same rule
from different angles (the user's framing, the agent's planned action,
the diff being reviewed).

### Scoping a tenet to specific files (`paths`)

For language- or framework-specific tenets, add an optional `paths`
list of glob patterns to the frontmatter. The generated skill emits
them as a `paths:` field, which Claude Code uses to auto-invoke the
skill **only when the active edit/read targets a matching file**. This
is more deterministic than description matching and — crucially —
keeps the global skill-description budget free of tenets that cannot
apply to the current file:

```yaml
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.java"
```

Omit `paths` for language-agnostic tenets (e.g. naming, commit
hygiene, security) — they should be eligible everywhere.

See `tenets/ET-0001-keeping-test-helpers-private.md` for a complete
example.

### Naming a tenet file

Filename pattern: `ET-NNNN-<slug>.md`, where `<slug>` is **gerund-style
and describes the desired behaviour, not the prohibition**:

- ✅ `ET-0001-keeping-test-helpers-private.md`
- ❌ `ET-0001-no-lowering-access-modifiers-for-tests.md`

The slug also drives the generated skill directory name
(`skills/et-NNNN-<slug>/`), and skill names with positive,
action-shaped slugs auto-invoke more reliably than negated topic
labels. The `Rule` body keeps the hard "Never" — only the slug shifts.

## Versioning

Warden follows SemVer from `0.1.0`.

- **Patch:** new tenet, copy edits, additive non-breaking metadata.
- **Minor:** new optional frontmatter field, new tier.
- **Major:** removed/renamed required frontmatter field or required
  body section — anything that breaks existing tenets.

The `since` field on each tenet records the plugin version in which
the tenet was introduced.
