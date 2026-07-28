"""Deterministic paired comparison and uncertainty reporting."""

from __future__ import annotations

import json
from collections import Counter
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from hashlib import sha256
from typing import NoReturn

from evalforge.canonical import canonical_bytes, digest, normalize_text
from evalforge.engine import EvaluationError, evaluate
from evalforge.io import (
    MAX_ARTIFACT_BYTES,
    SchemaError,
    canonical_candidates,
    canonical_dataset,
    canonical_slice_set,
    parse_candidates,
    parse_dataset,
    parse_slice_set,
)
from evalforge.models import (
    ComparisonReport,
    ComparisonSummary,
    ResultStatus,
    SliceComparison,
    Transition,
)

COMPARISON_SCHEMA_VERSION = "evalforge/comparison-v1"
METHOD_VERSION = "paired-bootstrap-v1"
CONFIDENCE = Decimal("0.95")
MIN_RESAMPLES = 100
MAX_RESAMPLES = 10_000
MAX_BOOTSTRAP_DRAWS = 10_000_000
MIN_SAMPLE = 30
MIN_DISCORDANT = 5
_MASK_64 = (1 << 64) - 1
_STATUSES: tuple[ResultStatus, ...] = (
    "passed",
    "failed",
    "timeout",
    "error",
    "missing",
)
_SIX_PLACES = Decimal("0.000001")


class ComparisonError(ValueError):
    """Raised when a comparison cannot be safely created or verified."""


class _SplitMix64:
    """Small fully specified generator for cross-version reproducibility."""

    def __init__(self, seed: int) -> None:
        self._state = seed & _MASK_64

    def next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & _MASK_64
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK_64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK_64
        return (value ^ (value >> 31)) & _MASK_64

    def randbelow(self, upper: int) -> int:
        limit = ((1 << 64) // upper) * upper
        while True:
            value = self.next_u64()
            if value < limit:
                return value % upper


def _format_rate(numerator: int, denominator: int) -> str:
    value = Decimal(numerator) / Decimal(denominator)
    return str(value.quantize(_SIX_PLACES, rounding=ROUND_HALF_EVEN))


def _bootstrap_interval(
    differences: tuple[int, ...],
    *,
    seed: int,
    resamples: int,
) -> tuple[str, str]:
    generator = _SplitMix64(seed)
    size = len(differences)
    sampled_sums = sorted(
        sum(differences[generator.randbelow(size)] for _ in range(size)) for _ in range(resamples)
    )
    tail = (Decimal(1) - CONFIDENCE) / 2
    lower_index = int((tail * Decimal(resamples)).to_integral_value(rounding=ROUND_FLOOR))
    upper_index = (
        int(((Decimal(1) - tail) * Decimal(resamples)).to_integral_value(rounding=ROUND_CEILING))
        - 1
    )
    return (
        _format_rate(sampled_sums[lower_index], size),
        _format_rate(sampled_sums[upper_index], size),
    )


def _derived_seed(seed: int, slice_id: str) -> int:
    material = f"{seed}:{slice_id}".encode()
    return int.from_bytes(sha256(material).digest()[:8], "big")


def _summary(
    case_ids: tuple[str, ...],
    status_a: dict[str, ResultStatus],
    status_b: dict[str, ResultStatus],
    *,
    seed: int,
    resamples: int,
) -> ComparisonSummary:
    transitions = Counter((status_a[case_id], status_b[case_id]) for case_id in case_ids)
    differences = tuple(
        int(status_b[case_id] == "passed") - int(status_a[case_id] == "passed")
        for case_id in case_ids
    )
    improved = differences.count(1)
    regressed = differences.count(-1)
    discordant = improved + regressed
    candidate_a_passed = sum(status_a[case_id] == "passed" for case_id in case_ids)
    candidate_b_passed = sum(status_b[case_id] == "passed" for case_id in case_ids)
    warnings: list[str] = []
    if len(case_ids) < MIN_SAMPLE:
        warnings.append("sample_below_30")
    if discordant < MIN_DISCORDANT:
        warnings.append("discordant_pairs_below_5")
    delta = candidate_b_passed - candidate_a_passed
    if warnings:
        conclusion = "insufficient_evidence"
    elif delta > 0:
        conclusion = "descriptive_increase"
    elif delta < 0:
        conclusion = "descriptive_decrease"
    else:
        conclusion = "no_observed_change"
    lower, upper = _bootstrap_interval(differences, seed=seed, resamples=resamples)
    return ComparisonSummary(
        total_cases=len(case_ids),
        candidate_a_passed=candidate_a_passed,
        candidate_b_passed=candidate_b_passed,
        improved_cases=improved,
        regressed_cases=regressed,
        tied_cases=len(case_ids) - discordant,
        discordant_cases=discordant,
        pass_rate_delta=_format_rate(delta, len(case_ids)),
        interval_lower=lower,
        interval_upper=upper,
        bootstrap_seed=seed,
        conclusion=conclusion,
        warnings=tuple(warnings),
        transitions=tuple(
            Transition(a_status, b_status, transitions[(a_status, b_status)])
            for a_status in _STATUSES
            for b_status in _STATUSES
        ),
    )


def compare(
    dataset_raw: bytes,
    candidate_a_raw: bytes,
    candidate_b_raw: bytes,
    slices_raw: bytes,
    *,
    seed: int = 0,
    resamples: int = 2_000,
) -> ComparisonReport:
    """Compare two recorded runs over one dataset and declared slices."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= _MASK_64:
        raise ComparisonError("seed must be an unsigned 64-bit integer")
    if (
        isinstance(resamples, bool)
        or not isinstance(resamples, int)
        or not MIN_RESAMPLES <= resamples <= MAX_RESAMPLES
    ):
        raise ComparisonError("resamples must be between 100 and 10000")
    try:
        dataset = parse_dataset(dataset_raw)
        candidate_a = parse_candidates(candidate_a_raw)
        candidate_b = parse_candidates(candidate_b_raw)
        slice_set = parse_slice_set(slices_raw, dataset)
        total_memberships = len(dataset.cases) + sum(
            len(item.case_ids) for item in slice_set.slices
        )
        if total_memberships * resamples > MAX_BOOTSTRAP_DRAWS:
            raise ComparisonError("comparison exceeds the bootstrap compute budget")
        evaluated_a = evaluate(dataset, candidate_a)
        evaluated_b = evaluate(dataset, candidate_b)
    except (SchemaError, EvaluationError) as error:
        raise ComparisonError("comparison source artifact is invalid") from error
    status_a = {result.case_id: result.status for result in evaluated_a.results}
    status_b = {result.case_id: result.status for result in evaluated_b.results}
    all_case_ids = tuple(case.case_id for case in dataset.cases)
    return ComparisonReport(
        schema_version=COMPARISON_SCHEMA_VERSION,
        dataset_sha256=digest(canonical_dataset(dataset)),
        candidate_a_sha256=digest(canonical_candidates(candidate_a)),
        candidate_b_sha256=digest(canonical_candidates(candidate_b)),
        slices_sha256=digest(canonical_slice_set(slice_set)),
        seed=seed,
        resamples=resamples,
        confidence=str(CONFIDENCE.quantize(_SIX_PLACES)),
        method_version=METHOD_VERSION,
        overall=_summary(
            all_case_ids,
            status_a,
            status_b,
            seed=seed,
            resamples=resamples,
        ),
        slices=tuple(
            SliceComparison(
                item.slice_id,
                _summary(
                    item.case_ids,
                    status_a,
                    status_b,
                    seed=_derived_seed(seed, item.slice_id),
                    resamples=resamples,
                ),
            )
            for item in slice_set.slices
        ),
    )


def _summary_document(summary: ComparisonSummary) -> dict[str, object]:
    return {
        "total_cases": summary.total_cases,
        "candidate_a_passed": summary.candidate_a_passed,
        "candidate_b_passed": summary.candidate_b_passed,
        "improved_cases": summary.improved_cases,
        "regressed_cases": summary.regressed_cases,
        "tied_cases": summary.tied_cases,
        "discordant_cases": summary.discordant_cases,
        "pass_rate_delta": summary.pass_rate_delta,
        "interval": {
            "lower": summary.interval_lower,
            "upper": summary.interval_upper,
        },
        "bootstrap_seed": summary.bootstrap_seed,
        "conclusion": summary.conclusion,
        "warnings": list(summary.warnings),
        "transitions": [
            {
                "candidate_a_status": transition.candidate_a_status,
                "candidate_b_status": transition.candidate_b_status,
                "count": transition.count,
            }
            for transition in summary.transitions
        ],
    }


def comparison_payload(report: ComparisonReport) -> dict[str, object]:
    """Convert a comparison report to its public canonical payload."""
    return {
        "schema_version": report.schema_version,
        "lineage": {
            "dataset_sha256": report.dataset_sha256,
            "candidate_a_sha256": report.candidate_a_sha256,
            "candidate_b_sha256": report.candidate_b_sha256,
            "slices_sha256": report.slices_sha256,
        },
        "method": {
            "version": report.method_version,
            "seed": report.seed,
            "resamples": report.resamples,
            "confidence": report.confidence,
            "minimum_sample": MIN_SAMPLE,
            "minimum_discordant_pairs": MIN_DISCORDANT,
            "maximum_bootstrap_draws": MAX_BOOTSTRAP_DRAWS,
        },
        "overall": _summary_document(report.overall),
        "slices": [
            {"slice_id": item.slice_id, "summary": _summary_document(item.summary)}
            for item in report.slices
        ],
    }


def create_comparison_report(
    dataset_raw: bytes,
    candidate_a_raw: bytes,
    candidate_b_raw: bytes,
    slices_raw: bytes,
    *,
    seed: int = 0,
    resamples: int = 2_000,
) -> bytes:
    """Create a canonical, checksum-protected paired comparison report."""
    report = compare(
        dataset_raw,
        candidate_a_raw,
        candidate_b_raw,
        slices_raw,
        seed=seed,
        resamples=resamples,
    )
    payload = comparison_payload(report)
    envelope = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "payload": payload,
        "sha256": digest(canonical_bytes(payload)),
    }
    return canonical_bytes(envelope)


def _reject_constant(value: str) -> NoReturn:
    raise ComparisonError(f"non-finite JSON constant is not allowed: {value}")


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        normalized = normalize_text(key)
        if normalized in result:
            raise ComparisonError("duplicate or normalization-colliding report key")
        result[normalized] = value
    return result


def verify_comparison_report(
    dataset_raw: bytes,
    candidate_a_raw: bytes,
    candidate_b_raw: bytes,
    slices_raw: bytes,
    report_raw: bytes,
    *,
    seed: int = 0,
    resamples: int = 2_000,
) -> None:
    """Recompute a comparison and reject any byte-level report divergence."""
    if len(report_raw) > MAX_ARTIFACT_BYTES:
        raise ComparisonError("comparison report exceeds the byte limit")
    try:
        supplied = json.loads(
            report_raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ComparisonError) as error:
        raise ComparisonError("comparison report is not valid strict UTF-8 JSON") from error
    if (
        not isinstance(supplied, dict)
        or set(supplied) != {"schema_version", "payload", "sha256"}
        or supplied["schema_version"] != COMPARISON_SCHEMA_VERSION
        or not isinstance(supplied["sha256"], str)
    ):
        raise ComparisonError("comparison report envelope fields are invalid")
    if digest(canonical_bytes(supplied["payload"])) != supplied["sha256"]:
        raise ComparisonError("comparison report payload checksum mismatch")
    expected = create_comparison_report(
        dataset_raw,
        candidate_a_raw,
        candidate_b_raw,
        slices_raw,
        seed=seed,
        resamples=resamples,
    )
    if report_raw != expected:
        raise ComparisonError("comparison report does not reproduce from source artifacts")
