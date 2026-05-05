---
name: et-0003-validating-at-boundaries
description: Use when adding a null/range/format check inside an internal helper that already receives a typed argument; deciding where to validate input that crosses a trust boundary (HTTP handler, CLI args, queue message, deserializer); reviewing a diff that scatters defensive guards through the call graph below the entry point; writing parsing/coercion logic that turns external data into a domain type.
user-invocable: false
---
<!-- generated from tenets/ET-0003-validating-at-boundaries.md by `uv run poe build` — do not edit by hand. -->

# ET-0003 — Validate at trust boundaries, trust the core

_Type: best-practice · Tier: 1_

## Rule

Validate untrusted input **once**, at the trust boundary where it enters
the system (HTTP handler, CLI parser, queue consumer, deserializer,
filesystem read, third-party API response). Inside the boundary, trust
your types: do not re-check arguments that the type system already
guarantees, do not add null-guards on parameters whose signature
forbids null, do not re-validate data that a constructor already
accepted. The boundary's job is to turn untrusted bytes into a
well-formed domain value; the core's job is to manipulate that value.

## Why

Defensive guards scattered through internal code create three durable
problems. First, they duplicate truth: when the rule changes (new
status enum value, new email format), every guard becomes a future bug
site, and the next reader cannot tell which check is the *real* one.
Second, they hide intent — a `if (user is null)` halfway down the call
stack tells the reader "this can be null", which silently widens the
contract; later refactors must preserve that nullability or risk the
"impossible" branch firing. Third, they paper over a missing
boundary: every internal guard is a symptom of validation that should
have happened at the edge, where the failure has a meaningful response
(HTTP 400, rejected message, parse error) instead of a generic
`ArgumentNullException` two layers deep.

## Bad Example

```csharp
// BAD: defensive null-checks on a parameter the type system already constrains.
public Money CalculateTotal(IReadOnlyList<LineItem> items)
{
    if (items == null) throw new ArgumentNullException(nameof(items)); // can't be null — non-nullable reference type
    if (items.Count == 0) return Money.Zero;                           // valid, but probably belongs at the boundary
    foreach (var item in items)
    {
        if (item == null) continue;                                    // List<LineItem> can't contain null in C# 8+ NRT
        // ...
    }
}
```

```python
# BAD: re-validating an EmailAddress value object inside a domain method.
def send_welcome(email: EmailAddress, name: str) -> None:
    if not email or "@" not in str(email):           # EmailAddress.__init__ already enforced this
        raise ValueError("invalid email")
    if name is None or not name.strip():             # `name: str` already excludes None
        raise ValueError("invalid name")
    mailer.send(email, name)
```

```ts
// BAD: parsing the same shape over and over, never producing a typed value.
function priceOrder(order: unknown): number {
  if (typeof order !== "object" || order === null) throw new Error("bad order");
  if (!("items" in order)) throw new Error("bad order");
  // ...same checks repeated in every consumer of `order`
}
```

## Good Example

```csharp
// GOOD: trust the type. Validate once at the boundary (HTTP / deserializer / factory).
public Money CalculateTotal(IReadOnlyList<LineItem> items)
{
    return items.Aggregate(Money.Zero, (acc, item) => acc + item.Subtotal);
}

// At the boundary:
[HttpPost("/orders/total")]
public IActionResult Total([FromBody] TotalRequest req)
{
    if (!ModelState.IsValid) return BadRequest(ModelState);   // boundary validation
    return Ok(CalculateTotal(req.Items));
}
```

```python
# GOOD: validate once in the value object's constructor; trust the type elsewhere.
@dataclass(frozen=True)
class EmailAddress:
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError(f"invalid email: {self.value!r}")

def send_welcome(email: EmailAddress, name: str) -> None:
    mailer.send(email, name)        # email is guaranteed valid; name is guaranteed str
```

```ts
// GOOD: parse once at the boundary into a typed Order; downstream code consumes Order, not unknown.
const OrderSchema = z.object({ items: z.array(LineItemSchema).min(1) });
type Order = z.infer<typeof OrderSchema>;

app.post("/orders/total", (req, res) => {
  const order = OrderSchema.parse(req.body);   // boundary: throws → 400
  res.json({ total: priceOrder(order) });
});

function priceOrder(order: Order): number {
  return order.items.reduce((acc, i) => acc + i.subtotal, 0);
}
```

## Exceptions

- **Public APIs of libraries** are themselves a trust boundary — every
  consumer is "untrusted" from the library's perspective. Argument
  validation at exported entry points is required, not defensive.
- **Languages without enforced types** (e.g. Python without runtime
  type-checking, JavaScript without TypeScript) — the type signature
  is documentation, not a guarantee. Validate at the boundary AND
  consider a runtime check on internal values that came from `dict`/
  `JSON.parse` paths, until they reach a typed value object.
- **Security-critical invariants** that are cheap to assert (e.g.
  "tenant ID matches the authenticated user") MAY be re-checked deeper
  in the stack as defense-in-depth. The check must be an `assert` /
  guard that throws, not a silent skip.
- **Cross-process / cross-trust calls** are new boundaries: a method
  that takes data from a queue or another service is a boundary, even
  if it looks like an internal call.

## Rationalizations

- **"What if someone passes null anyway?"**
  Then your type system is lying — fix the signature (non-nullable,
  `Optional`/`Maybe`), not the call site. The guard buries the contract
  violation in a generic exception two layers deep instead of catching
  it at the boundary where the response can be meaningful.
- **"Defense in depth — extra checks can't hurt."**
  They can: each check duplicates the validation rule, so the next
  refactor must update N places, and a missed update creates two
  branches that disagree about what "valid" means. Defense in depth
  applies to *security* invariants, not to type-system facts.
- **"It's just one `if` — barely any cost."**
  Compounded across a codebase, defensive guards become the dominant
  reading cost. Worse, they normalise the habit: the next contributor
  copies the pattern, and the boundary check that should exist never
  gets written.
- **"The compiler doesn't know X is non-empty / sorted / positive."**
  Then encode it: `NonEmptyList<T>`, a `PositiveInt` value object, a
  factory method on the type. Push the invariant into the type
  *once*, then everyone trusts it.
