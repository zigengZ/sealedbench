// Upload one or more public artifacts through Turbo's free tier.
// Usage: node tools/upload_artifact.mjs <spec.json>
// spec: { "items": [{ "path", "type", "batch", "round", "content_type" }] }
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { TurboFactory } from "@ardrive/turbo-sdk";

TurboFactory.setLogLevel("none");
import { TURBO_INFO_URL, WALLET_PATH, utcNowIso } from "./lib/constants.mjs";
import { verifyTurboReceipt } from "./lib/receipt.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const spec = JSON.parse(readFileSync(process.argv[2], "utf8"));
const wallet = JSON.parse(readFileSync(WALLET_PATH, "utf8"));
const ledgerPath = join(ROOT, "results", "batches", "upload_ledger.json");
const ledger = existsSync(ledgerPath)
  ? JSON.parse(readFileSync(ledgerPath, "utf8"))
  : { uploads: [], total_bytes: 0, count: 0 };

const MAX_ITEM = 100 * 1024;
const MAX_TOTAL = 2 * 1024 * 1024;
const MAX_COUNT = 30;

const infoRes = await fetch(TURBO_INFO_URL);
if (!infoRes.ok) {
  console.error(`turbo /info HTTP ${infoRes.status}`);
  process.exit(1);
}
const turboInfo = await infoRes.json();
const pinned = turboInfo?.addresses?.arweave;
if (!pinned) {
  console.error("turbo /info missing addresses.arweave");
  process.exit(1);
}
writeFileSync(join(ROOT, "results", "batches", "turbo_info.json"), JSON.stringify(turboInfo, null, 2) + "\n");

const turbo = TurboFactory.authenticated({ privateKey: wallet });
let free = null;
try {
  free = await turbo.getFreeStatus();
  console.log(`free_status ${JSON.stringify(free)}`);
} catch (err) {
  console.log(`free_status_error ${err instanceof Error ? err.message : String(err)}`);
}

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function txidsPath(batch) {
  return join(ROOT, "results", "batches", batch, "txids.json");
}

function loadTxids(batch) {
  const path = txidsPath(batch);
  if (!existsSync(path)) return { batch_id: batch, items: {} };
  return JSON.parse(readFileSync(path, "utf8"));
}

for (const item of spec.items) {
  const data = readFileSync(join(ROOT, item.path));
  if (data.length > MAX_ITEM) {
    console.error(`${item.path} is ${data.length} bytes, over 100 KiB`);
    process.exit(1);
  }
  if (ledger.count + 1 > MAX_COUNT || ledger.total_bytes + data.length > MAX_TOTAL) {
    console.error(`upload budget exceeded count=${ledger.count} bytes=${ledger.total_bytes}`);
    process.exit(1);
  }
  const txids = loadTxids(item.batch);
  if (txids.items[item.type]?.txid) {
    console.log(`SKIP ${item.batch} ${item.type} already ${txids.items[item.type].txid}`);
    continue;
  }
  const tags = [
    { name: "Content-Type", value: item.content_type },
    { name: "App-Name", value: "SealedBench" },
    { name: "App-Version", value: "0.1.0" },
    { name: "Type", value: item.type },
    { name: "Batch", value: item.batch },
    { name: "Drand-Round", value: String(item.round) },
  ];
  const uploadedUtc = utcNowIso();
  let receipt;
  try {
    receipt = await turbo.upload({ data, dataItemOpts: { tags } });
  } catch (err) {
    const rawMessage = err instanceof Error ? err.message : String(err);
    const q = '"';
    const dField = `${q}d${q}:`;
    const message = rawMessage
      .replace(new RegExp(`${dField}\\s*${q}[^${q}]*${q}`, "g"), `${dField}${q}[redacted]${q}`)
      .replace(/[A-Za-z0-9_-]{180,}/g, "[redacted-long]");
    console.error(`UPLOAD_FAIL ${item.batch} ${item.type} ${message}`);
    process.exit(1);
  }
  const raw = JSON.parse(JSON.stringify(receipt));
  if (String(raw.winc ?? "0") !== "0") {
    console.error(`UPLOAD_FAIL winc=${raw.winc} would spend credits; not accepting`);
    process.exit(1);
  }
  const check = await verifyTurboReceipt(raw, turboInfo);
  if (!check.pass) {
    console.error(`RECEIPT_FAIL ${item.batch} ${item.type} ${check.error}`);
    process.exit(1);
  }
  const receiptDir = join(ROOT, "results", "batches", item.batch, "receipts");
  mkdirSync(receiptDir, { recursive: true });
  const receiptName = `${item.type}.json`;
  writeFileSync(join(receiptDir, receiptName), JSON.stringify(raw, null, 2) + "\n");
  const digest = sha256(data);
  txids.items[item.type] = {
    txid: raw.id,
    sha256: digest,
    bytes: data.length,
    round: item.round,
    content_type: item.content_type,
    uploaded_utc: uploadedUtc,
    winc: raw.winc,
    receipt_timestamp_ms: raw.timestamp,
    receipt_path: `results/batches/${item.batch}/receipts/${receiptName}`,
    signature_variant: check.signature_variant,
  };
  writeFileSync(txidsPath(item.batch), JSON.stringify(txids, null, 2) + "\n");
  ledger.uploads.push({
    batch: item.batch,
    type: item.type,
    txid: raw.id,
    bytes: data.length,
    sha256: digest,
    uploaded_utc: uploadedUtc,
    file: basename(item.path),
  });
  ledger.count += 1;
  ledger.total_bytes += data.length;
  writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n");
  console.log(`${item.batch} ${item.type} id=${raw.id} bytes=${data.length} verify=PASS variant=${check.signature_variant}`);
}
console.log(`UPLOAD_DONE count=${ledger.count} bytes=${ledger.total_bytes}`);
