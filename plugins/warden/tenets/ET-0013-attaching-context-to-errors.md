---
id: ET-0013
title: Attach diagnostic context to errors; preserve the cause chain
type: best-practice
tier: 1
applies-to: any
since: 0.2.0
triggers:
  - raising or throwing an exception with only a string message
  - logging an error that names the failure but not the inputs / IDs needed to reproduce it
  - reviewing a diff where the only diagnostic information is the exception class name
  - deciding which fields a domain error type should expose to its handler
tags: [error-handling, observability, diagnostics]
related: [ET-0002]
---

## Rule

When you raise, throw, or return an error, attach the structured data
needed to diagnose it: the entity ID being processed, the operation
being attempted, the relevant inputs, and — when wrapping a
lower-level failure — the original exception as `cause` /
`InnerException` / `raise … from`. A string message is for a human
to read at a glance; the structured data is what the error handler,
the logger's structured fields, and the on-call engineer use to
locate what happened. Stripping the cause chain (`raise NewError(str(e))`
without `from`, `throw new Error(e.message)`, `catch (Exception ex) {
throw new Exception("failed"); }`) is forbidden — it loses the
original stack trace and the original exception type, both of which
are required for triage.

## Why

An error that says only "save failed" sends the on-call engineer back
to the logs to reconstruct which user, which order, which retry
attempt — context that the failing code already had and threw away.
Wrapping an exception by stringifying its message loses both the
original stack trace and the original exception type, so handlers
that match on type (e.g. "retry on `TransientNetworkError`,
abort on `AuthError`") silently stop matching and the system
behaves as if every wrapped error were a new generic failure.
Multiplied across an incident, the missing context is the difference
between a five-minute root-cause and a fifty-minute one.

## Bad Example

```python
# BAD: message-only error; no IDs, no cause; original traceback is lost.
def settle(invoice_id: str) -> None:
    try:
        repo.save(invoice_id)
    except Exception as exc:
        raise RuntimeError(f"save failed: {exc}")    # no `from exc`, no fields
```

```csharp
// BAD: rewraps the exception, drops InnerException, drops the stack trace.
public Order Submit(int orderId)
{
    try { return _repo.Save(orderId); }
    catch (Exception ex) { throw new Exception("submit failed: " + ex.Message); }
}
```

```ts
// BAD: only the class name carries information; the IDs and cause are gone.
async function ship(orderId: string) {
  try { await carrier.dispatch(orderId); }
  catch { throw new ShippingError("dispatch failed"); }
}
```

## Good Example

```python
# GOOD: typed error with structured fields and `raise … from` to preserve the cause.
class SettlementFailed(Exception):
    def __init__(self, invoice_id: str, stage: str, *, cause: BaseException) -> None:
        super().__init__(f"settlement failed: invoice={invoice_id} stage={stage}")
        self.invoice_id = invoice_id
        self.stage = stage
        self.__cause__ = cause   # explicit cause, traceback preserved

def settle(invoice_id: str) -> None:
    try:
        repo.save(invoice_id)
    except RepoError as exc:
        raise SettlementFailed(invoice_id, stage="persist", cause=exc) from exc
```

```csharp
// GOOD: domain exception with structured fields; InnerException carries the cause chain.
public sealed class SubmitFailed : Exception
{
    public int OrderId { get; }
    public string Stage { get; }
    public SubmitFailed(int orderId, string stage, Exception inner)
        : base($"submit failed: orderId={orderId} stage={stage}", inner)
    { OrderId = orderId; Stage = stage; }
}

public Order Submit(int orderId)
{
    try { return _repo.Save(orderId); }
    catch (DbException ex) { throw new SubmitFailed(orderId, "persist", ex); }
}
```

```ts
// GOOD: structured error with `cause` (ES2022). Loggers can serialize the chain.
class ShippingError extends Error {
  constructor(public orderId: string, public carrier: string, options: { cause: unknown }) {
    super(`shipping failed: orderId=${orderId} carrier=${carrier}`, options);
    this.name = "ShippingError";
  }
}

async function ship(orderId: string) {
  try { await carrier.dispatch(orderId); }
  catch (cause) { throw new ShippingError(orderId, "ups", { cause }); }
}
```

## Exceptions

- **Validation errors at trust boundaries** (see ET-0003) MAY use a
  message-only form when the message *is* the diagnostic — e.g. a
  parse error that already says "expected number at line 3 col 5".
  The "context" the rule asks for is data the *caller* threw away;
  for parse errors, the parse library carries the structured info.
- **`assert` and other "this can't happen" failures** in production
  code MAY raise with only a message: by definition there is no
  recovery, the path is unreachable, and the message names the
  invariant that was violated. Adding structured fields to an
  assert is welcome but not required.
- **Cross-process error responses** (HTTP 4xx/5xx, gRPC status,
  message-queue NACKs) are constrained by the wire format. Carry
  the structured context inside the response payload and the cause
  chain in correlated logs; the wire-level message can be terse.

## Rationalizations

- **"The logger will pick up the original exception."** Only if the
  cause chain is preserved. `raise NewError(str(old))` and
  `throw new Error(old.message)` both produce a *new* exception
  whose `cause` / `InnerException` is `null`; the logger has no
  trail to follow.
- **"I don't want to expose internal IDs in the error message."**
  Then put them in structured fields, not the message. Loggers can
  redact fields; rebuilding redacted information from a redacted
  message is impossible. The error type is the place where this
  decision is made once.
- **"Adding fields makes the exception class bigger."** It also
  makes the failure searchable: `kibana | filter exception.invoice_id
  = "abc"` works only if `invoice_id` is a field, not part of a
  free-form message string. The bigger class pays for itself the
  first time it's queried during an incident.
