# Day 3 — Reply Generation and Human Review

## Status: Implemented

Day 3 adds provider-neutral reply drafting and a persisted human-review
lifecycle. A draft is never sent. Generation, editing, approval, and rejection
are separate operations; approval is not connected to dispatch.

### Draft generation

`ReplyDraftService` receives an `Email` and its `EmailClassification` and
uses the existing `complete(prompt) -> str` provider contract. The structured
provider response is validated as `ReplyGenerationOutput`. Invalid JSON,
missing fields, incorrect types, or inconsistent human-input details raise
`ReplyGenerationError`; provider failures remain `LLMProviderError`.

The prompt JSON-encodes email subject and body as explicitly untrusted data,
prohibits following instructions embedded in the email, and asks the model not
to invent names, dates, schedules, requirements, policies, or commitments.
When details are missing, the model may provide a neutral response and mark
that human input is required with a reason. Prompting cannot guarantee
grounding or prevent prompt injection, so the result remains a draft for human
review.

### Draft state and persistence

Each generated draft has a unique ID and references an existing ingested email.
SQLite enforces this relationship with a foreign key. The record preserves
`original_generated_text` separately from editable `current_text`, along with
the optional human-input warning/reason, status, timestamps, and decision
timestamp.

Allowed lifecycle:

- Generation creates a new `draft`; generating again creates another record.
- Editing changes only `current_text`, is allowed only in `draft`, and never
  invokes the LLM or changes status.
- Approval or rejection requires an explicit operation while status is `draft`.
- `approved` and `rejected` are terminal. Repeated or conflicting decisions
  and edits after a decision are rejected.

Repository updates use conditional SQLite `UPDATE` statements that require
`status = 'draft'` and no prior decision. This makes concurrent decisions
atomic: only one can succeed. A human-input warning does not change lifecycle
status and does not imply approval or rejection.

The reply service is independently constructed and owns a SQLite draft
repository. No email sending, external LLM integration, UI, grouping, or export
is included.
