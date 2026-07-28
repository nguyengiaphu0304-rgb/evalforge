from __future__ import annotations

import argparse
from pathlib import Path

from evalforge import create_human_evidence_report, verify_human_evidence_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic human agreement evidence")
    parser.add_argument("--dataset", type=Path, default=Path("fixtures/cases.json"))
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("fixtures/candidates.json"),
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("fixtures/human-labels.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    dataset = arguments.dataset.read_bytes()
    candidates = arguments.candidates.read_bytes()
    labels = arguments.labels.read_bytes()
    report = create_human_evidence_report(dataset, candidates, labels)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(report)
    verify_human_evidence_report(dataset, candidates, labels, report)


if __name__ == "__main__":
    main()
