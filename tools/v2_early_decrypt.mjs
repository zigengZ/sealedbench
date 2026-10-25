// Exit 0 when tlock-js refuses to decrypt. Exit 1 if it returns plaintext.
import { readFileSync } from "node:fs";
import { timelockDecrypt } from "tlock-js";
import { makeQuicknetClient } from "./lib/tlock_client.mjs";

const armor = readFileSync(process.argv[2], "utf8");
try {
  await timelockDecrypt(armor, makeQuicknetClient());
  console.log("UNEXPECTED_OK");
  process.exit(1);
} catch (err) {
  const message = err instanceof Error ? err.message : String(err);
  console.log(`REFUSED ${message.slice(0, 300)}`);
}
