#!/usr/bin/env python3
"""NOCTUA signed checkpoint — run daily (scripts/publish_witness.sh).

Computes {date, root, entries} from the Sentinel chain, HMAC-signs the
canonical payload with the audit key, appends the signed checkpoint as a
JSON line to the checkpoints file, and prints it.

The key is resolved exactly as Janus resolves it (NOCTUA_AUDIT_KEY env,
else the .audit_key file next to the database). The signature is only as
independent as the key's custody: if the key lives on the same server as
the chain, the checkpoint detects tampering by outsiders and by an admin
who does not hold the key, but NOT a fully privileged insider who holds
both. The intended custody is Clerk/auditor-side — the checkpoint is
produced by Janus but verified by someone who does not answer to CPD or
to the system administrator. See the deploy README, "Hardening added
Nov. 23, 2026". Shipping default: key on the server, which is honest
about its limits.

1.0 addition — heartbeat: after writing the checkpoint, the job POSTs
/heartbeat {job: "checkpoint"} to Janus with the system key, when
NOCTUA_JANUS_URL and NOCTUA_SYSTEM_KEY are set; otherwise it prints that
the heartbeat was skipped (same wiring rule as scripts/retention.py).
That closes the loop this script exists for: a checkpoint job that
silently stops is itself an alarm condition at GET /health.

1.1: the heartbeat authenticates as the 'jobs' role (item 8) —
NOCTUA_JOBS_USER / NOCTUA_JOBS_KEY, falling back to the retired
NOCTUA_SYSTEM_* names. The key file is created with os.open(..., 0o600)
(item 13), and if the chain already has entries but no key exists
anywhere, this script REFUSES to mint one (item 30) — a fresh key
would silently orphan every plate_ref in the chain.

Env: NOCTUA_DB (default /data/noctua.db), NOCTUA_AUDIT_KEY,
     NOCTUA_CHECKPOINTS (default <DB>.checkpoints.jsonl),
     NOCTUA_JANUS_URL, NOCTUA_JOBS_USER (default jobs.local),
     NOCTUA_JOBS_KEY.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import urllib.request
from datetime import datetime, timezone

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")


def _audit_key():
    """Same resolution as janus.py: env, else the per-install key file.
    Item 30: never mint a key over an existing chain."""
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    kf = DB + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip()
    if os.path.exists(DB):
        db = sqlite3.connect(DB)
        try:
            n = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        except sqlite3.Error:
            n = 0
        db.close()
        if n:
            raise SystemExit(
                "checkpoint: the chain has %d entries but no audit key "
                "exists — refusing to mint one (item 30). Restore the "
                "key from the backup set or set NOCTUA_AUDIT_KEY." % n)
    k = secrets.token_hex(32)
    fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(k)
    return k


def heartbeat(ok, detail):
    url = os.environ.get("NOCTUA_JANUS_URL") or os.environ.get(
        "NOCTUA_JANUS")
    key = os.environ.get("NOCTUA_JOBS_KEY") or os.environ.get(
        "NOCTUA_SYSTEM_KEY")
    if not url or not key:
        print("heartbeat skipped: NOCTUA_JANUS_URL / NOCTUA_JOBS_KEY "
              "not set — the dead-man switch is not wired for this job")
        return
    req = urllib.request.Request(
        url.rstrip("/") + "/heartbeat",
        data=json.dumps({"job": "checkpoint", "ok": ok,
                         "detail": detail}).encode(),
        headers={"Content-Type": "application/json",
                 "X-Noctua-User": os.environ.get(
                     "NOCTUA_JOBS_USER",
                     os.environ.get("NOCTUA_SYSTEM_USER", "jobs.local")),
                 "X-Noctua-Key": key})
    try:
        urllib.request.urlopen(req, timeout=10).read()
        print(f"heartbeat sent (ok={ok})")
    except Exception as e:
        print(f"heartbeat FAILED ({e}) — the checkpoint was written, "
              f"but Janus could not record it")


def main():
    db = sqlite3.connect(DB)
    row = db.execute(
        "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    root = row[0] if row else "GENESIS"
    entries = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {"date": date, "root": root, "entries": entries}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(_audit_key().encode(), canonical.encode(),
                   hashlib.sha256).hexdigest()
    cp = {**payload, "sig": sig}
    out = os.environ.get("NOCTUA_CHECKPOINTS", DB + ".checkpoints.jsonl")
    with open(out, "a") as f:
        f.write(json.dumps(cp, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(cp, sort_keys=True))
    heartbeat(True, f"checkpoint {date}: {entries} entries, "
                    f"root {root[:16]}")


if __name__ == "__main__":
    main()
