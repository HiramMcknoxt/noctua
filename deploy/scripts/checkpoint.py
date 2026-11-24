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

Env: NOCTUA_DB (default /data/noctua.db), NOCTUA_AUDIT_KEY,
     NOCTUA_CHECKPOINTS (default <DB>.checkpoints.jsonl).
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")


def _audit_key():
    """Same resolution as janus.py: env, else the per-install key file."""
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    kf = DB + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip()
    k = secrets.token_hex(32)
    with open(kf, "w") as f:
        f.write(k)
    os.chmod(kf, 0o600)
    return k


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


if __name__ == "__main__":
    main()
