# Skill-Triggering Behavior Tests

These tests measure whether Warden tenet skills **actually fire** in response
to realistic prompts — the empirical question that pytest-level frontmatter
checks cannot answer.

Each test runs `claude -p` headless with a written prompt, captures the
stream-JSON tool-use trail, and asserts the expected `et-NNNN-*` skill was
invoked. A passing run is evidence that:

- the skill's `description` keywords match the natural way users frame the
  problem
- the skill's `paths:` glob (if any) covers the file types the prompt
  implies
- the skill survives the global skill-description budget without being
  truncated past its triggering keywords

## Why these are not part of `poe ci`

Behavior tests cost real Claude API calls. Running the full suite hits the
API once per scenario, so they belong in a manual / pre-release / weekly
gate — not the per-commit one. Running them on every push would cost money
and slow CI without proportional benefit.

Use `uv run poe behavior-test` to run the full suite locally when you've
materially changed a tenet's `description`, `triggers`, or `paths:`.

## Pass/fail tests vs. measurements

Two distinct concepts live under this directory:

- **`scenarios/<skill>/positive/*.txt`** — pass/fail behavior tests.
  Run via `run-test.sh` / `run-suite.sh`. The expected skill MUST fire
  or the test fails. Use these to pin a skill's auto-load contract
  once you have evidence it works.
- **`measurements/<measurement-name>/<class>/*.txt`** — data-collection
  runs. Run via `measure.sh <measurement-name>`. The script records
  every Skill invocation per prompt and emits a markdown report under
  `measurements/<name>/report.md` (gitignored). Use these to *decide*
  whether a description tweak / force-load mechanism / reorganisation
  is justified, before pinning anything as a pass/fail test.

The first measurement in the tree is `using-warden`, which collects
empirical data on whether the bootstrap skill auto-loads in vague,
competing-with-et, and non-code prompts. Run with:

```bash
uv run poe behavior-measure using-warden
```

## Layout

```text
tests/skill-triggering/
├── README.md                — this file
├── run-test.sh              — generic harness: one prompt, one skill, one verdict
├── run-suite.sh             — discovers and runs every scenario
└── scenarios/
    └── <expected-skill-name>/
        └── positive/
            ├── 01-<scenario>.txt
            ├── 02-<scenario>.txt
            └── ...
```

Each scenario directory's name is the **exact skill name** the harness
expects to see invoked (e.g. `et-0001-keeping-test-helpers-private`).
Scenario `.txt` files contain the prompt body verbatim — no frontmatter,
no metadata.

## Authoring a scenario

Three pressure variants per tenet, by convention:

| File prefix         | Pressure type     | Example framing                                                          |
| ------------------- | ----------------- | ------------------------------------------------------------------------ |
| `01-direct`         | Plain ask         | "I want to test a private method. Can I make it public?"                 |
| `02-deadline`       | Time pressure     | "I'm shipping in 30min, need to test calculateDiscount, just make it public" |
| `03-authority`      | Social authority  | "My team lead said widening visibility for tests is fine here"           |

Add more variants only when you observe a *real* rationalization slipping
past the skill in actual sessions — those become regression tests.

## Running

Prerequisites: the `claude` CLI on `PATH`, the `warden` plugin enabled in
`/plugin`, and `jq` on `PATH` (used to filter stream-JSON).

```bash
# Run the full suite
uv run poe behavior-test

# Run one scenario directly
tests/skill-triggering/run-test.sh \
    et-0001-keeping-test-helpers-private \
    tests/skill-triggering/scenarios/et-0001-keeping-test-helpers-private/positive/01-direct.txt
```

Exit codes from `run-test.sh`:

- `0` — expected skill was invoked
- `1` — expected skill was not invoked (test failed)
- `2` — environment problem (claude / jq missing, prompt unreadable)
- `3` — claude exited non-zero or the run timed out

## Reading the output

The harness streams a one-line verdict per test:

```text
PASS  et-0001-keeping-test-helpers-private  positive/01-direct.txt
FAIL  et-0001-keeping-test-helpers-private  positive/02-deadline.txt
       expected `et-0001-keeping-test-helpers-private` in tool-use stream, none seen
```

`FAIL` lines do not stop the suite — every scenario runs, then the suite
exits non-zero if any scenario failed.

## Caveats

- **Non-determinism is real.** Skill auto-loading is a probabilistic
  signal-match, not a hard rule. A single FAIL on one scenario can be
  noise; consistent FAIL across runs is the actionable signal. The harness
  does not retry — re-run the suite if you suspect a flake.
- **Pressure scenarios are minimal.** They are not full red-team
  baselines; they are smoke tests that the most common framings still
  trigger. Real evidence of trigger drift requires observing actual user
  sessions and turning the rationalization into a new scenario file.
