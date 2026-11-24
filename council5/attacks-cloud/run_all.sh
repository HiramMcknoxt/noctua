#!/usr/bin/env bash
# NOCTUA council round 5 — adversarial checks against 1.2.1 (Claude cloud
# seat). Written outside the build. A line printed as REPRODUCED is a
# defect that reproduced against the shipped code; NOT REPRODUCED means
# it did not. Any script that dies prints ERROR — a silent verdict is a
# harness failure, never a pass.
#
#   NOCTUA121_TREE=/path/to/noctua/1.2.1 \
#   NOCTUA11_TREE=/path/to/noctua/1.1 bash run_all.sh
#
# The 1.2.1 tree must contain janus.py, sentinel.py, scripts/ and
# tests/run_tests.py (the builders' helpers are reused unmodified for
# spawning servers and making requests). R5-01 and R5-13 boot the real
# 1.1 code first and upgrade its database in place.
# Needs: python3 (3.12+), openssl, bash. Uses loopback ports 19201-19299
# and temp dirs only.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${NOCTUA121_TREE:?set NOCTUA121_TREE to the 1.2.1 directory under test}"
: "${NOCTUA11_TREE:?set NOCTUA11_TREE to the 1.1 directory (upgrade attacks)}"
export NOCTUA121_TREE NOCTUA11_TREE
status=0
for f in r5_legacy_suppression.py r5_hotlist_expiry.py r5_supersede.py \
         r5_evidence_deadend.py r5_parity.py r5_gate_order.py \
         r5_rotation_grind.py r5_gates.py r5_minor.py \
         r5_restore_envkey.py; do
  echo "=== $f"
  out="$(python3 -I "$HERE/$f" 2>&1)"
  rc=$?
  echo "$out" | grep -E '^(REPRODUCED|NOT REPRODUCED|ERROR)'
  if [ $rc -ne 0 ] || ! echo "$out" | grep -qE '^(REPRODUCED|NOT REPRODUCED)'; then
    echo "ERROR: $f exited $rc without a full verdict (harness failure)"
    echo "$out" | tail -5
    status=1
  fi
done
exit $status
