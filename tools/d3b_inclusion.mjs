// D3′ inclusion poller. No arweave.net GraphQL.
// Turbo status at most once a second. arweave.net at most once per 10 minutes
// per URL, and in practice once per 10 minutes for the whole host.
// Writes results/inclusion/state.json and results/inclusion/summary.md each cycle.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "results", "inclusion");
mkdirSync(OUT, { recursive: true });

const INTERVAL_MS = 120_000;
const MAX_MS = 14 * 60 * 60 * 1000;
const TURBO_GAP_MS = 1100;
const ARWEAVE_GAP_MS = 10 * 60 * 1000 + 5000;
const DATA_GATEWAYS = ["https://ar-io.dev", "https://ario.zigza.xyz", "https://turbo-gateway.com"];
const ARWEAVE = "https://arweave.net";

const statePath = join(OUT, "state.json");
const state = existsSync(statePath)
  ? JSON.parse(readFileSync(statePath, "utf8"))
  : {
      started_utc: new Date().toISOString(),
      started_ms: Date.now(),
      items: {},
      arweave_last_ms: 0,
      arweave_attempts: 0,
      notes: [],
    };

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function get(url, headers = {}) {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "sealedbench/0.1.0", ...headers },
      signal: AbortSignal.timeout(30_000),
    });
    const buf = Buffer.from(await res.arrayBuffer());
    return { status: res.status, headers: res.headers, buf };
  } catch (err) {
    return {
      status: 0,
      headers: new Headers(),
      buf: Buffer.from(err instanceof Error ? err.message : String(err)),
    };
  }
}

function loadWanted() {
  const wanted = new Map();
  const day1 = JSON.parse(readFileSync(join(ROOT, "results", "day1", "manifest.json"), "utf8"));
  for (const probe of day1.probes) {
    const receipt = JSON.parse(readFileSync(join(ROOT, "results", "day1", "receipts", `${probe.probe_id}.json`), "utf8"));
    wanted.set(receipt.id, {
      label: probe.probe_id,
      group: "phase1",
      expected_sha256: probe.ciphertext_sha256,
      receipt_ts_ms: receipt.timestamp,
    });
  }
  for (const batch of ["b1", "cap"]) {
    const path = join(ROOT, "results", "batches", batch, "txids.json");
    if (!existsSync(path)) continue;
    const txids = JSON.parse(readFileSync(path, "utf8"));
    for (const [type, row] of Object.entries(txids.items || {})) {
      wanted.set(row.txid, {
        label: `${batch}/${type}`,
        group: batch,
        expected_sha256: row.sha256,
        receipt_ts_ms: row.receipt_timestamp_ms,
      });
    }
  }
  return wanted;
}

function ensure(id, meta) {
  if (!state.items[id]) {
    state.items[id] = {
      txid: id,
      label: meta.label,
      group: meta.group,
      expected_sha256: meta.expected_sha256,
      receipt_ts_ms: meta.receipt_ts_ms,
      turbo: null,
      l1: null,
      block: null,
      payload: null,
      gateways: {},
    };
  } else {
    state.items[id].label = meta.label;
    state.items[id].group = meta.group;
    state.items[id].expected_sha256 = meta.expected_sha256;
    state.items[id].receipt_ts_ms = meta.receipt_ts_ms;
  }
  return state.items[id];
}

async function turboStatus(item) {
  if (item.turbo && item.turbo.bundle_id && item.block) return;
  await sleep(TURBO_GAP_MS);
  const url = `https://upload.ardrive.io/v1/tx/${item.txid}/status`;
  try {
    const res = await get(url);
    if (res.status !== 200) {
      item.turbo = { ...(item.turbo || {}), http: res.status, utc: new Date().toISOString() };
      return;
    }
    const body = JSON.parse(res.buf.toString("utf8"));
    item.turbo = {
      http: 200,
      utc: new Date().toISOString(),
      status: body.status,
      bundle_id: body.bundleId || null,
      info: body.info || null,
      start_offset: body.startOffsetInRootBundle ?? null,
      payload_data_start: body.payloadDataStart ?? null,
      payload_length: body.payloadContentLength ?? null,
    };
  } catch (err) {
    item.turbo = { http: 0, error: err instanceof Error ? err.message : String(err) };
  }
}

async function arweaveGet(url) {
  const wait = ARWEAVE_GAP_MS - (Date.now() - state.arweave_last_ms);
  if (wait > 0) return null;
  state.arweave_last_ms = Date.now();
  state.arweave_attempts += 1;
  try {
    return await get(url);
  } catch (err) {
    return { status: 0, headers: new Headers(), buf: Buffer.from(String(err)) };
  }
}

async function fillL1(item) {
  const bundle = item.turbo && item.turbo.bundle_id;
  if (!bundle || item.block) return;
  const hosts = [ARWEAVE, "https://ar-io.dev", "https://ario.zigza.xyz"];
  let height = null;
  let l1Source = null;
  let confirmations = null;
  const attempts = item.l1_attempts || [];
  for (const host of hosts) {
    const url = `${host}/tx/${bundle}/status`;
    let res;
    if (host === ARWEAVE) {
      res = await arweaveGet(url);
      if (res === null) {
        attempts.push({ host, skipped: "arweave cooldown" });
        continue;
      }
    } else {
      res = await get(url);
    }
    let parsed = null;
    if (res.status === 200) {
      try {
        parsed = JSON.parse(res.buf.toString("utf8"));
      } catch {
        parsed = null;
      }
    }
    attempts.push({ host, http: res.status, height: parsed && parsed.block_height });
    if (!height && parsed && parsed.block_height) {
      height = parsed.block_height;
      l1Source = host;
      confirmations = parsed.number_of_confirmations;
    }
  }
  item.l1_attempts = attempts.slice(-12);
  if (!height) return;
  let block = null;
  let blockSource = null;
  for (const host of hosts) {
    const url = `${host}/block/height/${height}`;
    let res;
    if (host === ARWEAVE) {
      res = await arweaveGet(url);
      if (res === null) continue;
    } else {
      res = await get(url);
    }
    if (res.status === 200) {
      try {
        const parsed = JSON.parse(res.buf.toString("utf8"));
        if (parsed && parsed.timestamp && !block) {
          block = parsed;
          blockSource = host;
        }
      } catch {
        // keep looking
      }
    }
  }
  item.l1 = { source: l1Source, height, confirmations, bundle_id: bundle };
  if (block) {
    item.block = {
      source: blockSource,
      height: block.height,
      timestamp: block.timestamp,
      timestamp_utc: new Date(block.timestamp * 1000).toISOString().replace(/\.\d{3}Z$/, "Z"),
      indep_hash: block.indep_hash,
    };
  }
}

async function fillPayload(item) {
  if (item.payload || !item.turbo || !item.turbo.bundle_id) return;
  const start = item.turbo.start_offset;
  const rel = item.turbo.payload_data_start;
  const length = item.turbo.payload_length;
  if (![start, rel, length].every((v) => Number.isInteger(v)) || length < 0) return;
  const abs = start + rel;
  const end = abs + length - 1;
  const url = `https://ar-io.dev/${item.turbo.bundle_id}`;
  try {
    const res = await get(url, { Range: `bytes=${abs}-${end}` });
    const digest = sha256(res.buf);
    item.payload = {
      http: res.status,
      absolute_offset: abs,
      length,
      got: res.buf.length,
      sha256: digest,
      ok: (res.status === 200 || res.status === 206) && res.buf.length === length && digest === item.expected_sha256,
      utc: new Date().toISOString(),
    };
  } catch (err) {
    item.payload = { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function fillGateways(item) {
  for (const host of DATA_GATEWAYS) {
    if (item.gateways[host] && item.gateways[host].match) continue;
    const url = `${host}/${item.txid}`;
    try {
      const res = await get(url);
      const digest = sha256(res.buf);
      const match = res.status === 200 && digest === item.expected_sha256;
      const prev = item.gateways[host] || {};
      item.gateways[host] = {
        http: res.status,
        sha256: digest,
        match,
        bytes: res.buf.length,
        first_match_utc: match ? prev.first_match_utc || new Date().toISOString() : prev.first_match_utc || null,
        tries: (prev.tries || 0) + 1,
        last_utc: new Date().toISOString(),
      };
    } catch (err) {
      const prev = item.gateways[host] || {};
      item.gateways[host] = {
        ...prev,
        http: 0,
        match: false,
        error: err instanceof Error ? err.message : String(err),
        tries: (prev.tries || 0) + 1,
        last_utc: new Date().toISOString(),
      };
    }
    await sleep(200);
  }
}

async function arweaveDataOnce(items) {
  const pending = items.filter((item) => !(item.gateways[ARWEAVE] && item.gateways[ARWEAVE].match));
  if (!pending.length) return;
  pending.sort(
    (a, b) =>
      ((a.gateways[ARWEAVE] && a.gateways[ARWEAVE].tries) || 0) -
      ((b.gateways[ARWEAVE] && b.gateways[ARWEAVE].tries) || 0),
  );
  const item = pending[0];
  const res = await arweaveGet(`${ARWEAVE}/${item.txid}`);
  if (!res) return;
  const digest = sha256(res.buf);
  const match = res.status === 200 && digest === item.expected_sha256;
  const prev = item.gateways[ARWEAVE] || {};
  item.gateways[ARWEAVE] = {
    http: res.status,
    match,
    sha256: digest,
    bytes: res.buf.length,
    first_match_utc: match ? prev.first_match_utc || new Date().toISOString() : prev.first_match_utc || null,
    tries: (prev.tries || 0) + 1,
    last_utc: new Date().toISOString(),
  };
  console.log(`D3B_ARWEAVE ${item.label} http=${res.status} match=${match}`);
}

function percentile(sorted, p) {
  if (!sorted.length) return null;
  const k = Math.max(1, Math.ceil((p / 100) * sorted.length));
  return sorted[k - 1];
}

function fmt(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "n/a";
  return Number(n).toFixed(1);
}

function writeSummary() {
  const items = Object.values(state.items);
  const latencies = [];
  for (const item of items) {
    if (!item.block || !item.receipt_ts_ms) continue;
    const delta = item.block.timestamp - item.receipt_ts_ms / 1000;
    item.inclusion_latency_s = delta;
    latencies.push(delta);
  }
  latencies.sort((a, b) => a - b);
  const startedMs = state.started_ms;
  const fresh = items.filter((item) => item.receipt_ts_ms && item.receipt_ts_ms >= startedMs - 60_000);
  const lines = [];
  lines.push("# Inclusion");
  lines.push("");
  lines.push(`Poller started ${state.started_utc}. Updated ${new Date().toISOString()}.`);
  lines.push("");
  lines.push("L1 latency is block timestamp minus the Turbo receipt timestamp. It is historical, including the Phase 1 probes.");
  lines.push("Gateway times for items that already existed when the poller started are first observations, not first availability.");
  lines.push("Nearest-rank percentiles. arweave.net is requested at most once every 10 minutes.");
  lines.push("");
  lines.push(`Samples with a block timestamp: ${latencies.length}.`);
  lines.push("");
  lines.push("| stat | seconds |");
  lines.push("| --- | --- |");
  for (const [name, p] of [["min", 0], ["p50", 50], ["p90", 90], ["p95", 95], ["max", 100]]) {
    const value = name === "min" ? latencies[0] : name === "max" ? latencies[latencies.length - 1] : percentile(latencies, p);
    lines.push(`| ${name} | ${fmt(value)} |`);
  }
  lines.push("");
  lines.push("| item | receipt UTC | bundle | L1 height | block UTC | latency s | L1 source | payload | ar-io | zigza | turbo | arweave.net |");
  lines.push("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |");
  const gw = (item, host) => {
    const row = item.gateways[host];
    if (!row) return "—";
    if (row.match) return `yes ${row.first_match_utc || ""}`;
    return `no HTTP ${row.http}`;
  };
  for (const item of items.sort((a, b) => a.label.localeCompare(b.label))) {
    const receipt = item.receipt_ts_ms ? new Date(item.receipt_ts_ms).toISOString().replace(/\.\d{3}Z$/, "Z") : "n/a";
    lines.push(
      `| ${item.label} | ${receipt} | ${(item.turbo && item.turbo.bundle_id) || "n/a"} | ${(item.l1 && item.l1.height) || "n/a"} | ${(item.block && item.block.timestamp_utc) || "n/a"} | ${fmt(item.inclusion_latency_s)} | ${(item.l1 && item.l1.source) || "n/a"} | ${item.payload ? (item.payload.ok ? "match" : "no") : "n/a"} | ${gw(item, "https://ar-io.dev")} | ${gw(item, "https://ario.zigza.xyz")} | ${gw(item, "https://turbo-gateway.com")} | ${gw(item, ARWEAVE)} |`,
    );
  }
  lines.push("");
  if (fresh.length) {
    lines.push("## Gateway first-serve latency for items uploaded after the poller started");
    lines.push("");
    for (const host of [...DATA_GATEWAYS, ARWEAVE]) {
      const deltas = [];
      for (const item of fresh) {
        const row = item.gateways[host];
        if (row && row.match && row.first_match_utc && item.receipt_ts_ms) {
          deltas.push((Date.parse(row.first_match_utc) - item.receipt_ts_ms) / 1000);
        }
      }
      deltas.sort((a, b) => a - b);
      lines.push(`- ${host}: n=${deltas.length} p50=${fmt(percentile(deltas, 50))} p90=${fmt(percentile(deltas, 90))} max=${fmt(deltas[deltas.length - 1])}`);
    }
    lines.push("");
  }
  lines.push(`arweave.net requests so far: ${state.arweave_attempts}.`);
  lines.push("");
  writeFileSync(join(OUT, "summary.md"), lines.join("\n"));
  writeFileSync(statePath, JSON.stringify(state, null, 2) + "\n");
}

function finished() {
  if (Date.now() - state.started_ms > MAX_MS) return true;
  const items = Object.values(state.items);
  if (items.length < 20) return false;
  const phase2 = items.filter((item) => item.group === "b1" || item.group === "cap");
  if (phase2.length < 4) return false;
  if (state.arweave_attempts < 1) return false;
  const arweaveTried = items.every((item) => item.gateways[ARWEAVE] && item.gateways[ARWEAVE].tries >= 1);
  const arweaveDone = items.every((item) => item.gateways[ARWEAVE] && item.gateways[ARWEAVE].match);
  // One arweave.net data read per item, at most one host request every 10 minutes.
  if (!arweaveDone && !arweaveTried) return false;
  return items.every((item) => item.block && item.payload && DATA_GATEWAYS.every((host) => item.gateways[host]));
}

console.log(`D3B_START items_will_load ${new Date().toISOString()}`);
while (!finished()) {
  const wanted = loadWanted();
  for (const [id, meta] of wanted) ensure(id, meta);
  const items = Object.values(state.items);
  for (const item of items) {
    if (Date.now() - state.started_ms > MAX_MS) break;
    await turboStatus(item);
    console.log(
      `D3B_ITEM ${item.label} turbo=${(item.turbo && item.turbo.status) || "none"} http=${(item.turbo && item.turbo.http) || 0}`,
    );
    await fillL1(item);
    await fillPayload(item);
    await fillGateways(item);
  }
  await arweaveDataOnce(Object.values(state.items));
  writeSummary();
  const withBlock = items.filter((item) => item.block).length;
  console.log(`D3B_CYCLE items=${items.length} with_block=${withBlock} ${new Date().toISOString()}`);
  if (finished()) break;
  await sleep(INTERVAL_MS);
}
writeSummary();
console.log("D3B_DONE");
