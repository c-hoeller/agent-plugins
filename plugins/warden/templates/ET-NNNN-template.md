---
# Replace NNNN with the next free number (4 digits, zero-padded). The id
# MUST match the filename prefix; validation enforces this.
id: ET-NNNN

# One-line imperative title (≤ 80 chars). The Rule body keeps the hard
# "Never"/"Always" — title can match.
title: <one-sentence imperative title>

# best-practice | anti-pattern
type: anti-pattern

# critical | high | medium | low
severity: high

# 1 = universal, always-relevant; listed in the always-on Charter index.
# 2 = language- or framework-specific; not listed in Charter, auto-loads
#     via skill triggers (and optionally `paths:`) when relevant code is
#     touched.
tier: 1

# any | "<key>: <name>" | { <key>: <name> } | list of the above
# <key> ∈ { language, framework }
# Use "any" only for genuinely universal tenets. Anything language- or
# framework-specific should say so here AND scope via `paths:` below.
applies-to: any

# Plugin SemVer in which this tenet was introduced. Bump only when the
# tenet is added or substantially rewritten — minor wording edits do not
# bump `since`.
since: 0.1.0

# 3–5 short, action-shaped phrases describing situations where this tenet
# should auto-load. They become the generated skill's `description`,
# which Claude Code matches against to auto-invoke the skill.
#
# Three rules (see README "Writing good triggers"):
#   1. Action-shaped, not topic-labeled.
#      ✅ "keeping a member private when a test wants to call it directly"
#      ❌ "encapsulation in tests"
#   2. Positive framing, even when the Rule is negative ("Never X").
#      Negative directives have ~23 % lower compliance in 2026 benchmarks.
#   3. Front-load the strongest trigger — Claude Code applies a 250-char
#      cap on the `/skills` UI listing in addition to the per-skill
#      description budget. The first trigger survives truncation.
triggers:
  - <the situation that most directly activates this tenet>
  - <a different angle — the user's framing or the agent's planned action>
  - <the diff-review angle: "reviewing a diff that …">

# OPTIONAL: glob patterns scoping auto-invocation to specific files.
# Use this for language- or framework-specific tenets — it's more
# deterministic than description matching and frees the global skill-
# description budget for tenets that can't apply to the current file.
# Omit entirely for language-agnostic tenets (naming, security, commit
# hygiene, etc.).
#
# paths:
#   - "**/*.ts"
#   - "**/*.tsx"

# OPTIONAL: short topic labels for browse / grep via lookup-tenet.
tags: []

# OPTIONAL: cross-references to other tenets that interact with this one
# (e.g. shared exceptions, layered rules). Validation flags broken refs
# and self-references.
related: []
---

## Rule

<One paragraph. Imperative. Hard "Never"/"Always" framing is fine — the
slug and triggers handle positive framing. Be specific about what is
forbidden / required and what is not.>

## Why

<Root cause and consequence. Explain *why* the rule exists in terms of
real failure modes, not abstract principles. 2–4 sentences.>

## Bad Example

```ts
// BAD: <one-line summary of what makes this bad>
// Replace this fenced block with the smallest example that exhibits
// the violation. Match the language of `applies-to` where possible;
// for `applies-to: any`, pick the language that shows the issue
// most clearly.
```

## Good Example

```ts
// GOOD: <one-line summary of the fix>
// Same shape as Bad Example, with the violation removed. Avoid
// changing unrelated style — the diff between Bad and Good should be
// minimal so the rule is obvious.
```

## Exceptions

<Bulleted list of specific situations where the Rule legitimately does
not apply. Each exception MUST be scoped (a class of situations), not a
blanket waiver. If there are no real exceptions, write a single bullet
saying so — do not omit the section.>

- <scoped exception 1 — name the language/framework/situation>
- <scoped exception 2>

## Rationalizations

<OPTIONAL section. Use it for tenets that face predictable loophole
arguments. Each row should pair the excuse with the *real* underlying
situation and the correct path forward. Drop the section entirely if
the tenet has no recurring rationalizations — empty rows are noise.>

- **"<the excuse, in the agent's or user's voice>"** — <the reality
  underneath the excuse, in one sentence>. <The correct action.>
- **"<another excuse>"** — <reality>. <correct action>.
