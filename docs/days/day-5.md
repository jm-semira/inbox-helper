# Day 5 — Integration and Final Validation

## Status: Implemented

Day 5 integrates the existing application workflow in a local Streamlit
presentation layer. Streamlit pages call application services through a
context-managed composition bundle; they do not issue SQL or create
repositories. SQLite remains the persistence layer, and repository resources
are closed after each Streamlit script run.

### Dashboard and upload-to-review workflow

The dashboard reports total imported emails, draft counts by status, and the
number of drafts with a stored classification snapshot. Classifications remain
available on processing outcomes and are also snapshotted on generated drafts.
The inbox lists persisted emails, shows source content as plain text, and
accepts CSV uploads up to 10 MiB. Selecting a file validates it completely
before atomic persistence; each saved email is then classified and passed to
the existing reply-generation service. A validated classification is
persisted before reply generation, and each email gets its own draft. The UI
then opens the Review Queue and reports batch counts.

The upload fingerprint is stored in SQLite so an exact re-upload resolves to
the original email records, including rows whose IDs were generated at first
import. Per-email workflow state records completed, in-progress, classification
failure, or reply-generation failure outcomes. Failures for one email do not
roll back earlier or later successful emails. A draft-generation failure
retains its classification snapshot for recovery.

Only explicitly transient provider failures can be retried through the
Review Queue; the existing provider wrapper remains responsible for its
bounded completion retry. Invalid structured output and permanent provider
errors are recorded without a retry action. An interrupted operation becomes
eligible for an explicit retry after its ten-minute processing lease expires.
Retries continue from the last persisted successful stage and do not generate
a second draft when one already exists.

### Review queue and export

The review page displays the existing pending-only queue in its established
intent and urgency order, including source email details. Draft edits are saved
explicitly and remain in `draft` status. Approval and rejection are separate
explicit actions; unsaved edits disable both decisions. Approved drafts are
never sent. The download uses the existing approved-only export service and
removes its temporary directory after reading the generated CSV.

Streamlit session state contains UI selections and upload digests. The
database is authoritative for email processing state and draft content; the
editor widget keeps only the current editing session's text until the user
explicitly saves it. Both session upload guards and persisted upload identity
prevent reruns or exact re-uploads from repeating successful LLM operations.

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
empty states, automatic upload processing, failure display and retry,
upload-size checks, editing, explicit decisions, approved export selection,
Demo Mode, safe errors, temporary export cleanup, and duplicate-action
behavior across reruns. Application tests cover per-email isolation,
classification retention, idempotency, existing-draft preservation, and
compatibility with pre-workflow database records.

### Limitations

- Ollama requires the locally installed Ollama service and downloaded model.
  Mock default output is intentionally not schema-valid; Demo Mode is a
  demonstration fixture, not an AI model.
- Dashboard classification totals count persisted draft snapshots only;
  processing classifications without drafts are tracked in workflow state but
  are not included in that dashboard metric.
- There is no activity-event store, email sending, or external email
  integration. Ollama is a local HTTP dependency; its health probe does not
  run inference.
