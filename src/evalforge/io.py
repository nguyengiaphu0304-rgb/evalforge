from __future__ import annotations

import json
import re
from datetime import datetime
from typing import NoReturn, cast

from evalforge.canonical import (
    CanonicalizationError,
    canonical_bytes,
    freeze_json,
    normalize_text,
    thaw_json,
)
from evalforge.models import (
    CandidateOutput,
    CandidateStatus,
    Criterion,
    CriterionKind,
    Dataset,
    EvaluationCase,
    EvaluationReport,
    Provenance,
    SliceDefinition,
    SliceSet,
)

SCHEMA_VERSION = "evalforge/v1"
SLICE_SCHEMA_VERSION = "evalforge/slices-v1"
MAX_ARTIFACT_BYTES = 1_048_576
MAX_CASES = 1_000
MAX_CRITERIA_PER_CASE = 20
MAX_SLICES = 100
MAX_TEXT_CODEPOINTS = 100_000
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class SchemaError(ValueError):
    """Raised when an input violates the versioned evaluation schema."""


def _reject_constant(value: str) -> NoReturn:
    raise SchemaError(f"non-finite JSON constant is not allowed: {value}")


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        normalized = normalize_text(key)
        if normalized in result:
            raise SchemaError("duplicate or normalization-colliding JSON key")
        result[normalized] = value
    return result


def _load(raw: bytes) -> object:
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise SchemaError("artifact exceeds the byte limit")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SchemaError("artifact must be valid UTF-8 JSON") from error


def _mapping(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise SchemaError(f"{label} fields do not match the schema")
    return cast("dict[str, object]", value)


def _text(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{label} must be text")
    normalized = normalize_text(value)
    if (not allow_empty and not normalized) or len(normalized) > MAX_TEXT_CODEPOINTS:
        raise SchemaError(f"{label} length is invalid")
    return normalized


def _identifier(value: object, label: str) -> str:
    text = _text(value, label)
    if _ID.fullmatch(text) is None:
        raise SchemaError(f"{label} is invalid")
    return text


def _timestamp(value: object) -> str:
    text = _text(value, "retrieved_at")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise SchemaError("retrieved_at must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise SchemaError("retrieved_at must include a timezone")
    return text


def parse_dataset(raw: bytes) -> Dataset:
    root = _mapping(_load(raw), {"schema_version", "provenance", "cases"}, "dataset")
    if root["schema_version"] != SCHEMA_VERSION:
        raise SchemaError("unsupported dataset schema version")
    provenance_data = _mapping(
        root["provenance"],
        {"source", "license", "retrieved_at", "schema_version"},
        "provenance",
    )
    provenance = Provenance(
        source=_text(provenance_data["source"], "source"),
        license=_text(provenance_data["license"], "license"),
        retrieved_at=_timestamp(provenance_data["retrieved_at"]),
        schema_version=_text(provenance_data["schema_version"], "provenance schema version"),
    )
    case_values = root["cases"]
    if not isinstance(case_values, list) or not 0 < len(case_values) <= MAX_CASES:
        raise SchemaError("dataset case count is invalid")
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for case_value in case_values:
        case_data = _mapping(case_value, {"case_id", "input", "criteria"}, "case")
        case_id = _identifier(case_data["case_id"], "case_id")
        if case_id in seen:
            raise SchemaError("duplicate case_id")
        seen.add(case_id)
        criterion_values = case_data["criteria"]
        if (
            not isinstance(criterion_values, list)
            or not 0 < len(criterion_values) <= MAX_CRITERIA_PER_CASE
        ):
            raise SchemaError("criterion count is invalid")
        criteria: list[Criterion] = []
        criterion_ids: set[str] = set()
        for criterion_value in criterion_values:
            criterion_data = _mapping(
                criterion_value,
                {"criterion_id", "kind", "expected"},
                "criterion",
            )
            criterion_id = _identifier(criterion_data["criterion_id"], "criterion_id")
            if criterion_id in criterion_ids:
                raise SchemaError("duplicate criterion_id")
            criterion_ids.add(criterion_id)
            raw_kind = criterion_data["kind"]
            if raw_kind not in {"exact_text", "contains_text", "json_equal"}:
                raise SchemaError("unsupported criterion kind")
            kind = cast("CriterionKind", raw_kind)
            try:
                expected = freeze_json(criterion_data["expected"])
            except CanonicalizationError as error:
                raise SchemaError(f"criterion expected value is invalid: {error}") from error
            if kind in {"exact_text", "contains_text"} and not isinstance(expected, str):
                raise SchemaError("text criterion expected value must be text")
            criteria.append(Criterion(criterion_id, kind, expected))
        cases.append(
            EvaluationCase(
                case_id,
                _text(case_data["input"], "input", allow_empty=True),
                tuple(sorted(criteria, key=lambda criterion: criterion.criterion_id)),
            )
        )
    return Dataset(provenance, tuple(sorted(cases, key=lambda case: case.case_id)))


def parse_candidates(raw: bytes) -> tuple[CandidateOutput, ...]:
    root = _mapping(_load(raw), {"schema_version", "outputs"}, "candidate artifact")
    if root["schema_version"] != SCHEMA_VERSION:
        raise SchemaError("unsupported candidate schema version")
    values = root["outputs"]
    if not isinstance(values, list) or len(values) > MAX_CASES:
        raise SchemaError("candidate output count is invalid")
    outputs: list[CandidateOutput] = []
    seen: set[str] = set()
    for value in values:
        data = _mapping(value, {"case_id", "status", "output"}, "candidate output")
        case_id = _identifier(data["case_id"], "case_id")
        if case_id in seen:
            raise SchemaError("duplicate candidate case_id")
        seen.add(case_id)
        raw_status = data["status"]
        if raw_status not in {"ok", "timeout", "error"}:
            raise SchemaError("candidate status is invalid")
        status = cast("CandidateStatus", raw_status)
        output_value = data["output"]
        if status == "ok":
            output = _text(output_value, "output", allow_empty=True)
        elif output_value is not None:
            raise SchemaError("non-ok candidate output must be null")
        else:
            output = None
        outputs.append(CandidateOutput(case_id, status, output))
    return tuple(sorted(outputs, key=lambda output: output.case_id))


def parse_slice_set(raw: bytes, dataset: Dataset) -> SliceSet:
    root = _mapping(_load(raw), {"schema_version", "provenance", "slices"}, "slice artifact")
    if root["schema_version"] != SLICE_SCHEMA_VERSION:
        raise SchemaError("unsupported slice schema version")
    provenance_data = _mapping(
        root["provenance"],
        {"source", "license", "retrieved_at", "schema_version"},
        "slice provenance",
    )
    provenance = Provenance(
        source=_text(provenance_data["source"], "slice source"),
        license=_text(provenance_data["license"], "slice license"),
        retrieved_at=_timestamp(provenance_data["retrieved_at"]),
        schema_version=_text(
            provenance_data["schema_version"],
            "slice provenance schema version",
        ),
    )
    values = root["slices"]
    if not isinstance(values, list) or not 0 < len(values) <= MAX_SLICES:
        raise SchemaError("slice count is invalid")
    known_cases = {case.case_id for case in dataset.cases}
    slices: list[SliceDefinition] = []
    seen_slices: set[str] = set()
    for value in values:
        data = _mapping(value, {"slice_id", "case_ids"}, "slice")
        slice_id = _identifier(data["slice_id"], "slice_id")
        if slice_id in seen_slices:
            raise SchemaError("duplicate slice_id")
        seen_slices.add(slice_id)
        members = data["case_ids"]
        if not isinstance(members, list) or not 0 < len(members) <= MAX_CASES:
            raise SchemaError("slice member count is invalid")
        case_ids = tuple(_identifier(member, "slice case_id") for member in members)
        if len(set(case_ids)) != len(case_ids):
            raise SchemaError("duplicate slice case_id")
        unknown = sorted(set(case_ids) - known_cases)
        if unknown:
            raise SchemaError(f"slice contains unknown case IDs: {unknown}")
        slices.append(SliceDefinition(slice_id, tuple(sorted(case_ids))))
    return SliceSet(provenance, tuple(sorted(slices, key=lambda item: item.slice_id)))


def dataset_document(dataset: Dataset) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "source": dataset.provenance.source,
            "license": dataset.provenance.license,
            "retrieved_at": dataset.provenance.retrieved_at,
            "schema_version": dataset.provenance.schema_version,
        },
        "cases": [
            {
                "case_id": case.case_id,
                "input": case.input_text,
                "criteria": [
                    {
                        "criterion_id": criterion.criterion_id,
                        "kind": criterion.kind,
                        "expected": thaw_json(criterion.expected),
                    }
                    for criterion in case.criteria
                ],
            }
            for case in dataset.cases
        ],
    }


def candidates_document(outputs: tuple[CandidateOutput, ...]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "outputs": [
            {"case_id": output.case_id, "status": output.status, "output": output.output}
            for output in outputs
        ],
    }


def report_payload(report: EvaluationReport) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "dataset_sha256": report.dataset_sha256,
        "candidates_sha256": report.candidates_sha256,
        "results": [
            {
                "case_id": result.case_id,
                "status": result.status,
                "checks": [
                    {
                        "criterion_id": check.criterion_id,
                        "passed": check.passed,
                        "code": check.code,
                    }
                    for check in result.checks
                ],
            }
            for result in report.results
        ],
        "summary": {
            "total_cases": report.summary.total_cases,
            "passed_cases": report.summary.passed_cases,
            "failed_cases": report.summary.failed_cases,
            "missing_cases": report.summary.missing_cases,
            "timeout_cases": report.summary.timeout_cases,
            "error_cases": report.summary.error_cases,
            "pass_rate": report.summary.pass_rate,
        },
    }


def canonical_dataset(dataset: Dataset) -> bytes:
    return canonical_bytes(dataset_document(dataset))


def canonical_candidates(outputs: tuple[CandidateOutput, ...]) -> bytes:
    return canonical_bytes(candidates_document(outputs))


def slice_document(slice_set: SliceSet) -> dict[str, object]:
    return {
        "schema_version": SLICE_SCHEMA_VERSION,
        "provenance": {
            "source": slice_set.provenance.source,
            "license": slice_set.provenance.license,
            "retrieved_at": slice_set.provenance.retrieved_at,
            "schema_version": slice_set.provenance.schema_version,
        },
        "slices": [
            {"slice_id": item.slice_id, "case_ids": list(item.case_ids)}
            for item in slice_set.slices
        ],
    }


def canonical_slice_set(slice_set: SliceSet) -> bytes:
    return canonical_bytes(slice_document(slice_set))
