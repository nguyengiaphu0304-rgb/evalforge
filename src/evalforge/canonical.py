"""Canonical, immutable JSON representation and hashing helpers."""

from __future__ import annotations

import json
import math
import unicodedata
from hashlib import sha256
from typing import TYPE_CHECKING, cast

from evalforge.models import JsonArray, JsonObject

if TYPE_CHECKING:
    from evalforge.models import JsonValue

MAX_DEPTH = 32


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the canonical schema."""


def normalize_text(value: str) -> str:
    """Return Unicode text in the schema's canonical normalization form."""
    return unicodedata.normalize("NFC", value)


def freeze_json(value: object, *, depth: int = 0) -> JsonValue:
    """Validate and convert a decoded JSON value to immutable domain types."""
    if depth > MAX_DEPTH:
        raise CanonicalizationError("JSON nesting depth exceeds the limit")
    if value is None or isinstance(value, bool | int | str):
        return normalize_text(value) if isinstance(value, str) else value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("non-finite JSON numbers are not allowed")
        return value
    if isinstance(value, list):
        return JsonArray(tuple(freeze_json(item, depth=depth + 1) for item in value))
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        if not all(isinstance(key, str) for key in mapping):
            raise CanonicalizationError("JSON object keys must be strings")
        items = (
            (normalize_text(key), freeze_json(item, depth=depth + 1))
            for key, item in cast("dict[str, object]", mapping).items()
        )
        frozen = tuple(sorted(items, key=lambda item: item[0]))
        if len({key for key, _ in frozen}) != len(frozen):
            raise CanonicalizationError("normalized JSON object keys collide")
        return JsonObject(frozen)
    raise CanonicalizationError("unsupported JSON value")


def thaw_json(value: JsonValue) -> object:
    """Convert an immutable domain JSON value to standard JSON-compatible types."""
    if isinstance(value, JsonArray):
        return [thaw_json(item) for item in value.items]
    if isinstance(value, JsonObject):
        return {key: thaw_json(item) for key, item in value.items}
    return value


def canonical_bytes(value: object) -> bytes:
    """Serialize a JSON-compatible value to canonical newline-terminated UTF-8."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def digest(value: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return sha256(value).hexdigest()
