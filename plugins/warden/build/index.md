# Warden — Engineering Tenets Index

One line per tenet. Format: `ET-NNNN — <title> — <type> — <severity> — [<tags>]`.

- `ET-0001` — Never lower access modifiers for testing — anti-pattern — high — applies-to: any — tags: [testing, encapsulation, oop]
- `ET-0002` — Never silently swallow failures — anti-pattern — high — applies-to: any — tags: [error-handling, observability, reliability]
- `ET-0003` — Validate at trust boundaries, trust the core — best-practice — high — applies-to: any — tags: [validation, boundaries, defensive-programming, types]
- `ET-0004` — Tests assert observable behavior, not implementation — best-practice — high — applies-to: any — tags: [testing, mocks, refactoring, behavior]
- `ET-0005` — Comments explain why, not what — best-practice — medium — applies-to: any — tags: [comments, documentation, readability]
