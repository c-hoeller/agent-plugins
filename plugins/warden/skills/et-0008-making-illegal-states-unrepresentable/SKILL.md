---
name: et-0008-making-illegal-states-unrepresentable
description: Make illegal states unrepresentable.
when_to_use: Use when introducing a new type whose fields can combine into a state that has no domain meaning; modeling status with a free-form string and optional fields where some combinations are nonsense; reviewing a diff that adds a runtime check "if X is set then Y must also be set" on a struct/class/interface; deciding between a flat shape with multiple optionals and a discriminated union / sum type / sealed hierarchy.
user-invocable: false
---
<!-- generated from tenets/ET-0008-making-illegal-states-unrepresentable.md by `uv run poe build` — do not edit by hand. -->

# ET-0008 — Make illegal states unrepresentable

_Type: best-practice · Tier: 1_

## Rule

When designing a type that holds state, choose shapes such that
nonsensical combinations of values cannot be constructed. Prefer
discriminated unions / sum types / sealed class hierarchies,
constrained value objects (`NonEmptyList<T>`, `PositiveInt`,
`EmailAddress`), and fields whose presence is enforced by their type,
over flat records with multiple optionals coordinated by runtime
checks. If a domain rule says "field B is meaningful only when status
is `Failed`", encode that — `Failed { error: Error }` and
`Succeeded { value: T }` as separate variants — instead of a flat
`{ status, error?, value? }` whose validity lives in code comments and
defensive `if`s.

## Why

A type whose invariants live as runtime guards is one careless caller
away from a corrupted instance, and once an illegal state exists in
memory every consumer must defensively branch on it even though the
combination is meaningless. The bug is observed at the screen — a
spinner that shows next to an error message — not at the construction
site that produced the state, and reproduction requires reconstructing
the wrong path the data took. Modeling the state as a discriminated
union moves the error from "callers must remember not to" into
"the compiler refuses to compile it"; the invariant is enforced once,
in the type, and every match/switch is forced to handle each variant.

## Bad Example

```ts
// BAD: four flags, only some combinations are valid; consumers re-check forever.
type RequestState = {
  isLoading: boolean;
  data?: Response;
  error?: Error;
  isStale: boolean;
};

function render(s: RequestState) {
  if (s.isLoading && s.error) { /* impossible per spec, but type-allowed */ }
  if (s.data && s.error)      { /* same */ }
  // every consumer carries the same defensive logic.
}
```

```csharp
// BAD: status is a string; payload fields coexist with error fields.
public sealed class JobResult
{
    public string Status { get; init; } = "";   // "running" | "succeeded" | "failed"
    public byte[]? Output { get; init; }
    public string? ErrorMessage { get; init; }
    public int? ExitCode { get; init; }
}
```

## Good Example

```ts
// GOOD: discriminated union. The compiler refuses impossible combinations.
type RequestState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; data: Response; stale: boolean }
  | { kind: "failed"; error: Error };

function render(s: RequestState) {
  switch (s.kind) {
    case "idle":    return null;
    case "loading": return <Spinner/>;
    case "loaded":  return <View data={s.data} stale={s.stale}/>;
    case "failed":  return <Error err={s.error}/>;
  }
}
```

```csharp
// GOOD: sealed hierarchy / record-with-pattern-matching makes each variant a distinct shape.
public abstract record JobResult
{
    public sealed record Running                              : JobResult;
    public sealed record Succeeded(byte[] Output)             : JobResult;
    public sealed record Failed(string ErrorMessage, int ExitCode) : JobResult;
}
```

## Exceptions

- **Languages without sum types** (older Java, Go without generics
  exhaustiveness, plain JavaScript) MAY fall back to a tagged shape
  plus a constructor / factory function that is the *only* way to
  build the type. The constructor enforces the invariant; consumers
  still match on the discriminator.
- **Persistence shapes** (database rows, JSON wire formats) sometimes
  must be flat for storage or backwards-compatibility reasons. Treat
  them as boundary types: parse into a domain type with the proper
  variant structure at the boundary (see ET-0003), and never let the
  flat shape leak into business logic.
- **Genuinely orthogonal flags** that can independently combine
  meaningfully (e.g. `{ isAdmin, isOnline }` where all four
  combinations are real states) are correctly modeled as flat
  booleans. The test is whether every combination is reachable in
  the domain — not whether the type system happens to allow it.

## Rationalizations

- **"It's just a few extra fields, callers can check."** Every caller
  *will* have to check, forever, and the next contributor will forget
  one. The invariant either lives in the type (checked once, by the
  compiler) or in the prose (checked never, by anyone).
- **"A discriminated union is more code."** It is more code at the
  declaration site and less code at every consumer; consumers
  outnumber declarations 10-to-1. The aggregate cost is lower, and
  the failure mode (a missing variant in a switch) surfaces at compile
  time rather than as a blank screen.
- **"We'll add a validator on the constructor."** A constructor
  validator catches the wrong combination at runtime, not at compile
  time, and only at the construction site — every later mutation can
  re-introduce the illegal state. Make the shape itself refuse the
  combination.
