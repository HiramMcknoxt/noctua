"""Batch 5: the round-3 forced change's acceptance behaviours
(orphaned bundle, expired backup set), case_hash reversal by a
partner's chain_auditor, and the HOLD_DAYS ceiling."""
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import T, req, finding


def a35_orphan_bundle_and_backup():
    O = lib.instance("orph", 19161)
    O.start()
    try:
        lib.heartbeat_all(O.port)
    finally:
        O.stop()
    ev = os.path.join(O.dir, "evidence", "hit-77-20261001T000000Z")
    os.makedirs(ev)
    with open(os.path.join(ev, "reads.json"), "w") as f:
        json.dump([{"plate": "ORF123", "cam": "CAM-04",
                    "ts": "2026-10-01T00:00:00Z"}], f)
    bk = os.path.join(O.dir, "backups", "backup-20261001T000000Z")
    os.makedirs(bk)
    open(os.path.join(bk, "noctua.db"), "wb").write(b"x" * 64)
    old = time.time() - 40 * 86400
    for p in (os.path.join(ev, "reads.json"), ev,
              os.path.join(bk, "noctua.db"), bk):
        os.utime(p, (old, old))
    O.start()
    try:
        lib.heartbeat_all(O.port)
        h = T.health(O.port)
    finally:
        O.stop()
    r = lib.run_script("sentinel_audit.py", {}, args=("--db", O.db))
    rep = json.loads(r.stdout)
    ev_chk = [c for c in rep["checks"] if "evidence bundles" in c["name"]
              or c["name"].endswith("backups")]
    finding("A35 round-3 forced-change acceptance: a 40-day-old ORPHANED "
            "evidence bundle (on disk, no evidence row) is seen by nothing "
            "— /health and sentinel_audit both pass it; the expired backup "
            "set is caught by /health but only WARNs in sentinel_audit",
            "backups" in h["degraded"]["retention_breach"]
            and rep["summary"]["fail"] == 0,
            {"health_retention_breach": h["degraded"]["retention_breach"],
             "sentinel_audit_summary": rep["summary"],
             "sentinel_audit_checks": ev_chk})


def a36_case_hash_reversal():
    P = lib.instance("chash", 19162)
    P.start()
    try:
        p = P.port
        s, b = req(p, "GET", "/search?plate=ABC&case=2027-1031"
                   "&justification=dv+followup&tier=2", lib.DET)
        assert s == 200, b
        s, b = req(p, "GET", "/audit/range?from_seq=1&to_seq=50", lib.CA)
        targets = {}
        for e in b["entries"]:
            f = json.loads(e["payload"])
            if f.get("kind") == "QUERY":
                targets[f["case_hash"]] = (f["user"], f["ts"])
        t0 = time.time()
        found = {}
        for year in range(2020, 2031):
            for n in range(10000):
                c = "%d-%04d" % (year, n)
                h = hashlib.sha256(c.encode()).hexdigest()
                if h in targets:
                    found[c] = targets[h]
        dt = time.time() - t0
        finding("A36 a partner's chain_auditor recovers the case number "
                "behind every case_hash in seconds (unsalted SHA-256 over "
                "a ~10^5 space), next to the officer's username and time",
                bool(found), {"recovered": found,
                              "seconds": round(dt, 2)})
    finally:
        P.stop()


def a37_hold_days_ceiling():
    env = dict(os.environ)
    H = lib.instance("hd", 19163, env_extra={"HOLD_DAYS": "400"})
    # 1.2.2 RE-AIM: HOLD_DAYS is capped at the 150-day statutory
    # ceiling AT BOOT (janus.py refuses to start) — a refused
    # start naming HOLD_DAYS is the defended outcome. CONFIRMED
    # only if the boot succeeds (original assertions below) or
    # fails for an unrelated reason.
    try:
        H.start()
    except Exception:
        log = ""
        try:
            log = open(os.path.join(H.dir, "server.log")).read()
        except OSError:
            pass
        finding("A37 HOLD_DAYS has no ceiling: HOLD_DAYS=400 boots, a "
                "300-day-old hit (plate, camera, time) survives retention, "
                "/health is ok, and the SYSTEM entry does not record "
                "hold_days at all",
                "HOLD_DAYS" not in log,
                {"boot": "refused at startup", "log_tail": log[-300:]})
        return
    try:
        h = T.health(H.port)
        s, b = req(H.port, "POST", "/hotlist", lib.DET,
                   {"plate": "HDX100", "state": "AR", "category": "warrant",
                    "case": "2027-1014"})
        s, b = req(H.port, "POST", "/reads", lib.ING,
                   {"plate": "HDX100", "state": "AR", "cam": "CAM-01"})
        import sqlite3
        c = sqlite3.connect(H.db)
        c.execute("UPDATE hits SET ts=?", (lib.ago(days=300),))
        c.commit()
        c.close()
        lib.heartbeat_all(H.port)
        r = lib.run_script("retention.py", {
            "NOCTUA_DB": H.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
            "HOLD_DAYS": "400", "NOCTUA_JANUS_URL": H.url,
            "NOCTUA_JOBS_USER": lib.JOB, "NOCTUA_JOBS_KEY": lib.KEYS[lib.JOB]})
        n = sqlite3.connect(H.db).execute(
            "SELECT COUNT(*) FROM hits").fetchone()[0]
        h = T.health(H.port)
        sysent = [e["fields"] for e in lib.chain_entries(H.port)
                  if e["kind"] == "SYSTEM"]
        finding("A37 HOLD_DAYS has no ceiling: HOLD_DAYS=400 boots, a "
                "300-day-old hit (plate, camera, time) survives retention, "
                "/health is ok, and the SYSTEM entry does not record "
                "hold_days at all", n == 1 and h["ok"] is True,
                {"hits_left": n, "health_ok": h["ok"],
                 "health_hold_days": h["hold_days"],
                 "SYSTEM_fields": sorted(sysent[0].keys()) if sysent
                 else None})
    finally:
        H.stop()


if __name__ == "__main__":
    a35_orphan_bundle_and_backup()
    a36_case_hash_reversal()
    a37_hold_days_ceiling()
    lib.summary()
