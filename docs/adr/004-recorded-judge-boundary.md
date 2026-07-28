# ADR-004: recorded judge before live provider integration

## Status

Accepted for v0.4.

## Decision

Define a complete recorded-judge artifact before adding provider code. Bind each
record to a canonical request whose trusted policy and untrusted content are
separate fields. Restrict responses to structured decisions and allowlisted
reason codes. Preserve operational status and integer usage/cost metadata, then
calibrate against provenance-bound human evidence.

Do not add networking, credentials, provider SDKs, executable plugins, or
free-text rationales.

## Consequences

The provider boundary is reproducible, inspectable, and testable offline.
Prompt-like candidate content cannot structurally overwrite policy fields.
Failures and abstentions remain visible. However, request separation does not
prove model behavior; usage values are unauthenticated; and no real provider
privacy, retry, retention, or billing behavior has been validated.
