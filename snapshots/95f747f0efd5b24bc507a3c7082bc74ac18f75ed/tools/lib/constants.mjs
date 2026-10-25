export const CHAIN_HASH =
  "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971";
export const CHAIN_PUBKEY =
  "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a";
export const GENESIS = 1692803367;
export const PERIOD_S = 3;
export const DRAND_URL = `https://api.drand.sh/${CHAIN_HASH}`;
export const WALLET_PATH = "/root/.config/sealedbench/throwaway-wallet.json";
export const N_PROBES = 20;
export const TURBO_INFO_URL = "https://upload.ardrive.io/info";

export function roundAtUnix(unixSec) {
  return Math.floor((unixSec - GENESIS) / PERIOD_S) + 1;
}

export function unlockUnix(round) {
  return GENESIS + (round - 1) * PERIOD_S;
}

export function utcNowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}
