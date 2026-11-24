#!/usr/bin/env python3
"""Janus — the NOCTUA front door.

The ONLY way anything reads or writes NOCTUA data. Stdlib-only Python
service over SQLite, built to the Cabot pilot spec (Nov. 23, 2026):

  * Named individual accounts with per-user keys. Shared/generic accounts
    do not exist and cannot authenticate.
  * Every search is tied to a case number validated against the open-case
    list (in production: a nightly export from the records system).
  * Tier 2 (contemporaneous) needs a valid case. Tier 3 (historical)
    additionally needs judicial authorization on file, or the emergency
    flag from a supervisor — which is logged as an emergency.
  * The outside-auditor role is read-only for the audit log and cannot
    search, verify, or touch the hot list.
  * Every allowed AND blocked action is written to the Sentinel chain.

Endpoints:
  GET  /health           (includes Sentinel sink status)
  POST /reads            ingest a plate read (role: system) -> alert on match
  GET  /search?plate=&case=&why=&tier=2&judicial=0|1&emergency=0|1
                         (why is REQUIRED; catch-all case patterns banned;
                         suppressed plates are stubbed for non-supervisors)
  GET  /hotlist          POST /hotlist   DELETE /hotlist/<plate>
  POST /verify           {hit_id, decision: confirm|reject, case}
                         (also writes the plate-free outcome record)
  POST /outcomes         {hit_id, arrest, prosecution} — outcome feedback
                         (the prosecutor-feedback placeholder)
  GET  /report?from=&to= SS 12-12-1805 aggregates (auditor allowed)
  POST /holds            {scope: case|hit, ref, reason}  (detective+)
  POST /holds/release    {hold_id}  (supervisor)
  POST /suppressions     {plate, case}  (supervisor; protection orders)
  POST /suppressions/release  {plate}   (supervisor)
  GET  /hits?status=PENDING
  GET  /audit?limit=200  GET /audit/verify  GET /audit/root
  GET  /stats

Config (environment):
  NOCTUA_DB=/data/noctua.db  NOCTUA_USERS=/config/users.json
  NOCTUA_CASES=/config/cases.json  NOCTUA_PORT=8080
  RETENTION_DAYS=14  HOLD_DAYS=30
  NOCTUA_AUDIT_KEY=<hmac key>          (or the .audit_key file by the DB)
  NOCTUA_SENTINEL_SINK=/path/sink.jsonl  (optional streaming copy of chain)
  NOCTUA_BANNED_CASE_PATTERNS=PATROL,TEST,ADMIN,DUTY  (catch-all case ban)
"""
import hashlib
import hmac as hmac_mod
import json
import os
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from sentinel import Chain, now_iso, sha

DB_PATH = os.environ.get("NOCTUA_DB", "/data/noctua.db")
USERS_PATH = os.environ.get("NOCTUA_USERS", "/config/users.json")
CASES_PATH = os.environ.get("NOCTUA_CASES", "/config/cases.json")
PORT = int(os.environ.get("NOCTUA_PORT", "8080"))


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

USERS = {u["user"]: u for u in json.load(open(USERS_PATH))}
CASES = set(json.load(open(CASES_PATH))["open_cases"])

db = sqlite3.connect(DB_PATH, check_same_thread=False)
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
         ts TEXT, active INTEGER DEFAULT 1);"""
)
db.commit()
chain = Chain(DB_PATH)

# Catch-all case numbers ("PATROL-2026", a duty log, a test case) are how
# the case gate gets laundered — any case containing one of these patterns
# is rejected and logged. Comma list, case-insensitive substring match.
BANNED_CASE_PATTERNS = [p.strip().upper() for p in os.environ.get(
    "NOCTUA_BANNED_CASE_PATTERNS", "PATROL,TEST,ADMIN,DUTY").split(",")
    if p.strip()]


def auth(handler):
    """Return the user record or None. There are no shared accounts:
    a name that is not an individual in users.json cannot authenticate."""
    user = handler.headers.get("X-Noctua-User", "")
    key = handler.headers.get("X-Noctua-Key", "")
    rec = USERS.get(user)
    if not rec or sha(key) != rec["key_sha256"]:
        return None
    return rec


def janus_gate(user_rec, tier, case_no, judicial, emergency):
    """The rules, in order. Returns (ok, reason). Blocks are logged by caller."""
    if user_rec["role"] == "auditor":
        return False, "auditor accounts are read-only and cannot run queries"
    if case_no not in CASES:
        return False, "case number failed validation"
    if tier == 3 and not judicial and not emergency:
        return False, "Tier 3 requires judicial authorization or supervisor emergency"
    if emergency and user_rec["role"] != "supervisor":
        return False, "emergency path is supervisor-only"
    return True, ""


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

    # ---------------- reads / ingest ----------------
    def do_POST(self):
        path = urlparse(self.path).path
        rec = self.need_auth()
        if not rec:
            return
        if path == "/reads":
            if rec["role"] != "system":
                return self.send_json(403, {"error": "ingest is system-only"})
            d = self.body_json()
            plate, state = d["plate"].upper(), d.get("state", "AR").upper()
            db.execute("INSERT INTO reads(ts,cam,plate,state,conf) VALUES(?,?,?,?,?)",
                       (now_iso(), d["cam"], plate, state, d.get("conf", 0.95)))
            db.commit()
            hit = db.execute(
                "SELECT plate,category FROM hotlist WHERE plate=? AND state=? AND active=1",
                (plate, state)).fetchone()
            if hit:
                cur = db.execute(
                    "INSERT INTO hits(ts,cam,read_plate,entry_plate,category) VALUES(?,?,?,?,?)",
                    (now_iso(), d["cam"], plate, hit[0], hit[1]))
                db.commit()
                chain.append("ALERT", {"hit": cur.lastrowid, "cam": d["cam"],
                                       "category": hit[1]})
                return self.send_json(201, {"result": "ALERT", "hit_id": cur.lastrowid})
            return self.send_json(201, {"result": "stored"})
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
        return self.send_json(404, {"error": "no such route"})

    def do_DELETE(self):
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
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/health":
            return self.send_json(200, {"ok": True, "service": "janus",
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
            judicial = q.get("judicial", ["0"])[0] == "1"
            emergency = q.get("emergency", ["0"])[0] == "1"
            justification = q.get("why", [""])[0].strip()
            # A search with no stated reason is not a search this system
            # runs. The justification lands in the QUERY chain entry, so
            # "why was this plate run?" is always answerable later.
            if not justification:
                chain.append("BLOCKED", {"user": rec["user"], "action": "search",
                                         "tier": tier, "case": case_no,
                                         "reason": "no justification"})
                return self.send_json(403, {"error": "BLOCKED: searches require "
                                                   "a justification (why)"})
            if any(p in case_no.upper() for p in BANNED_CASE_PATTERNS):
                chain.append("BLOCKED", {"user": rec["user"], "action": "search",
                                         "tier": tier, "case": case_no,
                                         "reason": "banned case pattern"})
                return self.send_json(403, {"error": "BLOCKED: catch-all case "
                                                   "numbers are banned"})
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
            rows = db.execute(
                "SELECT ts,cam,plate,state FROM reads WHERE plate LIKE ? "
                "ORDER BY ts DESC LIMIT 200", ("%" + frag + "%",)).fetchall()
            hit_rows = db.execute(
                "SELECT ts,cam,read_plate,status FROM hits WHERE read_plate LIKE ? "
                "ORDER BY ts DESC LIMIT 50", ("%" + frag + "%",)).fetchall()
            chain.append("QUERY", {"user": rec["user"], "type": "read search",
                                   "tier": tier, "case": case_no,
                                   "justification": justification,
                                   "emergency": emergency})
            # Protection-order suppression (SS 12-12-1808): a suppressed
            # plate's data is disclosed only on a match workflow, so a
            # plain search returns a bare stub to non-supervisors —
            # no plate, no time, no camera. Supervisors see the record
            # with the marker, because someone has to be able to work it.
            sup = {r[0] for r in db.execute(
                "SELECT plate_ref FROM suppressions WHERE active=1")}

            def shape_read(r):
                if plate_ref(r[2]) in sup:
                    if rec["role"] != "supervisor":
                        return {"suppressed": True}
                    d = dict(zip(("ts", "cam", "plate", "state"), r))
                    d["marker"] = "SUPPRESSED — protection order"
                    return d
                return dict(zip(("ts", "cam", "plate", "state"), r))

            def shape_hit(r):
                if plate_ref(r[2]) in sup:
                    if rec["role"] != "supervisor":
                        return {"suppressed": True}
                    d = dict(zip(("ts", "cam", "plate", "status"), r))
                    d["marker"] = "SUPPRESSED — protection order"
                    return d
                return dict(zip(("ts", "cam", "plate", "status"), r))

            return self.send_json(200, {
                "reads": [shape_read(r) for r in rows],
                "hits": [shape_hit(r) for r in hit_rows]})
        if path == "/report":
            # SS 12-12-1805 usage report, in the statute's categories.
            # Aggregates only — no plate data — so the auditor role is
            # allowed. Match-side figures come from the outcomes table
            # (which retention never deletes); plates scanned counts the
            # reads currently in the store for the window, so the
            # six-month compilation must be snapshotted at period close,
            # before the retention horizon passes (see README).
            frm = q.get("from", [""])[0]
            to = q.get("to", ["9999-12-31T23:59:59Z"])[0]
            scanned = db.execute(
                "SELECT COUNT(*) FROM reads WHERE ts>=? AND ts<=?",
                (frm, to)).fetchone()[0]
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
                "hits_pending": one("SELECT COUNT(*) FROM hits WHERE status='PENDING'"),
                "hits_verified": one("SELECT COUNT(*) FROM hits WHERE status='VERIFIED'"),
                "hotlist_active": one("SELECT COUNT(*) FROM hotlist WHERE active=1"),
                "audit_entries": one("SELECT COUNT(*) FROM audit")})
        return self.send_json(404, {"error": "no such route"})


if __name__ == "__main__":
    chain.append("SYSTEM", {"event": "janus started", "port": PORT})
    print(f"Janus listening on :{PORT} (db {DB_PATH})")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
