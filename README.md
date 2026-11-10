# Inbox Helper

Inbox Helper is an AI-native email triage project. The current implementation
includes the Day 1 foundation—validated CSV ingestion and SQLite persistence—
and Day 2 provider-neutral email classification with validated structured
output. The LLM contract has a local mock adapter; no external provider is
implemented.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Configuration is read from environment variables (or `.env`). The only
implemented LLM provider is `mock`; other configured providers fail clearly.
The mock's default response is not classification JSON, so classification
requires a mock response configured with the expected structured output.

## Day 1 CSV contract

CSV files must include `sender`, `subject`, and `body` columns. `id` and
`received_at` are optional; missing values are generated. `received_at` accepts
ISO 8601 date/time values. Subject and body may be empty, and supplied content
is preserved. Sender must be non-empty, but is not restricted to email-address
syntax. The entire file is validated before any records are saved. Emails can
be imported through `EmailIngestionService`, and persisted using the
standard-library SQLite repository.

Run tests with:

```bash
pytest
```

See [project intent](docs/intent.md), [final directive](docs/final-directive.md),
and [Day 1](docs/days/day-1.md) for scope and architecture. The
[Day 2](docs/days/day-2.md) describes the implemented classifier; [Day 3](docs/days/day-3.md),
[Day 4](docs/days/day-4.md), and [Day 5](docs/days/day-5.md) documents record
deferred work, not implemented features. See the [development log](docs/development-log.md)
and [unlearning notes](docs/unlearning.md) for project history and design notes.
