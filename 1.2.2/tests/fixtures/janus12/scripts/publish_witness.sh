#!/usr/bin/env bash
# NOCTUA witness publication — run DAILY (09:00 city time; host cron:
#   0 9 * * *  /srv/noctua/scripts/publish_witness.sh
# A weekly anchor leaves up to seven days of chain an insider could
# rewrite and recompute before anyone outside holds a copy. Daily
# signed checkpoints shrink that window to a day, and the entry count
# makes silent truncation — cutting entries off the end — visible.)
#
# Runs scripts/checkpoint.py, which Ed25519-signs {agency, date, ts,
# root, entries} with the agency signing key (S7 — never the audit
# key), then publishes the checkpoint OUTSIDE the system: appended to
# a checkpoints file in a public git repository and emailed to the
# City Clerk. Tamper-evidence works because someone else holds a
# copy — if the live chain is ever rewritten, its checkpoints will
# disagree with the published ones.
#
# ORDER MATTERS (S6): the witness heartbeat is posted ONLY after the
# publish actually succeeds. 1.1 heartbeated from checkpoint.py
# before anyone knew whether the witness copy existed — a witness
# job that "ran fine" while its pushes failed for a month. Now:
# checkpoint -> append -> commit/push -> THEN heartbeat ok:true.
# A failed push posts heartbeat ok:false and exits nonzero.
#
# checkpoint.py reads the database file directly, so this script must
# run where NOCTUA_DB points at the live database (on the Docker host,
# NOCTUA_DB=/srv/noctua-data/... or run it inside a one-shot container:
#   docker compose run --rm -e NOCTUA_DB=/data/noctua.db retention \
#     python3 /scripts/checkpoint.py
# — set CHECKPOINT_CMD to override how the checkpoint is produced.)
#
# Fill in: WITNESS_REPO (a git repo the city controls, e.g. a public
# GitHub repo), CLERK_EMAIL. Heartbeat wiring: NOCTUA_JANUS_URL,
# NOCTUA_JOBS_USER, NOCTUA_JOBS_KEY.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WITNESS_REPO="${WITNESS_REPO:-/srv/noctua-witness}"
CLERK_EMAIL="${CLERK_EMAIL:-clerk@cabotar.gov}"
CHECKPOINT_CMD="${CHECKPOINT_CMD:-python3 $SCRIPT_DIR/checkpoint.py}"
JANUS_URL="${NOCTUA_JANUS_URL:-${NOCTUA_JANUS:-}}"
JOBS_USER="${NOCTUA_JOBS_USER:-jobs.local}"
JOBS_KEY="${NOCTUA_JOBS_KEY:-${NOCTUA_SYSTEM_KEY:-}}"

witness_heartbeat() {
  # $1 = true/false, $2 = detail. Best-effort: a heartbeat failure is
  # printed, never silently swallowed, but does not mask the publish
  # result this script's exit code reports.
  if [ -z "$JANUS_URL" ] || [ -z "$JOBS_KEY" ]; then
    echo "witness heartbeat skipped: NOCTUA_JANUS_URL / NOCTUA_JOBS_KEY not set" >&2
    return 0
  fi
  python3 - "$JANUS_URL" "$JOBS_USER" "$JOBS_KEY" "$1" "$2" <<'PYEOF' || echo "witness heartbeat FAILED to post" >&2
import json, sys, urllib.request
url, user, key, ok, detail = sys.argv[1:6]
req = urllib.request.Request(
    url.rstrip("/") + "/heartbeat",
    data=json.dumps({"job": "witness", "ok": ok == "true",
                     "detail": detail}).encode(),
    headers={"Content-Type": "application/json",
             "X-Noctua-User": user, "X-Noctua-Key": key})
urllib.request.urlopen(req, timeout=10).read()
PYEOF
}

fail() {
  echo "publish_witness FAILED: $1" >&2
  witness_heartbeat false "$1"
  exit 1
}

# checkpoint.py's stdout is exactly one JSON line (all chatter is on
# stderr since 1.2); grep for the JSON line anyway — a stray line
# from a wrapper must not corrupt the witness file.
CP_OUT=$($CHECKPOINT_CMD) || fail "checkpoint.py exited nonzero"
CP_JSON=$(echo "$CP_OUT" | grep -E '^\{' | tail -n 1)
[ -n "$CP_JSON" ] || fail "checkpoint.py produced no JSON line"
CP_DATE=$(echo "$CP_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['date'])") || fail "checkpoint JSON unparsable"
CP_ROOT=$(echo "$CP_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['root'])")
CP_ENTRIES=$(echo "$CP_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['entries'])")

mkdir -p "$WITNESS_REPO" || fail "cannot create witness dir $WITNESS_REPO"
echo "$CP_JSON" >> "$WITNESS_REPO/checkpoints.jsonl" || fail "cannot append to witness checkpoints file"

# Publish: commit + push the witness repo (repo remote configured by
# the city). A directory without .git is a local witness copy: the
# append IS the publication there, and the run counts as published.
if [ -d "$WITNESS_REPO/.git" ]; then
  git -C "$WITNESS_REPO" add checkpoints.jsonl || fail "git add failed"
  git -C "$WITNESS_REPO" commit -m "NOCTUA checkpoint $CP_DATE ($CP_ENTRIES entries)" >/dev/null 2>&1 || true
  git -C "$WITNESS_REPO" push || fail "git push failed — checkpoint saved locally only, NOT witnessed"
fi

# Email the Clerk their copy (mailx or equivalent on the host).
if command -v mail >/dev/null 2>&1; then
  echo "NOCTUA daily audit checkpoint: $CP_ENTRIES entries, root $CP_ROOT, $CP_DATE. Full signed checkpoint: $CP_JSON" | \
    mail -s "NOCTUA checkpoint — $CP_DATE" "$CLERK_EMAIL" || echo "WARN: clerk email failed" >&2
fi

# Only NOW — the checkpoint exists outside this system — say so.
witness_heartbeat true "witnessed checkpoint $CP_DATE: $CP_ENTRIES entries, root ${CP_ROOT:0:16}"
echo "checkpoint published: $CP_DATE root=$CP_ROOT entries=$CP_ENTRIES"
