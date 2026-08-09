"""Frozen addendum: public MCP help must not distribute private infrastructure."""

import json
from pathlib import Path
import tomllib

from tube_bridge.server import HELP_TEXT


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_HOSTNAME = ".".join(("tube-bridge-production", "up", "railway", "app"))
DEPLOY_FIELD = "_".join(("deploy", "url"))


def test_help_has_no_private_deployment_endpoint():
    assert DEPLOY_FIELD not in HELP_TEXT
    assert PRIVATE_HOSTNAME not in json.dumps(HELP_TEXT)


def test_help_version_matches_package_metadata():
    package_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert HELP_TEXT["version"] == package_version
