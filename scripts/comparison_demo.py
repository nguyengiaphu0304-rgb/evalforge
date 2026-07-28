from __future__ import annotations

import argparse
from pathlib import Path

from evalforge import create_comparison_report, verify_comparison_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the synthetic EvalForge comparison")
    parser.add_argument("--dataset", type=Path, default=Path("fixtures/cases.json"))
    parser.add_argument(
        "--candidate-a",
        type=Path,
        default=Path("fixtures/candidates.json"),
    )
    parser.add_argument(
        "--candidate-b",
        type=Path,
        default=Path("fixtures/candidates-b.json"),
    )
    parser.add_argument("--slices", type=Path, default=Path("fixtures/slices.json"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--resamples", type=int, default=2_000)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    dataset = arguments.dataset.read_bytes()
    candidate_a = arguments.candidate_a.read_bytes()
    candidate_b = arguments.candidate_b.read_bytes()
    slices = arguments.slices.read_bytes()
    report = create_comparison_report(
        dataset,
        candidate_a,
        candidate_b,
        slices,
        seed=arguments.seed,
        resamples=arguments.resamples,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(report)
    verify_comparison_report(
        dataset,
        candidate_a,
        candidate_b,
        slices,
        report,
        seed=arguments.seed,
        resamples=arguments.resamples,
    )


if __name__ == "__main__":
    main()
