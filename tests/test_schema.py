from __future__ import annotations

import json
from pathlib import Path

import pytest

from evalforge import SchemaError, parse_candidates, parse_dataset

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _dataset() -> dict[str, object]:
    return json.loads((FIXTURES / "cases.json").read_bytes())


def test_unicode_nfc_text_matches_and_is_canonical() -> None:
    document = _dataset()
    document["cases"][0]["input"] = "Cafe\u0301"
    parsed = parse_dataset(json.dumps(document).encode())
    assert any(case.input_text == "Café" for case in parsed.cases)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(constant: str) -> None:
    raw = (
        '{"schema_version":"evalforge/v1","provenance":{"source":"x","license":"x",'
        '"retrieved_at":"2026-01-01T00:00:00Z","schema_version":"x"},'
        f'"cases":[{{"case_id":"x","input":"","criteria":[{{"criterion_id":"x",'
        f'"kind":"json_equal","expected":{constant}}}]}}]}}'
    ).encode()
    with pytest.raises(SchemaError, match="non-finite"):
        parse_dataset(raw)


def test_duplicate_json_keys_are_rejected() -> None:
    with pytest.raises(SchemaError, match="duplicate"):
        parse_candidates(
            b'{"schema_version":"evalforge/v1","schema_version":"evalforge/v1","outputs":[]}'
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("cases", [], "case count"),
        ("schema_version", "future", "schema version"),
    ],
)
def test_invalid_dataset_boundaries(field: str, value: object, message: str) -> None:
    document = _dataset()
    document[field] = value
    with pytest.raises(SchemaError, match=message):
        parse_dataset(json.dumps(document).encode())


def test_duplicate_case_and_criterion_ids_are_rejected() -> None:
    document = _dataset()
    document["cases"].append(document["cases"][0])
    with pytest.raises(SchemaError, match="duplicate case"):
        parse_dataset(json.dumps(document).encode())

    document = _dataset()
    document["cases"][0]["criteria"].append(document["cases"][0]["criteria"][0])
    with pytest.raises(SchemaError, match="duplicate criterion"):
        parse_dataset(json.dumps(document).encode())


def test_candidate_status_contract_and_duplicates() -> None:
    with pytest.raises(SchemaError, match="must be null"):
        parse_candidates(
            b'{"schema_version":"evalforge/v1","outputs":['
            b'{"case_id":"x","status":"timeout","output":"partial"}]}'
        )
    with pytest.raises(SchemaError, match="duplicate candidate"):
        parse_candidates(
            b'{"schema_version":"evalforge/v1","outputs":['
            b'{"case_id":"x","status":"ok","output":""},'
            b'{"case_id":"x","status":"error","output":null}]}'
        )


def test_unknown_fields_and_oversize_artifacts_are_rejected() -> None:
    document = _dataset()
    document["unexpected"] = True
    with pytest.raises(SchemaError, match="fields"):
        parse_dataset(json.dumps(document).encode())
    with pytest.raises(SchemaError, match="byte limit"):
        parse_dataset(b" " * 1_048_577)


def test_json_nesting_depth_is_bounded() -> None:
    document = _dataset()
    value: object = "leaf"
    for _ in range(34):
        value = [value]
    document["cases"][0]["criteria"][0] = {
        "criterion_id": "deep",
        "kind": "json_equal",
        "expected": value,
    }
    with pytest.raises(ValueError, match="nesting"):
        parse_dataset(json.dumps(document).encode())
