#!/bin/bash
# Download the four Phase 1 Q8_0 GGUFs and check the published LFS sha256.
# Total is about 13.84 GB, under the 15 GB model cap.
set -euo pipefail
source /root/codes/sealedbench/tools/env.sh
DEST="${SEALEDBENCH_CACHE}/models"
mkdir -p "${DEST}"
cd "${DEST}"

download() {
  local url="$1" dest="$2" expect="$3"
  if [[ -f "${dest}" ]]; then
    local got
    got=$(sha256sum "${dest}" | awk '{print $1}')
    if [[ "${got}" == "${expect}" ]]; then
      echo "ALREADY_OK ${dest}"
      return 0
    fi
  fi
  curl -fL --retry 5 --retry-delay 2 -A "sealedbench/0.0.1" -o "${dest}.partial" "${url}"
  mv "${dest}.partial" "${dest}"
  local got
  got=$(sha256sum "${dest}" | awk '{print $1}')
  if [[ "${got}" != "${expect}" ]]; then
    echo "SHA_FAIL ${dest} got ${got} expect ${expect}" >&2
    return 1
  fi
  echo "SHA_OK ${dest} ${got}"
}

download \
  "https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/resolve/main/qwen3-4b-instruct-2507-q8_0.gguf?download=true" \
  "qwen3-4b-instruct-2507-q8_0.gguf" \
  "ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1"

download \
  "https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q8_0.gguf?download=true" \
  "gemma-3-4b-it-Q8_0.gguf" \
  "97b06383df48336e7d2f9b56b6ce545e0fa476407a62c0bd081b53447a58e644"

download \
  "https://huggingface.co/ggml-org/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q8_0.gguf?download=true" \
  "Ministral-3-3B-Instruct-2512-Q8_0.gguf" \
  "70c6e5b77435062a46bfa3f0b9fa21744a10161ed23eabe9fdc47b3fb6711ad3"

download \
  "https://huggingface.co/tiiuae/Falcon3-1B-Instruct-GGUF/resolve/main/Falcon3-1B-Instruct-q8_0.gguf?download=true" \
  "Falcon3-1B-Instruct-q8_0.gguf" \
  "dda44709157103fc272ea3c44ae0deb7fbec5b2d82b313362680dec08e66f57a"

du -sh "${DEST}"
