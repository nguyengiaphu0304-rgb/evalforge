from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

JsonScalar: TypeAlias = None | bool | int | float | str
CriterionKind: TypeAlias = Literal["exact_text", "contains_text", "json_equal"]
CandidateStatus: TypeAlias = Literal["ok", "timeout", "error"]
ResultStatus: TypeAlias = Literal["passed", "failed", "timeout", "error", "missing"]


@dataclass(frozen=True, slots=True)
class JsonArray:
    items: tuple[JsonValue, ...]


@dataclass(frozen=True, slots=True)
class JsonObject:
    items: tuple[tuple[str, JsonValue], ...]


JsonValue: TypeAlias = JsonScalar | JsonArray | JsonObject


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    license: str
    retrieved_at: str
    schema_version: str


@dataclass(frozen=True, slots=True)
class Criterion:
    criterion_id: str
    kind: CriterionKind
    expected: JsonValue


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    input_text: str
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True, slots=True)
class Dataset:
    provenance: Provenance
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True, slots=True)
class CandidateOutput:
    case_id: str
    status: CandidateStatus
    output: str | None


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    criterion_id: str
    passed: bool
    code: str


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    status: ResultStatus
    checks: tuple[CheckOutcome, ...]


@dataclass(frozen=True, slots=True)
class Summary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    missing_cases: int
    timeout_cases: int
    error_cases: int
    pass_rate: str


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    schema_version: str
    dataset_sha256: str
    candidates_sha256: str
    results: tuple[CaseResult, ...]
    summary: Summary
