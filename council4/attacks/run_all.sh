#!/usr/bin/env bash
# NOCTUA 1.2 — round-4 adversarial acceptance checks (Claude cloud seat).
# Written outside the build. A line printed as CONFIRMED is a defect that
# reproduced against the shipped code; NOT REPRODUCED means it did not.
# A27 is a negative control: it should NOT reproduce on OpenSSL 3.
#
#   NOCTUA12_TREE=/path/to/1.2/janus12 bash run_all.sh
#
# The tree must contain janus.py, sentinel.py, scripts/ and
# tests/run_tests.py (the builders' helpers are reused for spawning
# servers and making requests; no builders' test is relied on).
# Needs: python3 (3.12+ for tarfile filter=), openssl, git, bash.
# Uses loopback ports 19101-19163 and a temp dir; touches nothing else.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${NOCTUA12_TREE:?set NOCTUA12_TREE to the janus12 directory under test}"
export NOCTUA12_TREE
for f in attack1.py attack2.py attack2b.py attack3.py attack4.py attack5.py; do
  echo "=== $f"
  python3 -I "$HERE/$f" 2>&1 | grep -E '^(CONFIRMED|NOT REPRODUCED)'
done
