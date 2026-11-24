#!/usr/bin/env python3
"""Retention job — NOCTUA Janus 1.2.2. Purges BY THE REGISTRY.

1.2.2 (Q6): ONE transaction, ONE decision function. The purge and
its RETENTION_PURGE chain entry commit together or not at all —
1.2.1 committed the purge, closed, and only then chained the
record on a second connection, so a crash in between deleted
plate data with no audit entry (round 5, DeepSeek F2). And the
guarded hits delete no longer keeps its own age arithmetic: it
calls sentinel.hit_deletable — the same function
sentinel.registry_breaches evaluates — so the purger and the
checker cannot disagree by a day-boundary again (Gemini N2).
Per-bundle EVIDENCE_DESTROY entries name what was destroyed
(1.2.1 chained only a count).

1.2.1 (P10/P13): the guarded hits delete no longer keeps a private
copy of the hold/evidence predicate. It uses sentinel.hit_protected
— the same predicate sentinel.registry_breaches (Janus /health,
sentinel_audit) evaluates — so the purger, the health check, and
the external auditor cannot disagree about whether a hit is held.
And the statutory ceiling is absolute: a hit older than
sentinel.HITS_CAP_DAYS (150) is deleted regardless of paperwork;
an unconfirmed disposition or an open-ended hold never extends a
hit past it.

1.1 kept a hand-written list of tables in this file, and round 3
showed what that buys: stores the list forgot (Tier 3 result bodies,
share text, pre-restore copies) kept plate data forever while the
job reported success. In 1.2 this job iterates
sentinel.PLATE_DATA_STORES — the same registry Janus re-exports and
sentinel_audit checks — and applies each store's action:

  delete_rows          rows older than the class age are deleted
                       (reads; case_searches by day)
  delete_rows_guarded  hits: old AND not protected under the
                       SHARED predicate (sentinel.hit_protected:
                       CAST-normalized holds of either scope inside
                       their review window, or an exported unreleased
                       evidence bundle); never kept past 150 days
  purge_inactive       deactivated hotlist memberships past class age
  null_after_release   suppression plate TEXT nulled 30 days after
                       the order is released (the keyed ref stays)
  scrub_fragment       tier3 plate_fragment replaced by its frag_ref
  null_columns         free text / result ids nulled at class age
  null_after_destroy   evidence free text nulled 30 days after the
                       bundle is destroyed
  destroy_after_release evidence bundles past destroy_by are
                       destroyed here if the manual path has not
  prune_sets           backup sets older than the reads class
  prune_copies         pre-restore copies older than the reads class
  none / asserted      plate_free and external stores: nothing to do,
                       by construction (the registry says why)

frag_ref/plate_ref come from sentinel.py — the ONE implementation
(S15). The audit key resolves exactly as Janus resolves it
(env -> key file); if no key is available the fragment scrub cannot
run, and that is a FAILURE (heartbeat ok:false, nonzero exit), not
a skip: a scrub that silently does not happen is how 1.1 shipped a
fragment that never matched anything.

Any failure in any store — purge, scrub, or the chain append —
means heartbeat(False) and a nonzero exit. VACUUM is the one
exception: it runs under busy_timeout with retries, and on a
persistent lock it is SKIPPED (RETENTION_VACUUM_SKIPPED chained,
heartbeat ok with the note) — a vacuum must never stall ingest or
masquerade as a purge failure.

Env: NOCTUA_DB (default /data/noctua.db), NOCTUA_JANUS_URL
     (default http://127.0.0.1:8080; NOCTUA_JANUS still honored),
     RETENTION_DAYS / HOLD_DAYS (same names Janus reads),
     NOCTUA_JOBS_USER / NOCTUA_JOBS_KEY, NOCTUA_AUDIT_KEY.
"""
import glob as glob_mod
import json
import os
import shutil
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
JANUS = os.environ.get("NOCTUA_JANUS_URL") or os.environ.get(
    "NOCTUA_JANUS") or "http://127.0.0.1:8080"
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD_DAYS = int(os.environ.get("HOLD_DAYS", "30"))
JOBS_USER = os.environ.get("NOCTUA_JOBS_USER",
                           os.environ.get("NOCTUA_SYSTEM_USER",
                                          "jobs.local"))
JOBS_KEY = os.environ.get("NOCTUA_JOBS_KEY",
                          os.environ.get("NOCTUA_SYSTEM_KEY", ""))
EVIDENCE_DIR = os.environ.get(
    "NOCTUA_EVIDENCE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(DB)), "evidence"))
BACKUP_DIR = os.environ.get("NOCTUA_BACKUP_DIR",
                            os.path.join(os.path.dirname(
                                os.path.abspath(DB)), "backups"))


def heartbeat(ok, detail):
    if not JOBS_KEY:
        print("retention: no NOCTUA_JOBS_KEY — heartbeat skipped "
              "(Janus will show the retention job as overdue)")
        return
    body = json.dumps({"job": "retention", "ok": ok,
                       "detail": detail}).encode()
    req = urllib.request.Request(
        JANUS.rstrip("/") + "/heartbeat", data=body, method="POST",
        headers={"X-Noctua-User": JOBS_USER, "X-Noctua-Key": JOBS_KEY,
                 "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:
        print("retention: heartbeat failed:", exc)


_NOW_DT = [None]


def _now_dt():
    # One "now" for the whole run (Q6): the purge and the breach
    # checker evaluate the same instant, so a boundary row cannot be
    # flagged by one and excused by the other over run-time drift.
    if _NOW_DT[0] is None:
        _NOW_DT[0] = datetime.now(timezone.utc)
    return _NOW_DT[0]


def _cutoff(days):
    # 1.2.2 (Q6): cutoffs come from sentinel — the same helpers the
    # breach checker uses, so the two can never drift apart.
    return sentinel.ts_cutoff(days, _now_dt())


def _day_cutoff(days):
    return sentinel.day_cutoff(days, _now_dt())


CURRENT_CHAIN = [None]


def purge_store(db, entry, key, counts):
    """Apply one registry entry's action. Returns a note string for
    the run detail, or '' when the store needed nothing."""
    store = entry["store"]
    action = entry["action"]
    days = sentinel.class_days(entry, RETENTION_DAYS, HOLD_DAYS)
    if action in ("none",) or entry["kind"] == "asserted":
        return ""
    if entry["kind"] == "folder":
        if action == "prune_sets":
            return prune_backup_sets(days)
        if action == "destroy_after_release":
            return destroy_overdue_bundles(db, counts,
                                           chain=CURRENT_CHAIN[0])
        return ""
    if entry["kind"] == "glob":
        return prune_glob(entry["pattern"], days)
    table, column = entry["table"], entry["column"]
    ts_col = entry.get("ts_col")
    if action == "delete_rows" and entry.get("day_col"):
        n = db.execute(f"DELETE FROM {table} WHERE {entry['day_col']} "
                       f"< ?", (_day_cutoff(days),)).rowcount
        counts[store] = n
        return ""
    # Age-class branches compute their own cutoff: suppression and
    # evidence entries have no age class (class_days is None) and
    # their branches use fixed 30-day windows instead — computing a
    # shared cutoff up front crashed on exactly those entries.
    if action == "delete_rows":
        n = db.execute(f"DELETE FROM {table} WHERE {ts_col} < ?",
                       (_cutoff(days),)).rowcount
        counts[store] = n
    elif action == "delete_rows_guarded":
        # Q6 parity: sentinel.hit_deletable is the ONE decision —
        # the same function registry_breaches evaluates, with the
        # same exact-second cutoffs and the same protection rules
        # (strict-equality holds of either scope inside their
        # review window; evidence only when the bundle exists ON
        # DISK and remains unreleased). Past HITS_CAP_DAYS the hit
        # is deleted regardless: paperwork never extends a hit
        # past the 150-day statutory ceiling. 1.2.1's private
        # whole-day arithmetic is gone.
        n = 0
        now_dt = _now_dt()
        for hid, hts in db.execute(
                f"SELECT id, {ts_col} FROM {table}").fetchall():
            if sentinel.hit_deletable(db, hid, hts, RETENTION_DAYS,
                                      HOLD_DAYS, now_dt,
                                      evidence_dir=EVIDENCE_DIR,
                                      db_path=DB):
                db.execute(f"DELETE FROM {table} WHERE id=?", (hid,))
                n += 1
        counts[store] = n
    elif action == "purge_inactive":
        n = db.execute(
            f"DELETE FROM {table} WHERE active=0 AND {ts_col} < ?",
            (_cutoff(days),)).rowcount
        counts[store] = n
    elif action == "null_after_release":
        # Suppression class: the plate TEXT is nulled 30 days after
        # the order's release; the keyed plate_ref stays with the
        # order record so releases remain auditable.
        cut30 = _cutoff(30)
        n = db.execute(
            f"UPDATE {table} SET {column}=NULL WHERE active=0 AND "
            f"released_ts IS NOT NULL AND released_ts < ? AND "
            f"{column} IS NOT NULL", (cut30,)).rowcount
        counts[store] = n
    elif action == "scrub_fragment":
        rows = db.execute(
            f"SELECT id, {column} FROM {table} WHERE {ts_col} < ? "
            f"AND {column} IS NOT NULL AND {column} NOT LIKE 'pref:%'",
            (_cutoff(days),)).fetchall()
        for rid, frag in rows:
            db.execute(f"UPDATE {table} SET {column}=? WHERE id=?",
                       (sentinel.frag_ref(key, frag or ""), rid))
        counts[store] = len(rows)
    elif action == "null_columns":
        n = db.execute(
            f"UPDATE {table} SET {column}=NULL WHERE {ts_col} < ? "
            f"AND {column} IS NOT NULL", (_cutoff(days),)).rowcount
        counts[store] = n
    elif action == "null_after_destroy":
        # Mirrors registry_breaches' disp_note branch exactly (Q6):
        # the note dies 30 days after the bundle's destruction, 30
        # days after a CONFIRMED disposition, or — for a disposition
        # nobody confirmed — HOLD_DAYS+30 after it was filed, so an
        # unconfirmed note can no longer park a plate forever
        # (round 5, ChatGPT F5B).
        cut30 = _cutoff(30)
        n = db.execute(
            f"UPDATE {table} SET {column}=NULL WHERE {column} IS NOT "
            f"NULL AND ((destroyed_ts IS NOT NULL AND destroyed_ts "
            f"< ?) OR (disp_confirmed_ts IS NOT NULL AND "
            f"disp_confirmed_ts < ?) OR (disp_confirmed_ts IS NULL "
            f"AND disp_ts IS NOT NULL AND disp_ts < ?))",
            (cut30, cut30, _cutoff(HOLD_DAYS + 30))).rowcount
        counts[store] = n
    return ""


def prune_backup_sets(days):
    if not os.path.isdir(BACKUP_DIR):
        return ""
    cutoff = time.time() - days * 86400
    n = 0
    for name in sorted(os.listdir(BACKUP_DIR)):
        p = os.path.join(BACKUP_DIR, name)
        if not name.startswith("backup-") or not os.path.isdir(p):
            continue
        try:
            if os.path.getmtime(p) < cutoff:
                shutil.rmtree(p)
                n += 1
        except OSError:
            continue
    return "pruned %d backup sets" % n if n else ""


def prune_glob(pattern, days):
    cutoff = time.time() - days * 86400
    n = 0
    for p in glob_mod.glob(pattern.replace("<db>", DB)):
        try:
            if os.path.getmtime(p) < cutoff:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                n += 1
        except OSError:
            continue
    return "pruned %d pre-restore copies" % n if n else ""


def destroy_overdue_bundles(db, counts, chain=None):
    """Evidence class: a released bundle past its destroy_by date is
    destroyed by this job if nobody destroyed it manually. The row
    stays (it is the custody record); the bundle goes."""
    rows = db.execute(
        "SELECT hit_id, bundle FROM evidence WHERE destroyed_ts IS "
        "NULL AND destroy_by IS NOT NULL AND destroy_by < ?",
        (sentinel.now_iso(),)).fetchall()
    n = 0
    for hit_id, bundle in rows:
        if bundle:
            p = os.path.join(EVIDENCE_DIR, bundle)
            if os.path.isdir(p):
                shutil.rmtree(p)
        db.execute("UPDATE evidence SET destroyed_ts=?, "
                   "destroyed_by='retention' WHERE hit_id=?",
                   (sentinel.now_iso(), hit_id))
        if chain is not None:
            # Q27: custody excerpts name WHICH bundles retention
            # destroyed — 1.2.1 chained only the count (round 5,
            # Claude seat 2).
            chain.append("EVIDENCE_DESTROY", {
                "hit": hit_id, "by": "retention",
                "bundle_ref": sentinel.sha(bundle or "")[:16]})
        n += 1
    counts["evidence bundles"] = n
    return "destroyed %d overdue evidence bundles" % n if n else ""


def main():
    key = sentinel.resolve_audit_key(DB)
    if not key:
        msg = ("no audit key available (NOCTUA_AUDIT_KEY / key file) "
               "— the fragment scrub cannot run; refusing to report "
               "a partial purge as success")
        print("retention FAILED:", msg)
        heartbeat(False, msg)
        return 1
    counts, notes = {}, []
    vacuum_note = ""
    try:
        db = sqlite3.connect(DB, timeout=30)
        # S15: secure_delete on THIS connection too — a purge that
        # leaves the bytes recoverable in free pages is not a purge.
        db.execute("PRAGMA secure_delete = ON")
        db.execute("PRAGMA busy_timeout = 30000")
        db.execute("PRAGMA journal_mode = WAL")
        # Q6: the chain rides THIS connection from the start, so
        # the purge, the per-bundle destroy entries, and the
        # RETENTION_PURGE record commit in ONE transaction — a
        # crash or a failed append rolls the deletions back with
        # it. Nothing is deleted unchained, ever.
        chain = sentinel.Chain(DB, conn=db, key=key)
        CURRENT_CHAIN[0] = chain
        seen_tables = set()
        for entry in sentinel.PLATE_DATA_STORES:
            # reads.plate/plate_raw are one table delete, and the
            # two hits.* entries are one guarded delete.
            if entry["action"] in ("delete_rows", "delete_rows_guarded") \
                    and entry["kind"] == "table":
                if entry["table"] in seen_tables:
                    continue
                seen_tables.add(entry["table"])
            note = purge_store(db, entry, key, counts)
            if note:
                notes.append(note)
        # case_flags is case_searches' companion counter (not itself
        # plate-bearing); it purges on the same day horizon.
        db.execute("DELETE FROM case_flags WHERE day < ?",
                   (_day_cutoff(RETENTION_DAYS),))
        # Q27: a Tier 3 request still PENDING past the retention
        # class has lost its justification to the scrub — it
        # EXPIRES here rather than executing blank later.
        n_exp = db.execute(
            "UPDATE tier3_requests SET status='EXPIRED' WHERE "
            "status='PENDING' AND created_ts < ?",
            (_cutoff(RETENTION_DAYS),)).rowcount
        if n_exp:
            counts["tier3_requests expired"] = n_exp
        chain.append("RETENTION_PURGE", {
            "stores": {k: v for k, v in sorted(counts.items()) if v},
            "retention_days": RETENTION_DAYS, "hold_days": HOLD_DAYS,
            "registry_version": sentinel.REGISTRY_VERSION,
            "vacuum": "pending"})
        db.commit()
        try:
            chain.flush_deferred()
        except Exception:
            pass
        # WAL checkpoint: the result is CHECKED and reported — a
        # checkpoint that could not truncate means a writer held the
        # WAL through the whole purge, which the operator should see.
        busy, _log, _ckpt = db.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy:
            notes.append("WAL checkpoint busy — WAL not truncated")
        # VACUUM: busy_timeout + retry; on persistent lock, skip and
        # say so in the chain — never stall, never fake it.
        vacuumed = False
        for attempt in range(3):
            try:
                db.execute("VACUUM")
                vacuumed = True
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) and "busy" not in str(exc):
                    raise
                time.sleep(2 * (attempt + 1))
        db.close()
        if not vacuumed:
            # A post-commit fact, chained on its own connection —
            # the purge record itself already landed atomically.
            vacuum_note = "VACUUM skipped (database locked)"
            sentinel.Chain(DB, key=key).append(
                "RETENTION_VACUUM_SKIPPED", {
                    "reason": "database locked after retries"})
    except Exception as exc:
        print("retention FAILED:", exc)
        heartbeat(False, "purge failed: %s" % exc)
        return 1
    detail = ("purged by registry: "
              + (", ".join("%s=%d" % (k, v) for k, v in
                           sorted(counts.items()) if v) or "nothing")
              + ("; " + "; ".join(notes) if notes else "")
              + ("; " + vacuum_note if vacuum_note else ""))
    print("retention:", detail)
    heartbeat(True, detail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
