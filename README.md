# EvalForge

EvalForge is a provenance-first evaluation engine for recorded AI-system
outputs. Its v1.0 release candidate makes narrow deterministic claims: it validates bounded
artifacts, preserves every case in the denominator, reproduces reports
byte-for-byte, independently replays stored outcomes, and compares paired runs
with explicit uncertainty. It also measures agreement in provenance-bound human
labels before any learned judge is considered.

It is not a model leaderboard, a live inference gateway, or evidence that any
real model is accurate.

## Features

- Strict, immutable dataset and candidate-output schemas.
- Required source, license, retrieval timestamp, schema version, and SHA-256
  lineage.
- NFC-normalized exact text and required-fragment checks.
- Strict JSON structural equality with duplicate-key and non-finite rejection.
- Explicit `missing`, `timeout`, `error`, `failed`, and `passed` results.
- Canonical report artifacts that omit prompt and output bodies.
- Independent verification that recomputes every check and summary.
- Paired comparison with a complete status-transition matrix.
- Seeded, cross-version deterministic bootstrap intervals over paired pass
  indicators.
- Provenance-linked overlapping slices with explicit membership and denominator.
- Pseudonymous pass/fail/abstain human labels bound to exact dataset and candidate
  artifacts.
- Explicit unanimous, majority, tied, and insufficient consensus states.
- Exact nominal Krippendorff's alpha, identity-free pair summaries, and
  evaluator-versus-human confusion counts.
- Low-sample, undefined-agreement, and evaluator-non-success warnings that block
  quality claims.
- Recorded-judge artifacts with canonical request binding, strict structured
  decisions, and explicit timeout/error/truncation states.
- Separate trusted policy and untrusted case/candidate fields; no prompt string
  is assembled by the core.
- Integer retry, token, latency, and micro-USD lineage with human-calibrated
  coverage gates.
- Offline synthetic fixtures with no provider, private data, or benchmark claim.
- Dependency-free typed runtime with Python 3.11–3.13 CI.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python scripts/demo.py --output demo-output/report.json
python scripts/comparison_demo.py --output demo-output/comparison.json
python scripts/human_evidence_demo.py --output demo-output/human-evidence.json
python scripts/judge_evidence_demo.py --output demo-output/judge-evidence.json
python scripts/release_evidence.py --output-dir evidence/v1.0.0 --verify
python scripts/release_verify.py --output-dir release-artifacts
python -m pytest
```

The demo evaluates three generated synthetic cases. Two pass and one has an
explicit error status, so the report shows a `0.666667` pass rate. This is a
correctness fixture, not a measurement of model quality.

The comparison demo records one regression across the same three synthetic
cases. Because both the total sample and discordant-pair count are below the
documented thresholds, its conclusion is `insufficient_evidence`.

The human-evidence demo uses three synthetic pseudonymous raters and three
synthetic cases. Its small sample and disagreement deliberately produce
`insufficient_evidence`; it demonstrates arithmetic and failure handling, not
human or evaluator quality.

The recorded-judge demo uses only stored synthetic decisions. Its low human
sample, low agreement, 50% resolved-case coverage, and one truncated record force
`insufficient_evidence`. It makes no live request and measures no real model.

## Verification

```bash
ruff check .
ruff format --check .
mypy src scripts
pytest
python scripts/demo.py --output demo-output/report.json
python scripts/comparison_demo.py --output demo-output/comparison.json
python scripts/human_evidence_demo.py --output demo-output/human-evidence.json
python scripts/judge_evidence_demo.py --output demo-output/judge-evidence.json
python scripts/release_evidence.py --output-dir evidence/v1.0.0 --verify
python scripts/release_verify.py --output-dir release-artifacts
python -m pip check
python -m pip_audit --skip-editable
```

## Design documents

- [Architecture](docs/architecture.md)
- [Schema contract](docs/schema.md)
- [Comparison methodology](docs/comparison-methodology.md)
- [Human-evidence methodology](docs/human-evidence.md)
- [Recorded-judge contract](docs/judge-contract.md)
- [Threat model](docs/threat-model.md)
- [ADR-001](docs/adr/001-deterministic-offline-core.md)
- [ADR-002](docs/adr/002-paired-bootstrap-and-slices.md)
- [ADR-003](docs/adr/003-human-consensus-and-nominal-alpha.md)
- [ADR-004](docs/adr/004-recorded-judge-boundary.md)
- [ADR-005](docs/adr/005-reproducible-release-artifacts.md)
- [Release demo](docs/release-demo.md)
- [v1.0.0 release notes](docs/releases/v1.0.0.md)
- [Publication checklist](docs/releases/publication-checklist.md)
- [Residual risks](docs/releases/residual-risks.md)
- [Support and recovery matrix](docs/releases/support-matrix.md)
- [Roadmap](docs/roadmap.md)
- [Interview guide](docs/interview-guide.md)

## Current limitations

Criteria can still be unrepresentative or poorly written. SHA-256 does not
authenticate a publisher. NFC does not eliminate Unicode confusables. Reports
retain case IDs. There is no sandbox, encryption, signing, live provider,
provider SDK, identity service, adjudication workflow, causal inference,
multiple-comparison correction, deployment, or production telemetry. Human
label IDs are pseudonyms, not anonymity guarantees; case membership and vote
patterns can still be identifying. Alpha and bootstrap intervals describe the
declared samples and do not establish general model or annotator quality.
Structural request separation reduces accidental instruction mixing but cannot
prove that a model would ignore adversarial content.

The repository remains a release candidate until an annotated tag and
non-prerelease GitHub Release are published from the exact verified merge
commit. Artifacts are checksummed but not signed.
