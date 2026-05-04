---
name: et-0002-surfacing-failures
description: Use when handling an error you do not know how to recover from in the current scope; writing a `catch` / `except` / `.catch()` block that does nothing or only logs; reviewing a diff that adds a try/catch around new code without rethrow or remediation; deciding what to do with a Promise/Task whose failure path has no obvious owner.
---
<!-- generated from tenets/ET-0002-surfacing-failures.md by `uv run poe build` — do not edit by hand. -->

# ET-0002 — Never silently swallow failures

_Type: anti-pattern · Severity: high · Tier: 1_

## Rule

Never write an error handler — `catch`, `except`, `.catch()`, error-callback,
result-discard — that neither **recovers** the operation, **rethrows** (or
maps) the failure, nor **escalates** it through a documented channel. An
empty handler, a log-only handler, or a handler that returns a fabricated
"success" sentinel is a silent failure and is forbidden. If you do not know
how to recover at this layer, let the exception propagate.

## Why

Silent handlers turn one failure into two: the original bug, plus the
delayed downstream bug that surfaces hours later when corrupted state hits
a reporting query, a reconciliation job, or a customer screen. By then the
stack trace, request ID, and surrounding inputs are gone, and triage costs
ten times what it would have at the point of failure. Logging is not a
substitute — logs are observability, not control flow, and a `logger.error`
followed by silent return tells the next caller "this succeeded". If
recovery is genuinely impossible at this layer, propagation is the correct
behaviour, not embarrassment.

## Bad Example

```csharp
// BAD: empty catch hides every failure mode (network, auth, parsing, …)
// and returns a misleading "no orders" to every caller.
public List<Order> LoadOrders(int customerId)
{
    try
    {
        return _api.FetchOrders(customerId);
    }
    catch (Exception)
    {
        return new List<Order>();
    }
}
```

```python
# BAD: bare logging "swallows" the error — caller sees None and assumes "no user".
def load_user(user_id: str) -> User | None:
    try:
        return repo.fetch(user_id)
    except Exception as exc:
        log.error("fetch failed: %s", exc)
        return None
```

```ts
// BAD: .catch(() => undefined) erases every failure into a falsy value.
async function loadConfig(): Promise<Config | undefined> {
  return fetchConfig().catch(() => undefined);
}
```

## Good Example

```csharp
// GOOD: catch only what you can act on; map to a domain error; let the rest propagate.
public List<Order> LoadOrders(int customerId)
{
    try
    {
        return _api.FetchOrders(customerId);
    }
    catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
    {
        return new List<Order>(); // documented: 404 = customer has no orders
    }
    // network errors, auth errors, parsing errors propagate to the caller.
}
```

```python
# GOOD: re-raise as a typed domain error so callers can branch on it.
class UserNotFound(LookupError): ...

def load_user(user_id: str) -> User:
    try:
        return repo.fetch(user_id)
    except repo.NotFoundError as exc:
        raise UserNotFound(user_id) from exc
    # connection errors, timeouts, etc. propagate untouched.
```

```ts
// GOOD: handle the one recoverable case explicitly; let everything else bubble.
async function loadConfig(): Promise<Config> {
  try {
    return await fetchConfig();
  } catch (err) {
    if (err instanceof ConfigNotFoundError) {
      return defaultConfig; // documented fallback
    }
    throw err;
  }
}
```

## Exceptions

- **Top-level process boundaries** (HTTP request handler, job runner,
  message-queue consumer, UI event handler) MAY catch a broad
  `Exception` to convert it into a structured error response, a retry
  decision, or a user-facing message — provided the failure is logged
  *with* a request/correlation ID and the response signals failure
  (HTTP 5xx, NACK, error toast). This is mapping, not swallowing.
- **Cleanup paths** in `finally` / `using` / context-manager blocks MAY
  log-and-continue when the cleanup itself fails, because the original
  failure (which is what callers care about) is still being raised.
- **Best-effort side effects** that are explicitly documented as
  fire-and-forget (e.g. emitting a non-critical metric, prefetching a
  cache) MAY swallow failures, but the call site MUST carry a comment
  naming the side effect and why losing it is acceptable.

## Rationalizations

- **"I'll just log it for now and figure out recovery later."**
  "Later" turns into a corrupted database six months later. If you
  cannot decide on recovery now, propagate; the next layer either
  handles it or fails loudly. Logging plus silent return is the worst
  of both worlds — the failure is observable but not visible.
- **"The caller doesn't expect an exception here."**
  Then the caller is wrong, or the signature is. Document the exception,
  return a `Result`/`Either`/`tuple[None, Error]`, or split the API into
  a "may-fail" and a "won't-fail" form. Don't paper over the type
  mismatch by faking success.
- **"I'm catching `Exception` because I don't know what it can throw."**
  That is the bug, not the fix. Read the code path, list the realistic
  failures, and catch only those. A blanket catch hides the new failure
  mode the next refactor introduces.
- **"It's just a UI / non-critical path."**
  Silent UI failures train users to retry blindly and hide outages from
  ops. Show the failure in the UI (toast, error state) and report it to
  the error tracker — that is mapping, not swallowing.
