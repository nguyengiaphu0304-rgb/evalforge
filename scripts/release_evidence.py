from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Final

from evalforge import (
    __version__,
    create_comparison_report,
    create_human_evidence_report,
    create_judge_evidence_report,
    create_report,
    verify_comparison_report,
    verify_human_evidence_report,
    verify_judge_evidence_report,
    verify_report,
)

ROOT: Final = Path(__file__).resolve().parents[1]
FIXTURES: Final = ROOT / "fixtures"
EVIDENCE_FILES: Final = (
    "evaluation.json",
    "comparison.json",
    "human-evidence.json",
    "judge-evidence.json",
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate(output_dir: Path) -> None:
    """Generate the complete offline v1.0 evidence set."""
    dataset = (FIXTURES / "cases.json").read_bytes()
    candidates = (FIXTURES / "candidates.json").read_bytes()
    candidates_b = (FIXTURES / "candidates-b.json").read_bytes()
    slices = (FIXTURES / "slices.json").read_bytes()
    human_labels = (FIXTURES / "human-labels.json").read_bytes()
    judge_records = (FIXTURES / "judge-records.json").read_bytes()

    reports = {
        "evaluation.json": create_report(dataset, candidates),
        "comparison.json": create_comparison_report(
            dataset,
            candidates,
            candidates_b,
            slices,
            seed=7,
            resamples=2_000,
        ),
        "human-evidence.json": create_human_evidence_report(
            dataset,
            candidates,
            human_labels,
        ),
        "judge-evidence.json": create_judge_evidence_report(
            dataset,
            candidates,
            human_labels,
            judge_records,
        ),
    }
    verify_report(dataset, candidates, reports["evaluation.json"])
    verify_comparison_report(
        dataset,
        candidates,
        candidates_b,
        slices,
        reports["comparison.json"],
        seed=7,
        resamples=2_000,
    )
    verify_human_evidence_report(
        dataset,
        candidates,
        human_labels,
        reports["human-evidence.json"],
    )
    verify_judge_evidence_report(
        dataset,
        candidates,
        human_labels,
        judge_records,
        reports["judge-evidence.json"],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in reports.items():
        (output_dir / name).write_bytes(content)

    fixture_hashes = {
        path.name: _sha256(path.read_bytes()) for path in sorted(FIXTURES.glob("*.json"))
    }
    report_hashes = {name: _sha256(content) for name, content in sorted(reports.items())}
    generator = Path(__file__).read_bytes()
    manifest = {
        "artifact_schema": "evalforge-release-evidence/v1",
        "generator_sha256": _sha256(generator),
        "package_version": __version__,
        "reports": report_hashes,
        "sources": fixture_hashes,
        "synthetic_only": True,
    }
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    (output_dir / "manifest.json").write_text(f"{encoded}\n", encoding="utf-8")


def verify(output_dir: Path) -> None:
    """Regenerate evidence and require an exact checked-in match."""
    with tempfile.TemporaryDirectory(prefix="evalforge-evidence-") as temporary:
        regenerated = Path(temporary)
        generate(regenerated)
        expected = (*EVIDENCE_FILES, "manifest.json")
        actual = tuple(sorted(path.name for path in output_dir.iterdir() if path.is_file()))
        if actual != tuple(sorted(expected)):
            raise ValueError("release evidence file set is not exact")
        for name in expected:
            if (output_dir / name).read_bytes() != (regenerated / name).read_bytes():
                raise ValueError(f"release evidence drift: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or verify v1.0 release evidence")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    if arguments.verify:
        verify(arguments.output_dir)
    else:
        generate(arguments.output_dir)


if __name__ == "__main__":
    main()
