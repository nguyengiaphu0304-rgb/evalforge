# Recorded-judge contract

EvalForge v0.4 analyzes stored structured judge outcomes. It does not import a
provider SDK, construct a provider prompt, read credentials, or make a network
request.

## Canonical request boundary

Each request hash covers an `evalforge/judge-request-v1` object:

- `trusted`: adapter ID, policy SHA-256, response schema, and deterministic
  criteria.
- `untrusted`: case ID, case input, candidate status, and candidate output.

The fields remain separate throughout canonicalization. Instruction-like text,
JSON, delimiters, and role names in candidate data cannot become trusted fields
through parsing. A future live adapter must preserve this separation; the
current contract does not claim semantic resistance by any model.

## Recorded response

Every dataset case must have exactly one record. `ok` records contain only a
pass/fail/abstain decision and allowlisted reason codes. Timeout, error, and
truncated records carry no response. Free-text rationale is deliberately
excluded because it expands disclosure and injection surfaces without being
needed for deterministic calibration.

Attempts, input/output tokens, latency milliseconds, and cost in integer
micro-USD are bounded. They are auditable recorded values, not authenticated
provider billing.

## Calibration policy

Only judge pass/fail decisions against resolved human pass/fail consensus enter
the confusion matrix. Judge abstentions, operational non-success, human ties,
and insufficient human labels remain separate.

Evidence is `insufficient_evidence` when:

- fewer than 30 human cases are resolved;
- human nominal alpha is undefined or below 0.667;
- judge coverage of resolved human cases is below 95%; or
- any resolved human case has a non-success judge record.

Otherwise evidence is still only `descriptive_only`. Synthetic fixtures are
correctness evidence, not a model benchmark or deployment authorization.
