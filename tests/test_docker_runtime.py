"""Docker release-candidate runtime contract: health, auth, initialize, tools/list."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.slow
def test_docker_image_serves_authenticated_mcp():
    """Build the actual image and prove authenticated MCP initialize/tools-list=16."""
    assert (PROJECT_ROOT / "requirements-release.txt").is_file(), (
        "requirements-release.txt must exist before Docker release verification"
    )
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    assert "--require-hashes" in dockerfile and "requirements-release.txt" in dockerfile
    assert "--no-deps" in dockerfile

    tag = f"tube-bridge-rc-test:{uuid.uuid4().hex[:12]}"
    container = None
    port = _free_port()
    auth = "docker-mcp-test"
    try:
        build = subprocess.run(
            ["docker", "build", "-t", tag, "."], cwd=PROJECT_ROOT,
            capture_output=True, text=True, timeout=1200,
        )
        assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-4000:]
        run = subprocess.run(
            ["docker", "run", "--rm", "-d", "-p", f"127.0.0.1:{port}:8080",
             "-e", f"TUBE_BRIDGE_AUTH_KEY={auth}",
             "-e", "TUBE_BRIDGE_CACHE=/tmp/tube-bridge-test", tag],
            capture_output=True, text=True, timeout=60,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        container = run.stdout.strip()

        health = f"http://127.0.0.1:{port}/health"
        for _ in range(120):
            try:
                with urllib.request.urlopen(health, timeout=2) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.fail("Docker container did not become healthy")

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(request, timeout=5)
        assert denied.value.code == 401

        smoke = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tests" / "mcp_client_smoke.py"),
             "--url", f"http://127.0.0.1:{port}/mcp", "--auth", auth],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=90,
        )
        assert smoke.returncode == 0, smoke.stdout + smoke.stderr
        payload = json.loads(smoke.stdout)
        assert payload["ok"] is True
        assert payload["tool_count"] == 16
        assert len(payload["tool_names"]) == 16
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30)
        subprocess.run(["docker", "image", "rm", "-f", tag], capture_output=True, timeout=60)
