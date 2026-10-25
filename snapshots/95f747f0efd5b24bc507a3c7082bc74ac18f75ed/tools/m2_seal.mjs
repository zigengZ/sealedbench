// Encrypt the generator tarball to the b1 and cap quicknet rounds and prove
// that both Go tle and tlock-js refuse to decrypt before the round.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { timelockDecrypt } from "tlock-js";
import { CHAIN_HASH, utcNowIso } from "./lib/constants.mjs";
import { makeQuicknetClient } from "./lib/tlock_client.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TLE = process.env.TLE || "/root/.cache/sealedbench/gopath/bin/tle";
const plain = readFileSync(join(ROOT, "results", "batches", "generator.tar.gz"));
const client = makeQuicknetClient();

const batches = [
  { id: "b1", round: 33170212, unlock_utc: "2026-10-18T09:00:00Z" },
  { id: "cap", round: 33980212, unlock_utc: "2026-11-15T12:00:00Z" },
];

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
    child.on("error", (e) => resolve({ code: 127, stdout: Buffer.alloc(0), stderr: Buffer.from(String(e)) }));
    child.on("close", (code) => resolve({ code: code ?? 1, stdout: Buffer.concat(out), stderr: Buffer.concat(err) }));
    child.stdin.end(input);
  });
}

const records = [];
for (const batch of batches) {
  const dir = join(ROOT, "results", "batches", batch.id);
  mkdirSync(dir, { recursive: true });
  const enc = await runTle(
    ["-e", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH, "-r", String(batch.round), "-a"],
    plain,
  );
  if (enc.code !== 0 || enc.stdout.length < 80) {
    console.error(`${batch.id} encrypt failed ${enc.code} ${enc.stderr.toString()}`);
    process.exit(1);
  }
  const cipherPath = join(dir, "generator.tlock");
  writeFileSync(cipherPath, enc.stdout);
  const goAt = utcNowIso();
  const decGo = await runTle(["-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH], enc.stdout);
  const jsAt = utcNowIso();
  let js = { ok: false, error_name: null, error_message: null };
  try {
    const out = await timelockDecrypt(enc.stdout.toString("utf8"), client);
    js = { ok: true, error_name: null, error_message: null, unexpected_plaintext_sha256: sha256(Buffer.from(out)) };
  } catch (err) {
    js = {
      ok: false,
      error_name: err instanceof Error ? err.name : "Error",
      error_message: err instanceof Error ? err.message : String(err),
    };
  }
  const record = {
    batch_id: batch.id,
    round: batch.round,
    unlock_utc: batch.unlock_utc,
    plaintext_sha256: sha256(plain),
    plaintext_bytes: plain.length,
    ciphertext_sha256: sha256(enc.stdout),
    ciphertext_bytes: enc.stdout.length,
    early_decrypt: {
      go: {
        utc: goAt,
        exit_code: decGo.code,
        ok: decGo.code === 0,
        stderr: decGo.stderr.toString("utf8").trim().slice(0, 500),
        stdout_bytes: decGo.stdout.length,
      },
      js: { utc: jsAt, ...js },
    },
  };
  writeFileSync(join(dir, "early_decrypt.json"), JSON.stringify(record, null, 2) + "\n");
  records.push(record);
  const goFail = record.early_decrypt.go.ok === false;
  const jsFail = record.early_decrypt.js.ok === false;
  console.log(
    `${batch.id} round=${batch.round} cipher_bytes=${record.ciphertext_bytes} sha=${record.ciphertext_sha256} early_go_fail=${goFail} early_js_fail=${jsFail}`,
  );
  if (!goFail || !jsFail) {
    console.error(`${batch.id} early decrypt unexpectedly succeeded`);
    process.exit(2);
  }
}
writeFileSync(join(ROOT, "results", "batches", "seal_hashes.json"), JSON.stringify({ records }, null, 2) + "\n");
console.log("M2_SEALED");
