# Development Log

## Day 5 — Integration and Final Validation

- Added an optional Streamlit UI with a context-managed application service
  bundle, dashboard, inbox, and pending-draft review navigation.
- Added email browsing and dashboard aggregate services, uploaded-byte CSV
  ingestion with a 10 MiB limit, and source email content in review projections.
- Added explicit UI actions for classification, persisted draft generation,
  editing, approval/rejection, and approved-only CSV download. Session guards
  prevent duplicate upload and draft-generation actions on reruns.
- Added opt-in Demo Mode with predefined schema-valid mock outputs; the
  original mock default remains unchanged. The UI clearly identifies demo
  outputs as not actual AI-generated results.
- Bound Streamlit to loopback by default, rendered email/draft content as plain
  text, used safe error messages, and cleaned temporary export directories.
- Added AppTest coverage for empty states and the import/classify/generate/edit/
  decide/export workflow, plus rerun, size-limit, error, and Demo Mode cases.
- No cloud provider, email sending, automatic approval, or non-local network
  health behavior was added. Ollama is accessed only through its local HTTP
  adapter.

## Day 4 — Organization, Export and Reliability

- Persisted the Day 3 generation-time classification as a versioned JSON
  snapshot; migrated existing draft tables with a nullable column and retained
  legacy drafts as unclassified.
- Added an application-level pending-draft queue with explicit intent and
  urgency ordering, plus deterministic tie-breaks and lifecycle filtering.
- Added approved-only CSV selection and atomic UTF-8 CSV export using current
  edited text, source IDs, quoting, and export-only spreadsheet formula
  protection.
- Added one bounded completion retry wrapper for explicit transient provider
  errors and a separate mock health-check capability. The mock default and
  `complete(prompt) -> str` contract remain unchanged.
- Added safe retry/export diagnostics and tests for migration, queue ordering,
  CSV safety, retry classification, and provider health. No real network
  provider or timeout enforcement is available in this repository.
- No email sending, UI, or Day 5 feature was implemented.

## Day 3 — Reply Generation and Human Review

- Added provider-neutral reply generation using the existing LLM contract and
  strict Pydantic response validation; provider and generation-output errors
  remain distinct.
- Added persisted SQLite drafts with separate original/current text, optional
  human-input warning and reason, source-email foreign key, and lifecycle
  timestamps.
- Added explicit edit, approve, and reject operations. Conditional SQLite
  updates enforce terminal decisions atomically across repository connections.
- Added independent reply-service composition and deterministic tests for
  grounding prompts, invalid output, provider failure, editing, persistence,
  source integrity, terminal transitions, and conflicting concurrent
  decisions.
- No email sending, external provider, UI, or Day 4/5 feature was implemented.

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
