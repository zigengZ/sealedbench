// D3: polite GraphQL poller for L1 inclusion of the day-1 probe data items.
// One ids: query per cycle, at least 45s apart, for at most 3 hours.
import { readFileSync, writeFileSync, mkdirSync, appendFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DAY1 = join(ROOT, "results", "day1");
const POLL = join(DAY1, "poll");
mkdirSync(POLL, { recursive: true });

const INTERVAL_MS = 45_000;
const MAX_MS = 3 * 60 * 60 * 1000;
const GQL = "https://arweave.net/graphql";
const manifest = JSON.parse(readFileSync(join(DAY1, "manifest.json"), "utf8"));
const receipts = {};
for (const probe of manifest.probes) {
  const path = join(DAY1, "receipts", `${probe.probe_id}.json`);
  receipts[probe.probe_id] = JSON.parse(readFileSync(path, "utf8"));
}

const state = {
  started_utc: new Date().toISOString(),
  interval_s: INTERVAL_MS / 1000,
  max_hours: 3,
  probes: {},
};
for (const probe of manifest.probes) {
  const receipt = receipts[probe.probe_id];
  state.probes[probe.probe_id] = {
    probe_id: probe.probe_id,
    data_item_id: receipt.id,
    receipt_timestamp_ms: receipt.timestamp,
    deadline_height: receipt.deadlineHeight,
    first_seen_utc: null,
    first_seen_ms: null,
    inclusion_height: null,
    inclusion_timestamp_s: null,
    bundle_id: null,
    confirmations: null,
    confirmations_at_utc: null,
    bundle_status: null,
    deadline_minus_inclusion: null,
    seen: false,
    included: false,
  };
}

function percentile(sorted, p) {
  if (!sorted.length) return null;
  if (sorted.length === 1) return sorted[0];
  const k = (sorted.length - 1) * p;
  const f = Math.floor(k);
  const c = Math.ceil(k);
  if (f === c) return sorted[f];
  return sorted[f] + (sorted[c] - sorted[f]) * (k - f);
}

function summarize() {
  const rows = Object.values(state.probes);
  const blockDeltas = rows
    .filter((r) => r.inclusion_timestamp_s != null && r.receipt_timestamp_ms != null)
    .map((r) => r.inclusion_timestamp_s - r.receipt_timestamp_ms / 1000)
    .sort((a, b) => a - b);
  const seenDeltas = rows
    .filter((r) => r.first_seen_ms != null && r.receipt_timestamp_ms != null)
    .map((r) => (r.first_seen_ms - r.receipt_timestamp_ms) / 1000)
    .sort((a, b) => a - b);
  const stats = (xs) => ({
    n: xs.length,
    p50: percentile(xs, 0.5),
    p90: percentile(xs, 0.9),
    p95: percentile(xs, 0.95),
    max: xs.length ? xs[xs.length - 1] : null,
  });
  return {
    updated_utc: new Date().toISOString(),
    started_utc: state.started_utc,
    included: rows.filter((r) => r.included).length,
    not_included: rows.filter((r) => !r.included).length,
    seen_in_gql: rows.filter((r) => r.seen).length,
    block_timestamp_minus_receipt_s: stats(blockDeltas),
    first_seen_minus_receipt_s: stats(seenDeltas),
    percentile_method: "linear interpolation on sorted values, index (n-1)*p",
    probes: rows,
  };
}

function save() {
  const body = JSON.stringify(summarize(), null, 2) + "\n";
  writeFileSync(join(POLL, "latest.json"), body);
}

async function gql(ids) {
  const query = `query($ids:[ID!]!){
    transactions(ids:$ids, first:100){
      edges { node { id bundledIn { id } block { height timestamp } } }
    }
  }`;
  const res = await fetch(GQL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      accept: "application/json",
      "user-agent": "sealedbench/0.0.1",
    },
    body: JSON.stringify({ query, variables: { ids } }),
  });
  const text = await res.text();
  const retryAfterHeader = res.headers.get("retry-after");
  appendFileSync(
    join(POLL, "gql.log"),
    `${new Date().toISOString()} HTTP ${res.status} bytes ${text.length} retry-after ${retryAfterHeader || "-"}\n`,
  );
  if (!res.ok) {
    const err = new Error(`graphql HTTP ${res.status} ${text.slice(0, 180)}`);
    const retryAfter = Number(retryAfterHeader);
    err.retryAfterS = Number.isFinite(retryAfter) ? retryAfter : null;
    throw err;
  }
  const json = JSON.parse(text);
  if (json.errors) throw new Error(JSON.stringify(json.errors).slice(0, 500));
  return json.data?.transactions?.edges || [];
}

async function blockTimestamp(height) {
  const res = await fetch(`https://arweave.net/block/height/${height}`);
  const text = await res.text();
  if (!res.ok) return null;
  try {
    return JSON.parse(text).timestamp ?? null;
  } catch {
    return null;
  }
}

async function bundleStatus(bundleId) {
  const res = await fetch(`https://arweave.net/tx/${bundleId}/status`);
  const text = await res.text();
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text.slice(0, 300) };
  }
  return { http_status: res.status, body };
}

const ids = manifest.probes.map((p) => receipts[p.probe_id].id);
const byId = new Map(
  manifest.probes.map((p) => [receipts[p.probe_id].id, p.probe_id]),
);
const started = Date.now();
let cycle = 0;

while (Date.now() - started < MAX_MS) {
  cycle += 1;
  const cycleUtc = new Date().toISOString();
  let backedOff = false;
  try {
    const edges = await gql(ids);
    const seenThis = new Set();
    for (const edge of edges) {
      const node = edge.node;
      const probeId = byId.get(node.id);
      if (!probeId) continue;
      seenThis.add(probeId);
      const row = state.probes[probeId];
      row.seen = true;
      if (!row.first_seen_utc) {
        row.first_seen_utc = cycleUtc;
        row.first_seen_ms = Date.now();
      }
      if (node.bundledIn?.id) row.bundle_id = node.bundledIn.id;
      if (node.block?.height != null) {
        row.included = true;
        row.inclusion_height = node.block.height;
        row.inclusion_timestamp_s = node.block.timestamp;
        if (row.deadline_height != null) {
          row.deadline_minus_inclusion = row.deadline_height - node.block.height;
        }
      }
    }
    const bundleIds = [
      ...new Set(
        Object.values(state.probes)
          .map((r) => r.bundle_id)
          .filter(Boolean),
      ),
    ];
    for (const bundleId of bundleIds) {
      try {
        const status = await bundleStatus(bundleId);
        for (const row of Object.values(state.probes)) {
          if (row.bundle_id !== bundleId) continue;
          row.bundle_status = status.http_status;
          const conf = status.body?.number_of_confirmations;
          if (conf != null) {
            row.confirmations = conf;
            row.confirmations_at_utc = cycleUtc;
          }
          if (!row.included && status.body?.block_height != null) {
            row.included = true;
            row.inclusion_height = status.body.block_height;
            if (row.deadline_height != null) {
              row.deadline_minus_inclusion =
                row.deadline_height - status.body.block_height;
            }
          }
        }
      } catch (err) {
        appendFileSync(
          join(POLL, "gql.log"),
          `${cycleUtc} bundle ${bundleId} ${err instanceof Error ? err.message : err}\n`,
        );
      }
    }
    const heightsMissingTs = [
      ...new Set(
        Object.values(state.probes)
          .filter((r) => r.included && r.inclusion_height != null && r.inclusion_timestamp_s == null)
          .map((r) => r.inclusion_height),
      ),
    ];
    for (const height of heightsMissingTs) {
      const ts = await blockTimestamp(height);
      if (ts == null) continue;
      for (const row of Object.values(state.probes)) {
        if (row.inclusion_height === height && row.inclusion_timestamp_s == null) {
          row.inclusion_timestamp_s = ts;
        }
      }
    }
    console.log(
      `${cycleUtc} cycle=${cycle} gql_edges=${edges.length} included=${
        Object.values(state.probes).filter((r) => r.included).length
      }/${ids.length}`,
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`${cycleUtc} cycle=${cycle} ERROR ${message}`);
    appendFileSync(join(POLL, "gql.log"), `${cycleUtc} ERROR ${message}\n`);
    if (message.includes("429")) {
      backedOff = true;
      const waitS = Math.max((err.retryAfterS || 0) + 5, 120);
      console.error(`${cycleUtc} backing off ${waitS}s after HTTP 429`);
      await new Promise((r) => setTimeout(r, waitS * 1000));
    }
  }
  save();
  const allIncluded = Object.values(state.probes).every((r) => r.included);
  const minConf = Math.min(
    ...Object.values(state.probes).map((r) =>
      r.confirmations == null ? 0 : r.confirmations,
    ),
  );
  if (allIncluded && minConf >= 10) {
    console.log("all included with >=10 confirmations; stopping early");
    break;
  }
  const elapsed = Date.now() - started;
  if (elapsed + INTERVAL_MS >= MAX_MS) break;
  if (!backedOff) {
    await new Promise((r) => setTimeout(r, INTERVAL_MS));
  }
}

state.finished_utc = new Date().toISOString();
const finalBody = JSON.stringify({ ...summarize(), finished_utc: state.finished_utc }, null, 2) + "\n";
writeFileSync(join(POLL, "latest.json"), finalBody);
writeFileSync(join(POLL, "final.json"), finalBody);
console.log("D3_POLLER_DONE");
