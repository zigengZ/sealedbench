// D2: upload each armored probe ciphertext through Turbo's free tier and
// verify the receipt against the pinned /info address.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { TurboFactory } from "@ardrive/turbo-sdk";

// The SDK logs at info by default and can echo request bodies. Silence it
// before the wallet is loaded into the client.
TurboFactory.setLogLevel("none");
import {
  CHAIN_HASH,
  TURBO_INFO_URL,
  WALLET_PATH,
  unlockUnix,
  utcNowIso,
} from "./lib/constants.mjs";
import { verifyTurboReceipt } from "./lib/receipt.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DAY1 = join(ROOT, "results", "day1");
const manifestPath = join(DAY1, "manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const wallet = JSON.parse(readFileSync(WALLET_PATH, "utf8"));

const infoRes = await fetch(TURBO_INFO_URL);
if (!infoRes.ok) {
  console.error(`turbo /info HTTP ${infoRes.status}`);
  process.exit(1);
}
const turboInfo = await infoRes.json();
writeFileSync(
  join(DAY1, "turbo_info.json"),
  JSON.stringify(turboInfo, null, 2) + "\n",
);
const pinned = turboInfo?.addresses?.arweave;
if (!pinned) {
  console.error("turbo /info did not include addresses.arweave");
  process.exit(1);
}
console.log(`pinned_turbo_address ${pinned}`);
console.log(
  `freeUploadLimitBytes ${turboInfo.freeUploadLimitBytes} lifetimeBytes ${turboInfo.freeTier?.lifetimeBytes}`,
);

const turbo = TurboFactory.authenticated({ privateKey: wallet });
let free = null;
try {
  free = await turbo.getFreeStatus();
  console.log(`free_status ${JSON.stringify(free)}`);
} catch (err) {
  console.log(
    `free_status_error ${err instanceof Error ? err.message : String(err)}`,
  );
}
writeFileSync(
  join(DAY1, "free_status.json"),
  JSON.stringify({ utc: utcNowIso(), free }, null, 2) + "\n",
);

mkdirSync(join(DAY1, "receipts"), { recursive: true });
const verifications = [];
let totalBytes = 0;

for (const probe of manifest.probes) {
  const cipherPath = join(ROOT, probe.ciphertext_path);
  const data = readFileSync(cipherPath);
  totalBytes += data.length;
  if (data.length > 100 * 1024) {
    console.error(`${probe.probe_id} ciphertext ${data.length} exceeds 100 KiB`);
    process.exit(1);
  }
  const slack = probe.unlock_unix - Date.now() / 1000;
  if (slack < 15 * 60 || slack > 25 * 60) {
    console.error(
      `${probe.probe_id} unlock slack ${slack.toFixed(0)}s is outside 15-25 min; not uploading`,
    );
    process.exit(1);
  }
  const tags = [
    { name: "Content-Type", value: "text/plain" },
    { name: "App-Name", value: "SealedBench" },
    { name: "App-Version", value: "0.0.1-probe" },
    { name: "Type", value: "probe" },
    { name: "Drand-Chain", value: CHAIN_HASH },
    { name: "Drand-Round", value: String(probe.round) },
    { name: "Probe-Id", value: probe.probe_id },
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
    console.error(`${probe.probe_id} UPLOAD_FAIL ${message}`);
    verifications.push({
      probe_id: probe.probe_id,
      pass: false,
      error: message,
      uploaded_utc: uploadedUtc,
    });
    writeFileSync(
      join(DAY1, "receipt_verify.json"),
      JSON.stringify(verifications, null, 2) + "\n",
    );
    process.exit(1);
  }
  const raw = JSON.parse(JSON.stringify(receipt));
  writeFileSync(
    join(DAY1, "receipts", `${probe.probe_id}.json`),
    JSON.stringify(raw, null, 2) + "\n",
  );
  const check = await verifyTurboReceipt(raw, turboInfo);
  check.probe_id = probe.probe_id;
  check.uploaded_utc = uploadedUtc;
  check.winc = raw.winc ?? null;
  check.bytes = data.length;
  check.unlock_minus_upload_s = Math.round(
    unlockUnix(probe.round) - Date.parse(uploadedUtc) / 1000,
  );
  verifications.push(check);
  console.log(
    `${probe.probe_id} id=${raw.id} winc=${raw.winc} verify=${check.pass} variant=${check.signature_variant} slack_s=${check.unlock_minus_upload_s}`,
  );
  writeFileSync(
    join(DAY1, "receipt_verify.json"),
    JSON.stringify(verifications, null, 2) + "\n",
  );
}

if (totalBytes > 1024 * 1024) {
  console.error(`total upload bytes ${totalBytes} exceed 1 MiB`);
  process.exit(1);
}
const failed = verifications.filter((v) => !v.pass);
console.log(
  `D2_DONE uploads=${verifications.length} bytes=${totalBytes} verify_fail=${failed.length}`,
);
if (failed.length) process.exit(2);
