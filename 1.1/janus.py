#!/usr/bin/env python3
"""Janus — the NOCTUA front door. Version 1.1.

The ONLY way anything reads or writes NOCTUA data. Stdlib-only Python
service over SQLite, built to the Cabot pilot spec and the NOCTUA
interface spec. 1.1 is the council-round-2 hardening release: every
item below was a confirmed defect or a missing control in 1.0, found by
hostile review and verified against the 1.0 code before it was fixed.

1.1 changes (item numbers are the round-2 finding list):
  1  TEMPORAL WALL: Tier 2 (/search) is limited IN SQL to reads inside
     a contemporaneous window (NOCTUA_TIER2_WINDOW_H, default 24h) of
     server receipt time. Tier 3 (two-key) searches the full store.
  2  Fragments: empty, <3 chars, or containing %/_ are refused on
     /search and every /tier3/* and /share/query path.
  3  Every QUERY chain entry carries plate_ref AND result_count.
  4  GET /hits and GET /hotlist are role-checked and chained
     (HITS_VIEW / HOTLIST_VIEW). Failed authentications chain AUTH_FAIL.
     /audit loses the patrol role; its limit is clamped to [1,1000].
  5  SUPPRESSION REDESIGN (SS 12-12-1808(b)): a suppressed plate is
     EXCLUDED from plain search results for EVERY role — no stub, no
     supervisor view; absence is indistinguishable from no results.
     Disclosure happens only through the match workflow: hits on a
     suppressed plate appear only in GET /suppressed-hits
     (supervisor-only, chained). Suppression is placed against a
     protection-order reference (not a case number); hotlist-add of a
     suppressed plate is refused (SUPPRESSION_CONFLICT); release takes
     the order reference and TWO supervisors.
  6  Chain atomicity + sink spool: see sentinel.py.
  7  STARTUP ANCHOR: at boot the local chain is compared to the newest
     published checkpoint; a mismatch sets anchor_mismatch in /health
     until a supervisor+auditor two-key POST /audit/anchor-accept
     clears it.
  8  Heartbeats: ok must be explicit (missing ok = failure); ok:false
     degrades /health immediately. Roles split: 'ingest' (POST /reads
     only) and 'jobs' (POST /heartbeat only); 'system' is retired.
     Monitored jobs add hotlist_sync and backup. /health cross-checks
     retention directly (oldest read age vs RETENTION_DAYS).
  9  Evidence: export requires a VERIFIED hit whose case matches;
     scope is the hit +/- 1 hour of reads unless a supervisor expands
     with a stated reason; release requires an existing export;
     POST /evidence/destroy deletes the bundle after release and chains
     EVIDENCE_DESTROY. Custody excerpts use an indexed, paged lookup.
 10  SS 12-12-1804(b) both exits: a confirmed no-charges disposition
     releases data for deletion just as a prosecutor sign-off does.
     Holds carry review_by (default +90 days); overdue holds surface
     in /health and /report.
 11  SS 12-12-1805 report: all match counts derive from outcomes plus
     the lists_checked provenance table (every active list is recorded
     per day, so a list with zero matches still appears). Prosecutions
     are NULL until reported; the report says "not yet reported" when
     nothing has been reported. POST /report/compile freezes an
     immutable snapshot.
 12  Hot-list expiry is enforced at ingest (HOTLIST_EXPIRED).
 13  Hardening: binds 127.0.0.1 by default (NOCTUA_BIND overrides);
     auth uses hmac.compare_digest; request bodies cap at 1 MB;
     handler sockets time out; plate_ref and the hot list are keyed by
     (plate, state); the audit-key file is created with os.open 0o600.
 14  Indexes on reads(plate), reads(ts), hits(read_plate), audit(kind);
     WAL journal mode.
 15  Config staleness: a failed users/cases reload chains CONFIG_STALE
     (throttled hourly) and degrades /health; stale >24h fails /search
     and /tier3/* closed with 503.
 16  Backfill vs skew: a camera timestamp >5 min behind receipt is a
     BACKFILL (aggregated to at most one chain entry per camera per
     hour), not skew. CLOCK_SKEW is chained only for future camera
     timestamps (>5s ahead). skew_s is stored on the read.
 17  RETENTION_DAYS / HOLD_DAYS are read from the environment and
     exposed at /health.
 18  One shared case_gate runs on /search, /hotlist, /verify,
     /suppressions (when a case is supplied), /evidence/*, and /holds.
 19  Tier 3: approval re-runs the case gate at execution; results are
     retrieved by the REQUESTER via GET /tier3/results/<id> (chained
     TIER3_RESULT_VIEW); emergency requires auth_basis; a user with an
     unreviewed emergency older than 72h cannot file another.
 20  Derived-data purge (retention job): case_searches rows older than
     14 days are deleted; tier3_requests plate fragments are replaced
     by their frag_ref at day 14 (the rows persist for K8 statistics).
 21  The Compact: scripts/sentinel_audit.py is the standalone audit
     tool; /compact/* + /share/query implement reciprocal-audit data
     sharing — no cross-audit, no data, in both directions, enforced
     by the software. See COMPACT.md.
 23  Service accounts (ingest/jobs) and partner accounts are denied on
     every data-returning endpoint: they move data, they never read it.
 24  /health never reports ok:true while degraded. Degraded includes
     overdue/failed jobs, sink trouble, anchor mismatch, config
     staleness, and any camera silent >6h (per-camera last-seen is
     tracked from ingest).
 25  /audit/verify and /audit/root require auditor or supervisor.
 26  Chain payloads carry plate_ref, counts, and CODED fields only
     (reason codes, basis_type enum). Free text — justifications,
     warrant text, findings prose — lives in the DB tables, never in
     the permanent chain. Sentinel's scrubber enforces this in depth.
 27  Emergency review findings are an enum: justified | unjustified |
     needs_followup. The prose note stays in the DB.
 28  /tier3/pending visibility: detective/patrol see only their own
     requests; supervisors and the auditor see all. Pending-reviews:
     supervisor/auditor, plus a requester may see their own.
 29  /verify decision is an enum (confirm|reject, case-insensitive);
     a non-numeric tier is a 400, never a 500.
 30  Audit-key loss: if the DB holds audit rows but no key is
     available, Janus starts LOCKED — /health reports key_missing and
     every data endpoint answers 503 — instead of minting a new key
     that would silently orphan every plate_ref and suppression.
 31  Log before data: every data-returning endpoint appends its chain
     entry BEFORE the response is sent; if the append fails, the
     request fails.
 32  /holds and /holds/release run the shared case gate.
 33  Request bodies are read and parsed BEFORE the global lock is
     taken; handler sockets carry a timeout, so a stalled client
     cannot freeze the service.
 34  /report includes the K8 emergency-share computation (period share
     + trailing 3-month rolling share vs the pinned 25% threshold).

Concurrency: one shared SQLite connection plus one lock serializing
request handling (DBLOCK). Request bodies are read before the lock and
responses are serialized after it (item 33/14), so the lock covers
database work only. At a 9-camera city's volume that is not a
bottleneck; it removes a class of interleaved-write surprises. Stated
plainly: this is a small-city service, not a horizontal-scale design.
"""
import hashlib
import hmac as hmac_mod
import json
import os
import re
import secrets
import shutil
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from sentinel import Chain, ChainScrubError, now_iso, sha

VERSION = "1.1"
DB_PATH = os.environ.get("NOCTUA_DB", "/data/noctua.db")
USERS_PATH = os.environ.get("NOCTUA_USERS", "/config/users.json")
CASES_PATH = os.environ.get("NOCTUA_CASES", "/config/cases.json")
BIND = os.environ.get("NOCTUA_BIND", "127.0.0.1")
PORT = int(os.environ.get("NOCTUA_PORT", "8080"))
EVIDENCE_DIR = os.environ.get(
    "NOCTUA_EVIDENCE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "evidence"))
CHECKPOINTS_PATH = os.environ.get("NOCTUA_CHECKPOINTS",
                                  DB_PATH + ".checkpoints.jsonl")
AGENCY = os.environ.get("NOCTUA_AGENCY", "THIS-AGENCY")

# Retention clocks (item 17): the same env names retention.py uses.
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD_DAYS = int(os.environ.get("HOLD_DAYS", "30"))
TIER2_WINDOW_H = float(os.environ.get("NOCTUA_TIER2_WINDOW_H", "24"))

# Dead-man thresholds: a required job whose last heartbeat is older
# than this (or missing, or ok:false) makes /health report degraded.
JOB_MAX_AGE_S = {"retention": 26 * 3600, "checkpoint": 26 * 3600,
                 "hotlist_sync": 26 * 3600, "backup": 30 * 3600}
CAMERA_SILENCE_S = 6 * 3600
BODY_CAP = 1_000_000

BASIS_TYPES = ("warrant", "court_order", "other")
REVIEW_FINDINGS = ("justified", "unjustified", "needs_followup")
SERVICE_ROLES = ("ingest", "jobs", "partner")
DATA_ROLES = ("detective", "supervisor", "auditor")


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def _audit_key():
    """(key, locked). Resolve the plate_ref HMAC key: env, else the
    per-install key file (created with os.open 0o600 — no TOCTOU
    window, item 13). If the database already holds audit rows and NO
    key is available, return (None, True): Janus must start LOCKED
    (item 30). Minting a fresh key would silently unmatch every
    suppression and orphan every plate_ref already in the chain — a
    wrong key is worse than no service. Recovery is restore.py with
    the backup set's audit_key, or NOCTUA_AUDIT_KEY from custody."""
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k, False
    kf = DB_PATH + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip(), False
    # No key anywhere. Is there an existing chain it would orphan?
    has_rows = False
    if os.path.exists(DB_PATH):
        try:
            probe = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            has_rows = probe.execute(
                "SELECT COUNT(*) FROM audit").fetchone()[0] > 0
            probe.close()
        except sqlite3.Error:
            has_rows = False  # no audit table yet = fresh install
    if has_rows:
        return None, True
    k = secrets.token_hex(32)
    fd = os.open(kf, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, k.encode())
    finally:
        os.close(fd)
    return k, False


AUDIT_KEY, KEY_LOCKED = _audit_key()


def plate_ref(plate, state=""):
    """Keyed HMAC reference for a full plate, keyed by (plate, state)
    (item 13): the same plate text in two states is two vehicles."""
    msg = f"{plate.upper()}|{(state or '').upper()}"
    return "pref:" + hmac_mod.new(
        AUDIT_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:24]


def frag_ref(frag):
    """Keyed HMAC reference for a search FRAGMENT (not a full plate —
    a different domain, so a fragment ref can never collide with a
    plate ref)."""
    return "pref:" + hmac_mod.new(
        AUDIT_KEY.encode(), ("FRAG|" + frag.upper()).encode(),
        hashlib.sha256).hexdigest()[:24]


def normalize_plate(plate):
    """Strip spaces/hyphens, uppercase — the canonical plate form used
    for suppressions and hot-list entries (item 5)."""
    return re.sub(r"[\s\-]", "", (plate or "")).upper()


# --- users / cases, reloaded on mtime change so provision.py and the
# --- nightly case export take effect without a restart. 1.1 (item
# --- 15): a FAILED reload is no longer silent — it marks the file
# --- stale, chains CONFIG_STALE (throttled to one entry per file per
# --- hour), degrades /health, and past 24h of staleness the search
# --- surface fails closed. A torn users.json must never quietly keep
# --- yesterday's accounts — or yesterday's revocations — in force.
USERS = {}
CASES = set()
_config = {
    "users": {"path": USERS_PATH, "mtime": None, "stale_since": None,
              "last_chain": 0.0},
    "cases": {"path": CASES_PATH, "mtime": None, "stale_since": None,
              "last_chain": 0.0},
}


def _apply_config(name, data):
    global USERS, CASES
    if name == "users":
        USERS = {u["user"]: u for u in data}
    else:
        CASES = set(data["open_cases"])


def _reload_config():
    for name, st in _config.items():
        try:
            m = os.path.getmtime(st["path"])
            if m != st["mtime"]:
                with open(st["path"]) as f:
                    _apply_config(name, json.load(f))
                st["mtime"] = m
                st["stale_since"] = None
        except (OSError, ValueError) as exc:
            if st["stale_since"] is None:
                st["stale_since"] = time.time()
            now = time.time()
            if now - st["last_chain"] > 3600 and not KEY_LOCKED:
                try:
                    chain.append("CONFIG_STALE", {
                        "file": name, "error": type(exc).__name__})
                    st["last_chain"] = now
                except Exception:
                    pass


def config_status():
    out, fail_closed = {}, False
    now = time.time()
    for name, st in _config.items():
        since = st["stale_since"]
        out[name] = {
            "stale": since is not None,
            "stale_since": (datetime.fromtimestamp(
                since, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if since else None)}
        if since and now - since > 24 * 3600:
            fail_closed = True
    out["fail_closed"] = fail_closed
    return out


db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute("PRAGMA busy_timeout = 5000")
db.execute("PRAGMA secure_delete = ON")
db.execute("PRAGMA journal_mode = WAL")
db.executescript(
    """CREATE TABLE IF NOT EXISTS reads(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         plate TEXT, state TEXT, conf REAL, cam_ts TEXT, skew_s INTEGER);
       CREATE TABLE IF NOT EXISTS hotlist(
         plate TEXT, state TEXT, category TEXT, source TEXT,
         list_name TEXT, case_no TEXT, added_by TEXT, added_ts TEXT,
         expires_ts TEXT, active INTEGER DEFAULT 1,
         PRIMARY KEY(plate, state));
       CREATE TABLE IF NOT EXISTS hits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         read_plate TEXT, entry_plate TEXT, state TEXT, list_name TEXT,
         category TEXT, status TEXT DEFAULT 'PENDING', decided_by TEXT,
         case_no TEXT, decided_ts TEXT);
       CREATE TABLE IF NOT EXISTS holds(
         id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, ref TEXT,
         reason TEXT, placed_by TEXT, placed_ts TEXT,
         released_by TEXT, released_ts TEXT, active INTEGER DEFAULT 1,
         review_by TEXT);
       CREATE TABLE IF NOT EXISTS outcomes(
         hit_id INTEGER PRIMARY KEY, list_name TEXT, category TEXT,
         confirmed INTEGER DEFAULT 0, arrest INTEGER DEFAULT 0,
         prosecution INTEGER, updated_by TEXT, updated_ts TEXT,
         hit_ts TEXT);
       CREATE TABLE IF NOT EXISTS case_searches(
         case_no TEXT, day TEXT, frag TEXT,
         PRIMARY KEY(case_no, day, frag));
       CREATE TABLE IF NOT EXISTS case_flags(
         case_no TEXT, day TEXT, PRIMARY KEY(case_no, day));
       CREATE TABLE IF NOT EXISTS suppressions(
         plate_ref TEXT PRIMARY KEY, plate TEXT, state TEXT,
         order_ref TEXT, placed_by TEXT, case_no TEXT, ts TEXT,
         active INTEGER DEFAULT 1, release_requested_by TEXT,
         release_order_ref TEXT);
       CREATE TABLE IF NOT EXISTS counters(
         day TEXT, camera_id TEXT, reads INTEGER DEFAULT 0,
         alerts INTEGER DEFAULT 0, PRIMARY KEY(day, camera_id));
       CREATE TABLE IF NOT EXISTS lists_checked(
         day TEXT, list_name TEXT, PRIMARY KEY(day, list_name));
       CREATE TABLE IF NOT EXISTS heartbeats(
         job TEXT PRIMARY KEY, ts TEXT, ok INTEGER, detail TEXT);
       CREATE TABLE IF NOT EXISTS tier3_requests(
         id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT,
         case_no TEXT, why TEXT, plate_fragment TEXT, auth_basis TEXT,
         basis_type TEXT, status TEXT DEFAULT 'PENDING', created_ts TEXT,
         decided_by TEXT, decided_ts TEXT, emergency INTEGER DEFAULT 0,
         needs_review INTEGER DEFAULT 0, review_finding TEXT,
         review_note TEXT, reviewed_by TEXT, reviewed_ts TEXT,
         results_count INTEGER, results TEXT);
       CREATE TABLE IF NOT EXISTS evidence(
         hit_id INTEGER PRIMARY KEY, export_ts TEXT, export_by TEXT,
         manifest_hash TEXT, bundle TEXT, scope TEXT, expand_reason TEXT,
         prosecutor_name TEXT, prosecutor_date TEXT, released_by TEXT,
         released_ts TEXT, destroyed_ts TEXT, destroyed_by TEXT,
         disp_outcome TEXT, disp_by TEXT, disp_date TEXT, disp_note TEXT,
         disp_posted_by TEXT, disp_confirmed_by TEXT,
         disp_confirmed_ts TEXT);
       CREATE TABLE IF NOT EXISTS report_snapshots(
         id INTEGER PRIMARY KEY AUTOINCREMENT, from_ts TEXT, to_ts TEXT,
         compiled_by TEXT, compiled_ts TEXT, body TEXT);
       CREATE TABLE IF NOT EXISTS partners(
         agency TEXT PRIMARY KEY, endpoint TEXT,
         audit_key_fingerprint TEXT, agreement_ref TEXT,
         status TEXT DEFAULT 'active', added_by TEXT, added_ts TEXT);
       CREATE TABLE IF NOT EXISTS compact_receipts(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT, root TEXT,
         entries INTEGER, sig TEXT, received_ts TEXT);
       CREATE TABLE IF NOT EXISTS compact_audits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT, ok INTEGER,
         detail TEXT, report_hash TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS rotation_schedules(
         id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_start TEXT,
         period_days INTEGER, members_count INTEGER, schedule_hash TEXT,
         schedule TEXT, published_by TEXT, published_ts TEXT);
       CREATE TABLE IF NOT EXISTS meta(
         key TEXT PRIMARY KEY, value TEXT);"""
)
db.commit()

# --- migrations for databases created by 1.0 (fresh 1.1 installs take
# --- the schema above; these ALTERs only fire on the old shapes) -----
def _cols(table):
    return [r[1] for r in db.execute(f"PRAGMA table_info({table})")]


for _t, _c, _d in (
        ("reads", "cam_ts", "TEXT"), ("reads", "skew_s", "INTEGER"),
        ("hits", "state", "TEXT DEFAULT 'AR'"),
        ("hits", "list_name", "TEXT"),
        ("hits", "suppressed", "INTEGER DEFAULT 0"),
        ("holds", "review_by", "TEXT"),
        ("suppressions", "plate", "TEXT"), ("suppressions", "state", "TEXT"),
        ("suppressions", "order_ref", "TEXT"),
        ("suppressions", "release_requested_by", "TEXT"),
        ("suppressions", "release_order_ref", "TEXT"),
        ("tier3_requests", "basis_type", "TEXT"),
        ("tier3_requests", "review_note", "TEXT"),
        ("tier3_requests", "results", "TEXT"),
        ("evidence", "scope", "TEXT"), ("evidence", "expand_reason", "TEXT"),
        ("evidence", "destroyed_ts", "TEXT"),
        ("evidence", "destroyed_by", "TEXT"),
        ("evidence", "disp_outcome", "TEXT"), ("evidence", "disp_by", "TEXT"),
        ("evidence", "disp_date", "TEXT"), ("evidence", "disp_note", "TEXT"),
        ("evidence", "disp_posted_by", "TEXT"),
        ("evidence", "disp_confirmed_by", "TEXT"),
        ("evidence", "disp_confirmed_ts", "TEXT")):
    if _c not in _cols(_t):
        db.execute(f"ALTER TABLE {_t} ADD COLUMN {_c} {_d}")
db.commit()
if "list_name" not in _cols("hotlist"):
    # 1.0 hot list: plate-only primary key, no list provenance. Rebuild
    # keyed by (plate, state); the list label is derived from the old
    # source string with any case number stripped (item 11).
    db.executescript(
        """ALTER TABLE hotlist RENAME TO hotlist_10;
           CREATE TABLE hotlist(
             plate TEXT, state TEXT, category TEXT, source TEXT,
             list_name TEXT, case_no TEXT, added_by TEXT, added_ts TEXT,
             expires_ts TEXT, active INTEGER DEFAULT 1,
             PRIMARY KEY(plate, state));
           INSERT INTO hotlist SELECT plate, state, category, source,
             CASE WHEN source LIKE 'Local%' THEN 'Local agency list'
                  ELSE source END,
             case_no, added_by, added_ts, expires_ts, active
             FROM hotlist_10;
           DROP TABLE hotlist_10;""")
    db.commit()

db.executescript(
    """CREATE INDEX IF NOT EXISTS idx_reads_plate ON reads(plate);
       CREATE INDEX IF NOT EXISTS idx_reads_ts ON reads(ts);
       CREATE INDEX IF NOT EXISTS idx_hits_plate ON hits(read_plate);""")
db.commit()

chain = Chain(DB_PATH)
db.execute("CREATE INDEX IF NOT EXISTS idx_audit_kind ON audit(kind)")
db.commit()
DBLOCK = threading.Lock()

# Catch-all case numbers ("PATROL-2026", a duty log, a test case) are
# how the case gate gets laundered — any case containing one of these
# patterns is rejected and logged. Comma list, case-insensitive
# substring match.
BANNED_CASE_PATTERNS = [p.strip().upper() for p in os.environ.get(
    "NOCTUA_BANNED_CASE_PATTERNS", "PATROL,TEST,ADMIN,DUTY").split(",")
    if p.strip()]

_reload_config()


# ---------------- startup anchor (item 7) ----------------
def _meta_get(key):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(key, value):
    db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
    db.commit()


def anchor_mismatch():
    return _meta_get("anchor_mismatch") is not None


def _startup_anchor_check():
    """Compare the local chain to the newest published checkpoint. A
    chain that no longer contains the checkpoint's root at the
    checkpoint's entry count was rewritten or truncated after the
    checkpoint was published — that fact stays visible in /health
    until a supervisor + auditor two-key accept clears it."""
    if KEY_LOCKED or not os.path.exists(CHECKPOINTS_PATH):
        return
    last = None
    try:
        with open(CHECKPOINTS_PATH) as f:
            for line in f:
                if line.strip():
                    last = json.loads(line)
    except (OSError, ValueError):
        return
    if not last:
        return
    entries, root = last.get("entries"), last.get("root")
    mismatch = True
    if isinstance(entries, int) and root:
        if entries == 0:
            mismatch = root != "GENESIS"
        elif entries <= chain.count():
            mismatch = chain.hash_at_seq(entries) != root
    if mismatch and not anchor_mismatch():
        _meta_set("anchor_mismatch",
                  json.dumps({"checkpoint_entries": entries,
                              "chain_entries": chain.count(),
                              "detected": now_iso()}))
        chain.append("STARTUP_ANCHOR_MISMATCH", {
            "checkpoint_entries": entries, "chain_entries": chain.count()})


_startup_anchor_check()


# ---------------- shared gates ----------------
def auth(handler):
    """Return the user record or None. Named individual accounts only;
    a disabled account cannot authenticate. Comparison is constant-time
    (item 13)."""
    _reload_config()
    user = handler.headers.get("X-Noctua-User", "")
    key = handler.headers.get("X-Noctua-Key", "")
    rec = USERS.get(user)
    if not rec or rec.get("disabled"):
        return None
    if not hmac_mod.compare_digest(sha(key),
                                   str(rec.get("key_sha256", ""))):
        return None
    return rec


def case_gate(case_no):
    """(ok, reason_code) — THE case check (item 18). Every endpoint
    that takes a case number runs this one function: catch-all ban,
    then membership in the open-case list."""
    if any(p in (case_no or "").upper() for p in BANNED_CASE_PATTERNS):
        return False, "case_banned"
    if case_no not in CASES:
        return False, "case_invalid"
    return True, ""


CASE_GATE_MSGS = {
    "case_banned": "BLOCKED: catch-all case numbers are banned",
    "case_invalid": "BLOCKED: case number failed validation",
}


def janus_gate(user_rec, case_no):
    """Role + case gate for /search. Service and partner accounts are
    denied here as everywhere on the data surface (item 23)."""
    if user_rec["role"] == "auditor":
        return False, "role"
    if user_rec["role"] in SERVICE_ROLES:
        return False, "role"
    ok, why = case_gate(case_no)
    if not ok:
        return False, why
    return True, ""


def validate_fragment(frag):
    """(normalized, reason_code) — item 2. Fragments shorter than 3
    characters or carrying SQL wildcards turn a search into a browse;
    they are refused on every search path."""
    f = (frag or "").strip().upper()
    if not f:
        return None, "fragment_required"
    if "%" in f or "_" in f:
        return None, "fragment_wildcard"
    if len(f) < 3:
        return None, "fragment_too_short"
    return f, ""


FRAGMENT_MSGS = {
    "fragment_required": "a plate fragment is required",
    "fragment_wildcard": "wildcards (% and _) are not searchable",
    "fragment_too_short": "plate fragment must be at least 3 characters",
}


def active_suppression_refs():
    return {r[0] for r in db.execute(
        "SELECT plate_ref FROM suppressions WHERE active=1")}


def is_suppressed(plate, state):
    return plate_ref(plate, state) in active_suppression_refs()


def run_search(frag, scope="full"):
    """Execute a read search. scope='tier2' applies the temporal wall
    IN SQL (item 1): only reads received within TIER2_WINDOW_H hours
    are visible. scope='full' is the Tier 3 / Compact-historical scope.

    Suppressed plates are EXCLUDED for every viewer (item 5): no stub,
    no marker, no count difference an observer can use — the result is
    indistinguishable from the plate never having been read. The match
    workflow (GET /suppressed-hits) is the only disclosure path."""
    frag = (frag or "").upper()
    sup = active_suppression_refs()
    window = ""
    params = ["%" + frag + "%"]
    if scope == "tier2":
        since = (datetime.now(timezone.utc)
                 - timedelta(hours=TIER2_WINDOW_H)).strftime(
                     "%Y-%m-%dT%H:%M:%SZ")
        window = " AND ts>=?"
        params.append(since)
    rows = db.execute(
        "SELECT ts,cam,plate,state FROM reads WHERE plate LIKE ?"
        + window + " ORDER BY ts DESC LIMIT 200", params).fetchall()
    hit_rows = db.execute(
        "SELECT ts,cam,read_plate,state,status FROM hits "
        "WHERE read_plate LIKE ?" + window
        + " ORDER BY ts DESC LIMIT 50", params).fetchall()
    return {
        "reads": [dict(zip(("ts", "cam", "plate", "state"), r))
                  for r in rows
                  if plate_ref(r[2], r[3]) not in sup],
        "hits": [dict(zip(("ts", "cam", "plate", "state", "status"), r))
                 for r in hit_rows
                 if plate_ref(r[2], r[3]) not in sup]}


def jobs_status():
    """Dead-man status for the monitored jobs. A job that reported
    ok:false is degraded NOW, not when it goes stale (item 8)."""
    now = datetime.now(timezone.utc)
    rows = {r[0]: r for r in db.execute(
        "SELECT job, ts, ok, detail FROM heartbeats")}
    jobs, overdue = {}, []
    for job, max_age in JOB_MAX_AGE_S.items():
        r = rows.get(job)
        if not r:
            jobs[job] = {"last": None, "ok": False, "overdue": True,
                         "status": "never reported"}
            overdue.append(job)
            continue
        try:
            last = parse_ts(r[1])
            age = int((now - last).total_seconds())
        except (ValueError, TypeError):
            age = None
        od = age is None or age > max_age or not r[2]
        jobs[job] = {"last": r[1], "ok": bool(r[2]), "detail": r[3],
                     "age_s": age, "overdue": od,
                     "status": ("reported failure" if not r[2]
                                else "overdue" if od else "ok")}
        if od:
            overdue.append(job)
    for job, r in rows.items():
        if job not in jobs:
            jobs[job] = {"last": r[1], "ok": bool(r[2]), "detail": r[3],
                         "overdue": False}
    return jobs, overdue


def retention_oldest_read_age_h():
    row = db.execute("SELECT MIN(ts) FROM reads").fetchone()
    if not row or not row[0]:
        return None
    try:
        age = (datetime.now(timezone.utc) - parse_ts(row[0]))
        return round(age.total_seconds() / 3600.0, 2)
    except (ValueError, TypeError):
        return None


def cameras_status():
    """Per-camera last-seen from ingest (item 24). A camera with no
    read inside CAMERA_SILENCE_S is silent — a dead camera and a
    severed backhaul look the same from here, and both are alarms."""
    now = datetime.now(timezone.utc)
    out, silent = {}, []
    for cam, last in db.execute(
            "SELECT cam, MAX(ts) FROM reads GROUP BY cam"):
        try:
            age = int((now - parse_ts(last)).total_seconds())
        except (ValueError, TypeError):
            age = None
        out[cam] = {"last_read": last, "age_s": age}
        if age is None or age > CAMERA_SILENCE_S:
            silent.append(cam)
    return out, silent


def overdue_holds():
    return [dict(zip(("id", "scope", "ref", "placed_by", "review_by"), r))
            for r in db.execute(
                "SELECT id, scope, ref, placed_by, review_by FROM holds "
                "WHERE active=1 AND review_by IS NOT NULL "
                "AND review_by < ?", (now_iso(),))]


# ---------------- backfill aggregation (item 16) ----------------
# A camera clock behind receipt by >5 min on a replayed backlog is not
# "skew" — it is store-and-forward doing its job. Backfills aggregate
# into at most one BACKFILL chain entry per camera per hour; buckets
# flush on hour rollover, when a bucket reaches 1000 reads, or when a
# bucket has been idle longer than NOCTUA_BACKFILL_FLUSH_S (default
# 3600; the flush timer exists so a quiet camera's bucket still lands).
BACKFILL_FLUSH_S = int(os.environ.get("NOCTUA_BACKFILL_FLUSH_S", "3600"))
_backfill = {}


def _backfill_flush(key):
    b = _backfill.pop(key, None)
    if b:
        chain.append("BACKFILL", {"cam": key[0], "hour": key[1],
                                  "count": b["count"],
                                  "max_delay_s": b["max_delay_s"]})


def _backfill_note(cam, delay_s):
    hour = now_iso()[:13]
    for k in [k for k in _backfill if k[0] == cam and k[1] != hour]:
        _backfill_flush(k)
    b = _backfill.setdefault((cam, hour),
                             {"count": 0, "max_delay_s": 0,
                              "last": time.time()})
    b["count"] += 1
    b["max_delay_s"] = max(b["max_delay_s"], delay_s)
    b["last"] = time.time()
    if b["count"] >= 1000:
        _backfill_flush((cam, hour))


def _backfill_flush_idle():
    now = time.time()
    for k in [k for k, b in _backfill.items()
              if now - b["last"] > BACKFILL_FLUSH_S]:
        _backfill_flush(k)


# ---------------- report computation (items 11 + 34) ----------------
def _sanitize_list_name(name):
    """A list label must never carry a case number into the public
    report (item 11): strip case-number-shaped tokens; fall back to
    the local label."""
    if not name:
        return "Local agency list"
    cleaned = re.sub(r"\b\d{4}-\d+\b", "", str(name))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or "Local agency list"


def tier3_stats(frm, to):
    """K8 (INTEGRATION.md decision 3, item 34): the Tier 3 emergency
    share for the period and the trailing 3-month rolling share,
    against the pinned 25% threshold."""
    def _counts(a, b):
        total = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE created_ts>=? "
            "AND created_ts<=?", (a, b)).fetchone()[0]
        emerg = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE created_ts>=? "
            "AND created_ts<=? AND emergency=1", (a, b)).fetchone()[0]
        return total, emerg
    total, emerg = _counts(frm, to)
    try:
        to_dt = parse_ts(to) if len(to) > 10 else datetime.now(timezone.utc)
        if to_dt.year > 9000:
            # Open-ended report (to = 9999-…): the rolling window
            # anchors at NOW, not at the year 9999.
            to_dt = datetime.now(timezone.utc)
    except (ValueError, TypeError):
        to_dt = datetime.now(timezone.utc)
    r_from = (to_dt - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r_total, r_emerg = _counts(r_from, to)
    r_share = (r_emerg / r_total) if r_total else 0.0
    return {
        "tier3_actions": total, "emergencies": emerg,
        "emergency_share": round(emerg / total, 4) if total else 0.0,
        "rolling_3mo": {
            "actions": r_total, "emergencies": r_emerg,
            "share": round(r_share, 4), "threshold": 0.25,
            "state": "tripped" if r_total and r_share > 0.25 else "ok"}}


def compute_report(frm, to):
    """SS 12-12-1805 aggregates. Match-side figures derive ONLY from
    outcomes and lists_checked (item 11) — never from the hits table,
    which retention deletes. Prosecutions are NULL until the
    prosecutor feedback loop reports them; the report distinguishes
    'not yet reported' from zero (INTEGRATION.md decision 7)."""
    scanned = db.execute(
        "SELECT COALESCE(SUM(reads),0) FROM counters "
        "WHERE day>=? AND day<=?", (frm[:10], to[:10])).fetchone()[0]
    names = {r[0] for r in db.execute(
        "SELECT list_name FROM lists_checked WHERE day>=? AND day<=?",
        (frm[:10], to[:10]))}
    names |= {r[0] for r in db.execute(
        "SELECT DISTINCT list_name FROM outcomes WHERE hit_ts>=? "
        "AND hit_ts<=?", (frm, to))}
    lists = {}
    for name in sorted(names):
        row = db.execute(
            "SELECT COALESCE(SUM(confirmed),0), "
            "COALESCE(SUM(CASE WHEN confirmed=0 THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(arrest),0), "
            "COALESCE(SUM(CASE WHEN prosecution=1 THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN prosecution IS NOT NULL "
            "THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN arrest=1 AND prosecution=1 "
            "THEN 1 ELSE 0 END),0) "
            "FROM outcomes WHERE list_name=? AND hit_ts>=? AND hit_ts<=?",
            (name, frm, to)).fetchone()
        lists[name] = {
            "confirmed_matches": row[0], "non_corresponding": row[1],
            "arrests": row[2], "prosecutions": row[3],
            "prosecutions_reported": row[4],
            "arrests_and_prosecutions": row[5]}
    tot = db.execute(
        "SELECT COALESCE(SUM(confirmed),0), "
        "COALESCE(SUM(CASE WHEN confirmed=0 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(arrest),0), "
        "COALESCE(SUM(CASE WHEN prosecution=1 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN prosecution IS NOT NULL "
        "THEN 1 ELSE 0 END),0), COUNT(*) FROM outcomes "
        "WHERE hit_ts>=? AND hit_ts<=?", (frm, to)).fetchone()
    prosecutions = tot[3] if tot[4] else "not yet reported"
    return {
        "from": frm, "to": to, "plates_scanned": scanned,
        "plates_scanned_source": "counters (cumulative at ingest; "
                                 "survives retention deletes)",
        "lists": lists,
        "confirmed_matches": tot[0],
        "matches_not_corresponding": tot[1],
        "arrests": tot[2],
        "prosecutions": prosecutions,
        "prosecutions_coverage": {"reported": tot[4], "total": tot[5]},
        "tier3": tier3_stats(frm, to),
        "overdue_holds": len(overdue_holds())}


# ---------------- custody excerpt (item 9) ----------------
def custody_excerpt(hit_id):
    """The Sentinel entries that mention this hit, found with an
    INDEXED, paged scan over the entry kinds that can carry a hit id —
    not a 100k-row in-memory sweep (1.0's approach)."""
    kinds = ("ALERT", "VERIFY", "HOLD_PLACE", "HOLD_RELEASE",
             "EVIDENCE_EXPORT", "EVIDENCE_RELEASE", "EVIDENCE_DESTROY",
             "EVIDENCE_DISPOSITION", "EVIDENCE_DISPOSITION_CONFIRM")
    out, offset = [], 0
    while True:
        rows = db.execute(
            "SELECT seq,ts,kind,payload,prev,hash FROM audit "
            "WHERE kind IN (%s) ORDER BY seq LIMIT 500 OFFSET ?"
            % ",".join("?" * len(kinds)), (*kinds, offset)).fetchall()
        for seq, ts, kind, payload, prev, h in rows:
            fields = {k: v for k, v in json.loads(payload).items()
                      if k not in ("ts", "kind")}
            if fields.get("hit") == hit_id:
                out.append({"seq": seq, "ts": ts, "kind": kind,
                            "fields": fields, "prev": prev, "hash": h})
        if len(rows) < 500:
            return out
        offset += 500


class Server(ThreadingHTTPServer):
    daemon_threads = True


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def setup(self):
        super().setup()
        # A stalled client must not freeze the service (item 33).
        self.connection.settimeout(30)

    # Responses are CAPTURED, not written, while the DB lock is held;
    # the wrapper serializes and writes after the lock is released, so
    # the lock covers database work only (items 14/33).
    def send_json(self, code, obj):
        self._resp = (code, obj)
        return None

    def _flush_response(self):
        code, obj = getattr(self, "_resp", None) or (
            500, {"error": "internal: handler produced no response"})
        body = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def body_json(self):
        return getattr(self, "_json", {})

    def _read_body(self):
        """Read + parse the request body BEFORE the lock (item 33),
        capped at 1 MB (item 13). Returns False if the request has
        already been answered (413/400)."""
        self._json = {}
        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            n = 0
        if n > BODY_CAP:
            self._resp = (413, {"error": "request body exceeds the "
                                         "1 MB cap"})
            self._flush_response()
            return False
        raw = self.rfile.read(n) if n else b""
        if raw:
            try:
                self._json = json.loads(raw)
            except ValueError:
                self._resp = (400, {"error": "body must be JSON"})
                self._flush_response()
                return False
            if not isinstance(self._json, dict):
                self._resp = (400, {"error": "body must be a JSON object"})
                self._flush_response()
                return False
        return True

    def need_auth(self):
        rec = auth(self)
        if not rec:
            user = self.headers.get("X-Noctua-User", "")
            if user and not KEY_LOCKED:
                try:
                    chain.append("AUTH_FAIL", {"user": user})
                except Exception:
                    pass  # the 401 still goes out (item 4)
            self.send_json(401, {"error": "authentication failed — "
                                          "named individual accounts only"})
        return rec

    def locked_out(self):
        if KEY_LOCKED:
            self.send_json(503, {"error": "audit key missing — Janus is "
                                          "locked (see /health)"})
            return True
        return False

    def deny_service_role(self, rec, action):
        """Item 23: service and partner accounts move data; they never
        read it. Callers invoke this whenever a role check fails on a
        data-returning endpoint; it always answers 403 (the message
        distinguishes service accounts from other wrong roles)."""
        chain.append("BLOCKED", {"user": rec["user"], "action": action,
                                 "reason": "role"})
        msg = ("service accounts cannot read data"
               if rec["role"] in SERVICE_ROLES
               else "role cannot read this data")
        return self.send_json(403, {"error": msg})

    # ---------------- POST ----------------
    def do_POST(self):
        self._resp = None
        if not self._read_body():
            return
        with DBLOCK:
            try:
                self._post()
            except ChainScrubError as exc:
                self._resp = (500, {"error": f"chain scrub refused the "
                                             f"write: {exc}"})
            except Exception as exc:  # a handler bug must still answer
                self._resp = (500, {"error": f"internal: {exc}"})
        self._flush_response()

    def _post(self):
        path = urlparse(self.path).path
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        if path == "/reads":
            if rec["role"] != "ingest":
                return self.send_json(403, {"error": "ingest is the "
                                                   "ingest role only"})
            d = self.body_json()
            plate = (d.get("plate") or "").upper()
            state = (d.get("state") or "AR").upper()
            cam = d.get("cam")
            if not plate or not cam:
                return self.send_json(400, {"error": "plate and cam are "
                                                   "required"})
            ts = now_iso()
            cam_ts = d.get("ts")
            skew_s = None
            if cam_ts:
                try:
                    ct = parse_ts(cam_ts)
                    st = parse_ts(ts)
                    skew_s = int((st - ct).total_seconds())
                except (ValueError, TypeError):
                    cam_ts = None  # unparseable camera time: ignore
            db.execute("INSERT INTO reads(ts,cam,plate,state,conf,cam_ts,"
                       "skew_s) VALUES(?,?,?,?,?,?,?)",
                       (ts, cam, plate, state, d.get("conf", 0.95),
                        cam_ts, skew_s))
            # Provenance (item 11): every read is checked against every
            # active list; record which lists those were, per day, so
            # the statutory report can name lists with zero matches.
            for (ln,) in db.execute(
                    "SELECT DISTINCT list_name FROM hotlist "
                    "WHERE active=1").fetchall():
                db.execute("INSERT OR IGNORE INTO lists_checked(day,"
                           "list_name) VALUES(?,?)", (ts[:10], ln))
            entry = db.execute(
                "SELECT plate,category,list_name,expires_ts FROM hotlist "
                "WHERE plate=? AND state=? AND active=1",
                (plate, state)).fetchone()
            hit_id = None
            expired = False
            if entry and entry[3] and entry[3] <= ts:
                # Item 12: an expired entry alerts no one. It
                # auto-deactivates; the expiry is chained AFTER the
                # commit below (lock ordering — the chain writes
                # through its own connection).
                db.execute("UPDATE hotlist SET active=0 WHERE plate=? "
                           "AND state=?", (plate, state))
                expired = True
                entry = None
            if entry:
                # Item 5: a hit on a suppressed plate is flagged at
                # ingest so it routes to the supervisor-only queue
                # and never surfaces in /hits or search results.
                supp = 1 if is_suppressed(plate, state) else 0
                cur = db.execute(
                    "INSERT INTO hits(ts,cam,read_plate,entry_plate,state,"
                    "list_name,category,suppressed) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (ts, cam, plate, entry[0], state, entry[2], entry[1],
                     supp))
                hit_id = cur.lastrowid
            # Cumulative counters: the six-month report's plates_scanned
            # must survive the 14-day retention deletes, so it is
            # counted here, at ingest, in a table retention never
            # touches (for reads).
            db.execute(
                "INSERT INTO counters(day,camera_id,reads,alerts) "
                "VALUES(?,?,1,?) ON CONFLICT(day,camera_id) DO UPDATE "
                "SET reads=reads+1, alerts=alerts+excluded.alerts",
                (ts[:10], cam, 1 if hit_id else 0))
            db.commit()
            if expired:
                chain.append("HOTLIST_EXPIRED", {
                    "plate_ref": plate_ref(plate, state), "by": "ingest"})
            if skew_s is not None:
                if skew_s < -5:
                    # Camera clock AHEAD of receipt: real skew (item 16).
                    chain.append("CLOCK_SKEW", {"cam": cam,
                                                "skew_s": skew_s})
                elif skew_s > 300:
                    # Far behind receipt: a replayed backlog, not skew.
                    _backfill_note(cam, skew_s)
            _backfill_flush_idle()
            resp = {"result": "stored"}
            if skew_s is not None:
                resp["clock_skew_s"] = skew_s
            if hit_id:
                chain.append("ALERT", {"hit": hit_id, "cam": cam,
                                       "category": entry[1]})
                resp = {"result": "ALERT", "hit_id": hit_id}
                if skew_s is not None:
                    resp["clock_skew_s"] = skew_s
            return self.send_json(201, resp)
        if path == "/heartbeat":
            if rec["role"] != "jobs":
                return self.send_json(403, {"error": "heartbeats are the "
                                                   "jobs role only"})
            d = self.body_json()
            job = str(d.get("job", "")).strip()
            if not job:
                return self.send_json(400, {"error": "job is required"})
            # Item 8: ok must be EXPLICIT. A heartbeat that does not
            # say ok:true is recorded as a failure — silence about
            # success is not success.
            ok = d.get("ok") is True
            db.execute(
                "INSERT INTO heartbeats(job,ts,ok,detail) VALUES(?,?,?,?) "
                "ON CONFLICT(job) DO UPDATE SET ts=excluded.ts, "
                "ok=excluded.ok, detail=excluded.detail",
                (job, now_iso(), 1 if ok else 0,
                 str(d.get("detail", ""))[:500]))
            db.commit()
            chain.append("HEARTBEAT", {"job": job, "ok": ok})
            return self.send_json(200, {"result": "heartbeat recorded",
                                        "job": job, "ok": ok})
        if path == "/hotlist":
            if rec["role"] not in ("detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hotlist add",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot add "
                                                   "hot-list entries"})
            d = self.body_json()
            ok, reason = case_gate(d.get("case"))
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hotlist add",
                                         "reason": reason})
                return self.send_json(403, {"error": CASE_GATE_MSGS[reason]})
            plate = normalize_plate(d.get("plate"))
            state = (d.get("state") or "AR").upper()
            if not plate:
                return self.send_json(400, {"error": "plate is required"})
            if plate_ref(plate, state) in active_suppression_refs():
                # Item 5: listing a protected plate would route its
                # reads into a workflow the order forbids. Refused,
                # and the conflict itself is chained.
                chain.append("SUPPRESSION_CONFLICT", {
                    "plate_ref": plate_ref(plate, state), "by": rec["user"],
                    "action": "hotlist add"})
                return self.send_json(403, {
                    "error": "that plate is under a protection-order "
                             "suppression — it cannot be hot-listed"})
            list_name = _sanitize_list_name(
                d.get("list_name") or "Local agency list")
            db.execute(
                "INSERT OR REPLACE INTO hotlist(plate,state,category,"
                "source,list_name,case_no,added_by,added_ts,expires_ts,"
                "active) VALUES(?,?,?,?,?,?,?,?,?,1)",
                (plate, state, d["category"], list_name, list_name,
                 d["case"], rec["user"], now_iso(), d.get("expires", "")))
            db.commit()
            chain.append("HOTLIST_ADD", {
                "plate_ref": plate_ref(plate, state),
                "category": d["category"], "by": rec["user"],
                "case": d["case"]})
            return self.send_json(201, {"result": "added"})
        if path == "/verify":
            if rec["role"] not in ("detective", "patrol", "supervisor"):
                return self.send_json(403, {"error": "role cannot verify "
                                                   "hits"})
            d = self.body_json()
            decision = str(d.get("decision", "")).lower()
            if decision not in ("confirm", "reject"):
                return self.send_json(400, {
                    "error": "decision must be 'confirm' or 'reject'"})
            ok, reason = case_gate(d.get("case"))
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hit verification",
                                         "hit": d.get("hit_id"),
                                         "reason": reason})
                return self.send_json(403, {"error": CASE_GATE_MSGS[reason]})
            hit = db.execute("SELECT entry_plate, category, ts, list_name "
                             "FROM hits WHERE id=? AND status='PENDING'",
                             (d["hit_id"],)).fetchone()
            if not hit:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hit verification",
                                         "hit": d.get("hit_id"),
                                         "reason": "hit_not_pending"})
                return self.send_json(409, {"error": "hit not found or "
                                                   "already decided"})
            status = "VERIFIED" if decision == "confirm" else "REJECTED"
            db.execute("UPDATE hits SET status=?, decided_by=?, case_no=?, "
                       "decided_ts=? WHERE id=? AND status='PENDING'",
                       (status, rec["user"], d["case"], now_iso(),
                        d["hit_id"]))
            # Plate-free outcome record for the SS 12-12-1805 report.
            # prosecution is left NULL — unknown until the prosecutor
            # feedback loop reports it (item 11). The list name comes
            # from the hit itself, recorded at match time, so it
            # survives the hot-list entry being removed later.
            db.execute(
                "INSERT INTO outcomes(hit_id, list_name, category, "
                "confirmed, arrest, updated_by, updated_ts, hit_ts) "
                "VALUES(?,?,?,?,0,?,?,?) ON CONFLICT(hit_id) DO UPDATE SET "
                "confirmed=excluded.confirmed, "
                "updated_by=excluded.updated_by, "
                "updated_ts=excluded.updated_ts",
                (d["hit_id"], hit[3] or "Local agency list", hit[1],
                 1 if decision == "confirm" else 0,
                 rec["user"], now_iso(), hit[2]))
            db.commit()
            chain.append("VERIFY", {"hit": d["hit_id"], "result": status,
                                    "by": rec["user"], "case": d["case"]})
            return self.send_json(200, {"result": status})
        if path == "/outcomes":
            if rec["role"] not in ("detective", "supervisor"):
                return self.send_json(403, {"error": "role cannot update "
                                                   "outcomes"})
            d = self.body_json()
            row = db.execute("SELECT arrest, prosecution FROM outcomes "
                             "WHERE hit_id=?", (d.get("hit_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no outcome record "
                                                   "for that hit — verify "
                                                   "the hit first"})
            arrest = (1 if d["arrest"] else 0) if "arrest" in d else row[0]
            if "prosecution" in d:
                pros = None if d["prosecution"] is None \
                    else (1 if d["prosecution"] else 0)
            else:
                pros = row[1]
            db.execute("UPDATE outcomes SET arrest=?, prosecution=?, "
                       "updated_by=?, updated_ts=? WHERE hit_id=?",
                       (arrest, pros, rec["user"], now_iso(), d["hit_id"]))
            db.commit()
            chain.append("OUTCOME_UPDATE", {
                "hit": d["hit_id"], "arrest": arrest,
                "prosecution": ("unreported" if pros is None else pros),
                "by": rec["user"]})
            return self.send_json(200, {"result": "outcome updated",
                                        "hit": d["hit_id"],
                                        "arrest": arrest,
                                        "prosecution": pros})
        if path == "/holds":
            if rec["role"] not in ("detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hold place",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot place "
                                                   "holds"})
            d = self.body_json()
            if d.get("scope") not in ("case", "hit"):
                return self.send_json(400, {"error": "scope must be "
                                                   "'case' or 'hit'"})
            if d["scope"] == "case":
                # Item 32: a case-scoped hold runs the shared gate.
                ok, reason = case_gate(d.get("ref"))
                if not ok:
                    chain.append("BLOCKED", {"user": rec["user"],
                                             "action": "hold place",
                                             "reason": reason})
                    return self.send_json(403,
                                          {"error": CASE_GATE_MSGS[reason]})
            review_by = d.get("review_by") or (
                datetime.now(timezone.utc)
                + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
            cur = db.execute(
                "INSERT INTO holds(scope, ref, reason, placed_by, "
                "placed_ts, active, review_by) VALUES(?,?,?,?,?,1,?)",
                (d["scope"], str(d.get("ref", "")), d.get("reason", ""),
                 rec["user"], now_iso(), review_by))
            db.commit()
            chain.append("HOLD_PLACE", {"hold": cur.lastrowid,
                                        "scope": d["scope"],
                                        "ref": str(d.get("ref", "")),
                                        "by": rec["user"],
                                        "review_by": review_by})
            return self.send_json(201, {"result": "hold placed",
                                        "hold_id": cur.lastrowid,
                                        "review_by": review_by})
        if path == "/holds/release":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hold release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "hold release is "
                                                   "supervisor-only"})
            d = self.body_json()
            row = db.execute("SELECT active, scope, ref FROM holds "
                             "WHERE id=?", (d.get("hold_id"),)).fetchone()
            if not row or not row[0]:
                return self.send_json(404, {"error": "no active hold "
                                                   "with that id"})
            fields = {"hold": d["hold_id"], "by": rec["user"]}
            if row[1] == "case":
                # Item 32: the gate runs at release too — its result is
                # chained, but a release is never BLOCKED by it: a case
                # closing must not trap held data past its review.
                ok, _r = case_gate(row[2])
                fields["case_gate_ok"] = ok
            db.execute("UPDATE holds SET active=0, released_by=?, "
                       "released_ts=? WHERE id=?",
                       (rec["user"], now_iso(), d["hold_id"]))
            db.commit()
            chain.append("HOLD_RELEASE", fields)
            return self.send_json(200, {"result": "hold released"})
        if path == "/suppressions":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression place",
                                         "reason": "role"})
                return self.send_json(403, {"error": "suppressions are "
                                                   "supervisor-only"})
            d = self.body_json()
            # Item 5: a suppression is placed against the protection
            # ORDER (its court reference), not against a case number.
            # A case may be supplied for the file; when it is, it runs
            # the shared gate like everywhere else (item 18).
            order_ref = (d.get("order_ref") or "").strip()
            if not order_ref:
                return self.send_json(400, {
                    "error": "order_ref (the protection order's number / "
                             "court) is required"})
            if d.get("case"):
                ok, reason = case_gate(d["case"])
                if not ok:
                    chain.append("BLOCKED", {"user": rec["user"],
                                             "action": "suppression place",
                                             "reason": reason})
                    return self.send_json(403,
                                          {"error": CASE_GATE_MSGS[reason]})
            plate = normalize_plate(d.get("plate"))
            state = (d.get("state") or "AR").upper()
            if not plate:
                return self.send_json(400, {"error": "plate is required"})
            ref = plate_ref(plate, state)
            db.execute(
                "INSERT INTO suppressions(plate_ref, plate, state, "
                "order_ref, placed_by, case_no, ts, active) "
                "VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(plate_ref) DO "
                "UPDATE SET active=1, plate=excluded.plate, "
                "state=excluded.state, order_ref=excluded.order_ref, "
                "placed_by=excluded.placed_by, case_no=excluded.case_no, "
                "ts=excluded.ts, release_requested_by=NULL, "
                "release_order_ref=NULL",
                (ref, plate, state, order_ref, rec["user"],
                 d.get("case"), now_iso()))
            db.commit()
            chain.append("SUPPRESSION_PLACE", {"plate_ref": ref,
                                               "by": rec["user"]})
            # Near-match warning: raw plate forms already in the data
            # that normalize to this plate (a camera read it with a
            # space, the hot list carries a hyphen) differ only by
            # formatting — the operator should know the suppression's
            # normalized key may not be the only form on file.
            variants = set()
            for (raw,) in db.execute(
                    "SELECT DISTINCT plate FROM reads").fetchall():
                if raw != plate and normalize_plate(raw) == plate:
                    variants.add(raw)
            for (raw,) in db.execute(
                    "SELECT DISTINCT plate FROM hotlist").fetchall():
                if raw != plate and normalize_plate(raw) == plate:
                    variants.add(raw)
            return self.send_json(201, {
                "result": "suppression placed",
                "warning_near_matches": sorted(variants)})
        if path == "/suppressions/release":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "suppression release "
                                                   "is supervisor-only"})
            d = self.body_json()
            plate = normalize_plate(d.get("plate"))
            state = (d.get("state") or "AR").upper()
            ref = plate_ref(plate, state)
            row = db.execute(
                "SELECT order_ref, release_requested_by FROM suppressions "
                "WHERE plate_ref=? AND active=1", (ref,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no active suppression "
                                                   "for that plate"})
            order_ref, requested_by = row
            # Two-key release (item 5): the first supervisor requests,
            # a DIFFERENT supervisor confirms — and the order reference
            # on file must be repeated, so a release cannot ride on a
            # misremembered order.
            if requested_by is None:
                db.execute("UPDATE suppressions SET "
                           "release_requested_by=?, release_order_ref=? "
                           "WHERE plate_ref=?",
                           (rec["user"], d.get("order_ref"), ref))
                db.commit()
                chain.append("SUPPRESSION_RELEASE_REQUEST", {
                    "plate_ref": ref, "by": rec["user"]})
                return self.send_json(200, {
                    "result": "release requested — a second supervisor "
                              "must confirm with the order reference"})
            if requested_by == rec["user"]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression release",
                                         "reason": "two_key"})
                return self.send_json(403, {
                    "error": "BLOCKED: the two-key rule forbids "
                             "confirming your own suppression release"})
            if (d.get("order_ref") or "") != order_ref:
                return self.send_json(400, {
                    "error": "order_ref does not match the order on file"})
            db.execute("UPDATE suppressions SET active=0, "
                       "release_requested_by=NULL, release_order_ref=NULL "
                       "WHERE plate_ref=?", (ref,))
            db.commit()
            chain.append("SUPPRESSION_RELEASE", {
                "plate_ref": ref, "by": rec["user"],
                "requested_by": requested_by})
            return self.send_json(200, {"result": "suppression released"})
        if path.startswith("/tier3/"):
            return self._tier3_post(path, rec)
        if path.startswith("/evidence/"):
            return self._evidence_post(path, rec)
        if path.startswith("/compact/") or path == "/share/query":
            return self._compact_post(path, rec)
        if path == "/report/compile":
            return self._report_compile(rec)
        if path == "/audit/anchor-accept":
            return self._anchor_accept(rec)
        return self.send_json(404, {"error": "no such route"})

    def _report_compile(self, rec):
        if rec["role"] not in DATA_ROLES:
            return self.send_json(403, {"error": "role cannot compile "
                                                "reports"})
        d = self.body_json()
        frm = d.get("from", "")
        to = d.get("to", "9999-12-31T23:59:59Z")
        body = compute_report(frm, to)
        cur = db.execute(
            "INSERT INTO report_snapshots(from_ts, to_ts, compiled_by, "
            "compiled_ts, body) VALUES(?,?,?,?,?)",
            (frm, to, rec["user"], now_iso(),
             json.dumps(body, sort_keys=True)))
        db.commit()
        # Item 11: the compiled snapshot is immutable — retention never
        # deletes snapshots, and the compile itself is chained.
        chain.append("REPORT_COMPILE", {"snapshot": cur.lastrowid,
                                        "by": rec["user"]})
        return self.send_json(201, {"result": "snapshot compiled",
                                    "snapshot_id": cur.lastrowid,
                                    "report": body})

    def _anchor_accept(self, rec):
        """Two-key clearing of a startup anchor mismatch (item 7):
        a supervisor records acceptance, then the AUDITOR — a
        different person, outside the chain of command — confirms.
        Either order is refused: the auditor's key turns second."""
        if not anchor_mismatch():
            return self.send_json(200, {"result": "no anchor mismatch "
                                                  "to accept"})
        pending = _meta_get("anchor_accept_by")
        if rec["role"] == "supervisor" and not pending:
            _meta_set("anchor_accept_by", rec["user"])
            chain.append("ANCHOR_ACCEPT_REQUEST", {"by": rec["user"]})
            return self.send_json(200, {
                "result": "acceptance recorded — the auditor must "
                          "confirm to clear the mismatch"})
        if rec["role"] == "auditor" and pending:
            if rec["user"] == pending:
                return self.send_json(403, {"error": "the two-key rule "
                                                   "forbids self-confirm"})
            db.execute("DELETE FROM meta WHERE key IN "
                       "('anchor_mismatch','anchor_accept_by')")
            db.commit()
            chain.append("ANCHOR_ACCEPT", {"requested_by": pending,
                                           "by": rec["user"]})
            return self.send_json(200, {"result": "anchor mismatch "
                                                  "cleared"})
        return self.send_json(403, {
            "error": "anchor acceptance is supervisor-then-auditor, "
                     "two keys"})

    # ---------------- Tier 3 two-key workflow ----------------
    def _tier3_post(self, path, rec):
        d = self.body_json()
        if path == "/tier3/request":
            if rec["role"] not in ("detective", "patrol", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot request "
                                                   "Tier 3 searches"})
            case_no = d.get("case_id", "")
            why = (d.get("why") or "").strip()
            frag, ferr = validate_fragment(d.get("plate_fragment"))
            basis = (d.get("auth_basis") or "").strip()
            basis_type = (d.get("basis_type") or "other").strip().lower()
            if basis_type not in BASIS_TYPES:
                return self.send_json(400, {
                    "error": "basis_type must be one of "
                             + ", ".join(BASIS_TYPES)})
            if not why:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "no_justification"})
                return self.send_json(403, {"error": "BLOCKED: Tier 3 "
                                                   "requests require a "
                                                   "justification (why)"})
            if ferr:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": ferr})
                return self.send_json(400,
                                      {"error": FRAGMENT_MSGS[ferr]})
            if not basis:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "no_basis"})
                return self.send_json(403, {"error": "BLOCKED: Tier 3 "
                                                   "requests require "
                                                   "auth_basis (the warrant "
                                                   "or court order on file)"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "case": case_no, "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            if config_status()["fail_closed"]:
                return self.send_json(503, {"error": "configuration has "
                                                   "been stale >24h — "
                                                   "search is closed until "
                                                   "a clean reload"})
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, basis_type, status, "
                "created_ts) VALUES(?,?,?,?,?,?,'PENDING',?)",
                (rec["user"], case_no, why, frag, basis, basis_type,
                 now_iso()))
            db.commit()
            # Item 26: the chain carries the coded basis_type and the
            # fragment's ref — the warrant's free text stays in the DB.
            chain.append("TIER3_REQUEST", {
                "request": cur.lastrowid, "by": rec["user"],
                "case": case_no, "plate_ref": frag_ref(frag),
                "basis_type": basis_type})
            return self.send_json(201, {
                "result": "PENDING — nothing was searched",
                "request_id": cur.lastrowid})
        if path == "/tier3/approve":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "reason": "role"})
                return self.send_json(403, {"error": "Tier 3 approval is "
                                                   "supervisor-only"})
            row = db.execute(
                "SELECT requester, case_no, why, plate_fragment, "
                "auth_basis, basis_type, status FROM tier3_requests "
                "WHERE id=?", (d.get("request_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            requester, case_no, why, frag, basis, basis_type, status = row
            if status != "PENDING":
                return self.send_json(409, {"error": "request is not "
                                                   "pending (status: %s)"
                                                   % status})
            if rec["user"] == requester:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "request": d["request_id"],
                                         "reason": "two_key"})
                return self.send_json(403, {"error": "BLOCKED: the two-key "
                                                   "rule forbids approving "
                                                   "your own Tier 3 "
                                                   "request"})
            # Item 19: the case gate re-runs at execution — a case
            # that closed while the request waited no longer opens.
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "request": d["request_id"],
                                         "reason": reason})
                return self.send_json(403, {
                    "error": "BLOCKED at execution: "
                             + CASE_GATE_MSGS[reason]})
            if config_status()["fail_closed"]:
                return self.send_json(503, {"error": "configuration has "
                                                   "been stale >24h — "
                                                   "search is closed until "
                                                   "a clean reload"})
            results = run_search(frag, "full")
            n = len(results["reads"]) + len(results["hits"])
            db.execute(
                "UPDATE tier3_requests SET status='EXECUTED', "
                "decided_by=?, decided_ts=?, results_count=?, results=? "
                "WHERE id=?",
                (rec["user"], now_iso(), n,
                 json.dumps(results, sort_keys=True), d["request_id"]))
            db.commit()
            chain.append("TIER3_APPROVE", {
                "request": d["request_id"], "by": rec["user"],
                "requester": requester, "case": case_no,
                "plate_ref": frag_ref(frag), "basis_type": basis_type})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 approved search",
                "tier": 3, "case": case_no, "plate_ref": frag_ref(frag),
                "result_count": n, "via_request": d["request_id"],
                "emergency": False})
            # Item 19: the approver does NOT receive the results. The
            # requester retrieves them, and that retrieval is chained.
            return self.send_json(200, {
                "result": "EXECUTED", "request_id": d["request_id"],
                "results_count": n,
                "results_url": f"/tier3/results/{d['request_id']}"})
        if path == "/tier3/deny":
            row = db.execute(
                "SELECT requester, status FROM tier3_requests WHERE id=?",
                (d.get("request_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            if rec["role"] != "supervisor" and rec["user"] != row[0]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 deny",
                                         "reason": "role"})
                return self.send_json(403, {"error": "deny requires a "
                                                   "supervisor or the "
                                                   "requester"})
            if row[1] != "PENDING":
                return self.send_json(409, {"error": "request is not "
                                                   "pending"})
            db.execute(
                "UPDATE tier3_requests SET status='DENIED', decided_by=?, "
                "decided_ts=? WHERE id=?",
                (rec["user"], now_iso(), d["request_id"]))
            db.commit()
            chain.append("TIER3_DENY", {"request": d["request_id"],
                                        "by": rec["user"],
                                        "requester": row[0]})
            return self.send_json(200, {"result": "DENIED",
                                        "request_id": d["request_id"]})
        if path == "/tier3/emergency":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": "role"})
                return self.send_json(403, {"error": "the Tier 3 emergency "
                                                   "path is supervisor-only"})
            case_no = d.get("case_id", "")
            why = (d.get("why") or "").strip()
            frag, ferr = validate_fragment(d.get("plate_fragment"))
            basis = (d.get("auth_basis") or "").strip()
            basis_type = (d.get("basis_type") or "other").strip().lower()
            if basis_type not in BASIS_TYPES:
                return self.send_json(400, {
                    "error": "basis_type must be one of "
                             + ", ".join(BASIS_TYPES)})
            if not why:
                return self.send_json(400, {"error": "why is required"})
            if ferr:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": ferr})
                return self.send_json(400,
                                      {"error": FRAGMENT_MSGS[ferr]})
            if not basis:
                # Item 19: the emergency path requires auth_basis too —
                # exigency explains speed, not the absence of a basis.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": "no_basis"})
                return self.send_json(403, {"error": "BLOCKED: the "
                                                   "emergency path requires "
                                                   "auth_basis"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "case": case_no, "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            if config_status()["fail_closed"]:
                return self.send_json(503, {"error": "configuration has "
                                                   "been stale >24h — "
                                                   "search is closed until "
                                                   "a clean reload"})
            # Item 19: an unreviewed emergency older than 72h locks
            # the emergency path for that user until it is reviewed.
            stale = db.execute(
                "SELECT COUNT(*) FROM tier3_requests WHERE requester=? "
                "AND emergency=1 AND needs_review=1 AND created_ts < ?",
                (rec["user"], (datetime.now(timezone.utc)
                               - timedelta(hours=72)).strftime(
                                   "%Y-%m-%dT%H:%M:%SZ"))).fetchone()[0]
            if stale:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "reason": "unreviewed_emergency"})
                return self.send_json(403, {
                    "error": "BLOCKED: you have an unreviewed emergency "
                             "use older than 72 hours — it must be "
                             "reviewed before the emergency path opens "
                             "again"})
            results = run_search(frag, "full")
            n = len(results["reads"]) + len(results["hits"])
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, basis_type, status, "
                "created_ts, decided_by, decided_ts, emergency, "
                "needs_review, results_count, results) "
                "VALUES(?,?,?,?,?,?,'EMERGENCY',?,?,?,1,1,?,?)",
                (rec["user"], case_no, why, frag, basis, basis_type,
                 now_iso(), rec["user"], now_iso(), n,
                 json.dumps(results, sort_keys=True)))
            db.commit()
            chain.append("TIER3_EMERGENCY", {
                "request": cur.lastrowid, "by": rec["user"],
                "case": case_no, "plate_ref": frag_ref(frag),
                "basis_type": basis_type,
                "review": "mandatory post-hoc review queued"})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 emergency search",
                "tier": 3, "case": case_no, "plate_ref": frag_ref(frag),
                "result_count": n, "via_request": cur.lastrowid,
                "emergency": True})
            return self.send_json(200, {
                "result": "EXECUTED — flagged EMERGENCY, post-hoc "
                          "review queued",
                "request_id": cur.lastrowid, "results": results})
        if path == "/tier3/review":
            if rec["role"] not in ("supervisor", "auditor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 review",
                                         "reason": "role"})
                return self.send_json(403, {"error": "post-hoc review is "
                                                   "supervisor/auditor "
                                                   "only"})
            # Item 27: the finding is an enum — a bare "ok" is not a
            # review. The prose note stays in the DB (item 26).
            finding = (d.get("finding") or "").strip().lower()
            if finding not in REVIEW_FINDINGS:
                return self.send_json(400, {
                    "error": "finding must be one of "
                             + ", ".join(REVIEW_FINDINGS)})
            row = db.execute(
                "SELECT requester, needs_review FROM tier3_requests "
                "WHERE id=?", (d.get("request_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            if not row[1]:
                return self.send_json(409, {"error": "that use is not "
                                                   "awaiting review"})
            if rec["user"] == row[0]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 review",
                                         "request": d["request_id"],
                                         "reason": "own_use_review"})
                return self.send_json(403, {"error": "BLOCKED: you cannot "
                                                   "review your own "
                                                   "emergency use"})
            db.execute(
                "UPDATE tier3_requests SET status='REVIEWED', "
                "needs_review=0, review_finding=?, review_note=?, "
                "reviewed_by=?, reviewed_ts=? WHERE id=?",
                (finding, (d.get("note") or None), rec["user"],
                 now_iso(), d["request_id"]))
            db.commit()
            chain.append("TIER3_REVIEW", {"request": d["request_id"],
                                          "by": rec["user"],
                                          "finding": finding})
            return self.send_json(200, {"result": "REVIEWED",
                                        "request_id": d["request_id"]})
        return self.send_json(404, {"error": "no such route"})

    # ---------------- evidence lifecycle ----------------
    def _evidence_post(self, path, rec):
        d = self.body_json()
        if path == "/evidence/export":
            if rec["role"] not in ("detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot export "
                                                   "evidence"})
            case_no = d.get("case_id", "")
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": d.get("hit_id"),
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            hit = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,list_name,"
                "category,status,decided_by,case_no,decided_ts FROM hits "
                "WHERE id=?", (d.get("hit_id"),)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no such hit"})
            hkeys = ("id", "ts", "cam", "read_plate", "entry_plate",
                     "state", "list_name", "category", "status",
                     "decided_by", "case_no", "decided_ts")
            hit_rec = dict(zip(hkeys, hit))
            # Item 9: only a VERIFIED hit is evidence, and only under
            # the case it was verified under.
            if hit_rec["status"] != "VERIFIED":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit[0],
                                         "reason": "hit_not_verified"})
                return self.send_json(409, {
                    "error": "evidence export requires a VERIFIED hit "
                             "(status: %s)" % hit_rec["status"]})
            if hit_rec["case_no"] != case_no:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit[0],
                                         "reason": "case_mismatch"})
                return self.send_json(403, {
                    "error": "case_id does not match the case the hit "
                             "was verified under"})
            # Scope: the hit plus reads of the same plate within
            # +/- 1 hour. A supervisor may expand to full history only
            # with an explicit reason (kept in the DB, not the chain).
            expand = bool(d.get("expand"))
            reason_txt = (d.get("reason") or "").strip()
            if expand and rec["role"] != "supervisor":
                return self.send_json(403, {"error": "expansion beyond "
                                                   "the +/-1h window is "
                                                   "supervisor-only"})
            if expand and not reason_txt:
                return self.send_json(400, {"error": "expand requires a "
                                                   "reason"})
            plates = {hit[3], hit[4]}
            if expand:
                read_rows = db.execute(
                    "SELECT id,ts,cam,plate,state,conf,cam_ts,skew_s "
                    "FROM reads WHERE plate IN (%s) ORDER BY ts"
                    % ",".join("?" * len(plates)), tuple(plates)).fetchall()
                scope = "full"
            else:
                hit_dt = parse_ts(hit[1])
                lo = (hit_dt - timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                hi = (hit_dt + timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                read_rows = db.execute(
                    "SELECT id,ts,cam,plate,state,conf,cam_ts,skew_s "
                    "FROM reads WHERE plate IN (%s) AND ts>=? AND ts<=? "
                    "ORDER BY ts" % ",".join("?" * len(plates)),
                    (*plates, lo, hi)).fetchall()
                scope = "window_1h"
            reads = [dict(zip(("id", "ts", "cam", "plate", "state",
                               "conf", "cam_ts", "skew_s"), r))
                     for r in read_rows]
            outcome = db.execute(
                "SELECT hit_id,list_name,category,confirmed,arrest,"
                "prosecution,updated_by,updated_ts,hit_ts FROM outcomes "
                "WHERE hit_id=?", (hit[0],)).fetchone()
            outcome_rec = (dict(zip(
                ("hit_id", "list_name", "category", "confirmed", "arrest",
                 "prosecution", "updated_by", "updated_ts", "hit_ts"),
                outcome)) if outcome else None)
            excerpt = custody_excerpt(hit[0])
            os.makedirs(EVIDENCE_DIR, mode=0o700, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bundle_name = "hit-%d-%s" % (hit[0], stamp)
            bundle_path = os.path.join(EVIDENCE_DIR, bundle_name)
            # exist_ok: a re-export inside the same second reuses the
            # bundle directory and rewrites its files.
            os.makedirs(bundle_path, mode=0o700, exist_ok=True)
            files = {}

            def put(name, obj):
                data = json.dumps(obj, indent=1, sort_keys=True).encode()
                p = os.path.join(bundle_path, name)
                with open(p, "wb") as f:
                    f.write(data)
                os.chmod(p, 0o600)
                files[name] = hashlib.sha256(data).hexdigest()

            put("hit.json", hit_rec)
            put("reads.json", reads)
            put("outcome.json", outcome_rec)
            put("audit-excerpt.json", excerpt)
            manifest = {"hit_id": hit[0], "case_no": case_no,
                        "exported_by": rec["user"],
                        "exported_ts": now_iso(), "scope": scope,
                        "files": files}
            mhash = sha(json.dumps(manifest, sort_keys=True,
                                   separators=(",", ":")))
            manifest["manifest_hash"] = mhash
            put("manifest.json", manifest)
            db.execute(
                "INSERT INTO evidence(hit_id, export_ts, export_by, "
                "manifest_hash, bundle, scope, expand_reason) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(hit_id) DO UPDATE "
                "SET export_ts=excluded.export_ts, "
                "export_by=excluded.export_by, "
                "manifest_hash=excluded.manifest_hash, "
                "bundle=excluded.bundle, scope=excluded.scope, "
                "expand_reason=excluded.expand_reason, "
                "destroyed_ts=NULL, destroyed_by=NULL",
                (hit[0], manifest["exported_ts"], rec["user"], mhash,
                 bundle_name, scope, reason_txt or None))
            db.commit()
            chain.append("EVIDENCE_EXPORT", {
                "hit": hit[0], "case": case_no, "manifest": mhash,
                "scope": scope, "expanded": expand, "by": rec["user"]})
            return self.send_json(201, {"result": "exported",
                                        "bundle": bundle_name,
                                        "manifest_hash": mhash,
                                        "scope": scope, "files": files})
        if path == "/evidence/release":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "evidence release is "
                                                   "supervisor-only"})
            so = d.get("prosecutor_signoff") or {}
            pname = (so.get("name") or d.get("prosecutor_name")
                     or "").strip()
            pdate = (so.get("date") or d.get("prosecutor_date")
                     or "").strip()
            if not pname or not pdate:
                return self.send_json(400, {
                    "error": "prosecutor_signoff with name and date is "
                             "required"})
            if not db.execute("SELECT 1 FROM hits WHERE id=?",
                              (d.get("hit_id"),)).fetchone():
                return self.send_json(404, {"error": "no such hit"})
            ev = db.execute("SELECT export_ts FROM evidence WHERE "
                            "hit_id=?", (d.get("hit_id"),)).fetchone()
            if not ev or not ev[0]:
                # Item 9: there is nothing to release until an export
                # exists — a sign-off cannot precede the evidence.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence release",
                                         "hit": d.get("hit_id"),
                                         "reason": "no_export"})
                return self.send_json(409, {
                    "error": "no export exists for that hit — release "
                             "requires an export first"})
            db.execute(
                "UPDATE evidence SET prosecutor_name=?, "
                "prosecutor_date=?, released_by=?, released_ts=? "
                "WHERE hit_id=?",
                (pname, pdate, rec["user"], now_iso(), d["hit_id"]))
            db.commit()
            chain.append("EVIDENCE_RELEASE", {"hit": d["hit_id"],
                                              "by": rec["user"]})
            return self.send_json(200, {"result": "released",
                                        "hit": d["hit_id"]})
        if path == "/evidence/destroy":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence destroy",
                                         "reason": "role"})
                return self.send_json(403, {"error": "evidence destruction "
                                                   "is supervisor-only"})
            ev = db.execute(
                "SELECT bundle, released_ts, disp_confirmed_ts, "
                "destroyed_ts FROM evidence WHERE hit_id=?",
                (d.get("hit_id"),)).fetchone()
            if not ev or not ev[0]:
                return self.send_json(404, {"error": "no export bundle "
                                                   "for that hit"})
            if ev[3]:
                return self.send_json(409, {"error": "bundle already "
                                                   "destroyed"})
            if not ev[1] and not ev[2]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence destroy",
                                         "hit": d.get("hit_id"),
                                         "reason": "not_released"})
                return self.send_json(409, {
                    "error": "destruction requires a release (prosecutor "
                             "sign-off or a confirmed disposition) first"})
            bundle_path = os.path.join(EVIDENCE_DIR, ev[0])
            if os.path.isdir(bundle_path):
                shutil.rmtree(bundle_path)
            db.execute("UPDATE evidence SET destroyed_ts=?, "
                       "destroyed_by=? WHERE hit_id=?",
                       (now_iso(), rec["user"], d["hit_id"]))
            db.commit()
            # Item 9: verified destruction is itself a custody event.
            chain.append("EVIDENCE_DESTROY", {"hit": d["hit_id"],
                                              "by": rec["user"]})
            return self.send_json(200, {"result": "bundle destroyed",
                                        "hit": d["hit_id"]})
        if path == "/evidence/disposition":
            if rec["role"] not in ("detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence disposition",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot record "
                                                   "dispositions"})
            outcome = (d.get("outcome") or "").strip()
            if outcome not in ("no_charges", "charges_concluded"):
                return self.send_json(400, {
                    "error": "outcome must be 'no_charges' or "
                             "'charges_concluded'"})
            hit = db.execute("SELECT id FROM hits WHERE id=?",
                             (d.get("hit_id"),)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no such hit"})
            # Item 10: SS 12-12-1804(b) has two exits — charges that
            # concluded, and an investigation that never became charges.
            # A disposition records the second (and the conclusion of
            # the first) and, once CONFIRMED by a different supervisor,
            # releases the data for deletion exactly as a prosecutor
            # sign-off does. Free text (by/date/note) stays in the DB.
            db.execute(
                "INSERT INTO evidence(hit_id, disp_outcome, disp_by, "
                "disp_date, disp_note, disp_posted_by, "
                "disp_confirmed_by, disp_confirmed_ts) "
                "VALUES(?,?,?,?,?,?,NULL,NULL) ON CONFLICT(hit_id) DO "
                "UPDATE SET disp_outcome=excluded.disp_outcome, "
                "disp_by=excluded.disp_by, disp_date=excluded.disp_date, "
                "disp_note=excluded.disp_note, "
                "disp_posted_by=excluded.disp_posted_by, "
                "disp_confirmed_by=NULL, disp_confirmed_ts=NULL",
                (d["hit_id"], outcome, (d.get("by") or "").strip(),
                 (d.get("date") or "").strip(), d.get("note"),
                 rec["user"]))
            db.commit()
            chain.append("EVIDENCE_DISPOSITION", {
                "hit": d["hit_id"], "outcome": outcome, "by": rec["user"],
                "status": "awaiting confirmation"})
            return self.send_json(201, {
                "result": "disposition recorded — a different supervisor "
                          "must confirm it before it releases anything",
                "hit": d["hit_id"]})
        if path == "/evidence/disposition/confirm":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "disposition confirm",
                                         "reason": "role"})
                return self.send_json(403, {"error": "disposition "
                                                   "confirmation is "
                                                   "supervisor-only"})
            row = db.execute(
                "SELECT disp_outcome, disp_posted_by, disp_confirmed_ts "
                "FROM evidence WHERE hit_id=?",
                (d.get("hit_id"),)).fetchone()
            if not row or not row[0]:
                return self.send_json(404, {"error": "no disposition on "
                                                   "file for that hit"})
            if row[2]:
                return self.send_json(409, {"error": "disposition already "
                                                   "confirmed"})
            if rec["user"] == row[1]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "disposition confirm",
                                         "hit": d.get("hit_id"),
                                         "reason": "two_key"})
                return self.send_json(403, {
                    "error": "BLOCKED: the two-key rule forbids "
                             "confirming a disposition you posted"})
            db.execute("UPDATE evidence SET disp_confirmed_by=?, "
                       "disp_confirmed_ts=? WHERE hit_id=?",
                       (rec["user"], now_iso(), d["hit_id"]))
            db.commit()
            chain.append("EVIDENCE_DISPOSITION_CONFIRM", {
                "hit": d["hit_id"], "outcome": row[0], "by": rec["user"]})
            return self.send_json(200, {"result": "disposition confirmed "
                                                  "— data released for "
                                                  "deletion",
                                        "hit": d["hit_id"]})
        return self.send_json(404, {"error": "no such route"})

    # ---------------- the Compact (items 21-22, 35) ----------------
    def _compact_post(self, path, rec):
        d = self.body_json()
        if path == "/compact/partners":
            if rec["role"] != "supervisor":
                return self.send_json(403, {"error": "partner registration "
                                                   "is supervisor-only"})
            agency = (d.get("agency") or "").strip()
            if not agency:
                return self.send_json(400, {"error": "agency is required"})
            db.execute(
                "INSERT INTO partners(agency, endpoint, "
                "audit_key_fingerprint, agreement_ref, status, added_by, "
                "added_ts) VALUES(?,?,?,?, 'active', ?,?) "
                "ON CONFLICT(agency) DO UPDATE SET "
                "endpoint=excluded.endpoint, "
                "audit_key_fingerprint=excluded.audit_key_fingerprint, "
                "agreement_ref=excluded.agreement_ref",
                (agency, d.get("endpoint"), d.get("audit_key_fingerprint"),
                 d.get("agreement_ref"), rec["user"], now_iso()))
            db.commit()
            chain.append("COMPACT_PARTNER_ADD", {"agency": agency,
                                                 "by": rec["user"]})
            return self.send_json(201, {"result": "partner registered",
                                        "agency": agency})
        if path == "/compact/checkpoint-receipt":
            # A partner attests: "we audited your chain and your
            # published checkpoint is genuine." The receipt is accepted
            # only if the (root, entries) it names is a checkpoint WE
            # actually published — a receipt for a checkpoint that does
            # not exist attests nothing.
            if rec["role"] != "partner":
                return self.send_json(403, {"error": "receipts come from "
                                                   "partner accounts"})
            agency = (d.get("agency") or "").strip()
            if rec["user"] != agency:
                return self.send_json(403, {"error": "a partner account "
                                                   "receipts only for "
                                                   "its own agency"})
            root, entries = d.get("root"), d.get("entries")
            known = False
            if os.path.exists(CHECKPOINTS_PATH):
                with open(CHECKPOINTS_PATH) as f:
                    for line in f:
                        if not line.strip():
                            continue
                        cp = json.loads(line)
                        if cp.get("root") == root \
                                and cp.get("entries") == entries:
                            known = True
                            break
            if not known:
                chain.append("RECEIPT_REJECTED", {
                    "agency": agency, "reason": "checkpoint_mismatch"})
                return self.send_json(400, {
                    "error": "that (root, entries) pair is not a "
                             "checkpoint we published"})
            db.execute(
                "INSERT INTO compact_receipts(agency, root, entries, "
                "sig, received_ts) VALUES(?,?,?,?,?)",
                (agency, root, entries, d.get("sig"), now_iso()))
            db.commit()
            chain.append("CHECKPOINT_RECEIPT", {
                "agency": agency, "entries": entries,
                "root": (root or "")[:16]})
            return self.send_json(201, {"result": "receipt recorded",
                                        "agency": agency})
        if path == "/compact/audit-result":
            # scripts/compact.py records the outcome of OUR audit of a
            # partner here — this is the leg the sharing gate reads.
            if rec["role"] not in ("jobs", "supervisor"):
                return self.send_json(403, {"error": "audit results are "
                                                   "recorded by the jobs "
                                                   "role or a supervisor"})
            agency = (d.get("agency") or "").strip()
            if not db.execute("SELECT 1 FROM partners WHERE agency=?",
                              (agency,)).fetchone():
                return self.send_json(404, {"error": "no such partner"})
            ok = d.get("ok") is True
            db.execute(
                "INSERT INTO compact_audits(agency, ok, detail, "
                "report_hash, ts) VALUES(?,?,?,?,?)",
                (agency, 1 if ok else 0,
                 str(d.get("detail", ""))[:300], d.get("report_hash"),
                 now_iso()))
            db.commit()
            chain.append("CROSS_AUDIT_OK" if ok else "CROSS_AUDIT_FAIL",
                         {"agency": agency, "by": rec["user"]})
            return self.send_json(201, {"result": "audit result recorded",
                                        "agency": agency, "ok": ok})
        if path == "/compact/suspend":
            if rec["role"] != "supervisor":
                return self.send_json(403, {"error": "suspension is "
                                                   "supervisor-only"})
            agency = (d.get("agency") or "").strip()
            cur = db.execute("UPDATE partners SET status='suspended' "
                             "WHERE agency=?", (agency,))
            db.commit()
            if not cur.rowcount:
                return self.send_json(404, {"error": "no such partner"})
            # Suspension takes effect on the very next share attempt —
            # the gate reads the partners table every time.
            chain.append("COMPACT_SUSPEND", {"agency": agency,
                                             "by": rec["user"]})
            return self.send_json(200, {"result": "partner suspended — "
                                                  "sharing is blocked",
                                        "agency": agency})
        if path == "/compact/reinstate":
            if rec["role"] != "supervisor":
                return self.send_json(403, {"error": "reinstatement is "
                                                   "supervisor-only"})
            agency = (d.get("agency") or "").strip()
            cur = db.execute("UPDATE partners SET status='active' "
                             "WHERE agency=?", (agency,))
            db.commit()
            if not cur.rowcount:
                return self.send_json(404, {"error": "no such partner"})
            chain.append("COMPACT_REINSTATE", {"agency": agency,
                                               "by": rec["user"]})
            return self.send_json(200, {"result": "partner reinstated",
                                        "agency": agency})
        if path == "/compact/rotation":
            if rec["role"] != "supervisor":
                return self.send_json(403, {"error": "rotation "
                                                   "publication is "
                                                   "supervisor-only"})
            cycle_start = (d.get("cycle_start") or "").strip()
            schedule = d.get("schedule")
            if not cycle_start or not isinstance(schedule, dict):
                return self.send_json(400, {"error": "cycle_start and "
                                                   "schedule are required"})
            # Item 35: a published schedule is accepted ONLY if it
            # recomputes exactly from the deterministic function of
            # (cycle_start, sorted member list, period). Nobody gets
            # to hand the compact a friendlier rotation.
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "scripts"))
            import rotation as rotation_mod
            members = schedule.get("members") or []
            period = int(schedule.get("period_days") or
                         rotation_mod.DEFAULT_PERIOD_DAYS)
            expected = rotation_mod.build_schedule(
                members, cycle_start, period)
            canon = lambda o: json.dumps(  # noqa: E731
                {k: v for k, v in o.items() if k != "sig"},
                sort_keys=True, separators=(",", ":"))
            if canon(expected) != canon(schedule):
                chain.append("ROTATION_REJECTED", {
                    "cycle": cycle_start, "by": rec["user"],
                    "reason": "schedule_mismatch"})
                return self.send_json(400, {
                    "error": "schedule does not recompute from the "
                             "seed — rejected"})
            sched_hash = sha(canon(schedule))
            db.execute(
                "INSERT INTO rotation_schedules(cycle_start, "
                "period_days, members_count, schedule_hash, schedule, "
                "published_by, published_ts) VALUES(?,?,?,?,?,?,?)",
                (cycle_start, period, len(members), sched_hash,
                 json.dumps(schedule, sort_keys=True), rec["user"],
                 now_iso()))
            db.commit()
            chain.append("ROTATION_PUBLISHED", {
                "cycle": cycle_start, "schedule_hash": sched_hash,
                "members_count": len(members), "by": rec["user"]})
            return self.send_json(201, {"result": "rotation published",
                                        "schedule_hash": sched_hash})
        if path == "/share/query":
            return self._share_query(rec)
        return self.send_json(404, {"error": "no such route"})

    def _share_query(self, rec):
        """Reciprocal-audit data sharing (item 22). The gate has three
        legs and ALL of them are read fresh from the tables on every
        call: (a) the partner is active, (b) OUR audit of THEM passed
        within 26h, (c) THEIR receipt for OUR checkpoint landed within
        26h. Missing any leg: 403 SHARE_BLOCKED naming the leg, and the
        refusal is chained. No cross-audit, no data — in both
        directions, enforced by the software, not by trust."""
        d = self.body_json()
        agency = (d.get("agency") or "").strip()

        def blocked(missing):
            chain.append("SHARE_BLOCKED", {"agency": agency,
                                           "missing": missing})
            return self.send_json(403, {"error": "SHARE_BLOCKED",
                                        "missing": missing,
                                        "agency": agency})
        if rec["role"] != "partner" or rec["user"] != agency:
            return blocked("partner_identity")
        prow = db.execute("SELECT status FROM partners WHERE agency=?",
                          (agency,)).fetchone()
        if not prow or prow[0] != "active":
            return blocked("partner_inactive")
        fresh = (datetime.now(timezone.utc)
                 - timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ")
        our_audit = db.execute(
            "SELECT COUNT(*) FROM compact_audits WHERE agency=? "
            "AND ok=1 AND ts>=?", (agency, fresh)).fetchone()[0]
        if not our_audit:
            return blocked("cross_audit_ok")
        their_receipt = db.execute(
            "SELECT COUNT(*) FROM compact_receipts WHERE agency=? "
            "AND received_ts>=?", (agency, fresh)).fetchone()[0]
        if not their_receipt:
            return blocked("checkpoint_receipt")
        why = (d.get("why") or "").strip()
        if not why:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "reason": "no_justification"})
            return self.send_json(403, {"error": "BLOCKED: share queries "
                                                   "require a "
                                                   "justification (why)"})
        case_ref = (d.get("case_ref") or "").strip()
        if any(p in case_ref.upper() for p in BANNED_CASE_PATTERNS):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "reason": "case_banned"})
            return self.send_json(403, {"error": CASE_GATE_MSGS[
                "case_banned"]})
        frag, ferr = validate_fragment(d.get("plate_fragment"))
        if ferr:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "reason": ferr})
            return self.send_json(400, {"error": FRAGMENT_MSGS[ferr]})
        try:
            tier = int(d.get("tier", 2))
        except (TypeError, ValueError):
            return self.send_json(400, {"error": "tier must be 2 or 3"})
        if tier not in (2, 3):
            return self.send_json(400, {"error": "tier must be 2 or 3"})
        # The partner's case_ref is THEIR reference — it is recorded
        # as such, never validated against our case list (we cannot
        # validate another agency's cases; the Compact's audit is what
        # vouches for their gatekeeping). Suppression rules and the
        # Tier 2 temporal wall apply identically.
        results = run_search(frag, "tier2" if tier == 2 else "full")
        n = len(results["reads"]) + len(results["hits"])
        chain.append("SHARE_OUT", {
            "agency": agency, "case_ref": case_ref,
            "plate_ref": frag_ref(frag), "tier": tier, "result_count": n})
        return self.send_json(200, {"agency": agency, "tier": tier,
                                    "results": results})

    # ---------------- DELETE ----------------
    def do_DELETE(self):
        self._resp = None
        if not self._read_body():
            return
        with DBLOCK:
            try:
                self._delete()
            except Exception as exc:
                self._resp = (500, {"error": f"internal: {exc}"})
        self._flush_response()

    def _delete(self):
        path = urlparse(self.path).path
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        if path.startswith("/hotlist/"):
            if rec["role"] not in ("detective", "supervisor"):
                return self.send_json(403, {"error": "role cannot remove "
                                                   "entries"})
            plate = normalize_plate(path.split("/", 2)[2])
            q = parse_qs(urlparse(self.path).query)
            state = (q.get("state", [""])[0] or "").upper()
            if state:
                targets = [(plate, state)]
            else:
                targets = db.execute(
                    "SELECT plate, state FROM hotlist WHERE plate=? "
                    "AND active=1", (plate,)).fetchall()
            removed = []
            for p, s in targets:
                cur = db.execute("UPDATE hotlist SET active=0 WHERE "
                                 "plate=? AND state=? AND active=1",
                                 (p, s))
                if cur.rowcount:
                    removed.append((p, s))
            db.commit()
            # Chained after the commit (lock ordering — the chain
            # writes through its own connection).
            for p, s in removed:
                chain.append("HOTLIST_REMOVE", {
                    "plate_ref": plate_ref(p, s), "by": rec["user"]})
            n = len(removed)
            return self.send_json(200, {"result": "deactivated",
                                        "entries": n})
        return self.send_json(404, {"error": "no such route"})

    # ---------------- GET ----------------
    def do_GET(self):
        self._resp = None
        with DBLOCK:
            try:
                self._get()
            except Exception as exc:
                self._resp = (500, {"error": f"internal: {exc}"})
        self._flush_response()

    def _get(self):
        path = urlparse(self.path).path
        if path == "/health":
            _backfill_flush_idle()
            jobs, _overdue_jobs = jobs_status()
            cams_map, cams_silent = cameras_status()
            cams = {"cameras": cams_map, "silent": cams_silent}
            _cs = config_status()
            cs = {"stale": any(v.get("stale") for k, v in _cs.items()
                               if isinstance(v, dict)),
                  "stale_since": next(
                      (v["stale_since"] for k, v in _cs.items()
                       if isinstance(v, dict) and v.get("stale")), None),
                  "fail_closed": _cs["fail_closed"]}
            sink_st = chain.sink_status()
            # A disabled sink is not a failure; an enabled one that is
            # erroring (entries spooling) degrades health (item 24).
            sink_ok = (not sink_st["enabled"]) or sink_st["ok"]
            am = anchor_mismatch()
            oldest_age = retention_oldest_read_age_h()
            # Item 8: retention is cross-checked directly, not trusted
            # from the retention job's own say-so. One day of grace
            # past the policy before it counts as degradation.
            retention_breach = (oldest_age is not None
                                and oldest_age > RETENTION_DAYS * 24 + 26)
            degraded = (any(j["overdue"] or not j["ok"]
                            for j in jobs.values())
                        or not sink_ok or am or cs["stale"]
                        or bool(cams["silent"]) or retention_breach)
            body = {"version": VERSION, "chain_entries": chain.count(),
                    "chain_ok": chain.verify()["ok"],
                    "sentinel_sink_ok": sink_ok,
                    "sink_errors": sink_st["errors"],
                    "sink_spooled": sink_st["spooled"],
                    "anchor_mismatch": am,
                    "config_stale": cs["stale"],
                    "config_stale_since": cs["stale_since"],
                    "retention_days": RETENTION_DAYS,
                    "hold_days": HOLD_DAYS,
                    "tier2_window_h": TIER2_WINDOW_H,
                    "retention_oldest_read_age_h": oldest_age,
                    "cameras": cams["cameras"],
                    "cameras_silent": cams["silent"],
                    "overdue_holds": len(overdue_holds()),
                    "jobs": jobs, "degraded": degraded,
                    "ok": (not degraded) and (not KEY_LOCKED)}
            if KEY_LOCKED:
                body["key_missing"] = True
            return self.send_json(200, body)
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        q = parse_qs(urlparse(self.path).query)
        if path in ("/audit/verify", "/audit/root"):
            # Item 25: these were unauthenticated in 1.0 and could
            # stall ingest under the lock; they now require a role
            # that has business reading the chain's state.
            if rec["role"] not in ("auditor", "supervisor"):
                return self.send_json(403, {"error": "chain state is "
                                                   "auditor/supervisor "
                                                   "only"})
            if path == "/audit/verify":
                chain.append("AUDIT_VERIFY", {"by": rec["user"]})
                return self.send_json(200, {"ok": chain.verify()["ok"],
                                            "entries": chain.count()})
            root, n = chain.root(), chain.count()
            chain.append("AUDIT_ROOT_VIEW", {"by": rec["user"]})
            return self.send_json(200, {"root": root, "entries": n})
        if path == "/audit":
            if rec["role"] not in ("detective", "supervisor", "auditor"):
                return self.send_json(403, {"error": "role cannot read "
                                                   "the audit chain"})
            raw_limit = q.get("limit", ["200"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                limit = 200
            # Item 25: clamped both ways — limit=-1 meant "all rows"
            # to SQLite in 1.0.
            limit = max(1, min(1000, limit))
            if q.get("seq"):
                try:
                    entry = chain.entry_at_seq(int(q["seq"][0]))
                except ValueError:
                    return self.send_json(400, {"error": "seq must be a "
                                                       "number"})
                chain.append("AUDIT_VIEW", {"by": rec["user"], "seq": True})
                if entry is None:
                    return self.send_json(404, {"error": "no such entry"})
                return self.send_json(200, {"entry": entry})
            chain.append("AUDIT_VIEW", {"by": rec["user"], "limit": limit})
            rows = db.execute(
                "SELECT seq,ts,kind,payload,hash FROM audit ORDER BY "
                "seq DESC LIMIT ?", (limit,)).fetchall()
            out = [{"seq": r[0], "ts": r[1], "kind": r[2],
                    "payload": json.loads(r[3]), "hash": r[4]}
                   for r in rows]
            return self.send_json(200, {"entries": out})
        if path == "/search":
            return self._search_get(rec, q)
        if path == "/hits":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "/hits")
            suppressed = active_suppression_refs()
            rows = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,list_name,"
                "category,status,decided_by,case_no FROM hits "
                "WHERE suppressed=0 ORDER BY id DESC LIMIT 200").fetchall()
            # Item 5 belt-and-braces: even if the ingest-time flag
            # missed one, a hit whose plate is suppressed NOW never
            # leaves through this door.
            rows = [r for r in rows
                    if plate_ref(r[3], r[5]) not in suppressed]
            hits = [dict(zip(("id", "ts", "cam", "read_plate",
                              "entry_plate", "state", "list_name",
                              "category", "status", "decided_by",
                              "case_no"), r)) for r in rows]
            chain.append("HITS_VIEW", {"by": rec["user"],
                                       "count": len(hits)})
            return self.send_json(200, {"hits": hits})
        if path == "/suppressed-hits":
            # Item 5: THE disclosure path for suppressed plates —
            # supervisor-only, and the view itself is chained.
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppressed hits view",
                                         "reason": "role"})
                return self.send_json(403, {"error": "the suppressed-hit "
                                                   "queue is supervisor-"
                                                   "only"})
            rows = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,list_name,"
                "category,status,decided_by,case_no FROM hits "
                "WHERE suppressed=1 ORDER BY id DESC LIMIT 200").fetchall()
            hits = [dict(zip(("id", "ts", "cam", "read_plate",
                              "entry_plate", "state", "list_name",
                              "category", "status", "decided_by",
                              "case_no"), r)) for r in rows]
            for h in hits:
                h["suppressed"] = True
            chain.append("SUPPRESSED_HITS_VIEW", {"by": rec["user"],
                                                  "count": len(hits)})
            return self.send_json(200, {"hits": hits})
        if path == "/hotlist":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "/hotlist")
            rows = db.execute(
                "SELECT plate,state,case_no,category,expires_ts,"
                "list_name FROM hotlist WHERE active=1 ORDER BY plate"
            ).fetchall()
            entries = [dict(zip(("plate", "state", "case_no", "category",
                                 "expires_ts", "list_name"), r))
                       for r in rows]
            chain.append("HOTLIST_VIEW", {"by": rec["user"],
                                          "count": len(entries)})
            return self.send_json(200, {"hotlist": entries})
        if path == "/stats":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "/stats")
            chain.append("STATS_VIEW", {"by": rec["user"]})
            stats = {
                "reads": db.execute("SELECT COUNT(*) FROM reads"
                                    ).fetchone()[0],
                "hits": db.execute("SELECT COUNT(*) FROM hits"
                                   ).fetchone()[0],
                "pending": db.execute(
                    "SELECT COUNT(*) FROM hits WHERE status='PENDING'"
                ).fetchone()[0],
                "suppressed_pending": db.execute(
                    "SELECT COUNT(*) FROM hits WHERE suppressed=1 "
                    "AND status='PENDING'").fetchone()[0],
                "backfill_pending": {
                    cam: b["count"] for (cam, _h), b
                    in _backfill.items()},
                "suppressions": db.execute(
                    "SELECT COUNT(*) FROM suppressions WHERE active=1"
                ).fetchone()[0],
            }
            return self.send_json(200, stats)
        if path == "/report":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "/report")
            if q.get("snapshot"):
                row = db.execute(
                    "SELECT body FROM report_snapshots WHERE id=?",
                    (q["snapshot"][0],)).fetchone()
                if not row:
                    return self.send_json(404, {"error": "no such "
                                                       "snapshot"})
                chain.append("REPORT_VIEW", {"by": rec["user"],
                                             "snapshot": int(
                                                 q["snapshot"][0])})
                return self.send_json(200, json.loads(row[0]))
            chain.append("REPORT_VIEW", {"by": rec["user"]})
            return self.send_json(200, compute_report(
                q.get("from", [""])[0],
                q.get("to", ["9999-12-31T23:59:59Z"])[0]))
        if path.startswith("/tier3/results/"):
            return self._tier3_results_get(rec, path)
        if path == "/tier3/pending":
            # Item 28: a detective sees only their own requests;
            # supervisors and the auditor see the queue.
            if rec["role"] not in ("detective", "patrol", "supervisor",
                                   "auditor"):
                return self.deny_service_role(rec, "/tier3/pending")
            if rec["role"] in ("supervisor", "auditor"):
                rows = db.execute(
                    "SELECT id,requester,case_no,why,status,created_ts,"
                    "emergency,needs_review FROM tier3_requests WHERE "
                    "status='PENDING' ORDER BY id").fetchall()
            else:
                rows = db.execute(
                    "SELECT id,requester,case_no,why,status,created_ts,"
                    "emergency,needs_review FROM tier3_requests WHERE "
                    "status='PENDING' AND requester=? ORDER BY id",
                    (rec["user"],)).fetchall()
            reqs = [dict(zip(("id", "requester", "case_no", "why",
                              "status", "created_ts", "emergency",
                              "needs_review"), r)) for r in rows]
            return self.send_json(200, {"pending": reqs})
        if path == "/tier3/pending-reviews":
            if rec["role"] not in ("supervisor", "auditor", "detective",
                                   "patrol"):
                return self.deny_service_role(rec, "/tier3/pending-reviews")
            if rec["role"] in ("supervisor", "auditor"):
                rows = db.execute(
                    "SELECT id,requester,case_no,why,status,created_ts "
                    "FROM tier3_requests WHERE emergency=1 AND "
                    "needs_review=1 ORDER BY id").fetchall()
            else:
                rows = db.execute(
                    "SELECT id,requester,case_no,why,status,created_ts "
                    "FROM tier3_requests WHERE emergency=1 AND "
                    "needs_review=1 AND requester=? ORDER BY id",
                    (rec["user"],)).fetchall()
            reqs = [dict(zip(("id", "requester", "case_no", "why",
                              "status", "created_ts"), r)) for r in rows]
            return self.send_json(200, {"pending_reviews": reqs})
        if path == "/compact/partners":
            if rec["role"] not in ("supervisor", "auditor"):
                return self.send_json(403, {"error": "partner list is "
                                                   "supervisor/auditor "
                                                   "only"})
            rows = db.execute(
                "SELECT agency,endpoint,audit_key_fingerprint,"
                "agreement_ref,status,added_by,added_ts FROM partners "
                "ORDER BY agency").fetchall()
            out = [dict(zip(("agency", "endpoint",
                             "audit_key_fingerprint", "agreement_ref",
                             "status", "added_by", "added_ts"), r))
                   for r in rows]
            return self.send_json(200, {"partners": out})
        if path == "/compact/checkpoint":
            # A partner (or auditor/supervisor) reads our newest
            # published checkpoint line — the input to their audit.
            if rec["role"] not in ("partner", "auditor", "supervisor"):
                return self.send_json(403, {"error": "checkpoints are "
                                                   "for partners and "
                                                   "auditors"})
            if not os.path.exists(CHECKPOINTS_PATH):
                return self.send_json(404, {"error": "no checkpoint "
                                                   "published yet"})
            last = None
            with open(CHECKPOINTS_PATH) as f:
                for line in f:
                    if line.strip():
                        last = line
            if last is None:
                return self.send_json(404, {"error": "no checkpoint "
                                                   "published yet"})
            return self.send_json(200, {"checkpoint": json.loads(last)})
        if path == "/compact/rotation/status":
            return self._rotation_status(rec)
        return self.send_json(404, {"error": "no such route"})

    def _search_get(self, rec, q):
        if rec["role"] not in ("detective", "patrol", "supervisor",
                               "auditor"):
            return self.deny_service_role(rec, "/search")
        if rec["role"] == "auditor":
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "auditor_read_only"})
            return self.send_json(403, {"error": "auditors verify the "
                                               "system; they do not "
                                               "search it"})
        # Item 29: a non-numeric tier is a 400, never a 500.
        raw_tier = q.get("tier", ["2"])[0]
        try:
            tier = int(raw_tier)
        except (TypeError, ValueError):
            return self.send_json(400, {"error": "tier must be numeric"})
        if tier == 3:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "tier3_two_key"})
            return self.send_json(403, {"error": "Tier 3 search is not "
                                               "available at this "
                                               "endpoint — use /tier3/"
                                               "request or /tier3/"
                                               "emergency"})
        if tier != 2:
            # Item 1: /search is Tier 2 and only Tier 2.
            return self.send_json(400, {"error": "tier must be 2 at "
                                               "this endpoint"})
        # 'why' is the 1.0 parameter name; 'justification' is kept
        # as an accepted alias so both spellings work.
        justification = (q.get("why", [""])[0]
                         or q.get("justification", [""])[0]).strip()
        if not justification:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "no_justification"})
            return self.send_json(403, {"error": "BLOCKED: a plate search "
                                               "requires a justification"})
        case_no = q.get("case", [""])[0]
        ok, reason = janus_gate(rec, case_no)
        if not ok:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": reason})
            return self.send_json(403, {"error": CASE_GATE_MSGS.get(
                reason, "BLOCKED: role cannot search")})
        frag, ferr = validate_fragment(q.get("plate", [""])[0])
        if ferr:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": ferr})
            return self.send_json(400, {"error": FRAGMENT_MSGS[ferr]})
        if config_status()["fail_closed"]:
            return self.send_json(503, {"error": "configuration has been "
                                               "stale >24h — search is "
                                               "closed until a clean "
                                               "reload"})
        if case_no:
            # Pattern signal (schema: case_searches is a per-day
            # (case, fragment) ledger; case_flags marks a case's
            # first use each day). A case that suddenly starts
            # searching — or starts on a new fragment — leaves a
            # CASE_FLAG in the chain.
            day = now_iso()[:10]
            # Commit BEFORE chaining: the chain writes through its own
            # connection, and an uncommitted write here would block
            # its BEGIN IMMEDIATE (lock ordering, item 33's spirit).
            new_case = db.execute(
                "INSERT OR IGNORE INTO case_flags(case_no, day) "
                "VALUES(?,?)", (case_no, day)).rowcount
            new_frag = db.execute(
                "INSERT OR IGNORE INTO case_searches(case_no, day, "
                "frag) VALUES(?,?,?)", (case_no, day, frag)).rowcount
            db.commit()
            if new_case:
                chain.append("CASE_FLAG", {"user": rec["user"],
                                           "case": case_no,
                                           "flag": "CASE_FLAG"})
            if new_frag:
                chain.append("CASE_FLAG", {
                    "user": rec["user"], "case": case_no,
                    "flag": "CASE_FLAG (new fragment under case today)",
                    "plate_ref": frag_ref(frag)})
        results = run_search(frag, "tier2")
        n = len(results["reads"]) + len(results["hits"])
        # Items 3 + 31: plate_ref AND result_count, chained BEFORE
        # the response leaves.
        chain.append("QUERY", {
            "user": rec["user"], "type": "tier2 search", "tier": 2,
            "case": case_no, "plate_ref": frag_ref(frag),
            "result_count": n, "window_h": TIER2_WINDOW_H})
        return self.send_json(200, results)

    def _tier3_results_get(self, rec, path):
        if rec["role"] in SERVICE_ROLES:
            return self.deny_service_role(rec, path)
        try:
            rid = int(path.rsplit("/", 1)[1])
        except ValueError:
            return self.send_json(400, {"error": "request id must be a "
                                               "number"})
        row = db.execute(
            "SELECT requester, status, results, results_count FROM "
            "tier3_requests WHERE id=?", (rid,)).fetchone()
        if not row:
            return self.send_json(404, {"error": "no such Tier 3 "
                                               "request"})
        requester, status, results, n = row
        if rec["role"] not in ("supervisor", "auditor") \
                and rec["user"] != requester:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "tier3 results view",
                                     "request": rid,
                                     "reason": "not_requester"})
            return self.send_json(403, {"error": "results are for the "
                                               "requester (and "
                                               "supervisor/auditor)"})
        if results is None:
            return self.send_json(409, {"error": "no results yet "
                                               "(status: %s)" % status})
        chain.append("TIER3_RESULT_VIEW", {"request": rid,
                                           "by": rec["user"],
                                           "result_count": n or 0})
        return self.send_json(200, {"request_id": rid, "status": status,
                                    "results": json.loads(results)})

    def _rotation_status(self, rec):
        if rec["role"] not in ("supervisor", "auditor"):
            return self.send_json(403, {"error": "rotation status is "
                                               "supervisor/auditor "
                                               "only"})
        row = db.execute(
            "SELECT cycle_start, period_days, members_count, "
            "schedule_hash, schedule, published_ts FROM "
            "rotation_schedules ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return self.send_json(200, {"rotation": "inactive",
                                        "reason": "no schedule "
                                                  "published"})
        cycle_start, period, mcount, sched_hash, sched_json, pub = row
        schedule = json.loads(sched_json)
        start_dt = datetime.strptime(cycle_start, "%Y-%m-%d").replace(
            tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - start_dt).days
        round_idx = elapsed // period if period else 0
        rounds = schedule.get("rounds", [])
        current = rounds[round_idx] if 0 <= round_idx < len(rounds) \
            else None
        members = schedule.get("members", [])
        assignments = []
        if current:
            for pair in current.get("pairs", []):
                auditor, auditee = pair
                if auditee == AGENCY:
                    filed = db.execute(
                        "SELECT COUNT(*) FROM compact_audits WHERE "
                        "agency=? AND ok=1", (auditor,)).fetchone()[0] > 0
                elif auditor == AGENCY:
                    filed = db.execute(
                        "SELECT COUNT(*) FROM compact_audits WHERE "
                        "agency=? AND ok=1", (auditee,)).fetchone()[0] > 0
                else:
                    filed = None  # third-party duty: not visible here
                assignments.append({"auditor": auditor,
                                    "auditee": auditee, "filed": filed})
        # Delinquency: an agency that owed US an audit in each of the
        # last two completed rounds and filed neither is flagged.
        delinquent = []
        completed = [r for r in rounds[:round_idx]]
        if len(completed) >= 2:
            for m in members:
                if m == AGENCY:
                    continue
                owed = filed_n = 0
                for r in completed[-2:]:
                    for a, b in r.get("pairs", []):
                        if a == m and b == AGENCY:
                            owed += 1
                            if db.execute(
                                    "SELECT COUNT(*) FROM compact_audits "
                                    "WHERE agency=? AND ok=1",
                                    (m,)).fetchone()[0]:
                                filed_n += 1
                if owed == 2 and filed_n == 0:
                    delinquent.append(m)
        return self.send_json(200, {
            "agency": AGENCY, "cycle_start": cycle_start,
            "period_days": period, "members_count": mcount,
            "schedule_hash": sched_hash, "published_ts": pub,
            "current_round": (round_idx + 1) if current else None,
            "total_rounds": len(rounds),
            "assignments": assignments,
            "witness": current.get("witness") if current else None,
            "rotation_delinquent": delinquent})


if __name__ == "__main__":
    if not KEY_LOCKED:
        chain.append("SYSTEM", {"event": "janus started",
                                "version": VERSION})
    print("Janus %s on %s:%d (db %s)" % (VERSION, BIND, PORT, DB_PATH))
    Server((BIND, PORT), H).serve_forever()
