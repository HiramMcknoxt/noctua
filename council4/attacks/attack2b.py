"""Batch 2b: the two batch-2 attacks whose first harness was wrong —
A6b (the sandbox's global git config signs commits, so the failure has
to be the realistic one: a server with no git identity) and A9 (needs a
real Janus database so the registry checks are not noise)."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import T, req, finding


def a6b_witness_commit_fails():
    W = lib.instance("wit2", 19121)
    W.start()
    try:
        lib.heartbeat_all(W.port)
        req(W.port, "POST", "/heartbeat", lib.JOB,
            {"job": "witness", "ok": False, "detail": "reset"})
        iso = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
        remote = os.path.join(T.WORK, "wr.git")
        clone = os.path.join(T.WORK, "wclone")
        env0 = dict(os.environ, **iso)
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True,
                       env=env0)
        subprocess.run(["git", "clone", "-q", remote, clone], check=True,
                       env=env0, capture_output=True)
        open(os.path.join(clone, "README"), "w").write("witness\n")
        subprocess.run(["git", "-C", clone, "add", "README"], check=True,
                       env=env0)
        subprocess.run(["git", "-C", clone, "-c", "user.name=setup", "-c",
                        "user.email=setup@city.example", "commit", "-qm",
                        "init"], check=True, env=env0)
        subprocess.run(["git", "-C", clone, "push", "-q", "-u", "origin",
                        "HEAD"], check=True, env=env0, capture_output=True)
        # the cron user has NO git identity (the common server state)
        env = dict(os.environ, **iso, NOCTUA_DB=W.db,
                   NOCTUA_AUDIT_KEY=T.AUDIT_KEY, NOCTUA_JANUS_URL=W.url,
                   NOCTUA_JOBS_USER=lib.JOB,
                   NOCTUA_JOBS_KEY=lib.KEYS[lib.JOB], WITNESS_REPO=clone)
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                  "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
            env.pop(k, None)
        r = subprocess.run(["bash", os.path.join(lib.SCRIPTS,
                                                 "publish_witness.sh")],
                           env=env, capture_output=True, text=True,
                           timeout=120)
        log = subprocess.run(["git", "--git-dir", remote, "log",
                              "--oneline"], env=env0, capture_output=True,
                             text=True).stdout.strip().splitlines()
        status = subprocess.run(["git", "-C", clone, "status", "--short"],
                                env=env0, capture_output=True,
                                text=True).stdout.strip()
        h = T.health(W.port)
        finding("A6b on a server with no git identity, `git commit` fails, "
                "`|| true` hides it, the push is a no-op, the script exits "
                "0 and /health shows the witness job ok — the remote never "
                "got the checkpoint",
                r.returncode == 0 and len(log) == 1
                and h["jobs"]["witness"]["ok"] is True,
                {"exit": r.returncode, "remote_log": log,
                 "uncommitted_in_clone": status,
                 "stdout": r.stdout.strip()[-120:],
                 "witness_job": h["jobs"]["witness"]["detail"]})
    finally:
        W.stop()


def a9_sentinel_audit_newest_only():
    X = lib.instance("sa2", 19122)
    X.start()
    try:
        lib.heartbeat_all(X.port)
        for i in range(20):
            req(X.port, "GET", "/hits", lib.DET)   # chains HITS_VIEW
    finally:
        X.stop()
    cp1 = T.run_checkpoint(X.db)
    X.start()
    try:
        for i in range(10):
            req(X.port, "GET", "/hits", lib.DET)
        lib.heartbeat_all(X.port)
    finally:
        X.stop()
    # an insider rewrites an OLD entry (seq 10, covered by cp1) and
    # recomputes every later hash so the chain itself verifies
    c = sqlite3.connect(X.db)
    rows = c.execute("SELECT seq, payload FROM audit ORDER BY seq"
                     ).fetchall()
    prev = "GENESIS"
    changed = None
    for seq, payload in rows:
        if seq == 10:
            doc = json.loads(payload)
            doc["by"] = "someone.else"
            payload = json.dumps(doc, sort_keys=True,
                                 separators=(",", ":"))
            changed = doc
        h = hashlib.sha256((prev + "|" + payload).encode()).hexdigest()
        c.execute("UPDATE audit SET payload=?, prev=?, hash=? WHERE seq=?",
                  (payload, prev, h, seq))
        prev = h
    c.commit()
    c.close()
    cp2_run = subprocess.run(
        [sys.executable, os.path.join(lib.SCRIPTS, "checkpoint.py")],
        env=dict(os.environ, NOCTUA_DB=X.db, NOCTUA_AUDIT_KEY=T.AUDIT_KEY),
        capture_output=True, text=True, timeout=60)
    r = lib.run_script("sentinel_audit.py", {}, args=("--db", X.db))
    rep = json.loads(r.stdout)
    fails = [c_ for c_ in rep["checks"] if c_["status"] == "fail"]
    anchor = [c_ for c_ in rep["checks"] if c_["name"] == "anchor consistency"]
    finding("A9 after a rewrite of OLD history, checkpoint.py signs the "
            "rewritten root without checking anything, and sentinel_audit "
            "(DB mode) reports ZERO failures — it anchors only the newest "
            "checkpoint and never reads the older one that disagrees",
            cp2_run.returncode == 0 and rep["summary"]["fail"] == 0,
            {"rewritten_entry_10": changed,
             "older_checkpoint": (cp1["entries"], cp1["root"][:16]),
             "summary": rep["summary"], "anchor": anchor,
             "fails": fails})
    # contrast: Janus's own startup anchor does catch it (S6 fixed there)
    X.start()
    try:
        h = T.health(X.port)
        finding("A9b (contrast) Janus's startup anchor flags the same "
                "rewrite — the fix landed in janus.py, not in the audit "
                "tool or in checkpoint.py",
                h["anchor_mismatch"] is True,
                {"anchor_detail": h["degraded"]["anchor_detail"]})
    finally:
        X.stop()


if __name__ == "__main__":
    a6b_witness_commit_fails()
    a9_sentinel_audit_newest_only()
    lib.summary()
