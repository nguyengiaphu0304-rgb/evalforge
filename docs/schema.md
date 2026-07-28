# Evaluation schema contract

`evalforge/v1` datasets require provenance (`source`, `license`,
`retrieved_at`, and upstream `schema_version`) plus one or more cases. Each case
has a stable ID, input text, and one or more uniquely identified criteria.

Supported deterministic criteria:

- `exact_text`: NFC-normalized full-string equality.
- `contains_text`: NFC-normalized required substring.
- `json_equal`: strict structural equality after duplicate-key rejection,
  non-finite-number rejection, key sorting, and NFC normalization.

Candidate statuses are `ok`, `timeout`, and `error`. Only `ok` carries text and
is scored. Missing cases remain explicit. Unknown IDs fail closed.

Limits: 1 MiB per artifact, 1,000 cases or outputs, 20 criteria per case,
100,000 Unicode code points per text field, 64-character identifiers, and JSON
depth 32.

SHA-256 establishes change detection and lineage, not publisher identity.

## Slice artifacts

`evalforge/slices-v1` requires provenance and one to 100 slice definitions.
Each slice has a normalized ID and one or more unique, known case IDs. Slices
may overlap. Ordering is canonicalized; duplicate, empty, unknown, excessive,
or unexpected values fail closed.

## Comparison reports

`evalforge/comparison-v1` binds the canonical dataset, candidate A, candidate B,
and slice hashes. It records the method version, unsigned 64-bit seed, resample
count, confidence, thresholds, complete 5×5 status transitions, pass-indicator
delta, interval, warnings, and per-slice summaries. Prompt and output bodies are
not copied into the report.
