from __future__ import annotations

import json
from collections import Counter
from typing import NoReturn, cast

from evalforge.canonical import canonical_bytes, digest, freeze_json, normalize_text
from evalforge.io import (
    MAX_ARTIFACT_BYTES,
    SCHEMA_VERSION,
    SchemaError,
    canonical_candidates,
    canonical_dataset,
    parse_candidates,
    parse_dataset,
    report_payload,
)
from evalforge.models import (
    CandidateOutput,
    CaseResult,
    CheckOutcome,
    Criterion,
    Dataset,
    EvaluationReport,
    ResultStatus,
    Summary,
)

REPORT_SCHEMA_VERSION = "evalforge/report-v1"


class EvaluationError(ValueError):
    """Raised when evaluation inputs are inconsistent or unverifiable."""


def _reject_constant(value: str) -> NoReturn:
    raise EvaluationError(f"non-finite JSON constant is not allowed: {value}")


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        normalized = normalize_text(key)
        if normalized in result:
            raise EvaluationError("duplicate or normalization-colliding output JSON key")
        result[normalized] = value
    return result


def _check(criterion: Criterion, output: str) -> CheckOutcome:
    if criterion.kind == "exact_text":
        passed = normalize_text(output) == criterion.expected
        return CheckOutcome(criterion.criterion_id, passed, "matched" if passed else "mismatch")
    if criterion.kind == "contains_text":
        if not isinstance(criterion.expected, str):
            raise EvaluationError("text criterion invariant is invalid")
        passed = criterion.expected in normalize_text(output)
        return CheckOutcome(criterion.criterion_id, passed, "matched" if passed else "missing_text")
    try:
        parsed = json.loads(
            output,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
        passed = freeze_json(parsed) == criterion.expected
        code = "matched" if passed else "json_mismatch"
    except (json.JSONDecodeError, EvaluationError, ValueError):
        passed = False
        code = "malformed_json"
    return CheckOutcome(criterion.criterion_id, passed, code)


def _summary(results: tuple[CaseResult, ...]) -> Summary:
    counts = Counter(result.status for result in results)
    passed = counts["passed"]
    total = len(results)
    return Summary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=counts["failed"],
        missing_cases=counts["missing"],
        timeout_cases=counts["timeout"],
        error_cases=counts["error"],
        pass_rate=f"{passed / total:.6f}",
    )


def evaluate(dataset: Dataset, outputs: tuple[CandidateOutput, ...]) -> EvaluationReport:
    case_ids = {case.case_id for case in dataset.cases}
    output_ids = {output.case_id for output in outputs}
    unknown = sorted(output_ids - case_ids)
    if unknown:
        raise EvaluationError(f"candidate outputs contain unknown case IDs: {unknown}")
    by_id = {output.case_id: output for output in outputs}
    results: list[CaseResult] = []
    for case in dataset.cases:
        output = by_id.get(case.case_id)
        if output is None:
            results.append(CaseResult(case.case_id, "missing", ()))
        elif output.status in {"timeout", "error"}:
            results.append(CaseResult(case.case_id, cast("ResultStatus", output.status), ()))
        elif output.output is None:
            raise EvaluationError("ok candidate output cannot be null")
        else:
            checks = tuple(_check(criterion, output.output) for criterion in case.criteria)
            status: ResultStatus = "passed" if all(check.passed for check in checks) else "failed"
            results.append(CaseResult(case.case_id, status, checks))
    frozen_results = tuple(results)
    return EvaluationReport(
        schema_version=REPORT_SCHEMA_VERSION,
        dataset_sha256=digest(canonical_dataset(dataset)),
        candidates_sha256=digest(canonical_candidates(outputs)),
        results=frozen_results,
        summary=_summary(frozen_results),
    )


def create_report(dataset_raw: bytes, candidates_raw: bytes) -> bytes:
    dataset = parse_dataset(dataset_raw)
    candidates = parse_candidates(candidates_raw)
    report = evaluate(dataset, candidates)
    payload = report_payload(report)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "payload": payload,
        "sha256": digest(canonical_bytes(payload)),
    }
    return canonical_bytes(envelope)


def verify_report(dataset_raw: bytes, candidates_raw: bytes, report_raw: bytes) -> None:
    if len(report_raw) > MAX_ARTIFACT_BYTES:
        raise EvaluationError("report exceeds the byte limit")
    try:
        supplied = json.loads(
            report_raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, EvaluationError) as error:
        raise EvaluationError("report is not valid strict UTF-8 JSON") from error
    if (
        not isinstance(supplied, dict)
        or set(supplied) != {"schema_version", "payload", "sha256"}
        or supplied["schema_version"] != SCHEMA_VERSION
        or not isinstance(supplied["sha256"], str)
    ):
        raise EvaluationError("report envelope fields are invalid")
    if digest(canonical_bytes(supplied["payload"])) != supplied["sha256"]:
        raise EvaluationError("report payload checksum mismatch")
    try:
        expected = create_report(dataset_raw, candidates_raw)
    except SchemaError as error:
        raise EvaluationError("source artifact failed schema validation") from error
    if report_raw != expected:
        raise EvaluationError("report does not reproduce from source artifacts")
