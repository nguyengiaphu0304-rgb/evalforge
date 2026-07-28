# ADR-001: deterministic offline core

## Status

Accepted for v0.1.

## Decision

EvalForge begins with recorded outputs and deterministic criteria. All artifacts
are strict, bounded, versioned, canonicalized, and independently replayed.
Missing and non-success outputs stay in the denominator.

## Consequences

The first milestone is reproducible, inspectable, and provider-independent. It
cannot evaluate open-ended quality, establish statistical significance, or
replace human review. LLM-as-a-judge and live provider adapters require separate
threat, calibration, privacy, and reliability work.
