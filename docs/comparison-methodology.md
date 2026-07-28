# Comparison methodology

EvalForge compares two recorded candidate artifacts against one immutable
dataset. Every dataset case is evaluated for both candidates and aligned by case
ID. Missing, timeout, error, failed, and passed statuses remain distinct in a
complete 5×5 transition matrix.

The headline delta is:

`(candidate B passed cases - candidate A passed cases) / total dataset cases`

The denominator never becomes “cases where both providers returned output.”
Improvements are nonpassed-to-passed transitions; regressions are
passed-to-nonpassed transitions. Other pairs are tied for this binary delta but
remain visible in the transition matrix.

## Interval

For each case, EvalForge records `+1`, `0`, or `-1` from the paired pass
indicators. It resamples those case-level differences with replacement using
SplitMix64 and reports the equal-tail 95% percentile interval. The generator,
index selection, seed derivation, rounding, confidence, and method version are
part of the contract.

The interval is deterministic engineering evidence. It represents resampling
uncertainty for the declared case set, not dataset representativeness, criterion
validity, causality, or future model behavior.

The combined workload is capped at ten million bootstrap draws across the
overall result and all slices. Requests exceeding that budget fail before
evaluation rather than allowing individually valid limits to multiply into an
unbounded workload.

## Evidence safeguards

- Fewer than 30 cases emits `sample_below_30`.
- Fewer than five discordant pairs emits `discordant_pairs_below_5`.
- Either warning forces the conclusion to `insufficient_evidence`.
- With both thresholds met, conclusions are still named
  `descriptive_increase`, `descriptive_decrease`, or `no_observed_change`.
- Slice results use the slice's complete declared membership and may overlap.

No synthetic result is presented as a real-model benchmark.
