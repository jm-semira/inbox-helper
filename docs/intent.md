# Project Intent

Inbox Helper is intended to help a person understand and organize incoming
email. The five-day roadmap introduces AI classification, reply drafts, human
review, export, and a user interface in stages.

## Current state

The Day 1 foundation is implemented: a validated email data contract, CSV
ingestion, SQLite persistence, logging utilities, and a provider-neutral LLM
contract backed by a deterministic mock. Day 2 adds provider-neutral email
classification with validated intent, urgency, confidence, and explanation
fields. Day 3 adds SQLite-persisted reply drafts with explicit human approval
or rejection. Day 4 adds classification snapshots on drafts, an organized
pending review queue, approved-only CSV export, and bounded provider
retry/health behavior. Day 5 adds persisted per-email processing outcomes and a
local Streamlit interface that orchestrates ingestion, classification,
individual draft generation, recovery, review, and approved-only export. Day 5
also adds local Ollama inference alongside the existing
mock provider. Demo Mode uses predefined responses, not actual AI-generated
results. No cloud LLM provider or email sending is implemented.

Incoming email content must be treated as untrusted. External providers must
remain isolated behind adapters; secrets must come from environment or secure
configuration; any future outbound action must retain a human approval
boundary.
