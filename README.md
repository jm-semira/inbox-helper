# Inbox Helper

Inbox Helper is a local-first email triage application. It includes validated
CSV ingestion and SQLite persistence, provider-neutral email classification,
persisted reply drafts with explicit human review, an urgency-prioritized
review queue, approved-only CSV export, bounded provider retry/health behavior,
and a Streamlit interface. The available LLM choices are deterministic
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
be imported through `EmailIngestionService`, and persisted using the
standard-library SQLite repository.

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
