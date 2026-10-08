#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "========================================"
echo " OrbitWatch — Project Setup"
echo "========================================"
echo
echo "Project: $PROJECT_ROOT"
echo "Python:  $PYTHON_BIN"
echo

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: Python 3 was not found."
    exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" --version 2>&1)"
echo "Detected: $PYTHON_VERSION"
echo

if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment..."
    "$PYTHON_BIN" -m venv .venv
else
    echo "Virtual environment already exists."
fi

echo
echo "Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo
echo "Upgrading pip..."
python -m pip install --upgrade pip

echo
echo "Installing project dependencies..."
python -m pip install -r requirements.txt

echo
echo "Creating runtime directories..."
mkdir -p \
    data/mission \
    data/recordings/events \
    data/recordings/iq \
    data/samples \
    data/satellites \
    data/telemetry \
    assets/demo \
    assets/screenshots

echo
echo "Running import/compile validation..."
python -m compileall -q src

echo
echo "========================================"
echo " Setup completed successfully"
echo "========================================"
echo
echo "Activate the environment with:"
echo "  source .venv/bin/activate"
echo
echo "Start Mission Control with:"
echo "  ./scripts/run.sh dashboard"
echo
echo "Run the development replay with:"
echo "  ./scripts/run.sh demo"
echo
echo "Run the test suite with:"
echo "  ./scripts/test.sh"
echo
