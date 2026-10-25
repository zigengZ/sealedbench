# Inclusion

Poller started 2026-10-17T15:09:56.658Z. Updated 2026-10-17T20:06:51.609Z.

L1 latency is block timestamp minus the Turbo receipt timestamp. It is historical, including the Phase 1 probes.
Gateway times for items that already existed when the poller started are first observations, not first availability.
Nearest-rank percentiles. arweave.net is requested at most once every 10 minutes.

Samples with a block timestamp: 24.

| stat | seconds |
| --- | --- |
| min | 510.9 |
| p50 | 514.6 |
| p90 | 922.2 |
| p95 | 922.6 |
| max | 923.2 |

| item | receipt UTC | bundle | L1 height | block UTC | latency s | L1 source | payload | ar-io | zigza | turbo | arweave.net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| b1/generator-ciphertext | 2026-10-17T15:05:37Z | pzzVUc5WUQHkZMWHu3D12AseYrj6ZSwH1nx9lKurvxk | 2023266 | 2026-10-17T15:21:00Z | 922.6 | https://ar-io.dev | match | yes 2026-10-17T15:12:27.481Z | yes 2026-10-17T15:12:27.716Z | yes 2026-10-17T15:12:28.736Z | no HTTP 429 |
| b1/manifest | 2026-10-17T15:05:36Z | pzzVUc5WUQHkZMWHu3D12AseYrj6ZSwH1nx9lKurvxk | 2023266 | 2026-10-17T15:21:00Z | 923.2 | https://ar-io.dev | match | yes 2026-10-17T15:12:24.090Z | yes 2026-10-17T15:12:24.339Z | yes 2026-10-17T15:12:25.370Z | no HTTP 429 |
| cap/generator-ciphertext | 2026-10-17T15:05:38Z | pzzVUc5WUQHkZMWHu3D12AseYrj6ZSwH1nx9lKurvxk | 2023266 | 2026-10-17T15:21:00Z | 921.9 | https://ar-io.dev | match | yes 2026-10-17T15:12:34.352Z | yes 2026-10-17T15:12:35.155Z | yes 2026-10-17T15:12:36.198Z | no HTTP 429 |
| cap/manifest | 2026-10-17T15:05:37Z | pzzVUc5WUQHkZMWHu3D12AseYrj6ZSwH1nx9lKurvxk | 2023266 | 2026-10-17T15:21:00Z | 922.2 | https://ar-io.dev | match | yes 2026-10-17T15:12:30.854Z | yes 2026-10-17T15:12:31.087Z | yes 2026-10-17T15:12:32.107Z | no HTTP 429 |
| probe-00 | 2026-10-17T09:12:54Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 517.5 | https://arweave.net | match | yes 2026-10-17T15:10:03.669Z | yes 2026-10-17T15:10:03.919Z | yes 2026-10-17T15:10:05.240Z | no HTTP 429 |
| probe-01 | 2026-10-17T09:12:56Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 516.0 | https://ar-io.dev | match | yes 2026-10-17T15:10:11.189Z | yes 2026-10-17T15:10:11.441Z | yes 2026-10-17T15:10:12.607Z | no HTTP 429 |
| probe-02 | 2026-10-17T09:12:56Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 515.8 | https://ar-io.dev | match | yes 2026-10-17T15:10:18.816Z | yes 2026-10-17T15:10:19.068Z | yes 2026-10-17T15:10:20.215Z | no HTTP 429 |
| probe-03 | 2026-10-17T09:12:56Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 515.6 | https://ar-io.dev | match | yes 2026-10-17T15:10:25.280Z | yes 2026-10-17T15:10:25.528Z | yes 2026-10-17T15:10:26.847Z | no HTTP 429 |
| probe-04 | 2026-10-17T09:12:56Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 515.4 | https://ar-io.dev | match | yes 2026-10-17T15:10:32.579Z | yes 2026-10-17T15:10:32.827Z | yes 2026-10-17T15:10:33.980Z | no HTTP 429 |
| probe-05 | 2026-10-17T09:12:56Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 515.2 | https://ar-io.dev | match | yes 2026-10-17T15:10:40.143Z | yes 2026-10-17T15:10:40.376Z | yes 2026-10-17T15:10:41.589Z | no HTTP 429 |
| probe-06 | 2026-10-17T09:12:57Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 515.0 | https://ar-io.dev | match | yes 2026-10-17T15:10:48.070Z | yes 2026-10-17T15:10:48.321Z | yes 2026-10-17T15:10:49.486Z | no HTTP 429 |
| probe-07 | 2026-10-17T09:12:57Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 514.8 | https://ar-io.dev | match | yes 2026-10-17T15:10:54.647Z | yes 2026-10-17T15:10:54.868Z | yes 2026-10-17T15:10:56.038Z | no HTTP 429 |
| probe-08 | 2026-10-17T09:12:57Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 514.6 | https://ar-io.dev | match | yes 2026-10-17T15:11:01.979Z | yes 2026-10-17T15:11:02.230Z | yes 2026-10-17T15:11:03.393Z | no HTTP 429 |
| probe-09 | 2026-10-17T09:12:57Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 514.4 | https://ar-io.dev | match | yes 2026-10-17T15:11:09.644Z | yes 2026-10-17T15:11:09.879Z | yes 2026-10-17T15:11:11.164Z | no HTTP 429 |
| probe-10 | 2026-10-17T09:12:57Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 514.2 | https://ar-io.dev | match | yes 2026-10-17T15:11:16.700Z | yes 2026-10-17T15:11:16.932Z | yes 2026-10-17T15:11:18.101Z | no HTTP 429 |
| probe-11 | 2026-10-17T09:12:57Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 514.0 | https://ar-io.dev | match | yes 2026-10-17T15:11:24.287Z | yes 2026-10-17T15:11:24.523Z | yes 2026-10-17T15:11:25.706Z | no HTTP 429 |
| probe-12 | 2026-10-17T09:12:58Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 513.8 | https://ar-io.dev | match | yes 2026-10-17T15:11:30.459Z | yes 2026-10-17T15:11:30.693Z | yes 2026-10-17T15:11:31.972Z | no HTTP 429 |
| probe-13 | 2026-10-17T09:12:58Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 513.6 | https://ar-io.dev | match | yes 2026-10-17T15:11:36.770Z | yes 2026-10-17T15:11:37.008Z | yes 2026-10-17T15:11:38.173Z | no HTTP 429 |
| probe-14 | 2026-10-17T09:12:58Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 513.4 | https://ar-io.dev | match | yes 2026-10-17T15:11:43.752Z | yes 2026-10-17T15:11:44.001Z | yes 2026-10-17T15:11:45.171Z | no HTTP 429 |
| probe-15 | 2026-10-17T09:13:00Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 511.7 | https://ar-io.dev | match | yes 2026-10-17T15:11:50.590Z | yes 2026-10-17T15:11:50.837Z | yes 2026-10-17T15:11:51.988Z | no HTTP 429 |
| probe-16 | 2026-10-17T09:13:00Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 511.5 | https://ar-io.dev | match | yes 2026-10-17T15:11:57.951Z | yes 2026-10-17T15:11:58.184Z | yes 2026-10-17T15:11:59.383Z | no HTTP 429 |
| probe-17 | 2026-10-17T09:13:00Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 511.3 | https://ar-io.dev | match | yes 2026-10-17T15:12:05.909Z | yes 2026-10-17T15:12:06.139Z | yes 2026-10-17T15:12:07.302Z | no HTTP 429 |
| probe-18 | 2026-10-17T09:13:00Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 511.1 | https://ar-io.dev | match | yes 2026-10-17T15:12:12.637Z | yes 2026-10-17T15:12:12.888Z | yes 2026-10-17T15:12:14.227Z | no HTTP 429 |
| probe-19 | 2026-10-17T09:13:01Z | ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE | 2023095 | 2026-10-17T09:21:32Z | 510.9 | https://ar-io.dev | match | yes 2026-10-17T15:12:20.279Z | yes 2026-10-17T15:12:20.523Z | yes 2026-10-17T15:12:21.678Z | no HTTP 429 |

arweave.net requests so far: 26.

The four Phase 2 rows share bundle `pzzVUc5WUQHkZMWHu3D12AseYrj6ZSwH1nx9lKurvxk`, L1 height 2023266, block 2026-10-17T15:21:00Z. That is before the b1 unlock at 2026-10-18T09:00:00Z. L1 status and the block came from ar-io.dev. Confirmations were 1 at the first observation and 127 at 2026-10-17T20:08Z.

Payload for those four items: a range read at 15:16Z, before the block, returned HTTP 404. A recheck after the block, `startOffsetInRootBundle + payloadDataStart` for `payloadContentLength` bytes, matched each uploaded sha256. The bundle was 185260 bytes. Phase 1 payloads matched on the first read.

arweave.net data reads returned HTTP 429 (169-byte body) for every item. Gateway columns for ar-io.dev, ario.zigza.xyz, and turbo-gateway.com are first observations by this poller. Phase 2 was uploaded at 15:05Z and the poller started at 15:09Z, so those times are an upper bound on when the bytes became readable.
