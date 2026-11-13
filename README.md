# Inbox Helper

Inbox Helper is a local-first email triage application. It includes validated
CSV ingestion and SQLite persistence, provider-neutral email classification,
persisted reply drafts with explicit human review, an urgency-prioritized
review queue, approved-only CSV export, bounded provider retry/health behavior,
and a Streamlit interface. Uploading a valid CSV automatically processes its
emails one at a time: classification is persisted, each successfully
classified email receives its own draft, and the Review Queue groups pending
drafts by the saved intent. The available LLM choices are deterministic
`mock` and local Ollama inference; cloud providers and email sending are not
implemented.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[ui,dev]"
cp .env.example .env
```

Configuration is read from environment variables or `.env`. Start the UI with:

```bash
streamlit run streamlit_app.py
```

The checked-in Streamlit settings bind to `127.0.0.1` and cap uploads at
10 MiB. Keep the application local: imported emails, drafts, and database
content may be sensitive.

The implemented providers are `mock` and local `ollama`. OpenAI and Gemini
remain unimplemented and fail explicitly. The mock's default response remains
`"Mock response"` and does not satisfy the structured classification or reply
schemas; classification and drafting in normal Mock Mode will therefore
report a safe validation error.

## Upload-to-review workflow

On the Inbox page, selecting a CSV starts the workflow automatically. Inbox
Helper validates the entire file before persisting it, then processes each
saved email independently through the configured provider, the existing
classification validator, and the reply-generation service. A successful
classification is saved before reply generation. Every generated reply is an
individual draft; intent groups organize drafts but never share a response.
After processing, the UI opens the Review Queue and reports classified,
drafted, and failed counts.

The upload fingerprint and per-email processing state are stored in SQLite.
Re-uploading the same file returns its existing email records, and completed
emails or emails with an existing draft are not classified or drafted again.
If one email fails, previously completed emails and other successful records
remain intact. The Review Queue separates processing failures from drafts
awaiting review, identifies the failed stage, and offers explicit retry only
for failures classified as transient. A failed reply-generation attempt keeps
its validated classification so retry does not repeat classification.
Permanent provider errors and invalid structured responses are not retried.
An interrupted processing claim becomes retryable after ten minutes.

Pending drafts are grouped by their stored classification intent, with the
existing urgency order retained inside each group. Editing, approval, and
rejection remain separate explicit human actions. Draft generation does not
approve or send email, and approved-only export behavior is unchanged.

## Ollama AI Mode

1. Install Ollama using the instructions for your operating system at
   [ollama.com/download](https://ollama.com/download).
2. In one terminal, start the local Ollama service:

   ```bash
   ollama serve
   ```

3. In another terminal, download the default compatible local model:

   ```bash
   ollama pull llama3.2
   ```

4. Configure Inbox Helper in `.env`:

   ```dotenv
   INBOX_HELPER_LLM_PROVIDER=ollama
   INBOX_HELPER_LLM_MODEL=llama3.2
   INBOX_HELPER_LLM_TIMEOUT=30.0
   INBOX_HELPER_LLM_TEMPERATURE=0.2
   OLLAMA_BASE_URL=http://localhost:11434
   INBOX_HELPER_DEMO_MODE=false
   ```

5. Start Inbox Helper:

   ```bash
   streamlit run streamlit_app.py
   ```

The UI identifies this as **Ollama AI Mode** and displays the configured model.
Inference runs against the local Ollama HTTP service; generated classification
and reply text still pass the existing Pydantic validators and drafts still
require explicit human review. Keep Ollama bound to a trusted local interface.
Ollama being unavailable produces an actionable error; the application does
not switch providers automatically.

To switch back to the default deterministic provider, set
`INBOX_HELPER_LLM_PROVIDER=mock` and `INBOX_HELPER_DEMO_MODE=false`. To use
predefined, schema-valid demonstration responses instead, set
`INBOX_HELPER_LLM_PROVIDER=mock` and `INBOX_HELPER_DEMO_MODE=true`. The UI
labels that choice **Demo Mode** and explains that its responses are not
AI-generated. Neither mode sends email or automatically approves drafts.

The mock health check reports the local mock adapter available. Ollama health
checking verifies reachability of its local tags endpoint; it does not run
inference or guarantee the configured model is available. Ollama request
timeouts use `INBOX_HELPER_LLM_TIMEOUT`.

## Day 1 CSV contract

CSV files must include `sender`, `subject`, and `body` columns. `id` and
`received_at` are optional; missing values are generated. `received_at` accepts
ISO 8601 date/time values. Subject and body may be empty, and supplied content
is preserved. Sender must be non-empty, but is not restricted to email-address
syntax. The entire file is validated before any records are saved. Emails can
be imported through `EmailIngestionService`. The local UI uses its
byte-ingestion path and atomically persists the validated upload before
starting per-email AI processing. Email, workflow, and draft records remain
local in the standard-library SQLite repositories.

Run tests (including the Streamlit AppTest coverage) with:

```bash
pytest
```

See [project intent](docs/intent.md), [final directive](docs/final-directive.md),
and [Day 1](docs/days/day-1.md) for scope and architecture. [Day 2](docs/days/day-2.md)
covers classification, [Day 3](docs/days/day-3.md) covers draft generation and
human review, [Day 4](docs/days/day-4.md) covers organization/export/reliability,
and [Day 5](docs/days/day-5.md) documents the Streamlit integration. See the
[development log](docs/development-log.md) and [unlearning notes](docs/unlearning.md)
for project history and design notes.
