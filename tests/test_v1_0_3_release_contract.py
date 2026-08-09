"""Frozen WI-00067 contract for the self-hosted-only v1.0.3 release."""

from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib
import zipfile

from tube_bridge.server import HELP_TEXT


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.3"
SCANNER = ROOT / "scripts/verify-release-artifacts.py"
DEPLOY_FIELD = "_".join(("deploy", "url"))
RAILWAY_SUFFIX = "." + ".".join(("railway", "app"))


def _wheel(path: Path, server_source: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("tube_bridge/server.py", server_source)


def _sdist(path: Path, server_source: str, readme: str = "self-hosted") -> None:
    source = path.parent / "server.py"
    source.write_text(server_source)
    readme_file = path.parent / "README.md"
    readme_file.write_text(readme)
    with tarfile.open(path, "w:gz") as archive:
        archive.add(source, arcname="tube_bridge-1.0.3/tube_bridge/server.py")
        archive.add(readme_file, arcname="tube_bridge-1.0.3/README.md")


def _scan(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), *(str(path) for path in paths)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_package_and_mcp_help_use_v1_0_3_without_private_endpoint():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

    assert project["version"] == EXPECTED_VERSION
    assert HELP_TEXT["version"] == EXPECTED_VERSION
    assert DEPLOY_FIELD not in HELP_TEXT
    assert RAILWAY_SUFFIX not in str(HELP_TEXT)


def test_current_release_documentation_names_v1_0_3():
    index = (ROOT / "docs/INDEX.md").read_text()
    open_questions = (ROOT / "docs/planning/OPEN_QUESTIONS.md").read_text()
    work_breakdown = (ROOT / "docs/planning/WORK_BREAKDOWN.md").read_text()
    readiness = (ROOT / "docs/planning/PUBLICATION_READINESS.md").read_text()

    assert "Current public release: `v1.0.3`." in index
    assert "`v1.0.3` is current" in open_questions
    assert "current release `v1.0.3`" in work_breakdown
    assert "current `v1.0.3`" in readiness


def test_release_artifact_scanner_accepts_clean_wheel_and_sdist(tmp_path: Path):
    wheel = tmp_path / "tube_bridge-1.0.3-py3-none-any.whl"
    sdist = tmp_path / "tube_bridge-1.0.3.tar.gz"
    clean_source = 'HELP_TEXT = {"version": "1.0.3", "description": "self-hosted"}'
    _wheel(wheel, clean_source)
    _sdist(sdist, clean_source)

    result = _scan(wheel, sdist)

    assert result.returncode == 0, result.stderr


def test_release_artifact_scanner_rejects_wheel_and_sdist_leaks(tmp_path: Path):
    clean_source = 'HELP_TEXT = {"version": "1.0.3", "description": "self-hosted"}'
    leaking_wheel = tmp_path / "leaking.whl"
    clean_sdist = tmp_path / "clean.tar.gz"
    _wheel(leaking_wheel, f'HELP_TEXT = {{"{DEPLOY_FIELD}": "https://private.example/mcp"}}')
    _sdist(clean_sdist, clean_source)
    wheel_result = _scan(leaking_wheel, clean_sdist)

    clean_wheel = tmp_path / "clean.whl"
    leaking_sdist = tmp_path / "leaking.tar.gz"
    _wheel(clean_wheel, clean_source)
    _sdist(leaking_sdist, clean_source, "https://personal" + RAILWAY_SUFFIX + "/mcp")
    sdist_result = _scan(clean_wheel, leaking_sdist)

    assert wheel_result.returncode != 0
    assert "unexpected private deployment metadata" in wheel_result.stderr
    assert sdist_result.returncode != 0
    assert "unexpected private deployment metadata" in sdist_result.stderr


def test_tag_release_workflow_scans_artifacts_and_publishes_authorized_surfaces():
    workflow = (ROOT / ".github/workflows/release.yml").read_text()

    assert "python scripts/verify-release-artifacts.py dist/*" in workflow
    assert "pypa/gh-action-pypi-publish@" in workflow
    assert "ghcr.io/thewhitewater/tube-bridge" in workflow
    assert "type=semver,pattern={{version}}" in workflow
    assert "type=semver,pattern={{major}}.{{minor}}" in workflow
    assert "type=raw,value=latest" in workflow
    assert "softprops/action-gh-release@" in workflow
