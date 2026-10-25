// D1: create N probe payloads, tlock-encrypt them to future quicknet rounds,
// and immediately show that both Go tle and tlock-js refuse to decrypt.
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { timelockDecrypt } from "tlock-js";
import {
  CHAIN_HASH,
  N_PROBES,
  roundAtUnix,
  unlockUnix,
  utcNowIso,
} from "./lib/constants.mjs";
import { makeQuicknetClient } from "./lib/tlock_client.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DAY1 = join(ROOT, "results", "day1");
const PLAIN_DIR = join(DAY1, "plain");
const CIPHER_DIR = join(DAY1, "cipher");
const TLE = process.env.TLE || "/root/.cache/sealedbench/gopath/bin/tle";
const BASE_OFFSET_S = 20 * 60;
const STAGGER_S = 12;

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
    child.on("error", (e) => {
      resolve({
        code: 127,
        stdout: Buffer.concat(out),
        stderr: Buffer.from(String(e)),
      });
    });
    child.on("close", (code) => {
      resolve({
        code: code ?? 1,
        stdout: Buffer.concat(out),
        stderr: Buffer.concat(err),
      });
    });
    child.stdin.end(input);
  });
}

mkdirSync(PLAIN_DIR, { recursive: true });
mkdirSync(CIPHER_DIR, { recursive: true });

const client = makeQuicknetClient();
const probes = [];

for (let i = 0; i < N_PROBES; i++) {
  const probeId = `probe-${String(i).padStart(2, "0")}`;
  const created = utcNowIso();
  const payload = Buffer.from(
    JSON.stringify({
      probe_id: probeId,
      created_utc: created,
      nonce: randomBytes(32).toString("hex"),
      note: "SealedBench day-1 probe; not an exam",
    }),
  );
  const now = Date.now() / 1000;
  const target = now + BASE_OFFSET_S + i * STAGGER_S;
  const round = roundAtUnix(target);
  const unlock = unlockUnix(round);
  const plainPath = join(PLAIN_DIR, `${probeId}.json`);
  const cipherPath = join(CIPHER_DIR, `${probeId}.tlock`);
  writeFileSync(plainPath, payload);

  const enc = await runTle(
    ["-e", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH, "-r", String(round), "-a"],
    payload,
  );
  if (enc.code !== 0 || enc.stdout.length < 80) {
    console.error(
      `${probeId} encrypt failed code=${enc.code} stderr=${enc.stderr.toString()}`,
    );
    process.exit(1);
  }
  writeFileSync(cipherPath, enc.stdout);

  const goAttemptUtc = utcNowIso();
  const decGo = await runTle(
    ["-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
    enc.stdout,
  );
  const jsAttemptUtc = utcNowIso();
  let js = { ok: false, error_name: null, error_message: null };
  try {
    const out = await timelockDecrypt(enc.stdout.toString("utf8"), client);
    js = {
      ok: true,
      error_name: null,
      error_message: null,
      unexpected_plaintext_sha256: sha256(Buffer.from(out)),
    };
  } catch (err) {
    js = {
      ok: false,
      error_name: err instanceof Error ? err.name : "Error",
      error_message: err instanceof Error ? err.message : String(err),
    };
  }

  const record = {
    probe_id: probeId,
    created_utc: created,
    round,
    unlock_unix: unlock,
    unlock_utc: new Date(unlock * 1000).toISOString().replace(/\.\d{3}Z$/, "Z"),
    seconds_from_encrypt_to_unlock: Math.round(unlock - now),
    plaintext_sha256: sha256(payload),
    plaintext_bytes: payload.length,
    ciphertext_sha256: sha256(enc.stdout),
    ciphertext_bytes: enc.stdout.length,
    plaintext_path: `results/day1/plain/${probeId}.json`,
    ciphertext_path: `results/day1/cipher/${probeId}.tlock`,
    early_decrypt: {
      go: {
        utc: goAttemptUtc,
        exit_code: decGo.code,
        ok: decGo.code === 0,
        stderr: decGo.stderr.toString("utf8").trim(),
        stdout_sha256: sha256(decGo.stdout),
        stdout_bytes: decGo.stdout.length,
      },
      js: { utc: jsAttemptUtc, ...js },
    },
  };
  probes.push(record);
  const goFail = record.early_decrypt.go.ok === false;
  const jsFail = record.early_decrypt.js.ok === false;
  console.log(
    `${probeId} round=${round} unlock=${record.unlock_utc} bytes=${record.ciphertext_bytes} early_go_fail=${goFail} early_js_fail=${jsFail}`,
  );
  if (!goFail || !jsFail) {
    console.error(`${probeId} early decrypt unexpectedly succeeded`);
  }
}

const manifest = {
  created_utc: utcNowIso(),
  chain_hash: CHAIN_HASH,
  scheme: "bls-unchained-g1-rfc9380",
  period_s: 3,
  genesis: 1692803367,
  n: probes.length,
  tle: "github.com/drand/tlock/cmd/tle@v1.2.0",
  tlock_js: "0.9.0",
  armor: true,
  note: "Ciphertexts are public probes, not exams. Plaintext is committed so a third party can check the decrypt.",
  probes,
};
writeFileSync(join(DAY1, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
const earlyFails = probes.filter(
  (p) => p.early_decrypt.go.ok === false && p.early_decrypt.js.ok === false,
).length;
console.log(`D1_SEALED ${probes.length} early_fail_both=${earlyFails}`);
if (earlyFails !== probes.length) process.exit(2);
