# Unlearning Notes

- Keep the Day 1 provider interface intentionally small. Expand it only when
  an authorized use case requires additional operations.
- The mock provider exists to exercise the provider boundary; it is not an
  email classifier or reply generator.
- CSV validation is all-or-nothing. Revisit partial-row recovery only if a
  future requirement defines how users inspect and resolve rejected rows.
- The SQLite repository owns a connection and is intended for a single
  application context. Revisit lifecycle and concurrency needs when an
  authorized interface or deployment model requires them.
