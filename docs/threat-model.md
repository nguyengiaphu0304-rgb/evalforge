# Threat model

## Protected properties

- Failed, missing, timed-out, and errored cases cannot silently disappear.
- Stored scores cannot replace independent evaluation.
- Duplicate keys, IDs, unknown fields, non-finite numbers, and excessive inputs
  fail closed.
- Reports do not copy prompt or output bodies.
- Synthetic fixtures cannot be mistaken for real provider benchmarks.
- Candidate comparison cannot silently discard non-success cases or slices.
- Low sample and low discordance cannot produce a directional conclusion.
- Aggregate slice/bootstrap work cannot exceed ten million draws.
- Human annotations cannot silently attach to a different dataset or candidate
  run.
- Abstentions, ties, insufficient labels, and evaluator non-success states cannot
  become agreement or calibration successes.
- Public human-evidence reports omit annotator IDs and reject identity fields or
  free-text notes.

## Untrusted inputs

Dataset JSON, recorded candidate output JSON, candidate-produced JSON text, and
previously exported reports are untrusted.
Slice artifacts and comparison reports are also untrusted.
Human-label artifacts and human-evidence reports are also untrusted.

## Residual risks

SHA-256 does not authenticate authorship. Deterministic criteria can be badly
designed or unrepresentative. A pass rate is only meaningful for the documented
dataset and criterion policy. Unicode confusables beyond NFC are not resolved.
The parser is in-process and has no operating-system sandbox. There is no
encryption, access control, remote retention, signing, or live-provider timeout.
Bootstrap intervals reflect only resampling uncertainty inside the declared
case set. They do not address dataset bias, criterion validity, model drift,
multiple comparisons, or causal attribution.
Pseudonymous annotator IDs are not anonymous identities. Case IDs, overlap
counts, and unusual vote patterns may enable re-identification when combined
with outside knowledge. Report recipients still need appropriate access
controls. Nominal alpha does not measure validity, annotator expertise, fairness,
or representativeness; its operational threshold is a warning policy, not a
scientific universal. Majority consensus can preserve shared bias.
