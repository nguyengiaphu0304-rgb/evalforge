# ADR-005: Canonical release evidence and source archives

## Status

Accepted for the v1.0.0 release candidate.

## Context

An ordinary successful build does not prove that its inputs, archive members, or
demo evidence are reproducible and safe to publish. Hatchling can produce an
equivalent source tree with transport metadata that differs across builds.

## Decision

EvalForge checks in a canonical evidence set created exclusively from the CC0
fixtures. The generator independently verifies each report and records SHA-256
lineage for every fixture, report, and the generator itself.

The release verifier builds twice under a fixed epoch. Wheels must be
byte-identical without transformation. Each raw sdist is parsed without
extracting it, rejected unless every member is safe and regular, and repacked
with sorted names, fixed timestamps, numeric ownership, and fixed modes. The two
canonical sdists must then be byte-identical.

Only the verified wheel, canonical sdist, and `SHA256SUMS` become release
artifacts. The wheel is installed in a fresh environment with `--no-index
--no-deps` before success is reported.

## Consequences

Equivalent source archives become comparable byte-for-byte, and archive policy
is executable. This is not artifact signing, trusted provenance, or proof of
reproducibility on every operating system. Any change to a fixture or generator
requires deliberate evidence regeneration and review.
