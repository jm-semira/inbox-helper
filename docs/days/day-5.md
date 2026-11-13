# Day 5 — Integration and Final Validation

## Status: Implemented

Day 5 integrates the existing application workflow in a local Streamlit
presentation layer. Streamlit pages call application services through a
context-managed composition bundle; they do not issue SQL or create
repositories. SQLite remains the persistence layer, and repository resources
are closed after each Streamlit script run.

### Dashboard and inbox

The dashboard reports total imported emails, draft counts by status, and the
number of drafts with a stored classification snapshot. Classifications remain
transient until a draft is generated; no classification history was added.
The inbox lists persisted emails, shows source content as plain text, accepts
CSV uploads up to 10 MiB, and uses the existing validation and atomic SQLite
batch persistence path. It supports explicit classification and draft
generation through the existing application services.

### Review queue and export

The review page displays the existing pending-only queue in its established
intent and urgency order, including source email details. Draft edits are saved
explicitly and remain in `draft` status. Approval and rejection are separate
explicit actions; unsaved edits disable both decisions. Approved drafts are
never sent. The download uses the existing approved-only export service and
removes its temporary directory after reading the generated CSV.

Streamlit session state contains UI selections, JSON-compatible transient
classification results, upload digests, and rerun guards. Draft content remains
database-authoritative; the editor widget keeps only the current editing
session's text until the user explicitly saves it. A generated-email guard
prevents reruns in the same session from creating duplicate drafts.

### Demo Mode and security

Set `INBOX_HELPER_DEMO_MODE=true` with the `mock` provider to select the local
demo mock. The interface labels **Demo Mode** and states that responses are
predefined mock outputs, not actual AI-generated results. The mode still
passes outputs through the existing classifier, reply validator, and
persistence workflow. With Demo Mode off, the existing mock default response
remains `"Mock response"` and continues to fail structured validation as
before.

The optional Ollama adapter uses the local `/api/generate` endpoint in
non-streaming JSON mode, plus `/api/tags` for a separate health check. Set
`INBOX_HELPER_LLM_PROVIDER=ollama`, select a locally available model, and
configure the base URL, timeout, and temperature with the existing environment
variables. The UI labels **Ollama AI Mode** and displays the model name. No
automatic provider fallback occurs. OpenAI and Gemini remain unimplemented.

The Streamlit server binds to `127.0.0.1` by default. Streamlit's upload
setting and the inbox page enforce a 10 MiB upload cap. Email bodies,
subjects, sender values, and reply text are presented as plain text.
User-facing errors omit raw exception messages, prompts, and provider details.
There is no email sending or automatic approval.

### Run and validate

Install the optional UI and development dependencies and launch from the
repository root:

```bash
pip install -e ".[ui,dev]"
streamlit run streamlit_app.py
```

The UI tests use Streamlit AppTest and temporary SQLite databases. They cover
empty states, upload success/failure/size checks, classification, generation,
editing, explicit decisions, approved export selection, Demo Mode, safe errors,
temporary export cleanup, and duplicate-action behavior across reruns.

### Limitations

- Ollama requires the locally installed Ollama service and downloaded model.
  Mock default output is intentionally not schema-valid; Demo Mode is a
  demonstration fixture, not an AI model.
- Dashboard classification totals count persisted draft snapshots only;
  standalone classifications are not persisted.
- There is no activity-event store, email sending, or external email
  integration. Ollama is a local HTTP dependency; its health probe does not
  run inference.
