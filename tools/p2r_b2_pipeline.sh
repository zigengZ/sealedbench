#!/bin/bash
# b2 pipeline. Restart-safe. Does not touch the live b1 checkout.
# Waits for round 33188212 and for the b1 pipeline to finish, then
# releases, infers, replays, scores, uploads, verifies, and pushes p2r.
set -u
cd /root/codes/sealedbench-p2r
export SEALEDBENCH_ROOT=/root/codes/sealedbench-p2r
export SEALEDBENCH_CACHE=/root/.cache/sealedbench
export PATH="${SEALEDBENCH_CACHE}/go1.27.2/bin:${SEALEDBENCH_CACHE}/node/current/bin:${SEALEDBENCH_CACHE}/gopath/bin:${PATH}"
export TLE="${SEALEDBENCH_CACHE}/gopath/bin/tle"
export LLAMA_COMPLETION="${SEALEDBENCH_CACHE}/llama.cpp/build/bin/llama-completion"
export PYTHONPATH=/root/codes/sealedbench-p2r
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /root/sbw/p2r results/batches/b2
LOG=/root/sbw/p2r/b2_pipeline.log
exec >>"$LOG" 2>&1
echo "B2_PIPELINE_START $(date -u +%FT%TZ)"
HEART=/root/sbw/p2r/b2_heartbeat
STATE=results/batches/b2/pipeline_state.json

beat() { date -u +%FT%TZ > "$HEART"; }

done_step() {
  python3 - "$1" << 'PY'
import json, sys
from pathlib import Path
path = Path("results/batches/b2/pipeline_state.json")
state = json.loads(path.read_text()) if path.exists() else {"steps": {}}
state["steps"][sys.argv[1]] = True
path.write_text(json.dumps(state, indent=2) + "\n")
PY
}

have_step() {
  python3 - "$1" << 'PY'
import json, sys
from pathlib import Path
path = Path("results/batches/b2/pipeline_state.json")
state = json.loads(path.read_text()) if path.exists() else {"steps": {}}
raise SystemExit(0 if state.get("steps", {}).get(sys.argv[1]) else 1)
PY
}

UNLOCK=1792368000
while true; do
  beat
  now=$(date +%s)
  echo "HEARTBEAT $(date -u +%FT%TZ) remaining=$((UNLOCK - now))"
  if (( now >= UNLOCK + 5 )); then
    break
  fi
  sleep 60
done

echo "WAIT_B1 $(date -u +%FT%TZ)"
while true; do
  beat
  if [[ -f /root/sbw/p2/DONE ]]; then
    echo "B1_DONE_FILE"
    break
  fi
  if ! kill -0 3557323 2>/dev/null; then
    echo "B1_PID_GONE"
    break
  fi
  sleep 60
done

if ! have_step release; then
  if ! python3 -m sealedbench release --batch b2; then
    echo "RELEASE_FAIL"
    exit 1
  fi
  done_step release
fi

MODELS=(qwen3-4b-instruct-2507 gemma-3-4b-it ministral-3-3b-instruct-2512 falcon3-1b-instruct)
for model in "${MODELS[@]}"; do
  beat
  if have_step "infer_$model"; then
    continue
  fi
  python3 -m sealedbench infer --batch b2 --models "$model" || echo "INFER_NONEMPTY_FAILURES $model"
  done_step "infer_$model"
done

if ! have_step replay; then
  python3 -m sealedbench replay --batch b2 --model qwen3-4b-instruct-2507 --items 10 || echo "REPLAY_FAIL"
  done_step replay
fi

if ! have_step score; then
  python3 -m sealedbench score --batch b2 || { echo "SCORE_FAIL"; exit 1; }
  done_step score
fi

if ! have_step upload; then
  if [[ -f /root/sbw/p2r/HOLD ]]; then
    echo "HOLD set; skipping result upload"
  else
    python3 tools/v2_upload_results.py || echo "UPLOAD_RESULTS_FAIL"
  fi
  done_step upload
fi

if ! have_step verify; then
  python3 tools/v2_verify.py || echo "VERIFY_NONEMPTY"
  done_step verify
fi

if ! have_step publish_git; then
  bash tools/secret_scan.sh || { echo "SECRET_SCAN_FAIL"; exit 1; }
  git add results/batches/b2 results/batches/cap2 sealedbench tools review || true
  if git diff --cached --quiet; then
    echo "NO_COMMIT"
  else
    git commit -m "b2: results after round 33188212" || echo "COMMIT_FAIL"
    git push origin p2r || echo "PUSH_FAIL"
  fi
  done_step publish_git
fi

echo "B2_PIPELINE_DONE $(date -u +%FT%TZ)" > /root/sbw/p2r/B2_DONE
echo "B2_PIPELINE_DONE"
