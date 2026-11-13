# Unlearning Notes

This document captures engineering assumptions, implementation approaches, and decision-making habits that I have reconsidered while building Inbox Helper.

The objective is not simply to document what was learned during development, but to identify assumptions that proved incomplete, approaches that introduced unnecessary complexity, and engineering principles that should influence future decisions.

These notes focus on the reasoning behind technical decisions rather than documenting features or implementation details. The goal is to develop better engineering judgment through deliberate reflection.

## Day 1

### 1. Avoid coupling application logic to infrastructure providers

An application should not depend directly on a specific infrastructure or external service implementation when that dependency can reasonably be isolated behind a stable contract.

Provider-specific behavior belongs behind an abstraction, allowing application services to operate independently of the underlying implementation.

The important distinction is that abstraction should protect application boundaries, not introduce unnecessary indirection. The contract should represent actual application requirements rather than anticipate every possible provider capability.

### 2. Avoid designing abstractions around hypothetical requirements

Abstraction is valuable when it reduces coupling or establishes a meaningful boundary. It becomes counterproductive when designed around requirements that do not yet exist.

Starting with a small, well-defined contract makes the design easier to understand and maintain. Additional capabilities should be introduced when supported by a concrete use case, rather than speculative extensibility.

Good architecture is not measured by how many future scenarios it anticipates, but by how effectively it accommodates change without unnecessary complexity.

### 3. Distinguish infrastructure validation from actual application capability

A working mock implementation demonstrates that an integration boundary and application workflow behave as expected. It does not demonstrate that the actual external capability works.

Mocks are useful for deterministic testing and isolating application behavior, but they should not be mistaken for substitutes for real integration testing.

The distinction between simulated behavior and production capability should remain explicit in both implementation and user-facing interfaces.

### 4. Treat data ingestion semantics as an architectural decision

Partial imports are not inherently better than all-or-nothing imports. They introduce additional considerations around failure reporting, duplicate handling, recovery, and consistency.

The appropriate ingestion strategy depends on the business requirements and the guarantees expected by downstream workflows.

When partial processing is not an explicit requirement, atomic ingestion provides a simpler and more predictable starting point.

### 5. Establish resource ownership and lifecycle boundaries early

Resource lifecycle management should be an explicit architectural responsibility rather than something distributed across application components.

Composition roots should own dependency construction and initialization, while repositories and services should have clearly defined responsibilities.

Making ownership explicit reduces hidden dependencies, simplifies testing, and makes application behavior easier to reason about.

## Day 2

### 1. Do not mistake prompt instructions for security enforcement

Prompt engineering can influence model behavior, but it cannot establish a reliable security boundary.

External content, particularly user-provided or email-derived content, must be treated as untrusted input even when the prompt explicitly instructs the model to ignore embedded instructions.

Prompt design is a mitigation, not an enforcement mechanism. Application-level validation and authorization must remain responsible for determining which operations and outputs are acceptable.

### 2. Treat model output as untrusted external data

A successful model response does not automatically constitute a valid application response.

External model output should pass through the same discipline applied to other integration boundaries: parsing, schema validation, semantic validation, and explicit error handling.

The application must retain control over its domain rules rather than allowing model-generated content to define application behavior.

## Day 3

### 1. Separate generation from authorization

Generating a response and authorizing that response are fundamentally different responsibilities.

A generated response is a proposal, not an approved business action. Editing, approval, and rejection should remain explicit operations with independently defined state transitions.

This separation is particularly important in workflows involving external communication or decisions that affect users.

Automation should assist decision-making without silently assuming the authority to make decisions on behalf of the user.

## Day 4

### 1. Retry based on failure semantics, not convenience

Retries are not a universal solution to unreliable integrations.

Retrying permanent failures wastes resources and can make an already failing workflow more difficult to diagnose. Conversely, transient failures may justify another attempt.

Retry policies should be based on failure classification, bounded attempts, and explicit timeout limits.

Reliability comes from understanding failure behavior and applying an appropriate recovery strategy, not simply repeating operations until they succeed.

### 2. Separate persistence from eligibility for downstream operations

The fact that a record exists in persistent storage does not mean it is eligible for every subsequent operation.

Persisted data may represent different lifecycle states, and downstream operations must respect those states explicitly.

For example, generating a draft should not implicitly authorize its export or external use.

Eligibility rules should be enforced within the application layer rather than relying exclusively on UI restrictions or assumptions about how records are created.

## Day 5

### 1. Keep presentation responsibilities separate from application workflows

A user interface should coordinate user interactions and present application state. It should not become the primary owner of business rules or workflow orchestration.

When application behavior is embedded directly into UI components, it becomes harder to test independently and reuse across other interfaces.

Application services should own workflow decisions, repositories should own persistence concerns, and the UI should remain a consumer of those capabilities.

This separation allows the application to evolve without making its business behavior dependent on a particular presentation framework.

### 2. Choose implementation boundaries based on risk and dependency, not process preference

Breaking work into smaller phases can improve visibility, isolate risks, and provide useful review checkpoints. However, excessive decomposition can introduce repeated planning, context switching, duplicated validation, and unnecessary coordination overhead.

Phased implementation should be used when the work benefits from independent verification or when later decisions depend on earlier results.

When requirements and dependencies are already understood, related implementation work can be consolidated into a larger delivery unit without sacrificing review quality.

The objective is not to maximize the number of implementation phases, but to establish boundaries that reduce delivery risk while maintaining engineering control.

### 3. Treat external model responses as untrusted integration results

A successful HTTP response only confirms that the request was processed at the transport level. It does not guarantee that the returned content satisfies application requirements.

Model-generated output can be incomplete, malformed, or inconsistent with the expected schema, even when the provider reports success.

Structured output constraints can improve consistency, but application-side validation must remain authoritative.

The integration should fail explicitly when the response cannot be interpreted safely rather than weakening domain validation to accommodate inconsistent model behavior.

### 4. Do not equate model availability with model suitability

An available model is not necessarily suitable for every application task.

Model selection should account for output consistency, structured response adherence, latency, resource consumption, and the complexity of the task.

A smaller model may be sufficient for straightforward classification, while more demanding tasks may require a more capable model.

Model evaluation should be based on actual application behavior and validation results rather than availability or inference speed alone.

---

## Closing Reflection

One of the recurring themes throughout this project is the distinction between making something work and engineering it to behave predictably.

A working implementation is only one part of the responsibility. Equally important are clear boundaries, explicit ownership, controlled failure behavior, data integrity, and preserving human authority where automated decisions are involved.

The objective is not to introduce abstractions or processes for their own sake. It is to make deliberate engineering decisions, understand their trade-offs, and avoid adding complexity without a corresponding benefit.

These notes should continue to evolve as new implementation decisions challenge existing assumptions.