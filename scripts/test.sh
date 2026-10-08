#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "========================================"
echo " OrbitWatch — Test Suite"
echo "========================================"
echo

if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "Python:"
python --version

echo
echo "Running compilation check..."
python -m compileall -q src

echo "Compilation: PASS"

echo
echo "Running pytest..."
pytest -q

echo
echo "========================================"
echo " Tests completed successfully"
echo "========================================"
