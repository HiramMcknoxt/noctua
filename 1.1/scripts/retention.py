#!/usr/bin/env python3
"""Retention job — NOCTUA Janus 1.1. Deletes expired records and
writes a heartbeat. Run nightly by cron (see INSTALL.md).

  reads     older than RETENTION_DAYS (default 14)      -> deleted
  hits      older than HOLD_DAYS (default 30)           -> deleted,
            EXCEPT hits with an evidence bundle that has not
            been released (prosecutor sign-off OR a confirmed
            disposition), and hits under a legal hold
  case_searches / tier3_requests older than 14 days     -> purged
            (item 20, see below)

The chain keeps plate_ref + counts for every query, so deleting the
derived tables loses nothing the audit needs.

Item 20 choices, per table:
  * case_searches rows are DELETED outright after 14 days — the
    CASE_FLAG chain entries already carry the pattern signal, and the
    table itself is only a counter.
  * tier3_requests rows are kept for the workflow/statistics record
    (they are the Tier 3 paper trail), but at 14 days the plaintext
    plate_fragment is REPLACED by its frag_ref (the same keyed HMAC
    the chain uses) — the fragment text leaves the database while the
    row's status/history survives. Rows are never deleted by this job.

Retention values come from the SAME env names Janus reads
(RETENTION_DAYS / HOLD_DAYS) so the two can never drift (item 17).

Item 10: the evidence gate honors BOTH § 12-12-1804(b) exits — a
prosecutor sign-off (evidence.released_ts) or a CONFIRMED disposition
(evidence.disp_confirmed_ts) releases the data for deletion.

This job authenticates to Janus as the 'jobs' role (item 8): set
NOCTUA_JOBS_USER / NOCTUA_JOBS_KEY (falling back to the retired
NOCTUA_SYSTEM_* names for one migration window). After purging it
runs a WAL checkpoint + truncate (item 14).
"""
import hashlib
import hmac as hmac_mod
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

DB = os.environ.get("NOCTUA_DB", os.path.join(HERE, "..", "data",
                                              "janus.db"))
JANUS = os.environ.get("NOCTUA_JANUS", "http://127.0.0.1:8471")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD_DAYS = int(os.environ.get("HOLD_DAYS", "30"))
PURGE_DAYS = 14  # item 20: derived-data purge horizon (fixed by policy)
JOBS_USER = os.environ.get("NOCTUA_JOBS_USER",
                           os.environ.get("NOCTUA_SYSTEM_USER",
                                          "jobs.local"))
JOBS_KEY = os.environ.get("NOCTUA_JOBS_KEY",
                          os.environ.get("NOCTUA_SYSTEM_KEY", ""))
AUDIT_KEY = os.environ.get("NOCTUA_AUDIT_KEY", "")


def frag_ref(fragment):
    """Same keyed HMAC Janus uses for fragments — needs the audit key.
    Without it the fragment scrub cannot run; the job says so and
    skips (never guesses a key)."""
    if not AUDIT_KEY:
        return None
    return "pref:" + hmac_mod.new(
        AUDIT_KEY.encode(), ("FRAG|" + fragment).encode(),
        hashlib.sha256).hexdigest()


def heartbeat(ok, detail):
    if not JOBS_KEY:
        print("retention: no NOCTUA_JOBS_KEY — heartbeat skipped "
              "(Janus will show the retention job as overdue)")
        return
    body = json.dumps({"job": "retention", "ok": ok,
                       "detail": detail}).encode()
    req = urllib.request.Request(
        JANUS + "/heartbeat", data=body, method="POST",
        headers={"X-Noctua-User": JOBS_USER, "X-Noctua-Key": JOBS_KEY,
                 "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:
        print("retention: heartbeat failed:", exc)


def main():
    now = datetime.now(timezone.utc)
    db = sqlite3.connect(DB, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    cols = {r[1] for r in db.execute("PRAGMA table_info(evidence)")}
    disp_col = "disp_confirmed_ts" if "disp_confirmed_ts" in cols \
        else "NULL"
    purged = {}
    try:
        cutoff = (now - timedelta(days=RETENTION_DAYS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        purged["reads"] = db.execute(
            "DELETE FROM reads WHERE ts < ?", (cutoff,)).rowcount

        hold_cut = (now - timedelta(days=HOLD_DAYS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        # Item 10: a hit is deletable when it is old AND (no evidence
        # bundle OR the bundle was released by EITHER exit) AND no
        # active hold covers it. An unreleased bundle keeps the hit.
        # Holds are scope/ref rows: a hit is held by an active hold
        # with scope='hit' and ref=<hit id>, or scope='case' and
        # ref=<the hit's case number>.
        purged["hits"] = db.execute(
            "DELETE FROM hits WHERE ts < ? AND id NOT IN "
            "(SELECT hit_id FROM evidence WHERE released_ts IS NULL "
            "AND %s IS NULL) AND NOT EXISTS (SELECT 1 FROM holds "
            "WHERE active=1 AND released_ts IS NULL AND "
            "((scope='hit' AND ref = CAST(hits.id AS TEXT)) OR "
            "(scope='case' AND ref = hits.case_no)))"
            % disp_col, (hold_cut,)).rowcount

        purge_cut = (now - timedelta(days=PURGE_DAYS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        # Item 20: case_searches — delete outright (the table is
        # keyed by day; rows older than the horizon go).
        purge_day = (now - timedelta(days=PURGE_DAYS)).strftime(
            "%Y-%m-%d")
        purged["case_searches"] = db.execute(
            "DELETE FROM case_searches WHERE day < ?",
            (purge_day,)).rowcount
        db.execute("DELETE FROM case_flags WHERE day < ?",
                   (purge_day,))
        # Item 20: tier3_requests — keep the row, scrub the fragment.
        scrubbed = 0
        t3cols = {r[1] for r in db.execute(
            "PRAGMA table_info(tier3_requests)")}
        if "plate_fragment" in t3cols:
            rows = db.execute(
                "SELECT id, plate_fragment FROM tier3_requests WHERE "
                "created_ts < ? AND plate_fragment NOT LIKE 'pref:%'",
                (purge_cut,)).fetchall()
            for rid, frag in rows:
                ref = frag_ref(frag or "")
                if ref is None:
                    print("retention: NOCTUA_AUDIT_KEY not set — "
                          "tier3 fragment scrub skipped (%d rows "
                          "waiting)" % len(rows))
                    break
                db.execute("UPDATE tier3_requests SET "
                           "plate_fragment=? WHERE id=?", (ref, rid))
                scrubbed += 1
        purged["tier3_fragments_scrubbed"] = scrubbed

        db.commit()
        db.execute("VACUUM")
        # Item 14: after the purge + vacuum, fold the WAL back and
        # truncate it so the -wal file cannot grow without bound.
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.commit()
    except Exception as exc:
        db.close()
        heartbeat(False, "purge failed: %s" % exc)
        raise
    db.close()

    detail = ("purged %d reads, %d hits, %d case_searches; scrubbed "
              "%d tier3 fragments" % (purged["reads"], purged["hits"],
                                      purged["case_searches"],
                                      purged["tier3_fragments_scrubbed"]))
    print("retention:", detail)
    try:
        chain = sentinel.Chain(DB)
        chain.append("RETENTION_PURGE", {
            "reads": purged["reads"], "hits": purged["hits"],
            "case_searches": purged["case_searches"],
            "tier3_fragments_scrubbed":
                purged["tier3_fragments_scrubbed"],
            "retention_days": RETENTION_DAYS, "hold_days": HOLD_DAYS})
    except Exception as exc:
        print("retention: chain append failed:", exc)
    heartbeat(True, detail)


if __name__ == "__main__":
    main()
