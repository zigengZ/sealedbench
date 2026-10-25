#!/bin/bash
# CPU-only llama.cpp build. Native AVX-512, no CUDA and no BLAS.
# Re-runnable. Uses at most 6 compile jobs to match the 6-CPU cgroup quota.
set -euo pipefail
source /root/codes/sealedbench/tools/env.sh
SRC="${SEALEDBENCH_CACHE}/llama.cpp"
if [[ ! -d "${SRC}/.git" ]]; then
  git clone --depth 1 --branch v0.7.0 https://github.com/ggml-org/llama.cpp.git "${SRC}"
fi
cd "${SRC}"
echo "commit $(git rev-parse HEAD)"
echo "tag $(git describe --tags --exact-match HEAD || true)"
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_AVX512=ON \
  -DGGML_AVX512_VBMI=ON \
  -DGGML_AVX512_VNNI=ON \
  -DGGML_AVX512_BF16=ON \
  -DGGML_CUDA=OFF \
  -DGGML_BLAS=OFF \
  -DGGML_METAL=OFF \
  -DGGML_VULKAN=OFF \
  -DGGML_HIP=OFF \
  -DGGML_MUSA=OFF \
  -DGGML_RPC=OFF \
  -DGGML_SYCL=OFF \
  -DGGML_OPENCL=OFF \
  -DGGML_OPENVINO=OFF \
  -DGGML_ZENDNN=OFF \
  -DGGML_WEBGPU=OFF \
  -DLLAMA_CURL=OFF \
  -DLLAMA_OPENSSL=OFF \
  -DLLAMA_BUILD_SERVER=OFF \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF \
  -DLLAMA_BUILD_UI=OFF
# v0.7.0 builds tools/cli (llama-cli) only when LLAMA_BUILD_SERVER=ON.
# The classic completion binary is llama-completion, which is what C3 runs.
cmake --build build -j 6 --target llama-completion
ls -lh build/bin/llama-completion
