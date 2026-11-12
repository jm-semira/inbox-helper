# Day 4 — Organization, Export and Reliability

## Status: Implemented

Day 4 adds grouping and prioritization for pending reply drafts, approved-only
CSV export, a provider health check, and bounded completion retries.

### Review queue

The application-level `ReviewQueueService` uses each draft's persisted
classification snapshot. Snapshots are JSON envelopes with `schema_version: 1`
and a `classification` object serialized from the existing Pydantic
`EmailClassification` model. A nullable SQLite migration preserves existing
Day 3 rows; drafts without snapshots appear in an explicit unclassified group.
There is no automatic reclassification.

Only undecided drafts are queried. Intent groups use an explicit application
order: job application, interview scheduling, application status, general
inquiry, other, then unclassified. Inside a group, urgency order is critical,
high, normal, low, with missing or unknown values last. Ties use oldest source
email received time, then oldest draft creation time, then draft ID. Multiple
pending drafts for one email remain separate queue items.

### Approved reply export

The exporter writes UTF-8 CSV with fixed columns: `draft_id`,
`source_email_id`, `sender`, `subject`, `reply_text`, `approved_at`. The
repository query selects only approved drafts with a decision timestamp;
`reply_text` is the current edited text. Source email ID remains explicit.
Standard CSV quoting handles commas, quotes, and embedded newlines. Export
prefixes formula-like cells and cells with dangerous leading control/format
characters; stored values are not changed. The target is replaced only after
a complete temporary-file write. Export does not send email.

### Provider reliability and diagnostics

`RetryingLLMProvider` wraps the unchanged `complete(prompt) -> str` contract at
the provider factory boundary. It makes at most two total attempts, retries
only `TransientLLMProviderError` (including `LLMProviderTimeoutError`), and
re-raises the final transient exception unchanged. Permanent errors,
structured-output errors, and persistence failures are not retried.

Provider health is a separate capability and does not use completion retries.
The mock reports healthy deterministically. There are no real provider
adapters, so Day 4 does not claim network health or actual network timeout
enforcement. Timeout configuration is finite, positive, and capped at 300
seconds for future adapter use.

Retry and export logs contain generic operation/error diagnostics only; they
do not include prompts, email content, reply text, credentials, or raw provider
exception messages.

No UI, email dispatch, external provider, or Day 5 functionality is included.
