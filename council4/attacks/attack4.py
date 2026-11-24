"""Batch 4: availability. A large chain, a partner's chain_auditor
calling /audit/verify, and a hot-list read arriving at the same time."""
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import T, req, finding

N = int(os.environ.get("R4_CHAIN_N", "600000"))


def build_chain(dbp, n):
    c = sqlite3.connect(dbp)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS audit(
        seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
        kind TEXT NOT NULL, payload TEXT NOT NULL, prev TEXT NOT NULL,
        hash TEXT NOT NULL)""")
    prev = "GENESIS"
    batch = []
    ts = "2026-06-01T00:00:00Z"
    for i in range(n):
        payload = json.dumps(
            {"ts": ts, "kind": "QUERY", "user": "det.okafor",
             "type": "tier2 search", "tier": 2,
             "case_hash": "%064x" % i, "why_hash": "%064x" % (i * 7),
             "plate_ref": "pref:%024x" % i, "result_count": i % 9,
             "window_hours": 24.0}, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha256((prev + "|" + payload).encode()).hexdigest()
        batch.append((ts, "QUERY", payload, prev, h))
        prev = h
        if len(batch) == 50000:
            c.executemany("INSERT INTO audit(ts,kind,payload,prev,hash) "
                          "VALUES(?,?,?,?,?)", batch)
            batch = []
    if batch:
        c.executemany("INSERT INTO audit(ts,kind,payload,prev,hash) "
                      "VALUES(?,?,?,?,?)", batch)
    c.commit()
    c.close()


def timed(fn):
    t0 = time.time()
    out = fn()
    return time.time() - t0, out


def main():
    X = lib.instance("big", 19151)
    t_build, _ = timed(lambda: build_chain(X.db, N))
    X.start()
    try:
        p = X.port
        req(p, "POST", "/hotlist", lib.DET,
            {"plate": "BIG100", "state": "AR", "category": "stolen",
             "case": "2027-1014"})
        base, _ = timed(lambda: req(p, "POST", "/reads", lib.ING,
                                    {"plate": "BIG100", "state": "AR",
                                     "cam": "CAM-01"}))
        t_verify, (s, b) = timed(lambda: req(p, "GET", "/audit/verify",
                                             lib.CA))
        box = {}

        def verify():
            box["v"] = timed(lambda: req(p, "GET", "/audit/verify", lib.CA))
        th = threading.Thread(target=verify)
        th.start()
        time.sleep(0.05)
        t_read, (rs, rb) = timed(lambda: req(p, "POST", "/reads", lib.ING,
                                             {"plate": "BIG100",
                                              "state": "AR",
                                              "cam": "CAM-02"}))
        th.join()
        # /health computes verify_detached while holding DBLOCK (cached
        # 60 s); the first call after the cache expires stalls everyone
        box2 = {}

        def health():
            box2["h"] = timed(lambda: req(p, "GET", "/health", lib.SUP))
        th = threading.Thread(target=health)
        th.start()
        time.sleep(0.05)
        t_read2, _ = timed(lambda: req(p, "POST", "/reads", lib.ING,
                                       {"plate": "BIG100", "state": "AR",
                                        "cam": "CAM-03"}))
        th.join()
        finding("A18 a partner's chain_auditor calling /audit/verify (an "
                "uncached full-chain verify on the shared connection under "
                "the global lock) stalls ingest for the whole verify; "
                "/health's 'detached' verify also runs under that lock",
                t_read > 10 * base and t_read > 0.5,
                {"chain_entries": N + 3,
                 "build_s": round(t_build, 1),
                 "verify_alone_s": round(t_verify, 2),
                 "verify_ok": b.get("ok"),
                 "hotlist_read_baseline_s": round(base, 3),
                 "hotlist_read_during_verify_s": round(t_read, 2),
                 "read_status": rs,
                 "health_call_s": round(box2["h"][0], 2),
                 "read_during_health_s": round(t_read2, 2),
                 "bridge_forward_timeout_s": 10})
    finally:
        X.stop()


if __name__ == "__main__":
    main()
    lib.summary()
