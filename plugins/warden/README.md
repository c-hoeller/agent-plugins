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

**Tier 1** = universal, high-severity. Listed in the Charter index.
**Tier 2** = language- or framework-specific. Not listed in the
Charter; auto-loads via skill triggers when relevant code is touched.

## Repository layout

```text
plugins/warden/
├── .claude-plugin/plugin.json    # Claude Code plugin manifest
├── hooks/
│   ├── hooks.json                # SessionStart hook registration
│   └── inject-charter.cmd        # polyglot cmd+sh hook, emits charter.json
├── skills/
│   ├── using-warden/SKILL.md     # hand-authored: re-bootstraps Warden's contract mid-session
│   ├── lookup-tenet/SKILL.md     # hand-authored: on-demand catalog browser
│   └── et-NNNN-<slug>/SKILL.md   # generated: one auto-loadable skill per tenet
├── tenets/                       # source of truth — one file per tenet
│   └── ET-0001-*.md
├── templates/
│   └── ET-NNNN-template.md       # starting point for `cp` when authoring a new tenet
├── build/                        # generated, committed
│   ├── charter.json              # consumed by SessionStart hook (functional)
│   ├── charter.md                # same content, human-readable (review aid)
│   └── index.md                  # consumed by lookup-tenet skill
├── scripts/
│   ├── build.py                  # validate + render build artifacts + skills
│   ├── validate.py               # validation only
│   └── lib/warden_lib.py         # parsing, validation, rendering
├── tests/                        # pytest suite for build/validate/render
├── pyproject.toml                # uv-managed deps + ruff/mypy/poe config
└── uv.lock                       # pinned dependency versions (committed)
```

The `skills/et-*/` directories are **fully generated** by `poe build`
from `tenets/`. They are committed so the plugin is installable on
`git clone` without a build step. Hand-authored skills (currently only
`lookup-tenet`) live alongside and are never touched by the build.

## Authoring a tenet

1. Copy the template to a new file, picking the next free `NNNN` and a
   gerund-style slug (see "Naming a tenet file" below):

   ```bash
   cp templates/ET-NNNN-template.md tenets/ET-0042-keeping-something-private.md
   ```

2. Edit the new file. The template's inline comments document every
   field — required: `id`, `title`, `type`, `severity`, `tier`,
   `applies-to`, `since`, `triggers`; optional: `paths`, `tags`,
   `related`. Write the body sections in this order: `Rule`, `Why`,
   `Bad Example`, `Good Example`, `Exceptions`, optionally
   `Rationalizations`.
3. Run `uv run poe validate` to confirm the file is well-formed.
4. Run `uv run poe build` to regenerate `build/charter.{json,md}`,
   `build/index.md`, and the per-tenet `skills/et-*/SKILL.md`. All
   generated artifacts MUST be committed alongside the tenet — the
   plugin must be installable on `git clone` without a build step.

Or just run `uv run poe check` to do everything (format → lint →
typecheck → validate → build → test) in one go before committing.

### Writing good `triggers`

Triggers become the skill's `description`, which is what Claude Code
matches against to auto-invoke the skill. Three rules:

1. **Action-shaped, not topic-labeled.** Describe the situation the
   agent or user is in, not the abstract subject. "keeping a member
   private when a test wants to call it directly" beats "encapsulation
   in tests".
2. **Positive framing, even when the rule is negative.** Benchmarks
   show ~23 % lower compliance for negative directives ("never X")
   versus positive ones ("when about to X"). The Rule itself can — and
   should — be a hard "Never". The triggers describe the *situation*
   that activates the tenet, and situations read better in positive
   form.
3. **Front-load the strongest trigger.** Claude Code applies a
   ~250-character cap on the `/skills` UI listing on top of the
   per-skill description budget. The first trigger in the list is the
   one that survives truncation. Put your best one first.

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

See `ET-0001-keeping-test-helpers-private.md` for a complete example.

### Naming a tenet file

Filename pattern: `ET-NNNN-<slug>.md`, where `<slug>` is **gerund-style
and describes the desired behaviour, not the prohibition**:

- ✅ `ET-0001-keeping-test-helpers-private.md`
- ❌ `ET-0001-no-lowering-access-modifiers-for-tests.md`

The slug also drives the generated skill directory name
(`skills/et-NNNN-<slug>/`), and skill names with positive,
action-shaped slugs auto-invoke more reliably than negated topic
labels. The `Rule` body keeps the hard "Never" — only the slug shifts.

## Runtime requirements

The SessionStart hook ([`hooks/inject-charter.cmd`](hooks/inject-charter.cmd))
is a polyglot Windows-`.cmd` / POSIX-shell script — the same file is
interpreted as a batch script by `cmd.exe` on Windows and as a shell
script by `/bin/sh` on Unix. **No external runtime dependency is
required**: only POSIX `sh` + `cat` (Unix) and `cmd.exe` + `type`
(Windows), both of which are part of every base system. The hook
emits a pre-built JSON payload (`build/charter.json`); JSON escaping
is done at build time, never at runtime.

All Python dev dependencies (PyYAML, pytest, ruff, mypy, types-pyyaml,
poethepoet) live under `[dependency-groups.dev]` in
[pyproject.toml](pyproject.toml) and are pinned to exact versions in
[uv.lock](uv.lock). They are **dev-only** — used by maintainers to
build, lint, type-check, and test tenets. Plugin consumers never run
Python; they receive only the pre-built `build/` and `skills/et-*/`
artifacts and the polyglot hook.

## Maintainer setup

The build/validation tooling uses [`uv`](https://docs.astral.sh/uv/)
for dependency management and [`poethepoet`](https://poethepoet.natn.io/)
as a cross-platform task runner. Both work identically on macOS,
Linux, and Windows.

### One-time setup

```bash
cd plugins/warden
uv sync          # Creates .venv and installs dev dependencies from uv.lock.
```

That's it. There is no Make / shell-script bootstrap. The same command
works in PowerShell, cmd.exe, bash, and zsh.

### Day-to-day tasks

Run any task with `uv run poe <task>`:

| Command                       | What it does                                                            |
|-------------------------------|-------------------------------------------------------------------------|
| `uv run poe validate`         | Validate every tenet against the spec                                   |
| `uv run poe build`            | Validate + regenerate `build/` artifacts and per-tenet skills           |
| `uv run poe build-check`      | Verify committed `build/` and `skills/et-*/` match `tenets/` (no writes)|
| `uv run poe test`             | Run the pytest suite                                                    |
| `uv run poe lint`             | Ruff lint check (no auto-fix)                                           |
| `uv run poe fix`              | Ruff lint with auto-fix                                                 |
| `uv run poe format`           | Ruff format (writes changes)                                            |
| `uv run poe format-check`     | Ruff format check (no writes)                                           |
| `uv run poe typecheck`        | MyPy strict type-check                                                  |
| `uv run poe check`            | format → lint → typecheck → validate → build → test (local gate)        |
| `uv run poe ci`               | format-check → lint → typecheck → validate → build-check → test (CI)    |

`uv run poe -h` lists every task. `uv run poe -h <task>` shows a single
task's help line.

### Code style

- **Line length:** 100 characters (configured in `pyproject.toml`).
- **Formatter:** Ruff (Black-compatible). Quote style is double quotes.
- **Type checking:** MyPy `strict = true` for `scripts/`. Tests are
  exempted from `disallow_untyped_defs` because pytest fixtures rely
  on duck typing.
- **Imports:** sorted by Ruff's `I` rule (isort-equivalent).

The `poe check` task runs the full local gate. CI should run `poe ci`,
which fails if formatting drift exists rather than auto-fixing it.

## Versioning

Warden follows SemVer from `0.1.0`.

- **Patch:** new tenet, copy edits, additive non-breaking metadata.
- **Minor:** new optional frontmatter field, new tier, new severity.
- **Major:** removed/renamed required frontmatter field or required
  body section — anything that breaks existing tenets.

The `since` field on each tenet records the plugin version in which
the tenet was introduced.
