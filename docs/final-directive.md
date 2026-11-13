# Inbox Helper Engineering Directive

Develop Inbox Helper in five explicitly authorized stages. Day 1 through Day 5
are implemented under explicit authorization.

## Architecture

Keep domain, application, infrastructure, provider integrations, and
persistence concerns separated. Business logic must depend on provider-neutral
contracts. Provider-specific requests, credentials, response parsing, and
errors belong inside adapters. Treat email content as untrusted, do not store
credentials in source, and never permit autonomous email dispatch.

## Delivery discipline

For each authorized day, plan before implementation, implement only that
scope, test success and failure paths, review security and maintainability,
update documentation, report actual validation results, then stop. Planned
work must not be documented as completed.
