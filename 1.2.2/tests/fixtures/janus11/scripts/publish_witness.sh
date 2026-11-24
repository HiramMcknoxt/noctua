#!/usr/bin/env bash
# NOCTUA witness publication — run DAILY (09:00 city time; host cron:
#   0 9 * * *  /srv/noctua/scripts/publish_witness.sh
# It was weekly until the Nov. 23, 2026 council round: a weekly anchor
# leaves up to seven days of chain an insider could rewrite and recompute
# before anyone outside holds a copy. Daily signed checkpoints shrink
# that window to a day, and the entry count makes silent truncation —
# cutting entries off the end — visible too.)
#
# Runs scripts/checkpoint.py, which HMAC-signs {date, root, entries}
# with the audit key, then publishes the checkpoint OUTSIDE the system:
# appended to a checkpoints file in a public git repository and emailed
# to the City Clerk. Tamper-evidence works because someone else holds a
# copy — if the live chain is ever rewritten, its checkpoints will
# disagree with the published ones.
#
# KEY CUSTODY (read the README's hardening section before trusting this):
# the checkpoint signature means the most when the audit key is held by
# the Clerk/auditor side. checkpoint.py resolves the key from
# $NOCTUA_AUDIT_KEY or the .audit_key file next to the database; if that
# key lives on this server, the checkpoint still detects outside
# tampering, but not a fully privileged insider who holds both the chain
# and the key. The shipping default is the server-side key — its limits
# are stated, not hidden.
#
# checkpoint.py reads the database file directly, so this script must
# run where NOCTUA_DB points at the live database (on the Docker host,
# NOCTUA_DB=/srv/noctua-data/... or run it inside a one-shot container:
#   docker compose run --rm -e NOCTUA_DB=/data/noctua.db retention \
#     python3 /scripts/checkpoint.py
# — set CHECKPOINT_CMD to override how the checkpoint is produced.)
#
# Fill in: WITNESS_REPO (a git repo the city controls, e.g. a public
# GitHub repo), CLERK_EMAIL.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WITNESS_REPO="${WITNESS_REPO:-/srv/noctua-witness}"
CLERK_EMAIL="${CLERK_EMAIL:-clerk@cabotar.gov}"
CHECKPOINT_CMD="${CHECKPOINT_CMD:-python3 $SCRIPT_DIR/checkpoint.py}"

CP_JSON=$($CHECKPOINT_CMD)
CP_DATE=$(echo "$CP_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['date'])")
CP_ROOT=$(echo "$CP_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['root'])")
CP_ENTRIES=$(echo "$CP_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['entries'])")

mkdir -p "$WITNESS_REPO"
echo "$CP_JSON" >> "$WITNESS_REPO/checkpoints.jsonl"

# Publish: commit + push the witness repo (repo remote configured by the city).
if [ -d "$WITNESS_REPO/.git" ]; then
  git -C "$WITNESS_REPO" add checkpoints.jsonl
  git -C "$WITNESS_REPO" commit -m "NOCTUA checkpoint $CP_DATE ($CP_ENTRIES entries)" || true
  git -C "$WITNESS_REPO" push || echo "WARN: witness push failed — checkpoint saved locally only"
fi

# Email the Clerk their copy (mailx or equivalent on the host).
if command -v mail >/dev/null 2>&1; then
  echo "NOCTUA daily audit checkpoint: $CP_ENTRIES entries, root $CP_ROOT, $CP_DATE. Full signed checkpoint: $CP_JSON" | \
    mail -s "NOCTUA checkpoint — $CP_DATE" "$CLERK_EMAIL" || true
fi
echo "checkpoint published: $CP_DATE root=$CP_ROOT entries=$CP_ENTRIES"
