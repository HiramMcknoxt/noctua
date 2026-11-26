#!/usr/bin/env python3
"""NOCTUA signed checkpoint — run daily (scripts/publish_witness.sh).

Computes {date, ts, root, entries} from the Sentinel chain — (seq,
hash) read in ONE query inside ONE transaction, so the pair can
never straddle a concurrent append — signs the canonical payload
with the agency's Ed25519 SIGNING key (S7: NOT the audit key; the
plate-HMAC secret never leaves the box and never signs anything),
appends the signed checkpoint as a JSON line to the checkpoints
file, and prints EXACTLY that one JSON line on stdout. Everything
else this script has to say (heartbeats, warnings) goes to stderr,
so publish_witness.sh can parse stdout mechanically.

The signature is only as independent as the key's custody: if the
signing key lives on the same server as the chain, the checkpoint
detects tampering by outsiders and by an admin who does not hold
the key, but NOT a fully privileged insider who holds both. The
intended custody is Clerk/auditor-side. Shipping default: key on
the server, which is honest about its limits (see the deploy
README's hardening section).

Heartbeat: after writing the checkpoint, the job POSTs
/heartbeat {job: "checkpoint"} to Janus as the 'jobs' role when
NOCTUA_JANUS_URL and NOCTUA_JOBS_KEY are set. A checkpoint job that
silently stops is itself an alarm condition at GET /health.

Env: NOCTUA_DB (default /data/noctua.db), NOCTUA_CHECKPOINTS
     (default <DB>.checkpoints.jsonl), NOCTUA_AGENCY,
     NOCTUA_JANUS_URL, NOCTUA_JOBS_USER (default jobs.local),
     NOCTUA_JOBS_KEY.
"""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
AGENCY = os.environ.get("NOCTUA_AGENCY", "THIS-AGENCY")


def heartbeat(ok, detail):
    url = os.environ.get("NOCTUA_JANUS_URL") or os.environ.get(
        "NOCTUA_JANUS")
    key = os.environ.get("NOCTUA_JOBS_KEY") or os.environ.get(
        "NOCTUA_SYSTEM_KEY")
    if not url or not key:
        print("heartbeat skipped: NOCTUA_JANUS_URL / NOCTUA_JOBS_KEY "
              "not set — the dead-man switch is not wired for this "
              "job", file=sys.stderr)
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
        print(f"heartbeat sent (ok={ok})", file=sys.stderr)
    except Exception as e:
        print(f"heartbeat FAILED ({e}) — the checkpoint was written, "
              f"but Janus could not record it", file=sys.stderr)


def _refuse_if_rewritten(db, out_path):
    """P11/A9 + 1.2.2: never sign over a disagreement. If ANY
    EXISTING checkpoint disagrees with the chain as it now stands —
    the hash at its entry count is not its root, or the chain no
    longer has its entries — the history under it was rewritten,
    and a fresh signature would bless the rewrite. Refuse, unless a
    two-key anchor acceptance has already recorded THIS checkpoint
    (Janus's meta anchor_accepted_ids): acceptance is the human
    decision that supersedes the refusal, and after it a new
    checkpoint is exactly the recovery path. Returns a refusal
    message or None."""
    if not os.path.exists(out_path):
        return None
    cps = []
    try:
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    cps.append(json.loads(line))
    except (OSError, ValueError):
        return "existing checkpoints file is unreadable"
    valid = [c for c in cps if isinstance(c.get("entries"), int)]
    if not valid:
        return None
    accepted = set()
    try:
        row = db.execute("SELECT value FROM meta WHERE key="
                         "'anchor_accepted_ids'").fetchone()
        if row:
            accepted = {tuple(x) for x in json.loads(row[0])}
    except Exception:
        accepted = set()
    # 1.2.2: EVERY checkpoint is checked, not only the newest —
    # 1.2.1's newest-only refusal let a rewrite of OLD history
    # (with the newest checkpoint left consistent) be signed over
    # (round 5, Gemini N9). sentinel_audit and Janus's startup
    # check already anchor every checkpoint; the signer now does
    # too.
    for cp in sorted(valid, key=lambda c: c["entries"]):
        if (cp["entries"], cp.get("root")) in accepted:
            continue
        if cp["entries"] == 0:
            if cp.get("root") != "GENESIS":
                return ("a checkpoint claims GENESIS height with "
                        "a non-GENESIS root")
            continue
        row = db.execute("SELECT hash FROM audit WHERE seq=?",
                         (cp["entries"],)).fetchone()
        if row is None:
            return ("the chain no longer has the %d entries a "
                    "checkpoint attests — refusing to sign over a "
                    "truncation" % cp["entries"])
        if row[0] != cp.get("root"):
            return ("the chain hash at entry %d does not equal "
                    "that checkpoint's root — history under the "
                    "checkpoint was rewritten; refusing to sign"
                    % cp["entries"])
    return None


def main():
    try:
        # Read-only: a checkpoint must never mutate the database it
        # anchors. (seq, hash) come from ONE query inside ONE
        # transaction — the root and the entry count are the same
        # instant's facts or they are neither.
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT seq, hash FROM audit ORDER BY seq DESC "
                "LIMIT 1").fetchone()
            out_path = os.environ.get("NOCTUA_CHECKPOINTS",
                                      DB + ".checkpoints.jsonl")
            refusal = _refuse_if_rewritten(db, out_path)
            db.execute("COMMIT")
        finally:
            db.close()
        if refusal:
            print("CHECKPOINT_REFUSED: %s" % refusal, file=sys.stderr)
            heartbeat(False, "checkpoint refused: %s" % refusal)
            return 1
        if row:
            entries, root = row[0], row[1]
        else:
            entries, root = 0, "GENESIS"
        now = datetime.now(timezone.utc)
        cp = {"date": now.strftime("%Y-%m-%d"),
              "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "root": root, "entries": entries, "agency": AGENCY}
        # Ed25519 signing keypair beside the DB (created by Janus at
        # first boot; created here if this job runs first).
        priv, pub = sentinel.ensure_signing_key(DB)
        cp["sig_alg"] = "ed25519"
        cp["sig"] = sentinel.sign_bytes(
            priv, sentinel.checkpoint_signed_bytes(cp))
        cp["pubkey"] = open(pub).read()
        out = os.environ.get("NOCTUA_CHECKPOINTS",
                             DB + ".checkpoints.jsonl")
        with open(out, "a") as f:
            f.write(json.dumps(cp, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as exc:
        heartbeat(False, "checkpoint failed: %s" % exc)
        print("checkpoint FAILED: %s" % exc, file=sys.stderr)
        return 1
    # stdout carries the checkpoint JSON line and NOTHING else.
    print(json.dumps(cp, sort_keys=True))
    heartbeat(True, "checkpoint %s: %d entries, root %s"
              % (cp["date"], entries, root[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
