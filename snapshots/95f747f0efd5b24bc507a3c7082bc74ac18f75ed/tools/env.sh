#!/bin/bash
# Source from a shell. Does not edit system PATH, profiles, or systemd.
export SEALEDBENCH_ROOT=/root/codes/sealedbench
export SEALEDBENCH_CACHE=/root/.cache/sealedbench
export PATH="${SEALEDBENCH_CACHE}/go1.27.2/bin:${SEALEDBENCH_CACHE}/node/current/bin:${SEALEDBENCH_CACHE}/gopath/bin:${PATH}"
export GOPATH="${SEALEDBENCH_CACHE}/gopath"
export GOCACHE="${SEALEDBENCH_CACHE}/gocache"
export GOMODCACHE="${SEALEDBENCH_CACHE}/gomodcache"
export npm_config_cache="${SEALEDBENCH_CACHE}/npm-cache"
export TLE="${SEALEDBENCH_CACHE}/gopath/bin/tle"
export LLAMA_COMPLETION="${SEALEDBENCH_CACHE}/llama.cpp/build/bin/llama-completion"
