from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Final

PACKAGE: Final = "evalforge"
VERSION: Final = "1.0.0"
EPOCH: Final = 1_785_283_200
MAX_ARCHIVE_BYTES: Final = 1_048_576
MAX_WHEEL_FILES: Final = 64
MAX_SDIST_FILES: Final = 128
FORBIDDEN_PARTS: Final = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
}
ALLOWED_SDIST_TOP_LEVEL: Final = {
    ".github",
    ".gitignore",
    "LICENSE",
    "PKG-INFO",
    "README.md",
    "docs",
    "evidence",
    "fixtures",
    "pyproject.toml",
    "scripts",
    "src",
    "tests",
}


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name: str) -> PurePosixPath:
    if "\\" in name:
        raise ValueError("archive member contains a backslash")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
        raise ValueError("archive member path is unsafe")
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        raise ValueError("archive contains a forbidden path")
    return path


def inspect_wheel(path: Path) -> None:
    """Fail closed on malformed, unexpected, or oversized wheels."""
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("wheel exceeds size budget")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or len(names) > MAX_WHEEL_FILES:
            raise ValueError("wheel member count or uniqueness policy failed")
        prefixes = (f"{PACKAGE}/", f"{PACKAGE}-{VERSION}.dist-info/")
        for info in infos:
            name = _safe_name(info.filename)
            if not str(name).startswith(prefixes):
                raise ValueError("wheel contains a file outside the package allowlist")
            mode = info.external_attr >> 16
            if mode and (mode & 0o170000) not in {0, 0o100000}:
                raise ValueError("wheel contains a non-regular member")
        metadata_name = f"{PACKAGE}-{VERSION}.dist-info/METADATA"
        if metadata_name not in names:
            raise ValueError("wheel metadata is missing")
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        if metadata["Name"] != PACKAGE or metadata["Version"] != VERSION:
            raise ValueError("wheel metadata identity is wrong")


def canonical_sdist(path: Path) -> bytes:
    """Validate and deterministically repack an sdist."""
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("sdist exceeds size budget")
    prefix = f"{PACKAGE}-{VERSION}/"
    files: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or len(names) > MAX_SDIST_FILES:
            raise ValueError("sdist member count or uniqueness policy failed")
        for member in members:
            name = str(_safe_name(member.name))
            if not name.startswith(prefix):
                raise ValueError("sdist root is wrong")
            relative = PurePosixPath(name).relative_to(PurePosixPath(prefix))
            if not relative.parts or relative.parts[0] not in ALLOWED_SDIST_TOP_LEVEL:
                raise ValueError("sdist contains a file outside the source allowlist")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("sdist contains a non-regular member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("sdist member could not be read")
            files[name] = stream.read()
    pkg_info = f"{prefix}PKG-INFO"
    if pkg_info not in files:
        raise ValueError("sdist metadata is missing")
    metadata = BytesParser().parsebytes(files[pkg_info])
    if metadata["Name"] != PACKAGE or metadata["Version"] != VERSION:
        raise ValueError("sdist metadata identity is wrong")

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as output:
        for name in sorted(files):
            content = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = EPOCH
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            output.addfile(info, io.BytesIO(content))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=EPOCH) as gzip_stream:
        gzip_stream.write(tar_buffer.getvalue())
    return compressed.getvalue()


def _build(output: Path) -> tuple[Path, Path]:
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = str(EPOCH)
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output)],
        check=True,
        env=environment,
    )
    wheels = tuple(output.glob("*.whl"))
    sdists = tuple(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("build did not produce exactly one wheel and one sdist")
    return wheels[0], sdists[0]


def _isolated_smoke(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="evalforge-wheel-") as temporary:
        virtualenv = Path(temporary) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(virtualenv)], check=True)
        python = virtualenv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import evalforge; "
                    "assert evalforge.__version__ == '1.0.0'; "
                    "assert all(hasattr(evalforge, name) for name in evalforge.__all__)"
                ),
            ],
            check=True,
        )


def verify_release(output: Path) -> None:
    """Build twice, verify reproducibility, and publish one checked artifact set."""
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("release output directory must be empty")
    with tempfile.TemporaryDirectory(prefix="evalforge-build-") as temporary:
        root = Path(temporary)
        first_wheel, first_sdist = _build(root / "first")
        second_wheel, second_sdist = _build(root / "second")
        inspect_wheel(first_wheel)
        inspect_wheel(second_wheel)
        if first_wheel.read_bytes() != second_wheel.read_bytes():
            raise ValueError("wheel builds are not byte-identical")
        first_canonical = canonical_sdist(first_sdist)
        second_canonical = canonical_sdist(second_sdist)
        if first_canonical != second_canonical:
            raise ValueError("canonical sdist builds are not byte-identical")

        wheel = output / first_wheel.name
        sdist = output / f"{PACKAGE}-{VERSION}.tar.gz"
        wheel.write_bytes(first_wheel.read_bytes())
        sdist.write_bytes(first_canonical)
        inspect_wheel(wheel)
        if canonical_sdist(sdist) != sdist.read_bytes():
            raise ValueError("canonical sdist is not idempotent")
        _isolated_smoke(wheel)
        sums = "".join(f"{sha256(path)}  {path.name}\n" for path in sorted((wheel, sdist)))
        (output / "SHA256SUMS").write_text(sums, encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify EvalForge v1.0 release artifacts")
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    verify_release(arguments.output_dir)


if __name__ == "__main__":
    main()
