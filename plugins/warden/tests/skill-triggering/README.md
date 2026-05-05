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

Add a measurement when you want empirical data on whether a skill
auto-loads in a particular class of prompts (e.g. competing with other
skills, vague code actions, non-code conversation). Drop prompts under
`measurements/<measurement-name>/<class>/*.txt` and run:

```bash
uv run poe behavior-measure <measurement-name>
```

## Layout

```text
tests/skill-triggering/
├── README.md                — this file
├── run-test.sh              — generic harness: one prompt, one skill, one verdict
├── run-suite.sh             — discovers and runs every scenario
└── scenarios/
    └── <expected-skill-name>/
        ├── positive/        — skill MUST fire
        │   ├── 01-<scenario>.txt
        │   └── ...
        └── negative/        — skill MUST NOT fire (false-positive guard)
            ├── 01-<scenario>.txt
            └── ...
```

Each scenario directory's name is the **exact skill name** the harness
expects to see invoked (e.g. `et-0001-keeping-test-helpers-private`).
Scenario `.txt` files contain the prompt body verbatim — no frontmatter,
no metadata.

## Authoring a scenario

### Positive variants — skill MUST fire

Three pressure variants per tenet, by convention:

- `01-direct` — Plain ask. *Example (ET-0001):* "I want to test a
  private method. Can I make it public?"
- `02-deadline` — Time pressure. *Example (ET-0001):* "I'm shipping in
  30min, need to test `calculateDiscount`, just make it public."
- `03-authority` — Social authority. *Example (ET-0001):* "My team lead
  said widening visibility for tests is fine here."

Add more variants only when you observe a *real* rationalization slipping
past the skill in actual sessions — those become regression tests.

### Negative variants — skill MUST NOT fire

Two **adjacent-topic** prompts per tenet that share vocabulary or domain
with the tenet but do *not* match any of its trigger situations. They
guard against an over-broad `description` or `paths:` glob that lights
up the skill on prompts where it adds no value.

- `01-<adjacent-topic>` — Same vocabulary, different situation.
  *Example (ET-0001):* "I'm making `routeByZip` properly private — show
  me the diff." (access modifier, but no test-widening tension.)
- `02-<adjacent-topic>` — Same domain, different action.
  *Example (ET-0001):* "Provide a fake `PaymentGateway` via constructor
  injection and assert HTTP 402." (testing, but no access-modifier
  question.)

A negative is well-designed when removing the tenet's `paths:` filter or
broadening one trigger phrase by one word would *break* the test —
i.e. the test is sensitive to the exact scope of the trigger language.

## Running

Prerequisites: the `claude` CLI on `PATH`, the `warden` plugin enabled in
`/plugin`, and `jq` on `PATH` (used to filter stream-JSON).

```bash
# Run the full suite (positives + negatives)
uv run poe behavior-test

# Run one positive scenario directly (default expectation: --expect-present)
tests/skill-triggering/run-test.sh \
    et-0001-keeping-test-helpers-private \
    tests/skill-triggering/scenarios/et-0001-keeping-test-helpers-private/positive/01-direct.txt

# Run one negative scenario directly
tests/skill-triggering/run-test.sh \
    et-0001-keeping-test-helpers-private \
    tests/skill-triggering/scenarios/et-0001-keeping-test-helpers-private/negative/01-private-encapsulation.txt \
    --expect-absent
```

Exit codes from `run-test.sh`:

- `0` — expectation matched (skill invoked under `--expect-present`, or
  skill absent under `--expect-absent`)
- `1` — expectation violated (skill not invoked when expected, or skill
  fired when it should not have)
- `2` — environment problem (claude / jq missing, prompt unreadable,
  unknown expectation flag)
- `3` — claude exited non-zero or the run timed out

`run-suite.sh` walks each `<skill>/positive/` directory with
`--expect-present` and each `<skill>/negative/` directory with
`--expect-absent`. Both classes count toward the suite's pass/fail total.

Scenarios run concurrently (default: 4 in parallel). Override via
`WARDEN_BEHAVIOR_TEST_PARALLEL=N`:

```bash
WARDEN_BEHAVIOR_TEST_PARALLEL=8 uv run poe behavior-test   # faster, may hit API rate limits
WARDEN_BEHAVIOR_TEST_PARALLEL=1 uv run poe behavior-test   # strictly sequential
```

Each test still streams its verdict line as it lands; the suite prints a
`Failures:` block listing every non-passing verdict, then a final tally.
Run order is no longer deterministic across the suite (it depends on which
worker finishes first), but every individual verdict line stays intact —
verdicts are written atomically per test.

## Reading the output

The harness streams a one-line verdict per test. Positive scenarios use
`PASS` / `FAIL`; negative scenarios use `PASS-NEG` / `FAIL-NEG` so
false-positive failures stand out at a glance:

```text
PASS      et-0001-keeping-test-helpers-private  positive/01-direct.txt
FAIL      et-0001-keeping-test-helpers-private  positive/02-deadline.txt
           expected `et-0001-keeping-test-helpers-private` in tool-use stream, none seen
PASS-NEG  et-0001-keeping-test-helpers-private  negative/01-private-encapsulation.txt
FAIL-NEG  et-0001-keeping-test-helpers-private  negative/02-mocking-dependency.txt
           expected `et-0001-keeping-test-helpers-private` to be absent, but it was invoked
```

Failures of either kind do not stop the suite — every scenario runs,
then the suite exits non-zero if any scenario failed.

## Caveats

- **Non-determinism is real.** Skill auto-loading is a probabilistic
  signal-match, not a hard rule. A single FAIL on one scenario can be
  noise; consistent FAIL across runs is the actionable signal. The harness
  does not retry — re-run the suite if you suspect a flake.
- **Negative tests are even more flake-prone.** A skill description can
  match a tangentially related prompt once in a blue moon without
  meaning the trigger language is broken. Treat a single `FAIL-NEG` as
  noise; reproduce it across runs before tightening the description or
  `paths:` glob.
- **Pressure scenarios are minimal.** They are not full red-team
  baselines; they are smoke tests that the most common framings still
  trigger. Real evidence of trigger drift requires observing actual user
  sessions and turning the rationalization into a new scenario file.
