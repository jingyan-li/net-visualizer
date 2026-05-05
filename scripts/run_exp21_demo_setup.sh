#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.conda/path-link-demo-env/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python environment at: $PYTHON_BIN" >&2
  exit 1
fi

cd "$PROJECT_ROOT"

"$PYTHON_BIN" scripts/prepare_exp21_demo_inputs.py
"$PYTHON_BIN" scripts/preprocess_network.py
"$PYTHON_BIN" scripts/preprocess_paths.py
"$PYTHON_BIN" scripts/write_path_coverage_audit.py

echo "exp21 demo data preparation complete."
