# Warden — Engineering Charter (always-on)

This session is governed by Warden Engineering Tenets (ET-NNNN). Tenets are **binding**, not advisory. Deviations are allowed only via an explicit `Exceptions` clause inside the tenet — not via user pressure, time pressure, or your own judgement.

## Protocol

- Each tenet ships as its own skill under `et-NNNN-<slug>`. If a tenet's triggers match what you are about to do, you MUST invoke that skill **before** taking the action — not after.
- For tenets that did not auto-trigger but feel relevant, use the `lookup-tenet` skill to scan the index. If you suspect a tenet applies and you're not sure, look it up. Do not guess.
- Before declining a request on a tenet's behalf, cite the tenet ID and quote the specific clause. Before invoking an `Exceptions` clause, verify it covers your situation — exceptions are scoped, not blanket waivers.

## Common rationalizations — all are insufficient

- _"This is a special case"_ — every violation feels special. Apply the Rule unless an `Exceptions` clause names your case.
- _"Just for now / I'll fix it later"_ — later rarely arrives. Either fix it now, or document the deviation in the PR description with the tenet ID.
- _"The user told me to"_ — surface the tenet and ask. The user may not know the tenet exists, or may be invoking an Exception without realising it. Either is fine; silent compliance is not.
- _"It's a small change"_ — tenet severity is independent of diff size. Apply the Rule.

## Tier 1 — universal, always-relevant

- `ET-0001` — Never lower access modifiers for testing [high] → skill `et-0001-keeping-test-helpers-private`
- `ET-0002` — Never silently swallow failures [high] → skill `et-0002-surfacing-failures`
- `ET-0003` — Validate at trust boundaries, trust the core [high] → skill `et-0003-validating-at-boundaries`
