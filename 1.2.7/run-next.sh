#!/bin/sh
# VESPER · the evening watch
# NOCTUA 1.2.7 acceptance battery — runs every leg cold and logs it.
# Usage: ./run-next.sh [--quick]
#   full battery: builders' suite, round-4/5/6 attack legs, Q battery +
#   invariants, the R battery, the R14 load envelope, the S1-S12
#   discriminating battery (fails on janus123, passes here), the
#   T1-T9 discriminating battery (fails on janus124, passes here), the
#   U1-U14 discriminating battery (fails on janus125, passes here),
#   and the V1-V15 discriminating battery (fails on janus126, passes
#   here).
# Logs: scratch/battery-<timestamp>.log and scratch/battery-latest.log
# Exit 0 and prints SUCCESS only when every leg passes.
set -u
TREE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BASE=$(dirname "$TREE")
T122="$BASE/janus122"
T123="$BASE/janus123"
T124="$BASE/janus124"
T125="$BASE/janus125"
T126="$BASE/janus126"
SCRATCH="$TREE/scratch"
mkdir -p "$SCRATCH/tmp"
export TMPDIR="$SCRATCH/tmp"
# 1.2.7 (S10 test-only fix): the full-battery context arms the S10
# case's single logged retry of a dropped /health sample. Standalone
# battery runs (invoking a battery file directly) do NOT set this —
# there, a dropped sample still fails, per the round-9 conditions.
export NOCTUA_BATTERY_CONTEXT=full
TS=$(date +%Y%m%d-%H%M%S)
LOG="$SCRATCH/battery-$TS.log"
QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1
FAIL=0
exec 3>&1 >>"$LOG" 2>&1
echo "=== NOCTUA 1.2.7 acceptance battery $TS tree=$TREE quick=$QUICK ==="
leg() {
  name=$1; shift
  echo "--- LEG $name: $*"
  if "$@"; then echo "LEG $name: PASS"; else echo "LEG $name: FAIL (exit $?)"; FAIL=1; fi
}
leg builders   python3 "$TREE/tests/run_tests.py"
leg round4     python3 "$TREE/tests/attacks/run_round4.py" "$TREE"
leg round5     python3 "$TREE/tests/attacks/run_round5.py" "$TREE"
if [ "$QUICK" = "0" ]; then
  leg round6   python3 "$TREE/tests/attacks/run_round6.py" "$TREE"
  leg q-plus-invariants python3 "$TREE/tests/run_q122_cases.py" "$TREE" --invariants
  leg r-battery python3 "$TREE/tests/run_r123_cases.py" "$TREE" "$T122"
  leg load-envelope python3 "$TREE/tests/run_load_envelope.py" "$T122" "$TREE"
  leg s-battery python3 "$TREE/tests/run_s124_cases.py" "$TREE" "$T123"
  leg t-battery python3 "$TREE/tests/run_t125_cases.py" "$TREE" "$T124"
  leg u-battery python3 "$TREE/tests/run_u126_cases.py" "$TREE" "$T125"
  leg v-battery python3 "$TREE/tests/run_v127_cases.py" "$TREE" "$T126"
fi
cp "$LOG" "$SCRATCH/battery-latest.log"
if [ "$FAIL" = "0" ]; then echo "BATTERY RESULT: SUCCESS"; else echo "BATTERY RESULT: FAILURE"; fi
if [ "$FAIL" = "0" ]; then echo "SUCCESS - full log: $LOG" >&3; else echo "FAILURE - full log: $LOG" >&3; fi
exit $FAIL
