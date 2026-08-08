"""Distribution integration tests — clean install, hash-locked release set, Docker consumption.

Pack C Second Remediation: exact clean install/twine/lock/Docker contracts.

DISTRIBUTION contract:
1. Temp source copy → python -m build --sdist --wheel --no-isolation
2. twine check both, rc=0
3. Create ordinary venv (NO system-site), outside cwd, not under checkout/source
4. pip install --require-hashes -r requirements-release.txt, rc=0
5. pip install --no-deps WHEEL, rc=0
6. VENV/bin/python -c 'import tube_bridge' cwd outside, rc=0
7. VENV/bin/tube-bridge --help cwd outside, exit EXACTLY 0,
   no RuntimeWarning/coroutine/import errors
8. Never python -m tube_bridge, never allow rc=1

LOCK contract:
9. Parse pyproject direct deps with packaging.Requirement and canonicalize_name
10. Parse requirements-release.txt logical blocks
11. Every install requirement block exact == and >=1 sha256 hash, no ranges/editables/URLs
12. Pinned canonical names contain canonical names of all direct deps
13. Execute clean pip --require-hashes to prove transitive completeness
14. Require mcp exactly 1.28.1

DOCKER contract:
15. Read Dockerfile lines; ordered indices:
    COPY requirements-release.txt
    RUN pip install with BOTH --require-hashes and -r requirements-release.txt
    Then project COPY/wheel
    Then pip install project/wheel with --no-deps
16. Assert strict order and mandatory commands

Distribution tests marked slow; lock/Docker tests are fast syntax checks.
"""

import hashlib
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


# ===========================================================================
# Helpers
# ===========================================================================

@pytest.fixture(scope="module")
def project_root():
    """Return the tube-bridge project root from env or fallback."""
    env_root = os.environ.get("BRAINOPS_PROJECT_PATH")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pyproject_path(project_root):
    return project_root / "pyproject.toml"


def _release_python():
    return os.environ.get("TUBE_BRIDGE_RELEASE_TOOLS_PYTHON", sys.executable)


def _parse_pyproject_direct_deps(pyproject_text):
    """Extract direct dependency names from pyproject.toml [project] dependencies.

    Uses packaging.Requirement to parse and canonicalize_name for comparison.
    """
    deps = []
    in_deps = False
    for line in pyproject_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("dependencies"):
            in_deps = True
            continue
        if in_deps:
            if stripped == "]":
                break
            # Extract the quoted string: "pkg>=version"
            match = re.search(r'"([^"]+)"', stripped)
            if match:
                dep_str = match.group(1)
                req = Requirement(dep_str)
                deps.append(canonicalize_name(req.name))
    return deps


def _parse_requirements_blocks(req_text):
    """Strictly parse pip-compile style exact, hash-locked blocks."""
    blocks, current = [], None
    for raw in req_text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        logical = stripped[:-1].rstrip() if stripped.endswith("\\") else stripped
        if logical.startswith("--hash="):
            match = re.fullmatch(r"--hash=sha256:([0-9a-fA-F]{64})", logical)
            if current is None or match is None:
                raise AssertionError(f"Malformed or orphan hash line: {stripped}")
            current["hashes"].append(match.group(1).lower())
            continue
        if current is not None:
            blocks.append(current)
        try:
            req = Requirement(logical)
            specs = list(req.specifier)
            valid = req.url is None and req.marker is None and len(specs) == 1 and specs[0].operator == "=="
        except Exception:
            req, specs, valid = None, [], False
        if not valid:
            current = {"name": logical, "canonical_name": "", "version": "",
                       "hashes": [], "line": stripped, "invalid": True}
        else:
            current = {"name": req.name, "canonical_name": canonicalize_name(req.name),
                       "version": specs[0].version, "hashes": [], "line": stripped}
    if current is not None:
        blocks.append(current)
    return blocks


# ===========================================================================
# Distribution: build + twine check
# ===========================================================================

@pytest.mark.slow
class TestBuildAndTwine:
    """Build wheel/sdist from temp copy and run twine check."""

    def test_build_produces_one_sdist_and_one_wheel(self, project_root):
        """python -m build --sdist --wheel --no-isolation produces exactly one
        .tar.gz and one .whl."""
        with tempfile.TemporaryDirectory(prefix="tb_build_") as tmp:
            tmp_path = Path(tmp)
            src_copy = tmp_path / "src"
            shutil.copytree(project_root, src_copy,
                            ignore=shutil.ignore_patterns(
                                ".git", "__pycache__", "*.pyc",
                                ".brainops", ".hermes", "dist", "build",
                                "*.egg-info", ".tube_bridge*", "node_modules"))

            result = subprocess.run(
                [_release_python(), "-m", "build", "--sdist", "--wheel",
                 "--no-isolation"],
                cwd=str(src_copy),
                capture_output=True, text=True, timeout=300,
            )

            assert result.returncode == 0, (
                f"Build failed (rc={result.returncode}):\n"
                f"STDOUT: {result.stdout[-2000:]}\n"
                f"STDERR: {result.stderr[-2000:]}"
            )

            dist_dir = src_copy / "dist"
            sdists = list(dist_dir.glob("*.tar.gz"))
            wheels = list(dist_dir.glob("*.whl"))

            assert len(sdists) == 1, (
                f"Expected exactly 1 sdist, found {len(sdists)}: {sdists}"
            )
            assert len(wheels) == 1, (
                f"Expected exactly 1 wheel, found {len(wheels)}: {wheels}"
            )

    def test_twine_check_passes(self, project_root):
        """twine check on sdist and wheel returns rc=0."""
        with tempfile.TemporaryDirectory(prefix="tb_twine_") as tmp:
            tmp_path = Path(tmp)
            src_copy = tmp_path / "src"
            shutil.copytree(project_root, src_copy,
                            ignore=shutil.ignore_patterns(
                                ".git", "__pycache__", "*.pyc",
                                ".brainops", ".hermes", "dist", "build",
                                "*.egg-info", ".tube_bridge*", "node_modules"))

            # Build
            subprocess.run(
                [_release_python(), "-m", "build", "--sdist", "--wheel",
                 "--no-isolation"],
                cwd=str(src_copy), capture_output=True, timeout=300,
                check=True,
            )

            dist_dir = src_copy / "dist"
            artifacts = list(dist_dir.glob("*"))
            result = subprocess.run(
                [_release_python(), "-m", "twine", "check"] +
                [str(a) for a in artifacts],
                capture_output=True, text=True, timeout=60,
            )

            assert result.returncode == 0, (
                f"twine check failed (rc={result.returncode}):\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )


# ===========================================================================
# Distribution: clean install
# ===========================================================================

@pytest.mark.slow
class TestCleanInstall:
    """Build and exercise the installed artifact in a genuinely isolated venv."""

    def test_clean_wheel_import_and_cli(self, project_root):
        with tempfile.TemporaryDirectory(prefix="tb_clean_") as tmp:
            tmp_path = Path(tmp)
            src_copy, outside = tmp_path / "src", tmp_path / "outside"
            outside.mkdir()
            shutil.copytree(project_root, src_copy, ignore=shutil.ignore_patterns(
                ".git", "__pycache__", "*.pyc", ".brainops", ".hermes",
                "dist", "build", "*.egg-info", ".tube_bridge*", "node_modules"))
            build = subprocess.run(
                [_release_python(), "-m", "build", "--sdist", "--wheel", "--no-isolation"],
                cwd=src_copy, capture_output=True, text=True, timeout=300)
            assert build.returncode == 0, build.stdout + build.stderr
            wheels = list((src_copy / "dist").glob("*.whl"))
            assert len(wheels) == 1
            req_file = src_copy / "requirements-release.txt"
            assert req_file.is_file(), "requirements-release.txt is required before clean install"

            venv_dir = tmp_path / "venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            py = venv_dir / "bin" / "python"
            deps = subprocess.run(
                [str(py), "-m", "pip", "install", "--require-hashes", "-r", str(req_file)],
                cwd=outside, capture_output=True, text=True, timeout=600)
            assert deps.returncode == 0, deps.stdout + deps.stderr
            install = subprocess.run(
                [str(py), "-m", "pip", "install", "--no-deps", str(wheels[0])],
                cwd=outside, capture_output=True, text=True, timeout=120)
            assert install.returncode == 0, install.stdout + install.stderr
            imported = subprocess.run([str(py), "-c", "import tube_bridge"], cwd=outside,
                                      capture_output=True, text=True, timeout=30)
            assert imported.returncode == 0, imported.stdout + imported.stderr
            cli = subprocess.run([str(venv_dir / "bin" / "tube-bridge"), "--help"],
                                 cwd=outside, capture_output=True, text=True, timeout=30)
            assert cli.returncode == 0, cli.stdout + cli.stderr
            forbidden = ("runtimewarning", "coroutine", "never awaited", "importerror", "modulenotfounderror")
            assert not any(term in cli.stderr.lower() for term in forbidden), cli.stderr

            # Prove the installed console script serves the real MCP protocol.
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            runtime_cache = tmp_path / "runtime-cache"
            env = {**os.environ, "TUBE_BRIDGE_AUTH_KEY": "installed-wheel-test",
                   "TUBE_BRIDGE_CACHE": str(runtime_cache)}
            proc = subprocess.Popen(
                [str(venv_dir / "bin" / "tube-bridge"), "--http", "--host", "127.0.0.1",
                 "--port", str(port)], cwd=outside, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                import urllib.request
                health = f"http://127.0.0.1:{port}/health"
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(health, timeout=1) as response:
                            if response.status == 200:
                                break
                    except Exception:
                        if proc.poll() is not None:
                            break
                        time.sleep(0.25)
                else:
                    pytest.fail("installed wheel HTTP server did not become healthy")
                smoke_copy = outside / "mcp_client_smoke.py"
                shutil.copy2(project_root / "tests" / "mcp_client_smoke.py", smoke_copy)
                smoke = subprocess.run(
                    [str(py), str(smoke_copy), "--url", f"http://127.0.0.1:{port}/mcp",
                     "--auth", "installed-wheel-test"], cwd=outside,
                    capture_output=True, text=True, timeout=60,
                )
                assert smoke.returncode == 0, smoke.stdout + smoke.stderr
                payload = __import__("json").loads(smoke.stdout)
                assert payload["ok"] is True and payload["tool_count"] == 16
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()



# ===========================================================================
# Lock file contract
# ===========================================================================

class TestLockContract:
    """Exact release lock contract verification."""

    @pytest.fixture(scope="class")
    def pyproject_text(self, project_root):
        path = project_root / "pyproject.toml"
        if not path.exists():
            pytest.skip("pyproject.toml not found")
        return path.read_text()

    @pytest.fixture(scope="class")
    def req_text(self, project_root):
        path = project_root / "requirements-release.txt"
        return path.read_text() if path.is_file() else ""

    def test_requirements_release_txt_exists(self, project_root):
        """requirements-release.txt must exist at project root."""
        path = project_root / "requirements-release.txt"
        assert path.exists(), (
            "requirements-release.txt is required but not found at "
            f"{path}"
        )

    def test_all_direct_deps_in_lock(self, pyproject_text, req_text):
        """Every direct pyproject dependency has a corresponding pinned entry
        in requirements-release.txt."""
        direct_names = set(_parse_pyproject_direct_deps(pyproject_text))
        blocks = _parse_requirements_blocks(req_text)
        pinned_names = {b["canonical_name"] for b in blocks
                        if not b.get("invalid")}

        missing = direct_names - pinned_names
        assert not missing, (
            f"Direct deps missing from requirements-release.txt: {missing}"
        )

    def test_every_block_exact_pin(self, req_text):
        """Every install requirement block is exact == (no ranges, editables, URLs)."""
        blocks = _parse_requirements_blocks(req_text)
        assert blocks, "requirements-release.txt has no pinned requirement blocks"
        invalid = [b for b in blocks if b.get("invalid")]
        assert not invalid, (
            f"Requirements with non-exact pins: "
            f"{[(b['line'], b.get('invalid', '')) for b in invalid]}"
        )

    def test_every_block_has_at_least_one_hash(self, req_text):
        """Every install requirement block has >=1 --hash=sha256."""
        blocks = _parse_requirements_blocks(req_text)
        assert blocks, "requirements-release.txt has no hash-locked requirement blocks"
        missing_hashes = [b["name"] for b in blocks if len(b["hashes"]) == 0]
        assert not missing_hashes, (
            f"Requirement blocks missing sha256 hashes: {missing_hashes}"
        )

    def test_mcp_exactly_1_28_1(self, req_text):
        """mcp must be pinned to exactly 1.28.1."""
        blocks = _parse_requirements_blocks(req_text)
        mcp_blocks = [b for b in blocks if b["canonical_name"] == "mcp"]
        assert len(mcp_blocks) >= 1, "mcp not found in requirements-release.txt"
        for b in mcp_blocks:
            assert b["version"] == "1.28.1", (
                f"mcp version is {b['version']}, must be exactly 1.28.1"
            )

    @pytest.mark.slow
    def test_pip_require_hashes_succeeds(self, project_root, req_text):
        """pip install --require-hashes -r requirements-release.txt succeeds
        in a clean venv (proves transitive completeness)."""
        req_path = project_root / "requirements-release.txt"
        if not req_path.exists():
            pytest.skip("requirements-release.txt not found")

        with tempfile.TemporaryDirectory(prefix="tb_hashcheck_") as tmp:
            tmp_path = Path(tmp)
            venv_dir = tmp_path / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True, capture_output=True, timeout=120,
            )
            venv_pip = str(venv_dir / "bin" / "pip")

            result = subprocess.run(
                [venv_pip, "install", "--require-hashes",
                 "-r", str(req_path)],
                capture_output=True, text=True, timeout=600,
            )

            assert result.returncode == 0, (
                f"pip --require-hashes failed (rc={result.returncode}):\n"
                f"STDERR: {result.stderr[-3000:]}\n"
                f"STDOUT: {result.stdout[-1000:]}"
            )


# ===========================================================================
# Docker contract
# ===========================================================================

class TestDockerContract:
    """Dockerfile must have correct ordered commands for reproducible builds."""

    @pytest.fixture(scope="class")
    def dockerfile_lines(self, project_root):
        path = project_root / "Dockerfile"
        if not path.exists():
            pytest.skip("Dockerfile not found")
        return path.read_text().split("\n")

    def test_copy_requirements_first(self, dockerfile_lines):
        """Dockerfile must COPY requirements-release.txt."""
        for i, line in enumerate(dockerfile_lines):
            stripped = line.strip()
            if stripped.startswith("COPY ") and "requirements-release.txt" in stripped:
                return  # found
        pytest.fail(
            "Dockerfile missing: COPY requirements-release.txt"
        )

    def test_pip_install_require_hashes(self, dockerfile_lines):
        """Dockerfile must have RUN pip install with BOTH --require-hashes
        and -r requirements-release.txt."""
        for i, line in enumerate(dockerfile_lines):
            stripped = line.strip()
            if stripped.startswith("RUN ") and "pip" in stripped:
                if "--require-hashes" in stripped and \
                   "-r" in stripped and \
                   "requirements-release.txt" in stripped:
                    return  # found
        pytest.fail(
            "Dockerfile missing: RUN pip install with --require-hashes "
            "and -r requirements-release.txt"
        )

    def test_pip_install_no_deps(self, dockerfile_lines):
        """Dockerfile must install this project or its wheel with --no-deps."""
        commands = [line.strip() for line in dockerfile_lines if line.strip().startswith("RUN ")]
        assert any(
            "pip install" in cmd and "--no-deps" in cmd
            and (re.search(r"pip install\s+.*--no-deps\s+\.?($|\s)", cmd) or ".whl" in cmd)
            for cmd in commands
        ), f"No project/wheel --no-deps install command: {commands}"

    def test_ordered_indices(self, dockerfile_lines):
        """Strict order: COPY requirements → pip hashes → project COPY →
        pip install --no-deps. Index order must be monotonic."""
        idx_copy_req = None
        idx_pip_hashes = None
        idx_project_copy = None
        idx_pip_nodeps = None

        for i, line in enumerate(dockerfile_lines):
            stripped = line.strip()

            if stripped.startswith("COPY ") and \
               "requirements-release.txt" in stripped:
                idx_copy_req = i
            elif stripped.startswith("RUN ") and "pip" in stripped and \
                 "--require-hashes" in stripped and \
                 "requirements-release.txt" in stripped:
                idx_pip_hashes = i
            elif stripped == "COPY . ." or (
                stripped.startswith("COPY ") and ".whl" in stripped
            ):
                if idx_project_copy is None:
                    idx_project_copy = i
            elif stripped.startswith("RUN ") and "pip install" in stripped and \
                 "--no-deps" in stripped and \
                 (re.search(r"pip install\s+.*--no-deps\s+\.?($|\s)", stripped) or ".whl" in stripped):
                idx_pip_nodeps = i

        assert idx_copy_req is not None, "COPY requirements-release.txt not found"
        assert idx_pip_hashes is not None, \
            "RUN pip --require-hashes -r requirements-release.txt not found"
        assert idx_project_copy is not None, "Project COPY not found"
        assert idx_pip_nodeps is not None, "RUN pip --no-deps not found"

        # Verify strict ordering
        assert idx_copy_req < idx_pip_hashes, (
            f"COPY requirements-release.txt (line {idx_copy_req}) must come "
            f"before pip --require-hashes (line {idx_pip_hashes})"
        )
        assert idx_pip_hashes < idx_project_copy, (
            f"pip --require-hashes (line {idx_pip_hashes}) must come "
            f"before project COPY (line {idx_project_copy})"
        )
        assert idx_project_copy < idx_pip_nodeps, (
            f"Project COPY (line {idx_project_copy}) must come "
            f"before pip --no-deps (line {idx_pip_nodeps})"
        )
