"""Privacy-minimized human-label agreement and calibration evidence."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from itertools import combinations
from typing import NoReturn

from evalforge.canonical import canonical_bytes, digest, normalize_text
from evalforge.engine import EvaluationError, evaluate
from evalforge.io import (
    MAX_ARTIFACT_BYTES,
    SchemaError,
    canonical_human_labels,
    parse_candidates,
    parse_dataset,
    parse_human_labels,
)
from evalforge.models import (
    AgreementStatistics,
    CalibrationSummary,
    ConsensusResult,
    ConsensusStatus,
    HumanAnnotation,
    HumanEvidenceReport,
    PairAgreement,
    ResultStatus,
)

HUMAN_EVIDENCE_SCHEMA_VERSION = "evalforge/human-evidence-v1"
_SIX_PLACES = Decimal("0.000001")
_MIN_CALIBRATION_CASES = 30
_MIN_ALPHA = Decimal("0.667000")


class HumanEvidenceError(ValueError):
    """Raised when human evidence cannot be safely created or verified."""


def _format_fraction(value: Fraction) -> str:
    decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return str(decimal.quantize(_SIX_PLACES, rounding=ROUND_HALF_EVEN))


def _consensus(
    case_ids: tuple[str, ...],
    annotations: tuple[HumanAnnotation, ...],
) -> tuple[ConsensusResult, ...]:
    labels: dict[str, Counter[str]] = defaultdict(Counter)
    for annotation in annotations:
        labels[annotation.case_id][annotation.label] += 1
    results: list[ConsensusResult] = []
    for case_id in case_ids:
        counts = labels[case_id]
        pass_votes = counts["pass"]
        fail_votes = counts["fail"]
        abstain_votes = counts["abstain"]
        non_abstaining = pass_votes + fail_votes
        status: ConsensusStatus
        if non_abstaining < 2:
            status = "insufficient"
            basis = "insufficient"
        elif pass_votes == fail_votes:
            status = "tied"
            basis = "tied"
        elif pass_votes > fail_votes:
            status = "pass"
            basis = "unanimous" if fail_votes == 0 else "majority"
        else:
            status = "fail"
            basis = "unanimous" if pass_votes == 0 else "majority"
        results.append(
            ConsensusResult(
                case_id,
                status,
                basis,
                pass_votes,
                fail_votes,
                abstain_votes,
            )
        )
    return tuple(results)


def _agreement(
    case_ids: tuple[str, ...],
    annotations: tuple[HumanAnnotation, ...],
) -> AgreementStatistics:
    by_case: dict[str, list[str]] = defaultdict(list)
    for annotation in annotations:
        if annotation.label != "abstain":
            by_case[annotation.case_id].append(annotation.label)
    observed_disagreements = 0
    observed_pairs = 0
    comparable_cases = 0
    marginal = Counter[str]()
    for case_id in case_ids:
        labels = by_case[case_id]
        marginal.update(labels)
        if len(labels) < 2:
            continue
        comparable_cases += 1
        pass_count = labels.count("pass")
        fail_count = labels.count("fail")
        observed_disagreements += 2 * pass_count * fail_count
        observed_pairs += len(labels) * (len(labels) - 1)
    total_labels = marginal.total()
    expected_disagreements = 2 * marginal["pass"] * marginal["fail"]
    expected_pairs = total_labels * (total_labels - 1)
    alpha: str | None = None
    if observed_pairs > 0 and expected_pairs > 0 and expected_disagreements > 0:
        observed = Fraction(observed_disagreements, observed_pairs)
        expected = Fraction(expected_disagreements, expected_pairs)
        alpha = _format_fraction(1 - observed / expected)
    return AgreementStatistics(
        alpha,
        observed_disagreements,
        observed_pairs,
        expected_disagreements,
        expected_pairs,
        comparable_cases,
        total_labels,
    )


def _pair_agreements(
    annotations: tuple[HumanAnnotation, ...],
) -> tuple[PairAgreement, ...]:
    annotators = sorted({annotation.annotator_id for annotation in annotations})
    by_annotator: dict[str, dict[str, str]] = defaultdict(dict)
    for annotation in annotations:
        if annotation.label != "abstain":
            by_annotator[annotation.annotator_id][annotation.case_id] = annotation.label
    evidence: list[PairAgreement] = []
    for pair_index, (left, right) in enumerate(
        combinations(annotators, 2),
        start=1,
    ):
        common = sorted(set(by_annotator[left]) & set(by_annotator[right]))
        agreements = sum(
            by_annotator[left][case_id] == by_annotator[right][case_id] for case_id in common
        )
        rate = _format_fraction(Fraction(agreements, len(common))) if common else None
        evidence.append(PairAgreement(pair_index, len(common), agreements, rate))
    return tuple(evidence)


def _calibration(
    consensus: tuple[ConsensusResult, ...],
    evaluator_status: dict[str, ResultStatus],
    alpha: str | None,
) -> CalibrationSummary:
    counts = Counter[str]()
    for result in consensus:
        if result.status == "tied":
            counts["human_unresolved"] += 1
            continue
        if result.status == "insufficient":
            counts["human_insufficient"] += 1
            continue
        status = evaluator_status[result.case_id]
        if status not in {"passed", "failed"}:
            counts["evaluator_non_success"] += 1
            continue
        counts["evaluated_resolved"] += 1
        outcome = {
            ("passed", "pass"): "true_positive",
            ("failed", "fail"): "true_negative",
            ("passed", "fail"): "false_positive",
            ("failed", "pass"): "false_negative",
        }[(status, result.status)]
        counts[outcome] += 1
    warnings: list[str] = []
    if counts["evaluated_resolved"] < _MIN_CALIBRATION_CASES:
        warnings.append("resolved_sample_below_30")
    if alpha is None:
        warnings.append("agreement_undefined")
    elif Decimal(alpha) < _MIN_ALPHA:
        warnings.append("agreement_below_operational_threshold")
    if counts["evaluator_non_success"]:
        warnings.append("evaluator_non_success_present")
    evidence_status = "insufficient_evidence" if warnings else "descriptive_only"
    return CalibrationSummary(
        counts["true_positive"],
        counts["true_negative"],
        counts["false_positive"],
        counts["false_negative"],
        counts["evaluator_non_success"],
        counts["human_unresolved"],
        counts["human_insufficient"],
        counts["evaluated_resolved"],
        evidence_status,
        tuple(warnings),
    )


def analyze_human_evidence(
    dataset_raw: bytes,
    candidates_raw: bytes,
    labels_raw: bytes,
) -> HumanEvidenceReport:
    """Analyze bound annotations without exposing annotator identities."""
    try:
        dataset = parse_dataset(dataset_raw)
        candidates = parse_candidates(candidates_raw)
        labels = parse_human_labels(labels_raw, dataset, candidates)
        evaluation = evaluate(dataset, candidates)
    except (SchemaError, EvaluationError) as error:
        raise HumanEvidenceError("human evidence source artifact is invalid") from error
    case_ids = tuple(case.case_id for case in dataset.cases)
    consensus = _consensus(case_ids, labels.annotations)
    agreement = _agreement(case_ids, labels.annotations)
    evaluator_status = {result.case_id: result.status for result in evaluation.results}
    bases = Counter(result.basis for result in consensus)
    return HumanEvidenceReport(
        HUMAN_EVIDENCE_SCHEMA_VERSION,
        labels.dataset_sha256,
        labels.candidates_sha256,
        digest(canonical_human_labels(labels)),
        len({item.annotator_id for item in labels.annotations}),
        len(labels.annotations),
        bases["unanimous"],
        bases["majority"],
        bases["tied"],
        bases["insufficient"],
        sum(item.label == "abstain" for item in labels.annotations),
        consensus,
        agreement,
        _pair_agreements(labels.annotations),
        _calibration(consensus, evaluator_status, agreement.alpha),
    )


def _agreement_document(agreement: AgreementStatistics) -> dict[str, object]:
    return {
        "alpha": agreement.alpha,
        "observed_disagreements": agreement.observed_disagreements,
        "observed_pairs": agreement.observed_pairs,
        "expected_disagreements": agreement.expected_disagreements,
        "expected_pairs": agreement.expected_pairs,
        "comparable_cases": agreement.comparable_cases,
        "non_abstaining_labels": agreement.non_abstaining_labels,
    }


def human_evidence_payload(report: HumanEvidenceReport) -> dict[str, object]:
    """Convert human evidence to its public privacy-minimized payload."""
    calibration = report.calibration
    return {
        "schema_version": report.schema_version,
        "lineage": {
            "dataset_sha256": report.dataset_sha256,
            "candidates_sha256": report.candidates_sha256,
            "labels_sha256": report.labels_sha256,
        },
        "annotation_summary": {
            "annotator_count": report.annotator_count,
            "annotation_count": report.annotation_count,
            "unanimous_cases": report.unanimous_cases,
            "majority_cases": report.majority_cases,
            "tied_cases": report.tied_cases,
            "insufficient_cases": report.insufficient_cases,
            "abstention_count": report.abstention_count,
        },
        "consensus": [
            {
                "case_id": item.case_id,
                "status": item.status,
                "basis": item.basis,
                "pass_votes": item.pass_votes,
                "fail_votes": item.fail_votes,
                "abstain_votes": item.abstain_votes,
            }
            for item in report.consensus
        ],
        "agreement": _agreement_document(report.agreement),
        "annotator_pairs": [
            {
                "pair_index": item.pair_index,
                "overlapping_cases": item.overlapping_cases,
                "agreements": item.agreements,
                "agreement_rate": item.agreement_rate,
            }
            for item in report.pair_agreements
        ],
        "calibration": {
            "true_positive": calibration.true_positive,
            "true_negative": calibration.true_negative,
            "false_positive": calibration.false_positive,
            "false_negative": calibration.false_negative,
            "evaluator_non_success": calibration.evaluator_non_success,
            "human_unresolved": calibration.human_unresolved,
            "human_insufficient": calibration.human_insufficient,
            "evaluated_resolved": calibration.evaluated_resolved,
            "status": calibration.status,
            "warnings": list(calibration.warnings),
            "minimum_resolved_cases": _MIN_CALIBRATION_CASES,
            "operational_alpha_threshold": str(_MIN_ALPHA),
        },
    }


def create_human_evidence_report(
    dataset_raw: bytes,
    candidates_raw: bytes,
    labels_raw: bytes,
) -> bytes:
    """Create canonical human agreement and calibration evidence."""
    payload = human_evidence_payload(
        analyze_human_evidence(dataset_raw, candidates_raw, labels_raw)
    )
    envelope = {
        "schema_version": HUMAN_EVIDENCE_SCHEMA_VERSION,
        "payload": payload,
        "sha256": digest(canonical_bytes(payload)),
    }
    return canonical_bytes(envelope)


def _reject_constant(value: str) -> NoReturn:
    raise HumanEvidenceError(f"non-finite JSON constant is not allowed: {value}")


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        normalized = normalize_text(key)
        if normalized in result:
            raise HumanEvidenceError("duplicate or normalization-colliding report key")
        result[normalized] = value
    return result


def verify_human_evidence_report(
    dataset_raw: bytes,
    candidates_raw: bytes,
    labels_raw: bytes,
    report_raw: bytes,
) -> None:
    """Independently regenerate and byte-compare human evidence."""
    if len(report_raw) > MAX_ARTIFACT_BYTES:
        raise HumanEvidenceError("human evidence report exceeds the byte limit")
    try:
        supplied = json.loads(
            report_raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, HumanEvidenceError) as error:
        raise HumanEvidenceError("human evidence report is not strict UTF-8 JSON") from error
    if (
        not isinstance(supplied, dict)
        or set(supplied) != {"schema_version", "payload", "sha256"}
        or supplied["schema_version"] != HUMAN_EVIDENCE_SCHEMA_VERSION
        or not isinstance(supplied["sha256"], str)
    ):
        raise HumanEvidenceError("human evidence report envelope fields are invalid")
    if digest(canonical_bytes(supplied["payload"])) != supplied["sha256"]:
        raise HumanEvidenceError("human evidence report payload checksum mismatch")
    expected = create_human_evidence_report(dataset_raw, candidates_raw, labels_raw)
    if report_raw != expected:
        raise HumanEvidenceError("human evidence report does not reproduce")
