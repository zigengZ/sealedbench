// Verify one quicknet beacon from a JSON object on stdin.
// Prints PASS or FAIL. Exit 0 only on PASS.
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const candidates = [
  join(here, "..", "node_modules", "drand-client", "beacon-verification.js"),
];
const found = candidates.find((path) => existsSync(path));
if (!found) {
  console.error("FAIL drand-client is not installed (npm ci)");
  process.exit(2);
}
const require = createRequire(found);
const { verifyBeacon } = require(found);

const CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971";
const PUBLIC_KEY =
  "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a";

const raw = readFileSync(0, "utf8");
const body = JSON.parse(raw);
const beacon = body.beacon || body;
const round = Number(body.round || beacon.round);
const info = {
  public_key: body.public_key || PUBLIC_KEY,
  schemeID: "bls-unchained-g1-rfc9380",
  chain_hash: CHAIN_HASH,
};
const ok = await verifyBeacon(info, beacon, round);
if (!ok) {
  console.error(`FAIL round ${round}`);
  process.exit(1);
}
console.log(`PASS round ${round}`);
