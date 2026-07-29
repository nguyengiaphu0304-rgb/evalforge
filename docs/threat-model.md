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
- Recorded judge outcomes cannot attach to a different canonical request,
  dataset, candidate run, policy hash, or provider/model version.
- Instruction-like candidate text remains under an untrusted request field and
  cannot overwrite trusted policy fields through parsing.
- Free-text judge rationales, credentials, endpoints, provider request IDs, and
  exception text are not accepted artifact fields.
- Timeout, error, truncation, abstention, low coverage, and failed human gates
  cannot become a positive calibration conclusion.
- Checked release evidence cannot drift from fixtures or its generator.
- Release archives cannot contain traversal, duplicate, symlink, special,
  forbidden, wrongly versioned, or resource-exhausting members.

## Untrusted inputs

Dataset JSON, recorded candidate output JSON, candidate-produced JSON text, and
previously exported reports are untrusted.
Slice artifacts and comparison reports are also untrusted.
Human-label artifacts and human-evidence reports are also untrusted.
Recorded-judge artifacts and judge-evidence reports are also untrusted.

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
Typed field separation prevents structural instruction confusion inside
EvalForge, but it does not prove that a future provider or model will follow the
trusted policy. Policy hashes authenticate neither authorship nor safety.
Recorded usage metadata can be false even when internally consistent. Micro-USD
costs exclude undeclared provider charges. No live timeout, retry, rate-limit,
credential, egress, or data-retention boundary has been exercised.
Build reproducibility does not authenticate the builder. SHA-256 detects byte
changes only when compared with a trusted digest. The deterministic sdist
normalizes timestamps, ownership, modes, and ordering; it does not claim that
the raw build-backend tarball is stable.
