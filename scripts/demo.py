from __future__ import annotations

import argparse
from pathlib import Path

from evalforge import create_report, verify_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify the synthetic EvalForge demo")
    parser.add_argument("--dataset", type=Path, default=Path("fixtures/cases.json"))
    parser.add_argument("--candidates", type=Path, default=Path("fixtures/candidates.json"))
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    dataset = arguments.dataset.read_bytes()
    candidates = arguments.candidates.read_bytes()
    report = create_report(dataset, candidates)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(report)
    verify_report(dataset, candidates, report)


if __name__ == "__main__":
    main()
