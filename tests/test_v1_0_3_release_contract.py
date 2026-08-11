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
DEVELOPMENT_VERSION = "1.1.1"
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


def test_development_package_supersedes_v1_0_3_without_private_endpoint():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

    assert project["version"] == DEVELOPMENT_VERSION
    assert HELP_TEXT["version"] == DEVELOPMENT_VERSION
    assert DEPLOY_FIELD not in HELP_TEXT
    assert RAILWAY_SUFFIX not in str(HELP_TEXT)


def test_v1_1_0_documentation_preserves_v1_0_3_as_immutable_history():
    index = (ROOT / "docs/INDEX.md").read_text()
    open_questions = (ROOT / "docs/planning/OPEN_QUESTIONS.md").read_text()
    work_breakdown = (ROOT / "docs/planning/WORK_BREAKDOWN.md").read_text()
    readiness = (ROOT / "docs/planning/PUBLICATION_READINESS.md").read_text()

    assert "Authorized release candidate: `v1.1.0`" in index
    assert "`v1.1.0` is the authorized self-hosted-only candidate" in open_questions
    assert "v1.1.0 will supersede v1.0.3" in work_breakdown
    assert "v1.0.0–v1.0.3 remain immutable" in readiness


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
    assert "python scripts/build-agent-plugin.py --output-dir plugin-dist" in workflow
    assert "python scripts/verify-release-artifacts.py plugin-dist/*" in workflow
    assert "agent-plugin-preview" in workflow
    assert "SHA256SUMS" in workflow
    assert "body_path: docs/releases/${{ github.ref_name }}.md" in workflow
    assert workflow.count("persist-credentials: false") >= 3
    assert "COPY . ." not in (ROOT / "Dockerfile").read_text()
    assert "Inspect release candidate image boundary" in workflow
    assert "Publish inspected image" in workflow
    assert "(cd dist && sha256sum *) > SHA256SUMS" in workflow
    assert "(cd plugin-dist && sha256sum *) >> SHA256SUMS" in workflow
