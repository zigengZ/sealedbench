import { mkdirSync, writeFileSync, existsSync, chmodSync } from "node:fs";
import { dirname } from "node:path";
import Arweave from "arweave";
import { WALLET_PATH, utcNowIso } from "./lib/constants.mjs";

const outMd = new URL("../results/day1/WALLET.md", import.meta.url);

if (existsSync(WALLET_PATH)) {
  console.error(`refusing to overwrite existing wallet at ${WALLET_PATH}`);
  process.exit(1);
}

mkdirSync(dirname(WALLET_PATH), { recursive: true, mode: 0o700 });
chmodSync(dirname(WALLET_PATH), 0o700);

const arweave = Arweave.init({
  host: "arweave.net",
  port: 443,
  protocol: "https",
});
const jwk = await arweave.wallets.generate();
writeFileSync(WALLET_PATH, JSON.stringify(jwk), { mode: 0o600 });
chmodSync(WALLET_PATH, 0o600);
const address = await arweave.wallets.jwkToAddress(jwk);

const created = utcNowIso();
const md = `# Throwaway wallet

Public address only. The JWK lives at \`${WALLET_PATH}\` with mode 0600 and is not in this repository.

| field | value |
| --- | --- |
| address | \`${address}\` |
| created_utc | ${created} |
| algorithm | RSA-4096 (Arweave JWK, public exponent 65537) |
`;
mkdirSync(new URL("../results/day1/", import.meta.url), { recursive: true });
writeFileSync(outMd, md);
console.log(address);
console.log(created);
