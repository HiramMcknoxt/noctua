#!/usr/bin/env python3
# VESPER · the evening watch
"""Hotlist sync — NOCTUA 1.2.1 (S5; P2 sweep repair). The job
/health monitors, shipped.

/health has watched a 'hotlist_sync' heartbeat since the job was
first specified, but no such script existed — the dead-man switch
watched a job that could never run. This is that job:

  * Every hotlist membership whose expires_ts has passed is
    DEACTIVATED, and each deactivation is chained (HOTLIST_EXPIRED)
    with the plate's keyed ref — expiry is an audit event, not a
    silent edit. (Janus also deactivates lazily at match time; this
    sweep is what makes expiry happen on schedule rather than on
    next sighting.)
  * The heartbeat is the freshness signal: ok:true only when the
    sweep completed; any failure heartbeats ok:false and exits
    nonzero.

In a deployment with an upstream list feed (a state hotlist file, a
LPR vendor export), the fetch belongs in this job, above the sweep:
pull, diff, POST memberships to /hotlist as the supervisor, then
sweep. NOCTUA ships no vendor integration — the feed format is the
deploying agency's — so the shipped job is the sweep + heartbeat,
and says so.

Env: NOCTUA_DB (default /data/noctua.db), NOCTUA_JANUS_URL,
     NOCTUA_JOBS_USER / NOCTUA_JOBS_KEY, NOCTUA_AUDIT_KEY.
"""
import json
import os
import sqlite3
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
JANUS = os.environ.get("NOCTUA_JANUS_URL") or os.environ.get(
    "NOCTUA_JANUS") or "http://127.0.0.1:8080"
JOBS_USER = os.environ.get("NOCTUA_JOBS_USER",
                           os.environ.get("NOCTUA_SYSTEM_USER",
                                          "jobs.local"))
JOBS_KEY = os.environ.get("NOCTUA_JOBS_KEY",
                          os.environ.get("NOCTUA_SYSTEM_KEY", ""))


def heartbeat(ok, detail):
    if not JOBS_KEY:
        print("hotlist_sync: no NOCTUA_JOBS_KEY — heartbeat skipped "
              "(Janus will show the job as overdue)")
        return
    req = urllib.request.Request(
        JANUS.rstrip("/") + "/heartbeat",
        data=json.dumps({"job": "hotlist_sync", "ok": ok,
                         "detail": detail}).encode(),
        method="POST",
        headers={"X-Noctua-User": JOBS_USER, "X-Noctua-Key": JOBS_KEY,
                 "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:
        print("hotlist_sync: heartbeat failed:", exc)


def main():
    try:
        key = sentinel.resolve_audit_key(DB)
        if not key:
            raise RuntimeError(
                "no audit key available — cannot chain expiries "
                "with plate refs")
        db = sqlite3.connect(DB, timeout=30)
        db.execute("PRAGMA busy_timeout = 30000")
        # P2: "" means NO expiry — a row whose expires_ts is '' (or
        # NULL) is open-ended and the sweep must never touch it.
        # 1.2 stored '' for no-expiry rows and its sweep matched
        # them ('' IS NOT NULL and '' < now), deactivating every
        # open-ended stolen-vehicle entry the first night the job
        # ran; retention then deleted the rows. Janus 1.2.1 stores
        # NULL going forward and migrates '' at boot; this predicate
        # is the second line of defense for databases that have not
        # booted 1.2.1 yet.
        rows = db.execute(
            "SELECT plate, state, list_source, case_no FROM "
            "hotlist_members WHERE active=1 AND expires_ts IS NOT "
            "NULL AND expires_ts <> '' AND expires_ts < ?",
            (sentinel.now_iso(),)).fetchall()
        # P2: the updates and their HOTLIST_EXPIRED chain entries
        # commit in ONE shared transaction (Chain over this
        # connection, the pattern retention.py uses) — 1.2 committed
        # the deactivations first and chained afterwards, so a crash
        # between the two left expiries nobody recorded.
        # 1.2.3 (Gemini M10): the Chain carries the audit key —
        # without it the scrubber's replacements are bare SHA-256
        # hashes, unlinkable to the keyed plate_refs the rest of
        # the chain carries.
        chain = sentinel.Chain(DB, conn=db, key=key)
        for plate, state, source, case_no in rows:
            db.execute(
                "UPDATE hotlist_members SET active=0 WHERE plate=? "
                "AND state=? AND list_source=? AND case_no IS ?",
                (plate, state, source, case_no))
            chain.append("HOTLIST_EXPIRED", {
                "plate_ref": sentinel.plate_ref(key, plate),
                "list_source": source,
                "case_hash": sentinel.case_ref(key, case_no or "")})
        db.commit()
        chain.flush_deferred()
        db.close()
        active = sqlite3.connect(f"file:{DB}?mode=ro", uri=True) \
            .execute("SELECT COUNT(*) FROM hotlist_members WHERE "
                     "active=1").fetchone()[0]
        detail = ("swept %d expired memberships; %d active memberships "
                  "remain" % (len(rows), active))
        print("hotlist_sync:", detail)
        heartbeat(True, detail)
        return 0
    except Exception as exc:
        print("hotlist_sync FAILED:", exc)
        heartbeat(False, "sync failed: %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
