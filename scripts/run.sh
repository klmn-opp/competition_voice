#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv. Run: bash scripts/setup_venv.sh"
  exit 1
fi

exec .venv/bin/python -m competition_voice.app --config config.json "$@"
