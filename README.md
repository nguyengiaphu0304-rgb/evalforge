# EvalForge

EvalForge is a provenance-first evaluation engine for recorded AI-system
outputs. Its v0.1 core makes narrow deterministic claims: it validates bounded
artifacts, preserves every case in the denominator, reproduces reports
byte-for-byte, and independently replays stored outcomes.

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
- Offline synthetic fixtures with no provider, private data, or benchmark claim.
- Dependency-free typed runtime with Python 3.11–3.13 CI.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python scripts/demo.py --output demo-output/report.json
python -m pytest
```

The demo evaluates three generated synthetic cases. Two pass and one has an
explicit error status, so the report shows a `0.666667` pass rate. This is a
correctness fixture, not a measurement of model quality.

## Verification

```bash
ruff check .
ruff format --check .
mypy src scripts
pytest
python scripts/demo.py --output demo-output/report.json
python -m build
python -m pip check
python -m pip_audit --skip-editable
```

## Design documents

- [Architecture](docs/architecture.md)
- [Schema contract](docs/schema.md)
- [Threat model](docs/threat-model.md)
- [ADR-001](docs/adr/001-deterministic-offline-core.md)
- [Roadmap](docs/roadmap.md)
- [Interview guide](docs/interview-guide.md)

## Current limitations

Criteria can still be unrepresentative or poorly written. SHA-256 does not
authenticate a publisher. NFC does not eliminate Unicode confusables. Reports
retain case IDs. There is no sandbox, encryption, signing, live provider,
LLM-as-a-judge, human-label calibration, statistical uncertainty, deployment,
or production telemetry.
