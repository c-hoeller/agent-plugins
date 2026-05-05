---
id: ET-0006
title: Names describe the domain, not the implementation
type: best-practice
tier: 1
applies-to: any
since: 0.1.0
triggers:
  - choosing a name for a variable, parameter, field, or type that ends in `Array`/`List`/`Dict`/`Map`/`Manager`/`Helper`
  - naming a function after how it works (`run`, `process`, `handle`) instead of what it does to the domain
  - reviewing a diff that introduces identifiers like `userData`, `customerObj`, `orderInfo`
  - renaming an identifier whose current name leaks the type or storage
tags: [naming, readability, domain]
related: []
---

## Rule

Identifier names — variables, parameters, fields, methods, types — name
what the value **means in the domain**, not how it is **implemented**
or **stored**. `users` is a domain name; `userArray`, `userList`,
`userDict`, `userData`, `userObj`, `userInfo` are implementation
names. `sendInvoice` is a domain name; `runInvoiceSender`,
`processInvoice`, `handleInvoice`, `doInvoice` are mechanism names.
Suffixes like `Manager`, `Helper`, `Util`, `Processor` are
mechanism names that almost always indicate a missing concept — find
the verb the *domain* uses, or the noun the *user* would recognise,
and name accordingly.

## Why

Implementation names break the abstraction they're inside. A reader
sees `userArray` and forms a mental model that depends on it being an
array — when the next refactor switches to a `Set` (because
duplicates were a bug) or a `Map<id, User>` (because lookups got hot),
either the name lies or the rename touches every call site. Domain
names survive: `users` is correct whether the storage is `[]`,
`Set`, `Map`, or a streaming iterator. Names ending in `Manager` /
`Helper` / `Util` are a stronger smell — they describe the author's
inability to find the real concept, and the type ends up as a magnet
for unrelated logic ("it's the user manager, sure put it there").
The rename to a domain name usually splits the type into the two real
concepts that were hiding inside it.

## Bad Example

```csharp
// BAD: name leaks storage and verb leaks mechanism. Both will lie after the next refactor.
public class CustomerDataManager
{
    private readonly List<Customer> _customerList;

    public void ProcessCustomer(Customer customerObj)
    {
        // change `_customerList` to a Dictionary<id, Customer> for O(1) lookups
        // → name now lies; rename touches every reference.
    }
}
```

```python
# BAD: `*_data` / `*_dict` / `*_list` describe the container, not the meaning.
def process_user_data(user_dict: dict, order_list: list) -> dict:
    result_dict = {}
    for user_obj in user_dict.values():
        ...
    return result_dict
```

```ts
// BAD: every name describes its type or its role in the runtime, not in the domain.
function runOrderProcessor(orderArray: Order[]): ResultObj {
  const totalNum: number = orderArray.reduce(...);
  return { totalNum };
}
```

## Good Example

```csharp
// GOOD: types describe domain concepts; verbs describe domain actions.
public class CustomerDirectory
{
    private readonly Dictionary<CustomerId, Customer> _customers;

    public void Register(Customer customer)
    {
        _customers[customer.Id] = customer;   // storage can change without renaming.
    }
}
```

```python
# GOOD: parameters and locals carry meaning, not container type.
def settle_invoices(customers: Mapping[CustomerId, Customer], orders: Iterable[Order]) -> Receipts:
    receipts: dict[OrderId, Receipt] = {}
    for customer in customers.values():
        ...
    return Receipts(receipts)
```

```ts
// GOOD: name describes the domain. Refactoring `orders` to a Set or Map does not break the name.
function settleOrders(orders: Iterable<Order>): Receipt[] {
  const total = sum(orders, (o) => o.amount);
  return ...;
}
```

## Exceptions

- **Truly generic utilities** that operate on a container regardless
  of domain (e.g. `function chunk<T>(items: T[], size: number)`)
  legitimately use type-shaped names — the function has no domain.
- **Low-level / infrastructure code** that genuinely operates at the
  storage layer: a TCP read buffer is `buffer`, a deserialization
  staging dict is `payload`, a parser's token list is `tokens`. The
  domain *is* the mechanism here.
- **Test-local variables** in the smallest scope (within one
  arrange/act/assert) MAY use shape-y names when the test is about
  the shape itself (`emptyList`, `oneItem`, `manyItems`) — the test's
  domain *is* "what shape exposes the bug".
- **Established conventions** in a framework or codebase that are
  legible to its readers (`*Controller`, `*Repository`, `*Component`,
  `*Service` where the framework defines the role) — these are
  domain names *within their framework*. Avoid the same shape for
  ad-hoc internal classes that have no framework role.

## Rationalizations

- **"It's clearer what type it is at a glance."** Your IDE shows the
  type. The name's job is to carry meaning the type cannot — what
  this thing *is for*. `userArray` doesn't tell you whether it's
  "all users", "logged-in users", or "users to notify"; `recipients`
  does.
- **"I'll forget it's a list / dict otherwise."** Then the scope is
  too long. Either narrow the scope so the type is visible at a
  glance, or wrap the collection in a domain type (`Recipients`,
  `Inventory`, `Cart`) that also carries the invariants you actually
  care about.
- **"`Manager` / `Helper` is fine, the team uses it everywhere."**
  Team-wide use is the symptom, not the justification. Each
  `*Manager` is hiding a distinct domain concept that was never
  named; finding those names is a one-time cost that pays off every
  time someone tries to locate behavior.
- **"Renaming is risky / churn-y."** Modern refactor tools rename
  safely. The risk is leaving the lying name in place: every
  contributor learns to ignore the type-leaking suffix, and the next
  bad name slips in unchallenged.
