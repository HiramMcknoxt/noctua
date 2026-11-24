"""A18 RE-AIMED (1.2.2 verification): the round-5 form of the A18
harm. Claude seat 1's R5-02 showed 1.2.1 computing the chain
verification BEFORE authentication for /health and /audit/verify —
six concurrent ANONYMOUS calls against a 250k-entry chain each
forced a full scan (9-15s, ~180MB apiece). 1.2.2 (Q18) must
authenticate before computing anything, single-flight the refresh,
and serve the stale result meanwhile.

This re-aim doubles the chain to 600,000 entries and fires 12
concurrent anonymous calls (6x /audit/verify, 6x /health). The
defect is REPRODUCED if any anonymous call is answered with
anything but a fast 401, or if an authenticated verify afterwards
does not complete normally.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L

T = L.T
N = 600_000


def anon(port, path, out, idx):
    t0 = time.time()
    try:
        rq = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (port, path), method="GET")
        with urllib.request.urlopen(rq, timeout=30) as r:
            out[idx] = (r.status, time.time() - t0)
    except urllib.error.HTTPError as e:
        out[idx] = (e.code, time.time() - t0)
    except Exception as e:  # timeout / connection failure
        out[idx] = ("ERR:%s" % type(e).__name__, time.time() - t0)


def main():
    G = L.instance("a18-600k", 18093)
    gdb = sqlite3.connect(G.db)
    gdb.execute("CREATE TABLE IF NOT EXISTS audit("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT "
                "NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, "
                "prev TEXT NOT NULL, hash TEXT NOT NULL)")
    prev, batch = "GENESIS", []
    for i in range(N):
        payload = json.dumps(
            {"ts": "2026-06-01T00:00:00Z", "kind": "QUERY",
             "user": "det.okafor", "type": "tier2 search", "tier": 2,
             "case_hash": "%064x" % i, "why_hash": "%064x" % (i * 7),
             "plate_ref": "pref:%024x" % i, "result_count": i % 9,
             "window_hours": 24.0}, sort_keys=True,
            separators=(",", ":"))
        hh = hashlib.sha256((prev + "|" + payload).encode()).hexdigest()
        batch.append(("2026-06-01T00:00:00Z", "QUERY", payload,
                      prev, hh))
        prev = hh
        if len(batch) == 50000:
            gdb.executemany("INSERT INTO audit(ts,kind,payload,prev,"
                            "hash) VALUES(?,?,?,?,?)", batch)
            batch = []
    if batch:
        gdb.executemany("INSERT INTO audit(ts,kind,payload,prev,"
                        "hash) VALUES(?,?,?,?,?)", batch)
    gdb.commit()
    gdb.close()
    with open(G.db + ".audit_key", "w") as f:
        f.write(T.AUDIT_KEY)
    fp = hashlib.sha256(T.AUDIT_KEY.encode()).hexdigest()
    r = subprocess.run([sys.executable, os.path.join(
        L.TREE, "scripts", "provision.py"), "pin-audit-key",
        "--db", G.db, "--fingerprint", fp, "--confirm"],
        env=dict(G.env), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    G.start()
    try:
        paths = ["/audit/verify"] * 6 + ["/health"] * 6
        out = [None] * len(paths)
        threads = [threading.Thread(target=anon,
                                    args=(G.port, p, out, i))
                   for i, p in enumerate(paths)]
        t0 = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        burst_s = time.time() - t0
        bad = [(paths[i], o) for i, o in enumerate(out)
               if not o or o[0] != 401 or o[1] > 3.0]
        # The service must still work for an authenticated caller.
        t1 = time.time()
        s, b = L.req(G.port, "GET", "/audit/verify", L.CA)
        auth_s = time.time() - t1
        auth_ok = (s == 200 and isinstance(b, dict)
                   and b.get("ok") is True)
        reproduced = bool(bad) or not auth_ok
        L.finding(
            "A18", "anonymous concurrent /audit/verify + /health "
            "against a 600k-entry chain force no scan and stall "
            "nothing (Q18 re-aim)", reproduced,
            {"burst_s": round(burst_s, 2),
             "worst_anon_s": max((o[1] for o in out if o),
                                 default=None),
             "statuses": [o[0] for o in out],
             "bad": bad[:4], "auth_verify": (s, round(auth_s, 2),
                                             auth_ok)})
    finally:
        G.stop()


if __name__ == "__main__":
    main()
