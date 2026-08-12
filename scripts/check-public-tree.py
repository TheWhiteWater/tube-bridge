#!/usr/bin/env python3
"""Fail when repository-only or machine-specific material enters the public tree."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
FORBIDDEN_ROOTS = {
    ".brainops",
    ".hermes",
    ".tme",
    "operator",
}
FORBIDDEN_FILES = {
    "AGENTS.md",
    "PROJECT_VISION.md",
    "railway.toml",
    "scripts/station-verify.mjs",
}
CONTENT_RULES = {
    "absolute Linux user path": re.compile(rb"/home/[A-Za-z0-9._-]+/"),
    "absolute macOS user path": re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
    "private deployment hostname": re.compile(rb"[A-Za-z0-9.-]+\.railway\.app", re.I),
    "local orchestration variable": re.compile(rb"BRAINOPS_[A-Z0-9_]+"),
    "local orchestration name": re.compile(rb"BrainOps Station|station-codex", re.I),
    "workspace agent identifier": re.compile(rb"\b[WS]-[0-9]{4,}\b"),
    "work-item identifier": re.compile(rb"\bWI-[A-Z0-9_.-]+\b"),
    "personal email": re.compile(rb"ali\.agzamov" + rb"@gmail\.com", re.I),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / value.decode() for value in result.stdout.split(b"\0") if value]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        root_name = relative.split("/", 1)[0]
        if root_name in FORBIDDEN_ROOTS or relative in FORBIDDEN_FILES:
            findings.append(f"forbidden path: {relative}")
            continue
        if path.resolve() == SELF or not path.is_file():
            continue
        content = path.read_bytes()
        for label, pattern in CONTENT_RULES.items():
            if pattern.search(content):
                findings.append(f"{label}: {relative}")

    if findings:
        print("public-tree hygiene check failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("public-tree hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
