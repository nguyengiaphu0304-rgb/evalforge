"""Offline recorded-judge evidence with human calibration gates."""

from __future__ import annotations

import json
from collections import Counter
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from typing import NoReturn

from evalforge.canonical import canonical_bytes, digest, normalize_text
from evalforge.human import HumanEvidenceError, analyze_human_evidence
from evalforge.io import (
    MAX_ARTIFACT_BYTES,
    SchemaError,
    canonical_human_labels,
    canonical_judge_records,
    parse_candidates,
    parse_dataset,
    parse_human_labels,
    parse_judge_records,
)
from evalforge.models import (
    ConsensusResult,
    JudgeCalibration,
    JudgeEvidenceReport,
    JudgeRecord,
)

JUDGE_EVIDENCE_SCHEMA_VERSION = "evalforge/judge-evidence-v1"
_SIX_PLACES = Decimal("0.000001")
_MIN_HUMAN_CASES = 30
_MIN_HUMAN_ALPHA = Decimal("0.667000")
_MIN_JUDGE_COVERAGE = Decimal("0.950000")


class JudgeEvidenceError(ValueError):
    """Raised when recorded judge evidence is invalid or cannot reproduce."""


def _format_fraction(value: Fraction) -> str:
    decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return str(decimal.quantize(_SIX_PLACES, rounding=ROUND_HALF_EVEN))


def _calibration_counts(
    consensus: tuple[ConsensusResult, ...],
    records: tuple[JudgeRecord, ...],
) -> Counter[str]:
    record_by_case = {record.case_id: record for record in records}
    counts = Counter[str]()
    counts["judge_non_success"] = sum(record.status != "ok" for record in records)
    for human in consensus:
        if human.status == "tied":
            counts["human_unresolved"] += 1
            continue
        if human.status == "insufficient":
            counts["human_insufficient"] += 1
            continue
        counts["resolved_human_cases"] += 1
        judge = record_by_case[human.case_id]
        if judge.status != "ok":
            continue
        if judge.decision == "abstain":
            counts["judge_abstain"] += 1
            continue
        if judge.decision not in {"pass", "fail"}:
            raise JudgeEvidenceError("successful judge record has no decision")
        counts["evaluated_resolved"] += 1
        outcome = {
            ("pass", "pass"): "true_positive",
            ("fail", "fail"): "true_negative",
            ("pass", "fail"): "false_positive",
            ("fail", "pass"): "false_negative",
        }[(judge.decision, human.status)]
        counts[outcome] += 1
    return counts


def _calibrate(
    consensus: tuple[ConsensusResult, ...],
    human_alpha: str | None,
    records: tuple[JudgeRecord, ...],
) -> JudgeCalibration:
    counts = _calibration_counts(consensus, records)
    resolved = counts["resolved_human_cases"]
    coverage = (
        _format_fraction(Fraction(counts["evaluated_resolved"], resolved))
        if resolved
        else "0.000000"
    )
    warnings: list[str] = []
    if resolved < _MIN_HUMAN_CASES:
        warnings.append("human_resolved_sample_below_30")
    if human_alpha is None:
        warnings.append("human_agreement_undefined")
    elif Decimal(human_alpha) < _MIN_HUMAN_ALPHA:
        warnings.append("human_agreement_below_operational_threshold")
    if Decimal(coverage) < _MIN_JUDGE_COVERAGE:
        warnings.append("judge_coverage_below_0_95")
    if counts["judge_non_success"]:
        warnings.append("judge_non_success_present")
    evidence_status = "insufficient_evidence" if warnings else "descriptive_only"
    return JudgeCalibration(
        counts["true_positive"],
        counts["true_negative"],
        counts["false_positive"],
        counts["false_negative"],
        counts["judge_abstain"],
        counts["judge_non_success"],
        counts["human_unresolved"],
        counts["human_insufficient"],
        resolved,
        counts["evaluated_resolved"],
        coverage,
        evidence_status,
        tuple(warnings),
    )


def analyze_judge_evidence(
    dataset_raw: bytes,
    candidates_raw: bytes,
    human_labels_raw: bytes,
    judge_records_raw: bytes,
) -> JudgeEvidenceReport:
    """Analyze recorded judge outcomes without making a live provider call."""
    try:
        dataset = parse_dataset(dataset_raw)
        candidates = parse_candidates(candidates_raw)
        human_labels = parse_human_labels(human_labels_raw, dataset, candidates)
        judge_records = parse_judge_records(judge_records_raw, dataset, candidates)
        human_evidence = analyze_human_evidence(
            dataset_raw,
            candidates_raw,
            human_labels_raw,
        )
    except (SchemaError, HumanEvidenceError) as error:
        raise JudgeEvidenceError("judge evidence source artifact is invalid") from error
    statuses = Counter(record.status for record in judge_records.records)
    decisions = Counter(
        record.decision for record in judge_records.records if record.decision is not None
    )
    return JudgeEvidenceReport(
        JUDGE_EVIDENCE_SCHEMA_VERSION,
        judge_records.dataset_sha256,
        judge_records.candidates_sha256,
        digest(canonical_human_labels(human_labels)),
        digest(canonical_judge_records(judge_records)),
        judge_records.configuration,
        len(judge_records.records),
        statuses["ok"],
        statuses["timeout"],
        statuses["error"],
        statuses["truncated"],
        decisions["pass"],
        decisions["fail"],
        decisions["abstain"],
        sum(record.attempts for record in judge_records.records),
        sum(record.input_tokens for record in judge_records.records),
        sum(record.output_tokens for record in judge_records.records),
        sum(record.latency_ms for record in judge_records.records),
        sum(record.cost_microusd for record in judge_records.records),
        _calibrate(
            human_evidence.consensus,
            human_evidence.agreement.alpha,
            judge_records.records,
        ),
    )


def judge_evidence_payload(report: JudgeEvidenceReport) -> dict[str, object]:
    """Convert judge evidence to a privacy-minimized canonical payload."""
    configuration = report.configuration
    calibration = report.calibration
    return {
        "schema_version": report.schema_version,
        "lineage": {
            "dataset_sha256": report.dataset_sha256,
            "candidates_sha256": report.candidates_sha256,
            "human_labels_sha256": report.human_labels_sha256,
            "judge_records_sha256": report.judge_records_sha256,
        },
        "configuration": {
            "adapter_id": configuration.adapter_id,
            "provider": configuration.provider,
            "model": configuration.model,
            "model_version": configuration.model_version,
            "policy_sha256": configuration.policy_sha256,
            "response_schema": configuration.response_schema,
        },
        "record_summary": {
            "total_cases": report.total_cases,
            "ok_cases": report.ok_cases,
            "timeout_cases": report.timeout_cases,
            "error_cases": report.error_cases,
            "truncated_cases": report.truncated_cases,
            "pass_decisions": report.pass_decisions,
            "fail_decisions": report.fail_decisions,
            "abstain_decisions": report.abstain_decisions,
            "total_attempts": report.total_attempts,
            "total_input_tokens": report.total_input_tokens,
            "total_output_tokens": report.total_output_tokens,
            "total_latency_ms": report.total_latency_ms,
            "total_cost_microusd": report.total_cost_microusd,
        },
        "calibration": {
            "true_positive": calibration.true_positive,
            "true_negative": calibration.true_negative,
            "false_positive": calibration.false_positive,
            "false_negative": calibration.false_negative,
            "judge_abstain": calibration.judge_abstain,
            "judge_non_success": calibration.judge_non_success,
            "human_unresolved": calibration.human_unresolved,
            "human_insufficient": calibration.human_insufficient,
            "resolved_human_cases": calibration.resolved_human_cases,
            "evaluated_resolved": calibration.evaluated_resolved,
            "coverage": calibration.coverage,
            "status": calibration.status,
            "warnings": list(calibration.warnings),
            "minimum_human_cases": _MIN_HUMAN_CASES,
            "minimum_human_alpha": str(_MIN_HUMAN_ALPHA),
            "minimum_judge_coverage": str(_MIN_JUDGE_COVERAGE),
        },
    }


def create_judge_evidence_report(
    dataset_raw: bytes,
    candidates_raw: bytes,
    human_labels_raw: bytes,
    judge_records_raw: bytes,
) -> bytes:
    """Create a canonical report from recorded judge outcomes."""
    payload = judge_evidence_payload(
        analyze_judge_evidence(
            dataset_raw,
            candidates_raw,
            human_labels_raw,
            judge_records_raw,
        )
    )
    return canonical_bytes(
        {
            "schema_version": JUDGE_EVIDENCE_SCHEMA_VERSION,
            "payload": payload,
            "sha256": digest(canonical_bytes(payload)),
        }
    )


def _reject_constant(value: str) -> NoReturn:
    raise JudgeEvidenceError(f"non-finite JSON constant is not allowed: {value}")


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        normalized = normalize_text(key)
        if normalized in result:
            raise JudgeEvidenceError("duplicate or normalization-colliding report key")
        result[normalized] = value
    return result


def verify_judge_evidence_report(
    dataset_raw: bytes,
    candidates_raw: bytes,
    human_labels_raw: bytes,
    judge_records_raw: bytes,
    report_raw: bytes,
) -> None:
    """Independently regenerate and byte-compare recorded judge evidence."""
    if len(report_raw) > MAX_ARTIFACT_BYTES:
        raise JudgeEvidenceError("judge evidence report exceeds the byte limit")
    try:
        supplied = json.loads(
            report_raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, JudgeEvidenceError) as error:
        raise JudgeEvidenceError("judge evidence report is not strict UTF-8 JSON") from error
    if (
        not isinstance(supplied, dict)
        or set(supplied) != {"schema_version", "payload", "sha256"}
        or supplied["schema_version"] != JUDGE_EVIDENCE_SCHEMA_VERSION
        or not isinstance(supplied["sha256"], str)
    ):
        raise JudgeEvidenceError("judge evidence report envelope fields are invalid")
    if digest(canonical_bytes(supplied["payload"])) != supplied["sha256"]:
        raise JudgeEvidenceError("judge evidence report payload checksum mismatch")
    expected = create_judge_evidence_report(
        dataset_raw,
        candidates_raw,
        human_labels_raw,
        judge_records_raw,
    )
    if report_raw != expected:
        raise JudgeEvidenceError("judge evidence report does not reproduce")
