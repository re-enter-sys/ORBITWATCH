#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "========================================"
echo " OrbitWatch — Linux Satellite Ground Station"
echo "========================================"
echo

if [[ "${1:-}" == "dashboard" ]]; then
    echo "Starting Mission Control dashboard..."
    echo
    python -m src.main dashboard
    exit $?
fi

if [[ "${1:-}" == "demo" ]]; then
    echo "Starting development replay..."
    echo
    python -m src.main demo
    exit $?
fi

if [[ "${1:-}" == "help" || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage:
  ./scripts/run.sh dashboard
  ./scripts/run.sh demo
  ./scripts/run.sh help

Commands:
  dashboard    Start the read-only Mission Control dashboard.
  demo         Run the controlled development/replay mission.
  help         Show this help message.

Examples:
  ./scripts/run.sh dashboard
  ./scripts/run.sh demo

Safety:
  The dashboard is read-only.
  RF transmission is disabled.
  The demo uses controlled replay/development data.
EOF
    exit 0
fi

cat <<'EOF'
Usage:
  ./scripts/run.sh dashboard
  ./scripts/run.sh demo
  ./scripts/run.sh help

Use './scripts/run.sh dashboard' to start Mission Control.
Use './scripts/run.sh demo' to run the controlled development replay.
EOF
exit 1
