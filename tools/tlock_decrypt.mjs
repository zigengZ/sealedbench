// Decrypt one armored tlock ciphertext with tlock-js.
// Usage: node tools/tlock_decrypt.mjs <armor-path> <output-path>
import { readFileSync, writeFileSync } from "node:fs";
import { timelockDecrypt } from "tlock-js";
import { makeQuicknetClient } from "./lib/tlock_client.mjs";

const armor = readFileSync(process.argv[2], "utf8");
const client = makeQuicknetClient();
try {
  const out = await timelockDecrypt(armor, client);
  writeFileSync(process.argv[3], out);
  console.log("JS_DECRYPT_OK");
} catch (err) {
  const message = err instanceof Error ? err.message : String(err);
  console.error(message);
  process.exit(1);
}
