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

## Why a paired bootstrap?

Both runs are evaluated on the same cases, so the unit of resampling is the
per-case pass-indicator difference. This preserves pairing and keeps missing,
timeout, error, and failed outcomes in the denominator. EvalForge uses a fully
specified SplitMix64 generator so evidence is stable across supported Python
versions.

## Why emit a 5×5 transition matrix?

A scalar delta hides whether changes are failures, timeouts, errors, or missing
outputs. The matrix keeps all status movement inspectable while the interval
answers only the narrower pass-indicator question.

## Why no “winner” for small samples?

Fewer than 30 cases or five discordant pairs produces
`insufficient_evidence`. The thresholds are safeguards, not proof that a sample
above them is representative. Conclusions remain explicitly descriptive.

## Why distinguish abstention from failure?

An abstention means the rater did not issue a binary judgment; treating it as a
failure manufactures disagreement. EvalForge preserves abstention counts,
excludes them from nominal pair arithmetic, and requires at least two
non-abstaining labels before resolving a case.

## Why nominal Krippendorff's alpha?

It supports a varying number of usable labels per case and corrects observed
disagreement by the pass/fail marginal distribution. EvalForge publishes the
ordered disagreement and pair counts, computes with exact fractions, and emits
`null` when expected disagreement is zero instead of inventing perfect
agreement.

## Why omit annotator IDs from reports?

Agreement needs identity linkage during computation, but downstream calibration
does not. Pair indexes preserve auditability without propagating pseudonyms.
This is data minimization, not anonymity: case and vote patterns remain a
residual re-identification risk.

## Why is calibration still descriptive?

The confusion matrix compares deterministic evaluator outcomes with resolved
human consensus only. A small sample, low or undefined agreement, or evaluator
non-success forces `insufficient_evidence`. Passing those gates still would not
prove the labels representative, unbiased, or suitable for deployment.

## Why build a recorded judge before a live adapter?

It makes schema, lineage, failure accounting, privacy, and calibration testable
without provider availability, credentials, cost, or model drift. A live API
cannot repair an evidence format that silently drops truncation or accepts
unbound responses.

## How is prompt injection bounded?

EvalForge creates a typed object with separate `trusted` and `untrusted` fields
and hashes that object. Candidate text can contain role names, delimiters, or
instruction-like strings without changing trusted fields. The core never
concatenates a prompt. This is a structural invariant, not proof that a future
model will resist semantic prompt injection.

## Why integer micro-USD and explicit attempts?

Integer accounting avoids binary floating-point drift and makes retry cost
auditable. The report retains total attempts, tokens, latency, and cost, but
those values are recorded claims rather than verified provider invoices.

## Why gate on both humans and judge coverage?

A judge cannot be calibrated against unresolved or low-agreement labels. Even
with adequate human evidence, abstentions and operational failures reduce judge
coverage. Low sample, low/undefined alpha, coverage below 95%, or any recorded
judge non-success forces `insufficient_evidence`.

## Why canonicalize only the sdist?

The wheel is the installable runtime artifact, so two wheel builds must match
without transformation. Source distributions may inherit tar/gzip timestamps,
ownership, modes, and ordering from the build backend. The verifier first
rejects unsafe or unexpected members, then canonicalizes only that transport
metadata and requires the two resulting archives to match.

This is reproducibility and drift evidence, not publisher authentication.
Artifact signing and trusted build provenance remain separate future controls.
