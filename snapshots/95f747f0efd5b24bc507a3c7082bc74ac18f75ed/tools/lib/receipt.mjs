import { createHash, createPublicKey, verify, constants } from "node:crypto";
import { deepHash } from "@dha-team/arbundles";

function sha384(buf) {
  return createHash("sha384").update(buf).digest();
}

// Canonical ANS-104 deep hash: sha384(sha384("blob"||len) || raw_bytes).
export async function deepHashCanonical(data) {
  if (Array.isArray(data)) {
    let acc = sha384(
      Buffer.concat([Buffer.from("list"), Buffer.from(String(data.length))]),
    );
    for (const item of data) {
      acc = sha384(Buffer.concat([acc, await deepHashCanonical(item)]));
    }
    return acc;
  }
  const bytes = Buffer.isBuffer(data) ? data : Buffer.from(data);
  const tag = sha384(
    Buffer.concat([Buffer.from("blob"), Buffer.from(String(bytes.length))]),
  );
  return sha384(Buffer.concat([tag, bytes]));
}

export function addressFromModulus(publicB64url) {
  const mod = Buffer.from(publicB64url, "base64url");
  return createHash("sha256").update(mod).digest("base64url");
}

function pssOk(publicModulus, message, signatureB64url) {
  const key = createPublicKey({
    key: { kty: "RSA", n: publicModulus, e: "AQAB" },
    format: "jwk",
  });
  return verify(
    "sha256",
    Buffer.from(message),
    {
      key,
      padding: constants.RSA_PKCS1_PSS_PADDING,
      saltLength: 0,
    },
    Buffer.from(signatureB64url, "base64url"),
  );
}

export async function verifyTurboReceipt(receipt, pinnedInfo) {
  const pinnedAddress = pinnedInfo?.addresses?.arweave || null;
  const result = {
    id: receipt?.id || null,
    pinned_address: pinnedAddress,
    derived_address: null,
    address_match: false,
    signature_ok: false,
    signature_variant: null,
    pass: false,
    error: null,
  };
  try {
    if (!receipt?.public || !receipt?.signature || !receipt?.id) {
      result.error = "receipt missing id, public, or signature";
      return result;
    }
    result.derived_address = addressFromModulus(receipt.public);
    result.address_match =
      pinnedAddress !== null && result.derived_address === pinnedAddress;
    const parts = [
      Buffer.from("Bundlr"),
      Buffer.from(String(receipt.version)),
      Buffer.from(String(receipt.id)),
      Buffer.from(String(receipt.deadlineHeight)),
      Buffer.from(String(receipt.timestamp)),
    ];
    const canonical = await deepHashCanonical(parts);
    const library = Buffer.from(await deepHash(parts));
    if (pssOk(receipt.public, canonical, receipt.signature)) {
      result.signature_ok = true;
      result.signature_variant = "ans104-canonical-raw-bytes";
    } else if (pssOk(receipt.public, library, receipt.signature)) {
      result.signature_ok = true;
      result.signature_variant = "dha-team-arbundles-deepHash";
    }
    result.pass = result.address_match && result.signature_ok;
    if (!result.pass && !result.error) {
      result.error = !result.address_match
        ? "receipt.public does not hash to pinned Turbo address"
        : "signature did not verify under either deep-hash variant";
    }
  } catch (err) {
    result.error = err instanceof Error ? err.message : String(err);
  }
  return result;
}
