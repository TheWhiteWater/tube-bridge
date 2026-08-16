"""Distribution and CI addendum for the public Pi package adapter."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_executes_the_real_pi_adapter_smoke() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "actions/setup-node@v4" in workflow
    assert 'node-version: "22.22.0"' in workflow
    assert "cache: npm" in workflow
    assert "npm ci --ignore-scripts --legacy-peer-deps" in workflow
    assert "npm run test:pi" in workflow


def test_node_install_artifacts_stay_out_of_the_public_tree() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "node_modules/" in ignore
    assert ".npm/" in ignore


def test_readme_explains_pi_install_and_manual_runtime_dependencies() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Pi package" in readme
    assert "pi install git:github.com/TheWhiteWater/tube-bridge" in readme
    assert "pi remove git:github.com/TheWhiteWater/tube-bridge" in readme
    assert "Python 3.12+" in readme
    assert "does not install Python or ffmpeg" in readme
    assert "tube-bridge-research" in readme
    assert "17 MCP tools" in readme
