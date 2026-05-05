---
name: et-0005-writing-comments-that-explain-why
description: Comments explain why, not what.
when_to_use: Use when writing a comment that paraphrases the line of code immediately below it; adding a docstring to a function whose name and signature already say everything; reviewing a diff that adds explanatory comments to make obvious code "easier to read"; deciding whether a non-obvious decision (workaround, constraint, invariant) needs a comment.
user-invocable: false
---
<!-- generated from tenets/ET-0005-writing-comments-that-explain-why.md by `uv run poe build` — do not edit by hand. -->

# ET-0005 — Comments explain why, not what

_Type: best-practice · Tier: 1_

## Rule

Comments capture the **why** that the code itself cannot express:
hidden constraints, surprising invariants, references to upstream
bugs, deliberate workarounds, performance trade-offs, "we tried the
obvious way and it failed because…". Comments do **not** restate
*what* the code does — that is the code's job, and a clear identifier
or a short helper function does it better than prose. If you find
yourself describing the next line in English, rename the line; if a
function needs a paragraph to explain its purpose, the function is
doing too much. Default to no comment; add one only when removing it
would leave a future reader genuinely uncertain.

## Why

What-comments rot. The code changes, the comment doesn't, and the
next reader is left to guess which is right — usually losing minutes
diffing them, sometimes shipping a bug because they trusted the wrong
one. Why-comments survive: they record a fact the code cannot
encode (an external constraint, a past incident, a performance
measurement) and that fact stays true even when the implementation
changes. Comments that name the current PR, ticket, or caller (`// for
the new checkout flow`) rot the fastest — the moment "the new
checkout flow" is two years old, the comment is misleading.

## Bad Example

```csharp
// BAD: every comment paraphrases the next line.
public decimal CalculateTotal(IEnumerable<LineItem> items)
{
    // sum up all the line items
    decimal total = 0;
    foreach (var item in items)
    {
        // multiply price by quantity
        total += item.Price * item.Quantity;
    }
    // return the total
    return total;
}
```

```python
# BAD: docstring restates the signature; "added for X" comment will rot.
def send_invoice(customer_id: str, amount: Decimal) -> None:
    """Send an invoice to the customer with the given amount.

    Added for the new billing flow (PR #1842).
    """
    # loop through the line items and sum them
    ...
```

```ts
// BAD: comment narrates the obvious; the variable name already says it.
function priceOrder(order: Order): number {
  // initialize the total to zero
  let total = 0;
  // iterate over each item in the order
  for (const item of order.items) {
    // add the item's subtotal to the total
    total += item.subtotal;
  }
  return total;
}
```

## Good Example

```csharp
// GOOD: no narration of the loop. Comments only where the WHY is non-obvious.
public decimal CalculateTotal(IEnumerable<LineItem> items)
{
    return items.Sum(i => i.Price * i.Quantity);
}

// Elsewhere, where it matters:
// Stripe rejects amounts < 0.50 with a generic error; we round up at the API
// boundary so retries don't loop forever. See incident #2024-08-14.
private decimal NormalizeForStripe(decimal amount) =>
    amount < 0.50m ? 0.50m : amount;
```

```python
# GOOD: signature speaks for itself; comment captures a non-obvious constraint.
def send_invoice(customer_id: str, amount: Decimal) -> None:
    # SAP only accepts invoices in EUR; upstream code must convert before calling.
    # We do not convert here because the caller owns FX rate selection.
    ...
```

```ts
// GOOD: no narration. Comment names the workaround, not the loop.
function priceOrder(order: Order): number {
  // Round per-item, not on the sum: the legacy POS terminal computes the
  // same way and we must reconcile to its receipts to the cent.
  return order.items.reduce(
    (total, item) => total + Math.round(item.subtotal * 100) / 100,
    0,
  );
}
```

## Exceptions

- **Public API documentation** (XML doc comments, docstrings, JSDoc on
  exported symbols) is a contract for callers, not narration for the
  next reader. Document parameters, return values, thrown errors, and
  examples — these are the WHY of "how to use this", not the WHAT of
  "what this line does".
- **Required headers** — license blocks, generated-file markers, build-
  tool directives — are mandated by tooling or policy and are not
  subject to this rule.
- **Tricky algorithms** (custom hash, lock-free queue, numerical
  stability fixes) MAY include a brief WHAT-comment to orient the
  reader, but only as the lead-in to the WHY (why this specific
  algorithm, what failure mode it avoids).
- **TODOs and FIXMEs** with a tracked issue link are allowed; bare
  TODOs without a link are not — they are noise that never gets
  resolved.

## Rationalizations

- **"Future me will thank me for the explanation."** Future-you will
  read the code, not the comment. The comment that helps future-you
  is the one that says *why* the obvious approach was rejected, not
  the one that paraphrases the loop. If the code needs paraphrasing,
  rename it.
- **"More documentation is always better."** Wrong direction. More
  *correct* documentation is better; more documentation total raises
  the chance of a stale comment, which is worse than no comment at
  all because it actively misleads.
- **"The reviewer asked for a comment."** Then the reviewer found
  something non-obvious — capture *that* (the invariant, the
  constraint, the past incident), not a paraphrase of the line. If
  the reviewer wanted a paraphrase, the line itself needs renaming.
- **"It's a one-line comment, what's the harm?"** The harm is the
  next change to the line: comment doesn't update, code does, and
  now the file has two truths. Multiplied by every one-line narration
  in a codebase, you get the long-term reading tax this rule exists
  to prevent.
