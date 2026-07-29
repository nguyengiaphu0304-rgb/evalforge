# Residual risks

- SHA-256 checksums are not signatures and do not authenticate a publisher.
- Reproducible CI artifacts do not prove every environment or build service is
  trustworthy.
- The parser is in-process and is not an operating-system sandbox.
- Criteria, slices, datasets, and human labels may be biased or invalid even
  when their artifacts are internally consistent.
- Bootstrap intervals cover only resampling uncertainty in the declared cases.
- Agreement can preserve shared bias and does not measure expertise, fairness,
  or representativeness.
- Pseudonymous annotator IDs and case-level patterns may still be identifying.
- Structural trusted/untrusted fields do not prove a future model will resist
  semantic prompt injection.
- Recorded token, latency, and micro-USD values are not provider-attested.
- No live credential, egress, retention, timeout, retry, rate-limit, model drift,
  production telemetry, signing, encryption, or access-control boundary has
  been exercised.
