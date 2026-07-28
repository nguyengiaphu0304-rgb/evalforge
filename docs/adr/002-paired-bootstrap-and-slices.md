# ADR-002: paired bootstrap and provenance-bearing slices

## Status

Accepted for v0.2.

## Decision

Compare runs only on one shared dataset, retain the complete status transition
matrix, and estimate the pass-rate delta interval by resampling paired case
differences. Use a fully specified local generator rather than Python's global
random state. Keep slices in a separate versioned provenance-bearing artifact.

## Consequences

Comparisons are offline, reproducible, and auditable across Python versions.
They cannot compare unmatched datasets, estimate dataset-selection bias, prove
causality, or justify a general model ranking. Overlapping slices are allowed,
so consumers must not sum slice counts as if slices were disjoint.
