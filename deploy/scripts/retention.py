#!/usr/bin/env python3
"""NOCTUA retention job — run nightly (cron / systemd timer / compose cron).

Deletes non-hit reads older than RETENTION_DAYS (14 in the Cabot pilot)
and resolved hit records older than HOLD_DAYS (30), and writes the deletion
into the Sentinel chain so the shredder itself is audited. If this job stops
running, the missing RETENTION_DELETE entries are visible in the log —
silence is detectable.

Legal holds (Janus POST /holds) override the timers at the hit layer:
a resolved hit tied to an active hold — by case number or by hit id — is
skipped and counted as held_skipped in the output and the chain entry.
Reads carry no case link, so holds cannot attach to them; reads delete
by age alone. That is deliberate: SS 12-12-1804(b) destruction duties bite
on investigative material, which is what the hit/evidence layer is. The
plate-free outcomes table is NEVER touched here — SS 12-12-1805 requires
the six-month aggregates to be preserved 18 months.

Env: NOCTUA_DB (default /data/noctua.db), RETENTION_DAYS=14, HOLD_DAYS=30.
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "janus"))
from sentinel import Chain  # noqa: E402

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
RET = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD = int(os.environ.get("HOLD_DAYS", "30"))


def cutoff(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def main():
    db = sqlite3.connect(DB)
    # secure_delete zeroes freed content; the VACUUM after deletion rewrites
    # the file so deleted rows are not recoverable from free pages. Without
    # both, "deleted" plate data is still on disk (AI council finding,
    # Nov. 23, 2026). Backups must follow the same retention schedule --
    # see the deploy README; a backup that keeps everything forever makes
    # this job theater.
    db.execute("PRAGMA secure_delete = ON")
    # The holds table is created by Janus; create-if-missing so this job
    # can run standalone against a fresh database without crashing.
    db.execute(
        """CREATE TABLE IF NOT EXISTS holds(
             id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, ref TEXT,
             reason TEXT, placed_by TEXT, placed_ts TEXT,
             released_by TEXT, released_ts TEXT, active INTEGER DEFAULT 1)""")
    db.commit()
    case_holds = {r[0] for r in db.execute(
        "SELECT ref FROM holds WHERE active=1 AND scope='case'")}
    hit_holds = set()
    for (r,) in db.execute("SELECT ref FROM holds WHERE active=1 AND scope='hit'"):
        try:
            hit_holds.add(int(r))
        except (TypeError, ValueError):
            pass
    n_reads = db.execute("DELETE FROM reads WHERE ts < ?", (cutoff(RET),)).rowcount
    # Resolved hits past the hold window are deletion candidates — except
    # the ones under an active legal hold, which are skipped and counted.
    candidates = db.execute(
        "SELECT id, case_no FROM hits WHERE status != 'PENDING' "
        "AND decided_ts IS NOT NULL AND decided_ts < ?",
        (cutoff(HOLD),)).fetchall()
    held_ids = {hid for hid, cno in candidates
                if hid in hit_holds or (cno and cno in case_holds)}
    n_hits = 0
    for hid, _cno in candidates:
        if hid not in held_ids:
            db.execute("DELETE FROM hits WHERE id=?", (hid,))
            n_hits += 1
    held_skipped = len(held_ids)
    db.commit()
    if n_reads or n_hits:
        db.execute("VACUUM")
        db.commit()
    chain = Chain(DB)
    entry = chain.append("RETENTION_DELETE",
                         {"reads_deleted": n_reads, "hits_deleted": n_hits,
                          "held_skipped": held_skipped,
                          "retention_days": RET, "hold_days": HOLD})
    print(f"retention: {n_reads} reads, {n_hits} hits deleted, "
          f"{held_skipped} held skipped; audit seq {entry['seq']}")


if __name__ == "__main__":
    main()
