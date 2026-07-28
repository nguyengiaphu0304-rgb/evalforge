# Architecture

EvalForge v0.4 has seven boundaries:

1. `io.py` parses untrusted UTF-8 JSON into immutable, versioned domain objects.
2. `canonical.py` normalizes Unicode and JSON before hashing or comparison.
3. `engine.py` joins cases to recorded outputs, executes deterministic checks,
   aggregates every case, and exports a canonical report envelope.
4. `verify_report` independently reparses and re-evaluates both source artifacts;
   it never trusts stored outcomes or summary counts.
5. `comparison.py` aligns two evaluated runs over the same case IDs, computes
   complete status transitions, full-denominator deltas, deterministic paired
   bootstrap intervals, and independently reproducible comparison artifacts.
6. `human.py` resolves provenance-bound pass/fail/abstain annotations, computes
   consensus and nominal agreement, and compares resolved human consensus with
   deterministic evaluator outcomes. Its public report omits annotator IDs.
7. `judge.py` aggregates complete recorded judge outcomes, binds them to
   canonical typed requests, preserves operational failures and integer costs,
   and calibrates decisions against the existing human-evidence boundary.

The report intentionally excludes prompts and candidate output text. It contains
case IDs, check outcomes, aggregate counts, and SHA-256 lineage. This reduces
accidental disclosure but does not make the report anonymous.

There is no network, database, provider SDK, plugin system, or hidden global
state in the core. Input order does not define output order.

Slice definitions are a separate provenance-bearing artifact. They may overlap
but cannot contain duplicate or unknown case IDs. Slice membership never changes
the overall denominator.

Human labels are another separate artifact. They must bind the canonical dataset
and candidate hashes. The parser retains pseudonymous IDs only long enough to
compute agreement; reports expose stable pair indexes, never those IDs. No
network judge, provider SDK, or free-text annotation enters this boundary.

Judge request construction lives in `io.py` so the same canonical envelope is
used for creation and verification. Trusted policy/configuration and untrusted
case/candidate content occupy separate object fields. The core hashes this
structure but never serializes it into a provider prompt or performs a network
call.
