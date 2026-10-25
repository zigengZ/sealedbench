// Upload v2 artifacts through Turbo's free tier.
// spec: { "items": [{ path, type, batch, round, unlock_unix, unlock_utc, content_type, chain }] }
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { TurboFactory } from "@ardrive/turbo-sdk";
import { TURBO_INFO_URL, WALLET_PATH } from "./lib/constants.mjs";
import { verifyTurboReceipt } from "./lib/receipt.mjs";
import { reserveUpload } from "./lib/v2_upload_budget.mjs";

TurboFactory.setLogLevel("none");

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const spec = JSON.parse(readFileSync(process.argv[2], "utf8"));
const wallet = JSON.parse(readFileSync(WALLET_PATH, "utf8"));
const ledgerPath = join(ROOT, "results", "batches", "p2r_upload_ledger.json");
const ledger = existsSync(ledgerPath)
  ? JSON.parse(readFileSync(ledgerPath, "utf8"))
  : { uploads: [], total_bytes: 0, count: 0 };
const MAX_ITEM = 100 * 1024;
const MAX_TOTAL = 2 * 1024 * 1024;
const MAX_COUNT = 25;

function atomicJson(path, document) {
  const temporary = `${path}.partial`;
  writeFileSync(temporary, JSON.stringify(document, null, 2) + "\n");
  renameSync(temporary, path);
}

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
function txidsPath(batch) {
  return join(ROOT, "results", "batches", batch, "txids.json");
}
function loadTxids(batch) {
  const path = txidsPath(batch);
  if (!existsSync(path)) return { batch_id: batch, items: {} };
  return JSON.parse(readFileSync(path, "utf8"));
}

const infoRes = await fetch(TURBO_INFO_URL);
if (!infoRes.ok) {
  console.error(`turbo /info HTTP ${infoRes.status}`);
  process.exit(1);
}
const turboInfo = await infoRes.json();
if (turboInfo?.addresses?.arweave !== "JNC6vBhjHY1EPwV3pEeNmrsgFMxH5d38_LHsZ7jful8") {
  console.error("turbo address is not the pinned free-tier address");
  process.exit(1);
}
const turbo = TurboFactory.authenticated({ privateKey: wallet });

for (let index = 0; index < spec.items.length; index += 1) {
  if (index) await sleep(1200);
  const item = spec.items[index];
  const data = readFileSync(join(ROOT, item.path));
  const digest = sha256(data);
  if (data.length > MAX_ITEM) {
    console.error(`${item.path} is ${data.length} bytes`);
    process.exit(1);
  }
  const txids = loadTxids(item.batch);
  if (txids.items[item.type]?.txid && txids.items[item.type].sha256 === digest) {
    console.log(`SKIP ${item.batch} ${item.type} ${txids.items[item.type].txid}`);
    continue;
  }
  if (ledger.count + 1 > MAX_COUNT || ledger.total_bytes + data.length > MAX_TOTAL) {
    console.error(`budget count=${ledger.count} bytes=${ledger.total_bytes}`);
    process.exit(1);
  }
  const tags = [
    { name: "Content-Type", value: item.content_type },
    { name: "App-Name", value: "SealedBench" },
    { name: "App-Version", value: "0.2.0" },
    { name: "Protocol", value: "sealedbench/v2" },
    { name: "Type", value: item.type },
    { name: "Batch", value: item.batch },
    { name: "Drand-Chain", value: item.chain },
    { name: "Drand-Round", value: String(item.round) },
    { name: "Unlock-Unix", value: String(item.unlock_unix) },
    { name: "Unlock-UTC", value: item.unlock_utc },
    { name: "Content-SHA256", value: digest },
  ];
  const reservation = reserveUpload(ledger, item, digest, data.length, {
    item: MAX_ITEM, count: MAX_COUNT, total: MAX_TOTAL,
  });
  atomicJson(ledgerPath, ledger);
  let receipt;
  try {
    receipt = await turbo.upload({ data, dataItemOpts: { tags } });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`UPLOAD_FAIL ${item.batch} ${item.type} ${message.replace(/[A-Za-z0-9_-]{180,}/g, "[redacted-long]")}`);
    process.exit(1);
  }
  const raw = JSON.parse(JSON.stringify(receipt));
  if (String(raw.winc ?? "0") !== "0") {
    console.error(`UPLOAD_FAIL winc=${raw.winc}`);
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
  const uploadedUtc = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  txids.items[item.type] = {
    txid: raw.id,
    sha256: digest,
    bytes: data.length,
    round: item.round,
    unlock_unix: item.unlock_unix,
    content_type: item.content_type,
    uploaded_utc: uploadedUtc,
    winc: String(raw.winc),
    receipt_timestamp_ms: raw.timestamp,
    receipt_path: `results/batches/${item.batch}/receipts/${receiptName}`,
    signature_variant: check.signature_variant,
    tags: tags,
  };
  atomicJson(txidsPath(item.batch), txids);
  Object.assign(reservation, {
    txid: raw.id, uploaded_utc: uploadedUtc, status: 'receipt_verified',
  });
  atomicJson(ledgerPath, ledger);
  console.log(`${item.batch} ${item.type} id=${raw.id} bytes=${data.length} sha256=${digest}`);
}
console.log(`UPLOAD_DONE count=${ledger.count} bytes=${ledger.total_bytes}`);
