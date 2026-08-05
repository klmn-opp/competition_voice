#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv. Run: bash scripts/setup_venv.sh"
  exit 1
fi

. .venv/bin/activate
python -m pip install -r requirements-sherpa.txt

echo "sherpa-onnx is ready in $(pwd)/.venv"
