# Development Log

## Day 2 — AI Classification and Intent Detection

- Added a strict Pydantic classification result with five intent categories,
  four urgency levels, confidence, and a concise explanation.
- Added a provider-independent email classification service using the existing
  `complete(prompt) -> str` contract; classification output is validated and
  is not persisted.
- Distinguished provider failures (`LLMProviderError`) from invalid structured
  output (`ClassificationError`).
- Added independent composition-root construction for classification without
  changing the Day 1 ingestion service or opening its database.
- Kept the mock provider's default response unchanged and added deterministic
  tests using configured JSON responses. No external provider integration or
  Day 3+ workflow was added.

## Day 1 — Foundation and Architecture

- Added the initial email domain model, CSV reader, ingestion service, and
  SQLite repository.
- Added the LLM provider contract and mock adapter; other configured providers
  fail explicitly because they are not implemented.
- Added tests for ingestion validation, SQLite atomicity, provider selection,
  and sensitive-data redaction.
- Added project overview, intent, directive, roadmap-status, and design-note
  documentation.
- Completed targeted Day 1 corrections: documented and tested acceptance of
  empty subject/body content, verified emitted-log redaction for common
  credential formats and formatted arguments, and added a context-managed
  composition root that closes SQLite resources.
- Expanded ingestion and persistence tests for empty and header-only CSV files,
  invalid timestamps, duplicate IDs, and transaction rollback.
