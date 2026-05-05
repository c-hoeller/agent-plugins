# CLAUDE.md — Warden Plugin

This file guides any Claude Code session that touches the Warden plugin.
The repo-root [`CLAUDE.md`](../../CLAUDE.md) still applies (English-only
artifacts); this file adds Warden-specific rules.

## What this plugin is

Warden ships **coding standards as Engineering Tenets** (`ET-NNNN`).
Each tenet is one binding rule with `Rule` / `Why` / `Bad Example` /
`Good Example` / `Exceptions` (and optional `Rationalizations`). Tenets
reach Claude Code sessions via two mechanisms:

- A small always-on **Charter** injected by a `SessionStart` hook —
  a polyglot wrapper [`hooks/run-hook.cmd`](hooks/run-hook.cmd) that
  dispatches to the extensionless bash script
  [`hooks/session-start`](hooks/session-start) — that lists every
  Tier 1 tenet by ID.
- One **auto-loadable skill per tenet** under
  [`skills/et-NNNN-<slug>/`](skills/), generated from the source
  tenet by [`scripts/build.py`](scripts/build.py). The skill loads
  when its description triggers — or its `paths:` glob — match the
  agent's work.

The build pipeline (`uv run poe build`) is the **single way** to
produce `build/` and the `et-*/` skills. They are committed so the
plugin is installable on `git clone`, but they must always match what
the build would emit. The CI gate `poe ci` enforces this via
[`scripts/build_check.py`](scripts/build_check.py).

## Hard rules

1. **Never edit `build/` or `skills/et-*/` by hand.** They are
   regenerated from `tenets/`. Edit the source tenet, then run
   `uv run poe build`.
2. **Always commit generated artifacts alongside the source change.**
   `poe ci` runs `build-check`, which fails if a tenet edit was made
   without re-building.
3. **The `lookup-tenet` skill under `skills/` is hand-authored** —
   `_clean_generated_skills` only touches `et-*` prefixed dirs, so it
   is safe, but check before deleting anything in `skills/`.
4. **No new runtime dependencies in the hook.** The wrapper
   `run-hook.cmd` is intentionally limited to POSIX `sh + cat` (Unix)
   and `cmd.exe` locating `bash.exe` from Git for Windows / MSYS2 /
   Cygwin (Windows). Anything beyond that breaks Windows installs.
   Windows users without bash see a silent `exit /b 0` — the plugin
   keeps working, just without the always-on Charter.
5. **Don't widen the always-on Charter.** It is intentionally headline-
   only. Per-tenet detail belongs in the generated skill, which
   auto-loads when relevant. The Charter must scale to 25+ tenets
   without breaking the 5,000-char ceiling enforced by
   `test_render_charter_size_stays_small_for_25_tenets`.

## Where things live

| Concern                              | File / dir                                            |
|--------------------------------------|-------------------------------------------------------|
| Tenet source (edit here)             | [`tenets/ET-NNNN-<slug>.md`](tenets/)                 |
| New-tenet starting point             | [`templates/ET-NNNN-template.md`](templates/ET-NNNN-template.md) |
| Parsing / validation / rendering     | [`scripts/lib/warden_lib.py`](scripts/lib/warden_lib.py) |
| Build entry point                    | [`scripts/build.py`](scripts/build.py)                |
| CI build-drift check                 | [`scripts/build.py --check`](scripts/build.py)        |
| Standalone validation                | [`scripts/validate.py`](scripts/validate.py)          |
| SessionStart hook wrapper (polyglot) | [`hooks/run-hook.cmd`](hooks/run-hook.cmd)            |
| SessionStart hook payload (bash)     | [`hooks/session-start`](hooks/session-start)          |
| Hook registration                    | [`hooks/hooks.json`](hooks/hooks.json)                |
| Generated Charter (committed)        | [`build/charter.md`](build/charter.md), [`build/charter.json`](build/charter.json) |
| Generated index (committed)          | [`build/index.json`](build/index.json)                |
| Charter preamble source              | [`templates/charter-preamble.md`](templates/charter-preamble.md) |
| Hand-authored lookup skill           | [`skills/lookup-tenet/SKILL.md`](skills/lookup-tenet/SKILL.md) |
| Generated per-tenet skills           | [`skills/et-NNNN-<slug>/SKILL.md`](skills/)           |

## Authoring a tenet — short version

1. `cp templates/ET-NNNN-template.md tenets/ET-<next>-<gerund-slug>.md`.
2. Fill in the template (its inline comments document every field).
   Slug is gerund / positive (`keeping-test-helpers-private`), not
   negation (`no-lowering-…`), even when the `Rule` body is a hard
   "Never". See README "Naming a tenet file" + "Writing good triggers".
3. `uv run poe build` to regenerate `build/` and `skills/et-*/`.
4. `uv run poe ci` before committing — runs format-check, lint, mypy
   strict, validate, build-check, and the full pytest suite.
5. Commit the source tenet **and** all regenerated artifacts in the
   same commit.

## Tenet design rules (apply when adding/editing tenets)

- **Tenets only cover what linters/analyzers cannot.** Before adding a
  tenet, check whether a robust static-analysis rule already enforces
  the same constraint (e.g. `ruff B006` for mutable default arguments,
  `gitleaks` for secrets, Roslyn `CA2000` for missing `Dispose`). If a
  linter handles it deterministically, **do not add a tenet** — the
  linter is faster, cheaper, and runs without an agent in the loop.
  Warden's value is judgement-heavy rules and rules that the agent
  should follow at *generation* time, not patterns a CI gate can flag
  post-hoc. When a linter handles the rule *partially*, the tenet must
  cover the judgement gap, not the pattern the linter already catches.
- **Triggers describe situations, not topics.** ✅ "keeping a member
  private when a test wants to call it directly" — ❌ "encapsulation".
- **Triggers use positive framing**, even when the Rule is negative.
  Situations read more naturally in positive form ("when about to X")
  than as negated ones ("never X"); the Rule body keeps the hard
  "Never". Skill descriptions read as "when to use" prose; the
  imperative belongs in the Rule.
- **Front-load the strongest trigger** — skill `description` is capped
  at 1,536 chars in the global skill listing (per [Claude Code Skills
  docs](https://code.claude.com/docs/en/skills)); the first trigger is
  what survives any truncation when the shared budget tightens.
- **Use `paths:` to scope language-specific tenets** — it's more
  deterministic than description matching and frees the global
  description budget. Omit `paths:` only for genuinely
  language-agnostic tenets.
- **Exceptions are scoped, not blanket waivers.** Each `Exceptions`
  bullet must name the language / framework / situation it covers.
- **Add `Rationalizations` only when the tenet faces predictable
  loophole arguments.** Empty rows are noise. Bullets, not tables —
  long inline tables fail markdown-lint's column-style check.

## Code style (Python tooling)

- Line length 100, ruff format (Black-compatible), double quotes.
- mypy `strict = true` for `scripts/`. Tests are exempted from
  `disallow_untyped_defs` because pytest fixtures rely on duck typing.
- Imports sorted by ruff's `I` rule.
- Don't run `pip install` directly. The project is uv-managed; use
  `uv sync` once and `uv run poe <task>` thereafter.

## Things to know that aren't obvious from the code

- **The polyglot wrapper is fragile by design.** Don't reformat
  [`run-hook.cmd`](hooks/run-hook.cmd) — the `:<<'CMDBLOCK'` heredoc,
  `@echo off` line, the `CMDBLOCK` marker position, and the trailing
  `#…` comment on the `exec bash` line are all load-bearing. The file
  is pinned to CRLF in `.gitattributes`: `cmd.exe` mangles LF-only
  `.cmd` scripts (echo-off doesn't take effect), while the sh side
  tolerates the trailing `\r` on each line because the heredoc
  terminator is matched with-`\r`-on-both-ends and the exec line's
  trailing comment absorbs the carriage return before it can corrupt
  the path argument. If you change anything there, manually test on
  both `/bin/sh` and `cmd.exe`.
- **The actual hook payload lives in [`session-start`](hooks/session-start),
  not the wrapper.** The wrapper only finds bash and dispatches; all
  real logic (reading `build/charter.json`, the missing-payload
  warning) belongs in the bash script. The wrapper is reusable for
  future hooks via the `script-name` argument.
- **JSON escaping is done at build time, not at runtime.** The hook
  must `cat`/`type` the file verbatim. If you ever consider a
  templated runtime JSON, stop — the whole point of the build-time
  payload is that no JSON tooling is required at session start.
- **The IDE may report mypy import errors for `lib` / `yaml`.** That's
  the IDE's mypy running outside the venv; the configured `mypy_path`
  (`scripts/`) and `types-pyyaml` are present in `.venv/`. `uv run poe
  typecheck` is the source of truth.
- **`SessionStart` matcher is `startup|resume|clear|compact`.** Don't
  drop `compact` — without it the Charter is not re-injected after
  auto-compaction in long sessions.
