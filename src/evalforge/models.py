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


@dataclass(frozen=True, slots=True)
class SliceDefinition:
    slice_id: str
    case_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SliceSet:
    provenance: Provenance
    slices: tuple[SliceDefinition, ...]


@dataclass(frozen=True, slots=True)
class Transition:
    candidate_a_status: ResultStatus
    candidate_b_status: ResultStatus
    count: int


@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    total_cases: int
    candidate_a_passed: int
    candidate_b_passed: int
    improved_cases: int
    regressed_cases: int
    tied_cases: int
    discordant_cases: int
    pass_rate_delta: str
    interval_lower: str
    interval_upper: str
    bootstrap_seed: int
    conclusion: str
    warnings: tuple[str, ...]
    transitions: tuple[Transition, ...]


@dataclass(frozen=True, slots=True)
class SliceComparison:
    slice_id: str
    summary: ComparisonSummary


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    schema_version: str
    dataset_sha256: str
    candidate_a_sha256: str
    candidate_b_sha256: str
    slices_sha256: str
    seed: int
    resamples: int
    confidence: str
    method_version: str
    overall: ComparisonSummary
    slices: tuple[SliceComparison, ...]
