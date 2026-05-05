---
name: et-0009-separating-decisions-from-effects
description: Keep decisions pure; isolate effects in a thin shell.
when_to_use: Use when writing a function that mixes domain decisions with database / HTTP / filesystem calls; needing to mock half a class to test the other half; reviewing a diff where business logic is interleaved with `await db.query` / `requests.get` / `File.ReadAll*`; deciding where to place an algorithmic decision relative to the I/O it depends on.
user-invocable: false
---
<!-- generated from tenets/ET-0009-separating-decisions-from-effects.md by `uv run poe build` — do not edit by hand. -->

# ET-0009 — Keep decisions pure; isolate effects in a thin shell

_Type: best-practice · Tier: 1_

## Rule

Separate the decision logic from effect execution. Domain rules — what
to do given the inputs — live in functions that take values and return
values: no I/O, no clock reads, no random, no mutation of shared
state. Effect execution — fetching, persisting, sending, scheduling —
lives in a thin shell that gathers inputs, calls the pure core with
those inputs, and applies the resulting decisions to the world. A
function that fetches, decides, and writes in one body is fixable by
extracting the decision into a pure helper that takes the fetched
values and returns the intended effects; "it's just one call" is not
a reason to mix the two.

## Why

Tangled functions force a bad choice in tests: either run the real I/O
(slow, flaky, non-deterministic), or mock half the function (brittle
and asserts the wrong thing — see ET-0004). Both choices erode the
suite, which is why bugs that survive into production usually live in
code with the lowest test coverage. A pure decision function is
testable with values, deterministic, and free of setup; the shell is
testable by inspecting which effects it asked for. When the bug is
"we charged the wrong amount", you read the calculation in isolation,
without database fixtures or HTTP recordings — and when the bug is
"we charged the right amount but to the wrong account", you read the
shell.

## Bad Example

```python
# BAD: fetch, decide, write — all in one body. Untestable without a real DB or a maze of mocks.
async def settle_invoice(invoice_id: str) -> None:
    invoice = await db.fetch_invoice(invoice_id)
    customer = await db.fetch_customer(invoice.customer_id)
    discount = 0.10 if customer.tier == "gold" else 0.0
    if invoice.created_at < now() - timedelta(days=30):
        discount += 0.05
    total = invoice.amount * (1 - discount)
    await stripe.charge(customer.stripe_id, total)
    await db.mark_settled(invoice_id, total)
```

```csharp
// BAD: business rule lives inside an I/O method; tests must spin up a database or mock IRepo.
public async Task<decimal> CalculateAndSaveTotalAsync(int orderId)
{
    var order = await _repo.GetOrderAsync(orderId);
    var total = order.Items.Sum(i => i.Price);
    if (order.CustomerSince < DateTime.UtcNow.AddYears(-2))
        total *= 0.95m;                                       // loyalty rule, hidden behind IO
    await _repo.SaveTotalAsync(orderId, total);
    return total;
}
```

## Good Example

```python
# GOOD: pure decision function takes values, returns the intended effects.
@dataclass(frozen=True)
class SettlementDecision:
    charge_amount: Money
    record_total:  Money

def decide_settlement(invoice: Invoice, customer: Customer, today: date) -> SettlementDecision:
    discount = Decimal("0.10") if customer.tier == "gold" else Decimal("0")
    if (today - invoice.created_at.date()).days >= 30:
        discount += Decimal("0.05")
    total = invoice.amount * (1 - discount)
    return SettlementDecision(charge_amount=total, record_total=total)

# Thin shell wires inputs to outputs.
async def settle_invoice(invoice_id: str, *, today: date) -> None:
    invoice  = await db.fetch_invoice(invoice_id)
    customer = await db.fetch_customer(invoice.customer_id)
    decision = decide_settlement(invoice, customer, today)
    await stripe.charge(customer.stripe_id, decision.charge_amount)
    await db.mark_settled(invoice_id, decision.record_total)
```

```csharp
// GOOD: pure rule lives in one place; the shell does the IO.
public static decimal CalculateTotal(Order order, DateTime today)
{
    var total = order.Items.Sum(i => i.Price);
    if (order.CustomerSince < today.AddYears(-2))
        total *= 0.95m;
    return total;
}

public async Task<decimal> SaveTotalAsync(int orderId, IClock clock)
{
    var order = await _repo.GetOrderAsync(orderId);
    var total = CalculateTotal(order, clock.UtcNow);
    await _repo.SaveTotalAsync(orderId, total);
    return total;
}
```

## Exceptions

- **Trivial pass-through methods** that compose two effect calls with
  no domain logic between them (e.g. "fetch then publish") are
  acceptable as part of the shell — there is no decision to extract.
- **Streaming / pipeline code** where each element triggers an effect
  by design (e.g. an event handler that emits a downstream event)
  inherently mixes decisions with effects. Keep the per-element
  decision pure; the loop / pipeline is the shell.
- **Languages without first-class data types** (e.g. some scripting
  contexts) MAY accept tighter coupling for short-lived scripts. The
  exception applies only when the script is genuinely throwaway and
  has no test suite.

## Rationalizations

- **"Extracting the pure function makes the code longer."** It makes
  *the shell* shorter — the decision moves into a function that has a
  name, a signature, and tests. Aggregate line count goes down once
  the tests stop needing fixtures.
- **"There's only one decision in this function, it's not worth
  splitting."** Today there is one. The reason this rule exists is
  that the second decision is added inline, six months later, on top
  of the I/O calls — and now neither is testable.
- **"I'll just mock the DB."** That mock is asserting that the code
  called the DB the way the test expected, not that the decision was
  right (see ET-0004). Mocking is the shape of the problem this rule
  prevents, not its solution.
