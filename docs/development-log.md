# Development Log

## Day 5 — Integration and Final Validation

- Added an optional Streamlit UI with a context-managed application service
  bundle, dashboard, inbox, and pending-draft review navigation.
- Added an application-level upload workflow that atomically ingests validated
  CSV bytes, classifies each email, persists the classification, and generates
  one independent draft per successfully classified email.
- Added SQLite upload fingerprints and per-email processing outcomes. Exact
  re-uploads reuse original email identities; processing failures remain
  isolated, successful steps persist independently, and retries resume without
  repeating completed classification or creating another draft.
- Added automatic upload processing with per-batch counts, a recoverable
  processing-issues section, and separate intent-grouped pending drafts with
  source details. Transient failures can be explicitly retried; malformed
  structured output and permanent provider failures cannot.
- Retained explicit draft editing, approval/rejection, and approved-only CSV
  download. Editing does not approve, and neither classification nor draft
  generation sends email.
- Added opt-in Demo Mode with predefined schema-valid mock outputs; the
  original mock default remains unchanged. The UI clearly identifies demo
  outputs as not actual AI-generated results.
- Bound Streamlit to loopback by default, rendered email/draft content as plain
  text, used safe error messages, and cleaned temporary export directories.
- Added application and AppTest coverage for batch processing, per-email
  failure recovery, classification persistence, duplicate uploads, migration
  compatibility, empty states, human review, export, size limits, and reruns.
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
