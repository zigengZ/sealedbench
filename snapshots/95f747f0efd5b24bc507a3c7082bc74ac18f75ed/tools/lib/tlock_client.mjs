import { HttpCachingChain, HttpChainClient } from "tlock-js";
import { CHAIN_HASH, CHAIN_PUBKEY, DRAND_URL } from "./constants.mjs";

export function makeQuicknetClient() {
  const opts = {
    chainVerificationParams: {
      chainHash: CHAIN_HASH,
      publicKey: CHAIN_PUBKEY,
    },
  };
  return new HttpChainClient(new HttpCachingChain(DRAND_URL, opts), opts);
}
