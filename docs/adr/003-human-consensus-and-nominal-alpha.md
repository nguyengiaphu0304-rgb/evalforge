# ADR-003: provenance-bound human consensus and nominal alpha

## Status

Accepted for v0.3.

## Decision

Store human labels in a separate versioned artifact bound to the canonical
dataset and candidate hashes. Allow only pseudonymous annotator IDs and
pass/fail/abstain values. Resolve consensus explicitly and compute nominal
Krippendorff's alpha from auditable ordered-pair counts with exact arithmetic.
Omit annotator IDs from the derived report.

Do not add an LLM judge, provider SDK, free-text rationale, identity service, or
adjudication workflow in this milestone.

## Consequences

Agreement and deterministic-evaluator calibration are offline, reproducible,
and lineage-preserving. Abstentions and incomplete overlap are represented
without inventing labels. The report reduces identity propagation but is not
anonymous. Agreement cannot establish label validity or eliminate shared bias,
and the operational warning thresholds remain policy choices rather than
universal scientific cutoffs.
