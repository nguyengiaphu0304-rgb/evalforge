from __future__ import annotations

import json
import re
from datetime import datetime
from typing import NoReturn, cast

from evalforge.canonical import (
    CanonicalizationError,
    canonical_bytes,
    digest,
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
    HumanAnnotation,
    HumanLabelSet,
    HumanLabelValue,
    JudgeConfiguration,
    JudgeDecision,
    JudgeRecord,
    JudgeRecordSet,
    JudgeStatus,
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
MAX_ANNOTATORS = 50
MAX_ANNOTATIONS = 50_000
MAX_JUDGE_ATTEMPTS = 10
MAX_JUDGE_TOKENS = 1_000_000
MAX_JUDGE_LATENCY_MS = 3_600_000
MAX_JUDGE_COST_MICROUSD = 1_000_000_000
MAX_TEXT_CODEPOINTS = 100_000
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_JUDGE_REASON_CODES = {
    "criteria_satisfied",
    "criteria_not_satisfied",
    "insufficient_evidence",
    "policy_blocked",
    "malformed_candidate",
}


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


def _integer(value: object, label: str, maximum: int, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise SchemaError(f"{label} is outside the supported range")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SchemaError(f"{label} must be a lowercase SHA-256 digest")
    return value


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


def parse_human_labels(
    raw: bytes,
    dataset: Dataset,
    candidates: tuple[CandidateOutput, ...],
) -> HumanLabelSet:
    root = _mapping(
        _load(raw),
        {
            "schema_version",
            "provenance",
            "dataset_sha256",
            "candidates_sha256",
            "annotations",
        },
        "human label artifact",
    )
    if root["schema_version"] != "evalforge/human-labels-v1":
        raise SchemaError("unsupported human label schema version")
    expected_dataset_hash = digest(canonical_dataset(dataset))
    expected_candidates_hash = digest(canonical_candidates(candidates))
    if root["dataset_sha256"] != expected_dataset_hash:
        raise SchemaError("human label dataset lineage mismatch")
    if root["candidates_sha256"] != expected_candidates_hash:
        raise SchemaError("human label candidate lineage mismatch")
    provenance_data = _mapping(
        root["provenance"],
        {"source", "license", "retrieved_at", "schema_version"},
        "human label provenance",
    )
    provenance = Provenance(
        source=_text(provenance_data["source"], "human label source"),
        license=_text(provenance_data["license"], "human label license"),
        retrieved_at=_timestamp(provenance_data["retrieved_at"]),
        schema_version=_text(
            provenance_data["schema_version"],
            "human label provenance schema version",
        ),
    )
    values = root["annotations"]
    if not isinstance(values, list) or not 0 < len(values) <= MAX_ANNOTATIONS:
        raise SchemaError("human annotation count is invalid")
    known_cases = {case.case_id for case in dataset.cases}
    annotations: list[HumanAnnotation] = []
    assignments: set[tuple[str, str]] = set()
    annotators: set[str] = set()
    for value in values:
        data = _mapping(value, {"annotator_id", "case_id", "label"}, "human annotation")
        annotator_id = _identifier(data["annotator_id"], "annotator_id")
        case_id = _identifier(data["case_id"], "human annotation case_id")
        if case_id not in known_cases:
            raise SchemaError("human annotation references an unknown case")
        assignment = (annotator_id, case_id)
        if assignment in assignments:
            raise SchemaError("duplicate human annotation assignment")
        assignments.add(assignment)
        annotators.add(annotator_id)
        if len(annotators) > MAX_ANNOTATORS:
            raise SchemaError("human annotator count exceeds the limit")
        raw_label = data["label"]
        if raw_label not in {"pass", "fail", "abstain"}:
            raise SchemaError("unsupported human annotation label")
        annotations.append(
            HumanAnnotation(
                annotator_id,
                case_id,
                cast("HumanLabelValue", raw_label),
            )
        )
    return HumanLabelSet(
        provenance,
        expected_dataset_hash,
        expected_candidates_hash,
        tuple(
            sorted(
                annotations,
                key=lambda item: (item.case_id, item.annotator_id),
            )
        ),
    )


def human_label_document(label_set: HumanLabelSet) -> dict[str, object]:
    return {
        "schema_version": "evalforge/human-labels-v1",
        "provenance": {
            "source": label_set.provenance.source,
            "license": label_set.provenance.license,
            "retrieved_at": label_set.provenance.retrieved_at,
            "schema_version": label_set.provenance.schema_version,
        },
        "dataset_sha256": label_set.dataset_sha256,
        "candidates_sha256": label_set.candidates_sha256,
        "annotations": [
            {
                "annotator_id": item.annotator_id,
                "case_id": item.case_id,
                "label": item.label,
            }
            for item in label_set.annotations
        ],
    }


def canonical_human_labels(label_set: HumanLabelSet) -> bytes:
    return canonical_bytes(human_label_document(label_set))


def judge_request_document(
    case: EvaluationCase,
    candidate: CandidateOutput | None,
    configuration: JudgeConfiguration,
) -> dict[str, object]:
    """Build a typed request whose trusted and untrusted fields never mix."""
    return {
        "schema_version": "evalforge/judge-request-v1",
        "trusted": {
            "adapter_id": configuration.adapter_id,
            "policy_sha256": configuration.policy_sha256,
            "response_schema": configuration.response_schema,
            "criteria": [
                {
                    "criterion_id": criterion.criterion_id,
                    "kind": criterion.kind,
                    "expected": thaw_json(criterion.expected),
                }
                for criterion in case.criteria
            ],
        },
        "untrusted": {
            "case_id": case.case_id,
            "case_input": case.input_text,
            "candidate_status": "missing" if candidate is None else candidate.status,
            "candidate_output": None if candidate is None else candidate.output,
        },
    }


def _judge_configuration(value: object) -> JudgeConfiguration:
    data = _mapping(
        value,
        {
            "adapter_id",
            "provider",
            "model",
            "model_version",
            "policy_sha256",
            "response_schema",
        },
        "judge configuration",
    )
    return JudgeConfiguration(
        _identifier(data["adapter_id"], "judge adapter_id"),
        _identifier(data["provider"], "judge provider"),
        _identifier(data["model"], "judge model"),
        _identifier(data["model_version"], "judge model_version"),
        _sha256(data["policy_sha256"], "judge policy_sha256"),
        _identifier(data["response_schema"], "judge response_schema"),
    )


def _judge_response(
    status: JudgeStatus,
    response: object,
) -> tuple[JudgeDecision | None, tuple[str, ...]]:
    if status != "ok":
        if response is not None:
            raise SchemaError("non-success judge response must be null")
        return None, ()
    response_data = _mapping(
        response,
        {"decision", "reason_codes"},
        "judge response",
    )
    raw_decision = response_data["decision"]
    if raw_decision not in {"pass", "fail", "abstain"}:
        raise SchemaError("unsupported judge decision")
    raw_reasons = response_data["reason_codes"]
    if not isinstance(raw_reasons, list) or not 0 < len(raw_reasons) <= 10:
        raise SchemaError("judge reason code count is invalid")
    reason_codes = tuple(_identifier(reason, "judge reason code") for reason in raw_reasons)
    if len(set(reason_codes)) != len(reason_codes):
        raise SchemaError("duplicate judge reason code")
    if set(reason_codes) - _JUDGE_REASON_CODES:
        raise SchemaError("unsupported judge reason code")
    return cast("JudgeDecision", raw_decision), tuple(sorted(reason_codes))


def _judge_record(
    value: object,
    known_cases: dict[str, EvaluationCase],
    candidate_by_case: dict[str, CandidateOutput],
    configuration: JudgeConfiguration,
) -> JudgeRecord:
    data = _mapping(
        value,
        {
            "case_id",
            "request_sha256",
            "status",
            "response",
            "attempts",
            "input_tokens",
            "output_tokens",
            "latency_ms",
            "cost_microusd",
        },
        "judge record",
    )
    case_id = _identifier(data["case_id"], "judge case_id")
    if case_id not in known_cases:
        raise SchemaError("judge record references an unknown case")
    expected_request_hash = digest(
        canonical_bytes(
            judge_request_document(
                known_cases[case_id],
                candidate_by_case.get(case_id),
                configuration,
            )
        )
    )
    if data["request_sha256"] != expected_request_hash:
        raise SchemaError("judge request lineage mismatch")
    raw_status = data["status"]
    if raw_status not in {"ok", "timeout", "error", "truncated"}:
        raise SchemaError("unsupported judge status")
    status = cast("JudgeStatus", raw_status)
    decision, reason_codes = _judge_response(status, data["response"])
    return JudgeRecord(
        case_id,
        expected_request_hash,
        status,
        decision,
        reason_codes,
        _integer(data["attempts"], "judge attempts", MAX_JUDGE_ATTEMPTS, minimum=1),
        _integer(data["input_tokens"], "judge input_tokens", MAX_JUDGE_TOKENS),
        _integer(data["output_tokens"], "judge output_tokens", MAX_JUDGE_TOKENS),
        _integer(data["latency_ms"], "judge latency_ms", MAX_JUDGE_LATENCY_MS),
        _integer(data["cost_microusd"], "judge cost_microusd", MAX_JUDGE_COST_MICROUSD),
    )


def parse_judge_records(
    raw: bytes,
    dataset: Dataset,
    candidates: tuple[CandidateOutput, ...],
) -> JudgeRecordSet:
    """Parse complete, recorded judge outcomes and verify every request binding."""
    root = _mapping(
        _load(raw),
        {
            "schema_version",
            "provenance",
            "dataset_sha256",
            "candidates_sha256",
            "configuration",
            "records",
        },
        "judge record artifact",
    )
    if root["schema_version"] != "evalforge/judge-records-v1":
        raise SchemaError("unsupported judge record schema version")
    expected_dataset_hash = digest(canonical_dataset(dataset))
    expected_candidates_hash = digest(canonical_candidates(candidates))
    if root["dataset_sha256"] != expected_dataset_hash:
        raise SchemaError("judge record dataset lineage mismatch")
    if root["candidates_sha256"] != expected_candidates_hash:
        raise SchemaError("judge record candidate lineage mismatch")
    provenance_data = _mapping(
        root["provenance"],
        {"source", "license", "retrieved_at", "schema_version"},
        "judge record provenance",
    )
    provenance = Provenance(
        source=_text(provenance_data["source"], "judge record source"),
        license=_text(provenance_data["license"], "judge record license"),
        retrieved_at=_timestamp(provenance_data["retrieved_at"]),
        schema_version=_text(
            provenance_data["schema_version"],
            "judge record provenance schema version",
        ),
    )
    configuration = _judge_configuration(root["configuration"])
    values = root["records"]
    if not isinstance(values, list) or len(values) != len(dataset.cases):
        raise SchemaError("judge record count must match the dataset")
    known_cases = {case.case_id: case for case in dataset.cases}
    candidate_by_case = {candidate.case_id: candidate for candidate in candidates}
    unknown_candidates = sorted(set(candidate_by_case) - set(known_cases))
    if unknown_candidates:
        raise SchemaError("judge candidates contain unknown case IDs")
    records: list[JudgeRecord] = []
    seen: set[str] = set()
    for value in values:
        record = _judge_record(
            value,
            known_cases,
            candidate_by_case,
            configuration,
        )
        if record.case_id in seen:
            raise SchemaError("duplicate judge case record")
        seen.add(record.case_id)
        records.append(record)
    return JudgeRecordSet(
        provenance,
        expected_dataset_hash,
        expected_candidates_hash,
        configuration,
        tuple(sorted(records, key=lambda item: item.case_id)),
    )


def judge_record_document(record_set: JudgeRecordSet) -> dict[str, object]:
    """Convert judge records to their canonical source document."""
    configuration = record_set.configuration
    return {
        "schema_version": "evalforge/judge-records-v1",
        "provenance": {
            "source": record_set.provenance.source,
            "license": record_set.provenance.license,
            "retrieved_at": record_set.provenance.retrieved_at,
            "schema_version": record_set.provenance.schema_version,
        },
        "dataset_sha256": record_set.dataset_sha256,
        "candidates_sha256": record_set.candidates_sha256,
        "configuration": {
            "adapter_id": configuration.adapter_id,
            "provider": configuration.provider,
            "model": configuration.model,
            "model_version": configuration.model_version,
            "policy_sha256": configuration.policy_sha256,
            "response_schema": configuration.response_schema,
        },
        "records": [
            {
                "case_id": item.case_id,
                "request_sha256": item.request_sha256,
                "status": item.status,
                "response": (
                    {
                        "decision": item.decision,
                        "reason_codes": list(item.reason_codes),
                    }
                    if item.status == "ok"
                    else None
                ),
                "attempts": item.attempts,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "latency_ms": item.latency_ms,
                "cost_microusd": item.cost_microusd,
            }
            for item in record_set.records
        ],
    }


def canonical_judge_records(record_set: JudgeRecordSet) -> bytes:
    return canonical_bytes(judge_record_document(record_set))
