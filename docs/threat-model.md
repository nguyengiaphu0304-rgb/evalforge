# Threat model

## Protected properties

- Failed, missing, timed-out, and errored cases cannot silently disappear.
- Stored scores cannot replace independent evaluation.
- Duplicate keys, IDs, unknown fields, non-finite numbers, and excessive inputs
  fail closed.
- Reports do not copy prompt or output bodies.
- Synthetic fixtures cannot be mistaken for real provider benchmarks.

## Untrusted inputs

Dataset JSON, recorded candidate output JSON, candidate-produced JSON text, and
previously exported reports are untrusted.

## Residual risks

SHA-256 does not authenticate authorship. Deterministic criteria can be badly
designed or unrepresentative. A pass rate is only meaningful for the documented
dataset and criterion policy. Unicode confusables beyond NFC are not resolved.
The parser is in-process and has no operating-system sandbox. There is no
encryption, access control, remote retention, signing, or live-provider timeout.
