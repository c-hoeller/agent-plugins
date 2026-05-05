---
id: ET-0010
title: Pass dependencies explicitly; no global lookups inside units
type: anti-pattern
tier: 1
applies-to: any
since: 0.1.0
triggers:
  - calling a module-level singleton, service locator, or static accessor from inside a function or class method
  - writing a class that constructs its own database / HTTP / queue client in the constructor
  - reviewing a diff where a unit's behavior depends on something that does not appear in its signature or constructor
  - deciding how a unit obtains a collaborator it needs (parameter / constructor vs global lookup)
tags: [dependency-injection, testability, coupling]
related: [ET-0009, ET-0011, ET-0014]
---

## Rule

Every collaborator a unit needs — repository, HTTP client, logger,
clock, configuration, ID generator — is supplied through the unit's
constructor (for classes) or its function signature (for free
functions). Do not reach for module-level singletons, service
locators, ambient `static` accessors, or `import { db } from
'./db-singleton'` style patterns to *obtain* a dependency from inside
a unit. Concrete instances are constructed once in the **composition
root** (program entry, DI container configuration, top-level
factory) and passed down. A unit's signature is its complete
contract; if the unit secretly depends on something not listed there,
the contract is a lie.

## Why

A hidden dependency makes a unit untestable in isolation: tests cannot
substitute the dependency without monkey-patching imports, which is
brittle, leaks across tests (see ET-0014), and routinely fails for
transitive consumers. It also breaks local reasoning — you cannot
tell from reading the unit what it depends on, only what it admits to
depending on. The first symptom is usually a test that passes alone
and fails in the suite, or a "works on my machine" bug whose root
cause is a singleton initialised by an earlier import order. Explicit
parameters cost one line at the construction site of the unit and
return that cost as deterministic tests, parallelisable suites, and
substitutable fakes.

## Bad Example

```python
# BAD: the unit reaches for a module-level singleton; tests must monkeypatch the import path.
from app.db import session       # module-level singleton
from app.clock import now        # module-level function

def settle_invoice(invoice_id: str) -> None:
    invoice = session.query(Invoice).get(invoice_id)
    invoice.settled_at = now()
    session.commit()
```

```csharp
// BAD: the class constructs its own dependencies; nothing can substitute them.
public class OrderService
{
    private readonly SqlConnection _conn = new(Environment.GetEnvironmentVariable("DB"));
    private readonly HttpClient _http   = new();

    public Order Submit(OrderRequest req) { /* uses _conn, _http directly */ }
}
```

```ts
// BAD: a static accessor / service locator hides what the function actually needs.
function chargeCustomer(orderId: string) {
  const stripe = ServiceLocator.get("stripe");      // hidden dep
  const orders = ServiceLocator.get("orderRepo");   // hidden dep
  // ...
}
```

## Good Example

```python
# GOOD: dependencies are parameters; the test passes fakes, production passes real ones.
def settle_invoice(invoice_id: str, *, repo: InvoiceRepo, clock: Clock) -> None:
    invoice = repo.get(invoice_id)
    invoice.settled_at = clock.now()
    repo.save(invoice)

# Composition root (entry point) wires the real instances:
def main() -> None:
    repo  = SqlInvoiceRepo(connect(os.environ["DB_URL"]))
    clock = SystemClock()
    settle_invoice(sys.argv[1], repo=repo, clock=clock)
```

```csharp
// GOOD: dependencies are constructor parameters; tests pass fakes, DI passes real ones.
public class OrderService
{
    private readonly IOrderRepo _repo;
    private readonly IPaymentGateway _payments;

    public OrderService(IOrderRepo repo, IPaymentGateway payments)
    {
        _repo = repo;
        _payments = payments;
    }

    public Order Submit(OrderRequest req) { /* uses _repo, _payments */ }
}
```

```ts
// GOOD: pass collaborators in; the wiring lives in main() / a DI container.
function chargeCustomer(orderId: string, deps: { stripe: Stripe; orders: OrderRepo }) {
  // deps.stripe, deps.orders — no hidden lookups.
}
```

## Exceptions

- **Pure utility functions** that depend only on their arguments and
  on standard-library functions (`Math.max`, `string.upper`,
  `Enumerable.Sum`) need no injection — they have no collaborators
  to inject.
- **Composition root code** (program `main`, DI container setup,
  top-level factory functions) is *where* concrete dependencies are
  constructed and looked up; it is the one place global lookups are
  expected. This exception does not extend to "any class near `main`";
  only the wiring code itself.
- **Framework-mandated patterns** that the framework enforces (e.g.
  ASP.NET's `[FromServices]`, Spring's `@Autowired` field injection,
  Angular's `inject()`) are acceptable: the framework *is* the
  composition root, and substitution happens via its DI registry. The
  exception does not extend to ad-hoc service locators built on top
  of the framework.

## Rationalizations

- **"It's only used in one place, no point passing it."** Until it is
  used in two; then a second consumer reaches for the same
  module-level handle and now both are coupled to the same global.
  Adding a parameter once costs less than untangling a singleton
  later.
- **"The DI container is overkill for this."** The objection is
  against the *container*, not against parameters. A constructor
  taking `(IOrderRepo, IClock)` works whether you wire it by hand in
  `main()` or via a container — the unit doesn't care.
- **"I can monkey-patch / `vi.mock` the import in tests."** That
  patches the module globally for the test process; parallel tests in
  the same process will see each other's patches, and the patch
  routinely misses transitive imports. Substitution-through-parameter
  is local to the call.
- **"`new HttpClient()` inside the class is fine, it's just a
  detail."** It is the detail that makes the class untestable
  (real network), unconfigurable (timeouts, retries, base URL), and
  resource-leaky (no shared connection pool). All three are caused by
  the hidden construction.
