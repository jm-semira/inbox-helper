# Unlearning Notes

This document captures assumptions, habits, and implementation approaches that
I reconsidered while building Inbox Helper.

The goal is to document not only what I learned, but also what I stopped
assuming or doing.

## Day 1

### 1. Don't couple application logic to an LLM provider

**Previous assumption:** Application services can directly use a particular
LLM SDK because that is the provider selected for the project.

**What changed:** Provider-specific integrations belong behind a
provider-neutral interface. Application logic should depend on the contract,
not the vendor.

**New approach:** Keep the provider boundary small and introduce provider
implementations independently of business logic.

### 2. Don't build abstractions before they are needed

**Previous assumption:** A reusable interface should anticipate every
operation that future providers or features might require.

**What changed:** An abstraction becomes harder to maintain when it includes
operations without a current use case.

**New approach:** Start with the smallest useful contract and expand it when
an authorized requirement justifies the change.

### 3. Don't confuse a working mock with a working AI feature

**Previous assumption:** Having an LLM provider implementation means the AI
functionality is already in place.

**What changed:** A mock provider validates the integration boundary, not the
actual intelligence or behavior of a classifier or reply generator.

**New approach:** Keep mock behavior explicit and introduce real AI
capabilities only in their authorized development stages.

### 4. Don't assume partial CSV imports are always better

**Previous assumption:** An importer should save valid rows even when other
rows are invalid.

**What changed:** Partial imports introduce additional questions about
rejected records, retries, and duplicate handling.

**New approach:** Use all-or-nothing validation until partial recovery becomes
an explicit product requirement.

### 5. Don't postpone resource ownership decisions

**Previous assumption:** Database connection management can be addressed when
the application becomes larger.

**What changed:** Even a small application needs a clear owner for resources
and a predictable cleanup lifecycle.

**New approach:** Make resource ownership explicit through the composition
root and repository lifecycle.

---

## Continuing this document

For each subsequent development day, record:

- What assumption did I initially make?
- What did implementation or review reveal?
- What approach did I decide to stop using?
- What principle will guide future decisions?

Avoid turning this document into a list of features, technical decisions, or
future tasks. Those belong in the development log and architecture
documentation.
