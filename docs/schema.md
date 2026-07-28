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

## Human-label artifacts

`evalforge/human-labels-v1` requires provenance, the exact canonical dataset and
candidate SHA-256 hashes, and one or more annotations. Each annotation contains
only a pseudonymous annotator ID, known case ID, and `pass`, `fail`, or
`abstain`. Each annotator/case assignment is unique. Identity attributes,
free-text notes, unknown fields, duplicate normalized IDs, and lineage mismatch
fail closed.

Artifacts are limited to 50 annotators and 50,000 annotations under the common
1 MiB limit. Ordering is canonicalized by case and annotator.

`evalforge/human-evidence-v1` records vote counts and unanimous, majority, tied,
or insufficient consensus per case; nominal Krippendorff's alpha components;
identity-free pair overlap; and an evaluator-versus-human confusion matrix.
Missing, timeout, and error evaluator states remain explicit. The envelope has a
payload checksum and must reproduce byte-for-byte from all three source
artifacts.

## Recorded-judge artifacts

`evalforge/judge-records-v1` binds a complete set of records to the canonical
dataset and candidate hashes. Configuration contains normalized adapter,
provider, model, model-version, response-schema identifiers, and a lowercase
policy SHA-256. Endpoints, credentials, provider request IDs, and free text are
not schema fields.

Every dataset case has exactly one record whose `request_sha256` must match the
recomputed `evalforge/judge-request-v1` envelope. That envelope stores trusted
policy, response schema, and criteria separately from untrusted case input,
candidate status, and candidate output.

Statuses are `ok`, `timeout`, `error`, and `truncated`. Only `ok` has a response:
one `pass`, `fail`, or `abstain` decision and one to ten allowlisted reason
codes. Attempts, input/output tokens, latency milliseconds, and cost in
micro-USD are bounded non-boolean integers.

`evalforge/judge-evidence-v1` records artifact lineage, non-sensitive
configuration, aggregate statuses/decisions/usage, and human-calibrated confusion
counts. It excludes request bodies, request hashes, candidate outputs, prompts,
annotator IDs, and exception text. The checksum envelope must reproduce
byte-for-byte from all source artifacts.
