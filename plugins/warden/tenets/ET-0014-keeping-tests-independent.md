---
id: ET-0014
title: Keep tests independent and order-agnostic
type: anti-pattern
tier: 1
applies-to: any
since: 0.2.0
triggers:
  - writing a test that depends on data left behind by a previous test
  - using a module-level fixture or class-level mutable variable to share state between tests
  - reviewing a diff where reordering tests, randomising them, or running one in isolation would change the outcome
  - deciding where to put setup that touches database / filesystem / global state
tags: [testing, isolation, reliability]
related: [ET-0010, ET-0011, ET-0015]
---

## Rule

Each test arranges its own state, executes, and cleans up — without
relying on, or leaving behind, state another test can observe. No
shared mutable module-level fields, no class-level mutable variables
read by sibling tests, no order-dependent fixtures, no global mocks
or monkey-patches that survive the test, no tests that "must run in
order". Running the whole suite in random order, in parallel, or
running any single test in isolation must produce the same result
every time. A test that needs the world in a particular state
arranges that world itself, in its own setup.

## Why

Order-dependent tests fail in production CI but pass on a developer's
machine where `pytest tests/test_x.py::test_y` ran in isolation; the
debugging path is "run the suite ten times, bisect the order, find
the polluting test, find the leaked state". Hours of bisection
typically reveal that the failing test depended on an earlier test
seeding a row, freezing the clock, or populating a cache, and the
"fix" — adding more shared setup — makes the suite's true coverage
*shrink* because tests start asserting things that are true only
when the previous test ran. Independence is the property that lets
the suite be parallelised, sharded across machines, and trusted as a
signal at all.

## Bad Example

```python
# BAD: module-level shared state; test_b only passes after test_a runs.
USERS: list[User] = []

def test_a_create_user():
    USERS.append(User("alice"))
    assert USERS[0].name == "alice"

def test_b_count_users():
    assert len(USERS) == 1   # passes only because test_a ran first
```

```csharp
// BAD: static field carries state across tests; parallel runners flake.
public class OrderTests
{
    private static readonly OrderRepo _repo = new();   // shared across tests
    [Fact] public void CreatesOrder() { _repo.Save(new Order(1)); /* ... */ }
    [Fact] public void FindsOrder()   { Assert.NotNull(_repo.GetById(1)); }   // depends on the previous test
}
```

```ts
// BAD: a global mock leaks across tests; the second test sees fixtures from the first.
let mailerSpy = vi.fn();
beforeAll(() => { vi.spyOn(mailer, "send").mockImplementation(mailerSpy); });
test("sends welcome", () => { signup({ email: "a@b.c" }); expect(mailerSpy).toHaveBeenCalled(); });
test("sends nothing on opt-out", () => { signup({ email: "x@y.z", optOut: true }); expect(mailerSpy).not.toHaveBeenCalled(); });
//                                                                                  ^^ stale call from the previous test
```

## Good Example

```python
# GOOD: each test builds its own state; a fixture per test cleans up after itself.
@pytest.fixture
def users() -> list[User]:
    return []     # fresh per test

def test_create_user(users):
    users.append(User("alice"))
    assert users == [User("alice")]

def test_create_two_users(users):
    users.append(User("alice"))
    users.append(User("bob"))
    assert len(users) == 2
```

```csharp
// GOOD: instance per test class; fresh repo per test method.
public class OrderTests
{
    private readonly OrderRepo _repo = new();   // xUnit creates a new instance per test
    [Fact] public void CreatesOrder() { _repo.Save(new Order(1)); Assert.NotNull(_repo.GetById(1)); }
    [Fact] public void FindsByCustomer() { _repo.Save(new Order(2) { CustomerId = 7 }); /* ... */ }
}
```

```ts
// GOOD: fresh fakes per test; the framework's beforeEach resets state.
test("sends welcome", () => {
  const mailer = new FakeMailer();
  const svc = new SignupService(mailer);
  svc.signup({ email: "a@b.c" });
  expect(mailer.sent).toHaveLength(1);
});

test("sends nothing on opt-out", () => {
  const mailer = new FakeMailer();
  const svc = new SignupService(mailer);
  svc.signup({ email: "x@y.z", optOut: true });
  expect(mailer.sent).toHaveLength(0);
});
```

## Exceptions

- **Read-only / immutable fixtures** (a frozen lookup table, a
  preloaded sample dataset, a compiled regex) MAY be shared at
  module/class level. The test for "is this a real exception" is
  whether any test mutates it; if anything writes, the fixture
  is no longer read-only.
- **Expensive global setup** (spinning up a database container,
  starting a browser) is acceptable as a session-level fixture
  *provided* each test isolates its own data within (its own
  schema, its own row prefix, its own browser context). The
  shared resource is the harness; per-test state is still
  independent.
- **Contract tests against an external system** that the test cannot
  control (a vendor's staging API) MAY require a specific input
  state to exist. Document the precondition explicitly and, when
  possible, gate the test behind a fixture that asserts the
  precondition rather than assuming it.

## Rationalizations

- **"It's faster if the next test reuses what the previous one
  built."** Until a test fails because someone added a third test
  that mutates the shared state, and now you have to bisect the
  order. The speed savings are dwarfed by the debugging cost the
  first time the suite goes flaky.
- **"`@pytest.mark.dependency` / `[Order]` solves this."** It does
  not — it codifies the dependency, making it harder to refactor
  and impossible to parallelise. The point of the rule is that the
  dependency should not exist at all.
- **"Setting up the world in every test is repetitive."** Then
  extract a fresh-per-test factory (a `make_user()` helper, a
  `FakeMailer.fresh()` constructor) and call it from each test.
  Repetitive setup is a refactor, not a reason to share state.
- **"My fakes have global state because they're patched into a
  module."** That's a sign of hidden dependencies (see ET-0010);
  fix the production code to take the fake as a parameter, and the
  test isolation problem disappears with it.
