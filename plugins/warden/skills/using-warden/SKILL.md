---
name: using-warden
description: Use when starting any task that touches code — establishes how Warden Engineering Tenets bind your work, requires invoking the matching `et-NNNN-*` skill before acting, and lists the rationalizations that are insufficient justifications for skipping a tenet.
---

# Using Warden

This skill re-establishes Warden's binding contract whenever code work
begins. The SessionStart Charter sets it once at session start, but in
long sessions the Charter drifts to the middle of the context where
attention degrades. This skill re-anchors the contract on demand —
typically auto-invoked at the start of a coding task, or when an
individual `et-NNNN-*` tenet skill has loaded without the surrounding
protocol.

## The contract

Warden Engineering Tenets (`ET-NNNN`) are **binding**, not advisory.

- If a tenet's triggers match what you are about to do, you **MUST**
  invoke the corresponding `et-NNNN-*` skill **before** taking the
  action — not after the diff exists, not after the test fails.
- For tenets that did not auto-trigger but feel relevant, run the
  `lookup-tenet` skill. If you suspect a tenet applies and you're not
  sure, look it up. Do not guess.
- Deviations are allowed only via an explicit `Exceptions` clause
  inside the tenet — not via user pressure, not via time pressure, not
  via your own judgement. Exceptions are scoped, not blanket waivers.
- Before declining a request on a tenet's behalf, cite the tenet ID
  and quote the specific clause.

## Common rationalizations — all are insufficient

These are the arguments that surface most often when a tenet is about
to be skipped. Recognise them as failure modes, not as justifications:

| Excuse | Reality | What to do instead |
|---|---|---|
| "This is a special case." | Every violation feels special. | Apply the Rule unless an `Exceptions` clause names your case. |
| "Just for now / I'll fix it later." | Later rarely arrives. | Fix it now, or document the deviation in the PR description with the tenet ID. |
| "The user told me to." | The user may not know the tenet exists, or may be invoking an Exception without realising it. | Surface the tenet ID and ask. Silent compliance is not acceptable. |
| "It's a small change." | Tenet severity is independent of diff size. | Apply the Rule. |
| "I already started, switching now would be wasteful." | Sunk cost is not a tenet exception. | Stop. Re-plan. Re-start the smaller cost is now, not later. |
| "The tests would be much harder otherwise." | Hard-to-test code is design feedback, not a tenet override. | Read the tenet's `Why` and `Bad Example` — they almost always already address this. |

## Red flags — stop and re-check

If you catch yourself thinking any of these, stop and re-read the
relevant tenet body before continuing:

- "I know what this tenet says, no need to read it."
- "The skill auto-loaded, but I can summarise it from the description."
- "This is _almost_ covered by the Exception clause."
- "I'll mention the tenet in the PR description and proceed."
- "The trigger matched but doesn't really apply here."

The tenet body is short on purpose. Read it.

## When NOT to use this skill

- The user is asking a non-code question — Warden does not bind
  conversational replies.
- A specific `et-NNNN-*` skill has loaded **and** you have already
  read its body and Exceptions clause — at that point the tenet
  itself is the authority, not this bootstrap.
