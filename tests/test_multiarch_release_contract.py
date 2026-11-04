"""Container releases must cover amd64 and arm64 before any channel is published."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SMOKE = ROOT / "scripts/smoke-container-runtime.py"


def job(name: str) -> str:
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z-]+:\n|\Z)", RELEASE, re.M | re.S)
    assert match, f"release workflow has no job {name!r}"
    return match.group(1)


def test_each_platform_is_verified_on_a_native_runner() -> None:
    verify = job("verify-container")
    assert "platform: linux/amd64" in verify
    assert "platform: linux/arm64" in verify
    assert "runner: ubuntu-24.04-arm" in verify
    assert "setup-qemu-action" not in RELEASE
    assert "fail-fast: false" in verify


def test_platform_jobs_exercise_the_real_runtime_before_pushing() -> None:
    verify = job("verify-container")
    order = [
        verify.index("runtime image secret/private-marker scan failed"),
        verify.index("-m pip check"),
        verify.index("scripts/smoke-container-runtime.py"),
        verify.index("tests/mcp_client_smoke.py"),
        verify.index('docker push "$ref"'),
    ]
    assert order == sorted(order)


def test_candidate_is_a_single_manifest_so_the_index_gate_can_match_it() -> None:
    verify = job("verify-container")
    assert "provenance: false" in verify
    assert "sbom: false" in verify


def test_release_tags_only_move_after_both_platforms_pass() -> None:
    publish = job("publish-container")
    assert "needs: verify-container" in publish
    assert '{"amd64.txt", "arm64.txt"}' in publish
    assert '{("linux", "amd64"), ("linux", "arm64")}' in publish
    assert "index does not reference the inspected image digests" in publish
    assert "docker push" not in publish


def test_pypi_waits_for_the_container_so_a_failed_build_cannot_half_release() -> None:
    needs = re.search(r"needs:\s*\[([^\]]*)\]", job("publish-pypi"))
    assert needs, "publish-pypi must list its needs"
    assert {name.strip() for name in needs.group(1).split(",")} == {
        "verify-and-build",
        "publish-container",
    }


def test_dockerfile_never_compiles_dependencies_and_pins_the_distribution() -> None:
    assert DOCKERFILE.startswith("FROM python:3.12-slim-trixie\n")
    assert "--only-binary=:all: --require-hashes" in DOCKERFILE


def test_runtime_smoke_stays_out_of_the_image() -> None:
    assert SMOKE.is_file()
    assert "scripts" not in DOCKERFILE


def test_ci_runs_the_full_suite_on_arm64() -> None:
    assert "runs-on: ${{ matrix.runner }}" in CI
    assert 'runner: ubuntu-24.04-arm' in CI


def test_readme_states_supported_platforms() -> None:
    docker = README.split("### Docker", 1)[1].split("###", 1)[0]
    assert "`linux/amd64`" in docker
    assert "`linux/arm64`" in docker
    assert "64-bit" in docker
    assert "Raspberry Pi" in docker
