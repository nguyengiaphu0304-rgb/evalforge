from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.release_evidence import generate, verify
from scripts.release_verify import canonical_sdist, inspect_wheel


def _sdist(path: Path, members: list[tuple[str, bytes, str]]) -> None:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        for name, content, kind in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            if kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                info.size = 0
            archive.addfile(info, None if kind == "symlink" else io.BytesIO(content))
    with gzip.open(path, "wb") as stream:
        stream.write(raw.getvalue())


def _duplicate_wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("evalforge/__init__.py", "")
        archive.writestr("evalforge/__init__.py", "")
        archive.writestr(
            "evalforge-1.0.0.dist-info/METADATA",
            "Name: evalforge\nVersion: 0.0.0\n",
        )


def test_release_evidence_is_deterministic_and_detects_drift(tmp_path: Path) -> None:
    checked = tmp_path / "checked"
    generate(checked)
    verify(checked)
    (checked / "evaluation.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="drift"):
        verify(checked)


@pytest.mark.parametrize("name", ["/absolute", "../escape", "root\\backslash"])
def test_sdist_rejects_unsafe_paths(tmp_path: Path, name: str) -> None:
    path = tmp_path / "bad.tar.gz"
    _sdist(path, [(name, b"x", "file")])
    with pytest.raises(ValueError, match=r"unsafe|backslash"):
        canonical_sdist(path)


def test_sdist_rejects_symlink(tmp_path: Path) -> None:
    path = tmp_path / "bad.tar.gz"
    _sdist(path, [("evalforge-1.0.0/src/link", b"", "symlink")])
    with pytest.raises(ValueError, match="non-regular"):
        canonical_sdist(path)


def test_sdist_rejects_duplicate_members(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.tar.gz"
    metadata = b"Name: evalforge\nVersion: 1.0.0\n"
    _sdist(
        path,
        [
            ("evalforge-1.0.0/PKG-INFO", metadata, "file"),
            ("evalforge-1.0.0/PKG-INFO", metadata, "file"),
        ],
    )
    with pytest.raises(ValueError, match="uniqueness"):
        canonical_sdist(path)


def test_wheel_rejects_duplicate_and_wrong_metadata(tmp_path: Path) -> None:
    path = tmp_path / "bad.whl"
    with pytest.warns(UserWarning, match="Duplicate name"):
        _duplicate_wheel(path)
    with pytest.raises(ValueError, match="uniqueness"):
        inspect_wheel(path)


def test_wheel_rejects_wrong_version_metadata(tmp_path: Path) -> None:
    path = tmp_path / "wrong-version.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("evalforge/__init__.py", "")
        archive.writestr(
            "evalforge-1.0.0.dist-info/METADATA",
            "Name: evalforge\nVersion: 0.0.0\n",
        )
    with pytest.raises(ValueError, match="identity"):
        inspect_wheel(path)
