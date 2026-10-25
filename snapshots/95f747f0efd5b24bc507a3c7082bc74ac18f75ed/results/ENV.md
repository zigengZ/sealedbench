# Toolchain

Recorded 2026-10-17. Binaries live under `/root/.cache/sealedbench`. Shells that run the scripts source `tools/env.sh`, which prepends that cache to `PATH` for the current process only.

| tool | version | notes |
| --- | --- | --- |
| Go | 1.27.2 linux-amd64 | SHA256 `ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5`, from `https://go.dev/dl/?mode=json` |
| Node.js | 22.23.3 | SHA256 `df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de`, from `https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt` |
| npm | 10.9.9 | bundled with that Node |
| tle | github.com/drand/tlock/cmd/tle@v1.2.0 | `go install`, binary `$GOPATH/bin/tle` |
| tlock-js | 0.9.0 | drand client is built in `tools/lib/tlock_client.mjs` |
| drand-client | 1.2.5 | transitive of tlock-js |
| @ardrive/turbo-sdk | 2.1.1 | |
| @dha-team/arbundles | 1.0.4 | direct dependency; receipt deep-hash candidate |
| arbundles | 0.11.2 | present; receipt check uses `@dha-team/arbundles` |
| arweave | 1.15.7 | JWK generation only |
| Python | 3.12.3 | stdlib only; see `requirements.txt` |
| OpenSSL | 3.0.13 | `openssl ts` |
| cmake | 3.28.3 | |
| gcc | 13.3.0 | |
| llama.cpp | v0.7.0 | commit `620d2225cc436ab0b001e3200e590e3b286ef9ab` |

Host cgroup `sealedbench-p1.scope`: `cpu.max` 600000/100000 (6 CPUs), `memory.max` 19327352832 (18 GiB). Builds use `-j 6`. One llama.cpp process at a time.

drand quicknet chain `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, period 3 s, genesis 1692803367, scheme `bls-unchained-g1-rfc9380`.
