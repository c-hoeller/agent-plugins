# Contributing to Warden

This file documents the build, validation, and CI tooling for
maintainers. Plugin **consumers** never need to read this — they get
the pre-built `build/` and `skills/et-*/` artifacts by cloning the
repo, and the `SessionStart` hook needs no runtime dependency beyond
what every base system already ships (`sh + cat` or `cmd.exe + type`).

For tenet authoring (template, frontmatter, triggers, paths, naming),
see [README.md](README.md#authoring-a-tenet).

## Dev dependencies

All Python dev dependencies (PyYAML, pytest, ruff, mypy, types-pyyaml,
poethepoet) live under `[dependency-groups.dev]` in
[pyproject.toml](pyproject.toml) and are pinned to exact versions in
[uv.lock](uv.lock). They are dev-only — used by maintainers to build,
lint, type-check, and test tenets.

## One-time setup

The build/validation tooling uses [`uv`](https://docs.astral.sh/uv/)
for dependency management and [`poethepoet`](https://poethepoet.natn.io/)
as a cross-platform task runner. Both work identically on macOS,
Linux, and Windows.

```bash
cd plugins/warden
uv sync          # Creates .venv and installs dev dependencies from uv.lock.
```

That's it. There is no Make / shell-script bootstrap. The same command
works in PowerShell, cmd.exe, bash, and zsh.

### Optional: pre-commit hook

To run `uv run poe ci` automatically before every commit that touches
`plugins/warden/**` (catches build drift / lint / mypy / test
regressions before they reach CI):

```bash
bash plugins/warden/scripts/install-hooks.sh
```

The hook is local to your clone — re-run after a fresh clone. Skips
itself when no Warden files are staged, and degrades to a no-op when
`uv` is not on PATH. Bypass once with `git commit --no-verify`.

## Day-to-day tasks

Run any task with `uv run poe <task>`:

| Command                       | What it does                                                            |
|-------------------------------|-------------------------------------------------------------------------|
| `uv run poe validate`         | Validate every tenet against the spec                                   |
| `uv run poe build`            | Validate + regenerate `build/` artifacts and per-tenet skills           |
| `uv run poe build-check`      | Verify committed `build/` and `skills/et-*/` match `tenets/` (`build.py --check`, no writes)|
| `uv run poe test`             | Run the pytest suite                                                    |
| `uv run poe lint`             | Ruff lint check (no auto-fix)                                           |
| `uv run poe fix`              | Ruff lint with auto-fix                                                 |
| `uv run poe format`           | Ruff format (writes changes)                                            |
| `uv run poe format-check`     | Ruff format check (no writes)                                           |
| `uv run poe typecheck`        | MyPy strict type-check                                                  |
| `uv run poe check`            | format → lint → typecheck → validate → build → test (local gate)       |
| `uv run poe ci`               | format-check → lint → typecheck → validate → build-check → test (CI)   |

`uv run poe -h` lists every task. `uv run poe -h <task>` shows a
single task's help line.

## Authoring workflow

1. Copy the template, edit the new tenet file (see
   [README.md](README.md#authoring-a-tenet) for field semantics).
2. `uv run poe build` to regenerate `build/` and the per-tenet skill.
3. `uv run poe ci` before committing — runs format-check, lint, mypy
   strict, validate, build-check, and the full pytest suite.
4. Commit the source tenet **and** all regenerated artifacts in the
   same commit.

## Code style

- **Line length:** 100 characters (configured in `pyproject.toml`).
- **Formatter:** Ruff (Black-compatible). Quote style is double quotes.
- **Type checking:** MyPy `strict = true` for `scripts/`. Tests are
  exempted from `disallow_untyped_defs` because pytest fixtures rely
  on duck typing.
- **Imports:** sorted by Ruff's `I` rule (isort-equivalent).

The `poe check` task runs the full local gate. CI runs `poe ci`,
which fails on formatting drift rather than auto-fixing.

## CI

GitHub Actions runs [`.github/workflows/warden-ci.yml`](../../.github/workflows/warden-ci.yml)
on every push to `main` and every pull request that touches
`plugins/warden/**`. The workflow runs `poe ci` on a matrix of
**`macos-latest`** and **`windows-latest`** — both supported plugin
runtime targets. The Windows runner is what actually exercises the
`cmd.exe` branch of [`hooks/run-hook.cmd`](hooks/run-hook.cmd) (which
locates `bash.exe` and invokes [`hooks/session-start`](hooks/session-start));
the macOS runner exercises the `/bin/sh` branch (which heredoc-skips
the cmd block and exec-bashes `session-start` directly). A polyglot-
wrapper edit that breaks one branch fails CI before any user session
sees it.

Linux is omitted from the matrix intentionally — add it back if a
Linux user ever surfaces. The hook is plain POSIX shell on the Unix
side, so a Linux runner would not catch anything macOS does not
already catch.

## Behavior tests

Behavior tests under [`tests/skill-triggering/`](tests/skill-triggering/)
verify that each generated `et-*` skill actually auto-loads in
response to realistic prompts. They invoke the `claude` CLI and cost
real API calls, so they are **not** part of `poe ci`. Run manually
before releasing a tenet whose `description`, `triggers`, or `paths`
changed materially:

```bash
uv run poe behavior-test
```

See [`tests/skill-triggering/README.md`](tests/skill-triggering/README.md)
for the harness, scenario layout, and pressure-variant convention.
