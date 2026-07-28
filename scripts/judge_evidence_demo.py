from __future__ import annotations

import argparse
from pathlib import Path

from evalforge import create_judge_evidence_report, verify_judge_evidence_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic recorded-judge evidence")
    parser.add_argument("--dataset", type=Path, default=Path("fixtures/cases.json"))
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("fixtures/candidates.json"),
    )
    parser.add_argument(
        "--human-labels",
        type=Path,
        default=Path("fixtures/human-labels.json"),
    )
    parser.add_argument(
        "--judge-records",
        type=Path,
        default=Path("fixtures/judge-records.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    dataset = arguments.dataset.read_bytes()
    candidates = arguments.candidates.read_bytes()
    human_labels = arguments.human_labels.read_bytes()
    judge_records = arguments.judge_records.read_bytes()
    report = create_judge_evidence_report(
        dataset,
        candidates,
        human_labels,
        judge_records,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(report)
    verify_judge_evidence_report(
        dataset,
        candidates,
        human_labels,
        judge_records,
        report,
    )


if __name__ == "__main__":
    main()
