#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p models/sherpa .cache

download() {
  local url="$1"
  local output="$2"

  if [ -f "${output}" ]; then
    echo "[skip] ${output} exists"
    return 0
  fi

  echo "[download] ${url}"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --progress-bar -o "${output}" "${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${output}" "${url}"
  else
    echo "curl or wget is required"
    exit 1
  fi
}

VAD_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
MODEL_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2"
MODEL_ARCHIVE=".cache/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2"
MODEL_DIR="models/sherpa/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"

download "${VAD_URL}" "models/sherpa/silero_vad.onnx"

if [ -d "${MODEL_DIR}" ]; then
  echo "[skip] ${MODEL_DIR} exists"
else
  download "${MODEL_URL}" "${MODEL_ARCHIVE}"
  echo "[extract] ${MODEL_ARCHIVE}"
  tar -xjf "${MODEL_ARCHIVE}" -C models/sherpa
  echo "[ready] ${MODEL_DIR}"
fi
