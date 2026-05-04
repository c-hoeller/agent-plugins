---
id: ET-0001
title: Never lower access modifiers for testing
type: anti-pattern
severity: high
tier: 1
applies-to: any
triggers:
  - keeping a member private when a test wants to call it directly
  - testing a class whose helper is private/protected/internal and the test cannot reach it
  - deciding how to test logic that currently lives behind a `private`/`protected` modifier
  - reviewing a diff that widens an access modifier with a justification referencing tests
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.java"
  - "**/*.kt"
  - "**/*.kts"
  - "**/*.swift"
  - "**/*.cs"
  - "**/*.scala"
  - "**/*.dart"
tags: [testing, encapsulation, oop]
related: []
since: 0.1.0
---

## Rule

Never change a member's access modifier (e.g., `private` → `public`,
`protected` → `public`, `internal` → `public`) for the sole purpose of
making it accessible from a unit or integration test.

## Why

Lowering access modifiers leaks implementation details into the public
contract. Future refactors must preserve those internals or risk
breaking unrelated test suites, and consumers of the type may begin to
depend on members that were never intended to be public. The
encapsulation that drove the original modifier choice was a real design
decision; tests do not override it. If a private member is hard to
test, that is signal about the public surface — split the type, add a
collaborator, or test through observable behavior.

## Bad Example

```ts
// BAD: was `private`, made `public` so the test can call it directly.
export class OrderService {
  public calculateDiscount(order: Order): number {
    /* ... */
  }

  public price(order: Order): number {
    return order.total - this.calculateDiscount(order);
  }
}

// test
expect(new OrderService().calculateDiscount(order)).toBe(5);
```

## Good Example

```ts
// GOOD: keep the helper private, test through the public surface.
export class OrderService {
  private calculateDiscount(order: Order): number {
    /* ... */
  }

  public price(order: Order): number {
    return order.total - this.calculateDiscount(order);
  }
}

// test asserts on the observable result of price(), not the internal helper.
expect(new OrderService().price(order)).toBe(order.total - 5);
```

## Exceptions

- `internal` / package-private modifiers exposed to a *same-package*
  test are not a violation — the access scope is unchanged, the test
  is in the package the modifier already permits.
- Legacy code under active rewrite, where the public surface is being
  redesigned in the same PR. The widened modifier must be either
  removed or documented as part of the new public contract before the
  PR merges.
- Languages without true access modifiers (e.g., Python's leading
  underscore convention) — the convention is a hint, not a barrier,
  and tests may legitimately reach in. Prefer behavioral testing
  anyway.

## Rationalizations

- **"It's the only way to test this logic."** The logic is hard to
  reach because the public surface is missing it — that is design
  feedback, not a test problem. Add a public method that exposes the
  observable behaviour, or extract a collaborator the test can drive
  directly.
- **"Just for now — I'll re-narrow it after the test passes."**
  Modifier widenings rarely revert; the next reader sees `public` and
  depends on it. Use a same-package test (Java / Kotlin / Scala
  package-private, C# `internal` + `InternalsVisibleTo`) — the access
  scope is unchanged.
- **"It's only `protected`, not `public`."** `protected` still leaks
  the member to every subclass forever, including subclasses written
  by consumers. Same fix: test through observable behaviour or extract
  a collaborator.
- **"The class has a `@VisibleForTesting` annotation, so it's fine."**
  The annotation is a comment, not a barrier — production code can
  still call the widened member. Prefer language-level
  package-visibility where available; otherwise gate the member with a
  lint rule, not a tag.
