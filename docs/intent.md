# Project Intent

Inbox Helper is intended to help a person understand and organize incoming
email. The five-day roadmap introduces AI classification, reply drafts, human
review, export, and a user interface in stages.

## Current state

Only the Day 1 foundation is implemented: a validated email data contract,
CSV ingestion, SQLite persistence, logging utilities, and a provider-neutral
LLM contract backed by a deterministic mock. No email is sent by this
application.

Incoming email content must be treated as untrusted. External providers must
remain isolated behind adapters; secrets must come from environment or secure
configuration; any future outbound action must retain a human approval
boundary.
