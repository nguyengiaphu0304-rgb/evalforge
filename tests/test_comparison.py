from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from evalforge import (
    ComparisonError,
    SchemaError,
    create_comparison_report,
    parse_dataset,
    parse_slice_set,
    verify_comparison_report,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
SIX_PLACES = Decimal("0.000001")


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _report(
    candidate_a: bytes | None = None,
    candidate_b: bytes | None = None,
    slices: bytes | None = None,
    *,
    seed: int = 7,
    resamples: int = 200,
) -> bytes:
    return create_comparison_report(
        _fixture("cases.json"),
        candidate_a or _fixture("candidates.json"),
        candidate_b or _fixture("candidates-b.json"),
        slices or _fixture("slices.json"),
        seed=seed,
        resamples=resamples,
    )


def test_comparison_is_reproducible_complete_and_verifiable() -> None:
    first = _report()
    assert first == _report()
    payload = json.loads(first)["payload"]
    overall = payload["overall"]
    assert overall["total_cases"] == 3
    assert overall["candidate_a_passed"] == 2
    assert overall["candidate_b_passed"] == 1
    assert overall["regressed_cases"] == 1
    assert Decimal(overall["pass_rate_delta"]) == (Decimal(-1) / Decimal(3)).quantize(SIX_PLACES)
    assert overall["conclusion"] == "insufficient_evidence"
    assert sum(item["count"] for item in overall["transitions"]) == 3
    assert len(overall["transitions"]) == 25
    assert len(payload["slices"]) == 3
    assert "Return the" not in first.decode()
    assert "Welcome" not in first.decode()
    verify_comparison_report(
        _fixture("cases.json"),
        _fixture("candidates.json"),
        _fixture("candidates-b.json"),
        _fixture("slices.json"),
        first,
        seed=7,
        resamples=200,
    )


def test_swapping_candidates_reverses_delta_and_interval() -> None:
    forward = json.loads(_report())["payload"]["overall"]
    reverse = json.loads(_report(_fixture("candidates-b.json"), _fixture("candidates.json")))[
        "payload"
    ]["overall"]
    expected = (Decimal(1) / Decimal(3)).quantize(SIX_PLACES)
    assert Decimal(forward["pass_rate_delta"]) == -expected
    assert Decimal(reverse["pass_rate_delta"]) == expected
    assert Decimal(forward["interval"]["lower"]) == -Decimal(reverse["interval"]["upper"])
    assert Decimal(forward["interval"]["upper"]) == -Decimal(reverse["interval"]["lower"])


def test_input_and_slice_order_do_not_change_output() -> None:
    candidate_b = json.loads(_fixture("candidates-b.json"))
    slices = json.loads(_fixture("slices.json"))
    candidate_b["outputs"].reverse()
    slices["slices"].reverse()
    for item in slices["slices"]:
        item["case_ids"].reverse()
    assert (
        _report(
            candidate_b=json.dumps(candidate_b).encode(),
            slices=json.dumps(slices).encode(),
        )
        == _report()
    )


def test_identical_runs_have_zero_delta_and_only_ties() -> None:
    report = json.loads(_report(_fixture("candidates.json"), _fixture("candidates.json")))[
        "payload"
    ]["overall"]
    assert Decimal(report["pass_rate_delta"]) == Decimal(0)
    assert report["improved_cases"] == 0
    assert report["regressed_cases"] == 0
    assert report["tied_cases"] == 3
    assert report["interval"] == {"lower": "0.000000", "upper": "0.000000"}


@pytest.mark.parametrize(
    ("seed", "resamples", "message"),
    [
        (-1, 200, "seed"),
        (2**64, 200, "seed"),
        (True, 200, "seed"),
        (0, 99, "resamples"),
        (0, 10_001, "resamples"),
        (0, True, "resamples"),
    ],
)
def test_method_parameter_boundaries(
    seed: int,
    resamples: int,
    message: str,
) -> None:
    with pytest.raises(ComparisonError, match=message):
        _report(seed=seed, resamples=resamples)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda document: document.update({"unexpected": True}), "fields"),
        (lambda document: document.update({"slices": []}), "slice count"),
        (
            lambda document: document["slices"][0].update({"case_ids": []}),
            "member count",
        ),
        (
            lambda document: document["slices"][0].update({"case_ids": ["unknown"]}),
            "unknown",
        ),
        (
            lambda document: document["slices"].append(document["slices"][0]),
            "duplicate slice",
        ),
    ],
)
def test_invalid_slice_artifacts_fail_closed(mutation: object, message: str) -> None:
    document = json.loads(_fixture("slices.json"))
    mutation(document)
    dataset = parse_dataset(_fixture("cases.json"))
    with pytest.raises(SchemaError, match=message):
        parse_slice_set(json.dumps(document).encode(), dataset)


def test_duplicate_slice_member_is_rejected_but_overlap_is_allowed() -> None:
    document = json.loads(_fixture("slices.json"))
    document["slices"][0]["case_ids"] = ["json-profile", "json-profile"]
    with pytest.raises(SchemaError, match="duplicate slice case"):
        parse_slice_set(json.dumps(document).encode(), parse_dataset(_fixture("cases.json")))
    parse_slice_set(_fixture("slices.json"), parse_dataset(_fixture("cases.json")))


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("payload", "overall", "regressed_cases"), 0),
        (("payload", "overall", "interval", "upper"), "1.000000"),
        (("payload", "method", "version"), "unknown"),
        (("sha256",), "0" * 64),
    ],
)
def test_comparison_tampering_is_rejected(
    path: tuple[object, ...],
    replacement: object,
) -> None:
    document = json.loads(_report())
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    tampered = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ComparisonError):
        verify_comparison_report(
            _fixture("cases.json"),
            _fixture("candidates.json"),
            _fixture("candidates-b.json"),
            _fixture("slices.json"),
            tampered,
            seed=7,
            resamples=200,
        )


def test_sufficient_sample_uses_descriptive_not_causal_conclusion() -> None:
    cases = [
        {
            "case_id": f"case-{index:02d}",
            "input": "",
            "criteria": [{"criterion_id": "exact", "kind": "exact_text", "expected": "pass"}],
        }
        for index in range(30)
    ]
    dataset = {
        "schema_version": "evalforge/v1",
        "provenance": {
            "source": "synthetic-test",
            "license": "CC0-1.0",
            "retrieved_at": "2026-07-29T00:00:00Z",
            "schema_version": "fixture/v1",
        },
        "cases": cases,
    }
    outputs_a = [
        {
            "case_id": item["case_id"],
            "status": "ok",
            "output": "fail" if index < 10 else "pass",
        }
        for index, item in enumerate(cases)
    ]
    outputs_b = [
        {
            "case_id": item["case_id"],
            "status": "ok",
            "output": "pass" if index < 6 or index >= 15 else "fail",
        }
        for index, item in enumerate(cases)
    ]
    candidates_a = {"schema_version": "evalforge/v1", "outputs": outputs_a}
    candidates_b = {"schema_version": "evalforge/v1", "outputs": outputs_b}
    slices = {
        "schema_version": "evalforge/slices-v1",
        "provenance": dataset["provenance"],
        "slices": [{"slice_id": "all", "case_ids": [item["case_id"] for item in cases]}],
    }
    report = json.loads(
        create_comparison_report(
            json.dumps(dataset).encode(),
            json.dumps(candidates_a).encode(),
            json.dumps(candidates_b).encode(),
            json.dumps(slices).encode(),
            seed=11,
            resamples=100,
        )
    )["payload"]["overall"]
    assert report["discordant_cases"] == 11
    assert Decimal(report["pass_rate_delta"]) == (Decimal(1) / Decimal(30)).quantize(SIX_PLACES)
    assert report["warnings"] == []
    assert report["conclusion"] == "descriptive_increase"


def test_aggregate_bootstrap_work_is_bounded() -> None:
    cases = [
        {
            "case_id": f"case-{index:02d}",
            "input": "",
            "criteria": [{"criterion_id": "exact", "kind": "exact_text", "expected": "pass"}],
        }
        for index in range(30)
    ]
    provenance = {
        "source": "synthetic-test",
        "license": "CC0-1.0",
        "retrieved_at": "2026-07-29T00:00:00Z",
        "schema_version": "fixture/v1",
    }
    dataset = {
        "schema_version": "evalforge/v1",
        "provenance": provenance,
        "cases": cases,
    }
    outputs = {
        "schema_version": "evalforge/v1",
        "outputs": [
            {"case_id": item["case_id"], "status": "ok", "output": "pass"} for item in cases
        ],
    }
    members = [item["case_id"] for item in cases]
    slices = {
        "schema_version": "evalforge/slices-v1",
        "provenance": provenance,
        "slices": [{"slice_id": f"slice-{index:02d}", "case_ids": members} for index in range(34)],
    }
    with pytest.raises(ComparisonError, match="compute budget"):
        create_comparison_report(
            json.dumps(dataset).encode(),
            json.dumps(outputs).encode(),
            json.dumps(outputs).encode(),
            json.dumps(slices).encode(),
            resamples=10_000,
        )
