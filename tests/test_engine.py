from __future__ import annotations

import json
from pathlib import Path

import pytest

from evalforge import EvaluationError, create_report, verify_report

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_report_is_reproducible_and_counts_non_success_statuses() -> None:
    dataset = _fixture("cases.json")
    candidates = _fixture("candidates.json")
    first = create_report(dataset, candidates)
    second = create_report(dataset, candidates)
    assert first == second
    payload = json.loads(first)["payload"]
    assert payload["summary"] == {
        "error_cases": 1,
        "failed_cases": 0,
        "missing_cases": 0,
        "pass_rate": "0.666667",
        "passed_cases": 2,
        "timeout_cases": 0,
        "total_cases": 3,
    }
    assert "input" not in first.decode()
    assert "Welcome" not in first.decode()
    verify_report(dataset, candidates, first)


def test_input_order_does_not_change_report() -> None:
    dataset = json.loads(_fixture("cases.json"))
    candidates = json.loads(_fixture("candidates.json"))
    expected = create_report(
        json.dumps(dataset).encode(),
        json.dumps(candidates).encode(),
    )
    dataset["cases"].reverse()
    candidates["outputs"].reverse()
    assert create_report(json.dumps(dataset).encode(), json.dumps(candidates).encode()) == expected


@pytest.mark.parametrize(
    ("status", "field"),
    [("timeout", "timeout_cases"), ("error", "error_cases")],
)
def test_non_ok_status_is_never_scored_as_success(status: str, field: str) -> None:
    candidates = {
        "schema_version": "evalforge/v1",
        "outputs": [{"case_id": "welcome", "status": status, "output": None}],
    }
    report = json.loads(create_report(_fixture("cases.json"), json.dumps(candidates).encode()))
    assert report["payload"]["summary"][field] == 1
    assert report["payload"]["summary"]["missing_cases"] == 2
    assert report["payload"]["summary"]["passed_cases"] == 0


def test_unknown_candidate_case_fails_closed() -> None:
    candidates = {
        "schema_version": "evalforge/v1",
        "outputs": [{"case_id": "unknown", "status": "ok", "output": "x"}],
    }
    with pytest.raises(EvaluationError, match="unknown"):
        create_report(_fixture("cases.json"), json.dumps(candidates).encode())


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("payload", "summary", "passed_cases"), 3),
        (("payload", "results", 0, "status"), "failed"),
        (("sha256",), "0" * 64),
    ],
)
def test_report_tampering_is_rejected(path: tuple[object, ...], replacement: object) -> None:
    dataset = _fixture("cases.json")
    candidates = _fixture("candidates.json")
    document = json.loads(create_report(dataset, candidates))
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    tampered = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(EvaluationError):
        verify_report(dataset, candidates, tampered)


def test_json_object_and_array_are_not_equal_even_when_empty() -> None:
    dataset = {
        "schema_version": "evalforge/v1",
        "provenance": {
            "source": "synthetic-test",
            "license": "CC0-1.0",
            "retrieved_at": "2026-07-29T00:00:00Z",
            "schema_version": "fixture/v1",
        },
        "cases": [
            {
                "case_id": "shape",
                "input": "Return an empty object.",
                "criteria": [
                    {"criterion_id": "shape", "kind": "json_equal", "expected": {}},
                ],
            }
        ],
    }
    candidates = {
        "schema_version": "evalforge/v1",
        "outputs": [{"case_id": "shape", "status": "ok", "output": "[]"}],
    }
    report = json.loads(
        create_report(json.dumps(dataset).encode(), json.dumps(candidates).encode())
    )
    assert report["payload"]["results"][0]["checks"][0]["code"] == "json_mismatch"


def test_oversize_report_is_rejected_before_parsing() -> None:
    with pytest.raises(EvaluationError, match="byte limit"):
        verify_report(_fixture("cases.json"), _fixture("candidates.json"), b" " * 1_048_577)
