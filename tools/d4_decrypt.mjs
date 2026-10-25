// D4: after each probe unlocks, fetch the ciphertext from two gateways,
// decrypt with Go tle and tlock-js, and record the drand beacon.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, appendFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { timelockDecrypt } from "tlock-js";
import { CHAIN_HASH, DRAND_URL, utcNowIso } from "./lib/constants.mjs";
import { makeQuicknetClient } from "./lib/tlock_client.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DAY1 = join(ROOT, "results", "day1");
const OUT = join(DAY1, "decrypt");
mkdirSync(OUT, { recursive: true });
const TLE = process.env.TLE || "/root/.cache/sealedbench/gopath/bin/tle";
const GATEWAYS = ["https://arweave.net", "https://ario.zigza.xyz"];
const INTERVAL_MS = 45_000;
const MAX_MS = 3 * 60 * 60 * 1000;

const manifest = JSON.parse(readFileSync(join(DAY1, "manifest.json"), "utf8"));
const client = makeQuicknetClient();

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function runTle(args, input) {
  return new Promise((resolve) => {
    const child = spawn(TLE, args, { stdio: ["pipe", "pipe", "pipe"] });
    const out = [];
    const err = [];
    child.stdout.on("data", (d) => out.push(d));
    child.stderr.on("data", (d) => err.push(d));
    child.on("error", (e) =>
      resolve({ code: 127, stdout: Buffer.alloc(0), stderr: Buffer.from(String(e)) }),
    );
    child.on("close", (code) =>
      resolve({ code: code ?? 1, stdout: Buffer.concat(out), stderr: Buffer.concat(err) }),
    );
    child.stdin.end(input);
  });
}

async function fetchGateway(base, id) {
  const url = `${base}/${id}`;
  const started = utcNowIso();
  try {
    const res = await fetch(url);
    const buf = Buffer.from(await res.arrayBuffer());
    const retryAfter = Number(res.headers.get("retry-after"));
    return {
      url,
      utc: started,
      http_status: res.status,
      bytes: buf.length,
      sha256: sha256(buf),
      body: res.status === 200 ? buf : null,
      content_type: res.headers.get("content-type"),
      retry_after_s: Number.isFinite(retryAfter) ? retryAfter : null,
    };
  } catch (err) {
    return {
      url,
      utc: started,
      http_status: 0,
      error: err instanceof Error ? err.message : String(err),
      body: null,
    };
  }
}

async function beacon(round) {
  const res = await fetch(`${DRAND_URL}/public/${round}`);
  const text = await res.text();
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text.slice(0, 400) };
  }
  return { http_status: res.status, body };
}

const pending = new Map();
for (const probe of manifest.probes) {
  const receipt = JSON.parse(
    readFileSync(join(DAY1, "receipts", `${probe.probe_id}.json`), "utf8"),
  );
  const localCipher = readFileSync(join(ROOT, probe.ciphertext_path));
  const localPlain = readFileSync(join(ROOT, probe.plaintext_path));
  pending.set(probe.probe_id, {
    probe,
    receipt,
    localCipher,
    localPlain,
    attempts: [],
    done: false,
  });
}

const started = Date.now();
while (pending.size && Date.now() - started < MAX_MS) {
  const now = Date.now() / 1000;
  let cycleRetryAfterS = 0;
  for (const [id, job] of [...pending]) {
    if (now + 1 < job.probe.unlock_unix) continue;
    const attempt = { utc: utcNowIso(), gateways: {} };
    let served = null;
    for (const gw of GATEWAYS) {
      const got = await fetchGateway(gw, job.receipt.id);
      const summary = { ...got };
      delete summary.body;
      summary.matches_local_ciphertext =
        got.body != null && got.sha256 === job.probe.ciphertext_sha256;
      if (got.retry_after_s) {
        cycleRetryAfterS = Math.max(cycleRetryAfterS, got.retry_after_s);
      }
      attempt.gateways[gw] = summary;
      if (got.body && got.sha256 === job.probe.ciphertext_sha256 && !served) {
        served = { gateway: gw, body: got.body };
      }
    }
    if (!served) {
      // A gateway may have returned 200 with different bytes (an error page).
      // Keep the first 200 body only if it matches. Otherwise retry.
      attempt.decrypt = null;
      job.attempts.push(attempt);
      writeFileSync(
        join(OUT, `${id}.json`),
        JSON.stringify(
          {
            probe_id: id,
            data_item_id: job.receipt.id,
            round: job.probe.round,
            unlock_utc: job.probe.unlock_utc,
            done: false,
            attempts: job.attempts,
          },
          null,
          2,
        ) + "\n",
      );
      console.log(`${id} not yet byte-identical on a gateway`);
      continue;
    }
    const go = await runTle(
      ["-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
      served.body,
    );
    let jsPlain = null;
    let jsError = null;
    try {
      const out = await timelockDecrypt(served.body.toString("utf8"), client);
      jsPlain = Buffer.from(out);
    } catch (err) {
      jsError = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    }
    let beaconResult = null;
    try {
      beaconResult = await beacon(job.probe.round);
    } catch (err) {
      beaconResult = { error: err instanceof Error ? err.message : String(err) };
    }
    const plainSha = sha256(job.localPlain);
    attempt.served_by = served.gateway;
    attempt.decrypt = {
      go: {
        exit_code: go.code,
        sha256: sha256(go.stdout),
        matches_plaintext: sha256(go.stdout) === plainSha,
        stderr: go.stderr.toString("utf8").trim(),
      },
      js: {
        sha256: jsPlain ? sha256(jsPlain) : null,
        matches_plaintext: jsPlain ? sha256(jsPlain) === plainSha : false,
        error: jsError,
      },
    };
    attempt.drand = beaconResult;
    attempt.plaintext_sha256 = plainSha;
    job.attempts.push(attempt);
    const ok =
      attempt.decrypt.go.matches_plaintext && attempt.decrypt.js.matches_plaintext;
    job.done = ok;
    writeFileSync(
      join(OUT, `${id}.json`),
      JSON.stringify(
        {
          probe_id: id,
          data_item_id: job.receipt.id,
          round: job.probe.round,
          unlock_utc: job.probe.unlock_utc,
          done: job.done,
          served_by: served.gateway,
          drand_randomness: beaconResult?.body?.randomness || null,
          drand_signature: beaconResult?.body?.signature || null,
          go_match: attempt.decrypt.go.matches_plaintext,
          js_match: attempt.decrypt.js.matches_plaintext,
          attempts: job.attempts,
        },
        null,
        2,
      ) + "\n",
    );
    console.log(
      `${id} served_by=${served.gateway} go=${attempt.decrypt.go.matches_plaintext} js=${attempt.decrypt.js.matches_plaintext}`,
    );
    if (ok) pending.delete(id);
  }
  if (!pending.size) break;
  const nextUnlock = Math.min(
    ...[...pending.values()].map((j) => j.probe.unlock_unix),
  );
  const rateWaitMs = cycleRetryAfterS > 0 ? (cycleRetryAfterS + 5) * 1000 : 0;
  const waitMs = Math.max(
    1000,
    rateWaitMs ||
      Math.min(INTERVAL_MS, Math.ceil((nextUnlock - Date.now() / 1000) * 1000)),
  );
  if (Date.now() - started + waitMs >= MAX_MS) break;
  await new Promise((r) => setTimeout(r, Math.min(waitMs, INTERVAL_MS)));
}

const summary = {
  finished_utc: utcNowIso(),
  remaining: [...pending.keys()],
};
writeFileSync(join(OUT, "summary.json"), JSON.stringify(summary, null, 2) + "\n");
appendFileSync(join(OUT, "summary.json"), "");
console.log(`D4_DONE remaining=${summary.remaining.length}`);
if (summary.remaining.length) process.exit(2);
