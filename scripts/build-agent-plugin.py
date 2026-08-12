#!/usr/bin/env python3
"""Build the portable Agent Plugins v1 preview bundle for a GitHub Release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "LICENSE",
    "README.md",
    "plugin.json",
    "mcp.json",
    "pyproject.toml",
    "requirements-release.txt",
)
ROOT_DIRECTORIES = ("skills", "tube_bridge")
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    if manifest.get("version") != version:
        raise SystemExit(
            f"plugin version {manifest.get('version')!r} does not match project {version!r}"
        )
    return version


def _source_files() -> list[Path]:
    files = [ROOT / name for name in ROOT_FILES]
    for directory in ROOT_DIRECTORIES:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())

    selected: list[Path] = []
    for path in sorted(files, key=lambda value: value.relative_to(ROOT).as_posix()):
        if path.is_symlink():
            raise SystemExit(f"plugin bundle refuses symlink: {path.relative_to(ROOT)}")
        if path.suffix in EXCLUDED_SUFFIXES or "__pycache__" in path.parts:
            continue
        if not path.is_file():
            raise SystemExit(f"plugin bundle input is missing: {path.relative_to(ROOT)}")
        selected.append(path)
    return selected


def build(output_dir: Path) -> Path:
    version = _version()
    archive_root = f"tube-bridge-agent-plugin-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{archive_root}.zip"

    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source in _source_files():
            relative = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{archive_root}/{relative}", (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, source.read_bytes(), compresslevel=9)

    print(destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "plugin-dist")
    args = parser.parse_args()
    build(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
