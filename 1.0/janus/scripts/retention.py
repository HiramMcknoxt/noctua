#!/usr/bin/env python3
"""NOCTUA retention job — run nightly (cron / systemd timer / compose cron).

Deletes non-hit reads older than RETENTION_DAYS (14 in the Cabot pilot)
and resolved hit records older than HOLD_DAYS (30), and writes the deletion
into the Sentinel chain so the shredder itself is audited. If this job stops
running, the missing RETENTION_DELETE entries — and, in 1.0, the stale
heartbeat at GET /health — are visible: silence is detectable, and
scripts/alert_check.py turns it into a nonzero exit.

Legal holds (Janus POST /holds) override the timers at the hit layer:
a resolved hit tied to an active hold — by case number or by hit id — is
skipped and counted as held_skipped in the output and the chain entry.
Reads carry no case link, so holds cannot attach to them; reads delete
by age alone. That is deliberate: SS 12-12-1804(b) destruction duties bite
on investigative material, which is what the hit/evidence layer is. The
plate-free outcomes table is NEVER touched here — SS 12-12-1805 requires
the six-month aggregates to be preserved 18 months.

1.0 addition — the evidence gate: a resolved hit that has been exported
as evidence (POST /evidence/export) is NOT deleted until prosecutor
sign-off is recorded (POST /evidence/release), whatever the timers say;
such hits are skipped and counted as evidence_skipped. A verified hit
that was never exported follows the v0.9 resolved-hit timer — exporting
is the act that moves a hit into the evidence lifecycle, and a hit
nobody exported has no chain-of-custody bundle to protect. That reading
of INTERFACE.md's "never a flat timer" is stated here rather than
assumed silently; the Commission can tighten it by policy (export every
verified hit) without a code change.

1.0 addition — heartbeat: on completion (and on failure) the job POSTs
/heartbeat to Janus with the system key, when NOCTUA_JANUS_URL and
NOCTUA_SYSTEM_KEY are set. If they are not set, it prints that the
heartbeat was skipped and why — the job still did its work, but the
dead-man switch only works when the wiring exists. If Janus itself is
down the heartbeat cannot land; that is what alert_check.py's
"janus unreachable" branch is for.

Env: NOCTUA_DB (default /data/noctua.db), RETENTION_DAYS=14, HOLD_DAYS=30,
     NOCTUA_JANUS_URL (e.g. http://127.0.0.1:8080), NOCTUA_SYSTEM_USER
     (default ingest.local), NOCTUA_SYSTEM_KEY.
"""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sentinel import Chain  # noqa: E402

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
RET = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD = int(os.environ.get("HOLD_DAYS", "30"))


def cutoff(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def heartbeat(ok, detail):
    url = os.environ.get("NOCTUA_JANUS_URL")
    key = os.environ.get("NOCTUA_SYSTEM_KEY")
    if not url or not key:
        print("heartbeat skipped: NOCTUA_JANUS_URL / NOCTUA_SYSTEM_KEY "
              "not set — the dead-man switch is not wired for this job")
        return
    req = urllib.request.Request(
        url.rstrip("/") + "/heartbeat",
        data=json.dumps({"job": "retention", "ok": ok,
                         "detail": detail}).encode(),
        headers={"Content-Type": "application/json",
                 "X-Noctua-User": os.environ.get("NOCTUA_SYSTEM_USER",
                                                 "ingest.local"),
                 "X-Noctua-Key": key})
    try:
        urllib.request.urlopen(req, timeout=10).read()
        print(f"heartbeat sent (ok={ok})")
    except Exception as e:  # Janus down etc. — report, don't mask the job
        print(f"heartbeat FAILED ({e}) — the job ran, but Janus could "
              f"not record it; alert_check will show retention overdue")


def run():
    db = sqlite3.connect(DB)
    # secure_delete zeroes freed content; the VACUUM after deletion rewrites
    # the file so deleted rows are not recoverable from free pages. Without
    # both, "deleted" plate data is still on disk (AI council finding,
    # Nov. 23, 2026). Backups must follow the same retention schedule --
    # see scripts/backup.py; a backup that keeps everything forever makes
    # this job theater.
    db.execute("PRAGMA secure_delete = ON")
    # Tables created by Janus; create-if-missing so this job can run
    # standalone against a fresh database without crashing.
    db.execute(
        """CREATE TABLE IF NOT EXISTS holds(
             id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, ref TEXT,
             reason TEXT, placed_by TEXT, placed_ts TEXT,
             released_by TEXT, released_ts TEXT, active INTEGER DEFAULT 1)""")
    db.execute(
        """CREATE TABLE IF NOT EXISTS evidence(
             hit_id INTEGER PRIMARY KEY, export_ts TEXT, export_by TEXT,
             manifest_hash TEXT, bundle TEXT, prosecutor_name TEXT,
             prosecutor_date TEXT, released_by TEXT, released_ts TEXT)""")
    db.commit()
    case_holds = {r[0] for r in db.execute(
        "SELECT ref FROM holds WHERE active=1 AND scope='case'")}
    hit_holds = set()
    for (r,) in db.execute("SELECT ref FROM holds WHERE active=1 AND scope='hit'"):
        try:
            hit_holds.add(int(r))
        except (TypeError, ValueError):
            pass
    # Exported-but-unreleased hits are evidence, not records on a timer.
    evidence_blocked = {r[0] for r in db.execute(
        "SELECT hit_id FROM evidence WHERE export_ts IS NOT NULL "
        "AND released_ts IS NULL")}
    n_reads = db.execute("DELETE FROM reads WHERE ts < ?", (cutoff(RET),)).rowcount
    # Resolved hits past the hold window are deletion candidates — except
    # the ones under an active legal hold or in the evidence lifecycle,
    # which are skipped and counted.
    candidates = db.execute(
        "SELECT id, case_no FROM hits WHERE status != 'PENDING' "
        "AND decided_ts IS NOT NULL AND decided_ts < ?",
        (cutoff(HOLD),)).fetchall()
    held_ids = {hid for hid, cno in candidates
                if hid in hit_holds or (cno and cno in case_holds)}
    ev_ids = {hid for hid, _c in candidates if hid in evidence_blocked}
    n_hits = 0
    for hid, _cno in candidates:
        if hid not in held_ids and hid not in ev_ids:
            db.execute("DELETE FROM hits WHERE id=?", (hid,))
            n_hits += 1
    held_skipped = len(held_ids - ev_ids)
    evidence_skipped = len(ev_ids)
    db.commit()
    if n_reads or n_hits:
        db.execute("VACUUM")
        db.commit()
    chain = Chain(DB)
    entry = chain.append("RETENTION_DELETE",
                         {"reads_deleted": n_reads, "hits_deleted": n_hits,
                          "held_skipped": held_skipped,
                          "evidence_skipped": evidence_skipped,
                          "retention_days": RET, "hold_days": HOLD})
    msg = (f"retention: {n_reads} reads, {n_hits} hits deleted, "
           f"{held_skipped} held skipped, {evidence_skipped} evidence "
           f"skipped; audit seq {entry['seq']}")
    print(msg)
    return msg


def main():
    try:
        msg = run()
    except Exception as e:
        heartbeat(False, f"retention job failed: {e}")
        raise
    heartbeat(True, msg)


if __name__ == "__main__":
    main()
