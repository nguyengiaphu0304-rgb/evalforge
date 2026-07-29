# Reproducible release demo

The v1.0.0 evidence is generated entirely offline from the repository's CC0
synthetic fixtures:

```bash
python scripts/release_evidence.py --output-dir /tmp/evalforge-evidence
diff -ru evidence/v1.0.0 /tmp/evalforge-evidence
python scripts/release_evidence.py --output-dir evidence/v1.0.0 --verify
```

The directory contains evaluation, comparison, human-agreement, and
recorded-judge reports plus a canonical manifest. The manifest records the exact
SHA-256 lineage of all fixture inputs, generated reports, and the generator.

The figures inside these reports are correctness fixtures. They are not real
model results, rankings, latency measurements, cost estimates, or evidence of
deployment quality.

To build the publishable artifact set:

```bash
python scripts/release_verify.py --output-dir release-artifacts
sha256sum --check release-artifacts/SHA256SUMS
```

The output contains one wheel, one canonical sdist, and checksums. The command
builds twice, checks archive policy, requires reproducibility, and performs an
offline isolated-wheel smoke test.
