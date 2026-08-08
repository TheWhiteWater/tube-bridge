"""CLI and release configuration contract tests.

Defect-driving RED tests for:
- Script target is importable synchronous callable inside tube_bridge
  (current: server:main is async and in root module)
- Subprocess pip wheel produces exactly one wheel with required members
- Build-system with real wheel packaging declaration (setuptools/hatch equivalent)
- pyproject.toml has project.readme and project.license metadata
- MCP dependency uses packaging.requirements.Requirement/SpecifierSet semantics:
  1.28.1 must be allowed; 1.28.0 and 1.29.0 must be rejected

The wheel test replaces the prior config-shape package-discovery test.
It builds a real wheel via subprocess pip wheel and inspects the zip.
Allowed to RED because cli.py entrypoint is currently missing.

SIDE-EFFECT-FREE: _build_wheel copies the project source tree to a
temporary directory and runs pip wheel from there.  The project root
is left unchanged — no build/, dist/, egg-info, or other artifacts
remain after the test completes.  The finally block asserts that no
artifacts leaked to PROJECT_ROOT; it never deletes project paths.

CLEANUP GUARANTEE: test_built_wheel_has_required_package_members captures
pre-existing artifact paths and wraps all wheel/assertion logic in
try/finally.  The finally block asserts exact state unchanged — no new
build/, dist/, or *.egg-info appeared at PROJECT_ROOT.  It never calls
shutil.rmtree or any other destructive operation on project paths.
"""

import configparser
import hashlib
import importlib
import inspect
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# Add project root for tomllib import of pyproject
PROJECT_ROOT = Path(os.environ.get(
    "BRAINOPS_PROJECT_PATH",
    Path(__file__).resolve().parent.parent,
))


def _load_pyproject():
    """Load pyproject.toml from the project root."""
    import tomllib

    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Script entrypoint contract — DEFECT-DRIVING RED
# ---------------------------------------------------------------------------

def test_script_target_is_importable():
    """RED: pyproject.toml [project.scripts] tube-bridge = 'server:main'
    must resolve to a callable inside the tube_bridge package.

    Current defect: server:main is async, lives in root server.py,
    and requires the project checkout directory on sys.path.
    """
    data = _load_pyproject()
    scripts = data.get("project", {}).get("scripts", {})
    entry = scripts.get("tube-bridge")
    assert entry is not None, "tube-bridge script entrypoint not found"

    module_name, _, callable_name = entry.partition(":")

    # RED assertion: the current value "server:main" is NOT inside tube_bridge
    assert module_name.startswith("tube_bridge"), (
        f"Script entrypoint '{entry}' references '{module_name}' which is "
        f"outside the tube_bridge package. Expected a module inside "
        f"tube_bridge (e.g. tube_bridge.cli:main).")


def test_script_callable_is_synchronous():
    """RED: The CLI entrypoint callable must be synchronous (asyncio.run
    internally). Current 'server:main' is async.
    """
    data = _load_pyproject()
    scripts = data.get("project", {}).get("scripts", {})
    entry = scripts.get("tube-bridge")
    if not entry:
        pytest.skip("No tube-bridge script entrypoint found")

    module_name, _, callable_name = entry.partition(":")

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        pytest.fail(
            f"Cannot import '{module_name}': {e}. "
            f"The entrypoint must reference an importable module inside "
            f"tube_bridge.")

    func = getattr(mod, callable_name, None)
    assert func is not None, f"Callable '{callable_name}' not found in {module_name}"

    # RED: server:main is async
    assert not inspect.iscoroutinefunction(func), (
        f"Script callable '{entry}' is a coroutine function. "
        f"CLI entrypoints must be synchronous (use asyncio.run() internally).")

    assert callable(func), f"'{entry}' is not callable"


# ---------------------------------------------------------------------------
# Wheel build contract — BEHAVIOR TEST (replaces config-shape discovery)
# ---------------------------------------------------------------------------

def _build_wheel(tmp_path):
    """Run pip wheel from a temp copy of the project source and return
    the path to the single output .whl file.

    Copies the project source tree to a temporary directory and runs
    pip wheel there.  Wheel output goes to tmp_path.  The project root
    is never mutated — no build/, dist/, or egg-info artifacts.

    Uses TemporaryDirectory as parent; source_copy is a nonexistent
    subpath inside it so copytree with dirs_exist_ok=False does not
    raise FileExistsError (the mkdtemp-then-copytree bug from Pack B).
    """
    with tempfile.TemporaryDirectory(prefix="tb_build_") as parent:
        source_copy = Path(parent) / "source"
        # source_copy does NOT exist — safe for copytree(dir=source_copy,
        # dirs_exist_ok=False).  This is the critical fix: never pass an
        # already-existing mkdtemp directory to copytree.
        ignore_patterns = shutil.ignore_patterns(
            ".git", "__pycache__", "*.pyc", "*.pyo",
            "build", "dist", "*.egg-info",
            ".brainops", ".hermes", ".venv", "venv", ".env",
            "node_modules",
        )
        shutil.copytree(PROJECT_ROOT, source_copy, ignore=ignore_patterns,
                        symlinks=False, dirs_exist_ok=False)

        cmd = [
            sys.executable, "-m", "pip", "wheel",
            "--no-deps", "--no-build-isolation",
            "-w", str(tmp_path),
            str(source_copy),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=120, cwd=str(source_copy))
        if result.returncode != 0:
            pytest.fail(
                f"pip wheel failed (exit {result.returncode}):\n"
                f"STDOUT: {result.stdout[:1000]}\n"
                f"STDERR: {result.stderr[:1000]}")

        wheels = sorted(tmp_path.glob("*.whl"))
        if len(wheels) == 0:
            pytest.fail("pip wheel produced no .whl files")
        if len(wheels) > 1:
            pytest.fail(f"Expected exactly 1 wheel, got {len(wheels)}: "
                        f"{[w.name for w in wheels]}")
        return wheels[0]


@pytest.mark.slow
def test_built_wheel_has_required_package_members():
    """Build the wheel via subprocess pip wheel and inspect zip members.

    Required members:
    - tube_bridge/__init__.py
    - tube_bridge/server.py
    - tube_bridge/tools.py
    - tube_bridge/transport.py
    - tube_bridge/cache.py
    - tube_bridge/corpus.py
    - tube_bridge/cli.py (RED: currently missing)
    - tube_bridge/youtube/ subpackage

    Entrypoint contract (exact, no substring/contains):
    Locate exactly one member matching *.dist-info/entry_points.txt by
    filename (NOT by explicit .dist-info/ directory entries — those are
    not required zip members). Parse with configparser; require
    [console_scripts] has exact key tube-bridge and exact normalized
    value tube_bridge.cli:main.

    This test uses pip wheel subprocess, not config-shape parsing.
    RED: cli.py is missing; entrypoint is server:main (not in package).

    SIDE-EFFECT-FREE GUARANTEE: Snapshot pre-existing artifact paths at
    PROJECT_ROOT before execution.  Build from temp copied source.  In
    finally, assert exact state unchanged — no new build/, dist/, or
    *.egg-info appeared.  Never deletes project paths.
    """
    def artifact_snapshot():
        """Content snapshot of every project-root build artifact.

        Comparing names alone would miss deletion or replacement of a
        pre-existing file. Directories and SHA-256 file contents are recorded;
        timestamps are intentionally ignored because reading must not matter.
        """
        roots = [PROJECT_ROOT / "build", PROJECT_ROOT / "dist"]
        roots.extend(sorted(PROJECT_ROOT.glob("*.egg-info")))
        snapshot = {}
        for root in roots:
            if not root.exists():
                continue
            paths = [root]
            if root.is_dir():
                paths.extend(sorted(root.rglob("*")))
            for path in paths:
                rel = path.relative_to(PROJECT_ROOT).as_posix()
                if path.is_dir():
                    snapshot[rel] = ("dir",)
                elif path.is_file():
                    snapshot[rel] = (
                        "file",
                        path.stat().st_size,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                else:
                    snapshot[rel] = ("other",)
        return snapshot

    pre_artifacts = artifact_snapshot()

    try:
        with tempfile.TemporaryDirectory(prefix="tb_wheel_test_") as tmp:
            whl_path = _build_wheel(Path(tmp))

            with zipfile.ZipFile(whl_path, "r") as zf:
                names = set(zf.namelist())

                required = [
                    "tube_bridge/__init__.py",
                    "tube_bridge/server.py",
                    "tube_bridge/tools.py",
                    "tube_bridge/transport.py",
                    "tube_bridge/cache.py",
                    "tube_bridge/corpus.py",
                    "tube_bridge/cli.py",
                ]

                for member in required:
                    assert member in names, (
                        f"Wheel missing required package member: {member}\n"
                        f"Wheel members (first 60): {sorted(names)[:60]}")

                # youtube package must be present (at least __init__.py)
                youtube_members = [n for n in names
                                   if n.startswith("tube_bridge/youtube/")]
                assert len(youtube_members) > 0, (
                    "Wheel missing tube_bridge/youtube/ subpackage")

                # --- entry_points.txt: exact filename match, configparser parse ---
                # Do NOT require explicit .dist-info/ directory entries — they are
                # not guaranteed zip members. Match by filename pattern instead.
                ep_candidates = [
                    n for n in names
                    if n.endswith("/entry_points.txt") and ".dist-info" in n
                ]
                assert len(ep_candidates) == 1, (
                    f"Expected exactly 1 entry_points.txt in wheel, "
                    f"got {len(ep_candidates)}: {ep_candidates}")

                ep_path = ep_candidates[0]
                content = zf.read(ep_path).decode("utf-8")

                parser = configparser.ConfigParser()
                parser.read_file(io.StringIO(content))

                assert parser.has_section("console_scripts"), (
                    f"entry_points.txt missing [console_scripts] section:\n{content}")
                assert parser.has_option("console_scripts", "tube-bridge"), (
                    f"entry_points.txt [console_scripts] missing tube-bridge key:\n{content}")

                actual = parser.get("console_scripts", "tube-bridge")
                # configparser strips whitespace; normalize again for belt-and-suspenders
                normalized = " ".join(actual.split())
                assert normalized == "tube_bridge.cli:main", (
                    f"entry_points.txt tube-bridge = '{actual}' "
                    f"(normalized: '{normalized}'), "
                    f"expected 'tube_bridge.cli:main'")

    finally:
        # Exact, non-destructive before/after comparison. This catches creation,
        # deletion, replacement, and content mutation while preserving anything
        # that existed before the test.
        post_artifacts = artifact_snapshot()
        assert post_artifacts == pre_artifacts, (
            "Project-root build artifacts changed during temp-copy wheel test. "
            f"Before: {pre_artifacts}; after: {post_artifacts}"
        )


# ---------------------------------------------------------------------------
# Build system and wheel packaging declaration
# ---------------------------------------------------------------------------

def test_build_backend_is_wheel_capable():
    """pyproject.toml must have [build-system] with a backend that supports
    wheel packaging (setuptools, hatchling, flit, pdm, poetry).

    RED: current pyproject.toml has no [build-system] at all.
    """
    data = _load_pyproject()
    build = data.get("build-system", {})
    assert build, (
        "[build-system] table is missing — pyproject.toml needs a build "
        "backend declaration (e.g. setuptools, hatchling)")

    backend = build.get("build-backend", "")
    assert backend, "build-system.build-backend is missing"

    # Recognised wheel-capable backends
    known_backends = (
        "setuptools", "hatchling", "flit", "pdm", "poetry",
        "maturin", "mesonpy", "scikit",
    )
    assert any(k in backend.lower() for k in known_backends), (
        f"Unknown build-backend '{backend}'; expected one of {known_backends}")

    assert "requires" in build, "build-system.requires missing"


# ---------------------------------------------------------------------------
# README and license: non-empty meaningful declarations required.
# Existing root files alone do not satisfy metadata.
# ---------------------------------------------------------------------------

def test_pyproject_readme_is_meaningful():
    """RED: project.readme must name README.md (as a string or table file),
    not just be present/truthy.

    Accepts:
    - readme = "README.md"  (PEP 621 string shorthand)
    - readme = {file = "README.md"}  (PEP 621 table)

    Rejects:
    - readme missing
    - readme = "" (empty string)
    - readme = {} (empty table — file field missing)
    - readme = {file = ""} (empty file field)
    """
    data = _load_pyproject()
    proj = data.get("project", {})
    readme = proj.get("readme")

    assert readme is not None, (
        "project.readme is missing from pyproject.toml — must declare a "
        "readme file (e.g. readme = 'README.md')")

    if isinstance(readme, str):
        assert readme.strip(), (
            "project.readme is an empty string — must name a file, "
            "e.g. readme = 'README.md'")
        assert readme.strip() == "README.md", (
            f"project.readme is '{readme}' but must be 'README.md'. "
            f"The project root contains README.md; pyproject must "
            f"reference it by that exact name.")

    elif isinstance(readme, dict):
        assert readme, (
            "project.readme is an empty table — must have at least "
            "a 'file' key, e.g. readme = {file = 'README.md'}")
        readme_file = readme.get("file", "")
        assert isinstance(readme_file, str) and readme_file.strip(), (
            f"project.readme.file is missing or empty (got: {readme_file!r})")
        assert readme_file.strip() == "README.md", (
            f"project.readme.file is '{readme_file}' but must be "
            f"'README.md'")
    else:
        pytest.fail(
            f"project.readme is {type(readme).__name__}, expected str or "
            f"table")


def test_pyproject_license_is_meaningful():
    """RED: project.license must name LICENSE or declare MIT text/expression,
    not just be present/truthy.

    Accepts:
    - license = {file = "LICENSE"}
    - license = {text = "MIT"}  or any MIT-containing text
    - license = "MIT" (PEP 639 expression)
    - license = "MIT License"

    Rejects:
    - license missing
    - license = "" (empty string)
    - license = {} (empty table — no file/text)
    - license = {file = ""} (empty file field)
    """
    data = _load_pyproject()
    proj = data.get("project", {})
    license_val = proj.get("license")

    # Also check classifiers as a valid alternative
    has_mit_classifier = any(
        "MIT" in c and "License" in c
        for c in proj.get("classifiers", [])
    )

    assert license_val is not None or has_mit_classifier, (
        "project.license is missing from pyproject.toml and no MIT License "
        "classifier found. Must declare license metadata: "
        "license = 'MIT', license = {file = 'LICENSE'}, "
        "or license = {text = 'MIT'}")

    if license_val is not None:
        if isinstance(license_val, str):
            assert license_val.strip(), (
                "project.license is an empty string — must contain a valid "
                "license expression or text")
            assert "mit" in license_val.lower(), (
                f"project.license is '{license_val}' but must reference MIT "
                f"(e.g. 'MIT', 'MIT License')")

        elif isinstance(license_val, dict):
            assert license_val, (
                "project.license is an empty table — must have a 'file' or "
                "'text' key")
            lic_file = license_val.get("file", "")
            lic_text = license_val.get("text", "")
            has_file = isinstance(lic_file, str) and lic_file.strip()
            has_text = isinstance(lic_text, str) and lic_text.strip()

            if has_file:
                assert "LICENSE" in lic_file, (
                    f"project.license.file is '{lic_file}' but must reference "
                    f"LICENSE")
            elif has_text:
                assert "mit" in lic_text.lower(), (
                    f"project.license.text is '{lic_text}' but must mention "
                    f"MIT")
            else:
                pytest.fail(
                    "project.license table has no non-empty 'file' or 'text' "
                    "key — must reference LICENSE or declare MIT")
        else:
            pytest.fail(
                f"project.license is {type(license_val).__name__}, expected "
                f"str or table")


# ---------------------------------------------------------------------------
# MCP dependency range — packaging.requirements.Requirement/SpecifierSet
# ---------------------------------------------------------------------------

def test_mcp_dependency_parses_as_requirement():
    """The mcp dependency string must parse as a valid Requirement."""
    from packaging.requirements import Requirement

    deps = _load_pyproject().get("project", {}).get("dependencies", [])
    mcp_dep = None
    for dep in deps:
        if dep.startswith("mcp"):
            mcp_dep = dep
            break

    assert mcp_dep is not None, "mcp dependency not found in pyproject.toml"

    req = Requirement(mcp_dep)
    assert req.name == "mcp", f"Parsed name '{req.name}' != 'mcp'"


def test_mcp_specifier_allows_1_28_1():
    """1.28.1 MUST be allowed by the MCP version specifier."""
    from packaging.requirements import Requirement

    deps = _load_pyproject().get("project", {}).get("dependencies", [])
    mcp_dep = next(d for d in deps if d.startswith("mcp"))

    req = Requirement(mcp_dep)
    spec = req.specifier
    assert spec.contains("1.28.1", prereleases=True), (
        f"MCP specifier '{spec}' does not allow 1.28.1. "
        f"The code imports StreamableHTTPSessionManager (1.28.1+). "
        f"Lower bound must be >=1.28.1.")


def test_mcp_specifier_rejects_1_28_0():
    """1.28.0 MUST be rejected — StreamableHTTPSessionManager is not present."""
    from packaging.requirements import Requirement

    deps = _load_pyproject().get("project", {}).get("dependencies", [])
    mcp_dep = next(d for d in deps if d.startswith("mcp"))

    req = Requirement(mcp_dep)
    spec = req.specifier
    assert not spec.contains("1.28.0"), (
        f"MCP specifier '{spec}' incorrectly allows 1.28.0. "
        f"StreamableHTTPSessionManager requires 1.28.1+.")


def test_mcp_specifier_rejects_1_29_0():
    """1.29.0 MUST be rejected — silent upgrade to 1.29+ is not tested."""
    from packaging.requirements import Requirement

    deps = _load_pyproject().get("project", {}).get("dependencies", [])
    mcp_dep = next(d for d in deps if d.startswith("mcp"))

    req = Requirement(mcp_dep)
    spec = req.specifier
    assert not spec.contains("1.29.0"), (
        f"MCP specifier '{spec}' incorrectly allows 1.29.0. "
        f"Silent upgrade to 1.29+ must be blocked (<1.29).")


# ---------------------------------------------------------------------------
# Required publication metadata
# ---------------------------------------------------------------------------

def test_pyproject_has_required_metadata():
    """pyproject.toml must have version, description, requires-python."""
    data = _load_pyproject()
    proj = data.get("project", {})
    assert proj.get("version"), "project.version missing"
    assert proj.get("description"), "project.description missing"
    assert proj.get("requires-python"), "project.requires-python missing"


def test_pyproject_description_tool_count():
    """pyproject.toml description must not claim 10 or 11 tools.

    This is a characterization/RED test: if pyproject claims a stale count,
    it fails. Correct claim (16) or no claim both pass.
    """
    data = _load_pyproject()
    desc = data.get("project", {}).get("description", "")
    for bad_claim in ["10 tools", "11 tools"]:
        assert bad_claim not in desc, (
            f"pyproject.toml description has stale tool count: '{desc[:80]}...'")
