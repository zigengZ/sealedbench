#!/bin/bash
# Wait for the b1 round, then release, infer, score, publish, verify, and replay.
# One llama-completion at a time. Safe to re-run: finished items are skipped.
set -u
source /root/codes/sealedbench/tools/env.sh
cd /root/codes/sealedbench
mkdir -p results/batches/b1 /root/sbw/p2
LOG=results/batches/b1/pipeline.log
exec >>"$LOG" 2>&1
echo "PIPELINE_START $(date -u +%FT%TZ)"

commit_paths() {
  local msg="$1"
  shift
  bash tools/secret_scan.sh || { echo "SECRET_SCAN_FAIL"; return 1; }
  git add "$@" || return 1
  if git diff --cached --quiet; then
    echo "NO_COMMIT $msg"
    return 0
  fi
  git commit -m "$msg" || return 1
  git pull --rebase origin main || return 1
  git push origin main || return 1
}

mark() {
  python3 -m sealedbench.statuslog "$@" || true
}

UNLOCK=1792314000
while true; do
  now=$(date +%s)
  echo "HEARTBEAT $(date -u +%FT%TZ) remaining=$((UNLOCK - now))"
  if (( now >= UNLOCK + 5 )); then
    break
  fi
  sleep 60
done

if ! python3 -m sealedbench release --batch b1; then
  mark R1 FAIL "release command exited non-zero; see results/batches/b1/pipeline.log"
  echo "R1_FAIL" > /root/sbw/p2/DONE
  exit 1
fi
python3 - << 'PY'
import json
from pathlib import Path
rec=json.loads(Path("results/batches/b1/release.json").read_text())
print(f"valid={rec['batch_valid']} items={rec['n_items']} qsha={rec['question_set_sha256']} js={rec['js_decrypt_match']}")
PY
qsha=$(python3 -c 'import json; print(json.load(open("results/batches/b1/release.json"))["question_set_sha256"])')
valid=$(python3 -c 'import json; print(json.load(open("results/batches/b1/release.json"))["batch_valid"])')
mark R1 PASS "question_set_sha256 ${qsha}" "batch_valid ${valid}" "items.jsonl results/batches/b1/items.jsonl" "beacon results/batches/b1/beacon.json"
commit_paths "R1: release b1 and write the question set" \
  results/batches/b1/items.jsonl results/batches/b1/release.json results/batches/b1/beacon.json \
  results/batches/b1/inclusion_manifest.json results/batches/b1/inclusion_ciphertext.json STATUS.md || echo "COMMIT_R1_FAIL"

FIRST=qwen3-4b-instruct-2507
if ! python3 -m sealedbench infer --batch b1 --models "$FIRST"; then
  echo "INFER_FIRST_NONEMPTY_FAILURES"
fi
if ! python3 -m sealedbench replay --batch b1 --model "$FIRST" --items 10; then
  mark V2 FAIL "early replay of ${FIRST} k=10 did not match; see results/batches/b1/replay_${FIRST}.json"
else
  matches=$(python3 -c "import json; print(json.load(open('results/batches/b1/replay_${FIRST}.json'))['matches'])")
  mark V2 PASS "early replay ${FIRST} matches ${matches}/10 before the index upload" "results/batches/b1/replay_${FIRST}.json"
fi
cp -f "results/batches/b1/replay_${FIRST}.json" "results/batches/b1/replay_${FIRST}_early.json" || true
commit_paths "R2: ${FIRST} completions and a 10-item replay" \
  "results/batches/b1/runs/${FIRST}" "results/batches/b1/reference_runs/${FIRST}" \
  "results/batches/b1/replay" "results/batches/b1/replay_${FIRST}.json" STATUS.md || echo "COMMIT_R2A_FAIL"

if ! python3 -m sealedbench infer --batch b1 --models gemma-3-4b-it ministral-3-3b-instruct-2512 falcon3-1b-instruct; then
  echo "INFER_REST_FAILURES"
fi
mark R2 PASS "four models finished or recorded per-item failures in results/batches/b1/runs" "one llama-completion at a time, manifest flags"
commit_paths "R2: remaining b1 completions" \
  results/batches/b1/runs results/batches/b1/reference_runs STATUS.md || echo "COMMIT_R2_FAIL"

if ! python3 -m sealedbench score --batch b1; then
  mark R3 FAIL "score command failed"
  echo "R3_FAIL" > /root/sbw/p2/DONE
  exit 1
fi
mark R3 PASS "results/batches/b1/scores.json" "results/batches/b1/scores.md" "batch_valid ${valid}"
commit_paths "R3: score b1" results/batches/b1/scores.json results/batches/b1/scores.md results/batches/b1/grades.jsonl results/batches/b1/completions.tar.gz STATUS.md || echo "COMMIT_R3_FAIL"

if ! python3 -m sealedbench publish --batch b1; then
  mark R4 FAIL "publish failed"
  echo "R4_FAIL" > /root/sbw/p2/DONE
  exit 1
fi
index_txid=$(python3 -c 'import json; print(json.load(open("results/batches/b1/txids.json"))["items"]["index"]["txid"])')
mark R4 PASS "index ${index_txid}" "results/batches/b1/txids.json" "results/batches/b1/index.json"
commit_paths "R4: upload b1 scores and index" \
  results/batches/b1/index.json results/batches/b1/txids.json results/batches/b1/receipts \
  results/batches/upload_ledger.json STATUS.md || echo "COMMIT_R4_FAIL"

set +e
python3 -m sealedbench verify --txid "$index_txid" --batch b1
verify_rc=$?
set -e
if [[ "$verify_rc" -eq 0 ]]; then
  mark V1 PASS "verify exit 0" "index ${index_txid}" "output results/batches/b1/verify_output.txt"
else
  mark V1 FAIL "verify exit ${verify_rc}" "index ${index_txid}" "output results/batches/b1/verify_output.txt"
fi

set +e
python3 -m sealedbench replay --txid "$index_txid" --model "$FIRST" --items 10
replay_rc=$?
set -e
matches=$(python3 -c "import json; print(json.load(open('results/batches/b1/replay_${FIRST}.json'))['matches'])" 2>/dev/null || echo "n/a")
if [[ "$replay_rc" -eq 0 ]]; then
  mark V2 PASS "replay --txid ${index_txid} --model ${FIRST} --items 10 matches ${matches}/10"
else
  mark V2 FAIL "replay --txid exit ${replay_rc} matches ${matches}/10"
fi

# Refresh the inclusion summary if the poller has written one.
if [[ -f results/inclusion/summary.md ]]; then
  commit_paths "D3: refresh inclusion summary after b1" results/inclusion STATUS.md || true
fi

commit_paths "Phase 2: verify output and final replay" \
  results/batches/b1/verify_output.txt "results/batches/b1/replay_${FIRST}.json" \
  results/batches/b1/replay STATUS.md || echo "COMMIT_FINAL_FAIL"

echo "PIPELINE_DONE $(date -u +%FT%TZ) verify_rc=${verify_rc} replay_rc=${replay_rc} index=${index_txid}" > /root/sbw/p2/DONE
echo "PIPELINE_DONE"
