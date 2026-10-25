// Reserve conservatively BEFORE a submission. A lost response still consumes
// the phase budget; only a matching saved txid can skip a later submission.
export function reserveUpload(ledger, item, digest, bytes, limits) {
  if (bytes > limits.item || ledger.count + 1 > limits.count || ledger.total_bytes + bytes > limits.total) {
    throw new Error(`budget count=${ledger.count} bytes=${ledger.total_bytes} item=${bytes}`);
  }
  const reservation = {
    batch: item.batch, type: item.type, sha256: digest, bytes,
    file: item.path.split('/').pop(), status: 'reserved',
  };
  ledger.uploads.push(reservation);
  ledger.count += 1;
  ledger.total_bytes += bytes;
  return reservation;
}
