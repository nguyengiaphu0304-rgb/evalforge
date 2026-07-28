from __future__ import annotations

import json
from pathlib import Path

import pytest

from evalforge import (
    HumanEvidenceError,
    SchemaError,
    create_human_evidence_report,
    parse_candidates,
    parse_dataset,
    parse_human_labels,
    verify_human_evidence_report,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _report(labels: bytes | None = None) -> bytes:
    return create_human_evidence_report(
        _fixture("cases.json"),
        _fixture("candidates.json"),
        labels or _fixture("human-labels.json"),
    )


def _label_document() -> dict[str, object]:
    return json.loads(_fixture("human-labels.json"))


def test_human_evidence_is_reproducible_auditable_and_private() -> None:
    first = _report()
    assert first == _report()
    payload = json.loads(first)["payload"]
    assert payload["annotation_summary"] == {
        "abstention_count": 2,
        "annotation_count": 9,
        "annotator_count": 3,
        "insufficient_cases": 0,
        "majority_cases": 0,
        "tied_cases": 1,
        "unanimous_cases": 2,
    }
    assert payload["agreement"] == {
        "alpha": "0.650000",
        "comparable_cases": 3,
        "expected_disagreements": 24,
        "expected_pairs": 42,
        "non_abstaining_labels": 7,
        "observed_disagreements": 2,
        "observed_pairs": 10,
    }
    assert payload["calibration"]["true_positive"] == 1
    assert payload["calibration"]["evaluator_non_success"] == 1
    assert payload["calibration"]["human_unresolved"] == 1
    assert payload["calibration"]["status"] == "insufficient_evidence"
    decoded = first.decode()
    assert "rater-a" not in decoded
    assert "Welcome" not in decoded
    assert "Return the" not in decoded
    verify_human_evidence_report(
        _fixture("cases.json"),
        _fixture("candidates.json"),
        _fixture("human-labels.json"),
        first,
    )


def test_annotation_order_does_not_change_report_or_lineage() -> None:
    document = _label_document()
    document["annotations"].reverse()
    assert _report(json.dumps(document).encode()) == _report()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda document: document.update({"dataset_sha256": "0" * 64}),
            "dataset lineage",
        ),
        (
            lambda document: document.update({"candidates_sha256": "0" * 64}),
            "candidate lineage",
        ),
        (
            lambda document: document["annotations"][0].update({"label": "maybe"}),
            "unsupported",
        ),
        (
            lambda document: document["annotations"][0].update({"case_id": "unknown"}),
            "unknown",
        ),
        (
            lambda document: document["annotations"].append(document["annotations"][0]),
            "duplicate",
        ),
        (
            lambda document: document["annotations"][0].update({"email": "x@example.test"}),
            "fields",
        ),
        (lambda document: document.update({"annotations": []}), "count"),
    ],
)
def test_invalid_label_artifacts_fail_closed(mutation: object, message: str) -> None:
    document = _label_document()
    mutation(document)
    dataset = parse_dataset(_fixture("cases.json"))
    candidates = parse_candidates(_fixture("candidates.json"))
    with pytest.raises(SchemaError, match=message):
        parse_human_labels(json.dumps(document).encode(), dataset, candidates)


def test_all_abstain_and_single_category_do_not_fabricate_alpha() -> None:
    document = _label_document()
    for annotation in document["annotations"]:
        annotation["label"] = "abstain"
    payload = json.loads(_report(json.dumps(document).encode()))["payload"]
    assert payload["agreement"]["alpha"] is None
    assert payload["annotation_summary"]["insufficient_cases"] == 3
    assert len(payload["annotator_pairs"]) == 3
    assert all(pair["agreement_rate"] is None for pair in payload["annotator_pairs"])

    for annotation in document["annotations"]:
        annotation["label"] = "pass"
    payload = json.loads(_report(json.dumps(document).encode()))["payload"]
    assert payload["agreement"]["alpha"] is None
    assert payload["annotation_summary"]["unanimous_cases"] == 3


def test_systematic_disagreement_can_produce_negative_alpha() -> None:
    document = _label_document()
    document["annotations"] = [
        {"annotator_id": "rater-a", "case_id": "welcome", "label": "pass"},
        {"annotator_id": "rater-b", "case_id": "welcome", "label": "fail"},
        {"annotator_id": "rater-a", "case_id": "json-profile", "label": "fail"},
        {"annotator_id": "rater-b", "case_id": "json-profile", "label": "pass"},
    ]
    payload = json.loads(_report(json.dumps(document).encode()))["payload"]
    assert payload["agreement"]["alpha"] == "-0.500000"
    assert payload["annotation_summary"]["tied_cases"] == 2
    assert payload["annotation_summary"]["insufficient_cases"] == 1


def test_majority_consensus_is_distinct_from_unanimity() -> None:
    document = _label_document()
    document["annotations"] = [
        {"annotator_id": "rater-a", "case_id": "welcome", "label": "pass"},
        {"annotator_id": "rater-b", "case_id": "welcome", "label": "pass"},
        {"annotator_id": "rater-c", "case_id": "welcome", "label": "fail"},
    ]
    payload = json.loads(_report(json.dumps(document).encode()))["payload"]
    assert payload["annotation_summary"]["majority_cases"] == 1
    assert payload["annotation_summary"]["insufficient_cases"] == 2


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("payload", "agreement", "alpha"), "1.000000"),
        (("payload", "calibration", "true_positive"), 99),
        (("payload", "consensus", 0, "status"), "pass"),
        (("sha256",), "0" * 64),
    ],
)
def test_human_evidence_tampering_is_rejected(
    path: tuple[object, ...],
    replacement: object,
) -> None:
    document = json.loads(_report())
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    tampered = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(HumanEvidenceError):
        verify_human_evidence_report(
            _fixture("cases.json"),
            _fixture("candidates.json"),
            _fixture("human-labels.json"),
            tampered,
        )


def test_oversized_report_is_rejected_before_parsing() -> None:
    with pytest.raises(HumanEvidenceError, match="byte limit"):
        verify_human_evidence_report(
            _fixture("cases.json"),
            _fixture("candidates.json"),
            _fixture("human-labels.json"),
            b" " * 1_048_577,
        )
