#!/bin/bash
# Source from a shell. Does not edit system PATH, profiles, or systemd.
# ROOT is this checkout. CACHE defaults to the user's cache directory.
_env_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SEALEDBENCH_ROOT="$(cd "${_env_dir}/.." && pwd)"
export SEALEDBENCH_CACHE="${SEALEDBENCH_CACHE:-${HOME}/.cache/sealedbench}"
export PATH="${SEALEDBENCH_CACHE}/go1.27.2/bin:${SEALEDBENCH_CACHE}/node/current/bin:${SEALEDBENCH_CACHE}/gopath/bin:${PATH}"
export GOPATH="${SEALEDBENCH_CACHE}/gopath"
export GOCACHE="${SEALEDBENCH_CACHE}/gocache"
export GOMODCACHE="${SEALEDBENCH_CACHE}/gomodcache"
export npm_config_cache="${SEALEDBENCH_CACHE}/npm-cache"
export TLE="${TLE:-${SEALEDBENCH_CACHE}/gopath/bin/tle}"
export LLAMA_COMPLETION="${LLAMA_COMPLETION:-${SEALEDBENCH_CACHE}/llama.cpp/build/bin/llama-completion}"
