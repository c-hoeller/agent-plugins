---
id: ET-0011
title: Inject time, randomness, and IO; never read them ambiently
type: anti-pattern
tier: 1
applies-to: any
since: 0.2.0
triggers:
  - calling `DateTime.UtcNow` / `Date.now()` / `datetime.now()` inside business logic
  - calling `Random` / `Math.random()` / `random.random()` / `Guid.NewGuid()` to make a decision domain code depends on
  - needing to wait, sleep, or freeze the clock in a test because production code reads the wall clock
  - reviewing a diff where logic branches on "now" or on a freshly-generated ID without taking either as a parameter
tags: [testability, determinism, dependencies, time, randomness]
related: [ET-0009, ET-0010]
---

## Rule

Wall-clock time, monotonic time, randomness, UUID/ID generation,
environment lookups, and filesystem / network access are
**dependencies**, not primitives. Any unit whose behavior depends on
them takes them as a parameter or constructor argument: `IClock`,
`IRandom`, `IIdGenerator`, `IConfigProvider`, etc. Direct calls to
`DateTime.Now` / `DateTime.UtcNow`, `Date.now()`, `datetime.now()` /
`time.time()`, `Random` / `Math.random()` / `random.*`,
`Guid.NewGuid()` / `crypto.randomUUID()`, `os.environ` /
`process.env`, and direct `File.ReadAll*` / `fs.readFileSync` /
`open()` are reserved for the composition root and the thin adapters
that implement those interfaces. Linters can ban specific APIs in
specific directories; this tenet covers the broader judgement of
*what is a system dependency in this codebase*.

## Why

Code that reads the wall clock or rolls a random number directly is
non-deterministic by construction: tests must either wait, freeze
time globally, or accept flakiness — and global time-freezing leaks
across tests in the same process (see ET-0014), making the suite
order-dependent. Every direct call to a system primitive is a hidden
input the type system does not record and the test cannot control,
so the test ends up asserting "code ran without throwing" rather
than "code produced the right result for these inputs". Once the
dependency is injected, the test passes a fixed clock, a deterministic
generator, or an in-memory filesystem; production wiring is one line
in the composition root.

## Bad Example

```python
# BAD: reads the wall clock and a random ID inline; test must monkey-patch both.
def issue_token(user_id: str) -> Token:
    return Token(
        id=str(uuid.uuid4()),
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
```

```csharp
// BAD: business rule branches on DateTime.UtcNow; the test can't make "today" deterministic.
public bool IsTrialExpired(Account account)
{
    return DateTime.UtcNow - account.CreatedAt > TimeSpan.FromDays(14);
}
```

```ts
// BAD: reads env at decision time; toggling the flag requires re-importing the module.
export function pricingFor(plan: Plan): number {
  const promo = process.env.PROMO_RATE;       // hidden input
  return promo ? plan.base * Number(promo) : plan.base;
}
```

## Good Example

```python
# GOOD: clock + ID generator are arguments. Tests pass fakes; production passes the real ones.
def issue_token(user_id: str, *, clock: Clock, ids: IdGenerator) -> Token:
    return Token(
        id=ids.new(),
        user_id=user_id,
        expires_at=clock.now() + timedelta(hours=1),
    )
```

```csharp
// GOOD: IClock injected; tests use a FakeClock that advances under test control.
public bool IsTrialExpired(Account account, IClock clock)
{
    return clock.UtcNow - account.CreatedAt > TimeSpan.FromDays(14);
}
```

```ts
// GOOD: configuration arrives as a parsed value (see ET-0012); the function is now a pure decision.
export function pricingFor(plan: Plan, config: PricingConfig): number {
  return config.promoRate !== undefined ? plan.base * config.promoRate : plan.base;
}
```

## Exceptions

- **Composition-root code** (program `main`, DI container setup,
  top-level CLI entry, framework startup hooks) is exactly where
  `SystemClock`, `CryptoRandom`, real filesystem adapters, and
  environment lookups are constructed. The exception applies only to
  the wiring code, not to "any code that runs near `main`".
- **Adapters that implement an injected interface** (the concrete
  `SystemClock` whose only job is `() => DateTime.UtcNow`, the
  `EnvConfigSource` whose only job is to read `process.env`) are
  expected to call the system primitive directly. Their job is to
  expose it through a substitutable interface.
- **Logging timestamps and metric timestamps** that are emitted by a
  logging/metrics framework whose API does not accept a clock
  parameter are acceptable — the framework owns the clock. Domain
  decisions still go through the injected clock.
- **One-shot scripts** with no test suite and no expected lifetime
  beyond a single run MAY read primitives directly. The exception
  expires the moment a test is written or the script is reused.

## Rationalizations

- **"It's just one `Date.now()`, freezing time in tests is easy."**
  Easy until the second test in the same process freezes a different
  time, or a test that runs in parallel reads the frozen value, or a
  library you depend on caches the time at import. Injection is local;
  global freezes are not.
- **"A random UUID is fine, the test doesn't need to assert on it."**
  Until the bug is "two records collided" and the only way to
  reproduce it is to replay the exact sequence of UUIDs that were
  generated. A deterministic generator under test is a one-line
  fixture; reverse-engineering a non-deterministic one is a day.
- **"`process.env` is configuration, not a system dependency."** It
  *is* a system dependency: its value is set outside the process, can
  change between runs, and is not part of the function's signature.
  Read it once at startup (see ET-0012), parse into a typed `Config`,
  and pass that — never read it inside business logic.
