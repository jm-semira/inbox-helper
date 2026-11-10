# Day 2 — AI Classification and Intent Detection

## Status: Implemented

Day 2 adds provider-neutral classification of one email at a time. The
classifier returns a validated Pydantic result and does not persist it. The
existing synchronous `complete(prompt) -> str` provider contract remains
unchanged. The deterministic mock remains the only configured implementation;
its default response is still `"Mock response"` and is intentionally not a
valid classification.

### Classification schema

- Intent: `job_application`, `interview_scheduling`, `application_status`,
  `general_inquiry`, or `other`.
- Urgency: `low`, `normal`, `high`, or `critical`.
- Confidence: a numeric value from 0.0 through 1.0, representing the model's
  self-assessment only—not proof of correctness or an approval signal.
- Explanation: a concise, non-empty rationale.

Urgency reflects evidence of time pressure rather than importance or a need
for any response. The prompt prohibits inventing deadlines and says not to
infer urgency only from forceful wording such as "urgent" or "ASAP"; absent
sufficient evidence, it directs the model to `normal`. `high` is for concrete
deadlines generally within two business days with meaningful consequences;
`critical` is for an imminent deadline or serious active issue requiring
attention now or today. `low` is informational or optional with no apparent
need for prompt response.

### Application behavior and limitations

`EmailClassifier` accepts the existing provider port and an `Email`, encodes
subject and body as JSON data in the prompt, and validates the provider text
against the strict result model. Provider call failures surface as
`LLMProviderError`; malformed JSON and invalid classification data surface as
`ClassificationError`. No fallback classification is produced. The
composition root exposes classification construction separately from the
Day 1 ingestion service; it does not connect classification to ingestion or
open a database for classification.

The prompt identifies email content as untrusted and provides explicit
classification rules. This framing is a mitigation, not a guarantee against
prompt injection. The synchronous provider contract has no timeout support.
No actual external provider adapter, classification persistence, reply
generation, approval workflow, grouping, export, or UI is implemented.
