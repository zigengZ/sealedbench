#!/bin/bash
# Exit 1 if the repo tree looks like it contains private key material.
set -euo pipefail
cd /root/codes/sealedbench
# The needles are assembled so this script does not itself contain them.
q='"'
priv=$(printf '%s%s' PRI VATE)
pat="${q}d${q}:|${q}p${q}:|BEGIN (RSA |OPENSSH |EC )?${priv} KEY|${priv} KEY"
hits=$(grep -RInE --exclude-dir=.git --exclude-dir=node_modules \
  --exclude-dir=__pycache__ \
  "${pat}" . || true)
if [[ -n "${hits}" ]]; then
  echo "SECRET_SCAN_FAIL"
  echo "${hits}" | head -80
  exit 1
fi
echo "SECRET_SCAN_OK"
