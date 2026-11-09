# Day 1 — Foundation and Architecture

## Status: Implemented

- Python source package organized into domain, application, and infrastructure.
- Environment-based application settings and logging utilities retained.
- Email data contract and validated CSV ingestion implemented.
- SQLite persistence and repository boundary implemented.
- Provider-neutral LLM contract and mock adapter implemented.
- Automated tests and initial documentation added.

CSV requires `sender`, `subject`, and `body`; `id` and `received_at` are
optional. Files are validated before persistence. Only the mock LLM adapter is
available. Subject and body fields may be empty or whitespace-only because
valid incoming email can omit either; supplied content is preserved. Sender
must be non-empty, but no email-address syntax is required by the Day 1
contract.

## Deferred

Classification, intent and urgency detection, prompt-injection defenses,
reply drafting, human review workflows, grouping, export, health checks, and
the Streamlit interface are not implemented.
