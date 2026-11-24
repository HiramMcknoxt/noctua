#!/usr/bin/env python3
"""Janus — the NOCTUA front door. Version 1.0.

The ONLY way anything reads or writes NOCTUA data. Stdlib-only Python
service over SQLite, built to the Cabot pilot spec (Nov. 23, 2026) and
the NOCTUA 1.0 interface spec. Every v0.9 endpoint keeps working; 1.0
adds two-key Tier 3, the evidence lifecycle, cumulative report counters,
dead-man heartbeats, and clock-skew flagging at ingest.

Rules enforced here:
  * Named individual accounts with per-user keys. Shared/generic accounts
    do not exist and cannot authenticate. Disabled accounts (see
    scripts/provision.py) cannot authenticate either. users.json and
    cases.json are reloaded when their mtime changes, so provisioning
    and the nightly case-list export take effect without a restart.
  * Every search is tied to a case number validated against the open-case
    list (in production: a nightly export from the records system).
  * Tier 2 (contemporaneous) needs a valid case. Tier 3 (historical)
    runs ONLY through the two-key workflow below, or the supervisor
    emergency path — the v0.9 `judicial=1` query flag no longer executes
    a Tier 3 search by itself (it is still accepted on /search for
    backwards compatibility of the URL shape, but Tier 3 via /search is
    refused with a pointer to /tier3/request; see do_GET /search).
  * Two-key Tier 3: POST /tier3/request creates a PENDING request and
    executes NOTHING. POST /tier3/approve — by a supervisor who is NOT
    the requester — executes the search and returns the results.
    POST /tier3/emergency (supervisor) executes immediately, is flagged
    EMERGENCY, and queues a mandatory post-hoc review that a different
    supervisor or the outside auditor must close (POST /tier3/review).
  * The outside-auditor role is read-only for the audit log and cannot
    search, verify, or touch the hot list. (Closing a Tier 3 emergency
    review is the one write an auditor may make: it is a judgment about
    someone else's search, not access to data, and the interface spec's
    post-hoc review has to be closable by the reviewer class.)
  * Every allowed AND blocked action mediated by Janus is written to
    the Sentinel chain. Chain entries never contain plate text — keyed
    HMAC plate references only (see _audit_key / plate_ref).
  * Evidence: POST /evidence/export writes a hashed bundle for a hit;
    POST /evidence/release records prosecutor sign-off. The retention
    job refuses to delete an exported hit until its release is on file.

Endpoints (v0.9, unchanged):
  GET  /health           (now also reports dead-man job status/degraded)
  POST /reads            ingest a plate read (role: system) -> alert on match
  GET  /search?plate=&case=&why=&tier=2   (Tier 3 refused; use /tier3/*)
  GET  /hotlist          POST /hotlist   DELETE /hotlist/<plate>
  POST /verify           {hit_id, decision: confirm|reject, case}
  POST /outcomes         {hit_id, arrest, prosecution}
  GET  /report?from=&to= SS 12-12-1805 aggregates; plates_scanned now
                         comes from the cumulative counters table, so it
                         survives retention deletes
  POST /holds            {scope: case|hit, ref, reason}  (detective+)
  POST /holds/release    {hold_id}  (supervisor)
  POST /suppressions     {plate, case}  (supervisor; protection orders)
  POST /suppressions/release  {plate}   (supervisor)
  GET  /hits?status=PENDING
  GET  /audit?limit=200  GET /audit/verify  GET /audit/root
  GET  /stats
Endpoints (1.0 additions):
  POST /tier3/request    {case_id, why, plate_fragment, auth_basis}
  POST /tier3/approve    {request_id}  (supervisor, != requester)
  POST /tier3/deny       {request_id}  (supervisor, or requester=cancel)
  POST /tier3/emergency  {case_id, why, plate_fragment, auth_basis}
  GET  /tier3/pending            PENDING requests (supervisor/detective/auditor)
  GET  /tier3/pending-reviews    unreviewed emergency uses (same roles)
  POST /tier3/review     {request_id, finding}  (supervisor/auditor, != user)
  POST /evidence/export  {hit_id, case_id}  (detective+supervisor)
  POST /evidence/release {hit_id, prosecutor_signoff:{name,date}} (supervisor)
  POST /heartbeat        {job, ok, detail}  (system) — dead-man switches

Config (environment):
  NOCTUA_DB=/data/noctua.db  NOCTUA_USERS=/config/users.json
  NOCTUA_CASES=/config/cases.json  NOCTUA_PORT=8080
  RETENTION_DAYS=14  HOLD_DAYS=30
  NOCTUA_AUDIT_KEY=<hmac key>          (or the .audit_key file by the DB)
  NOCTUA_SENTINEL_SINK=/path/sink.jsonl  (optional streaming copy of chain)
  NOCTUA_BANNED_CASE_PATTERNS=PATROL,TEST,ADMIN,DUTY  (catch-all case ban)
  NOCTUA_EVIDENCE_DIR=<dir>  (default: <db dir>/evidence; bundles are
                              evidence and contain plate text — filesystem
                              permissions are the control; dir is 0700)

Concurrency: one shared SQLite connection plus one lock serializing
request handling (DBLOCK). At a 9-camera city's volume that is not a
bottleneck; it removes a class of interleaved-write surprises. The
Sentinel chain has its own connection and relies on SQLite locking with
busy_timeout. Stated plainly: this is a small-city service, not a
horizontal-scale design.
"""
import hashlib
import hmac as hmac_mod
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from sentinel import Chain, now_iso, sha

DB_PATH = os.environ.get("NOCTUA_DB", "/data/noctua.db")
USERS_PATH = os.environ.get("NOCTUA_USERS", "/config/users.json")
CASES_PATH = os.environ.get("NOCTUA_CASES", "/config/cases.json")
PORT = int(os.environ.get("NOCTUA_PORT", "8080"))
EVIDENCE_DIR = os.environ.get(
    "NOCTUA_EVIDENCE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "evidence"))

# Dead-man thresholds: a required job whose last heartbeat is older than
# this (or missing entirely) makes /health report degraded.
JOB_MAX_AGE_S = {"retention": 26 * 3600, "checkpoint": 26 * 3600}


def _audit_key():
    """Key for plate references in the Sentinel chain.

    The chain is append-only and effectively permanent, so it must NEVER
    store plate text: under Ark. Code SS 12-12-1802 captured plate data
    includes the plate number itself, and a permanent log of plate text
    would outlive every retention limit in the system. Chain entries carry
    a keyed HMAC reference instead -- correlatable by key holders,
    useless to anyone else. Key comes from NOCTUA_AUDIT_KEY, else a random
    per-install key persisted next to the database (0600).
    """
    k = os.environ.get("NOCTUA_AUDIT_KEY")
    if k:
        return k
    kf = DB_PATH + ".audit_key"
    if os.path.exists(kf):
        return open(kf).read().strip()
    k = secrets.token_hex(32)
    with open(kf, "w") as f:
        f.write(k)
    os.chmod(kf, 0o600)
    return k


AUDIT_KEY = _audit_key()


def plate_ref(plate):
    return "pref:" + hmac_mod.new(
        AUDIT_KEY.encode(), plate.upper().encode(), hashlib.sha256
    ).hexdigest()[:24]


# --- users / cases, reloaded on mtime change so provision.py and the
# --- nightly case export take effect without a restart ----------------
_users_mtime = None
_cases_mtime = None
USERS = {}
CASES = set()


def _reload_config():
    global USERS, CASES, _users_mtime, _cases_mtime
    try:
        m = os.path.getmtime(USERS_PATH)
        if m != _users_mtime:
            USERS = {u["user"]: u for u in json.load(open(USERS_PATH))}
            _users_mtime = m
    except (OSError, ValueError):
        pass  # keep last good config; a missing file must not open the door
    try:
        m = os.path.getmtime(CASES_PATH)
        if m != _cases_mtime:
            CASES = set(json.load(open(CASES_PATH))["open_cases"])
            _cases_mtime = m
    except (OSError, ValueError):
        pass


_reload_config()

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute("PRAGMA busy_timeout = 5000")
db.execute("PRAGMA secure_delete = ON")
db.executescript(
    """CREATE TABLE IF NOT EXISTS reads(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         plate TEXT, state TEXT, conf REAL);
       CREATE TABLE IF NOT EXISTS hotlist(
         plate TEXT PRIMARY KEY, state TEXT, category TEXT, source TEXT,
         case_no TEXT, added_by TEXT, added_ts TEXT, expires_ts TEXT,
         active INTEGER DEFAULT 1);
       CREATE TABLE IF NOT EXISTS hits(
         id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cam TEXT,
         read_plate TEXT, entry_plate TEXT, category TEXT,
         status TEXT DEFAULT 'PENDING', decided_by TEXT, case_no TEXT,
         decided_ts TEXT);
       CREATE TABLE IF NOT EXISTS holds(
         id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, ref TEXT,
         reason TEXT, placed_by TEXT, placed_ts TEXT,
         released_by TEXT, released_ts TEXT, active INTEGER DEFAULT 1);
       CREATE TABLE IF NOT EXISTS outcomes(
         hit_id INTEGER PRIMARY KEY, list_name TEXT, category TEXT,
         confirmed INTEGER DEFAULT 0, arrest INTEGER DEFAULT 0,
         prosecution INTEGER DEFAULT 0, updated_by TEXT, updated_ts TEXT,
         hit_ts TEXT);
       CREATE TABLE IF NOT EXISTS case_searches(
         case_no TEXT, day TEXT, frag TEXT,
         PRIMARY KEY(case_no, day, frag));
       CREATE TABLE IF NOT EXISTS case_flags(
         case_no TEXT, day TEXT, PRIMARY KEY(case_no, day));
       CREATE TABLE IF NOT EXISTS suppressions(
         plate_ref TEXT PRIMARY KEY, placed_by TEXT, case_no TEXT,
         ts TEXT, active INTEGER DEFAULT 1);
       CREATE TABLE IF NOT EXISTS counters(
         day TEXT, camera_id TEXT, reads INTEGER DEFAULT 0,
         alerts INTEGER DEFAULT 0, PRIMARY KEY(day, camera_id));
       CREATE TABLE IF NOT EXISTS heartbeats(
         job TEXT PRIMARY KEY, ts TEXT, ok INTEGER, detail TEXT);
       CREATE TABLE IF NOT EXISTS tier3_requests(
         id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT,
         case_no TEXT, why TEXT, plate_fragment TEXT, auth_basis TEXT,
         status TEXT DEFAULT 'PENDING', created_ts TEXT,
         decided_by TEXT, decided_ts TEXT, emergency INTEGER DEFAULT 0,
         needs_review INTEGER DEFAULT 0, review_finding TEXT,
         reviewed_by TEXT, reviewed_ts TEXT, results_count INTEGER);
       CREATE TABLE IF NOT EXISTS evidence(
         hit_id INTEGER PRIMARY KEY, export_ts TEXT, export_by TEXT,
         manifest_hash TEXT, bundle TEXT, prosecutor_name TEXT,
         prosecutor_date TEXT, released_by TEXT, released_ts TEXT);"""
)
db.commit()
chain = Chain(DB_PATH)
DBLOCK = threading.Lock()

# Catch-all case numbers ("PATROL-2026", a duty log, a test case) are how
# the case gate gets laundered — any case containing one of these patterns
# is rejected and logged. Comma list, case-insensitive substring match.
BANNED_CASE_PATTERNS = [p.strip().upper() for p in os.environ.get(
    "NOCTUA_BANNED_CASE_PATTERNS", "PATROL,TEST,ADMIN,DUTY").split(",")
    if p.strip()]


def auth(handler):
    """Return the user record or None. There are no shared accounts:
    a name that is not an individual in users.json cannot authenticate,
    and a disabled account (provision.py disable-user) cannot either."""
    _reload_config()
    user = handler.headers.get("X-Noctua-User", "")
    key = handler.headers.get("X-Noctua-Key", "")
    rec = USERS.get(user)
    if not rec or rec.get("disabled") or sha(key) != rec["key_sha256"]:
        return None
    return rec


def case_gate(case_no):
    """(ok, reason) for the case checks shared by /search and /tier3/*."""
    if any(p in (case_no or "").upper() for p in BANNED_CASE_PATTERNS):
        return False, "catch-all case numbers are banned"
    if case_no not in CASES:
        return False, "case number failed validation"
    return True, ""


def janus_gate(user_rec, tier, case_no, judicial, emergency):
    """The v0.9 rules for /search, in order. Returns (ok, reason).

    1.0 note: Tier 3 no longer passes this gate at all — /search refuses
    tier=3 before reaching here and points at the two-key workflow.
    """
    if user_rec["role"] == "auditor":
        return False, "auditor accounts are read-only and cannot run queries"
    ok, why = case_gate(case_no)
    if not ok:
        return False, why
    if emergency and user_rec["role"] != "supervisor":
        return False, "emergency path is supervisor-only"
    return True, ""


def run_search(frag, viewer_rec):
    """Execute a read search and shape the results for the viewer.

    Protection-order suppression (SS 12-12-1808): a suppressed plate's
    data is disclosed only on a match workflow, so a plain search
    returns a bare stub to non-supervisors — no plate, no time, no
    camera. Supervisors see the record with the marker, because someone
    has to be able to work it. Used by /search, /tier3/approve and
    /tier3/emergency so the shaping rule exists exactly once.
    """
    frag = (frag or "").upper()
    rows = db.execute(
        "SELECT ts,cam,plate,state FROM reads WHERE plate LIKE ? "
        "ORDER BY ts DESC LIMIT 200", ("%" + frag + "%",)).fetchall()
    hit_rows = db.execute(
        "SELECT ts,cam,read_plate,status FROM hits WHERE read_plate LIKE ? "
        "ORDER BY ts DESC LIMIT 50", ("%" + frag + "%",)).fetchall()
    sup = {r[0] for r in db.execute(
        "SELECT plate_ref FROM suppressions WHERE active=1")}

    def shape(r, keys, plate_idx):
        if plate_ref(r[plate_idx]) in sup:
            if viewer_rec["role"] != "supervisor":
                return {"suppressed": True}
            d = dict(zip(keys, r))
            d["marker"] = "SUPPRESSED — protection order"
            return d
        return dict(zip(keys, r))

    return {
        "reads": [shape(r, ("ts", "cam", "plate", "state"), 2) for r in rows],
        "hits": [shape(r, ("ts", "cam", "plate", "status"), 2)
                 for r in hit_rows]}


def jobs_status():
    """Dead-man status for the required jobs (retention, checkpoint)."""
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
            last = datetime.strptime(r[1], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            age = int((now - last).total_seconds())
        except ValueError:
            age = None
        od = age is None or age > max_age
        jobs[job] = {"last": r[1], "ok": bool(r[2]), "detail": r[3],
                     "age_s": age, "overdue": od}
        if od:
            overdue.append(job)
    for job, r in rows.items():
        if job not in jobs:
            jobs[job] = {"last": r[1], "ok": bool(r[2]), "detail": r[3],
                         "overdue": False}
    return jobs, overdue


# --- reads table migration: carry the camera timestamp alongside the
# --- server receipt time (INTERFACE: "reads carry camera timestamps,
# --- server flags clock skew >5s"). ts stays the server receipt time —
# --- the system of record — so a mis-set camera clock cannot make a
# --- read born-expired under the retention job.
_cols = [r[1] for r in db.execute("PRAGMA table_info(reads)")]
if "cam_ts" not in _cols:
    db.execute("ALTER TABLE reads ADD COLUMN cam_ts TEXT")
    db.commit()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def need_auth(self):
        rec = auth(self)
        if not rec:
            self.send_json(401, {"error": "authentication failed — "
                                         "named individual accounts only"})
        return rec

    # ---------------- POST ----------------
    def do_POST(self):
        with DBLOCK:
            self._post()

    def _post(self):
        path = urlparse(self.path).path
        rec = self.need_auth()
        if not rec:
            return
        if path == "/reads":
            if rec["role"] != "system":
                return self.send_json(403, {"error": "ingest is system-only"})
            d = self.body_json()
            plate, state = d["plate"].upper(), d.get("state", "AR").upper()
            cam = d["cam"]
            ts = now_iso()
            cam_ts = d.get("ts")
            skew_s = None
            if cam_ts:
                try:
                    ct = datetime.strptime(
                        cam_ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc)
                    st = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc)
                    skew_s = int((st - ct).total_seconds())
                except (ValueError, TypeError):
                    cam_ts = None  # unparseable camera time: ignore, don't fail ingest
            db.execute("INSERT INTO reads(ts,cam,plate,state,conf,cam_ts) "
                       "VALUES(?,?,?,?,?,?)",
                       (ts, cam, plate, state, d.get("conf", 0.95), cam_ts))
            hit = db.execute(
                "SELECT plate,category FROM hotlist WHERE plate=? AND state=? AND active=1",
                (plate, state)).fetchone()
            hit_id = None
            if hit:
                cur = db.execute(
                    "INSERT INTO hits(ts,cam,read_plate,entry_plate,category) VALUES(?,?,?,?,?)",
                    (ts, cam, plate, hit[0], hit[1]))
                hit_id = cur.lastrowid
            # Cumulative counters: the six-month report's plates_scanned
            # must survive the 14-day retention deletes, so it is counted
            # here, at ingest, in a table retention never touches.
            db.execute(
                "INSERT INTO counters(day,camera_id,reads,alerts) VALUES(?,?,1,?) "
                "ON CONFLICT(day,camera_id) DO UPDATE SET reads=reads+1, "
                "alerts=alerts+excluded.alerts",
                (ts[:10], cam, 1 if hit else 0))
            db.commit()
            if skew_s is not None and abs(skew_s) > 5:
                chain.append("CLOCK_SKEW", {"cam": cam, "skew_s": skew_s})
            resp = {"result": "stored"}
            if skew_s is not None:
                resp["clock_skew_s"] = skew_s
            if hit:
                chain.append("ALERT", {"hit": hit_id, "cam": cam,
                                       "category": hit[1]})
                resp = {"result": "ALERT", "hit_id": hit_id}
                if skew_s is not None:
                    resp["clock_skew_s"] = skew_s
            return self.send_json(201, resp)
        if path == "/heartbeat":
            if rec["role"] != "system":
                return self.send_json(403, {"error": "heartbeats are system-only"})
            d = self.body_json()
            job = str(d.get("job", "")).strip()
            if not job:
                return self.send_json(400, {"error": "job is required"})
            db.execute(
                "INSERT INTO heartbeats(job,ts,ok,detail) VALUES(?,?,?,?) "
                "ON CONFLICT(job) DO UPDATE SET ts=excluded.ts, "
                "ok=excluded.ok, detail=excluded.detail",
                (job, now_iso(), 1 if d.get("ok", True) else 0,
                 str(d.get("detail", ""))[:500]))
            db.commit()
            chain.append("HEARTBEAT", {"job": job, "ok": bool(d.get("ok", True))})
            return self.send_json(200, {"result": "heartbeat recorded", "job": job})
        if path == "/hotlist":
            if rec["role"] not in ("detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"], "action": "hotlist add",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot add hot-list entries"})
            d = self.body_json()
            if d.get("case") not in CASES:
                chain.append("BLOCKED", {"user": rec["user"], "action": "hotlist add",
                                         "reason": "case failed validation"})
                return self.send_json(403, {"error": "case number failed validation"})
            db.execute(
                "INSERT OR REPLACE INTO hotlist VALUES(?,?,?,?,?,?,?,?,1)",
                (d["plate"].upper(), d.get("state", "AR").upper(), d["category"],
                 "Local — case " + d["case"], d["case"], rec["user"], now_iso(),
                 d.get("expires", "")))
            db.commit()
            chain.append("HOTLIST_ADD", {"plate_ref": plate_ref(d["plate"]),
                                         "category": d["category"], "by": rec["user"],
                                         "case": d["case"]})
            return self.send_json(201, {"result": "added"})
        if path == "/verify":
            if rec["role"] not in ("detective", "patrol", "supervisor"):
                return self.send_json(403, {"error": "role cannot verify hits"})
            d = self.body_json()
            if d.get("case") not in CASES:
                chain.append("BLOCKED", {"user": rec["user"], "action": "hit verification",
                                         "hit": d.get("hit_id"),
                                         "reason": "case failed validation"})
                return self.send_json(403, {"error": "case number failed validation"})
            hit = db.execute("SELECT entry_plate, category, ts FROM hits "
                             "WHERE id=? AND status='PENDING'",
                             (d["hit_id"],)).fetchone()
            if not hit:
                chain.append("BLOCKED", {"user": rec["user"], "action": "hit verification",
                                         "hit": d.get("hit_id"),
                                         "reason": "hit not pending"})
                return self.send_json(409, {"error": "hit not found or already decided"})
            status = "VERIFIED" if d["decision"] == "confirm" else "REJECTED"
            db.execute("UPDATE hits SET status=?, decided_by=?, case_no=?, decided_ts=? "
                       "WHERE id=? AND status='PENDING'",
                       (status, rec["user"], d["case"], now_iso(), d["hit_id"]))
            # Plate-free outcome record for the SS 12-12-1805 report. It
            # carries NO plate text and the retention job NEVER deletes
            # outcomes — the statute's six-month aggregates must survive
            # 18 months, long past the 14/30-day record horizons.
            src = db.execute("SELECT source FROM hotlist WHERE plate=?",
                             (hit[0],)).fetchone()
            db.execute(
                "INSERT INTO outcomes(hit_id, list_name, category, confirmed,"
                " arrest, prosecution, updated_by, updated_ts, hit_ts)"
                " VALUES(?,?,?,?,0,0,?,?,?)"
                " ON CONFLICT(hit_id) DO UPDATE SET"
                " confirmed=excluded.confirmed,"
                " updated_by=excluded.updated_by,"
                " updated_ts=excluded.updated_ts",
                (d["hit_id"], src[0] if src else hit[1], hit[1],
                 1 if d["decision"] == "confirm" else 0,
                 rec["user"], now_iso(), hit[2]))
            db.commit()
            chain.append("VERIFY", {"hit": d["hit_id"], "result": status,
                                    "by": rec["user"], "case": d["case"]})
            return self.send_json(200, {"result": status})
        if path == "/outcomes":
            if rec["role"] not in ("detective", "supervisor"):
                return self.send_json(403, {"error": "role cannot update outcomes"})
            d = self.body_json()
            row = db.execute("SELECT arrest, prosecution FROM outcomes "
                             "WHERE hit_id=?", (d.get("hit_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no outcome record for that "
                                                   "hit — verify the hit first"})
            arrest = (1 if d["arrest"] else 0) if "arrest" in d else row[0]
            pros = (1 if d["prosecution"] else 0) if "prosecution" in d else row[1]
            db.execute("UPDATE outcomes SET arrest=?, prosecution=?, "
                       "updated_by=?, updated_ts=? WHERE hit_id=?",
                       (arrest, pros, rec["user"], now_iso(), d["hit_id"]))
            db.commit()
            chain.append("OUTCOME_UPDATE", {"hit": d["hit_id"], "arrest": arrest,
                                            "prosecution": pros, "by": rec["user"]})
            return self.send_json(200, {"result": "outcome updated",
                                        "hit": d["hit_id"], "arrest": arrest,
                                        "prosecution": pros})
        if path == "/holds":
            if rec["role"] not in ("detective", "supervisor"):
                chain.append("BLOCKED", {"user": rec["user"], "action": "hold place",
                                         "reason": "role"})
                return self.send_json(403, {"error": "role cannot place holds"})
            d = self.body_json()
            if d.get("scope") not in ("case", "hit"):
                return self.send_json(400, {"error": "scope must be 'case' or 'hit'"})
            cur = db.execute(
                "INSERT INTO holds(scope, ref, reason, placed_by, placed_ts, active)"
                " VALUES(?,?,?,?,?,1)",
                (d["scope"], str(d.get("ref", "")), d.get("reason", ""),
                 rec["user"], now_iso()))
            db.commit()
            chain.append("HOLD_PLACE", {"hold": cur.lastrowid, "scope": d["scope"],
                                        "ref": str(d.get("ref", "")),
                                        "by": rec["user"]})
            return self.send_json(201, {"result": "hold placed",
                                        "hold_id": cur.lastrowid})
        if path == "/holds/release":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"], "action": "hold release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "hold release is supervisor-only"})
            d = self.body_json()
            row = db.execute("SELECT active FROM holds WHERE id=?",
                             (d.get("hold_id"),)).fetchone()
            if not row or not row[0]:
                return self.send_json(404, {"error": "no active hold with that id"})
            db.execute("UPDATE holds SET active=0, released_by=?, released_ts=? "
                       "WHERE id=?", (rec["user"], now_iso(), d["hold_id"]))
            db.commit()
            chain.append("HOLD_RELEASE", {"hold": d["hold_id"], "by": rec["user"]})
            return self.send_json(200, {"result": "hold released"})
        if path == "/suppressions":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression place",
                                         "reason": "role"})
                return self.send_json(403, {"error": "suppressions are supervisor-only"})
            d = self.body_json()
            if d.get("case") not in CASES:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression place",
                                         "reason": "case failed validation"})
                return self.send_json(403, {"error": "case number failed validation"})
            ref = plate_ref(d["plate"])
            db.execute(
                "INSERT INTO suppressions(plate_ref, placed_by, case_no, ts, active)"
                " VALUES(?,?,?,?,1)"
                " ON CONFLICT(plate_ref) DO UPDATE SET active=1,"
                " placed_by=excluded.placed_by, case_no=excluded.case_no,"
                " ts=excluded.ts",
                (ref, rec["user"], d["case"], now_iso()))
            db.commit()
            chain.append("SUPPRESSION_PLACE", {"plate_ref": ref, "by": rec["user"],
                                               "case": d["case"]})
            return self.send_json(201, {"result": "suppression placed"})
        if path == "/suppressions/release":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "suppression release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "suppressions are supervisor-only"})
            d = self.body_json()
            ref = plate_ref(d["plate"])
            cur = db.execute("UPDATE suppressions SET active=0 "
                             "WHERE plate_ref=? AND active=1", (ref,))
            db.commit()
            if not cur.rowcount:
                return self.send_json(404, {"error": "no active suppression for "
                                                   "that plate"})
            chain.append("SUPPRESSION_RELEASE", {"plate_ref": ref,
                                                 "by": rec["user"]})
            return self.send_json(200, {"result": "suppression released"})
        if path.startswith("/tier3/"):
            return self._tier3_post(path, rec)
        if path.startswith("/evidence/"):
            return self._evidence_post(path, rec)
        return self.send_json(404, {"error": "no such route"})

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
            frag = (d.get("plate_fragment") or "").strip().upper()
            basis = (d.get("auth_basis") or "").strip()
            if not why:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "no justification"})
                return self.send_json(403, {"error": "BLOCKED: Tier 3 requests "
                                                   "require a justification (why)"})
            if not frag:
                return self.send_json(400, {"error": "plate_fragment is required"})
            if not basis:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "reason": "no authorization basis"})
                return self.send_json(403, {"error": "BLOCKED: Tier 3 requests "
                                                   "require auth_basis (the warrant "
                                                   "or court order on file)"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 request",
                                         "case": case_no, "reason": reason})
                return self.send_json(403, {"error": "BLOCKED: " + reason})
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, status, created_ts) "
                "VALUES(?,?,?,?,?,'PENDING',?)",
                (rec["user"], case_no, why, frag, basis, now_iso()))
            db.commit()
            chain.append("TIER3_REQUEST", {
                "request": cur.lastrowid, "by": rec["user"], "case": case_no,
                "plate_ref": plate_ref(frag), "auth_basis": basis})
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
                "SELECT requester, case_no, why, plate_fragment, auth_basis, "
                "status FROM tier3_requests WHERE id=?",
                (d.get("request_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 request"})
            requester, case_no, why, frag, basis, status = row
            if status != "PENDING":
                return self.send_json(409, {"error": "request is not pending "
                                                   "(status: %s)" % status})
            if rec["user"] == requester:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 approve",
                                         "request": d["request_id"],
                                         "reason": "same-user approval — "
                                                   "two-key rule"})
                return self.send_json(403, {"error": "BLOCKED: the two-key rule "
                                                   "forbids approving your own "
                                                   "Tier 3 request"})
            results = run_search(frag, rec)
            n = len(results["reads"]) + len(results["hits"])
            db.execute(
                "UPDATE tier3_requests SET status='EXECUTED', decided_by=?, "
                "decided_ts=?, results_count=? WHERE id=?",
                (rec["user"], now_iso(), n, d["request_id"]))
            db.commit()
            chain.append("TIER3_APPROVE", {
                "request": d["request_id"], "by": rec["user"],
                "requester": requester, "case": case_no,
                "plate_ref": plate_ref(frag), "auth_basis": basis})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 approved search",
                "tier": 3, "case": case_no, "justification": why,
                "via_request": d["request_id"], "emergency": False})
            return self.send_json(200, {"result": "EXECUTED",
                                        "request_id": d["request_id"],
                                        "results": results})
        if path == "/tier3/deny":
            row = db.execute(
                "SELECT requester, status FROM tier3_requests WHERE id=?",
                (d.get("request_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 request"})
            if rec["role"] != "supervisor" and rec["user"] != row[0]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 deny",
                                         "reason": "role"})
                return self.send_json(403, {"error": "deny requires a supervisor "
                                                   "or the requester"})
            if row[1] != "PENDING":
                return self.send_json(409, {"error": "request is not pending"})
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
                return self.send_json(403, {"error": "the Tier 3 emergency path "
                                                   "is supervisor-only"})
            case_no = d.get("case_id", "")
            why = (d.get("why") or "").strip()
            frag = (d.get("plate_fragment") or "").strip().upper()
            basis = (d.get("auth_basis") or "").strip()
            if not why or not frag:
                return self.send_json(400, {"error": "why and plate_fragment "
                                                   "are required"})
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 emergency",
                                         "case": case_no, "reason": reason})
                return self.send_json(403, {"error": "BLOCKED: " + reason})
            results = run_search(frag, rec)
            n = len(results["reads"]) + len(results["hits"])
            cur = db.execute(
                "INSERT INTO tier3_requests(requester, case_no, why, "
                "plate_fragment, auth_basis, status, created_ts, "
                "decided_by, decided_ts, emergency, needs_review, "
                "results_count) VALUES(?,?,?,?,?,'EMERGENCY',?,?,?,1,1,?)",
                (rec["user"], case_no, why, frag, basis, now_iso(),
                 rec["user"], now_iso(), n))
            db.commit()
            chain.append("TIER3_EMERGENCY", {
                "request": cur.lastrowid, "by": rec["user"], "case": case_no,
                "plate_ref": plate_ref(frag),
                "review": "mandatory post-hoc review queued"})
            chain.append("QUERY", {
                "user": rec["user"], "type": "tier3 emergency search",
                "tier": 3, "case": case_no, "justification": why,
                "via_request": cur.lastrowid, "emergency": True})
            return self.send_json(200, {
                "result": "EXECUTED — flagged EMERGENCY, post-hoc review queued",
                "request_id": cur.lastrowid, "results": results})
        if path == "/tier3/review":
            if rec["role"] not in ("supervisor", "auditor"):
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 review",
                                         "reason": "role"})
                return self.send_json(403, {"error": "post-hoc review is "
                                                   "supervisor/auditor only"})
            finding = (d.get("finding") or "").strip()
            if not finding:
                return self.send_json(400, {"error": "a finding is required — "
                                                   "an unreviewed-feeling "
                                                   "checkbox is not a review"})
            row = db.execute(
                "SELECT requester, needs_review FROM tier3_requests WHERE id=?",
                (d.get("request_id"),)).fetchone()
            if not row:
                return self.send_json(404, {"error": "no such Tier 3 request"})
            if not row[1]:
                return self.send_json(409, {"error": "that use is not awaiting "
                                                   "review"})
            if rec["user"] == row[0]:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "tier3 review",
                                         "request": d["request_id"],
                                         "reason": "cannot review own "
                                                   "emergency use"})
                return self.send_json(403, {"error": "BLOCKED: you cannot review "
                                                   "your own emergency use"})
            db.execute(
                "UPDATE tier3_requests SET status='REVIEWED', needs_review=0, "
                "review_finding=?, reviewed_by=?, reviewed_ts=? WHERE id=?",
                (finding, rec["user"], now_iso(), d["request_id"]))
            db.commit()
            chain.append("TIER3_REVIEW", {"request": d["request_id"],
                                          "by": rec["user"], "finding": finding})
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
                return self.send_json(403, {"error": "role cannot export evidence"})
            case_no = d.get("case_id", "")
            ok, reason = case_gate(case_no)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence export",
                                         "hit": d.get("hit_id"), "reason": reason})
                return self.send_json(403, {"error": "BLOCKED: " + reason})
            hit = db.execute(
                "SELECT id,ts,cam,read_plate,entry_plate,category,status,"
                "decided_by,case_no,decided_ts FROM hits WHERE id=?",
                (d.get("hit_id"),)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no such hit"})
            hkeys = ("id", "ts", "cam", "read_plate", "entry_plate",
                     "category", "status", "decided_by", "case_no",
                     "decided_ts")
            hit_rec = dict(zip(hkeys, hit))
            reads = [dict(zip(("id", "ts", "cam", "plate", "state", "conf",
                               "cam_ts"), r)) for r in db.execute(
                "SELECT id,ts,cam,plate,state,conf,cam_ts FROM reads "
                "WHERE plate IN (?,?) ORDER BY ts", (hit[3], hit[4]))]
            outcome = db.execute(
                "SELECT hit_id,list_name,category,confirmed,arrest,"
                "prosecution,updated_by,updated_ts,hit_ts FROM outcomes "
                "WHERE hit_id=?", (hit[0],)).fetchone()
            outcome_rec = (dict(zip(
                ("hit_id", "list_name", "category", "confirmed", "arrest",
                 "prosecution", "updated_by", "updated_ts", "hit_ts"),
                outcome)) if outcome else None)
            # Chain-of-custody excerpt: the Sentinel entries that mention
            # this hit (best-effort match on the canonical payload's
            # "hit" field — the full chain stays verifiable via /audit).
            excerpt = [e for e in chain.entries(100000)
                       if e["fields"].get("hit") == hit[0]]
            os.makedirs(EVIDENCE_DIR, mode=0o700, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bundle_name = "hit-%d-%s" % (hit[0], stamp)
            bundle_path = os.path.join(EVIDENCE_DIR, bundle_name)
            os.makedirs(bundle_path, mode=0o700)
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
                        "exported_by": rec["user"], "exported_ts": now_iso(),
                        "files": files}
            mhash = sha(json.dumps(manifest, sort_keys=True,
                                   separators=(",", ":")))
            manifest["manifest_hash"] = mhash
            put("manifest.json", manifest)
            db.execute(
                "INSERT INTO evidence(hit_id, export_ts, export_by, "
                "manifest_hash, bundle) VALUES(?,?,?,?,?) "
                "ON CONFLICT(hit_id) DO UPDATE SET export_ts=excluded.export_ts,"
                " export_by=excluded.export_by,"
                " manifest_hash=excluded.manifest_hash, bundle=excluded.bundle",
                (hit[0], manifest["exported_ts"], rec["user"], mhash,
                 bundle_name))
            db.commit()
            chain.append("EVIDENCE_EXPORT", {"hit": hit[0], "case": case_no,
                                             "manifest": mhash,
                                             "by": rec["user"]})
            return self.send_json(201, {"result": "exported",
                                        "bundle": bundle_name,
                                        "manifest_hash": mhash,
                                        "files": files})
        if path == "/evidence/release":
            if rec["role"] != "supervisor":
                chain.append("BLOCKED", {"user": rec["user"],
                                         "action": "evidence release",
                                         "reason": "role"})
                return self.send_json(403, {"error": "evidence release is "
                                                   "supervisor-only"})
            so = d.get("prosecutor_signoff") or {}
            pname = (so.get("name") or d.get("prosecutor_name") or "").strip()
            pdate = (so.get("date") or d.get("prosecutor_date") or "").strip()
            if not pname or not pdate:
                return self.send_json(400, {"error": "prosecutor_signoff with "
                                                   "name and date is required"})
            hit = db.execute("SELECT id FROM hits WHERE id=?",
                             (d.get("hit_id"),)).fetchone()
            if not hit:
                return self.send_json(404, {"error": "no such hit"})
            db.execute(
                "INSERT INTO evidence(hit_id, prosecutor_name, "
                "prosecutor_date, released_by, released_ts) VALUES(?,?,?,?,?) "
                "ON CONFLICT(hit_id) DO UPDATE SET "
                "prosecutor_name=excluded.prosecutor_name, "
                "prosecutor_date=excluded.prosecutor_date, "
                "released_by=excluded.released_by, "
                "released_ts=excluded.released_ts",
                (d["hit_id"], pname, pdate, rec["user"], now_iso()))
            db.commit()
            chain.append("EVIDENCE_RELEASE", {"hit": d["hit_id"],
                                              "prosecutor": pname,
                                              "date": pdate,
                                              "by": rec["user"]})
            return self.send_json(200, {"result": "released",
                                        "hit": d["hit_id"]})
        return self.send_json(404, {"error": "no such route"})

    def do_DELETE(self):
        with DBLOCK:
            self._delete()

    def _delete(self):
        path = urlparse(self.path).path
        rec = self.need_auth()
        if not rec:
            return
        if path.startswith("/hotlist/"):
            if rec["role"] not in ("detective", "supervisor"):
                return self.send_json(403, {"error": "role cannot remove entries"})
            plate = path.split("/", 2)[2].upper()
            db.execute("UPDATE hotlist SET active=0 WHERE plate=?", (plate,))
            db.commit()
            chain.append("HOTLIST_REMOVE", {"plate_ref": plate_ref(plate),
                                            "by": rec["user"]})
            return self.send_json(200, {"result": "deactivated"})
        return self.send_json(404, {"error": "no such route"})

    # ---------------- queries ----------------
    def do_GET(self):
        with DBLOCK:
            self._get()

    def _get(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/health":
            jobs, overdue = jobs_status()
            return self.send_json(200, {"ok": True, "service": "janus",
                                        "version": "1.0",
                                        "degraded": bool(overdue),
                                        "overdue_jobs": overdue,
                                        "jobs": jobs,
                                        "root": chain.root()[:16],
                                        "sentinel_sink": chain.sink_status()})
        if path == "/audit/verify":
            return self.send_json(200, chain.verify())
        if path == "/audit/root":
            return self.send_json(200, {"root": chain.root(), "ts": now_iso()})
        rec = self.need_auth()
        if not rec:
            return
        if path == "/audit":
            if rec["role"] not in ("detective", "supervisor", "auditor", "patrol"):
                return self.send_json(403, {"error": "role"})
            return self.send_json(200, {"entries": chain.entries(
                int(q.get("limit", ["200"])[0]))})
        if path == "/search":
            tier = int(q.get("tier", ["2"])[0])
            case_no = q.get("case", [""])[0]
            justification = q.get("why", [""])[0].strip()
            if tier == 3:
                # 1.0: Tier 3 is two-key only. The v0.9 judicial=1 flag
                # no longer executes a historical search by itself.
                chain.append("BLOCKED", {"user": rec["user"], "action": "search",
                                         "tier": 3, "case": case_no,
                                         "reason": "tier 3 requires the two-key "
                                                   "workflow"})
                return self.send_json(403, {
                    "error": "BLOCKED: Tier 3 (historical) searches run only "
                             "through the two-key workflow — POST "
                             "/tier3/request, then a supervisor approves "
                             "with POST /tier3/approve"})
            judicial = q.get("judicial", ["0"])[0] == "1"
            emergency = q.get("emergency", ["0"])[0] == "1"
            # A search with no stated reason is not a search this system
            # runs. The justification lands in the QUERY chain entry, so
            # "why was this plate run?" is always answerable later.
            if not justification:
                chain.append("BLOCKED", {"user": rec["user"], "action": "search",
                                         "tier": tier, "case": case_no,
                                         "reason": "no justification"})
                return self.send_json(403, {"error": "BLOCKED: searches require "
                                                   "a justification (why)"})
            ok, why = janus_gate(rec, tier, case_no, judicial, emergency)
            if not ok:
                chain.append("BLOCKED", {"user": rec["user"], "action": "search",
                                         "tier": tier, "case": case_no, "reason": why})
                return self.send_json(403, {"error": "BLOCKED: " + why})
            frag = q.get("plate", [""])[0].upper()
            # Case-reuse flag: one case number sweeping many distinct
            # plates in a day is the laundering pattern. Flag it for the
            # auditor (once per case per day) — flag, not block: a real
            # investigation can legitimately run hot.
            day = now_iso()[:10]
            db.execute("INSERT OR IGNORE INTO case_searches(case_no, day, frag)"
                       " VALUES(?,?,?)", (case_no, day, frag))
            db.commit()
            n_frag = db.execute("SELECT COUNT(*) FROM case_searches "
                                "WHERE case_no=? AND day=?",
                                (case_no, day)).fetchone()[0]
            if n_frag > 8:
                cur = db.execute("INSERT OR IGNORE INTO case_flags(case_no, day)"
                                 " VALUES(?,?)", (case_no, day))
                db.commit()
                if cur.rowcount:
                    chain.append("CASE_FLAG", {
                        "case": case_no, "day": day, "distinct_plates": n_frag,
                        "reason": "one case searched many distinct plates in "
                                  "one day — auditor review"})
            results = run_search(frag, rec)
            chain.append("QUERY", {"user": rec["user"], "type": "read search",
                                   "tier": tier, "case": case_no,
                                   "justification": justification,
                                   "emergency": emergency})
            return self.send_json(200, results)
        if path == "/tier3/pending" or path == "/tier3/pending-reviews":
            if rec["role"] not in ("detective", "supervisor", "auditor"):
                return self.send_json(403, {"error": "role"})
            keys = ("id", "requester", "case_no", "why", "plate_fragment",
                    "auth_basis", "status", "created_ts", "decided_by",
                    "decided_ts", "emergency", "needs_review")
            if path == "/tier3/pending":
                rows = db.execute(
                    "SELECT id,requester,case_no,why,plate_fragment,"
                    "auth_basis,status,created_ts,decided_by,decided_ts,"
                    "emergency,needs_review FROM tier3_requests "
                    "WHERE status='PENDING' ORDER BY id").fetchall()
                return self.send_json(200, {"requests": [
                    dict(zip(keys, r)) for r in rows]})
            rows = db.execute(
                "SELECT id,requester,case_no,why,plate_fragment,"
                "auth_basis,status,created_ts,decided_by,decided_ts,"
                "emergency,needs_review FROM tier3_requests "
                "WHERE needs_review=1 ORDER BY id").fetchall()
            return self.send_json(200, {"pending_reviews": [
                dict(zip(keys, r)) for r in rows]})
        if path == "/report":
            # SS 12-12-1805 usage report, in the statute's categories.
            # Aggregates only — no plate data — so the auditor role is
            # allowed. Match-side figures come from the outcomes table
            # (which retention never deletes). 1.0 change: plates_scanned
            # comes from the cumulative counters table (incremented at
            # ingest), so the six-month figure survives the 14-day
            # retention deletes — the v0.9 caveat (snapshot at period
            # close) is gone. Counters are day-granular: a window's
            # first/last partial days count whole days. Counters start
            # accumulating at 1.0 deployment; reads ingested under v0.9
            # are not in them.
            frm = q.get("from", [""])[0]
            to = q.get("to", ["9999-12-31T23:59:59Z"])[0]
            scanned = db.execute(
                "SELECT COALESCE(SUM(reads),0) FROM counters "
                "WHERE day>=? AND day<=?", (frm[:10], to[:10])).fetchone()[0]
            lists = {}
            for name, n in db.execute(
                    "SELECT list_name, COUNT(*) FROM outcomes "
                    "WHERE confirmed=1 AND hit_ts>=? AND hit_ts<=? "
                    "GROUP BY list_name", (frm, to)):
                lists[name] = {"confirmed_matches": n}
            confirmed = sum(v["confirmed_matches"] for v in lists.values())
            not_corr = db.execute(
                "SELECT COUNT(*) FROM hits WHERE status='REJECTED' "
                "AND decided_ts>=? AND decided_ts<=?", (frm, to)).fetchone()[0]
            arrests = db.execute(
                "SELECT COUNT(*) FROM outcomes WHERE arrest=1 "
                "AND hit_ts>=? AND hit_ts<=?", (frm, to)).fetchone()[0]
            prosecutions = db.execute(
                "SELECT COUNT(*) FROM outcomes WHERE prosecution=1 "
                "AND hit_ts>=? AND hit_ts<=?", (frm, to)).fetchone()[0]
            return self.send_json(200, {
                "from": frm, "to": to, "plates_scanned": scanned,
                "plates_scanned_source": "counters (cumulative at ingest; "
                                         "survives retention deletes)",
                "lists": lists, "confirmed_matches": confirmed,
                "matches_not_corresponding": not_corr,
                "arrests": arrests, "prosecutions": prosecutions})
        if path == "/hotlist":
            rows = db.execute("SELECT plate,state,category,source,added_by,expires_ts "
                              "FROM hotlist WHERE active=1 ORDER BY plate").fetchall()
            return self.send_json(200, {"entries": [
                dict(zip(("plate", "state", "category", "source", "added_by", "expires"), r))
                for r in rows]})
        if path == "/hits":
            st = q.get("status", ["PENDING"])[0]
            rows = db.execute("SELECT id,ts,cam,read_plate,entry_plate,category,status "
                              "FROM hits WHERE status=? ORDER BY ts DESC", (st,)).fetchall()
            return self.send_json(200, {"hits": [
                dict(zip(("id", "ts", "cam", "read_plate", "entry_plate",
                          "category", "status"), r)) for r in rows]})
        if path == "/stats":
            one = lambda sql: db.execute(sql).fetchone()[0]
            return self.send_json(200, {
                "reads": one("SELECT COUNT(*) FROM reads"),
                "reads_counted": one("SELECT COALESCE(SUM(reads),0) FROM counters"),
                "hits_pending": one("SELECT COUNT(*) FROM hits WHERE status='PENDING'"),
                "hits_verified": one("SELECT COUNT(*) FROM hits WHERE status='VERIFIED'"),
                "hotlist_active": one("SELECT COUNT(*) FROM hotlist WHERE active=1"),
                "tier3_pending": one("SELECT COUNT(*) FROM tier3_requests "
                                     "WHERE status='PENDING'"),
                "tier3_unreviewed_emergencies": one(
                    "SELECT COUNT(*) FROM tier3_requests WHERE needs_review=1"),
                "audit_entries": one("SELECT COUNT(*) FROM audit")})
        return self.send_json(404, {"error": "no such route"})


if __name__ == "__main__":
    chain.append("SYSTEM", {"event": "janus started", "port": PORT,
                            "version": "1.0"})
    print(f"Janus 1.0 listening on :{PORT} (db {DB_PATH})")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
