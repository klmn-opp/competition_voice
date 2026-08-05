#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m compileall competition_voice
python3 scripts/self_check.py --config config.json
