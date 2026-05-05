---
name: et-0007-avoiding-any-and-unchecked-casts
description: Reach for `unknown` and validation, not `any` or unchecked `as`.
when_to_use: Use when typing a value as `any` to make a TypeScript error go away; writing `as Foo` to coerce a value of unknown shape into a domain type; turning untyped JSON / network / form data into a typed value without runtime validation; silencing a type error with `// @ts-ignore` or `// @ts-expect-error` to keep the build green.
user-invocable: false
paths: ["**/*.ts", "**/*.tsx"]
---
<!-- generated from tenets/ET-0007-avoiding-any-and-unchecked-casts.md by `uv run poe build` — do not edit by hand. -->

# ET-0007 — Reach for `unknown` and validation, not `any` or unchecked `as`

_Type: anti-pattern · Tier: 2_

## Rule

In TypeScript, do not use `any` and do not use `as`-casts to coerce a
value into a more specific type without a runtime check that proves
the cast is safe. Untyped external data (JSON responses, form input,
`localStorage`, message-bus payloads) enters as `unknown` and leaves
as a typed domain value only via a **validating parser** (Zod,
Valibot, ArkType, io-ts, a hand-written type guard). `// @ts-ignore`
and `// @ts-expect-error` are not allowed without a comment that
links to a tracked issue or names the third-party-library bug being
worked around. `as const`, `as` between *structurally compatible*
types, and `unknown` → narrowed-via-`typeof`/`instanceof` are not
violations.

## Why

`any` is contagious: every property access, call, or arithmetic
operation on an `any` value produces another `any`, so a single
`any` typed at the boundary silently turns the entire call graph
that consumes it into untyped JavaScript. The compiler reports zero
errors, the IDE offers no completions, and the first sign that
something is wrong is a `TypeError: cannot read property of
undefined` in production. `as Foo` without a runtime check is a
written promise to the compiler that the value has shape `Foo` —
when the promise is wrong (a renamed field upstream, an optional
turned required, a string where a number was expected), the type
system stops being a safety net and starts being a confidence
generator for crashes. A validating parser at the boundary is the
only place where the runtime and the type system agree.

## Bad Example

```ts
// BAD: `any` to silence the compiler. Every downstream `.x` is now untyped too.
async function loadUser(id: string) {
  const res: any = await fetch(`/api/users/${id}`).then((r) => r.json());
  return { name: res.name, plan: res.subscription.plan };
}

// BAD: `as User` is a lie — nothing checks the shape.
function parseUser(raw: unknown): User {
  return raw as User;
}

// BAD: ts-ignore with no link, no reason, no plan to remove.
// @ts-ignore
config.unknownField = "hello";
```

## Good Example

```ts
// GOOD: untyped at the boundary, validated into a typed value, downstream is fully typed.
const UserSchema = z.object({
  name: z.string(),
  subscription: z.object({ plan: z.enum(["free", "pro"]) }),
});
type User = z.infer<typeof UserSchema>;

async function loadUser(id: string): Promise<{ name: string; plan: User["subscription"]["plan"] }> {
  const raw: unknown = await fetch(`/api/users/${id}`).then((r) => r.json());
  const user = UserSchema.parse(raw);     // throws on shape mismatch — boundary error
  return { name: user.name, plan: user.subscription.plan };
}

// GOOD: hand-written type guard for shapes a schema lib would be overkill for.
function isUser(value: unknown): value is User {
  return typeof value === "object"
      && value !== null
      && "name" in value
      && typeof (value as { name: unknown }).name === "string";
}

// GOOD: ts-expect-error with a tracked link and an expiry condition.
// @ts-expect-error — upstream type bug, see github.com/vendor/lib/issues/1234, remove when v3.0.0 lands
config.unknownField = "hello";
```

## Exceptions

- **`as const`** is not a coercion — it narrows literal types. Always
  allowed.
- **`as` between structurally compatible types** (e.g. widening to a
  supertype, narrowing within a tagged union after a discriminator
  check) is fine; the compiler verifies the relationship.
- **Type predicates / type guards** (`function isX(v: unknown): v is X`)
  are the canonical way to narrow `unknown` and are required by
  several APIs (e.g. `Array.prototype.filter`).
- **Test fixtures** that build deeply-nested partial objects MAY use a
  helper like `as unknown as Foo` for the test arrangement, provided
  the helper is colocated with the tests and never imported into
  production code.
- **Third-party type bugs** are a real failure mode — `// @ts-expect-error`
  with a comment that (1) names the library, (2) links to the
  upstream issue, and (3) describes the trigger for removal is
  acceptable until the bug is fixed.

## Rationalizations

- **"TypeScript is too strict here, the value really is a `Foo`."**
  If you know the shape, encode the proof: a type guard, a schema
  parse, or a constructor on the domain type. A bare `as Foo`
  records your belief, not the proof. The day the upstream shape
  changes, your belief silently becomes wrong.
- **"It's just JSON from our own API, we control it."**
  You control today's deploy. The next deploy renames a field, the
  rolling update has both versions live for ten minutes, and a
  validation parser turns a 1% error rate into a clear log line —
  versus an `as` that turns it into a stack-traceless `undefined`
  bug.
- **"`unknown` is annoying, I have to write a guard."**
  That is the feature, not the bug. The annoyance is exactly the
  amount of work proportional to the risk you are taking; the
  guard is also the place where tests live and the place where
  future type changes are noticed.
- **"`@ts-ignore` is just for now — I'll remove it after the deploy."**
  Modifier widenings and type-suppressions almost never revert; the
  next contributor sees the comment and assumes it is load-bearing.
  Use `@ts-expect-error` instead — if the underlying error goes
  away, the directive itself fails and forces removal.
