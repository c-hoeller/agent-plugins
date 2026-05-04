---
name: et-0004-asserting-observable-behavior
description: Use when writing a test that verifies a mock was called instead of the effect the call produced; reaching for a spy/stub/inspector to peek at internal state from a test; reviewing a test that breaks every time the production code is refactored; deciding what to assert about a function whose contract is "given X, the world looks like Y".
---
<!-- generated from tenets/ET-0004-asserting-observable-behavior.md by `uv run poe build` — do not edit by hand. -->

# ET-0004 — Tests assert observable behavior, not implementation

_Type: best-practice · Severity: high · Tier: 1_

## Rule

A test asserts the **observable behavior** of the system under test —
the return value, the persisted state, the message emitted, the
HTTP/database/file effect produced, or the exception raised. It does
**not** assert *how* that behavior was produced: which private method
was called, which collaborator was invoked, in what order, with what
arguments — unless the call itself **is** the behavior (e.g. the unit
exists to send that exact message). When the only way to express the
test is to reach for a mock and verify a method-call, the unit under
test has no observable contract — fix the design, not the test.

## Why

Implementation-coupled tests fail every time someone refactors the
production code, even when the behavior is unchanged. The team learns
that a green test suite means "nothing was refactored", not "nothing
broke" — so refactoring stops, the code rots, and the suite becomes a
maintenance tax rather than a safety net. Worse, mock-verification
tests routinely pass while the system is broken: the mock returns
whatever the test set up, regardless of whether the *real* collaborator
would. The test asserts that two pieces of code agree on a fiction.
Behavior tests survive refactors because the contract — not the
mechanism — is what matters to the caller.

## Bad Example

```csharp
// BAD: verifies that `_repo.Save` was called, not that the order was actually saved.
[Fact]
public void Submit_PersistsOrder()
{
    var repoMock = new Mock<IOrderRepo>();
    var sut = new OrderService(repoMock.Object);

    sut.Submit(new Order { Id = 42 });

    repoMock.Verify(r => r.Save(It.Is<Order>(o => o.Id == 42)), Times.Once);
    // refactor: introduce a UnitOfWork that batches saves → test breaks even though the order is still saved.
}
```

```python
# BAD: peeks at private state, asserts the spy, ignores the actual effect.
def test_enqueue_increments_pending_count(monkeypatch):
    queue = JobQueue()
    spy = MagicMock(wraps=queue._pending)   # reaching into _pending
    monkeypatch.setattr(queue, "_pending", spy)

    queue.enqueue(Job("a"))

    spy.append.assert_called_once()         # asserts append was called, not that the job is enqueued
```

```ts
// BAD: every test that uses `sendEmail` is coupled to the mailer's internal API.
test("welcome email is sent", () => {
  const mailer = { send: vi.fn() };
  const svc = new SignupService(mailer);

  svc.signup({ email: "a@b.c" });

  expect(mailer.send).toHaveBeenCalledWith(
    expect.objectContaining({ to: "a@b.c", template: "welcome-v3" }),
  );
  // refactor: switch from `template` to `subject`+`body` → test breaks; the user still got the email.
});
```

## Good Example

```csharp
// GOOD: assert the persisted result through the observable surface (the repo's read side).
[Fact]
public void Submit_PersistsOrder()
{
    var repo = new InMemoryOrderRepo();           // real fake, observable
    var sut = new OrderService(repo);

    sut.Submit(new Order { Id = 42 });

    Assert.Equal(42, repo.GetById(42).Id);        // the order is actually retrievable
}
```

```python
# GOOD: assert the public observable — what a caller can see.
def test_enqueue_makes_job_visible():
    queue = JobQueue()

    queue.enqueue(Job("a"))

    assert queue.peek().name == "a"   # observable through the public API
    assert queue.size() == 1
```

```ts
// GOOD: capture what the world saw — a real fake records sent messages, the test asserts on them.
test("welcome email is sent", () => {
  const mailer = new FakeMailer();      // records sends, exposes a `sent` accessor
  const svc = new SignupService(mailer);

  svc.signup({ email: "a@b.c" });

  expect(mailer.sent).toHaveLength(1);
  expect(mailer.sent[0].to).toBe("a@b.c");
  // refactor: swap template engine, change call shape → test still passes if the email goes out.
});
```

## Exceptions

- **The call itself IS the behavior.** A unit whose entire job is to
  emit a specific message (event publisher, audit logger, retry
  scheduler) is correctly tested by asserting the message it emits.
  The mock-verification *is* the behavioral assertion — there is no
  deeper observable.
- **Cross-process boundaries** (HTTP, DB, queue) where the real
  collaborator is too slow / non-deterministic for unit tests. Use a
  contract-tested fake: a fake that itself has tests proving it
  behaves like the real collaborator on the relevant subset of the
  contract. Mock-verifications against an unverified fake are still a
  violation.
- **Performance / interaction-count tests** that exist explicitly to
  prove "this code path makes exactly N database calls". The
  cardinality of calls *is* the contract under test.
- **Legacy code with no testable seam.** A characterization test that
  pins current behavior — including current call patterns — is
  acceptable as a temporary scaffold. The test must carry a comment
  naming the planned refactor and the seam it is waiting on.

## Rationalizations

- **"It's easier to test the helper directly."**
  See ET-0001. If the helper is hard to test through the public
  surface, the public surface is missing something — extract a
  collaborator the test can drive, or expose the observable result.
- **"Mocks are faster than real fakes."**
  Speed is rarely the bottleneck a project actually has; broken
  refactors are. A real fake costs once to build and saves every
  refactor afterwards; a wall of mocks costs every refactor forever.
- **"I need to prove the cache was hit / the retry happened."**
  Then the cache hit and the retry are observable behaviors — expose
  them as metrics, counters, or decorator state, and assert on those.
  The test is right; the design is missing the observable.
- **"The collaborator is an interface, so mocking it is fine."**
  Interfaces describe shape, not contract. Mocking an interface lets
  you assert against a fiction; a real fake forces you to encode the
  *contract* (e.g. "after `save(x)`, `getById(x.id)` returns `x`").
  That contract is what the test should assert against.
