"""Public API for deterministic, provenance-first evaluation."""

from evalforge.engine import EvaluationError, create_report, evaluate, verify_report
from evalforge.io import SchemaError, parse_candidates, parse_dataset
from evalforge.models import (
    CandidateOutput,
    CaseResult,
    CheckOutcome,
    Criterion,
    Dataset,
    EvaluationCase,
    EvaluationReport,
    Provenance,
    Summary,
)

__version__ = "0.1.0"

__all__ = [
    "CandidateOutput",
    "CaseResult",
    "CheckOutcome",
    "Criterion",
    "Dataset",
    "EvaluationCase",
    "EvaluationError",
    "EvaluationReport",
    "Provenance",
    "SchemaError",
    "Summary",
    "__version__",
    "create_report",
    "evaluate",
    "parse_candidates",
    "parse_dataset",
    "verify_report",
]
