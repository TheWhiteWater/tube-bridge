#!/usr/bin/env python3
"""Reject public release archives containing private deployment metadata."""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path
import zipfile


FORBIDDEN_MARKERS = (b"deploy_url", b".railway.app")


def _scan_member(archive: Path, member: str, content: bytes) -> list[str]:
    return [
        f"{archive.name}:{member}:{marker.decode()}"
        for marker in FORBIDDEN_MARKERS
        if marker in content
    ]


def scan_archive(path: Path) -> list[str]:
    findings: list[str] = []
    if path.suffix in {".whl", ".zip"}:
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.endswith("/"):
                    findings.extend(_scan_member(path, member, archive.read(member)))
        return findings

    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is not None:
                    findings.extend(_scan_member(path, member.name, extracted.read()))
        return findings

    raise ValueError(f"unsupported release artifact: {path}")


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: verify-release-artifacts.py <wheel> <sdist> [plugin.zip]", file=sys.stderr)
        return 2

    paths = [Path(value) for value in argv]
    try:
        findings = [finding for path in paths for finding in scan_archive(path)]
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"release artifact verification failed: {exc}", file=sys.stderr)
        return 2

    if findings:
        print("unexpected private deployment metadata in release artifacts:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print(f"verified {len(paths)} self-hosted-only release artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
