# Human-evidence methodology

EvalForge accepts recorded `pass`, `fail`, or `abstain` labels from
pseudonymous annotators. The label artifact is valid only for the exact
canonical dataset and candidate-output hashes it declares. It cannot contain
names, email addresses, demographic attributes, rationales, or other free text.

## Consensus

A case needs at least two non-abstaining labels. Equal pass and fail votes are
`tied`; otherwise the larger count wins and is marked `unanimous` or
`majority`. Cases with fewer than two usable labels are `insufficient`.
Abstentions remain counted in every case record.

## Nominal agreement

Krippendorff's alpha uses ordered pass/fail pairs:

`alpha = 1 - observed disagreement / expected disagreement`

Observed components are computed within cases. Expected components come from the
overall pass/fail marginals. All arithmetic uses exact rational numbers before
six-place decimal serialization. Alpha is undefined when there are no
comparable pairs or the marginal distribution has no expected disagreement.
EvalForge reports `null` in those cases rather than claiming perfect agreement.

Pair summaries expose overlap, agreement count, and rate under sequential pair
indexes. They do not expose annotator IDs. Pairs with no shared non-abstaining
case remain explicit with a null rate.

## Evaluator calibration

Resolved human consensus is compared with deterministic EvalForge outcomes.
Only `passed` and `failed` enter the confusion matrix. Missing, timeout, and
error outcomes are counted as evaluator non-success; tied and insufficient
human cases remain separate.

The result is `insufficient_evidence` when fewer than 30 resolved cases are
evaluated, alpha is undefined or below 0.667, or evaluator non-success is
present. Otherwise the status is only `descriptive_only`. Neither status is a
leaderboard, causal result, production-readiness claim, or proof of human-label
validity.

## Privacy and limitations

The source artifact still contains pseudonymous IDs and must be protected. The
public evidence report omits them but retains case IDs and vote counts, which can
support re-identification when combined with outside information. Shared
annotator bias can produce agreement. Alpha does not establish expertise,
fairness, criterion validity, dataset representativeness, or future behavior.
