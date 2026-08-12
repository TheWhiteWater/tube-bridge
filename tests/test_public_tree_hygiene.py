"""Public source tree must stay free of local automation and operator material."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_tree_hygiene_check_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-public-tree.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
