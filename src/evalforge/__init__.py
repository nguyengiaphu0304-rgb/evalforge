"""Public API for deterministic, provenance-first evaluation."""

from evalforge.comparison import (
    ComparisonError,
    create_comparison_report,
    verify_comparison_report,
)
from evalforge.engine import EvaluationError, create_report, evaluate, verify_report
from evalforge.io import SchemaError, parse_candidates, parse_dataset, parse_slice_set
from evalforge.models import (
    CandidateOutput,
    CaseResult,
    CheckOutcome,
    ComparisonReport,
    ComparisonSummary,
    Criterion,
    Dataset,
    EvaluationCase,
    EvaluationReport,
    Provenance,
    SliceComparison,
    SliceDefinition,
    SliceSet,
    Summary,
)

__version__ = "0.2.0"

__all__ = [
    "CandidateOutput",
    "CaseResult",
    "CheckOutcome",
    "ComparisonError",
    "ComparisonReport",
    "ComparisonSummary",
    "Criterion",
    "Dataset",
    "EvaluationCase",
    "EvaluationError",
    "EvaluationReport",
    "Provenance",
    "SchemaError",
    "SliceComparison",
    "SliceDefinition",
    "SliceSet",
    "Summary",
    "__version__",
    "create_comparison_report",
    "create_report",
    "evaluate",
    "parse_candidates",
    "parse_dataset",
    "parse_slice_set",
    "verify_comparison_report",
    "verify_report",
]
