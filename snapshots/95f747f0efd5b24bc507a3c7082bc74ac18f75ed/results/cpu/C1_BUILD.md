# C1 — llama.cpp CPU build

| field | value |
| --- | --- |
| source | `https://github.com/ggml-org/llama.cpp` tag `v0.7.0` |
| commit | `620d2225cc436ab0b001e3200e590e3b286ef9ab` |
| binary | `/root/.cache/sealedbench/llama.cpp/build/bin/llama-completion` |
| version string | `0.7.0-dev (build 1, commit 620d222)` |
| compiler | GNU 13.3.0 |

`llama-completion` is the completion binary C3 runs. In v0.7.0, `tools/cli` (`llama-cli`) is added only when `LLAMA_BUILD_SERVER=ON`. This build leaves the server off.

CMake (also in `tools/c1_build.sh`):

```
-DCMAKE_BUILD_TYPE=Release
-DGGML_NATIVE=ON
-DGGML_AVX512=ON
-DGGML_AVX512_VBMI=ON
-DGGML_AVX512_VNNI=ON
-DGGML_AVX512_BF16=ON
-DGGML_CUDA=OFF
-DGGML_BLAS=OFF
-DGGML_METAL=OFF
-DGGML_VULKAN=OFF
-DGGML_HIP=OFF
-DGGML_MUSA=OFF
-DGGML_RPC=OFF
-DGGML_SYCL=OFF
-DGGML_OPENCL=OFF
-DGGML_OPENVINO=OFF
-DGGML_ZENDNN=OFF
-DGGML_WEBGPU=OFF
-DLLAMA_CURL=OFF
-DLLAMA_OPENSSL=OFF
-DLLAMA_BUILD_SERVER=OFF
-DLLAMA_BUILD_TESTS=OFF
-DLLAMA_BUILD_EXAMPLES=OFF
-DLLAMA_BUILD_UI=OFF
```

`ggml-cpu` compile line from `build/ggml/src/CMakeFiles/ggml-cpu.dir/flags.make`:

```
-O3 -DNDEBUG -std=gnu++17 -fPIC -march=native -fopenmp
```

There is no separate `-mavx512*` flag. `-march=native` on this Ryzen 7 7700 is what turns the AVX-512 paths on, together with the `GGML_AVX512*` options above. Defines include `GGML_USE_OPENMP` and `GGML_USE_CPU_REPACK`. CUDA and BLAS are off in `CMakeCache.txt`.

A later completion run printed:

```
CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | BMI2 = 1 | AVX512 = 1 | AVX512_VBMI = 1 | AVX512_VNNI = 1 | AVX512_BF16 = 1 | LLAMAFILE = 1 | OPENMP = 1 | REPACK = 1
```

Build command: `cmake --build build -j 6 --target llama-completion`. Exit 0.
