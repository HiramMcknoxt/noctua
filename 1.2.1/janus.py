#!/usr/bin/env python3
"""Janus — the NOCTUA front door. Version 1.2.1.

The ONLY way anything reads or writes NOCTUA data. Stdlib-only Python
service over SQLite, built to the Cabot pilot spec and the NOCTUA
interface spec. 1.2 is the council-round-3 hardening release: round 3
confirmed 1.1's core repairs (Tier 2 wall, chain atomicity, role
splits, QUERY logging, SS 1805 counts) and concentrated on what
remained — secondary copies of plate data retention didn't know
about, trust records that attested rather than verified, and scripts
that quietly undid the service's own protections.

1.2 changes (item numbers are the round-3 brief, S1-S17):
 S1  PLATE_DATA_STORES: a code-level registry (declared in
     sentinel.py, re-exported here) of every table.column and folder
     that can hold plate text or plate-derived time+place, each with
     a retention class. retention.py purges BY the registry;
     sentinel_audit.py audits BY it; a schema test fails the build
     when a plate-bearing column or folder is unregistered.
 S2  Tier 3 results are no longer stored as serialized bodies.
     tier3_requests stores only the matched read ids + hit ids;
     GET /tier3/results/<id> resolves them LIVE through the current
     shaping layer (suppression filter, case revalidation); aged-out
     detail returns the plate-free summary and says so.
 S3  Canonical, state-blind suppression identity: plate_ref() hashes
     the canonical plate only (sentinel.normalize_plate); ingest
     stores plate (canonical) AND plate_raw (as read). Search
     shaping filters suppressed rows IN SQL before the LIMIT.
     /verify and /evidence/export route suppressed hits only via
     the supervisor queue.
 S4  Ingest honesty: a camera REGISTRY (cameras.json) — an
     unregistered camera's reads are refused (INGEST_REJECTED).
     Missing state is stored as "" (unknown), missing confidence as
     NULL; the 0.95/AR fabrication is gone. Frigate event ids are
     forwarded and deduped persistently on (camera, event_id).
 S5  Health truth: degraded includes a broken chain and a retention
     breach, by name. /health requires auth (supervisor/auditor/
     jobs); the unauthenticated probe is GET /ping. Chain
     verification is cached (<=60s) and computed on a detached
     read-only connection, never under the write lock. Camera health
     is computed against the registry — a camera that has never
     reported appears as never_reported. scripts/hotlist_sync.py
     ships, so the monitored hotlist_sync job can actually exist;
     the witness job is monitored too.
 S6  Witness + anchor: checkpoint.py reads (seq, hash) in ONE query
     inside one transaction and keeps stdout to the single JSON
     line; publish_witness.sh posts the witness heartbeat only
     after a successful publish. restore.py never overwrites the
     live checkpoints file, requires a signed manifest when a key
     is configured, uses tarfile filter="data", moves db + -wal +
     -shm aside together, prunes pre-restore copies per the
     registry, and leaves a marker Janus chains as RESTORE at boot.
     The startup anchor fails CLOSED on a missing/malformed
     checkpoints file, verifies checkpoint SIGNATURES, checks the
     max-entries checkpoint, and remembers accepted state.
 S7  Key separation: NOCTUA_AUDIT_KEY stays the plate-HMAC secret.
     Checkpoints, audit reports, rotation schedules, and Compact
     receipts are signed with an Ed25519 keypair (system openssl;
     sentinel.py). Boot stores the audit key's fingerprint in meta
     and locks on a MISMATCH, not just on a missing key.
 S8  Compact gate semantics: the gate reads the LATEST audit row
     per partner — a newer failure closes it immediately. Receipts
     must name our NEWEST checkpoint, carry the partner's Ed25519
     signature over (root, entries, checkpoint_ts, agency), and
     freshness is measured from the checkpoint's own timestamp.
     compact.py independently recomputes the partner's chain over
     GET /audit/range and records a SIGNED report — the endpoint
     verifies the signature, not a bare boolean.
 S9  chain_auditor role: /audit, /audit/root, /audit/verify,
     /audit/range, GET /compact/checkpoint — nothing else.
     /tier3/results readership is requester + supervisors only.
 S10 Shares capped at Tier 2; case_ref and basis_type required;
     partner free text is stored in the DB and NEVER chained raw
     (the chain carries why_hash); the stale-config fail-closed
     rule applies; 60 queries/hour per partner, then 429.
 S11 Chain discipline + atomic logging: Janus's data connection IS
     the chain's connection — a handler's data writes and its chain
     appends commit in ONE transaction. Chain payloads carry
     case_hash / why_hash and enum categories; AUTH_FAIL chains a
     hashed username, throttled, with aggregate counts. The
     scrubber sanitizes and flags (CHAIN_SCRUB_FLAG) instead of
     raising, and legitimate IDs (CAM-101, CPD-1001) work.
 S12 Rotation correctness: build_schedule's seed actually permutes
     the slots (documented algorithm); members are deduplicated
     and validated; publication validates members against the
     partner registry, requires a real date and a 7-120 day
     period, and refuses to replace an active cycle (voiding is
     supervisor+auditor two-key, ROTATION_VOID). Duty tracking
     reads signed receipts (audits of us) and audit rows (audits
     by us) inside each round's window; witness duty is tracked
     via attestations.
 S13 Config ceilings: RETENTION_DAYS > 150 refuses startup; the
     Tier 2 window ceiling is 72h (refused, value in the error).
     The effective config is recorded in the SYSTEM chain entry at
     boot. Stale-config fail-closed applies to ALL data endpoints.
     Config reloads chain CONFIG_CHANGED with a diff hash.
 S14 Report residuals: REPORT_COMPILE chains a HASH of the
     snapshot. List names come from a supervisor-managed list
     registry (POST /lists). K8's denominator is EXECUTED Tier 3
     searches only. Per-list prosecutions get the same
     "not yet reported" treatment as the totals. Outcomes are
     created at ALERT time (status=unresolved) and updated at
     verification — an unreviewed hit that ages out stays counted
     as unresolved forever. A plate may sit on multiple lists:
     hotlist membership is its own table.
 S17 Evidence residuals: re-export deletes the prior bundle in the
     same operation; released bundles carry destroy_by (release +
     30d), surfaced in /health when overdue; custody excerpts
     compare hit ids as ints; HOLD entries carry hit_id; evidence
     bundles are included in backups (0600).

Concurrency: one shared SQLite connection plus one lock serializing
request handling (DBLOCK). Request bodies are read before the lock
and responses are serialized after it, so the lock covers database
work only. At a 9-camera city's volume that is not a bottleneck.
Stated plainly: this is a small-city service, not a horizontal-scale
design.

1.2.1 changes (council round 4, items P1-P13 of the 1.2.1 brief —
round 4 reproduced 39 defects at runtime against 1.2; each item is
the fix for named findings):
 P1  Share tier is strict: /share/query accepts ONLY tier==2 as a
     JSON int. tier=1, tier=true, tier=3 all refuse with
     SHARE_BLOCKED and the refused tier chained as a coded value.
 P2  "" no longer means expiry: hotlist rows store NULL when no
     expiry is given (existing '' rows are migrated at boot), and
     hotlist_sync sweeps in ONE transaction with its chain entries.
 P3  Suppression is a property of the PLATE AT QUERY TIME. /hits,
     Tier 3 result resolution, /verify, /evidence/export and share
     results all evaluate live suppression (canonical plate vs the
     active orders) at read time; hits.suppressed is a cache only.
 P4  In-place upgrades are repaired at first 1.2.1 boot: legacy
     reads.plate / hits.read_plate are normalized to canonical form
     (original kept in plate_raw), chained as MIGRATION with counts.
 P7  Compact records bind: audit-result requires report.agency ==
     the filing agency and report.ts within 26h, and stores the
     report's own ts; the share gate is evaluated AT QUERY TIME by
     one helper (newest checkpoint must exist; the latest receipt
     must match it, be verified, and be <=26h old); reinstate reads
     the latest audit row by id.
 P9  Rotation: the seed is DERIVED (SHA-256 of sorted members,
     cycle_start, current chain root) — a publisher-supplied seed
     is refused; delinquency counts completed rounds only, per
     agency, by direction-correct filings; /compact/witness
     requires a supervisor or the partner's registered-key
     signature and chains WITNESS_ATTEST.
 P11 One verification contract (sentinel.entry_hash, hash v2);
     anchor acceptance records the accepted CHECKPOINT IDS, so a
     later good checkpoint does not re-trigger an accepted
     disagreement; first config load chains CONFIG_CHANGED and the
     SYSTEM entry carries the config hash + hold_days; a key-locked
     boot no longer eats the restore marker; an env audit key is
     never trust-on-first-use pinned over an existing chain.
 P12 /tier3/pending shows a SUPERVISOR approver the fragment, case,
     justification, and auth basis — the second key can judge what
     it approves. Detectives stay plate-free, own requests only.
 P13 Holds: review_by must be a real date in (today, today+HOLD_DAYS];
     HOLD_DAYS itself is capped at 150 at boot; retention is never
     blocked past 150 days by paperwork alone (an unconfirmed
     disposition protects nothing without a bundle). DELETE /hotlist
     DELETES the identified membership (404 when none). /audit limit
     outside 1..1000 is a 400. Negative Content-Length is a 400.
     /audit/verify uses the cached detached verify and never holds
     DBLOCK while verifying. A Frigate redelivery with a corrected
     plate supersedes the stored read (READ_SUPERSEDED) instead of
     dying as a duplicate.
"""
import base64
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
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import sentinel
from sentinel import Chain, now_iso, sha

VERSION = "1.2.1"
# S1: the plate-data registry is declared once, in sentinel.py (the
# module every component already shares), and re-exported here so
# janus.PLATE_DATA_STORES is the name the council's forced change
# asked for.
PLATE_DATA_STORES = sentinel.PLATE_DATA_STORES
REGISTRY_VERSION = sentinel.REGISTRY_VERSION

DB_PATH = os.environ.get("NOCTUA_DB", "/data/noctua.db")
USERS_PATH = os.environ.get("NOCTUA_USERS", "/config/users.json")
CASES_PATH = os.environ.get("NOCTUA_CASES", "/config/cases.json")
CAMERAS_PATH = os.environ.get("NOCTUA_CAMERAS", "/config/cameras.json")
BIND = os.environ.get("NOCTUA_BIND", "127.0.0.1")
PORT = int(os.environ.get("NOCTUA_PORT", "8080"))
EVIDENCE_DIR = os.environ.get(
    "NOCTUA_EVIDENCE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "evidence"))
CHECKPOINTS_PATH = os.environ.get("NOCTUA_CHECKPOINTS",
                                  DB_PATH + ".checkpoints.jsonl")
AGENCY = os.environ.get("NOCTUA_AGENCY", "THIS-AGENCY")

# Retention clocks: the same env names retention.py uses.
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
HOLD_DAYS = int(os.environ.get("HOLD_DAYS", "30"))
TIER2_WINDOW_H = float(os.environ.get("NOCTUA_TIER2_WINDOW_H", "24"))

# S13: hard ceilings, refused at startup with the value named. The
# 150-day ceiling is Ark. Code SS 12-12-1804(a)'s statutory cap — a
# config above it is not a policy choice, it is an illegality the
# service declines to boot into. The 72h Tier 2 ceiling keeps
# "contemporaneous" from quietly becoming "last quarter".
if RETENTION_DAYS > 150:
    raise SystemExit(
        "REFUSING TO START: RETENTION_DAYS=%d exceeds the 150-day "
        "statutory ceiling (Ark. Code 12-12-1804(a))" % RETENTION_DAYS)
if TIER2_WINDOW_H > 72:
    raise SystemExit(
        "REFUSING TO START: NOCTUA_TIER2_WINDOW_H=%s exceeds the "
        "72-hour ceiling for a 'contemporaneous' Tier 2 window"
        % TIER2_WINDOW_H)
if HOLD_DAYS > 150:
    # P13: the hits class is a retention promise; a hold window
    # above the statutory cap would keep plate data past the
    # 150-day ceiling of Ark. Code 12-12-1804(a) by configuration.
    raise SystemExit(
        "REFUSING TO START: HOLD_DAYS=%d exceeds the 150-day "
        "statutory ceiling (Ark. Code 12-12-1804(a))" % HOLD_DAYS)

# Dead-man thresholds: a required job whose last heartbeat is older
# than this (or missing, or ok:false) makes /health report degraded.
JOB_MAX_AGE_S = {"retention": 26 * 3600, "checkpoint": 26 * 3600,
                 "hotlist_sync": 26 * 3600, "backup": 30 * 3600,
                 "witness": 26 * 3600}
CAMERA_SILENCE_S = 6 * 3600
BODY_CAP = 1_000_000

BASIS_TYPES = ("warrant", "court_order", "other")
REVIEW_FINDINGS = ("justified", "unjustified", "needs_followup")
SERVICE_ROLES = ("ingest", "jobs", "partner")
DATA_ROLES = ("detective", "supervisor", "auditor")
# S9: the chain_auditor may touch exactly these GET paths.
CHAIN_AUDITOR_GETS = ("/audit", "/audit/root", "/audit/verify",
                      "/audit/range", "/compact/checkpoint")
AUDIT_READ_ROLES = ("supervisor", "auditor", "chain_auditor")
# S11/S14: hot-list categories chained as an ENUM; unknown maps to
# "other". (The DB keeps the operator's original wording; the
# permanent chain gets the code.)
CATEGORY_ENUM = ("stolen_vehicle", "felony_warrant", "warrant",
                 "missing_person", "amber_alert", "silver_alert",
                 "evidence", "expired", "test", "other")


def category_enum(category):
    norm = re.sub(r"\s+", "_", (category or "").strip().lower())
    return norm if norm in CATEGORY_ENUM else "other"


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def _audit_key():
    """(key, locked). Resolve the plate_ref HMAC key: env, else the
    per-install key file (created with os.open 0o600 — no TOCTOU
    window). If the database already holds audit rows and NO key is
    available, return (None, True): Janus must start LOCKED (round-2
    item 30). Minting a fresh key would silently unmatch every
    suppression and orphan every plate_ref already in the chain."""
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k, False
    kf = DB_PATH + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip(), False
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
KEY_LOCK_REASON = "missing" if KEY_LOCKED else None


def plate_ref(plate):
    """This deployment's plate_ref: sentinel.plate_ref over the
    canonical, state-blind plate identity (S3/S15)."""
    if AUDIT_KEY is None:
        return "pref:unavailable"
    return sentinel.plate_ref(AUDIT_KEY, plate)


def frag_ref(frag):
    if AUDIT_KEY is None:
        return "pref:unavailable"
    return sentinel.frag_ref(AUDIT_KEY, frag)


def normalize_plate(plate):
    return sentinel.normalize_plate(plate)


def case_hash(case_no):
    """1.2.1 (P11/A36): case numbers are chained as a KEYED HMAC
    (sentinel.case_ref). 1.2's bare SHA-256 was reversible by brute
    force over the ~10^5 case-number space in seconds — the chain
    is readable by partners' chain_auditors by design, so anything
    chained must be keyed or public."""
    if AUDIT_KEY is None:
        return "cref:unavailable"
    return sentinel.case_ref(AUDIT_KEY, case_no or "")


def why_hash(text):
    if AUDIT_KEY is None:
        return "tref:unavailable"
    return sentinel.text_ref(AUDIT_KEY, text or "")


# --- users / cases / cameras, reloaded on mtime change so
# --- provision.py and the nightly case export take effect without a
# --- restart. A FAILED reload marks the file stale, chains
# --- CONFIG_STALE (throttled), degrades /health, and past 24h of
# --- staleness the data surface fails closed. A SUCCESSFUL reload
# --- whose content changed chains CONFIG_CHANGED with a diff hash
# --- (S13): account and case-list changes are auditable events.
USERS = {}
CASES = set()
CAMERAS = {}
_config = {
    "users": {"path": USERS_PATH, "mtime": None, "stale_since": None,
              "last_chain": 0.0, "hash": None},
    "cases": {"path": CASES_PATH, "mtime": None, "stale_since": None,
              "last_chain": 0.0, "hash": None},
    "cameras": {"path": CAMERAS_PATH, "mtime": None,
                "stale_since": None, "last_chain": 0.0, "hash": None},
}


def _apply_config(name, data):
    global USERS, CASES, CAMERAS
    if name == "users":
        USERS = {u["user"]: u for u in data}
    elif name == "cases":
        CASES = set(data["open_cases"])
    else:  # cameras: a JSON list of ids, or {cameras: [...]} / {id: {...}}
        if isinstance(data, dict) and "cameras" in data:
            data = data["cameras"]
        if isinstance(data, dict):
            CAMERAS = dict(data)
        else:
            CAMERAS = {c: {} for c in data}


def _reload_config():
    for name, st in _config.items():
        try:
            m = os.path.getmtime(st["path"])
            if m != st["mtime"]:
                with open(st["path"], "rb") as f:
                    raw = f.read()
                _apply_config(name, json.loads(raw))
                digest = sha(raw.decode("utf-8", "replace"))[:16]
                # P11/A13: the FIRST load chains too. 1.2 chained
                # only changes against an in-memory hash, so an
                # account added while Janus was stopped was live at
                # boot with no CONFIG_CHANGED anywhere — the audit
                # trail began after the fact it most needed to
                # record. The boot-time load is a chained fact.
                changed = digest != st["hash"]
                st["hash"] = digest
                st["mtime"] = m
                st["stale_since"] = None
                if changed and not KEY_LOCKED:
                    try:
                        chain.append("CONFIG_CHANGED", {
                            "file": name, "diff_hash": digest,
                            "config_hash": digest})
                    except Exception:
                        pass
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


def config_hash():
    """The combined hash of the three config files as last loaded —
    carried in the SYSTEM chain entry (P11/A13), so the exact
    account/case/camera set a boot started under is a chain fact,
    not a log line."""
    parts = []
    for name in ("users", "cases", "cameras"):
        parts.append("%s=%s" % (name, _config[name]["hash"] or "none"))
    return sha("|".join(parts))[:32]


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
         plate TEXT, plate_raw TEXT, state TEXT, conf REAL,
         cam_ts TEXT, skew_s INTEGER, event_id TEXT);
       CREATE TABLE IF NOT EXISTS hotlist_members(
         plate TEXT, state TEXT, list_source TEXT, case_no TEXT,
         category TEXT, added_by TEXT, added_ts TEXT,
         expires_ts TEXT, active INTEGER DEFAULT 1,
         PRIMARY KEY(plate, state, list_source, case_no));
       CREATE TABLE IF NOT EXISTS hits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         read_plate TEXT, entry_plate TEXT, state TEXT, list_name TEXT,
         category TEXT, status TEXT DEFAULT 'PENDING', decided_by TEXT,
         case_no TEXT, decided_ts TEXT, suppressed INTEGER DEFAULT 0);
       CREATE TABLE IF NOT EXISTS holds(
         id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, ref TEXT,
         reason TEXT, placed_by TEXT, placed_ts TEXT,
         released_by TEXT, released_ts TEXT, active INTEGER DEFAULT 1,
         review_by TEXT);
       CREATE TABLE IF NOT EXISTS outcomes(
         hit_id INTEGER PRIMARY KEY, list_name TEXT, category TEXT,
         confirmed INTEGER DEFAULT 0, arrest INTEGER DEFAULT 0,
         prosecution INTEGER, reviewed INTEGER DEFAULT 0,
         status TEXT DEFAULT 'unresolved', updated_by TEXT,
         updated_ts TEXT, hit_ts TEXT);
       CREATE TABLE IF NOT EXISTS case_searches(
         case_no TEXT, day TEXT, frag TEXT,
         PRIMARY KEY(case_no, day, frag));
       CREATE TABLE IF NOT EXISTS case_flags(
         case_no TEXT, day TEXT, PRIMARY KEY(case_no, day));
       CREATE TABLE IF NOT EXISTS suppressions(
         plate_ref TEXT PRIMARY KEY, plate TEXT, state TEXT,
         order_ref TEXT, placed_by TEXT, case_no TEXT, ts TEXT,
         active INTEGER DEFAULT 1, release_requested_by TEXT,
         release_order_ref TEXT, released_ts TEXT);
       CREATE TABLE IF NOT EXISTS counters(
         day TEXT, camera_id TEXT, reads INTEGER DEFAULT 0,
         alerts INTEGER DEFAULT 0, PRIMARY KEY(day, camera_id));
       CREATE TABLE IF NOT EXISTS lists_checked(
         day TEXT, list_name TEXT, PRIMARY KEY(day, list_name));
       CREATE TABLE IF NOT EXISTS list_registry(
         list_name TEXT PRIMARY KEY, created_by TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS heartbeats(
         job TEXT PRIMARY KEY, ts TEXT, ok INTEGER, detail TEXT);
       CREATE TABLE IF NOT EXISTS tier3_requests(
         id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT,
         case_no TEXT, why TEXT, plate_fragment TEXT, auth_basis TEXT,
         basis_type TEXT, status TEXT DEFAULT 'PENDING', created_ts TEXT,
         decided_by TEXT, decided_ts TEXT, emergency INTEGER DEFAULT 0,
         needs_review INTEGER DEFAULT 0, review_finding TEXT,
         review_note TEXT, reviewed_by TEXT, reviewed_ts TEXT,
         results_count INTEGER, results TEXT, results_read_ids TEXT,
         results_hit_ids TEXT);
       CREATE TABLE IF NOT EXISTS evidence(
         hit_id INTEGER PRIMARY KEY, export_ts TEXT, export_by TEXT,
         manifest_hash TEXT, bundle TEXT, scope TEXT, expand_reason TEXT,
         prosecutor_name TEXT, prosecutor_date TEXT, released_by TEXT,
         released_ts TEXT, destroyed_ts TEXT, destroyed_by TEXT,
         destroy_by TEXT,
         disp_outcome TEXT, disp_by TEXT, disp_date TEXT, disp_note TEXT,
         disp_posted_by TEXT, disp_confirmed_by TEXT,
         disp_confirmed_ts TEXT);
       CREATE TABLE IF NOT EXISTS report_snapshots(
         id INTEGER PRIMARY KEY AUTOINCREMENT, from_ts TEXT, to_ts TEXT,
         compiled_by TEXT, compiled_ts TEXT, body TEXT);
       CREATE TABLE IF NOT EXISTS partners(
         agency TEXT PRIMARY KEY, endpoint TEXT,
         audit_key_fingerprint TEXT, pubkey_pem TEXT,
         agreement_ref TEXT, status TEXT DEFAULT 'active',
         added_by TEXT, added_ts TEXT);
       CREATE TABLE IF NOT EXISTS compact_receipts(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT, root TEXT,
         entries INTEGER, sig TEXT, checkpoint_ts TEXT,
         verified INTEGER DEFAULT 0, received_ts TEXT);
       CREATE TABLE IF NOT EXISTS compact_audits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT, ok INTEGER,
         detail TEXT, report_hash TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS share_queries(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT,
         case_ref TEXT, why TEXT, basis_type TEXT, plate_ref TEXT,
         tier INTEGER, result_count INTEGER, outcome TEXT, ts TEXT);
       CREATE TABLE IF NOT EXISTS rotation_schedules(
         id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_start TEXT,
         period_days INTEGER, members_count INTEGER, schedule_hash TEXT,
         schedule TEXT, published_by TEXT, published_ts TEXT);
       CREATE TABLE IF NOT EXISTS witness_attestations(
         id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT,
         cycle_start TEXT, round_no INTEGER, ok INTEGER, detail TEXT,
         ts TEXT);
       CREATE TABLE IF NOT EXISTS meta(
         key TEXT PRIMARY KEY, value TEXT);"""
)
db.commit()

# --- migrations for databases created by 1.0/1.1 -------------------
def _cols(table):
    return [r[1] for r in db.execute(f"PRAGMA table_info({table})")]


for _t, _c, _d in (
        ("reads", "plate_raw", "TEXT"), ("reads", "event_id", "TEXT"),
        ("reads", "cam_ts", "TEXT"), ("reads", "skew_s", "INTEGER"),
        ("hits", "state", "TEXT DEFAULT 'AR'"),
        ("hits", "list_name", "TEXT"),
        ("hits", "suppressed", "INTEGER DEFAULT 0"),
        ("holds", "review_by", "TEXT"),
        ("outcomes", "reviewed", "INTEGER DEFAULT 0"),
        ("outcomes", "status", "TEXT DEFAULT 'unresolved'"),
        ("suppressions", "plate", "TEXT"), ("suppressions", "state", "TEXT"),
        ("suppressions", "order_ref", "TEXT"),
        ("suppressions", "release_requested_by", "TEXT"),
        ("suppressions", "release_order_ref", "TEXT"),
        ("suppressions", "released_ts", "TEXT"),
        ("tier3_requests", "basis_type", "TEXT"),
        ("tier3_requests", "review_note", "TEXT"),
        ("tier3_requests", "results", "TEXT"),
        ("tier3_requests", "results_read_ids", "TEXT"),
        ("tier3_requests", "results_hit_ids", "TEXT"),
        ("evidence", "scope", "TEXT"), ("evidence", "expand_reason", "TEXT"),
        ("evidence", "destroyed_ts", "TEXT"),
        ("evidence", "destroyed_by", "TEXT"),
        ("evidence", "destroy_by", "TEXT"),
        ("evidence", "disp_outcome", "TEXT"), ("evidence", "disp_by", "TEXT"),
        ("evidence", "disp_date", "TEXT"), ("evidence", "disp_note", "TEXT"),
        ("evidence", "disp_posted_by", "TEXT"),
        ("evidence", "disp_confirmed_by", "TEXT"),
        ("evidence", "disp_confirmed_ts", "TEXT"),
        ("partners", "pubkey_pem", "TEXT"),
        ("compact_receipts", "checkpoint_ts", "TEXT"),
        ("compact_receipts", "verified", "INTEGER DEFAULT 0")):
    if _c not in _cols(_t):
        db.execute(f"ALTER TABLE {_t} ADD COLUMN {_c} {_d}")
db.commit()
# reads.plate_raw backfill: pre-1.2 rows stored only the (already
# normalized-by-convention) plate; raw = plate is the honest record.
db.execute("UPDATE reads SET plate_raw = plate WHERE plate_raw IS NULL")
# outcomes created by 1.1 were written at verify time: they ARE reviewed.
db.execute("UPDATE outcomes SET reviewed = 1, status = 'reviewed' "
           "WHERE reviewed = 0 AND updated_ts IS NOT NULL")
db.commit()
if "hotlist" in [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]:
    # S14: the 1.1 single-row hotlist becomes the membership table —
    # a plate may sit on several lists, under several cases.
    db.executescript(
        """INSERT OR IGNORE INTO hotlist_members(plate, state,
             list_source, case_no, category, added_by, added_ts,
             expires_ts, active)
           SELECT plate, state,
             CASE WHEN list_name IS NULL OR list_name = ''
                  THEN 'Local agency list' ELSE list_name END,
             case_no, category, added_by, added_ts, expires_ts, active
             FROM hotlist;
           DROP TABLE hotlist;""")
    db.commit()

db.executescript(
    """CREATE INDEX IF NOT EXISTS idx_reads_plate ON reads(plate);
       CREATE INDEX IF NOT EXISTS idx_reads_ts ON reads(ts);
       CREATE INDEX IF NOT EXISTS idx_hits_plate ON hits(read_plate);
       CREATE UNIQUE INDEX IF NOT EXISTS idx_reads_event
         ON reads(cam, event_id) WHERE event_id IS NOT NULL;""")
db.commit()
# The default local list exists from boot; every other name a report
# may print must be registered by a supervisor first (S14).
db.execute("INSERT OR IGNORE INTO list_registry(list_name, created_by,"
           " ts) VALUES('Local agency list', 'system', ?)", (now_iso(),))
db.commit()

# S11: the chain SHARES Janus's connection — a handler's data writes
# and its chain appends are one transaction, committed together.
chain = Chain(DB_PATH, conn=db)
db.execute("CREATE INDEX IF NOT EXISTS idx_audit_kind ON audit(kind)")
db.commit()
DBLOCK = threading.Lock()


def _migrate_121():
    """1.2.1 boot repairs (P4 + P2), each chained once as MIGRATION
    with row counts, each a no-op on a database that does not need
    it (so the entry appears exactly when history was rewritten,
    and says how much):

    P4 — a 1.1/1.2 database upgraded in place kept its legacy plate
    TEXT: reads.plate could hold 'VIC 309' while suppressions key
    on the canonical 'VIC309', so every pre-upgrade suppression
    silently stopped matching. Normalize reads.plate and
    hits.read_plate to canonical form; the original read text is
    already preserved in reads.plate_raw by the 1.2 backfill.
    P2 — hotlist rows written by 1.2 with no expiry carry
    expires_ts='' — which the sweep read as 'expired before
    everything'. '' becomes NULL (no expiry), the only meaning it
    ever had."""
    if KEY_LOCKED:
        return
    counts = {}
    try:
        n = 0
        for rid, plate in db.execute(
                "SELECT id, plate FROM reads WHERE plate IS NOT NULL"
        ).fetchall():
            canon = normalize_plate(plate)
            if canon != plate:
                db.execute("UPDATE reads SET plate=? WHERE id=?",
                           (canon, rid))
                n += 1
        if n:
            counts["reads_plate_normalized"] = n
        n = 0
        for hid, plate in db.execute(
                "SELECT id, read_plate FROM hits WHERE read_plate "
                "IS NOT NULL").fetchall():
            canon = normalize_plate(plate)
            if canon != plate:
                db.execute("UPDATE hits SET read_plate=? WHERE id=?",
                           (canon, hid))
                n += 1
        if n:
            counts["hits_read_plate_normalized"] = n
        n = db.execute(
            "UPDATE hotlist_members SET expires_ts=NULL WHERE "
            "expires_ts=''").rowcount
        if n:
            counts["hotlist_empty_expiry_to_null"] = n
        if counts:
            chain.append("MIGRATION", {"to": "1.2.1", **counts})
        db.commit()
    except sqlite3.Error:
        try:
            db.rollback()
        except sqlite3.Error:
            pass

# Catch-all case numbers ("PATROL-2026", a duty log, a test case) are
# how the case gate gets laundered — any case containing one of these
# patterns is rejected and logged. Comma list, case-insensitive
# substring match.
BANNED_CASE_PATTERNS = [p.strip().upper() for p in os.environ.get(
    "NOCTUA_BANNED_CASE_PATTERNS", "PATROL,TEST,ADMIN,DUTY").split(",")
    if p.strip()]


# ---------------- meta + boot integrity (S6, S7) ----------------
def _meta_get(key):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(key, value):
    db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
    db.commit()


def _key_fingerprint_check():
    """S7: at first boot Janus stores the audit key's fingerprint in
    meta; every later boot compares. A MISMATCH — or a probe error
    against a chain that already has rows — locks the service,
    exactly as a missing key does. Silently minting over an existing
    chain was the 1.0/1.1 failure this closes."""
    global KEY_LOCKED, KEY_LOCK_REASON
    if KEY_LOCKED:
        return
    try:
        stored = _meta_get("audit_key_fingerprint")
        if stored is None:
            # First pin. Over an EMPTY chain any key is the install's
            # key by definition. Over an EXISTING chain (a pre-1.2
            # database carries no fingerprint), the key is trusted
            # only when it comes from the install's own key FILE —
            # an ENV-supplied key over existing history is trust on
            # first use at exactly the moment the wrong-key scenario
            # happens (1.2.1, P11/A28), so it locks instead.
            n = 0
            try:
                n = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
            except sqlite3.Error:
                n = 0
            if n == 0:
                _meta_set("audit_key_fingerprint", sha(AUDIT_KEY))
            else:
                kf = DB_PATH + ".audit_key"
                file_key = None
                if os.path.exists(kf):
                    file_key = open(kf).read().strip()
                env_key = os.environ.get("NOCTUA_AUDIT_KEY")
                if file_key and (not env_key or env_key == file_key):
                    _meta_set("audit_key_fingerprint", sha(AUDIT_KEY))
                else:
                    KEY_LOCKED = True
                    KEY_LOCK_REASON = "unpinned_key_over_existing_chain"
        elif not hmac_mod.compare_digest(stored, sha(AUDIT_KEY)):
            KEY_LOCKED = True
            KEY_LOCK_REASON = "mismatch"
    except sqlite3.Error:
        try:
            n = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        except sqlite3.Error:
            n = 0
        if n:
            KEY_LOCKED = True
            KEY_LOCK_REASON = "probe_error"


_key_fingerprint_check()

# The Ed25519 signing keypair (S7) — created beside the DB if absent.
# Failure here (no openssl) is loud at boot and disables signing, not
# the service: checkpoints will fail elsewhere, by name.
SIGNING_PRIV = None
SIGNING_PUB = None
try:
    SIGNING_PRIV, SIGNING_PUB = sentinel.ensure_signing_key(DB_PATH)
    SIGNING_PUB_PEM = open(SIGNING_PUB).read()
except Exception as exc:  # pragma: no cover - environment failure
    SIGNING_PUB_PEM = None
    print("janus: WARNING — Ed25519 signing key unavailable: %s" % exc,
          file=sys.stderr)


def _load_checkpoints():
    """(list, error). The checkpoints file is the outside anchor's
    local copy; a malformed line is an anchor problem, not a detail
    to skip (S6)."""
    if not os.path.exists(CHECKPOINTS_PATH):
        return [], None
    cps = []
    try:
        with open(CHECKPOINTS_PATH) as f:
            for line in f:
                if line.strip():
                    cps.append(json.loads(line))
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__
    return cps, None


def anchor_mismatch():
    return _meta_get("anchor_mismatch") is not None


def _checkpoint_id(cp):
    """A checkpoint's identity for acceptance purposes: its entry
    count and root. Two checkpoints with the same id ARE the same
    anchor fact; a new checkpoint is a new fact (1.2.1, P11)."""
    return [cp.get("entries"), cp.get("root")]


def _accepted_checkpoint_ids():
    try:
        raw = json.loads(_meta_get("anchor_accepted_ids") or "[]")
        return {tuple(x) for x in raw if isinstance(x, list)}
    except ValueError:
        return set()


def _bad_checkpoints(cps=None):
    """The published checkpoints that DISAGREE with the chain right
    now: bad Ed25519 signature, a root that is not the chain hash at
    the checkpoint's entry count, or an entry count the chain no
    longer has (truncation). Acceptance is not consulted here — this
    is the raw disagreement list _anchor_accept records against."""
    if cps is None:
        cps, err = _load_checkpoints()
        if err or not cps:
            return []
    bad = []
    for cp in cps:
        n = cp.get("entries")
        if cp.get("sig_alg") == "ed25519":
            ok_sig = bool(SIGNING_PUB_PEM) and bool(cp.get("pubkey")) \
                and sentinel.pubkey_fingerprint(cp["pubkey"]) \
                == sentinel.pubkey_fingerprint(SIGNING_PUB_PEM) \
                and sentinel.verify_bytes(
                    SIGNING_PUB_PEM,
                    sentinel.checkpoint_signed_bytes(cp),
                    cp.get("sig", ""))
            if not ok_sig:
                bad.append(cp)
                continue
        if not isinstance(n, int):
            bad.append(cp)
        elif n == 0:
            if cp.get("root") != "GENESIS":
                bad.append(cp)
        elif n > chain.count():
            bad.append(cp)  # the checkpoint claims entries we no
            # longer have — the chain was truncated under it
        elif chain.hash_at_seq(n) != cp.get("root"):
            bad.append(cp)
    return bad


def _anchor_evaluate():
    """(mismatch, detail). Checks EVERY published checkpoint (via
    _bad_checkpoints), minus the specific checkpoints a two-key
    acceptance already recorded. 1.2 pinned acceptance to the
    NEWEST checkpoint's (root, entries), so the next good daily
    checkpoint changed the pin and the same accepted disagreement
    re-triggered at every restart (round 4, A15). 1.2.1 records the
    accepted checkpoint IDS: an accepted checkpoint stays accepted
    forever; a NEW disagreeing checkpoint is a new fact and does
    trigger. A checkpoints file that vanished or went malformed
    while the chain has history fails CLOSED."""
    if KEY_LOCKED:
        return False, {}
    cps, err = _load_checkpoints()
    if err:
        return True, {"reason": "checkpoints_unreadable", "error": err}
    if not cps:
        if chain.count() > 0 and _meta_get("anchor_seen_checkpoint"):
            return True, {"reason": "checkpoints_missing"}
        return False, {}
    _meta_set("anchor_seen_checkpoint", "1")
    accepted = _accepted_checkpoint_ids()
    bad = [cp for cp in _bad_checkpoints(cps)
           if tuple(_checkpoint_id(cp)) not in accepted]
    if not bad:
        return False, {}
    newest = max((c for c in bad if isinstance(c.get("entries"), int)),
                 key=lambda c: c["entries"], default=None)
    detail = {"reason": "checkpoint_disagreement",
              "bad_entries": sorted({str(c.get("entries"))
                                     for c in bad})[:5],
              "checkpoint_entries": newest.get("entries")
              if newest else None,
              "checkpoint_root": newest.get("root") if newest else None,
              "chain_entries": chain.count()}
    return True, detail


def _startup_anchor_check():
    mismatch, detail = _anchor_evaluate()
    if mismatch and not anchor_mismatch():
        detail = dict(detail, detected=now_iso())
        _meta_set("anchor_mismatch", json.dumps(detail))
        chain.append("STARTUP_ANCHOR_MISMATCH", {
            "reason": detail.get("reason", ""),
            "checkpoint_entries": detail.get("checkpoint_entries") or 0,
            "chain_entries": chain.count()})


def _consume_restore_marker():
    """S6: restore.py leaves a marker beside the DB; Janus chains
    the RESTORE at boot (restore itself cannot chain into a service
    that is stopped) and removes the marker."""
    marker = DB_PATH + ".restore_marker"
    if not os.path.exists(marker):
        return
    if KEY_LOCKED:
        # P11/A29: a locked boot must NOT consume the marker — 1.2
        # deleted it unchained, so the restore it recorded vanished
        # from history. The marker waits for the first boot that can
        # actually chain the RESTORE.
        return
    try:
        info = json.load(open(marker))
    except (OSError, ValueError):
        info = {}
    chain.append("RESTORE", {
        "from_backup": str(info.get("from_backup", ""))[:64],
        "restored_ts": str(info.get("ts", ""))[:32]})
    try:
        os.remove(marker)
    except OSError:
        pass


_reload_config()
_migrate_121()
_startup_anchor_check()
_consume_restore_marker()


# ---------------- shared gates ----------------
_auth_fail_counts = {}
_auth_fail_global = {}
AUTH_FAIL_GLOBAL_CAP = 25


def _note_auth_fail(user):
    """S11: AUTH_FAIL chains a HASHED username — never the raw header
    an unauthenticated stranger typed — throttled to one entry per
    source per minute, with the minute's aggregate count chained
    when the minute rolls over. 1.2.1 (P13/A20): a GLOBAL cap joins
    the per-user throttle — 1.2 chained one entry per DISTINCT
    username per minute, so 300 throwaway usernames wrote 300
    permanent entries: the audit chain itself was the flood target.
    Past the cap the 401 still goes out; only the chaining stops."""
    if not user or KEY_LOCKED:
        return
    bucket = int(time.time() // 60)
    g = _auth_fail_global.get(bucket, 0) + 1
    _auth_fail_global[bucket] = g
    for k in [k for k in _auth_fail_global if k < bucket - 1]:
        del _auth_fail_global[k]
    if g > AUTH_FAIL_GLOBAL_CAP:
        return
    uh = sha(user)[:16]
    for k in [k for k in _auth_fail_counts if k[1] < bucket - 1]:
        del _auth_fail_counts[k]
    prev = _auth_fail_counts.get((user, bucket - 1))
    if prev and prev > 1 and not _auth_fail_counts.get(
            ("flushed", user, bucket)):
        _auth_fail_counts[("flushed", user, bucket)] = 1
        try:
            chain.append("AUTH_FAIL", {"user_hash": uh, "count": prev,
                                       "aggregate": True})
        except Exception:
            pass
    n = _auth_fail_counts.get((user, bucket), 0) + 1
    _auth_fail_counts[(user, bucket)] = n
    if n == 1:
        try:
            chain.append("AUTH_FAIL", {"user_hash": uh, "count": 1})
        except Exception:
            pass  # the 401 still goes out


def auth(handler):
    """Return the user record or None. Named individual accounts only;
    a disabled account cannot authenticate. Comparison is
    constant-time."""
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
    """(ok, reason_code) — THE case check. Every endpoint that takes
    a case number runs this one function: catch-all ban, then
    membership in the open-case list."""
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
    denied here as everywhere on the data surface."""
    if user_rec["role"] == "auditor":
        return False, "role"
    if user_rec["role"] in SERVICE_ROLES:
        return False, "role"
    if user_rec["role"] == "chain_auditor":
        return False, "role"
    ok, why = case_gate(case_no)
    if not ok:
        return False, why
    return True, ""


def validate_fragment(frag):
    """(normalized, reason_code). Fragments shorter than 3 characters
    or carrying SQL wildcards turn a search into a browse; they are
    refused on every search path."""
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


def is_suppressed(plate):
    """S3: suppression identity is the canonical plate alone. The
    state recorded with a read (or left unknown) is not part of it —
    a protection order follows the vehicle."""
    return plate_ref(plate) in active_suppression_refs()


_SUPPRESSED_SQL = (
    " NOT EXISTS (SELECT 1 FROM suppressions s WHERE s.active=1 "
    "AND s.plate = {col})")

# A hit is suppressed when EITHER plate it carries (the plate as
# read, the plate as listed) is under an active order — evaluated
# against the suppressions table as it stands NOW (P3).
_SUPPRESSED_HIT_SQL = (
    " NOT EXISTS (SELECT 1 FROM suppressions s WHERE s.active=1 "
    "AND (s.plate = hits.read_plate OR s.plate = hits.entry_plate))")


def hit_suppressed_now(read_plate, entry_plate=None):
    """P3: suppression as a property of the plate AT QUERY TIME.
    1.2 stamped hits.suppressed at ingest and every disclosure path
    read the stamp, so a protection order entered after a hit left
    the hit fully visible — verifiable and exportable by the very
    people the order exists to keep it from. The hits.suppressed
    column is now a CACHE (it still routes the ingest-time alert);
    every read path asks this question live, by canonical plate_ref
    against the active orders."""
    refs = active_suppression_refs()
    for plate in (read_plate, entry_plate):
        if plate and plate_ref(plate) in refs:
            return True
    return False


def run_search(frag, scope="full"):
    """Execute a read search. scope='tier2' applies the temporal wall
    IN SQL: only reads received within TIER2_WINDOW_H hours are
    visible. scope='full' is the Tier 3 scope.

    Suppressed plates are EXCLUDED for every viewer, in SQL, BEFORE
    the LIMIT (S3): no stub, no marker, and no count difference an
    observer can use — filtering after the limit would leak the
    suppressed row's existence through the page size. The match
    workflow (GET /suppressed-hits) is the only disclosure path."""
    frag = (frag or "").upper()
    window = ""
    params = ["%" + frag + "%"]
    if scope == "tier2":
        since = (datetime.now(timezone.utc)
                 - timedelta(hours=TIER2_WINDOW_H)).strftime(
                     "%Y-%m-%dT%H:%M:%SZ")
        window = " AND ts>=?"
        params.append(since)
    rows = db.execute(
        "SELECT id,ts,cam,plate,state FROM reads WHERE plate LIKE ?"
        + window + " AND" + _SUPPRESSED_SQL.format(col="reads.plate")
        + " ORDER BY ts DESC LIMIT 200", params).fetchall()
    hit_rows = db.execute(
        "SELECT id,ts,cam,read_plate,state,status FROM hits "
        "WHERE read_plate LIKE ?" + window
        + " AND" + _SUPPRESSED_HIT_SQL
        + " ORDER BY ts DESC LIMIT 50", params).fetchall()
    return {
        "reads": [dict(zip(("id", "ts", "cam", "plate", "state"), r))
                  for r in rows],
        "hits": [dict(zip(("id", "ts", "cam", "plate", "state",
                           "status"), r)) for r in hit_rows]}


def jobs_status():
    """Dead-man status for the monitored jobs. A job that reported
    ok:false is degraded NOW, not when it goes stale."""
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
    """Per-camera health against the CONFIG REGISTRY (S5): every
    registered camera appears — never_reported if it has never sent
    a read, silent if its last read is older than CAMERA_SILENCE_S.
    (1.1 computed health from the reads table alone, so a camera
    that died before its first read was invisible.)"""
    now = datetime.now(timezone.utc)
    last_by_cam = dict(db.execute(
        "SELECT cam, MAX(ts) FROM reads GROUP BY cam").fetchall())
    out, silent = {}, []
    names = list(CAMERAS) + [c for c in last_by_cam if c not in CAMERAS]
    for cam in names:
        last = last_by_cam.get(cam)
        registered = cam in CAMERAS
        if last is None:
            out[cam] = {"last_read": None, "age_s": None,
                        "registered": registered,
                        "status": "never_reported"}
            silent.append(cam)
            continue
        try:
            age = int((now - parse_ts(last)).total_seconds())
        except (ValueError, TypeError):
            age = None
        status = "ok" if (age is not None and age <= CAMERA_SILENCE_S) \
            else "silent"
        out[cam] = {"last_read": last, "age_s": age,
                    "registered": registered, "status": status}
        if status != "ok":
            silent.append(cam)
    return out, silent


def overdue_holds():
    """Active holds whose review DATE has passed (P13: review_by is
    a date; an overdue hold is an operational alarm in /health, and
    it no longer protects anything in retention)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [dict(zip(("id", "scope", "ref", "placed_by", "review_by"), r))
            for r in db.execute(
                "SELECT id, scope, ref, placed_by, review_by FROM holds "
                "WHERE active=1 AND review_by IS NOT NULL "
                "AND date(review_by) < ?", (today,))]


def evidence_destroy_overdue():
    """S17: released bundles past their destroy_by date, still on
    disk — a registered store in breach, surfaced by name."""
    return db.execute(
        "SELECT COUNT(*) FROM evidence WHERE destroyed_ts IS NULL "
        "AND destroy_by IS NOT NULL AND destroy_by < ?",
        (now_iso(),)).fetchone()[0]


# ---------------- backfill aggregation ----------------
# A camera clock behind receipt by >5 min on a replayed backlog is
# not "skew" — it is store-and-forward doing its job. Backfills
# aggregate into at most one BACKFILL chain entry per camera per
# hour; buckets flush on hour rollover, at 1000 reads, or when idle
# longer than NOCTUA_BACKFILL_FLUSH_S (default 3600).
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


# ---------------- report computation (S14) ----------------
def tier3_stats(frm, to):
    """K8: the Tier 3 emergency share. S14: the denominator is
    EXECUTED Tier 3 searches only — pending and denied requests are
    not searches, and counting them diluted the very signal K8
    exists to catch."""
    EXEC = "status IN ('EXECUTED','EMERGENCY','REVIEWED')"

    def _counts(a, b):
        total = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE created_ts>=? "
            "AND created_ts<=? AND " + EXEC, (a, b)).fetchone()[0]
        emerg = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE created_ts>=? "
            "AND created_ts<=? AND emergency=1 AND " + EXEC,
            (a, b)).fetchone()[0]
        return total, emerg
    total, emerg = _counts(frm, to)
    try:
        to_dt = parse_ts(to) if len(to) > 10 else datetime.now(timezone.utc)
        if to_dt.year > 9000:
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
    outcomes and lists_checked — never from the hits table, which
    retention deletes. Outcomes are created at ALERT time with
    status=unresolved (S14) and updated at verification, so an
    unreviewed hit that ages out stays counted as unresolved
    forever instead of vanishing. Prosecutions are NULL until the
    prosecutor feedback loop reports them; per-list figures get the
    same 'not yet reported' treatment as the totals."""
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
            "COALESCE(SUM(CASE WHEN reviewed=1 AND confirmed=0 "
            "THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN reviewed=0 THEN 1 ELSE 0 END),0), "
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
            "unresolved": row[2], "arrests": row[3],
            "prosecutions": (row[4] if row[5] else "not yet reported"),
            "prosecutions_reported": row[5],
            "arrests_and_prosecutions": row[6]}
    tot = db.execute(
        "SELECT COALESCE(SUM(confirmed),0), "
        "COALESCE(SUM(CASE WHEN reviewed=1 AND confirmed=0 "
        "THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN reviewed=0 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(arrest),0), "
        "COALESCE(SUM(CASE WHEN prosecution=1 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN prosecution IS NOT NULL "
        "THEN 1 ELSE 0 END),0), COUNT(*) FROM outcomes "
        "WHERE hit_ts>=? AND hit_ts<=?", (frm, to)).fetchone()
    prosecutions = tot[4] if tot[5] else "not yet reported"
    return {
        "from": frm, "to": to, "plates_scanned": scanned,
        "plates_scanned_source": "counters (cumulative at ingest; "
                                 "survives retention deletes)",
        "lists": lists,
        "confirmed_matches": tot[0],
        "matches_not_corresponding": tot[1],
        "unresolved": tot[2],
        "arrests": tot[3],
        "prosecutions": prosecutions,
        "prosecutions_coverage": {"reported": tot[5], "total": tot[6]},
        "tier3": tier3_stats(frm, to),
        "overdue_holds": len(overdue_holds())}


# ---------------- custody excerpt (S17) ----------------
def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def custody_excerpt(hit_id):
    """The Sentinel entries that mention this hit, found with an
    INDEXED, paged scan over the entry kinds that can carry a hit
    id. S17: hit ids are compared as INTS on both sides — a string
    '7' in an old payload and an int 7 in the query are the same
    hit, and type drift must not silently empty a custody record."""
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
            if _as_int(fields.get("hit")) == hit_id:
                out.append({"seq": seq, "ts": ts, "kind": kind,
                            "fields": fields, "prev": prev, "hash": h})
        if len(rows) < 500:
            return out
        offset += 500


# ---------------- chain verification cache (S5) ----------------
_chain_cache = {"ts": 0.0, "result": None}


def chain_ok_cached():
    """verify() costs a full scan; /health caches it for <=60s and
    computes it on a DETACHED read-only connection — never while
    holding the write lock, never through the shared connection's
    possibly-open transaction."""
    now = time.time()
    if _chain_cache["result"] is None \
            or now - _chain_cache["ts"] > 60:
        try:
            _chain_cache["result"] = sentinel.verify_detached(DB_PATH)
        except Exception:
            _chain_cache["result"] = {"ok": False,
                                      "reason": "verify error"}
        _chain_cache["ts"] = now
    return _chain_cache["result"]


def read_newest_checkpoint():
    """The newest published checkpoint (max entries), or None."""
    cps, err = _load_checkpoints()
    if err or not cps:
        return None
    valid = [c for c in cps if isinstance(c.get("entries"), int)]
    if not valid:
        return cps[-1]
    return max(valid, key=lambda c: c["entries"])


def share_gate_missing(agency):
    """The Compact share gate, evaluated AT QUERY TIME (1.2.1, P7):
    returns None when the gate is open, else the coded reason it is
    closed. One helper, consumed by _share_query and by
    share_gate_open, so the gate the partner list DISPLAYS is the
    gate the share endpoint ENFORCES. 1.2's legs were checked
    piecemeal and each had a fail-open seam: a missing newest
    checkpoint passed (`if newest and ...`), a receipt's age was
    checked only when it was POSTed (a years-old receipt opened the
    gate forever), and verified=0 receipts counted. Now: the newest
    checkpoint must EXIST, the latest receipt must match it, carry
    verified=1, and its checkpoint_ts must be <=26h old — all read
    fresh on every call."""
    row = db.execute("SELECT status FROM partners WHERE agency=?",
                     (agency,)).fetchone()
    if not row or row[0] != "active":
        return "partner_inactive"
    a = db.execute("SELECT ok, ts FROM compact_audits WHERE agency=? "
                   "ORDER BY id DESC LIMIT 1", (agency,)).fetchone()
    if not a or not a[0]:
        return "cross_audit_ok"
    try:
        if (datetime.now(timezone.utc)
                - parse_ts(a[1])).total_seconds() > 26 * 3600:
            return "cross_audit_ok"
    except (ValueError, TypeError):
        return "cross_audit_ok"
    newest = read_newest_checkpoint()
    if not newest:
        return "checkpoint_receipt"
    r = db.execute(
        "SELECT root, entries, checkpoint_ts, verified FROM "
        "compact_receipts WHERE agency=? ORDER BY id DESC LIMIT 1",
        (agency,)).fetchone()
    if not r:
        return "checkpoint_receipt"
    if r[0] != newest.get("root") or r[1] != newest.get("entries"):
        return "checkpoint_receipt"
    if not r[3]:
        return "checkpoint_receipt"
    try:
        if (datetime.now(timezone.utc)
                - parse_ts(r[2])).total_seconds() > 26 * 3600:
            return "checkpoint_receipt"
    except (ValueError, TypeError):
        return "checkpoint_receipt"
    return None


def share_gate_open(agency):
    """S8/S10 + P7: the gate as share_gate_missing judges it now."""
    return share_gate_missing(agency) is None


def list_registry_names():
    return [r[0] for r in db.execute(
        "SELECT list_name FROM list_registry ORDER BY list_name")]


def hit_public(rec, show_suppressed=False):
    """A hit as the API returns it. S3: a suppressed hit's plate
    text reaches ONLY the supervisor queue — every other viewer
    gets the keyed ref, so the listing cannot confirm the very
    plate the suppression exists to hide. P3: 'suppressed' here is
    the LIVE evaluation (hit_suppressed_now), not the ingest-time
    cache column — the record is re-judged on every read."""
    rec = dict(rec)
    live = hit_suppressed_now(rec.get("read_plate"),
                              rec.get("entry_plate"))
    rec["suppressed"] = 1 if live else 0
    if live and not show_suppressed:
        rec["plate_ref"] = plate_ref(rec.get("read_plate") or "")
        rec["read_plate"] = None
        if rec.get("entry_plate") is not None:
            rec["entry_plate"] = None
    return rec


def stats_body():
    jobs, overdue = jobs_status()
    # P3: the pending split is computed LIVE — a hit whose plate was
    # suppressed after ingest counts as suppressed-pending NOW.
    pend = db.execute(
        "SELECT read_plate, entry_plate FROM hits WHERE "
        "status='PENDING'").fetchall()
    n_supp_pend = sum(1 for rp, ep in pend if hit_suppressed_now(rp, ep))
    return {
        "reads": db.execute("SELECT COUNT(*) FROM reads").fetchone()[0],
        "hits": db.execute("SELECT COUNT(*) FROM hits").fetchone()[0],
        "hits_pending": len(pend),
        "pending": len(pend) - n_supp_pend,
        "suppressed_pending": n_supp_pend,
        "chain_entries": chain.count(),
        "plates_scanned_total": db.execute(
            "SELECT COALESCE(SUM(reads),0) FROM counters").fetchone()[0],
        "jobs_overdue": overdue,
        "retention_days": RETENTION_DAYS,
        "registry_version": REGISTRY_VERSION}


def retention_breach():
    """S1/S5 + P10: the registered stores past their retention
    class, named store by store. 1.2.1: this is a thin wrapper over
    sentinel.registry_breaches — the ONE breach implementation,
    shared with sentinel_audit.py and mirroring retention.py's
    purge semantics exactly (round 4 found Janus, the audit tool,
    and the purge disagreeing about the same database: scrubbed
    fragments failed the audit, scope='case' holds were invisible
    to Janus, and NOCTUA_BACKUP_DIR was honored by neither check).
    Returns the breached store names ([] = clean)."""
    breaches = sentinel.registry_breaches(
        db, RETENTION_DAYS, HOLD_DAYS, db_path=DB_PATH,
        evidence_dir=EVIDENCE_DIR)
    return sorted(breaches)


class Server(ThreadingHTTPServer):
    daemon_threads = True


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def setup(self):
        super().setup()
        # A stalled client must not freeze the service.
        self.connection.settimeout(30)

    # Responses are CAPTURED, not written, while the DB lock is held;
    # the wrapper serializes and writes after the lock is released,
    # so the lock covers database work only.
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
        """Read + parse the request body BEFORE the lock, capped at
        1 MB. Returns False if the request has already been answered
        (413/400)."""
        self._json = {}
        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            n = 0
        if n < 0:
            # P13: a negative Content-Length is a malformed request,
            # not a zero-length body (BaseHTTPRequestHandler would
            # otherwise read(-1) — the whole stream).
            self._resp = (400, {"error": "negative Content-Length"})
            self._flush_response()
            return False
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
            if user:
                _note_auth_fail(user)
            self.send_json(401, {"error": "authentication failed — "
                                          "named individual accounts only"})
        return rec

    def locked_out(self):
        if KEY_LOCKED:
            self.send_json(503, {"error": "audit key %s — Janus is "
                                          "locked (see /health)"
                                          % KEY_LOCK_REASON})
            return True
        return False

    def config_closed(self):
        """S13: stale-config fail-closed applies to ALL data
        endpoints, not just search."""
        if config_status()["fail_closed"]:
            self.send_json(503, {"error": "configuration has been "
                                          "stale >24h — the data "
                                          "surface is closed until a "
                                          "clean reload"})
            return True
        return False

    def deny_service_role(self, rec, action):
        """Service and partner accounts move data; they never read
        it. chain_auditor (S9) is fenced to its five paths by the
        dispatcher; this answers role failures on data endpoints."""
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
                if db.in_transaction:
                    db.commit()
            except Exception as exc:  # a handler bug must still answer
                try:
                    db.rollback()
                except Exception:
                    pass
                self._resp = (500, {"error": f"internal: {exc}"})
        # P11: sink copies stream only AFTER the commit lands;
        # flush_deferred presence-checks each queued entry, so a
        # rolled-back write never reaches the sink.
        try:
            chain.flush_deferred()
        except Exception:
            pass
        self._flush_response()

    def _post(self):
        path = urlparse(self.path).path
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        if rec["role"] == "chain_auditor":
            # S9: the chain_auditor has NO write surface at all.
            return self.send_json(403, {"error": "chain_auditor is "
                                                "read-only"})
        if path == "/reads":
            return self._post_reads(rec)
        if path == "/heartbeat":
            if rec["role"] != "jobs":
                return self.send_json(403, {"error": "heartbeats are the "
                                                   "jobs role only"})
            d = self.body_json()
            job = str(d.get("job", "")).strip()
            if not job:
                return self.send_json(400, {"error": "job is required"})
            # ok must be EXPLICIT. A heartbeat that does not say
            # ok:true is recorded as a failure — silence about
            # success is not success.
            ok = d.get("ok") is True
            db.execute(
                "INSERT INTO heartbeats(job,ts,ok,detail) VALUES(?,?,?,?) "
                "ON CONFLICT(job) DO UPDATE SET ts=excluded.ts, "
                "ok=excluded.ok, detail=excluded.detail",
                (job, now_iso(), 1 if ok else 0,
                 str(d.get("detail", ""))[:500]))
            chain.append("HEARTBEAT", {"job": job, "ok": ok})
            db.commit()
            return self.send_json(200, {"result": "heartbeat recorded",
                                        "job": job, "ok": ok})
        if path == "/hotlist":
            return self._post_hotlist(rec)
        if path == "/lists":
            if rec["role"] != "supervisor":
                return self.send_json(403, {"error": "the list registry "
                                                   "is supervisor-managed"})
            d = self.body_json()
            name = (d.get("list_name") or "").strip()
            if not name or re.search(r"\b\d{4}-\d+\b", name):
                return self.send_json(400, {
                    "error": "list_name is required and must not carry "
                             "a case number — list names print in the "
                             "public report"})
            db.execute("INSERT OR IGNORE INTO list_registry(list_name,"
                       " created_by, ts) VALUES(?,?,?)",
                       (name, rec["user"], now_iso()))
            chain.append("LIST_REGISTER", {"list": name,
                                           "by": rec["user"]})
            db.commit()
            return self.send_json(201, {"result": "list registered",
                                        "list_name": name})
        if path == "/verify":
            return self._post_verify(rec)
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
            chain.append("OUTCOME_UPDATE", {
                "hit": d["hit_id"], "arrest": arrest,
                "prosecution": ("unreported" if pros is None else pros),
                "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "outcome updated",
                                        "hit": d["hit_id"],
                                        "arrest": arrest,
                                        "prosecution": pros})
        if path == "/holds":
            return self._post_holds(rec)
        if path == "/holds/release":
            return self._post_hold_release(rec)
        if path == "/suppressions":
            return self._post_suppression(rec)
        if path == "/suppressions/release":
            return self._post_suppression_release(rec)
        if path.startswith("/tier3/"):
            if self.config_closed():
                return
            return self._tier3_post(path, rec)
        if path.startswith("/evidence/"):
            if self.config_closed():
                return
            return self._evidence_post(path, rec)
        if path.startswith("/compact/") or path == "/share/query":
            return self._compact_post(path, rec)
        if path == "/report/compile":
            return self._report_compile(rec)
        if path == "/audit/anchor-accept":
            return self._anchor_accept(rec)
        return self.send_json(404, {"error": "no such route"})

    # ---------------- ingest (S3, S4, S14) ----------------
    def _hits_for_read(self, plate, state, ts, cam):
        """Hot-list matching for one stored read: lists_checked
        provenance (S14), membership matching on the canonical
        plate, hit + outcome births, ALERT chains. Shared by fresh
        ingest and by the supersede path (P13) so a corrected read
        is matched by exactly the rules a fresh read is."""
        # Provenance (S14): every read is checked against every
        # active list; record which lists those were, per day, so
        # the statutory report can name lists with zero matches.
        for (ln,) in db.execute(
                "SELECT DISTINCT list_source FROM hotlist_members "
                "WHERE active=1").fetchall():
            db.execute("INSERT OR IGNORE INTO lists_checked(day,"
                       "list_name) VALUES(?,?)", (ts[:10], ln))
        # Match: memberships on the canonical plate. State rule: an
        # entry matches when its state is unknown, the read's state
        # is unknown, or they agree — a state is a bridge's guess,
        # not a vehicle's identity (S3).
        memberships = db.execute(
            "SELECT plate, state, list_source, case_no, category, "
            "expires_ts FROM hotlist_members WHERE plate=? AND "
            "active=1 AND (state=? OR state='' OR ?='')",
            (plate, state, state)).fetchall()
        hit_ids = []
        for m_plate, m_state, m_list, m_case, m_cat, m_exp in memberships:
            if m_exp and m_exp <= ts:
                # An expired entry alerts no one. It auto-deactivates;
                # the expiry is chained in the same transaction.
                db.execute(
                    "UPDATE hotlist_members SET active=0 WHERE "
                    "plate=? AND state=? AND list_source=? AND "
                    "case_no=?", (m_plate, m_state, m_list, m_case))
                chain.append("HOTLIST_EXPIRED", {
                    "plate_ref": plate_ref(plate), "by": "ingest"})
                continue
            # A hit on a suppressed plate is flagged at ingest so it
            # routes to the supervisor-only queue and never surfaces
            # in /hits or search results. (The flag is a cache; P3
            # judges suppression live at every read.)
            supp = 1 if is_suppressed(plate) else 0
            cur = db.execute(
                "INSERT INTO hits(ts,cam,read_plate,entry_plate,state,"
                "list_name,category,suppressed) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (ts, cam, plate, m_plate, state, m_list, m_cat, supp))
            hit_id = cur.lastrowid
            hit_ids.append(hit_id)
            # S14: the outcome record is born at ALERT time,
            # unresolved. Verification updates it; nothing deletes
            # it inside the 18-month window.
            db.execute(
                "INSERT INTO outcomes(hit_id, list_name, category, "
                "confirmed, arrest, prosecution, reviewed, status, "
                "hit_ts) VALUES(?,?,?,0,0,NULL,0,'unresolved',?)",
                (hit_id, m_list, m_cat, ts))
            chain.append("ALERT", {"hit": hit_id, "cam": cam,
                                   "category": category_enum(m_cat)})
        return hit_ids

    def _post_reads(self, rec):
        if rec["role"] != "ingest":
            return self.send_json(403, {"error": "ingest is the "
                                               "ingest role only"})
        d = self.body_json()
        raw_plate = d.get("plate")
        cam = d.get("cam")
        if not raw_plate or not cam:
            return self.send_json(400, {"error": "plate and cam are "
                                               "required"})
        plate = normalize_plate(raw_plate)
        if cam not in CAMERAS:
            # S4: an unregistered camera is not a data source. "No
            # new cameras without a vote" is a config fact now, not
            # a hope — the registry is the vote's record.
            chain.append("INGEST_REJECTED", {
                "cam": cam, "plate_ref": plate_ref(plate),
                "reason": "unregistered_camera"})
            return self.send_json(403, {
                "error": "camera %s is not in the camera registry — "
                         "its reads are not accepted" % cam})
        # S4: honesty about what the camera did NOT say. Missing
        # state is "" (unknown), missing confidence is NULL. 1.0/1.1
        # fabricated "AR" and 0.95 — a confidence the camera never
        # produced ended up in evidence files.
        state = (d.get("state") or "").upper()
        conf = d.get("conf")
        if conf is not None:
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = None
        event_id = d.get("event_id") or None
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
        if event_id:
            # Persistent dedupe (S4): a redelivered event returns the
            # ORIGINAL read id — the bridge's memory-only set was
            # never a dedupe boundary, just a hope with a TTL.
            # 1.2.1 (P13/A12): dedupe is on the EVENT, not on the
            # first OCR guess. Frigate sends a partial 'update' read
            # and then the corrected final 'end' read under the same
            # event id; 1.2 dropped the correction as a duplicate
            # and the stolen plate never alerted. A redelivery with
            # a DIFFERENT plate, or a HIGHER confidence, SUPERSEDES
            # the stored read in place (READ_SUPERSEDED chained) and
            # is re-matched — the corrected final OCR wins.
            dup = db.execute(
                "SELECT id, plate, conf, ts FROM reads WHERE cam=? "
                "AND event_id=?", (cam, event_id)).fetchone()
            if dup:
                old_id, old_plate, old_conf, old_ts = dup
                better_conf = conf is not None and (
                    old_conf is None or conf > old_conf)
                if plate == old_plate and not better_conf:
                    return self.send_json(200, {"result": "duplicate",
                                                "read_id": old_id})
                db.execute(
                    "UPDATE reads SET plate=?, plate_raw=?, state=?, "
                    "conf=?, cam_ts=?, skew_s=? WHERE id=?",
                    (plate, str(raw_plate), state, conf, cam_ts,
                     skew_s, old_id))
                # Any PENDING hit the superseded OCR produced is
                # withdrawn with its outcome record; decided hits
                # are history and stay.
                stale = [r[0] for r in db.execute(
                    "SELECT id FROM hits WHERE cam=? AND ts=? AND "
                    "read_plate=? AND status='PENDING'",
                    (cam, old_ts, old_plate)).fetchall()]
                for hid in stale:
                    db.execute("DELETE FROM outcomes WHERE hit_id=?",
                               (hid,))
                    db.execute("DELETE FROM hits WHERE id=?", (hid,))
                chain.append("READ_SUPERSEDED", {
                    "read": old_id, "cam": cam,
                    "plate_ref": plate_ref(plate),
                    "withdrawn_hits": len(stale)})
                hit_ids = self._hits_for_read(plate, state, old_ts,
                                              cam)
                db.execute(
                    "INSERT INTO counters(day,camera_id,reads,alerts) "
                    "VALUES(?,?,0,?) ON CONFLICT(day,camera_id) DO "
                    "UPDATE SET alerts=alerts+excluded.alerts",
                    (old_ts[:10], cam, len(hit_ids)))
                db.commit()
                resp = {"result": "superseded", "read_id": old_id}
                if hit_ids:
                    resp = {"result": "ALERT", "hit_id": hit_ids[0],
                            "hit_ids": hit_ids, "read_id": old_id,
                            "superseded": True}
                return self.send_json(200, resp)
        cur = db.execute(
            "INSERT INTO reads(ts,cam,plate,plate_raw,state,conf,"
            "cam_ts,skew_s,event_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (ts, cam, plate, str(raw_plate), state, conf, cam_ts,
             skew_s, event_id))
        read_id = cur.lastrowid
        hit_ids = self._hits_for_read(plate, state, ts, cam)
        # Cumulative counters: the six-month report's plates_scanned
        # must survive the retention deletes, so it is counted here,
        # at ingest, in a table retention never touches (for reads).
        db.execute(
            "INSERT INTO counters(day,camera_id,reads,alerts) "
            "VALUES(?,?,1,?) ON CONFLICT(day,camera_id) DO UPDATE "
            "SET reads=reads+1, alerts=alerts+excluded.alerts",
            (ts[:10], cam, len(hit_ids)))
        db.commit()
        if skew_s is not None:
            if skew_s < -5:
                # Camera clock AHEAD of receipt: real skew.
                chain.append("CLOCK_SKEW", {"cam": cam,
                                            "skew_s": skew_s})
            elif skew_s > 300:
                # Far behind receipt: a replayed backlog, not skew.
                _backfill_note(cam, skew_s)
        _backfill_flush_idle()
        resp = {"result": "stored", "read_id": read_id}
        if skew_s is not None:
            resp["clock_skew_s"] = skew_s
        if hit_ids:
            resp = {"result": "ALERT", "hit_id": hit_ids[0],
                    "hit_ids": hit_ids, "read_id": read_id}
            if skew_s is not None:
                resp["clock_skew_s"] = skew_s
        return self.send_json(201, resp)

    # ---------------- hot list (S14 membership) ----------------
    def _post_hotlist(self, rec):
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
        state = (d.get("state") or "").upper()
        if not plate:
            return self.send_json(400, {"error": "plate is required"})
        if is_suppressed(plate):
            # Listing a protected plate would route its reads into a
            # workflow the order forbids. Refused, and the conflict
            # itself is chained.
            chain.append("SUPPRESSION_CONFLICT", {
                "plate_ref": plate_ref(plate), "by": rec["user"],
                "action": "hotlist add"})
            return self.send_json(403, {
                "error": "that plate is under a protection-order "
                         "suppression — it cannot be hot-listed"})
        list_name = (d.get("list_name") or "Local agency list").strip()
        if not db.execute("SELECT 1 FROM list_registry WHERE "
                          "list_name=?", (list_name,)).fetchone():
            # S14: report list names come from a controlled
            # vocabulary — a supervisor registers the list first.
            # (1.1 sanitized free text; a sanitizer is a hope, a
            # registry is a fact.)
            return self.send_json(400, {
                "error": "list_name %r is not in the list registry — "
                         "a supervisor must register it first "
                         "(POST /lists)" % list_name})
        db.execute(
            "INSERT INTO hotlist_members(plate,state,list_source,"
            "case_no,category,added_by,added_ts,expires_ts,active) "
            "VALUES(?,?,?,?,?,?,?,?,1) ON CONFLICT(plate,state,"
            "list_source,case_no) DO UPDATE SET "
            "category=excluded.category, added_by=excluded.added_by, "
            "added_ts=excluded.added_ts, "
            "expires_ts=excluded.expires_ts, active=1",
            (plate, state, list_name, d["case"], d["category"],
             rec["user"], now_iso(), d.get("expires") or None))
        chain.append("HOTLIST_ADD", {
            "plate_ref": plate_ref(plate),
            "category": category_enum(d["category"]), "by": rec["user"],
            "case_hash": case_hash(d["case"])})
        db.commit()
        return self.send_json(201, {"result": "added"})

    # ---------------- verify (S3, S14) ----------------
    def _post_verify(self, rec):
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
        hit = db.execute("SELECT entry_plate, category, ts, list_name, "
                         "suppressed, read_plate FROM hits WHERE id=? "
                         "AND status='PENDING'",
                         (d["hit_id"],)).fetchone()
        if not hit:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hit verification",
                                     "hit": d.get("hit_id"),
                                     "reason": "hit_not_pending"})
            return self.send_json(409, {"error": "hit not found or "
                                               "already decided"})
        if hit_suppressed_now(hit[5], hit[0]) \
                and rec["role"] != "supervisor":
            # S3: a suppressed hit moves ONLY through the supervisor
            # queue — a detective cannot verify it directly, however
            # they learned its id.
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hit verification",
                                     "hit": d.get("hit_id"),
                                     "reason": "suppressed_queue"})
            return self.send_json(403, {
                "error": "that hit is under a protection-order "
                         "suppression — it moves through the "
                         "supervisor queue only"})
        status = "VERIFIED" if decision == "confirm" else "REJECTED"
        db.execute("UPDATE hits SET status=?, decided_by=?, case_no=?, "
                   "decided_ts=? WHERE id=? AND status='PENDING'",
                   (status, rec["user"], d["case"], now_iso(),
                    d["hit_id"]))
        # The outcome record was created at ALERT time (S14);
        # verification resolves it. prosecution stays NULL — unknown
        # until the prosecutor feedback loop reports it.
        db.execute(
            "UPDATE outcomes SET confirmed=?, reviewed=1, "
            "status='reviewed', updated_by=?, updated_ts=? "
            "WHERE hit_id=?",
            (1 if decision == "confirm" else 0, rec["user"], now_iso(),
             d["hit_id"]))
        chain.append("VERIFY", {"hit": d["hit_id"], "result": status,
                                "by": rec["user"],
                                "case_hash": case_hash(d["case"])})
        db.commit()
        return self.send_json(200, {"result": status})

    # ---------------- holds (S17) ----------------
    def _post_holds(self, rec):
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
            ok, reason = case_gate(d.get("ref"))
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "hold place",
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
        # P13: review_by is a real DATE in (today, today+HOLD_DAYS].
        # 1.2 stored whatever string arrived — "9999-12-31" made a
        # hold immortal and kept its hit past the 150-day statutory
        # cap while /health stayed green. A hold is a review
        # appointment, not a retention override.
        today = datetime.now(timezone.utc).date()
        raw_rb = d.get("review_by")
        if raw_rb:
            try:
                rb_date = date.fromisoformat(str(raw_rb)[:10])
                if len(str(raw_rb)[:10]) != 10:
                    raise ValueError("not a date")
            except ValueError:
                return self.send_json(400, {
                    "error": "review_by must be a real ISO date "
                             "(YYYY-MM-DD)"})
            if rb_date <= today or rb_date > today + timedelta(
                    days=HOLD_DAYS):
                return self.send_json(400, {
                    "error": "review_by must be after today and no "
                             "later than today + HOLD_DAYS (%d days)"
                             % HOLD_DAYS})
            review_by = rb_date.isoformat()
        else:
            review_by = (today + timedelta(
                days=min(90, HOLD_DAYS))).isoformat()
        cur = db.execute(
            "INSERT INTO holds(scope, ref, reason, placed_by, "
            "placed_ts, active, review_by) VALUES(?,?,?,?,?,1,?)",
            (d["scope"], str(d.get("ref", "")), d.get("reason", ""),
             rec["user"], now_iso(), review_by))
        fields = {"hold": cur.lastrowid, "scope": d["scope"],
                  "by": rec["user"], "review_by": review_by}
        if d["scope"] == "hit":
            # S17: HOLD entries carry hit_id, so custody excerpts
            # find them by the hit they protect.
            hid = _as_int(d.get("ref"))
            if hid is not None:
                fields["hit"] = hid
        else:
            fields["case_hash"] = case_hash(d.get("ref"))
        chain.append("HOLD_PLACE", fields)
        db.commit()
        return self.send_json(201, {"result": "hold placed",
                                    "hold_id": cur.lastrowid,
                                    "review_by": review_by})

    def _post_hold_release(self, rec):
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
            # The gate runs at release too — its result is chained,
            # but a release is never BLOCKED by it: a case closing
            # must not trap held data past its review date.
            ok, _r = case_gate(row[2])
            fields["case_gate_ok"] = ok
            fields["case_hash"] = case_hash(row[2])
        elif row[1] == "hit":
            hid = _as_int(row[2])
            if hid is not None:
                fields["hit"] = hid
        db.execute("UPDATE holds SET active=0, released_by=?, "
                   "released_ts=? WHERE id=?",
                   (rec["user"], now_iso(), d["hold_id"]))
        chain.append("HOLD_RELEASE", fields)
        db.commit()
        return self.send_json(200, {"result": "hold released"})

    # ---------------- suppressions (S3) ----------------
    def _post_suppression(self, rec):
        if rec["role"] != "supervisor":
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "suppression place",
                                     "reason": "role"})
            return self.send_json(403, {"error": "suppressions are "
                                               "supervisor-only"})
        d = self.body_json()
        # A suppression is placed against the protection ORDER (its
        # court reference), not against a case number. A case may be
        # supplied for the file; when it is, it runs the shared gate.
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
        # The state is RECORDED (the order may name one) but is not
        # part of the suppression's identity (S3).
        state = (d.get("state") or "").upper()
        if not plate:
            return self.send_json(400, {"error": "plate is required"})
        ref = plate_ref(plate)
        db.execute(
            "INSERT INTO suppressions(plate_ref, plate, state, "
            "order_ref, placed_by, case_no, ts, active) "
            "VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(plate_ref) DO "
            "UPDATE SET active=1, plate=excluded.plate, "
            "state=excluded.state, order_ref=excluded.order_ref, "
            "placed_by=excluded.placed_by, case_no=excluded.case_no, "
            "ts=excluded.ts, release_requested_by=NULL, "
            "release_order_ref=NULL, released_ts=NULL",
            (ref, plate, state, order_ref, rec["user"],
             d.get("case"), now_iso()))
        chain.append("SUPPRESSION_PLACE", {"plate_ref": ref,
                                           "by": rec["user"]})
        db.commit()
        # Near-match warning: raw plate forms already in the data
        # that canonicalize to this plate (a camera read it with a
        # space, an operator typed a hyphen) — the operator should
        # know the raw forms on file. (Identity is canonical either
        # way; the warning is about the RECORD, not the matching.)
        variants = set()
        for (raw,) in db.execute(
                "SELECT DISTINCT plate_raw FROM reads").fetchall():
            if raw and raw != plate and normalize_plate(raw) == plate:
                variants.add(raw)
        return self.send_json(201, {
            "result": "suppression placed",
            "warning_near_matches": sorted(variants)})

    def _post_suppression_release(self, rec):
        if rec["role"] != "supervisor":
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "suppression release",
                                     "reason": "role"})
            return self.send_json(403, {"error": "suppression release "
                                               "is supervisor-only"})
        d = self.body_json()
        plate = normalize_plate(d.get("plate"))
        ref = plate_ref(plate)
        row = db.execute(
            "SELECT order_ref, release_requested_by FROM suppressions "
            "WHERE plate_ref=? AND active=1", (ref,)).fetchone()
        if not row:
            return self.send_json(404, {"error": "no active suppression "
                                               "for that plate"})
        order_ref, requested_by = row
        # Two-key release: the first supervisor requests, a DIFFERENT
        # supervisor confirms — and the order reference on file must
        # be repeated, so a release cannot ride on a misremembered
        # order.
        if requested_by is None:
            db.execute("UPDATE suppressions SET "
                       "release_requested_by=?, release_order_ref=? "
                       "WHERE plate_ref=?",
                       (rec["user"], d.get("order_ref"), ref))
            chain.append("SUPPRESSION_RELEASE_REQUEST", {
                "plate_ref": ref, "by": rec["user"]})
            db.commit()
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
                   "release_requested_by=NULL, release_order_ref=NULL, "
                   "released_ts=? WHERE plate_ref=?",
                   (now_iso(), ref))
        chain.append("SUPPRESSION_RELEASE", {
            "plate_ref": ref, "by": rec["user"],
            "requested_by": requested_by})
        db.commit()
        return self.send_json(200, {"result": "suppression released"})


    def _report_compile(self, rec):
        if rec["role"] not in DATA_ROLES:
            return self.send_json(403, {"error": "role cannot compile "
                                                "reports"})
        d = self.body_json()
        frm = d.get("from", "")
        to = d.get("to", "9999-12-31T23:59:59Z")
        body = compute_report(frm, to)
        body_json = json.dumps(body, sort_keys=True)
        cur = db.execute(
            "INSERT INTO report_snapshots(from_ts, to_ts, compiled_by, "
            "compiled_ts, body) VALUES(?,?,?,?,?)",
            (frm, to, rec["user"], now_iso(), body_json))
        # S14: the compile chains a HASH of the snapshot contents —
        # a snapshot whose body is later edited no longer matches
        # its chain entry, which is the point of compiling one.
        chain.append("REPORT_COMPILE", {
            "snapshot": cur.lastrowid, "by": rec["user"],
            "body_hash": sha(body_json)})
        db.commit()
        return self.send_json(201, {"result": "snapshot compiled",
                                    "snapshot_id": cur.lastrowid,
                                    "report": body})

    def _anchor_accept(self, rec):
        """Two-key clearing of a startup anchor mismatch: a
        supervisor records acceptance, then the AUDITOR — a
        different person, outside the chain of command — confirms.
        The accepted state (the disagreeing checkpoints) is recorded
        (S6), so a restart on the same state does not re-trigger;
        a NEW disagreement does."""
        if not anchor_mismatch():
            return self.send_json(200, {"result": "no anchor mismatch "
                                                  "to accept"})
        pending = _meta_get("anchor_accept_by")
        if rec["role"] == "supervisor" and not pending:
            # P11: meta write + chain entry + commit are ONE
            # transaction (1.2's _meta_set committed first).
            db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                       "ON CONFLICT(key) DO UPDATE SET "
                       "value=excluded.value",
                       ("anchor_accept_by", rec["user"]))
            chain.append("ANCHOR_ACCEPT_REQUEST", {"by": rec["user"]})
            db.commit()
            return self.send_json(200, {
                "result": "acceptance recorded — the auditor must "
                          "confirm to clear the mismatch"})
        if rec["role"] == "auditor" and pending:
            if rec["user"] == pending:
                return self.send_json(403, {"error": "the two-key rule "
                                                   "forbids self-confirm"})
            # P11/A15: record the IDS of the checkpoints that
            # disagree NOW. They stay accepted; tomorrow's new
            # checkpoint is judged on its own facts.
            accepted = _accepted_checkpoint_ids()
            for cp in _bad_checkpoints():
                accepted.add(tuple(_checkpoint_id(cp)))
            db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                       "ON CONFLICT(key) DO UPDATE SET "
                       "value=excluded.value",
                       ("anchor_accepted_ids",
                        json.dumps(sorted(
                            [list(x) for x in accepted],
                            key=lambda x: str(x)))))
            db.execute("DELETE FROM meta WHERE key IN "
                       "('anchor_mismatch','anchor_accept_by',"
                       "'anchor_accepted')")
            chain.append("ANCHOR_ACCEPT", {"requested_by": pending,
                                           "by": rec["user"],
                                           "accepted_checkpoints":
                                           len(accepted)})
            db.commit()
            return self.send_json(200, {"result": "anchor mismatch "
                                                  "cleared"})
        return self.send_json(403, {
            "error": "anchor acceptance is supervisor-then-auditor, "
                     "two keys"})

    # ---------------- Tier 3 two-key workflow (S2) ----------------
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
                                         "case_hash": case_hash(case_no),
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, basis_type, status, "
                "created_ts) VALUES(?,?,?,?,?,?,'PENDING',?)",
                (rec["user"], case_no, why, frag, basis, basis_type,
                 now_iso()))
            # S11: the chain carries the coded basis_type and the
            # fragment's ref — the warrant's free text stays in the
            # DB (and is itself retention-classed, S1).
            chain.append("TIER3_REQUEST", {
                "request": cur.lastrowid, "by": rec["user"],
                "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "basis_type": basis_type})
            db.commit()
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
            # The case gate re-runs at execution — a case that closed
            # while the request waited no longer opens.
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "request": d["request_id"],
                                         "reason": reason})
                return self.send_json(403, {
                    "error": "BLOCKED at execution: "
                             + CASE_GATE_MSGS[reason]})
            results = run_search(frag, "full")
            read_ids = [r["id"] for r in results["reads"]]
            hit_ids = [r["id"] for r in results["hits"]]
            n = len(read_ids) + len(hit_ids)
            # S2: store ONLY the matched ids. The result body is
            # resolved live at read time, through whatever the
            # suppression layer and the case list say THEN — a
            # stored body could do neither, and outlived everything.
            db.execute(
                "UPDATE tier3_requests SET status='EXECUTED', "
                "decided_by=?, decided_ts=?, results_count=?, "
                "results=NULL, results_read_ids=?, results_hit_ids=? "
                "WHERE id=?",
                (rec["user"], now_iso(), n, json.dumps(read_ids),
                 json.dumps(hit_ids), d["request_id"]))
            chain.append("TIER3_APPROVE", {
                "request": d["request_id"], "by": rec["user"],
                "requester": requester, "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "basis_type": basis_type})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 approved search",
                "tier": 3, "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "result_count": n,
                "via_request": d["request_id"], "emergency": False})
            db.commit()
            # The approver does NOT receive the results. The
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
            chain.append("TIER3_DENY", {"request": d["request_id"],
                                        "by": rec["user"],
                                        "requester": row[0]})
            db.commit()
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
                # The emergency path requires auth_basis too —
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
                                         "case_hash": case_hash(case_no),
                                         "reason": reason})
                return self.send_json(403,
                                      {"error": CASE_GATE_MSGS[reason]})
            # An unreviewed emergency older than 72h locks the
            # emergency path for that user until it is reviewed.
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
            read_ids = [r["id"] for r in results["reads"]]
            hit_ids = [r["id"] for r in results["hits"]]
            n = len(read_ids) + len(hit_ids)
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, basis_type, status, "
                "created_ts, decided_by, decided_ts, emergency, "
                "needs_review, results_count, results, "
                "results_read_ids, results_hit_ids) "
                "VALUES(?,?,?,?,?,?,'EMERGENCY',?,?,?,1,1,?,NULL,?,?)",
                (rec["user"], case_no, why, frag, basis, basis_type,
                 now_iso(), rec["user"], now_iso(), n,
                 json.dumps(read_ids), json.dumps(hit_ids)))
            chain.append("TIER3_EMERGENCY", {
                "request": cur.lastrowid, "by": rec["user"],
                "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "basis_type": basis_type,
                "review": "mandatory post-hoc review queued"})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 emergency search",
                "tier": 3, "case_hash": case_hash(case_no),
                "plate_ref": frag_ref(frag), "result_count": n,
                "via_request": cur.lastrowid, "emergency": True})
            db.commit()
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
            # The finding is an enum — a bare "ok" is not a review.
            # The prose note stays in the DB.
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
            chain.append("TIER3_REVIEW", {"request": d["request_id"],
                                          "by": rec["user"],
                                          "finding": finding})
            db.commit()
            return self.send_json(200, {"result": "REVIEWED",
                                        "request_id": d["request_id"]})
        return self.send_json(404, {"error": "no such route"})

    # ---------------- evidence lifecycle (S3, S17) ----------------
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
                "category,status,decided_by,case_no,decided_ts,"
                "suppressed FROM hits WHERE id=?",
                (d.get("hit_id"),)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no such hit"})
            hkeys = ("id", "ts", "cam", "read_plate", "entry_plate",
                     "state", "list_name", "category", "status",
                     "decided_by", "case_no", "decided_ts", "suppressed")
            hit_rec = dict(zip(hkeys, hit))
            # P3: the export gate judges suppression LIVE — the
            # stored stamp is a cache, never the authority.
            hit_rec["suppressed"] = 1 if hit_suppressed_now(
                hit_rec["read_plate"], hit_rec["entry_plate"]) else 0
            if hit_rec["suppressed"] and rec["role"] != "supervisor":
                # S3: a suppressed hit's evidence moves only through
                # the supervisor queue.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": hit[0],
                                         "reason": "suppressed_queue"})
                return self.send_json(403, {
                    "error": "that hit is under a protection-order "
                             "suppression — export is supervisor-only"})
            # Only a VERIFIED hit is evidence, and only under the
            # case it was verified under.
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
            # S17: a re-export deletes the PRIOR bundle in the same
            # operation — 1.1 left the old bundle orphaned on disk,
            # a plate archive nobody's retention knew about (S1).
            prior = db.execute("SELECT bundle FROM evidence WHERE "
                               "hit_id=?", (hit[0],)).fetchone()
            os.makedirs(EVIDENCE_DIR, mode=0o700, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bundle_name = "hit-%d-%s" % (hit[0], stamp)
            bundle_path = os.path.join(EVIDENCE_DIR, bundle_name)
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
            if prior and prior[0] and prior[0] != bundle_name:
                old_path = os.path.join(EVIDENCE_DIR, prior[0])
                if os.path.isdir(old_path):
                    shutil.rmtree(old_path)
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
            chain.append("EVIDENCE_EXPORT", {
                "hit": hit[0], "case_hash": case_hash(case_no),
                "manifest": mhash, "scope": scope, "expanded": expand,
                "by": rec["user"]})
            db.commit()
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
                # There is nothing to release until an export exists —
                # a sign-off cannot precede the evidence.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence release",
                                         "hit": d.get("hit_id"),
                                         "reason": "no_export"})
                return self.send_json(409, {
                    "error": "no export exists for that hit — release "
                             "requires an export first"})
            released = now_iso()
            # S17: release starts the destruction clock — the bundle
            # must be destroyed by release + 30 days, and /health
            # names it when the date passes.
            destroy_by = (parse_ts(released)
                          + timedelta(days=30)).strftime(
                              "%Y-%m-%dT%H:%M:%SZ")
            db.execute(
                "UPDATE evidence SET prosecutor_name=?, "
                "prosecutor_date=?, released_by=?, released_ts=?, "
                "destroy_by=? WHERE hit_id=?",
                (pname, pdate, rec["user"], released, destroy_by,
                 d["hit_id"]))
            chain.append("EVIDENCE_RELEASE", {"hit": d["hit_id"],
                                              "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "released",
                                        "hit": d["hit_id"],
                                        "destroy_by": destroy_by})
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
            chain.append("EVIDENCE_DESTROY", {"hit": d["hit_id"],
                                              "by": rec["user"]})
            db.commit()
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
            # SS 12-12-1804(b) has two exits — charges that concluded,
            # and an investigation that never became charges. A
            # disposition records the second (and the conclusion of
            # the first) and, once CONFIRMED by a different
            # supervisor, releases the data for deletion exactly as a
            # prosecutor sign-off does. Free text stays in the DB.
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
            chain.append("EVIDENCE_DISPOSITION", {
                "hit": d["hit_id"], "outcome": outcome, "by": rec["user"],
                "status": "awaiting confirmation"})
            db.commit()
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
            confirmed = now_iso()
            destroy_by = (parse_ts(confirmed)
                          + timedelta(days=30)).strftime(
                              "%Y-%m-%dT%H:%M:%SZ")
            db.execute("UPDATE evidence SET disp_confirmed_by=?, "
                       "disp_confirmed_ts=?, destroy_by=? WHERE hit_id=?",
                       (rec["user"], confirmed, destroy_by, d["hit_id"]))
            chain.append("EVIDENCE_DISPOSITION_CONFIRM", {
                "hit": d["hit_id"], "outcome": row[0], "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "disposition confirmed "
                                                  "— data released for "
                                                  "deletion",
                                        "hit": d["hit_id"],
                                        "destroy_by": destroy_by})
        return self.send_json(404, {"error": "no such route"})


    # ---------------- Compact / shares / rotation (S7–S10, S12) ----------------
    def _compact_post(self, path, rec):
        d = self.body_json()
        if path == "/share/query":
            return self._share_query(rec, d)
        if path == "/compact/partners":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner add",
                                         "reason": "role"})
                return self.send_json(403, {"error": "partner management "
                                                   "is supervisor-only"})
            agency = (d.get("agency") or "").strip()
            endpoint = (d.get("endpoint") or "").strip()
            # S7: the partner's Ed25519 PUBLIC key is what a Compact
            # agency registers; its audit key (the plate-HMAC secret)
            # is NEVER sent or stored here — it never leaves the
            # partner's box either. Registration stores the
            # fingerprint of the supplied public key.
            pubkey_pem = (d.get("pubkey_pem") or "").strip()
            if not agency or not endpoint:
                return self.send_json(400, {"error": "agency and "
                                                   "endpoint are "
                                                   "required"})
            if not pubkey_pem:
                return self.send_json(400, {
                    "error": "pubkey_pem (the partner's Ed25519 public "
                             "key, PEM) is required"})
            try:
                fp = sentinel.pubkey_fingerprint(pubkey_pem)
            except (ValueError, TypeError):
                fp = None
            if not fp:
                return self.send_json(400, {"error": "pubkey_pem is not "
                                                   "a readable Ed25519 "
                                                   "public key"})
            if "://" not in endpoint:
                return self.send_json(400, {"error": "endpoint must be a "
                                                   "URL"})
            db.execute(
                "INSERT INTO partners(agency, endpoint, "
                "audit_key_fingerprint, pubkey_pem, agreement_ref, "
                "status, added_by, added_ts) VALUES(?,?,?,?,?,'active',"
                "?,?) ON CONFLICT(agency) DO UPDATE SET "
                "endpoint=excluded.endpoint, "
                "pubkey_pem=excluded.pubkey_pem, "
                "audit_key_fingerprint=excluded.audit_key_fingerprint, "
                "agreement_ref=excluded.agreement_ref",
                (agency, endpoint, fp, pubkey_pem,
                 (d.get("agreement_ref") or "").strip() or None,
                 rec["user"], now_iso()))
            chain.append("PARTNER_ADD", {"agency": agency, "by": rec["user"],
                                         "audit_key_fingerprint": fp})
            db.commit()
            return self.send_json(201, {
                "result": "partner registered", "agency": agency,
                "audit_key_fingerprint": fp})
        if path == "/compact/audit-result":
            # OUR auditor records the result of OUR audit of a
            # partner. S8: the REPORT is signed with OUR Ed25519
            # signing key (compact.py signs it), and the hash of the
            # report is what this endpoint records. The signature is
            # verified against OUR OWN public key first — this row
            # attests to work THIS agency's auditor did, so this
            # agency's key is the one that must have signed it. A
            # report that does not verify is not recorded at all.
            if rec["role"] not in ("auditor", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "compact audit-result",
                                         "reason": "role"})
                return self.send_json(403, {"error": "audit results are "
                                                   "recorded by the "
                                                   "auditor role"})
            agency = (d.get("agency") or "").strip()
            report = d.get("report")
            sig = (d.get("report_sig") or "").strip()
            if not isinstance(report, dict) or not sig:
                return self.send_json(400, {
                    "error": "report (object) and report_sig (base64 "
                             "Ed25519 signature) are required"})
            partner = db.execute(
                "SELECT 1 FROM partners WHERE agency=?",
                (agency,)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            if not SIGNING_PUB_PEM:
                return self.send_json(503, {
                    "error": "this agency has no signing key — signed "
                             "audit reports cannot be verified"})
            ok = sentinel.verify_bytes(
                SIGNING_PUB_PEM, sentinel.canonical_bytes(report), sig)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "compact audit-result",
                                         "agency": agency,
                                         "reason": "bad_report_sig"})
                return self.send_json(403, {
                    "error": "the report signature does not verify "
                             "against this agency's signing key"})
            if not isinstance(report.get("ok"), bool):
                return self.send_json(400, {"error": "report.ok must be "
                                                   "a boolean"})
            # P7/A3: the report is BOUND to its subject and its
            # moment. 1.2 verified the signature and nothing else —
            # a signed report from 2025 was stamped fresh with
            # now_iso(), and the same signed body could be re-filed
            # as a passing audit of a DIFFERENT partner. Now the
            # report must name the agency it is filed under, its own
            # ts must be within 26h, and the row stores the REPORT's
            # ts — the freshness the gate later reads is the
            # report's, not the filing's.
            if report.get("agency") != agency:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "compact audit-result",
                                         "agency": agency,
                                         "reason": "report_agency_mismatch"})
                return self.send_json(400, {
                    "error": "report.agency does not match the agency "
                             "the report is filed under"})
            try:
                report_age = (datetime.now(timezone.utc)
                              - parse_ts(report.get("ts") or "")
                              ).total_seconds()
            except (ValueError, TypeError):
                return self.send_json(400, {
                    "error": "report.ts must be a valid timestamp"})
            if report_age > 26 * 3600 or report_age < -3600:
                return self.send_json(409, {
                    "error": "report.ts is not within 26h — a stale "
                             "signed report cannot be re-filed as a "
                             "fresh audit"})
            report_hash = sha(sentinel.canonical_bytes(report).decode())
            ok_val = report.get("ok")
            db.execute(
                "INSERT INTO compact_audits(agency, ok, detail, "
                "report_hash, ts) VALUES(?,?,?,?,?)",
                (agency, 1 if ok_val else 0,
                 json.dumps(report, sort_keys=True)[:2000], report_hash,
                 report["ts"]))
            chain.append("COMPACT_AUDIT_RESULT", {
                "agency": agency, "ok": ok_val,
                "report_hash": report_hash, "by": rec["user"]})
            db.commit()
            return self.send_json(201, {"result": "audit result recorded",
                                        "agency": agency,
                                        "report_hash": report_hash})
        if path == "/compact/checkpoint-receipt":
            # S8: a receipt must name OUR NEWEST checkpoint, and the
            # partner's Ed25519 signature over (root, entries,
            # checkpoint_ts, agency) must verify against the registered
            # public key. A replay of an old receipt fails here: its
            # root/entries no longer match the newest checkpoint.
            agency = (d.get("agency") or "").strip()
            root = (d.get("checkpoint_root") or "").strip()
            entries = d.get("checkpoint_entries")
            cts = (d.get("checkpoint_ts") or "").strip()
            sig = (d.get("signature") or "").strip()
            if not agency or not root or not isinstance(entries, int) \
                    or not cts or not sig:
                return self.send_json(400, {
                    "error": "agency, checkpoint_root, checkpoint_entries, "
                             "checkpoint_ts and signature are required"})
            if rec["role"] != "partner" or rec["user"] != agency:
                # A receipt is the partner agency's own attestation,
                # posted under its own partner identity — an
                # operator account cannot file one on its behalf.
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "checkpoint-receipt",
                                         "agency": agency,
                                         "reason": "partner_identity"})
                return self.send_json(403, {
                    "error": "checkpoint receipts are posted by the "
                             "partner agency's own partner identity"})
            partner = db.execute(
                "SELECT pubkey_pem FROM partners WHERE agency=?",
                (agency,)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            newest = read_newest_checkpoint()
            if not newest:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "checkpoint-receipt",
                                         "agency": agency,
                                         "reason": "no_checkpoint"})
                return self.send_json(409, {"error": "this agency has no "
                                                   "checkpoint yet — "
                                                   "nothing to attest"})
            # Freshness is measured from the checkpoint's OWN
            # timestamp, not from when the receipt arrived: a receipt
            # attesting a stale checkpoint is not a live check.
            if newest.get("root") != root or \
                    newest.get("entries") != entries or \
                    newest.get("ts") != cts:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "checkpoint-receipt",
                                         "agency": agency,
                                         "reason": "stale_checkpoint"})
                return self.send_json(409, {
                    "error": "receipt does not name this agency's newest "
                             "checkpoint (root/entries/ts mismatch)"})
            payload = {"agency": agency, "checkpoint_ts": cts,
                       "entries": entries, "root": root}
            ok = sentinel.verify_bytes(
                partner[0], sentinel.canonical_bytes(payload), sig)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "checkpoint-receipt",
                                         "agency": agency,
                                         "reason": "bad_receipt_sig"})
                return self.send_json(403, {
                    "error": "the receipt signature does not verify "
                             "against the registered public key"})
            try:
                age_s = (datetime.now(timezone.utc)
                         - parse_ts(cts)).total_seconds()
            except (ValueError, TypeError):
                return self.send_json(400, {"error": "checkpoint_ts is not "
                                                   "a valid timestamp"})
            if age_s > 26 * 3600:
                return self.send_json(409, {
                    "error": "the newest checkpoint is older than 26h — "
                             "publish a fresh checkpoint before asking "
                             "for an attestation"})
            db.execute(
                "INSERT INTO compact_receipts(agency, root, entries, "
                "sig, checkpoint_ts, verified, received_ts) "
                "VALUES(?,?,?,?,?,1,?)",
                (agency, root, entries, sig, cts, now_iso()))
            chain.append("COMPACT_RECEIPT", {
                "agency": agency, "checkpoint_root": root,
                "checkpoint_entries": entries, "verified": True})
            db.commit()
            return self.send_json(201, {"result": "receipt recorded and "
                                                  "verified",
                                        "agency": agency,
                                        "checkpoint_root": root})
        if path == "/compact/suspend":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner suspend",
                                         "reason": "role"})
                return self.send_json(403, {"error": "partner suspension "
                                                   "is supervisor-only"})
            # P11/A21b: suspending a partner that does not exist is
            # an error, not a 200 with the caller's raw text chained.
            # (The agency field is scrubber-exempt because REGISTERED
            # agency ids are configuration; unregistered text never
            # reaches the chain through this endpoint now.)
            partner = db.execute("SELECT 1 FROM partners WHERE "
                                 "agency=?", (d.get("agency"),)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            db.execute("UPDATE partners SET status='suspended' WHERE "
                       "agency=?", (d.get("agency"),))
            chain.append("PARTNER_SUSPEND", {"agency": d.get("agency"),
                                             "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "partner suspended",
                                        "agency": d.get("agency")})
        if path == "/compact/reinstate":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner reinstate",
                                         "reason": "role"})
                return self.send_json(403, {"error": "partner "
                                                   "reinstatement is "
                                                   "supervisor-only"})
            # Reinstatement requires a FRESH audit — the stale record
            # a partner fell behind on cannot be re-validated by age.
            partner = db.execute("SELECT 1 FROM partners WHERE agency=?",
                                 (d.get("agency"),)).fetchone()
            if not partner:
                return self.send_json(404, {"error": "no such partner"})
            # P7: the LATEST audit row is the one with the highest
            # id — filing order, not the (now report-supplied) ts.
            row = db.execute(
                "SELECT ok, ts FROM compact_audits WHERE agency=? "
                "ORDER BY id DESC LIMIT 1",
                (d.get("agency"),)).fetchone()
            if not row or not row[0] or (datetime.now(timezone.utc)
                                         - parse_ts(row[1])).total_seconds() \
                    > 26 * 3600:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "partner reinstate",
                                         "agency": d.get("agency"),
                                         "reason": "no_fresh_audit"})
                return self.send_json(409, {
                    "error": "reinstatement requires a fresh (≤26h) "
                             "passing audit — submit one first"})
            db.execute("UPDATE partners SET status='active' WHERE "
                       "agency=?", (d.get("agency"),))
            chain.append("PARTNER_REINSTATE", {"agency": d.get("agency"),
                                               "by": rec["user"]})
            db.commit()
            return self.send_json(200, {"result": "partner reinstated",
                                        "agency": d.get("agency")})
        if path == "/compact/rotation":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "rotation publish",
                                         "reason": "role"})
                return self.send_json(403, {"error": "rotation publishing "
                                                   "is supervisor-only"})
            return self._rotation_publish(rec, d)
        if path == "/compact/rotation/void":
            latest = db.execute(
                "SELECT id FROM rotation_schedules ORDER BY id DESC "
                "LIMIT 1").fetchone()
            if not latest:
                return self.send_json(409, {"error": "no rotation cycle "
                                                   "exists to void"})
            pending = _meta_get("rotation_void_by")
            if rec["role"] == "supervisor" and not pending:
                # P11: one transaction — meta write, chain entry,
                # commit (1.2's _meta_set committed before the chain
                # append, splitting the act from its record).
                db.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                           "ON CONFLICT(key) DO UPDATE SET "
                           "value=excluded.value",
                           ("rotation_void_by", rec["user"]))
                chain.append("ROTATION_VOID_REQUEST", {"by": rec["user"]})
                db.commit()
                return self.send_json(200, {
                    "result": "void recorded — the auditor must confirm"})
            if rec["role"] == "auditor" and pending:
                if rec["user"] == pending:
                    return self.send_json(403, {"error": "the two-key "
                                                       "rule forbids "
                                                       "self-confirm"})
                db.execute("DELETE FROM rotation_schedules WHERE id=?",
                           (latest[0],))
                db.execute("DELETE FROM meta WHERE key='rotation_void_by'")
                chain.append("ROTATION_VOID", {"requested_by": pending,
                                               "by": rec["user"]})
                db.commit()
                return self.send_json(200, {"result": "rotation cycle "
                                                  "voided"})
            return self.send_json(403, {
                "error": "rotation void is supervisor-then-auditor, "
                         "two keys"})
        if path == "/compact/witness":
            # S12: the witness attests, per round of the active
            # cycle, that it verified the round auditor's checkpoint
            # signature and chain state. The attestation names the
            # cycle and round it covers — a free-floating "ok" would
            # attest nothing.
            # P9/A25: 1.2 let ANY authenticated role file one, with
            # no signature and no chain entry — the ingest service
            # account attested for another agency and history kept
            # no record. Now the filer is either a SUPERVISOR of
            # this agency, or the partner's REGISTERED AUDITOR
            # identity: an Ed25519 signature over the attestation,
            # verified against the public key registered for the
            # agency the attestation is about. Either way the filing
            # chains WITNESS_ATTEST in the same transaction.
            agency = (d.get("agency") or "").strip()
            cycle_start = (d.get("cycle_start") or "").strip()
            round_no = d.get("round")
            ok_val = d.get("ok")
            if not agency or not cycle_start \
                    or not isinstance(round_no, int) \
                    or isinstance(round_no, bool) \
                    or not isinstance(ok_val, bool):
                return self.send_json(400, {
                    "error": "agency, cycle_start, round (integer) and "
                             "ok (boolean) are required"})
            if rec["role"] == "supervisor":
                attested_by = rec["user"]
            else:
                partner = db.execute(
                    "SELECT pubkey_pem FROM partners WHERE agency=?",
                    (agency,)).fetchone()
                sig = (d.get("signature") or "").strip()
                attestation = {"agency": agency,
                               "cycle_start": cycle_start,
                               "round": round_no, "ok": ok_val}
                if not partner or not sig or not sentinel.verify_bytes(
                        partner[0],
                        sentinel.canonical_bytes(attestation), sig):
                    chain.append("BLOCKED", {
                        "user": rec["user"],
                        "action": "witness attestation",
                        "reason": "unverified_attestation"})
                    return self.send_json(403, {
                        "error": "witness attestations require a "
                                 "supervisor, or the partner's "
                                 "registered-key Ed25519 signature "
                                 "over the attestation"})
                attested_by = agency
            db.execute(
                "INSERT INTO witness_attestations(agency, cycle_start, "
                "round_no, ok, detail, ts) VALUES(?,?,?,?,?,?)",
                (agency, cycle_start, round_no, 1 if ok_val else 0,
                 (d.get("detail") or "")[:500], now_iso()))
            chain.append("WITNESS_ATTEST", {
                "agency": agency, "cycle_start": cycle_start,
                "round": round_no, "ok": ok_val, "by": attested_by})
            db.commit()
            return self.send_json(201, {"result": "witness attestation "
                                                  "recorded"})
        return self.send_json(404, {"error": "no such route"})

    def _rotation_publish(self, rec, d):
        # S12 + P9: the schedule USES the seed — but the seed is
        # DERIVED by Janus, never chosen by the publisher. 1.2 let
        # the publishing supervisor supply (or grind) the seed, and
        # picking who audits whom took ~3 tries on average (round
        # 4, A14c). The derived seed is SHA-256(sorted members ‖
        # cycle_start ‖ current chain root): nobody can grind it
        # without rewriting the chain itself, and any partner can
        # recompute it from public facts. A client-supplied seed is
        # refused outright.
        if d.get("seed"):
            return self.send_json(400, {
                "error": "the rotation seed is derived by Janus "
                         "(SHA-256 of the sorted members, the cycle "
                         "start, and the current chain root) — a "
                         "publisher-supplied seed is refused"})
        members = d.get("members")
        if not isinstance(members, list) or not members:
            return self.send_json(400, {"error": "members must be a "
                                               "non-empty list of agency "
                                               "names"})
        members = [str(m).strip() for m in members]
        if len(set(members)) != len(members):
            return self.send_json(400, {"error": "members contains "
                                               "duplicates — rotation "
                                               "members must be unique"})
        if len(members) < 2:
            return self.send_json(400, {
                "error": "a rotation cycle needs at least 2 members"})
        partner_names = {r[0] for r in db.execute(
            "SELECT agency FROM partners WHERE status='active'").fetchall()}
        # P9: the HOME agency may be a rotation member without
        # registering as its own partner.
        if not set(members) <= (partner_names | {AGENCY}):
            return self.send_json(400, {
                "error": "rotation members must be registered, "
                         "non-suspended partners (or this agency)"})
        cycle_start = (d.get("cycle_start") or "").strip()
        try:
            start = date.fromisoformat(cycle_start)
        except ValueError:
            return self.send_json(400, {"error": "cycle_start must be a "
                                               "real date (YYYY-MM-DD)"})
        period = d.get("period_days")
        if not isinstance(period, int) or period < 7 or period > 120:
            return self.send_json(400, {"error": "period_days must be an "
                                               "integer between 7 and 120"})
        # An ACTIVE cycle (its window has not ended) cannot be
        # replaced by publication — voiding it is a separate two-key
        # act (ROTATION_VOID). A cycle whose window HAS ended is
        # history and a new publication simply succeeds it.
        latest = db.execute(
            "SELECT cycle_start, period_days, members_count FROM "
            "rotation_schedules ORDER BY id DESC LIMIT 1").fetchone()
        if latest:
            try:
                end = date.fromisoformat(latest[0]) + timedelta(
                    days=latest[1] * latest[2])
            except ValueError:
                end = None
            if end and date.today() < end:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "rotation publish",
                                         "reason": "active_cycle"})
                return self.send_json(409, {
                    "error": "an active rotation cycle already exists "
                             "(started %s, ends %s) — void it "
                             "(supervisor + auditor two-key) before "
                             "publishing a replacement"
                             % (latest[0], end.isoformat())})
        seed = rotation_seed(members, cycle_start, chain.root())
        rounds = build_schedule(members, cycle_start, chain.root())
        # S7: a rotation schedule is signed with the Ed25519 signing
        # key when one is available, so partners can verify it came
        # from this agency rather than a spoofed poster.
        sched_doc = {"members": members, "seed": seed, "rounds": rounds}
        sig = None
        if SIGNING_PRIV:
            sig = sentinel.sign_bytes(
                SIGNING_PRIV,
                sentinel.canonical_bytes({"members": members,
                                          "seed": seed,
                                          "rounds": rounds}))
        if sig:
            sched_doc["sig"] = sig
            sched_doc["sig_alg"] = "ed25519"
        sched_json = json.dumps(sched_doc, sort_keys=True)
        sched_hash = sha(sched_json)
        db.execute(
            "INSERT INTO rotation_schedules(cycle_start, period_days, "
            "members_count, schedule_hash, schedule, published_by, "
            "published_ts) VALUES(?,?,?,?,?,?,?)",
            (cycle_start, period, len(members), sched_hash, sched_json,
             rec["user"], now_iso()))
        chain.append("ROTATION_PUBLISH", {
            "cycle_start": cycle_start, "period_days": period,
            "members": members, "seed_hash": sha(seed)[:16],
            "sched_hash": sched_hash, "signed": bool(sig),
            "by": rec["user"]})
        db.commit()
        return self.send_json(201, {
            "result": "rotation schedule published",
            "cycle_start": cycle_start, "period_days": period,
            "members": members, "schedule": rounds,
            "sched_hash": sched_hash, "seed": seed,
            "sig": sig, "sig_alg": "ed25519" if sig else None})

    def _share_query(self, rec, d):
        # S8/S10: reciprocal-audit data sharing. The caller must BE
        # the partner (a partner-role account whose username IS the
        # agency). The gate has two legs, both read fresh on every
        # call: (a) the LATEST compact_audits row for the partner is
        # ok AND <=26h old — any newer failure closes the gate
        # immediately, no manual suspension needed; (b) the partner's
        # latest verified receipt names our NEWEST checkpoint.
        # Shares are capped at Tier 2, require case_ref + why +
        # basis_type, and the partner's free text is stored in the
        # DB only — the chain carries why_hash (S11). The
        # stale-config fail-closed rule applies (S10/S13).
        if self.config_closed():
            return
        agency = (d.get("agency") or "").strip()
        # A21: the agency field is scrubber-EXEMPT because registered
        # agency ids are configuration. Caller-supplied text that is
        # NOT a registered partner is not configuration — it is a
        # stranger's string, and it never reaches the permanent
        # chain raw: unregistered agencies chain as a hash.
        registered = db.execute(
            "SELECT 1 FROM partners WHERE agency=?",
            (agency,)).fetchone() is not None

        def chain_agency():
            return {"agency": agency} if registered else {
                "agency_hash": sha(agency)[:16]}

        def blocked(missing, **extra):
            fields = dict(chain_agency())
            fields["missing"] = missing
            fields.update(extra)
            chain.append("SHARE_BLOCKED", fields)
            db.commit()
            return self.send_json(403, {"error": "SHARE_BLOCKED",
                                        "missing": missing,
                                        "agency": agency})
        if rec["role"] != "partner" or rec["user"] != agency:
            return blocked("partner_identity")
        prow = db.execute("SELECT status FROM partners WHERE agency=?",
                          (agency,)).fetchone()
        if not prow or prow[0] != "active":
            return blocked("partner_inactive")
        # P1/A2: the Tier 2 cap is the Compact's core promise, and
        # 1.2 enforced it with `tier > 2 or tier < 1` on a value it
        # then branched on loosely — tier=1 (and JSON true, which
        # Python reads as 1) ran a FULL historical search. Now the
        # ONLY accepted share tier is the integer 2; anything else
        # is SHARE_BLOCKED with the refused tier chained as a coded
        # value (type + value, never free text).
        tier = d.get("tier", 2)
        if type(tier) is not int or tier != 2:
            coded = tier if isinstance(tier, (int, bool)) \
                else type(tier).__name__
            return blocked("tier", tier_refused=coded)
        basis_type = (d.get("basis_type") or "").strip().lower()
        if basis_type not in BASIS_TYPES:
            return blocked("basis_type")
        # P7: the gate is evaluated at query time by the one helper
        # (fresh audit, existing newest checkpoint, matching +
        # verified + fresh receipt).
        missing = share_gate_missing(agency)
        if missing:
            return blocked(missing)
        why = (d.get("why") or "").strip()
        case_ref = (d.get("case_ref") or "").strip()
        if not why or not case_ref:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "agency": agency,
                                     "reason": "no_justification"})
            return self.send_json(403, {
                "error": "share queries require case_ref and why"})
        # The partner's case_ref is THEIR reference — it is recorded
        # as such, never validated against our case list (we cannot
        # validate another agency's cases; the Compact's audit is
        # what vouches for their gatekeeping). The catch-all ban
        # still applies: a partner may not launder a query through
        # a PATROL/TEST reference either.
        if any(p in case_ref.upper() for p in BANNED_CASE_PATTERNS):
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "agency": agency,
                                     "reason": "case_banned"})
            return self.send_json(403, {"error": CASE_GATE_MSGS[
                "case_banned"]})
        # 60 queries per partner per rolling hour (S10), counted
        # from the SHARE_OUT chain entries themselves — the limit
        # survives even a cleared share_queries table.
        hour_ago = (datetime.now(timezone.utc)
                    - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        count = db.execute(
            "SELECT COUNT(*) FROM audit WHERE kind='SHARE_OUT' AND "
            "ts>=? AND payload LIKE ?",
            (hour_ago, '%"agency":' + json.dumps(agency) + '%')
        ).fetchone()[0]
        if count >= 60:
            chain.append("SHARE_RATE_LIMIT", {"agency": agency,
                                              "window": "1h", "cap": 60})
            db.commit()
            return self.send_json(429, {
                "error": "share rate limit: 60 queries per partner per "
                         "hour"})
        frag, ferr = validate_fragment(d.get("plate_fragment"))
        if ferr:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "share query",
                                     "agency": agency,
                                     "reason": ferr})
            return self.send_json(400, {"error": FRAGMENT_MSGS[ferr]})
        results = run_search(frag, "tier2")
        n = len(results["reads"]) + len(results["hits"])
        db.execute(
            "INSERT INTO share_queries(agency, case_ref, why, "
            "basis_type, plate_ref, tier, result_count, outcome, ts) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (agency, case_ref, why, basis_type, frag_ref(frag), tier,
             n, "completed", now_iso()))
        chain.append("SHARE_OUT", {"agency": agency, "tier": tier,
                                   "case_hash": case_hash(case_ref),
                                   "why_hash": why_hash(why),
                                   "plate_ref": frag_ref(frag),
                                   "result_count": n})
        db.commit()
        return self.send_json(200, {"result": "share completed",
                                    "agency": agency, "tier": tier,
                                    "results": results})
    def _rotation_status(self):
        row = db.execute(
            "SELECT cycle_start, period_days, schedule_hash, schedule, "
            "published_ts FROM rotation_schedules ORDER BY id DESC "
            "LIMIT 1").fetchone()
        if not row:
            return self.send_json(200, {"active": False})
        start, period, sched_hash, sched_json, published_ts = row
        doc = json.loads(sched_json)
        members = doc.get("members", [])
        rounds_def = doc.get("rounds", [])
        start_date = date.fromisoformat(start)
        cycle_end = start_date + timedelta(days=period * len(members))
        rounds = []
        today = date.today()
        for i, rd in enumerate(rounds_def):
            ws = start_date + timedelta(days=i * period)
            we = ws + timedelta(days=period - 1)
            auditor = rd.get("auditor")
            audited = rd.get("audited")
            lo = ws.isoformat() + "T00:00:00Z"
            hi = we.isoformat() + "T23:59:59Z"
            # P9: "filed" is direction-correct and success-only.
            # Audits OF us are the auditor's verified receipts in
            # compact_receipts; audits BY us are our ok=1 rows in
            # compact_audits against the AUDITED agency. 1.2 counted
            # both tables against the auditor regardless of
            # direction and regardless of ok — a failed audit
            # 'filed', and a receipt about someone else counted.
            filed_of = db.execute(
                "SELECT COUNT(*) FROM compact_receipts WHERE agency=? "
                "AND verified=1 AND received_ts>=? AND received_ts<=?",
                (auditor, lo, hi)).fetchone()[0]
            filed_by = db.execute(
                "SELECT COUNT(*) FROM compact_audits WHERE agency=? "
                "AND ok=1 AND ts>=? AND ts<=?",
                (audited, lo, hi)).fetchone()[0]
            witness = db.execute(
                "SELECT COUNT(*) FROM witness_attestations WHERE "
                "agency=? AND cycle_start=? AND round_no=?",
                (auditor, start, i + 1)).fetchone()[0]
            # The auditor's OWN duty in this round, judged from the
            # table that records it: if the auditor is US, our duty
            # is the audit we owed the audited agency (compact_
            # audits); if the audited agency is US, the auditor's
            # duty is their receipt (compact_receipts). A round
            # between two OTHER members is witnessed, not recorded
            # here — it cannot ground a delinquency finding either
            # way, and says so.
            completed = we < today
            if auditor == AGENCY:
                filed = filed_by > 0
            elif audited == AGENCY:
                filed = filed_of > 0
            else:
                filed = None
            rounds.append({
                "round": i + 1, "auditor": auditor,
                "audited": audited,
                "window_start": ws.isoformat(),
                "window_end": we.isoformat(),
                "completed": completed,
                "audits_of_us_filed": filed_of,
                "audits_by_us_filed": filed_by,
                "witness_attestation_filed": witness > 0,
                "delinquent": bool(completed and filed is False)})
        # P9 delinquency: PER AGENCY, across COMPLETED rounds only
        # — an agency that owed a filing in a completed round and
        # filed in none of its completed rounds. Future rounds never
        # count (1.2 listed a not-yet-started cycle's members as
        # delinquent on publication day).
        owed, filed_any = {}, {}
        for r in rounds:
            if not r["completed"]:
                continue
            a = r["auditor"]
            if a == AGENCY:
                owed[a] = owed.get(a, 0) + 1
                if r["audits_by_us_filed"]:
                    filed_any[a] = True
            elif r["audited"] == AGENCY:
                owed[a] = owed.get(a, 0) + 1
                if r["audits_of_us_filed"]:
                    filed_any[a] = True
        delinquent = sorted(a for a in owed if not filed_any.get(a))
        return self.send_json(200, {
            "active": date.today() < cycle_end,
            "cycle_start": start, "period_days": period,
            "members": members, "sched_hash": sched_hash,
            "published_ts": published_ts,
            "rounds": rounds,
            "delinquent_agencies": delinquent})

    # ---------------- DELETE ----------------
    def do_DELETE(self):
        self._resp = None
        if not self._read_body():
            return
        with DBLOCK:
            try:
                self._delete()
                if db.in_transaction:
                    db.commit()
            except Exception as exc:  # a handler bug must still answer
                try:
                    db.rollback()
                except Exception:
                    pass
                self._resp = (500, {"error": f"internal: {exc}"})
        try:
            chain.flush_deferred()
        except Exception:
            pass
        self._flush_response()

    def _delete(self):
        if self.locked_out():
            return
        rec = self.need_auth()
        if not rec:
            return
        if urlparse(self.path).path != "/hotlist":
            return self.send_json(404, {"error": "no such route"})
        if rec["role"] != "supervisor":
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "hotlist remove",
                                     "reason": "role"})
            return self.send_json(403, {"error": "hotlist removal is "
                                               "supervisor-only"})
        d = self.body_json()
        # P13/A24: removal DELETES the membership row. 1.2 only
        # deactivated — and deactivated the WRONG row silently when
        # the caller omitted the entry's state: it answered 200
        # "membership deactivated", chained HOTLIST_REMOVE, and the
        # entry stayed active. Now the membership is identified by
        # the fields given (plate, plus state / list_source /
        # case_no when supplied); exactly one ACTIVE membership
        # must match — no match is a 404, several matches without
        # enough identifiers is a 400 — and the row is deleted.
        plate = normalize_plate(d.get("plate") or "")
        if not plate:
            return self.send_json(400, {"error": "plate is required"})
        clauses = ["plate=?", "active=1"]
        params = [plate]
        if d.get("state"):
            clauses.append("state=?")
            params.append(str(d["state"]).strip().upper())
        source = d.get("list_source") or d.get("list_name")
        if source:
            clauses.append("list_source=?")
            params.append(str(source).strip())
        if d.get("case_no"):
            clauses.append("case_no=?")
            params.append(d["case_no"])
        rows = db.execute(
            "SELECT state, list_source, case_no FROM hotlist_members "
            "WHERE " + " AND ".join(clauses), params).fetchall()
        if not rows:
            return self.send_json(404, {
                "error": "no active hot-list membership matches — "
                         "nothing was removed"})
        if len(rows) > 1:
            return self.send_json(400, {
                "error": "that plate has %d active memberships — "
                         "name the state and list_source to remove "
                         "one" % len(rows)})
        m_state, m_source, m_case = rows[0]
        db.execute(
            "DELETE FROM hotlist_members WHERE plate=? AND state=? "
            "AND list_source=? AND case_no IS ?",
            (plate, m_state, m_source, m_case))
        chain.append("HOTLIST_REMOVE", {
            "plate_ref": plate_ref(plate), "by": rec["user"],
            "list_source": m_source})
        db.commit()
        return self.send_json(200, {"result": "membership deleted",
                                    "plate": plate,
                                    "list_source": m_source})

    # ---------------- GET ----------------
    def do_GET(self):
        self._resp = None
        # P13/A18: chain verification is computed BEFORE the lock is
        # taken — detached, read-only, cached 60s — so a partner's
        # /audit/verify (or a /health) can never stall ingest behind
        # a full-chain scan on the shared connection. _health and the
        # /audit/verify branch consume self._verify_pre.
        self._verify_pre = None
        base0 = urlparse(self.path).path
        if base0 in ("/health", "/audit/verify"):
            self._verify_pre = chain_ok_cached()
        with DBLOCK:
            try:
                self._get()
                if db.in_transaction:
                    db.commit()
            except Exception as exc:  # a handler bug must still answer
                try:
                    db.rollback()
                except Exception:
                    pass
                self._resp = (500, {"error": f"internal: {exc}"})
        try:
            chain.flush_deferred()
        except Exception:
            pass
        self._flush_response()

    def _get(self):
        path = self.path
        base = urlparse(path).path
        # S5: the unauthenticated liveness probe is /ping, and it
        # answers with liveness only — nothing about the system.
        if base == "/ping":
            return self.send_json(200, {"alive": True})
        if self.locked_out():
            return
        # Authenticate once for everything else (S5: /health
        # requires auth now). The chain_auditor fence (S9) runs
        # before the per-endpoint role checks.
        rec = self.need_auth()
        if not rec:
            return
        if rec["role"] == "chain_auditor" \
                and base not in CHAIN_AUDITOR_GETS:
            return self.send_json(403, {
                "error": "the chain_auditor role may only read the "
                         "audit chain and the checkpoint"})
        q = parse_qs(urlparse(path).query)
        if base == "/health":
            if rec["role"] not in ("supervisor", "auditor", "jobs"):
                return self.send_json(403, {"error": "health detail is "
                                                   "supervisor/auditor/"
                                                   "jobs only"})
            return self._health(rec)
        if base in ("/audit", "/audit/root", "/audit/verify",
                    "/audit/range"):
            if rec["role"] not in AUDIT_READ_ROLES:
                return self.send_json(403, {"error": "audit chain is "
                                                   "supervisor/auditor/"
                                                   "chain_auditor only"})
            if base == "/audit":
                # P13/A17: the limit is a contract, not a clamp —
                # 1.2's min(limit, 1000) let limit=-1 through to
                # SQLite, where LIMIT -1 means UNLIMITED: the whole
                # chain in one response, under the global lock, for
                # any chain_auditor. Out-of-contract is a 400.
                raw_limit = q.get("limit", ["200"])[0]
                try:
                    limit = int(raw_limit)
                except (TypeError, ValueError):
                    return self.send_json(400, {
                        "error": "limit must be an integer in "
                                 "1..1000"})
                if limit < 1 or limit > 1000:
                    return self.send_json(400, {
                        "error": "limit must be an integer in "
                                 "1..1000"})
                rows = chain.entries(limit)
                return self.send_json(200, {"entries": rows})
            if base == "/audit/root":
                return self.send_json(200, {"root": chain.root(),
                                            "entries": chain.count()})
            if base == "/audit/verify":
                # P13: the SAME 60s cached, detached verify /health
                # uses — computed before DBLOCK was taken (do_GET),
                # never a fresh full scan under the lock.
                return self.send_json(
                    200, self._verify_pre or chain_ok_cached())
            # S8: the range endpoint the Compact auditor uses to
            # recompute our chain independently. Raw payloads only —
            # the verifier rehashes the exact bytes itself.
            try:
                frm = int(q.get("from_seq", ["1"])[0])
                to = int(q.get("to_seq", ["0"])[0])
            except ValueError:
                return self.send_json(400, {"error": "from_seq and "
                                                   "to_seq must be "
                                                   "integers"})
            if frm < 1 or to < frm or to - frm > 1000:
                return self.send_json(400, {"error": "range must be "
                                                   "from_seq>=1, "
                                                   "to_seq>=from_seq, "
                                                   "span<=1000"})
            return self.send_json(200, {"entries": chain.entries_range(
                frm, to), "from_seq": frm, "to_seq": to})
        if base == "/search":
            # No DATA_ROLES pre-gate here: as in 1.1, patrol may run
            # Tier 2 searches; _run_tiered_search + janus_gate refuse
            # auditor/service/partner roles themselves.
            if self.config_closed():
                return
            body, err = self._run_tiered_search(rec, q)
            if err:
                return err
            return self.send_json(200, body)
        if base == "/hits":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "hits read")
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,"
                "list_name,category,status,suppressed FROM hits "
                "ORDER BY id DESC LIMIT 400"
            ).fetchall()
            # S3 + P3: suppressed hits are not listed here AT ALL —
            # not even for a supervisor — and suppression is judged
            # LIVE (hit_suppressed_now), not by the ingest-time
            # stamp: a hit whose plate came under an order an hour
            # ago is in the supervisor queue NOW. They live in
            # /suppressed-hits, and nowhere else.
            rows = [r for r in rows
                    if not hit_suppressed_now(r[3], r[4])][:200]
            chain.append("HITS_VIEW", {"by": rec["user"],
                                       "count": len(rows)})
            return self.send_json(200, {"hits": [
                hit_public(dict(zip(("id", "ts", "cam", "read_plate",
                                     "entry_plate", "state", "list_name",
                                     "category", "status", "suppressed"),
                                    r)))
                for r in rows]})
        if base == "/suppressed-hits":
            if rec["role"] != "supervisor":
                return self.send_json(403, {"error": "the suppressed-hit "
                                                   "queue is supervisor-"
                                                   "only"})
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,state,"
                "list_name,category,status,suppressed FROM hits "
                "ORDER BY id DESC").fetchall()
            # P3: the queue is also live — a hit whose order was
            # RELEASED leaves the queue even if its stamp still says
            # suppressed, and a post-hoc order puts its hit here.
            rows = [r for r in rows if hit_suppressed_now(r[3], r[4])]
            chain.append("SUPPRESSED_HITS_VIEW", {"by": rec["user"],
                                                  "count": len(rows)})
            return self.send_json(200, {"hits": [
                hit_public(dict(zip(("id", "ts", "cam", "read_plate",
                                     "entry_plate", "state", "list_name",
                                     "category", "status", "suppressed"),
                                    r)), show_suppressed=True)
                for r in rows]})
        if base == "/hotlist":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "hotlist read")
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT plate,state,list_source,category,case_no,"
                "expires_ts FROM hotlist_members WHERE active=1 "
                "ORDER BY plate, list_source").fetchall()
            chain.append("HOTLIST_VIEW", {"by": rec["user"],
                                          "count": len(rows)})
            return self.send_json(200, {"entries": [
                {"plate": r[0], "state": r[1], "list_source": r[2],
                 "category": r[3], "case_no": r[4], "expires": r[5]}
                for r in rows]})
        if base == "/lists":
            if rec["role"] not in ("supervisor", "auditor"):
                return self.send_json(403, {"error": "the list registry "
                                                   "is supervisor/auditor "
                                                   "only"})
            return self.send_json(200, {"lists": list_registry_names()})
        if base == "/stats":
            if rec["role"] not in DATA_ROLES:
                return self.deny_service_role(rec, "stats read")
            if self.config_closed():
                return
            return self.send_json(200, stats_body())
        if base == "/report":
            if rec["role"] not in ("supervisor", "auditor"):
                return self.send_json(403, {"error": "the effectiveness "
                                                   "report is supervisor/"
                                                   "auditor only"})
            if self.config_closed():
                return
            frm = q.get("from", [""])[0]
            to = q.get("to", ["9999-12-31T23:59:59Z"])[0]
            snap = q.get("snapshot", [None])[0]
            if snap:
                row = db.execute(
                    "SELECT body FROM report_snapshots WHERE id=?",
                    (int(snap),)).fetchone()
                if not row:
                    return self.send_json(404, {"error": "no such "
                                                       "snapshot"})
                # The frozen body, exactly as compiled — the
                # snapshot's immutability is the feature.
                return self.send_json(200, json.loads(row[0]))
            return self.send_json(200, compute_report(frm, to))
        if base == "/tier3/pending":
            if rec["role"] not in ("supervisor", "auditor", "detective",
                                   "patrol"):
                return self.send_json(403, {"error": "role cannot read "
                                                   "the Tier 3 queue"})
            if self.config_closed():
                return
            # P12 (round 4, R17): the second key must be able to
            # JUDGE what it approves. Round 3 overcorrected this
            # queue to hashes only — an approver who cannot see the
            # fragment, the case, the justification, or the basis is
            # a rubber stamp with a key. A SUPERVISOR approver now
            # sees plate_fragment, case_no, why, auth_basis, tier,
            # requester. The auditor keeps the hashed sampling view.
            # Detectives/patrol see only their OWN requests and stay
            # plate-free (hashes and refs, as before).
            if rec["role"] in ("supervisor", "auditor"):
                rows = db.execute(
                    "SELECT id,requester,case_no,created_ts,emergency,"
                    "needs_review,plate_fragment,basis_type,why,"
                    "auth_basis FROM tier3_requests WHERE "
                    "status='PENDING' OR needs_review=1 ORDER BY id"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id,requester,case_no,created_ts,emergency,"
                    "needs_review,plate_fragment,basis_type,why,"
                    "auth_basis FROM tier3_requests WHERE "
                    "(status='PENDING' OR needs_review=1) AND "
                    "requester=? ORDER BY id",
                    (rec["user"],)).fetchall()
            out = []
            for r in rows:
                item = {"id": r[0], "request_id": r[0],
                        "requester": r[1], "created_ts": r[3],
                        "emergency": bool(r[4]),
                        "needs_review": bool(r[5]),
                        "basis_type": r[7], "tier": 3}
                if rec["role"] == "supervisor":
                    item.update({
                        "plate_fragment": r[6], "case_no": r[2],
                        "why": r[8], "auth_basis": r[9],
                        "case_hash": case_hash(r[2]),
                        "plate_ref": frag_ref(r[6] or "")})
                else:
                    item.update({
                        "case_hash": case_hash(r[2]),
                        "plate_ref": frag_ref(r[6] or "")})
                out.append(item)
            return self.send_json(200, {"pending": out})
        if base == "/tier3/reviews":
            if rec["role"] not in ("supervisor", "auditor"):
                return self.send_json(403, {"error": "the Tier 3 review "
                                                   "queue is supervisor/"
                                                   "auditor only"})
            if self.config_closed():
                return
            rows = db.execute(
                "SELECT id,requester,case_no,created_ts,emergency,"
                "plate_fragment,basis_type FROM tier3_requests WHERE "
                "needs_review=1 ORDER BY id").fetchall()
            return self.send_json(200, {"reviews": [
                {"request_id": r[0], "requester": r[1],
                 "case_hash": case_hash(r[2]), "created_ts": r[3],
                 "emergency": bool(r[4]),
                 "plate_ref": frag_ref(r[5] or ""), "basis_type": r[6]}
                for r in rows]})
        if base.startswith("/tier3/results/"):
            # S9: results are read by the requester and supervisors
            # ONLY. The auditor samples via refs and counts.
            # P13: the stale-config fail-closed rule applies here
            # too — 1.2 checked it on the POST routes and on search
            # but not on this read, the most sensitive one.
            if self.config_closed():
                return
            if rec["role"] not in ("supervisor", "detective", "patrol"):
                return self.send_json(403, {
                    "error": "Tier 3 results are read by the requester "
                             "and supervisors only"})
            try:
                rid = int(base.rsplit("/", 1)[1])
            except ValueError:
                return self.send_json(400, {"error": "bad request id"})
            row = db.execute(
                "SELECT requester, case_no, status, results, "
                "results_count, results_read_ids, results_hit_ids, "
                "plate_fragment FROM tier3_requests WHERE id=?",
                (rid,)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 "
                                                   "request"})
            requester, case_no, status, legacy_body, results_count, \
                read_ids_json, hit_ids_json, frag = row
            if rec["role"] != "supervisor" and rec["user"] != requester:
                return self.send_json(403, {"error": "results are "
                                                   "returned to the "
                                                   "requester only"})
            if status not in ("EXECUTED", "EMERGENCY", "REVIEWED"):
                return self.send_json(409, {"error": "no results exist "
                                                   "for a request in "
                                                   "status %s" % status})
            # S2: the case gate revalidates AT READ TIME — a case
            # that closed since execution no longer opens its results.
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 results",
                                         "request": rid,
                                         "reason": reason})
                return self.send_json(403, {
                    "error": "BLOCKED at read: "
                             + CASE_GATE_MSGS[reason]})
            if legacy_body and not read_ids_json and not hit_ids_json:
                # A 1.0/1.1-era row: the stored body is legacy state
                # retention will NULL at class age. The 1.2 endpoint
                # never returns it — the detail is treated as expired.
                chain.append("TIER3_RESULTS_VIEW", {
                    "request": rid, "by": rec["user"],
                    "results_count": results_count or 0,
                    "stored_count": results_count or 0, "expired": True})
                return self.send_json(200, {
                    "result": "results detail expired (pre-1.2 stored "
                              "body)", "request_id": rid,
                    "results_count": results_count,
                    "plate_ref": frag_ref(frag or ""),
                    "expired": True})
            # S2: resolve the stored ids LIVE through the current
            # shaping layer. Suppressed rows are excluded NOW, not as
            # they were when the search ran.
            read_ids = json.loads(read_ids_json or "[]")
            hit_ids = json.loads(hit_ids_json or "[]")
            live_reads, live_hits = [], []
            if read_ids:
                placeholders = ",".join("?" * len(read_ids))
                live_reads = [dict(zip(
                    ("id", "ts", "cam", "plate", "state", "conf",
                     "cam_ts", "skew_s"), r)) for r in db.execute(
                    "SELECT id,ts,cam,plate,state,conf,cam_ts,skew_s "
                    "FROM reads WHERE id IN (%s) AND NOT EXISTS "
                    "(SELECT 1 FROM suppressions s WHERE s.active=1 AND "
                    "s.plate = reads.plate) ORDER BY ts" % placeholders,
                    tuple(read_ids)).fetchall()]
            if hit_ids:
                placeholders = ",".join("?" * len(hit_ids))
                live_hits = [dict(zip(
                    ("id", "ts", "cam", "read_plate", "entry_plate",
                     "state", "list_name", "category", "status"), r))
                    for r in db.execute(
                    "SELECT id,ts,cam,read_plate,entry_plate,state,"
                    "list_name,category,status FROM hits WHERE id IN "
                    "(%s) AND" % placeholders + _SUPPRESSED_HIT_SQL
                    + " ORDER BY ts",
                    tuple(hit_ids)).fetchall()]
            stored_n = len(read_ids) + len(hit_ids)
            live_n = len(live_reads) + len(live_hits)
            chain.append("TIER3_RESULTS_VIEW", {
                "request": rid, "by": rec["user"], "results_count": live_n,
                "stored_count": stored_n})
            if live_n == 0 and (stored_n or (results_count or 0)):
                # Everything aged out or was suppressed since
                # execution — or retention already nulled the stored
                # ids at class age (stored_n == 0 with a positive
                # execution count): the plate-free summary either
                # way. A search that truly matched nothing has
                # results_count == 0 and falls through to the empty
                # ok below.
                return self.send_json(200, {
                    "result": "results detail expired",
                    "request_id": rid,
                    "results_count": results_count,
                    "plate_ref": frag_ref(frag or ""),
                    "expired": True})
            return self.send_json(200, {
                "result": "ok", "request_id": rid,
                "results": {"reads": live_reads, "hits": live_hits},
                "results_count": live_n,
                "stored_count": stored_n,
                "expired": live_n < stored_n})
        if base == "/compact/partners":
            if rec["role"] not in ("supervisor", "auditor"):
                return self.send_json(403, {"error": "partner list is "
                                                   "supervisor/auditor "
                                                   "only"})
            rows = db.execute(
                "SELECT agency, endpoint, status, "
                "audit_key_fingerprint FROM partners ORDER BY agency"
                ).fetchall()
            out = []
            for agency, endpoint, status, fp in rows:
                row = db.execute(
                    "SELECT ok, ts FROM compact_audits WHERE agency=? "
                    "ORDER BY id DESC LIMIT 1", (agency,)).fetchone()
                out.append({
                    "agency": agency, "endpoint": endpoint,
                    "status": status, "suspended": status != "active",
                    "audit_key_fingerprint": fp,
                    "last_audit_ok": bool(row[0]) if row else None,
                    "last_audit_ts": row[1] if row else None,
                    "share_gate_open": share_gate_open(agency)})
            return self.send_json(200, {"partners": out})
        if base == "/compact/checkpoint":
            if rec["role"] not in ("supervisor", "auditor",
                                   "chain_auditor"):
                return self.send_json(403, {"error": "checkpoint read is "
                                                   "supervisor/auditor/"
                                                   "chain_auditor only"})
            cp = read_newest_checkpoint()
            if not cp:
                return self.send_json(404, {"error": "no checkpoint "
                                                   "published yet"})
            return self.send_json(200, {"checkpoint": cp})
        if base == "/compact/rotation/status":
            if rec["role"] not in ("supervisor", "auditor"):
                return self.send_json(403, {"error": "rotation status is "
                                                   "supervisor/auditor "
                                                   "only"})
            return self._rotation_status()
        return self.send_json(404, {"error": "no such route"})

    def _run_tiered_search(self, rec, q):
        """GET /search — Tier 2 ONLY, as in 1.1 (the temporal wall,
        a required justification, the shared case gate, and the
        per-day case/fragment pattern ledger). 1.2 changes are the
        S11 ones: the chain carries case_hash/why_hash, never the
        raw case number or justification. Returns (body, None) or
        (None, error) — on error the response is already captured."""
        if rec["role"] == "auditor":
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "auditor_read_only"})
            return None, self._send_err(
                403, "auditors verify the system; they do not search it")
        raw_tier = q.get("tier", ["2"])[0]
        try:
            tier = int(raw_tier)
        except (TypeError, ValueError):
            return None, self._send_err(400, "tier must be numeric")
        if tier == 3:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "tier3_two_key"})
            return None, self._send_err(
                403, "Tier 3 search is not available at this endpoint "
                     "— use /tier3/request or /tier3/emergency")
        if tier != 2:
            return None, self._send_err(
                400, "tier must be 2 at this endpoint")
        # 'why' is the 1.0 parameter name; 'justification' is kept
        # as an accepted alias so both spellings work.
        justification = (q.get("why", [""])[0]
                         or q.get("justification", [""])[0]).strip()
        if not justification:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": "no_justification"})
            return None, self._send_err(
                403, "BLOCKED: a plate search requires a justification")
        case_no = q.get("case", [""])[0] or q.get("case_id", [""])[0]
        ok, reason = janus_gate(rec, case_no)
        if not ok:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": reason})
            return None, self._send_err(
                403, CASE_GATE_MSGS.get(
                    reason, "BLOCKED: role cannot search"))
        frag, ferr = validate_fragment(q.get("plate", [""])[0])
        if ferr:
            chain.append("BLOCKED", {"user": rec["user"],
                                     "action": "search",
                                     "reason": ferr})
            return None, self._send_err(400, FRAGMENT_MSGS[ferr])
        if case_no:
            # Pattern signal: case_searches is the per-day
            # (case, fragment) ledger and case_flags marks a case's
            # first use each day — a case that suddenly starts
            # searching leaves a CASE_FLAG in the chain (with the
            # case's HASH, per S11).
            day = now_iso()[:10]
            new_case = db.execute(
                "INSERT OR IGNORE INTO case_flags(case_no, day) "
                "VALUES(?,?)", (case_no, day)).rowcount
            new_frag = db.execute(
                "INSERT OR IGNORE INTO case_searches(case_no, day, "
                "frag) VALUES(?,?,?)", (case_no, day, frag)).rowcount
            if new_case:
                chain.append("CASE_FLAG", {
                    "user": rec["user"], "case_hash": case_hash(case_no),
                    "flag": "CASE_FLAG"})
            if new_frag:
                chain.append("CASE_FLAG", {
                    "user": rec["user"], "case_hash": case_hash(case_no),
                    "flag": "CASE_FLAG (new fragment under case today)",
                    "plate_ref": frag_ref(frag)})
        results = run_search(frag, "tier2")
        n = len(results["reads"]) + len(results["hits"])
        chain.append("QUERY", {
            "user": rec["user"], "type": "tier2 search", "tier": 2,
            "case_hash": case_hash(case_no),
            "why_hash": why_hash(justification),
            "plate_ref": frag_ref(frag), "result_count": n,
            "window_hours": TIER2_WINDOW_H})
        db.commit()
        return results, None

    def _send_err(self, code, msg):
        self.send_json(code, {"error": msg})
        return (code, msg)

    def _health(self, rec):
        n_chain = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        n_reads = db.execute("SELECT COUNT(*) FROM reads").fetchone()[0]
        n_hits = db.execute("SELECT COUNT(*) FROM hits").fetchone()[0]
        n_pending = db.execute(
            "SELECT COUNT(*) FROM tier3_requests WHERE status='PENDING' "
            "OR needs_review=1").fetchone()[0]
        n_supp = db.execute("SELECT COUNT(*) FROM suppressions WHERE "
                            "active=1").fetchone()[0]
        jobs, overdue = jobs_status()
        cams, silent_cams = cameras_status()
        try:
            sink = chain.sink_status()
        except Exception:
            sink = {"enabled": False, "ok": True}
        sink_up = (not sink.get("enabled")) or bool(sink.get("ok"))
        # S5: a broken chain degrades health BY NAME — 1.1 computed
        # chain_ok and then left it out of `degraded`, so a service
        # with a broken audit chain reported itself healthy.
        # P13: the verify was computed in do_GET BEFORE DBLOCK was
        # taken (detached + cached); it is never computed here,
        # under the lock.
        cv = getattr(self, "_verify_pre", None) or chain_ok_cached()
        chain_ok = bool(cv.get("ok"))
        # S1/S5: a retention breach is named, store by store.
        breach = retention_breach()
        destroy_overdue = evidence_destroy_overdue()
        anchor_bad = anchor_mismatch()
        cfg = config_status()
        cfg_stale = any(v.get("stale") for k, v in cfg.items()
                        if isinstance(v, dict))
        ok_all = (chain_ok and not overdue and sink_up and not anchor_bad
                  and not breach and destroy_overdue == 0
                  and not cfg_stale and not cfg["fail_closed"])
        return self.send_json(200, {
            "service": "janus", "version": VERSION, "ok": ok_all,
            "degraded": {
                "jobs_overdue": overdue,
                "sink_up": sink_up,
                "chain_ok": chain_ok,
                "anchor_mismatch": anchor_bad,
                "anchor_detail": (json.loads(_meta_get("anchor_mismatch"))
                                  if anchor_bad else None),
                "config": cfg,
                "retention_breach": breach,
                "evidence_destroy_overdue": destroy_overdue,
                "cameras_silent": silent_cams,
                "overdue_holds": len(overdue_holds()),
            },
            "chain_entries": n_chain, "chain_ok": chain_ok,
            "chain_verify": cv,
            "retention_breach": bool(breach),
            "retention_days": RETENTION_DAYS,
            "hold_days": HOLD_DAYS,
            "tier2_window_hours": TIER2_WINDOW_H,
            "tier2_window_h": TIER2_WINDOW_H,
            "anchor_mismatch": anchor_bad,
            "cameras_silent": silent_cams,
            "overdue_holds": len(overdue_holds()),
            "config_stale": any(v.get("stale") for k, v in cfg.items()
                                if isinstance(v, dict)),
            "config_stale_since": next(
                (v.get("stale_since") for k, v in cfg.items()
                 if isinstance(v, dict) and v.get("stale")), None),
            "sentinel_sink_ok": sink_up,
            "retention_oldest_read_age_h":
                retention_oldest_read_age_h(),
            "registry_version": REGISTRY_VERSION,
            "reads": n_reads, "hits": n_hits,
            "tier3_pending": n_pending,
            "active_suppressions": n_supp,
            "cameras": cams,
            "jobs": jobs,
            "sink": sink,
        })
# ---------------- rotation schedule builder (S12) ----------------
def rotation_seed(members, cycle_start, chain_root):
    """The derived rotation seed (P9): SHA-256 over the sorted
    member list, the cycle start, and the chain root at publication
    time. Derived, never chosen — see _rotation_publish."""
    canon = ",".join(sorted(members)) + "|" + cycle_start + "|" \
        + chain_root
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def build_schedule(members, cycle_start, chain_root):
    """Deterministic audit-rotation schedule.

    ALGORITHM (documented so any partner can reproduce it): the seed
    is rotation_seed(members, cycle_start, chain_root) — derived
    from public facts, never publisher-supplied (P9). The members
    are sorted, then permuted by a Fisher-Yates shuffle driven by
    SHA-256(seed) as a byte stream — bytes are consumed two at a
    time (big-endian uint16) to pick each swap index j = value %
    (i+1), walking i from n-1 down to 1. The permuted list becomes
    the auditor order for rounds 1..n; round r's auditor audits
    round (r+1)'s agency (cyclically), so every agency both audits
    and is audited exactly once per cycle. The same inputs reproduce
    the schedule byte-identically."""
    seed = rotation_seed(members, cycle_start, chain_root)
    n = len(members)
    order = sorted(members)
    stream = bytearray(hashlib.sha256(seed.encode("utf-8")).digest())
    pos = 0

    def next16():
        nonlocal pos
        while pos + 2 > len(stream):
            stream.extend(hashlib.sha256(bytes(stream)).digest())
        v = (stream[pos] << 8) | stream[pos + 1]
        pos += 2
        return v

    for i in range(n - 1, 0, -1):
        j = next16() % (i + 1)
        order[i], order[j] = order[j], order[i]
    schedule = []
    for r in range(n):
        schedule.append({
            "round": r + 1,
            "auditor": order[r],
            "audited": order[(r + 1) % n],
        })
    return schedule


if __name__ == "__main__":
    if KEY_LOCKED:
        print("JANUS REFUSES TO START: audit key %s — restore the "
              "key (env NOCTUA_AUDIT_KEY or the key file beside the "
              "database) and restart" % KEY_LOCK_REASON,
              file=sys.stderr)
        sys.exit(3)
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    # S13: the effective config is part of the permanent record —
    # what retention ran under is a fact a later auditor can check,
    # not a log line that rotated away.
    try:
        chain.append("SYSTEM", {
            "event": "janus started", "version": VERSION,
            "retention_days": RETENTION_DAYS,
            "hold_days": HOLD_DAYS,
            "tier2_window_h": TIER2_WINDOW_H,
            "config_hash": config_hash(),
            "bind": "%s:%d" % (BIND, PORT),
            "registry_version": REGISTRY_VERSION,
            "signing_pubkey_fingerprint":
                sentinel.pubkey_fingerprint(SIGNING_PUB_PEM)
                if SIGNING_PUB_PEM else None})
        chain.flush_deferred()
    except Exception as e:  # noqa: BLE001 — boot must not die on chain
        print("warning: SYSTEM chain entry failed: %s" % e,
              file=sys.stderr)
    print(f"janus {VERSION} listening on {BIND}:{PORT} db={DB_PATH}")
    Server((BIND, PORT), H).serve_forever()
