#!/usr/bin/env python3
"""Build a deterministic MCPB v0.4 archive from public tube-bridge files."""

from __future__ import annotations

import argparse
import tomllib
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "tube_bridge"
ROOT_FILES = ("manifest.json", "pyproject.toml", "README.md", "LICENSE", "server.py")
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def project_version() -> str:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    return str(project["version"])


def bundle_files() -> list[Path]:
    for candidate in SOURCE_ROOT.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(f"refusing symlink in bundle source: {candidate}")

    files = [PROJECT_ROOT / name for name in ROOT_FILES]
    files.extend(sorted(SOURCE_ROOT.rglob("*.py"), key=lambda path: path.as_posix()))

    for path in files:
        if path.is_symlink():
            raise ValueError(f"refusing symlink in bundle: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"required bundle file is missing: {path}")
        path.resolve().relative_to(PROJECT_ROOT.resolve())

    return sorted(files, key=lambda path: path.relative_to(PROJECT_ROOT).as_posix())


def build(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"tube-bridge-{project_version()}.mcpb"

    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for path in bundle_files():
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Directory for tube-bridge-<version>.mcpb",
    )
    args = parser.parse_args()
    print(build(args.output_dir).resolve())


if __name__ == "__main__":
    main()
