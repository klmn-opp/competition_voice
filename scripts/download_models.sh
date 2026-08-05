#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p models .cache

download_one() {
  local name="$1"
  local url="$2"
  local mirror_url="$3"
  local dirname="$4"
  local zip_path=".cache/${dirname}.zip"

  if [ -d "models/${dirname}" ]; then
    echo "[skip] ${name}: models/${dirname} already exists"
    return 0
  fi

  echo "[download] ${name}"
  echo "          ${mirror_url}"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --continue-at - --progress-bar -o "${zip_path}" "${mirror_url}" \
      || { echo "[fallback] ${url}"; curl -L --fail --continue-at - --progress-bar -o "${zip_path}" "${url}"; }
  elif command -v wget >/dev/null 2>&1; then
    wget -c -O "${zip_path}" "${mirror_url}" || wget -c -O "${zip_path}" "${url}"
  else
    echo "curl or wget is required"
    return 1
  fi

  echo "[extract] ${zip_path}"
  unzip -tq "${zip_path}" >/dev/null
  unzip -q "${zip_path}" -d models
  echo "[ready] models/${dirname}"
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/download_models.sh small-cn
  bash scripts/download_models.sh cn
  bash scripts/download_models.sh multi-cn
  bash scripts/download_models.sh all

Models:
  small-cn  vosk-model-small-cn-0.22         about 42 MB download
  cn        vosk-model-cn-0.22               about 1.3 GB download
  multi-cn  vosk-model-cn-kaldi-multicn-0.15 about 1.5 GB download
EOF
}

target="${1:-small-cn}"

case "${target}" in
  small-cn)
    download_one \
      "small-cn" \
      "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip" \
      "https://github.com/kercre123/vosk-models/raw/main/vosk-model-small-cn-0.22.zip" \
      "vosk-model-small-cn-0.22"
    ;;
  cn)
    download_one \
      "cn" \
      "https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip" \
      "https://huggingface.co/rhasspy/vosk-models/resolve/main/zh/vosk-model-cn-0.22.zip?download=true" \
      "vosk-model-cn-0.22"
    ;;
  multi-cn)
    download_one \
      "multi-cn" \
      "https://alphacephei.com/vosk/models/vosk-model-cn-kaldi-multicn-0.15.zip" \
      "https://huggingface.co/rhasspy/vosk-models/resolve/main/zh/vosk-model-cn-kaldi-multicn-0.15.zip?download=true" \
      "vosk-model-cn-kaldi-multicn-0.15"
    ;;
  all)
    "$0" small-cn
    "$0" cn
    "$0" multi-cn
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    echo
    echo "Unknown model: ${target}"
    exit 1
    ;;
esac
