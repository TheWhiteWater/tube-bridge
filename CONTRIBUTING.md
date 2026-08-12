# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-release.txt
pip install --no-deps -e .
pip install pytest pytest-asyncio pytest-mock build twine
```

## Before opening a pull request

```bash
python -m pytest tests -q
python -m build
python -m twine check dist/*
python scripts/check-public-tree.py
```

Keep changes focused, add tests for behavior changes, and do not commit credentials, local data, generated artifacts, or private deployment configuration.
