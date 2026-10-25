#!/bin/bash
# b2 orchestration v2. The original script is deliberately left untouched.
set -Eeuo pipefail
ROOT=${SEALEDBENCH_ROOT:-/root/codes/sealedbench-p2r}
BATCH=${SEALEDBENCH_BATCH:-b2}
if [[ "$BATCH" != b2 ]]; then
  [[ "$BATCH" == b2r && "${SEALEDBENCH_DRY_UPLOAD:-0}" == 1 && "$ROOT" == /root/codes/sealedbench-b2r ]] || exit 64
fi
if [[ "$BATCH" == b2 && ( "$ROOT" != /root/codes/sealedbench-p2r || "${SEALEDBENCH_DRY_UPLOAD:-0}" == 1 ) ]]; then exit 64; fi
cd "$ROOT"
export SEALEDBENCH_ROOT="$ROOT"
export SEALEDBENCH_BATCH="$BATCH"
export SEALEDBENCH_CACHE=/root/.cache/sealedbench
export PATH="${SEALEDBENCH_CACHE}/go1.27.2/bin:${SEALEDBENCH_CACHE}/node/current/bin:${SEALEDBENCH_CACHE}/gopath/bin:${PATH}"
export TLE="${SEALEDBENCH_CACHE}/gopath/bin/tle"
export LLAMA_COMPLETION="${SEALEDBENCH_CACHE}/llama.cpp/build/bin/llama-completion"
export PYTHONPATH="$ROOT"
export PYTHONDONTWRITEBYTECODE=1
if [[ "$BATCH" == b2 ]]; then
  CONTROL=/root/sbw/p2r
  LOG="$CONTROL/b2_pipeline.log"
  HEART="$CONTROL/b2_heartbeat"
  DONE="$CONTROL/B2_DONE"
else
  CONTROL=/root/sbw/c2r
  LOG="$CONTROL/b2r_pipeline.log"
  HEART="$CONTROL/b2r_heartbeat"
  DONE="$CONTROL/B2R_DONE"
fi
mkdir -p "$CONTROL" "results/batches/$BATCH"
export SEALEDBENCH_PIPELINE_STATE="$CONTROL/${BATCH}_pipeline_state.json"
exec >>"$LOG" 2>&1
exec 9>"$CONTROL/${BATCH}_pipeline.lock"
flock -n 9 || { echo "ALREADY_RUNNING $BATCH"; exit 75; }
echo "PIPELINE_V2_START $(date -u +%FT%TZ) batch=$BATCH pid=$$"
beat() { date -u +%FT%TZ > "$HEART"; }
have_step() { python3 -m sealedbench.v2.pipeline_state have "$BATCH" "$1"; }
done_step() { python3 -m sealedbench.v2.pipeline_state done "$BATCH" "$1"; }
# Only terminate descendants of this pipeline when the pipeline itself is stopped.
cleanup() {
  trap - TERM INT
  python3 - "$$" <<'PY'
import os,signal,subprocess,sys
parent=int(sys.argv[1]);own=os.getpid()
rows=[list(map(int,line.split())) for line in subprocess.check_output(['ps','-eo','pid=,ppid='],text=True).splitlines()]
children={parent}
while True:
    more={pid for pid,ppid in rows if ppid in children}
    if more<=children:break
    children|=more
for pid in children-{parent,own}:
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
PY
  echo "PIPELINE_INTERRUPTED $(date -u +%FT%TZ)"
  exit 143
}
trap cleanup TERM INT
trap 'echo "PIPELINE_ERROR line=$LINENO rc=$? $(date -u +%FT%TZ)"' ERR
retry_delay=${SEALEDBENCH_RETRY_DELAY:-60}
disk_ok() {
  local available
  available=$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')
  [[ "$available" -ge 1048576 ]]
}
retry() {
  local rc
  while true; do
    beat
    if ! disk_ok; then
      echo "DISK_WAIT less than 1 GiB free $(date -u +%FT%TZ)"
      sleep "$retry_delay"; continue
    fi
    "$@" &
    child=$!
    if wait "$child"; then return 0; else rc=$?; fi
    echo "STEP_RETRY rc=$rc command=$* $(date -u +%FT%TZ)"
    sleep "$retry_delay"
  done
}
step_once() {
  local step=$1; shift
  "$@" || return $?
  done_step "$step"
}
run_step() {
  local step=$1; shift
  if have_step "$step"; then echo "STEP_SKIP $step"; return; fi
  echo "STEP_START $step $(date -u +%FT%TZ)"
  retry step_once "$step" "$@"
  echo "STEP_DONE $step $(date -u +%FT%TZ)"
}
if [[ "$BATCH" == b2 ]]; then
  UNLOCK=1792368000
  while true; do
    beat; now=$(date +%s)
    echo "HEARTBEAT $(date -u +%FT%TZ) remaining=$((UNLOCK-now))"
    if (( now >= UNLOCK+5 )); then break; fi
    sleep 60
  done
  # No cutoff: a b1 overrun delays b2, and is logged every minute.
  while true; do
    beat
    b1_args=$(ps -p 3557323 -o args= || true)
    if python3 -m sealedbench.v2.pipeline_state llama-active; then llama_active=yes; else llama_active=no; fi
    if [[ "$b1_args" != *'/root/codes/sealedbench/tools/p2_pipeline.sh'* && "$llama_active" == no ]]; then break; fi
    echo "WAIT_B1 $(date -u +%FT%TZ) pid_active=$([[ -n "$b1_args" ]] && echo yes || echo no) llama_active=$llama_active"
    sleep 60
  done
fi
run_step release python3 -m sealedbench release --batch "$BATCH"
# Rehearsal inference is forcibly bounded by 08:40Z; the real b2 run is tomorrow.
if [[ "$BATCH" == b2r ]]; then
  deadline=1792312790
  (
    while (( $(date +%s) < deadline )); do sleep 10; done
    echo "REHEARSAL_CPU_DEADLINE"
    kill -TERM "$$"
  ) &
  watchdog=$!
fi
infer_once() {
  local model=$1 rc
  if [[ "$BATCH" == b2r ]] && (( $(date +%s) >= 1792312790 )); then return 125; fi
  if python3 -m sealedbench infer --batch "$BATCH" --models "$model"; then rc=0; else rc=$?; fi
  if (( rc != 0 && rc != 2 )); then return "$rc"; fi
  # rc=2 is accepted only for a complete, terminal partial model: all items
  # have metadata, matching output hashes and two attempts for crashed items.
  python3 -m sealedbench.v2.pipeline_state validate-infer "$BATCH" "$model" || return 1
  if (( rc==2 )); then echo "MODEL_PARTIAL $model"; fi
}
for model in qwen3-4b-instruct-2507 gemma-3-4b-it ministral-3-3b-instruct-2512 falcon3-1b-instruct; do
  run_step "infer_$model" infer_once "$model"
done
run_step replay python3 -m sealedbench replay --batch "$BATCH" --model qwen3-4b-instruct-2507 --items 10
if [[ "$BATCH" == b2r ]]; then kill "$watchdog"; wait "$watchdog" || true; fi
run_step score python3 -m sealedbench score --batch "$BATCH"
upload_once() {
  if [[ -f /root/sbw/p2r/HOLD ]]; then echo "UPLOAD_HOLD"; return 1; fi
  python3 tools/v2_upload_results.py
}
run_step upload upload_once
verify_once() {
  local rc
  if python3 tools/v2_verify.py; then rc=0; else rc=$?; fi
  [[ "$rc" == 0 || "$rc" == 2 ]] || return "$rc"
  # An exception returning 2 must not be treated as an UNKNOWN report.
  python3 -m sealedbench.v2.pipeline_state done "$BATCH" verify
}
run_step verify verify_once
# Keep a reviewable checkpoint snapshot in the published results.
cp "$SEALEDBENCH_PIPELINE_STATE" "results/batches/$BATCH/pipeline_state.json"
publish_git() {
  local branch
  branch=$(git branch --show-current)
  [[ "$branch" == "$([[ "$BATCH" == b2 ]] && echo p2r || echo b2r)" ]] || return 1
  bash tools/secret_scan.sh || return 1
  # Explicit result paths only. Never recursively stage extracted src/secrets,
  # arbitrary module edits, other batches, or unrelated files.
  python3 tools/v2_stage_results.py "$BATCH" || return 1
  if ! git diff --cached --quiet; then
    git commit -m "$BATCH: results after the registered release round" || return 1
  fi
  # Always push, including restart after a local commit followed by failed push.
  bash tools/secret_scan.sh || return 1
  git push origin "$branch" || return 1
}
retry publish_git
date -u +"PIPELINE_V2_DONE %FT%TZ" > "$DONE"
echo "PIPELINE_V2_DONE batch=$BATCH"
