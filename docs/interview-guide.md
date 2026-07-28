# Interview guide

## Why recorded outputs first?

They isolate evaluation correctness from provider availability, cost, retries,
and model drift. A failing core cannot be rescued by adding an API.

## Why keep missing cases in the denominator?

Dropping failures inflates scores. EvalForge reports passed, failed, missing,
timeout, and error counts against the same total case set.

## Why strict JSON equality?

Permissive coercion can turn schema mistakes into false passes. Duplicate keys,
NaN, structural type changes, and unexpected fields remain meaningful failures.

## Why hash canonical artifacts?

Equivalent input ordering produces identical lineage. The hash detects change;
it does not authenticate the source, so signing remains separate work.

## Main trade-off

Deterministic criteria are reproducible but narrow. Open-ended judgment may be
necessary later, but it needs calibration against human labels rather than an
unverified model call.
