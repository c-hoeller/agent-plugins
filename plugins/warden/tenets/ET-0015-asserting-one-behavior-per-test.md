---
id: ET-0015
title: Assert one behavior per test
type: best-practice
tier: 1
applies-to: any
since: 0.1.0
triggers:
  - writing a test whose body covers two unrelated behaviors with the same setup
  - naming a test `test_login_and_signup_and_password_reset` or similar conjunction-named test
  - reviewing a test where the failure message could mean any of several different broken things
  - deciding whether multiple `expect` / `Assert` calls belong in one test or in several
tags: [testing, assertions, focus]
related: [ET-0004, ET-0014]
---

## Rule

Each test verifies a single behavior: one input scenario producing
one observable outcome. Multiple assertions are fine when they are
**facets of the same behavior** — the fields of a single returned
object, the contents and length of a single returned list, the
status code and body of one HTTP response. They are not fine when
they assert independent behaviors that happen to share setup. When a
test fails, its name and the failing assertion together name the
broken behavior; if a single failing test could mean any of three
different bugs, the test is doing too much. Split it.

## Why

Multi-behavior tests fail with a message that names the *first*
broken assertion only — every assertion library short-circuits on
failure — so the second and third bugs are discovered only after the
first is fixed and CI runs again. They also discourage refactoring:
changing one behavior pays the cost of also reading and possibly
re-validating the unrelated assertions that share its setup, so
people stop refactoring and the code drifts. Single-behavior tests
turn a failure log into a reading-list of broken behaviors instead
of a riddle.

## Bad Example

```python
# BAD: one test, three independent behaviors. A failure tells you "something is wrong, somewhere".
def test_user_lifecycle():
    user = create_user("alice@example.com")
    assert user.id is not None                 # behavior 1: creation
    user.update(name="Alice")
    assert user.name == "Alice"                # behavior 2: update
    user.delete()
    assert get_user(user.id) is None           # behavior 3: deletion
```

```csharp
// BAD: same shape — three unrelated assertions sharing a single test.
[Fact]
public void OrderEndToEnd()
{
    var o = _service.Create(customerId: 7);
    Assert.NotNull(o.Id);
    _service.AddItem(o.Id, productId: 1);
    Assert.Single(_service.Get(o.Id).Items);
    _service.Cancel(o.Id);
    Assert.Equal(OrderStatus.Cancelled, _service.Get(o.Id).Status);
}
```

```ts
// BAD: independent assertions interleaved.
test("user flow", () => {
  const u = api.signup({ email: "a@b.c" });
  expect(u.email).toBe("a@b.c");
  expect(api.login("a@b.c", "wrongpass")).toBe(null);
  expect(api.login("a@b.c", "correctpass")).not.toBe(null);
});
```

## Good Example

```python
# GOOD: one test per behavior; failures point straight at the broken contract.
def test_create_user_returns_id():
    user = create_user("alice@example.com")
    assert user.id is not None

def test_update_user_changes_name():
    user = create_user("alice@example.com")
    user.update(name="Alice")
    assert user.name == "Alice"

def test_delete_user_removes_record():
    user = create_user("alice@example.com")
    user.delete()
    assert get_user(user.id) is None

# Multiple assertions on facets of ONE behavior are fine:
def test_create_user_returns_full_record():
    user = create_user("alice@example.com")
    assert user.email == "alice@example.com"
    assert user.id is not None
    assert user.created_at is not None       # all facets of "what create_user returns"
```

```ts
// GOOD: one behavior per test; one rejected-login test asserts both facets of that behavior.
test("signup returns a user with the given email", () => {
  const u = api.signup({ email: "a@b.c" });
  expect(u.email).toBe("a@b.c");
});

test("login with wrong password returns null and does not create a session", () => {
  api.signup({ email: "a@b.c", password: "correctpass" });
  const result = api.login("a@b.c", "wrongpass");
  expect(result).toBeNull();
  expect(api.activeSessions()).toHaveLength(0);   // facet of the same "rejected" behavior
});
```

## Exceptions

- **Multiple assertions on one returned value** (every field of a
  DTO, every property of an object, length+contents of a list) are
  facets of one behavior — keep them in a single test. The test is
  asking "what does this call return", and the assertions describe
  the answer.
- **Snapshot / golden-file tests** that assert a single artefact
  (a rendered HTML page, a generated SQL string) match a fixture are
  one-behavior tests even when the artefact is large. The behavior
  is "produces this output".
- **Property-based / parameterised tests** that run the same single
  behavior with many inputs are still one behavior — the
  parameterisation is the input set, not multiple behaviors.
- **End-to-end smoke tests** whose explicit purpose is "the whole
  flow works at all" MAY chain steps. They are smoke tests, not
  unit/behavior tests, and complement (do not replace) per-behavior
  tests at the unit and integration levels.

## Rationalizations

- **"Setup is expensive, I want to amortise it."** Either the setup
  is reused fixture code (extract it; ET-0014 still applies), or
  the steps actually share data and timing (a smoke test, see the
  exception). Squeezing unrelated assertions into one test to save
  setup cost trades a one-time refactor for a permanent debugging
  tax.
- **"The behaviors are part of the same user journey."** User
  journeys are end-to-end tests; they live alongside, not in place
  of, per-behavior unit tests. The journey test passes only when
  every step works; the unit tests tell you *which* step broke.
- **"Splitting will create three nearly-identical tests."** Three
  near-identical tests are exactly right — they all share setup and
  differ in one assertion, which is what a parameterised test or a
  shared fixture is for. The shape of three small tests is much
  cheaper to read than one big one once any of them fails.
