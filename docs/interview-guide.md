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
