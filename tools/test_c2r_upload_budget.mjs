import test from 'node:test';
import assert from 'node:assert/strict';
import { reserveUpload } from './lib/v2_upload_budget.mjs';

test('uncertain submissions consume count and bytes before any receipt', () => {
  const ledger = { count: 5, total_bytes: 135875, uploads: [] };
  const item = { batch: 'b2', type: 'results', path: 'scores.json' };
  const limits = { item: 100 * 1024, count: 7, total: 2 * 1024 * 1024 };
  const first = reserveUpload(ledger, item, 'hash', 100, limits);
  assert.equal(first.status, 'reserved');
  // No receipt for first: reserve another attempt, still counting the first.
  reserveUpload(ledger, item, 'hash', 100, limits);
  assert.equal(ledger.count, 7);
  assert.equal(ledger.total_bytes, 136075);
  assert.throws(() => reserveUpload(ledger, item, 'hash', 100, limits), /budget/);
});

test('byte and item caps reject before mutating the ledger', () => {
  const ledger = { count: 5, total_bytes: 900, uploads: [] };
  const limits = { item: 100, count: 25, total: 1000 };
  assert.throws(() => reserveUpload(ledger, {path:'x'}, 'hash', 101, limits), /budget/);
  ledger.total_bytes = 950;
  assert.throws(() => reserveUpload(ledger, {path:'x'}, 'hash', 60, limits), /budget/);
  assert.equal(ledger.count, 5);
  assert.equal(ledger.uploads.length, 0);
});
