from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

JsonScalar: TypeAlias = None | bool | int | float | str
CriterionKind: TypeAlias = Literal["exact_text", "contains_text", "json_equal"]
CandidateStatus: TypeAlias = Literal["ok", "timeout", "error"]
ResultStatus: TypeAlias = Literal["passed", "failed", "timeout", "error", "missing"]
HumanLabelValue: TypeAlias = Literal["pass", "fail", "abstain"]
ConsensusStatus: TypeAlias = Literal["pass", "fail", "tied", "insufficient"]
JudgeStatus: TypeAlias = Literal["ok", "timeout", "error", "truncated"]
JudgeDecision: TypeAlias = Literal["pass", "fail", "abstain"]


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


@dataclass(frozen=True, slots=True)
class HumanAnnotation:
    annotator_id: str
    case_id: str
    label: HumanLabelValue


@dataclass(frozen=True, slots=True)
class HumanLabelSet:
    provenance: Provenance
    dataset_sha256: str
    candidates_sha256: str
    annotations: tuple[HumanAnnotation, ...]


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    case_id: str
    status: ConsensusStatus
    basis: str
    pass_votes: int
    fail_votes: int
    abstain_votes: int


@dataclass(frozen=True, slots=True)
class PairAgreement:
    pair_index: int
    overlapping_cases: int
    agreements: int
    agreement_rate: str | None


@dataclass(frozen=True, slots=True)
class AgreementStatistics:
    alpha: str | None
    observed_disagreements: int
    observed_pairs: int
    expected_disagreements: int
    expected_pairs: int
    comparable_cases: int
    non_abstaining_labels: int


@dataclass(frozen=True, slots=True)
class CalibrationSummary:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    evaluator_non_success: int
    human_unresolved: int
    human_insufficient: int
    evaluated_resolved: int
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HumanEvidenceReport:
    schema_version: str
    dataset_sha256: str
    candidates_sha256: str
    labels_sha256: str
    annotator_count: int
    annotation_count: int
    unanimous_cases: int
    majority_cases: int
    tied_cases: int
    insufficient_cases: int
    abstention_count: int
    consensus: tuple[ConsensusResult, ...]
    agreement: AgreementStatistics
    pair_agreements: tuple[PairAgreement, ...]
    calibration: CalibrationSummary


@dataclass(frozen=True, slots=True)
class JudgeConfiguration:
    adapter_id: str
    provider: str
    model: str
    model_version: str
    policy_sha256: str
    response_schema: str


@dataclass(frozen=True, slots=True)
class JudgeRecord:
    case_id: str
    request_sha256: str
    status: JudgeStatus
    decision: JudgeDecision | None
    reason_codes: tuple[str, ...]
    attempts: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_microusd: int


@dataclass(frozen=True, slots=True)
class JudgeRecordSet:
    provenance: Provenance
    dataset_sha256: str
    candidates_sha256: str
    configuration: JudgeConfiguration
    records: tuple[JudgeRecord, ...]


@dataclass(frozen=True, slots=True)
class JudgeCalibration:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    judge_abstain: int
    judge_non_success: int
    human_unresolved: int
    human_insufficient: int
    resolved_human_cases: int
    evaluated_resolved: int
    coverage: str
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JudgeEvidenceReport:
    schema_version: str
    dataset_sha256: str
    candidates_sha256: str
    human_labels_sha256: str
    judge_records_sha256: str
    configuration: JudgeConfiguration
    total_cases: int
    ok_cases: int
    timeout_cases: int
    error_cases: int
    truncated_cases: int
    pass_decisions: int
    fail_decisions: int
    abstain_decisions: int
    total_attempts: int
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int
    total_cost_microusd: int
    calibration: JudgeCalibration
