# Architecture

EvalForge v0.2 has five boundaries:

1. `io.py` parses untrusted UTF-8 JSON into immutable, versioned domain objects.
2. `canonical.py` normalizes Unicode and JSON before hashing or comparison.
3. `engine.py` joins cases to recorded outputs, executes deterministic checks,
   aggregates every case, and exports a canonical report envelope.
4. `verify_report` independently reparses and re-evaluates both source artifacts;
   it never trusts stored outcomes or summary counts.
5. `comparison.py` aligns two evaluated runs over the same case IDs, computes
   complete status transitions, full-denominator deltas, deterministic paired
   bootstrap intervals, and independently reproducible comparison artifacts.

The report intentionally excludes prompts and candidate output text. It contains
case IDs, check outcomes, aggregate counts, and SHA-256 lineage. This reduces
accidental disclosure but does not make the report anonymous.

There is no network, database, provider SDK, plugin system, or hidden global
state in the core. Input order does not define output order.

Slice definitions are a separate provenance-bearing artifact. They may overlap
but cannot contain duplicate or unknown case IDs. Slice membership never changes
the overall denominator.
