"""Round-4 attack harness: reuses the builders' own helpers (Instance,
req, sign, post_receipt, run_checkpoint) from a pristine copy of the
1.2 tree, so every attack runs against exactly the shipped code."""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

TREE = os.environ.get("NOCTUA12_TREE", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "attack", "janus12"))
TREE = os.path.abspath(TREE)
sys.path.insert(0, os.path.join(TREE, "tests"))
import run_tests as T  # noqa: E402  (builders' helpers, unmodified)

SCRIPTS = os.path.join(TREE, "scripts")
JANUS = os.path.join(TREE, "janus.py")
DET, PAT, SUP, SUP2, AUD, CA, ING, JOB = (T.DET, T.PAT, T.SUP, T.SUP2,
                                          T.AUD, T.CA, T.ING, T.JOB)
KEYS = T.KEYS
req = T.req
RESULTS = []


def finding(name, confirmed, evidence=""):
    """confirmed=True means the DEFECT reproduced."""
    RESULTS.append((name, confirmed, evidence))
    tag = "CONFIRMED " if confirmed else "NOT REPRODUCED "
    print(tag + name + ((" :: " + str(evidence)[:600]) if evidence else ""))
    sys.stdout.flush()


def ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def ahead(**kw):
    return (datetime.now(timezone.utc) + timedelta(**kw)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def chain_entries(port, user=AUD, limit=1000):
    s, b = req(port, "GET", "/audit?limit=%d" % limit, user)
    assert s == 200, (s, b)
    return b["entries"]


def heartbeat_all(port):
    for job in T.JOBS:
        s, b = req(port, "POST", "/heartbeat", JOB,
                   {"job": job, "ok": True, "detail": "r4"})
        assert s == 200, b


def run_script(name, env_extra, args=(), timeout=120):
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, name),
                           *args], env=env, capture_output=True,
                          text=True, timeout=timeout)


def instance(name, port, **kw):
    inst = T.Instance(name, port, **kw)
    return inst


def db(inst):
    return sqlite3.connect(inst.db)


def open_gate(B, A, agency="agency-a"):
    """Open B's share gate for partner `agency` the way the builders'
    suite does: register A's pubkey, a signed passing audit by B's
    auditor, B checkpoint, A's signed receipt for it."""
    s, b = req(B.port, "POST", "/compact/partners", SUP,
               {"agency": agency, "endpoint": A.url,
                "pubkey_pem": T.pub_pem(A.db), "agreement_ref": "MOU"})
    assert s == 201, b
    s, b = T.post_audit_result(B.port, B.db, agency, True)
    assert s == 201, b
    cp = T.run_checkpoint(B.db, B.url)
    s, b = T.post_receipt(B.port, A.db, agency, cp)
    assert s == 201, b
    return cp


def summary():
    print("\n==== %d attacks, %d confirmed ====" % (
        len(RESULTS), sum(1 for _n, c, _e in RESULTS if c)))
    for n, c, _e in RESULTS:
        print(("  [X] " if c else "  [ ] ") + n)
