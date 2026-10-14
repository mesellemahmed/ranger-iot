#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "[ci] FAILED at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

cd /workspace

echo "[ci] Python"
python --version

echo "[ci] Ruff lint"
ruff check src tests

echo "[ci] Ruff format"
ruff format --check src tests

echo "[ci] MyPy"
mypy src

echo "[ci] Pytest + branch coverage"
pytest --cov=ranger_iot --cov-branch --cov-report=term-missing

echo "[ci] PASS"
