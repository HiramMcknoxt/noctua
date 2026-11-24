#!/usr/bin/env python3
"""NOCTUA Janus 1.1 live test suite.

Spins up scratch Janus instances on loopback ports with throwaway
databases and exercises every council-round-2 fix over HTTP, plus
the standalone scripts (sentinel concurrency/sink, checkpoint +
anchor, rotation, sentinel_audit, compact) and the demo seed.

    python3 tests/run_tests.py

Prints one line per check and a final PASS/FAIL count; exit code is
0 only when everything passes. Nothing here touches a real install:
all state lives under a tempfile.mkdtemp directory.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JANUS = os.path.join(ROOT, "janus.py")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import rotation as rotation_mod  # noqa: E402

WORK = tempfile.mkdtemp(prefix="noctua11-tests-")
AUDIT_KEY = "test-audit-key-0123456789abcdef"

KEYS = {
    "det.okafor": "DEMO-KEY-DETECTIVE",
    "ofc.chen": "DEMO-KEY-PATROL",
    "sgt.reyes": "DEMO-KEY-SUPERVISOR",
    "capt.voss": "DEMO-KEY-SUPERVISOR2",
    "auditor.external": "DEMO-KEY-AUDITOR",
    "ingest.local": "DEMO-KEY-INGEST",
    "jobs.local": "DEMO-KEY-JOBS",
    "agency-a": "KEY-PARTNER-A",
    "agency-b": "KEY-PARTNER-B",
}
ROLES = {
    "det.okafor": "detective", "ofc.chen": "patrol",
    "sgt.reyes": "supervisor", "capt.voss": "supervisor",
    "auditor.external": "auditor", "ingest.local": "ingest",
    "jobs.local": "jobs", "agency-a": "partner", "agency-b": "partner",
}
CASES = ["2027-1001", "2027-1014", "2027-1023", "2027-1031",
         "2027-1040", "2027-1052"]

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name
          + ((" — " + str(extra)[:200]) if (extra and not cond) else ""))


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def write_users(path, extra=()):
    users = [{"user": u, "role": ROLES[u], "key_sha256": sha(k)}
             for u, k in KEYS.items()]
    for u, r, k in extra:
        users.append({"user": u, "role": r, "key_sha256": sha(k)})
    with open(path, "w") as f:
        json.dump(users, f, indent=1)


def write_cases(path, cases=CASES):
    with open(path, "w") as f:
        json.dump({"open_cases": cases}, f)


class Instance:
    def __init__(self, name, port, audit_key=AUDIT_KEY, env_extra=None,
                 key_file=False):
        self.dir = os.path.join(WORK, name)
        os.makedirs(self.dir)
        self.port = port
        self.db = os.path.join(self.dir, "janus.db")
        self.users = os.path.join(self.dir, "users.json")
        self.cases = os.path.join(self.dir, "cases.json")
        write_users(self.users)
        write_cases(self.cases)
        self.env = dict(os.environ)
        self.env.update({
            "NOCTUA_DB": self.db, "NOCTUA_USERS": self.users,
            "NOCTUA_CASES": self.cases, "NOCTUA_PORT": str(port),
            "NOCTUA_BACKFILL_FLUSH_S": "1",
            "NOCTUA_EVIDENCE_DIR": os.path.join(self.dir, "evidence"),
        })
        if audit_key and not key_file:
            self.env["NOCTUA_AUDIT_KEY"] = audit_key
        else:
            self.env.pop("NOCTUA_AUDIT_KEY", None)
        if env_extra:
            self.env.update(env_extra)
        self.proc = None

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def start(self):
        self.proc = subprocess.Popen(
            [sys.executable, JANUS], env=self.env,
            stdout=open(os.path.join(self.dir, "server.log"), "w"),
            stderr=subprocess.STDOUT)
        for _ in range(60):
            try:
                s, _b = req(self.port, "GET", "/health")
                if s == 200:
                    return
            except Exception:
                pass
            time.sleep(0.25)
        raise RuntimeError("instance %s did not start" % self.dir)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            self.proc = None


def req(port, method, path, user=None, body=None, raw_key=None):
    r = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path),
                               method=method)
    if user:
        r.add_header("X-Noctua-User", user)
        r.add_header("X-Noctua-Key", raw_key if raw_key is not None
                     else KEYS[user])
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(
            body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, data=data, timeout=20) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except ValueError:
            return e.code, {"raw": raw[:200].decode("utf-8", "replace")}


def audit_kinds(port, limit=1000):
    s, b = req(port, "GET", "/audit?limit=%d" % limit, "auditor.external")
    assert s == 200, b
    return [e["kind"] for e in b["entries"]], b["entries"]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ago_iso(**kw):
    return (datetime.now(timezone.utc)
            - timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


DET, PAT, SUP, SUP2, AUD, ING, JOB = (
    "det.okafor", "ofc.chen", "sgt.reyes", "capt.voss",
    "auditor.external", "ingest.local", "jobs.local")


def main():
    A = Instance("a", 18099)
    A.start()
    try:
        suite_a(A)
    finally:
        A.stop()
    suite_scripts(A)
    B = Instance("b", 18098)
    B.start()
    A.start()
    try:
        suite_compact(A, B)
    finally:
        B.stop()
        A.stop()
    suite_keyloss()
    suite_retention()
    suite_demo()
    failed = [n for n, ok in RESULTS if not ok]
    print("\n%d checks, %d passed, %d failed"
          % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        print("FAILED CHECKS:")
        for n in failed:
            print("  - " + n)
    return 1 if failed else 0


def suite_a(A):
    p = A.port
    # ---------- health truth + heartbeats (items 8, 24) ----------
    s, h = req(p, "GET", "/health")
    check("health: fresh instance is degraded (jobs never reported)",
          s == 200 and h["ok"] is False and h["degraded"] is True)
    check("health: exposes retention/hold days + tier2 window",
          h["retention_days"] == 14 and h["hold_days"] == 30
          and h["tier2_window_h"] == 24)
    for job in ("retention", "checkpoint", "hotlist_sync", "backup"):
        s, b = req(p, "POST", "/heartbeat", JOB,
                   {"job": job, "ok": True, "detail": "test"})
        assert s == 200, b
    s, h = req(p, "GET", "/health")
    check("health: ok:true once all jobs report ok", h["ok"] is True, h)
    s, b = req(p, "POST", "/heartbeat", JOB,
               {"job": "backup", "detail": "no ok field"})
    check("heartbeat: missing ok recorded as failure",
          s == 200 and b["ok"] is False, b)
    s, h = req(p, "GET", "/health")
    check("health: missing-ok heartbeat degrades immediately",
          h["ok"] is False and h["jobs"]["backup"]["ok"] is False)
    s, b = req(p, "POST", "/heartbeat", JOB,
               {"job": "backup", "ok": False, "detail": "disk full"})
    s, h = req(p, "GET", "/health")
    check("health: ok:false heartbeat degrades immediately",
          h["ok"] is False and h["jobs"]["backup"]["status"]
          == "reported failure")
    req(p, "POST", "/heartbeat", JOB,
        {"job": "backup", "ok": True, "detail": "recovered"})
    # ---------- service-role walls (items 8, 23) ----------
    s, b = req(p, "POST", "/heartbeat", ING,
               {"job": "retention", "ok": True})
    check("roles: ingest cannot heartbeat", s == 403, b)
    s, b = req(p, "POST", "/reads", JOB,
               {"plate": "XXX111", "cam": "CAM-01"})
    check("roles: jobs cannot ingest reads", s == 403, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=x&tier=2", ING)
    check("roles: ingest denied on /search", s == 403, b)
    s, b = req(p, "GET", "/hits", JOB)
    check("roles: jobs denied on /hits", s == 403, b)
    s, b = req(p, "GET", "/report", ING)
    check("roles: ingest denied on /report", s == 403, b)
    s, b = req(p, "GET", "/audit", PAT)
    check("roles: patrol denied on /audit", s == 403, b)
    s, b = req(p, "GET", "/audit/verify")
    check("audit/verify: unauthenticated refused", s == 401, b)
    s, b = req(p, "GET", "/audit/verify", PAT)
    check("audit/verify: patrol refused", s == 403, b)
    s, b = req(p, "GET", "/hits", DET, raw_key="wrong-key")
    check("auth: bad key refused", s == 401, b)
    kinds, _ = audit_kinds(p)
    check("auth: failed attempt chained as AUTH_FAIL",
          "AUTH_FAIL" in kinds)
    s, b = req(p, "GET", "/audit?limit=5000", AUD)
    check("audit: limit clamped to 1000",
          s == 200 and len(b["entries"]) <= 1000, len(b.get("entries",
                                                            [])))
    # ---------- hotlist, ingest, temporal wall (items 1, 2) ----------
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "RST417", "state": "AR",
                "category": "stolen vehicle", "case": "2027-1014"})
    check("hotlist: add ok", s == 201, b)
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "RST417", "state": "AR", "category": "x",
                "case": "PATROL-7"})
    check("hotlist: banned case refused (shared gate)", s == 403, b)
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "RST417", "state": "AR", "cam": "CAM-01",
                "conf": 0.97})
    check("ingest: hot plate alerts", s == 201
          and b["result"] == "ALERT", b)
    hit1 = b["hit_id"]
    # a 25h-old read, inserted directly (no backfill API by design)
    db = sqlite3.connect(A.db)
    db.execute("INSERT INTO reads(ts,cam,plate,state,conf) "
               "VALUES(?,?,?,?,?)",
               (ago_iso(hours=25), "CAM-02", "OLD111", "AR", 0.9))
    db.execute("INSERT INTO reads(ts,cam,plate,state,conf) "
               "VALUES(?,?,?,?,?)",
               (ago_iso(hours=25), "CAM-02", "RST417", "AR", 0.9))
    db.commit()
    db.close()
    s, b = req(p, "GET", "/search?plate=OLD111&case=2027-1014"
               "&justification=wall+test&tier=2", PAT)
    check("temporal wall: Tier 2 cannot see a 25h-old read",
          s == 200 and b["reads"] == [], b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=wall+test&tier=2", PAT)
    check("temporal wall: Tier 2 sees the fresh read only",
          s == 200 and len(b["reads"]) == 1, b)
    for frag, label in (("%25", "%"), ("AB", "too short"),
                        ("A_C", "underscore"), ("", "empty")):
        s, b = req(p, "GET", "/search?plate=%s&case=2027-1014"
                   "&justification=x&tier=2" % frag, PAT)
        check("fragments: %s rejected on /search" % label, s == 400, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=x&tier=3", PAT)
    check("search: tier=3 refused at /search", s == 403, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=x&tier=abc", PAT)
    check("search: non-numeric tier is 400, never 500", s == 400, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=x&tier=1", PAT)
    check("search: tier=1 refused", s == 400, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014&tier=2",
               PAT)
    check("search: missing justification blocked", s == 403, b)
    # QUERY chain entries carry plate_ref + result_count (item 3)
    kinds, entries = audit_kinds(p)
    queries = [e for e in entries if e["kind"] == "QUERY"]
    check("logging: QUERY entries carry plate_ref + result_count",
          queries and all(
              str(e["payload"].get("plate_ref", "")).startswith("pref:")
              and "result_count" in e["payload"] for e in queries),
          queries[:1])
    # ---------- hits / hotlist views (item 4) ----------
    s, b = req(p, "GET", "/hits", DET)
    check("hits: detective can view", s == 200
          and any(h["id"] == hit1 for h in b["hits"]), b)
    s, b = req(p, "GET", "/hotlist", AUD)
    check("hotlist: auditor can view", s == 200, b)
    kinds, _ = audit_kinds(p)
    check("logging: HITS_VIEW and HOTLIST_VIEW chained",
          "HITS_VIEW" in kinds and "HOTLIST_VIEW" in kinds)
    suite_a2(A, hit1)


def suite_a2(A, hit1):
    p = A.port
    # ---------- suppression redesign (item 5) ----------
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "VIC 309", "state": "AR", "cam": "CAM-04",
                "conf": 0.9})
    check("ingest: raw-format variant read stored", s == 201, b)
    s, b = req(p, "POST", "/suppressions", SUP, {"plate": "VIC309"})
    check("suppression: order_ref required", s == 400, b)
    s, b = req(p, "POST", "/suppressions", SUP,
               {"plate": "VIC309",
                "order_ref": "PO-2027-0117 (DEMO)"})
    check("suppression: placed with order reference", s == 201, b)
    check("suppression: near-match warning names the variant",
          "VIC 309" in b.get("warning_near_matches", []), b)
    s, b = req(p, "POST", "/suppressions", DET,
               {"plate": "VIC309", "order_ref": "PO-X"})
    check("suppression: detective cannot place", s == 403, b)
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "VIC309", "state": "AR", "cam": "CAM-04",
                "conf": 0.9})
    check("ingest: suppressed plate read stored silently",
          s == 201 and b["result"] == "stored", b)
    for user, label in ((PAT, "patrol"), (SUP, "supervisor"),
                        (DET, "detective")):
        s, b = req(p, "GET", "/search?plate=VIC309&case=2027-1040"
                   "&justification=check&tier=2", user)
        check("suppression: invisible in search to %s" % label,
              s == 200 and b["reads"] == [] and b["hits"] == [], b)
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "VIC309", "state": "AR", "category": "warrant",
                "case": "2027-1031"})
    check("suppression: hotlist-add refused", s == 403, b)
    kinds, _ = audit_kinds(p)
    check("suppression: conflict chained as SUPPRESSION_CONFLICT",
          "SUPPRESSION_CONFLICT" in kinds)
    # hot-listed AND suppressed: hits route to the supervisor queue
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "PRT208", "state": "AR",
                "category": "felony warrant", "case": "2027-1031"})
    assert s == 201, b
    s, b = req(p, "POST", "/suppressions", SUP,
               {"plate": "PRT208", "order_ref": "PO-2027-0131 (DEMO)"})
    assert s == 201, b
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "PRT208", "state": "AR", "cam": "CAM-06",
                "conf": 0.95})
    check("ingest: suppressed hot plate still alerts internally",
          s == 201 and b["result"] == "ALERT", b)
    prt_hit = b["hit_id"]
    s, b = req(p, "GET", "/hits", SUP)
    check("suppression: hit absent from /hits even for supervisor",
          s == 200 and all(h["id"] != prt_hit for h in b["hits"]), b)
    s, b = req(p, "GET", "/suppressed-hits", DET)
    check("suppressed-hits: detective refused", s == 403, b)
    s, b = req(p, "GET", "/suppressed-hits", SUP)
    check("suppressed-hits: supervisor sees the queued hit",
          s == 200 and any(h["id"] == prt_hit for h in b["hits"]), b)
    kinds, _ = audit_kinds(p)
    check("suppressed-hits: view chained", "SUPPRESSED_HITS_VIEW"
          in kinds)
    # two-key release
    s, b = req(p, "POST", "/suppressions/release", SUP,
               {"plate": "VIC309", "order_ref": "PO-2027-0117 (DEMO)"})
    check("suppression release: first supervisor requests",
          s == 200, b)
    s, b = req(p, "POST", "/suppressions/release", SUP,
               {"plate": "VIC309", "order_ref": "PO-2027-0117 (DEMO)"})
    check("suppression release: same supervisor cannot confirm",
          s == 403, b)
    s, b = req(p, "POST", "/suppressions/release", SUP2,
               {"plate": "VIC309", "order_ref": "PO-WRONG"})
    check("suppression release: wrong order ref refused", s == 400, b)
    s, b = req(p, "POST", "/suppressions/release", SUP2,
               {"plate": "VIC309", "order_ref": "PO-2027-0117 (DEMO)"})
    check("suppression release: second supervisor confirms",
          s == 200, b)
    s, b = req(p, "GET", "/search?plate=VIC309&case=2027-1040"
               "&justification=check&tier=2", PAT)
    check("suppression: released plate is searchable again",
          s == 200 and len(b["reads"]) == 1, b)
    # ---------- verify / outcomes / report (items 11, 29) ----------
    s, b = req(p, "POST", "/verify", DET,
               {"hit_id": hit1, "decision": "maybe",
                "case": "2027-1014"})
    check("verify: non-enum decision is 400", s == 400, b)
    s, b = req(p, "POST", "/verify", DET,
               {"hit_id": hit1, "decision": "CONFIRM",
                "case": "2027-1014"})
    check("verify: 'CONFIRM' confirms (case-insensitive enum)",
          s == 200 and b["result"] == "VERIFIED", b)
    s, b = req(p, "POST", "/verify", DET,
               {"hit_id": hit1, "decision": "confirm",
                "case": "2027-9999"})
    check("verify: invalid case refused (shared gate)", s == 403, b)
    s, b = req(p, "GET", "/report", AUD)
    check("report: prosecutions 'not yet reported' while unset",
          s == 200 and b["prosecutions"] == "not yet reported"
          and b["prosecutions_coverage"] == {"reported": 0, "total": 1},
          b.get("prosecutions_coverage"))
    check("report: per-list counts from outcomes",
          b["lists"]["Local agency list"]["confirmed_matches"] == 1, b)
    s, b = req(p, "POST", "/outcomes", DET,
               {"hit_id": hit1, "arrest": True, "prosecution": False})
    check("outcomes: prosecution set explicitly", s == 200, b)
    s, b = req(p, "GET", "/report", AUD)
    check("report: prosecutions becomes a count once reported",
          b["prosecutions"] == 0
          and b["prosecutions_coverage"]["reported"] == 1, b)
    check("report: arrest + combined counts present",
          b["arrests"] == 1
          and b["lists"]["Local agency list"]["arrests"] == 1, b)
    check("report: K8 tier3 block present with threshold state",
          "tier3" in b and b["tier3"]["rolling_3mo"]["threshold"] == 0.25
          and b["tier3"]["rolling_3mo"]["state"] in ("ok", "tripped"), b)
    # zero-match list still appears (from lists_checked)
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "ZZQ999", "state": "AR", "category": "test",
                "case": "2027-1001", "list_name": "State list"})
    assert s == 201, b
    req(p, "POST", "/reads", ING,
        {"plate": "ZZQ998", "state": "AR", "cam": "CAM-01",
         "conf": 0.9})
    s, b = req(p, "GET", "/report", AUD)
    check("report: zero-match list appears via lists_checked",
          "State list" in b["lists"]
          and b["lists"]["State list"]["confirmed_matches"] == 0, b)
    # snapshot compile + immutability
    s, b = req(p, "POST", "/report/compile", SUP,
               {"from": "", "to": "9999-12-31T23:59:59Z"})
    check("report: compile freezes a snapshot", s == 201, b)
    snap_id = b["snapshot_id"]
    snap_body = json.dumps(b["report"], sort_keys=True)
    req(p, "POST", "/reads", ING,
        {"plate": "RST417", "state": "AR", "cam": "CAM-03",
         "conf": 0.9})
    s, b = req(p, "GET", "/report?snapshot=%d" % snap_id, AUD)
    check("report: snapshot is immutable after new data",
          s == 200 and json.dumps(b, sort_keys=True) == snap_body, b)
    suite_a3(A, hit1)


def suite_a3(A, hit1):
    p = A.port
    # ---------- evidence lifecycle (items 9, 10) ----------
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "EVD100", "state": "AR", "category": "evidence",
                "case": "2027-1014"})
    assert s == 201, b
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "EVD100", "state": "AR", "cam": "CAM-01",
                "conf": 0.9})
    ev_hit = b["hit_id"]
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": ev_hit, "case_id": "2027-1014"})
    check("evidence: export of a PENDING hit refused", s == 409, b)
    req(p, "POST", "/verify", DET,
        {"hit_id": ev_hit, "decision": "confirm", "case": "2027-1014"})
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": ev_hit, "case_id": "2027-1023"})
    check("evidence: export under the wrong case refused",
          s == 403, b)
    s, b = req(p, "POST", "/evidence/release", SUP,
               {"hit_id": ev_hit, "prosecutor_signoff":
                {"name": "PA Demo", "date": "2027-01-05"}})
    check("evidence: release before export refused", s == 409, b)
    # a read 2h after the hit must fall OUTSIDE the +-1h bundle scope
    db = sqlite3.connect(A.db)
    db.execute("INSERT INTO reads(ts,cam,plate,state,conf) "
               "VALUES(?,?,?,?,?)",
               ((datetime.now(timezone.utc)
                 + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "CAM-01", "EVD100", "AR", 0.9))
    db.commit()
    db.close()
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": ev_hit, "case_id": "2027-1014"})
    check("evidence: verified export ok, window scope",
          s == 201 and b["scope"] == "window_1h", b)
    bundle = os.path.join(A.dir, "evidence", b["bundle"])
    reads_bundle = json.load(open(os.path.join(bundle, "reads.json")))
    check("evidence: bundle holds only the +-1h reads",
          len(reads_bundle) == 1, len(reads_bundle))
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": ev_hit, "case_id": "2027-1014",
                "expand": True})
    check("evidence: expand by detective refused", s == 403, b)
    s, b = req(p, "POST", "/evidence/export", SUP,
               {"hit_id": ev_hit, "case_id": "2027-1014",
                "expand": True})
    check("evidence: expand without reason refused", s == 400, b)
    s, b = req(p, "POST", "/evidence/export", SUP,
               {"hit_id": ev_hit, "case_id": "2027-1014",
                "expand": True, "reason": "pattern across days (DEMO)"})
    check("evidence: supervisor expand with reason ok",
          s == 201 and b["scope"] == "full", b)
    live_bundle = os.path.join(A.dir, "evidence", b["bundle"])
    reads_bundle = json.load(open(os.path.join(
        A.dir, "evidence", b["bundle"], "reads.json")))
    check("evidence: expanded bundle holds full history",
          len(reads_bundle) == 2, len(reads_bundle))
    s, b = req(p, "POST", "/evidence/destroy", SUP,
               {"hit_id": ev_hit})
    check("evidence: destroy before release refused", s == 409, b)
    # disposition path: post (detective) + confirm (different sup)
    s, b = req(p, "POST", "/evidence/disposition", DET,
               {"hit_id": ev_hit, "outcome": "no_charges",
                "by": "PA Demo", "date": "2027-01-06",
                "note": "declined (DEMO)"})
    check("evidence: disposition posted", s == 201, b)
    s, b = req(p, "POST", "/evidence/disposition/confirm", DET,
               {"hit_id": ev_hit})
    check("evidence: disposition confirm is supervisor-only",
          s == 403, b)
    s, b = req(p, "POST", "/evidence/disposition/confirm", SUP,
               {"hit_id": ev_hit})
    check("evidence: disposition confirmed by supervisor",
          s == 200, b)
    s, b = req(p, "POST", "/evidence/destroy", SUP,
               {"hit_id": ev_hit})
    check("evidence: destroy after confirmed disposition ok",
          s == 200, b)
    check("evidence: bundle files actually deleted",
          not os.path.exists(live_bundle), live_bundle)
    kinds, _ = audit_kinds(p)
    for kind in ("EVIDENCE_EXPORT", "EVIDENCE_DISPOSITION",
                 "EVIDENCE_DISPOSITION_CONFIRM", "EVIDENCE_DESTROY"):
        check("evidence: %s chained" % kind, kind in kinds)
    # ---------- holds (items 10, 18, 32) ----------
    s, b = req(p, "POST", "/holds", DET,
               {"scope": "case", "ref": "PATROL-9",
                "reason": "test"})
    check("holds: banned case refused (shared gate)", s == 403, b)
    s, b = req(p, "POST", "/holds", DET,
               {"scope": "case", "ref": "2027-1014",
                "reason": "litigation (DEMO)"})
    check("holds: placed with default review_by (+90d)",
          s == 201 and b.get("review_by", "")[:4]
          == str((datetime.now(timezone.utc)
                  + timedelta(days=90)).year), b)
    hold_id = b["hold_id"]
    s, b = req(p, "POST", "/holds/release", SUP,
               {"hold_id": hold_id})
    check("holds: release ok", s == 200, b)
    db = sqlite3.connect(A.db)
    db.execute("INSERT INTO holds(scope,ref,reason,placed_by,placed_ts,"
               "active,review_by) VALUES('case','2027-1023','old',"
               "'det.okafor',?,1,?)", (ago_iso(days=100),
                                        ago_iso(days=1)))
    db.commit()
    db.close()
    s, h = req(p, "GET", "/health")
    check("holds: overdue hold surfaces in /health",
          h["overdue_holds"] >= 1, h.get("overdue_holds"))
    s, b = req(p, "GET", "/report", AUD)
    check("holds: overdue hold surfaces in /report",
          b["overdue_holds"] >= 1, b.get("overdue_holds"))
    suite_a4(A)


def suite_a4(A):
    p = A.port
    # ---------- Tier 3 workflow (items 2, 19, 27, 28) ----------
    s, b = req(p, "POST", "/tier3/request", DET,
               {"case_id": "2027-1014", "why": "trace",
                "plate_fragment": "OLD111",
                "auth_basis": "Warrant W-1 (DEMO)",
                "basis_type": "warrant"})
    check("tier3: request accepted, nothing searched",
          s == 201 and "PENDING" in b["result"], b)
    rid_old = b["request_id"]
    s, b = req(p, "POST", "/tier3/request", DET,
               {"case_id": "2027-1014", "why": "trace",
                "plate_fragment": "OLD111"})
    check("tier3: request without auth_basis refused", s == 403, b)
    s, b = req(p, "POST", "/tier3/request", DET,
               {"case_id": "2027-1014", "why": "trace",
                "plate_fragment": "OL%",
                "auth_basis": "Warrant W-1 (DEMO)"})
    check("tier3: wildcard fragment refused", s == 400, b)
    s, b = req(p, "POST", "/tier3/request", SUP,
               {"case_id": "2027-1023", "why": "own request",
                "plate_fragment": "RST417",
                "auth_basis": "Court order C-1 (DEMO)",
                "basis_type": "court_order"})
    rid_own = b["request_id"]
    s, b = req(p, "POST", "/tier3/approve", SUP,
               {"request_id": rid_own})
    check("tier3: approving your own request refused", s == 403, b)
    s, b = req(p, "POST", "/tier3/approve", SUP2,
               {"request_id": rid_own})
    check("tier3: second key approves", s == 200
          and b["result"] == "EXECUTED", b)
    check("tier3: approve returns count + URL, not results",
          "results" not in b and "results_url" in b, b)
    s, b = req(p, "GET", "/tier3/results/%d" % rid_own, DET)
    check("tier3: results fenced to the requester", s == 403, b)
    s, b = req(p, "GET", "/tier3/results/%d" % rid_own, SUP)
    check("tier3: requester retrieves results", s == 200, b)
    kinds, entries = audit_kinds(p)
    check("tier3: retrieval chained as TIER3_RESULT_VIEW",
          "TIER3_RESULT_VIEW" in kinds)
    q3 = [e for e in entries if e["kind"] == "QUERY"
          and e["payload"].get("tier") == 3]
    check("tier3: QUERY entries carry plate_ref + result_count",
          q3 and all("result_count" in e["payload"]
                     and str(e["payload"].get("plate_ref", "")
                             ).startswith("pref:") for e in q3), q3[:1])
    # Tier 3 sees past the temporal wall
    s, b = req(p, "POST", "/tier3/approve", SUP, {"request_id": rid_old})
    assert s == 200, b
    s, b = req(p, "GET", "/tier3/results/%d" % rid_old, DET)
    check("temporal wall: Tier 3 sees the 25h-old read",
          s == 200 and len(b["results"]["reads"]) == 1, b)
    # approve re-runs the case gate: close the case, then approve
    s, b = req(p, "POST", "/tier3/request", DET,
               {"case_id": "2027-1052", "why": "trace",
                "plate_fragment": "RST417",
                "auth_basis": "Warrant W-2 (DEMO)",
                "basis_type": "warrant"})
    rid_closed = b["request_id"]
    write_cases(A.cases, [c for c in CASES if c != "2027-1052"])
    time.sleep(0.2)
    s, b = req(p, "POST", "/tier3/approve", SUP,
               {"request_id": rid_closed})
    check("tier3: approve re-runs case gate (closed case blocks)",
          s == 403, b)
    write_cases(A.cases)
    time.sleep(0.2)
    # pending visibility
    s, b = req(p, "POST", "/tier3/request", PAT,
               {"case_id": "2027-1023", "why": "patrol request",
                "plate_fragment": "RST417",
                "auth_basis": "Warrant W-3 (DEMO)",
                "basis_type": "warrant"})
    rid_pat = b["request_id"]
    s, b = req(p, "GET", "/tier3/pending", DET)
    mine = [r["id"] for r in b["pending"]]
    check("tier3: detective sees only own pending requests",
          rid_closed in mine and rid_pat not in mine, mine)
    s, b = req(p, "GET", "/tier3/pending", SUP)
    check("tier3: supervisor sees all pending",
          rid_pat in [r["id"] for r in b["pending"]], b)
    # emergency path
    s, b = req(p, "POST", "/tier3/emergency", SUP,
               {"case_id": "2027-1023", "why": "exigent",
                "plate_fragment": "RST417"})
    check("tier3: emergency without auth_basis refused", s == 403, b)
    s, b = req(p, "POST", "/tier3/emergency", SUP,
               {"case_id": "2027-1023", "why": "exigent",
                "plate_fragment": "RST417",
                "auth_basis": "exigent circumstances (DEMO)",
                "basis_type": "other"})
    check("tier3: emergency executes with basis", s == 200, b)
    rid_em = b["request_id"]
    s, b = req(p, "POST", "/tier3/review", AUD,
               {"request_id": rid_em, "finding": "ok"})
    check("tier3: bare 'ok' finding is 400", s == 400, b)
    s, b = req(p, "POST", "/tier3/review", SUP,
               {"request_id": rid_em, "finding": "justified"})
    check("tier3: user cannot review own emergency use", s == 403, b)
    s, b = req(p, "POST", "/tier3/review", AUD,
               {"request_id": rid_em, "finding": "justified",
                "note": "exigency documented (DEMO)"})
    check("tier3: auditor closes review with enum finding",
          s == 200, b)
    # 72h unreviewed-emergency lockout
    db = sqlite3.connect(A.db)
    db.execute("INSERT INTO tier3_requests(requester,case_no,why,"
               "plate_fragment,auth_basis,basis_type,status,created_ts,"
               "emergency,needs_review) VALUES('capt.voss',"
               "'2027-1023','stale','RST417','x','other','EMERGENCY',"
               "?,1,1)", (ago_iso(hours=73),))
    db.commit()
    db.close()
    s, b = req(p, "POST", "/tier3/emergency", SUP2,
               {"case_id": "2027-1023", "why": "exigent",
                "plate_fragment": "RST417",
                "auth_basis": "exigent (DEMO)", "basis_type": "other"})
    check("tier3: unreviewed emergency >72h locks the path",
          s == 403, b)
    suite_a5(A)


def suite_a5(A):
    p = A.port
    # ---------- hotlist expiry (item 12) ----------
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "EXP100", "state": "AR", "category": "expired",
                "case": "2027-1001", "expires": ago_iso(hours=1)})
    assert s == 201, b
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "EXP100", "state": "AR", "cam": "CAM-01",
                "conf": 0.9})
    check("expiry: expired entry produces no alert",
          s == 201 and b["result"] == "stored", b)
    s, b = req(p, "GET", "/hotlist", DET)
    check("expiry: entry auto-deactivated",
          all(e["plate"] != "EXP100" for e in b["hotlist"]), b)
    kinds, _ = audit_kinds(p)
    check("expiry: HOTLIST_EXPIRED chained", "HOTLIST_EXPIRED" in kinds)
    # ---------- skew / backfill (item 16) ----------
    future = (datetime.now(timezone.utc)
              + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "SKW100", "state": "AR", "cam": "CAM-09",
                "conf": 0.9, "ts": future})
    check("skew: future cam_ts reported on the read",
          s == 201 and b.get("clock_skew_s") is not None
          and b["clock_skew_s"] < -5, b)
    kinds, _ = audit_kinds(p)
    check("skew: CLOCK_SKEW chained for future cam_ts",
          "CLOCK_SKEW" in kinds)
    old1 = ago_iso(minutes=10)
    old2 = ago_iso(minutes=20)
    for ts in (old1, old2):
        req(p, "POST", "/reads", ING,
            {"plate": "BFL100", "state": "AR", "cam": "CAM-08",
             "conf": 0.9, "ts": ts})
    time.sleep(1.6)
    req(p, "GET", "/health")  # idle flush runs on health checks
    kinds, entries = audit_kinds(p)
    bf = [e for e in entries if e["kind"] == "BACKFILL"
          and e["payload"].get("cam") == "CAM-08"]
    check("backfill: two backfills aggregate to one entry per cam/hour",
          len(bf) == 1 and bf[0]["payload"].get("count") == 2, bf)
    db = sqlite3.connect(A.db)
    row = db.execute("SELECT skew_s FROM reads WHERE plate='BFL100' "
                     "ORDER BY id LIMIT 1").fetchone()
    db.close()
    check("backfill: skew_s stored on the read row",
          row and row[0] and row[0] > 300, row)
    # ---------- body cap (item 13) ----------
    s, b = req(p, "POST", "/reads", ING, body=b"x" * (1024 * 1024 + 1))
    check("hardening: body over 1MB refused", s == 413, s)
    # ---------- rotation endpoints (item 35) ----------
    members = ["agency-a", "agency-b", "agency-c", "agency-d"]
    sched = rotation_mod.build_schedule(members, "2027-01-01", 90)
    tampered = json.loads(json.dumps(sched))
    tampered["rounds"][0]["pairs"][0] = ["agency-d", "agency-a"]
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-01", "schedule": tampered})
    check("rotation: tampered schedule rejected", s == 400, b)
    kinds, _ = audit_kinds(p)
    check("rotation: rejection chained as ROTATION_REJECTED",
          "ROTATION_REJECTED" in kinds)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-01", "schedule": sched})
    check("rotation: valid schedule published", s == 201, b)
    kinds, _ = audit_kinds(p)
    check("rotation: publication chained as ROTATION_PUBLISHED",
          "ROTATION_PUBLISHED" in kinds)
    s, b = req(p, "GET", "/compact/rotation/status", SUP)
    check("rotation: status view answers",
          s == 200 and b["members_count"] == 4, b)
    # ---------- config staleness (item 15) ----------
    with open(A.cases, "w") as f:
        f.write("{ this is not json")
    time.sleep(0.2)
    req(p, "GET", "/health")
    req(p, "GET", "/stats", DET)  # any authed request trips the reload
    s, h = req(p, "GET", "/health")
    check("config: failed reload degrades health (CONFIG_STALE)",
          h["config_stale"] is True and h["ok"] is False, h)
    kinds, _ = audit_kinds(p)
    check("config: CONFIG_STALE chained", "CONFIG_STALE" in kinds)
    write_cases(A.cases)
    time.sleep(0.2)
    req(p, "GET", "/stats", DET)
    s, h = req(p, "GET", "/health")
    check("config: clean reload clears staleness",
          h["config_stale"] is False, h)


def suite_scripts(A):
    # ---------- rotation mathematics (item 35) ----------
    for n in (3, 4, 5):
        members = ["agency-%s" % c for c in "abcde"[:n]]
        sched = rotation_mod.build_schedule(members, "2027-01-01", 90)
        pairs = [tuple(pr) for r in sched["rounds"] for pr in r["pairs"]]
        expect = {(a, b) for a in members for b in members if a != b}
        mutual = any((b, a) in [tuple(x) for x in r["pairs"]]
                     for r in sched["rounds"] for a, b in
                     [tuple(x) for x in r["pairs"]])
        check("rotation N=%d: every ordered pair exactly once" % n,
              set(pairs) == expect and len(pairs) == len(expect),
              "%d pairs" % len(pairs))
        check("rotation N=%d: no same-round mutual pair" % n,
              not mutual)
        if n % 2 == 1:
            witnesses = [r["witness"] for r in sched["rounds"]]
            check("rotation N=%d: bye rotates as witness" % n,
                  all(witnesses) and set(witnesses) == set(members),
                  witnesses)
        again = rotation_mod.build_schedule(members, "2027-01-01", 90)
        check("rotation N=%d: seed recompute is byte-identical" % n,
              rotation_mod.canonical(again)
              == rotation_mod.canonical(sched))
    s2 = rotation_mod.build_schedule(["agency-a", "agency-b"],
                                     "2027-01-01", 90)
    check("rotation N=2: static pairing, stated plainly",
          s2["mode"] == "static" and "STATIC" in s2["note"])
    s1 = rotation_mod.build_schedule(["agency-a"], "2027-01-01", 90)
    check("rotation N=1: inactive", s1["mode"] == "inactive")
    # ---------- chain atomicity: 200 appends, two processes ----------
    cdb = os.path.join(WORK, "conc.db")
    worker = os.path.join(WORK, "worker.py")
    with open(worker, "w") as f:
        f.write("import sys\nsys.path.insert(0, %r)\nimport sentinel\n"
                "c = sentinel.Chain(sys.argv[1])\n"
                "for i in range(100):\n"
                "    c.append('TEST', {'worker': sys.argv[2], 'i': i})\n"
                % ROOT)
    procs = [subprocess.Popen([sys.executable, worker, cdb, w])
             for w in ("w1", "w2")]
    for pr in procs:
        pr.wait(timeout=120)
    sys.path.insert(0, ROOT)
    import sentinel as sentinel_mod
    chain = sentinel_mod.Chain(cdb)
    check("chain: 200 concurrent appends from two processes verify",
          chain.verify()["ok"] is True and chain.count() == 200,
          chain.count())
    # ---------- chain scrubber (item 26) ----------
    try:
        chain.append("TEST", {"plate": "ABC123"})
        scrub_blocked = False
    except sentinel_mod.ChainScrubError:
        scrub_blocked = True
    kinds = [e["kind"] for e in chain.entries(5)]
    check("chain: raw plate text in a payload is scrub-blocked",
          scrub_blocked and "CHAIN_SCRUB_BLOCKED" in kinds, kinds)
    e = chain.append("TEST", {"plate_ref": "pref:" + "a" * 64,
                              "case": "2027-1014", "cam": "CAM-01",
                              "count": 3})
    check("chain: coded payloads (refs, cases, cameras) pass",
          e["kind"] == "TEST")
    # ---------- sink spool + recovery (item 6) ----------
    sink_dir = os.path.join(WORK, "sinkdir")
    sink_path = os.path.join(sink_dir, "sink.jsonl")
    sdb = os.path.join(WORK, "sink.db")
    os.makedirs(sink_dir)
    os.makedirs(sink_path)  # outage: the sink path is unusable (a
    # directory sits where the file belongs) while the spool beside
    # it stays writable — the mount-failure shape the spool exists for
    os.environ["NOCTUA_SENTINEL_SINK"] = sink_path
    schain = sentinel_mod.Chain(sdb)
    for i in range(3):
        schain.append("TEST", {"i": i})
    st = schain.sink_status()
    check("sink: outage spools entries, status shows the failure",
          st["spooled"] == 3 and st["ok"] is False, st)
    os.rmdir(sink_path)  # the sink comes back
    schain.append("TEST", {"i": 3})
    st = schain.sink_status()
    lines = [json.loads(l) for l in open(sink_path) if l.strip()]
    hashes = [schain.hash_at_seq(i) for i in range(1, 5)]
    check("sink: recovery drains the spool in order, byte-identical",
          st["spooled"] == 0 and st["ok"] is True
          and [l["hash"] for l in lines] == hashes, st)
    os.environ.pop("NOCTUA_SENTINEL_SINK")
    # ---------- startup anchor (item 7) ----------
    env = dict(os.environ)
    env.update({"NOCTUA_DB": A.db, "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "checkpoint.py")],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    check("anchor: checkpoint.py publishes a checkpoint",
          r.returncode == 0 and os.path.exists(
              A.db + ".checkpoints.jsonl"), r.stderr[-200:])
    # Simulate a history rewrite: alter the newest entry's payload
    # AND its hash (a tamper that keeps the chain internally
    # consistent but changes the root the checkpoint witnessed).
    import hashlib as _hl
    _db = sqlite3.connect(A.db)
    _seq, _payload, _prev = _db.execute(
        "SELECT seq, payload, prev FROM audit ORDER BY seq DESC "
        "LIMIT 1").fetchone()
    _new_payload = _payload.replace('"event"', '"eventx"', 1)
    if _new_payload == _payload:
        _new_payload = _payload + " "
    _new_hash = _hl.sha256((_prev + "|" + _new_payload).encode()
                           ).hexdigest()
    _db.execute("UPDATE audit SET payload=?, hash=? WHERE seq=?",
                (_new_payload, _new_hash, _seq))
    _db.commit()
    _db.close()
    A.start()
    try:
        s, h = req(A.port, "GET", "/health")
        check("anchor: mismatch visible in /health after restart",
              h["anchor_mismatch"] is True, h.get("anchor_mismatch"))
        kinds, _ = audit_kinds(A.port)
        check("anchor: STARTUP_ANCHOR_MISMATCH chained",
              "STARTUP_ANCHOR_MISMATCH" in kinds)
        s, b = req(A.port, "POST", "/audit/anchor-accept", SUP, {})
        check("anchor: supervisor records acceptance", s == 200, b)
        s, h = req(A.port, "GET", "/health")
        check("anchor: still mismatched until the auditor confirms",
              h["anchor_mismatch"] is True)
        s, b = req(A.port, "POST", "/audit/anchor-accept", AUD, {})
        check("anchor: auditor confirms (two-key)", s == 200, b)
        s, h = req(A.port, "GET", "/health")
        check("anchor: mismatch cleared after two-key accept",
              h["anchor_mismatch"] is False)
    finally:
        A.stop()


def suite_compact(A, B):
    p = B.port
    # B holds data worth sharing
    req(p, "POST", "/hotlist", DET,
        {"plate": "RST417", "state": "AR", "category": "stolen vehicle",
         "case": "2027-1014"})
    req(p, "POST", "/reads", ING,
        {"plate": "RST417", "state": "AR", "cam": "CAM-01",
         "conf": 0.97})
    s, b = req(p, "POST", "/compact/partners", SUP,
               {"agency": "agency-a", "endpoint": A.url,
                "agreement_ref": "COMPACT-DEMO-1"})
    check("compact: partner registered", s == 201, b)
    share_body = {"agency": "agency-a", "case_ref": "B-2027-1",
                  "why": "regional stolen-vehicle check (DEMO)",
                  "plate_fragment": "RST417", "tier": 2}
    s, b = req(p, "POST", "/share/query", "agency-a", share_body)
    check("share: blocked with no audit legs (names cross_audit_ok)",
          s == 403 and b.get("missing") == "cross_audit_ok", b)
    kinds, _ = audit_kinds(p)
    check("share: refusal chained as SHARE_BLOCKED",
          "SHARE_BLOCKED" in kinds)
    s, b = req(p, "POST", "/compact/audit-result", JOB,
               {"agency": "agency-a", "ok": True,
                "detail": "audit passed (test)"})
    check("compact: our audit of them recorded", s == 201, b)
    s, b = req(p, "POST", "/share/query", "agency-a", share_body)
    check("share: blocked with one leg (names checkpoint_receipt)",
          s == 403 and b.get("missing") == "checkpoint_receipt", b)
    env = dict(os.environ)
    env.update({"NOCTUA_DB": B.db, "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "checkpoint.py")],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    s, b = req(p, "GET", "/compact/checkpoint", AUD)
    cp = b["checkpoint"]
    s, b = req(p, "POST", "/compact/checkpoint-receipt", DET,
               {"agency": "agency-a", "root": cp["root"],
                "entries": cp["entries"], "sig": cp["sig"]})
    check("compact: receipt from a non-partner account refused",
          s == 403, b)
    s, b = req(p, "POST", "/compact/checkpoint-receipt", "agency-a",
               {"agency": "agency-a", "root": "0" * 64, "entries": 1,
                "sig": "x"})
    check("compact: receipt for an unpublished checkpoint rejected",
          s == 400, b)
    s, b = req(p, "POST", "/compact/checkpoint-receipt", "agency-a",
               {"agency": "agency-a", "root": cp["root"],
                "entries": cp["entries"], "sig": cp["sig"]})
    check("compact: genuine receipt recorded", s == 201, b)
    s, b = req(p, "POST", "/share/query", "agency-a", share_body)
    check("share: allowed when both legs are fresh",
          s == 200 and len(b["results"]["reads"]) == 1, b)
    kinds, entries = audit_kinds(p)
    outs = [e for e in entries if e["kind"] == "SHARE_OUT"]
    check("share: SHARE_OUT chained with plate_ref + count",
          outs and outs[0]["payload"].get("result_count") == 2
          and str(outs[0]["payload"].get("plate_ref", "")
                  ).startswith("pref:"), outs[:1])
    s, b = req(p, "POST", "/compact/suspend", SUP,
               {"agency": "agency-a"})
    check("compact: suspension recorded", s == 200, b)
    s, b = req(p, "POST", "/share/query", "agency-a", share_body)
    check("share: suspension blocks immediately",
          s == 403 and b.get("missing") == "partner_inactive", b)
    req(p, "POST", "/compact/reinstate", SUP, {"agency": "agency-a"})
    # ---------- sentinel_audit tool (item 21) ----------
    for job in ("retention", "checkpoint", "hotlist_sync", "backup"):
        req(p, "POST", "/heartbeat", JOB,
            {"job": job, "ok": True, "detail": "test"})
    env2 = dict(os.environ)
    env2["SENTINEL_AUDIT_KEY"] = "auditor-signing-key"
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "sentinel_audit.py"),
         "--url", B.url, "--user", AUD, "--key", KEYS[AUD]],
        env=env2, capture_output=True, text=True, timeout=120)
    try:
        rep = json.loads(r.stdout)
    except ValueError:
        rep = {}
    names = {c["name"]: c["status"] for c in rep.get("checks", [])}
    check("sentinel_audit URL mode: signed report, chain checks ok",
          rep.get("sig") is not None
          and names.get("chain integrity (independent)") == "ok"
          and names.get("anchor consistency") == "ok", names)
    check("sentinel_audit URL mode: exit 1 (warnings only)",
          r.returncode == 1, r.returncode)
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "sentinel_audit.py"),
         "--db", B.db, "--checkpoints", B.db + ".checkpoints.jsonl",
         "--audit-key", AUDIT_KEY],
        env=env2, capture_output=True, text=True, timeout=120)
    try:
        rep = json.loads(r.stdout)
    except ValueError:
        rep = {}
    names = {c["name"]: c["status"] for c in rep.get("checks", [])}
    check("sentinel_audit DB mode: clean audit exits 0",
          r.returncode == 0
          and all(v == "ok" for v in names.values()), names)
    # ---------- compact.py end-to-end ----------
    req(A.port, "POST", "/compact/partners", SUP,
        {"agency": "agency-b", "endpoint": B.url,
         "agreement_ref": "COMPACT-DEMO-1"})
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "compact.py"),
         "--partner-url", B.url, "--partner-user", AUD,
         "--partner-key", KEYS[AUD], "--agency", "agency-b",
         "--janus", A.url, "--jobs-user", JOB,
         "--jobs-key", KEYS[JOB], "--our-agency", "agency-a",
         "--receipt-user", "agency-a",
         "--receipt-key", KEYS["agency-a"]],
        capture_output=True, text=True, timeout=120)
    check("compact.py: cross-audit run succeeds", r.returncode == 0,
          r.stdout[-200:] + r.stderr[-200:])
    kinds, entries = audit_kinds(A.port)
    oks = [e for e in entries if e["kind"] == "CROSS_AUDIT_OK"
           and e["payload"].get("agency") == "agency-b"]
    check("compact.py: CROSS_AUDIT_OK chained on our side",
          len(oks) >= 1, oks[:1])


def suite_keyloss():
    C = Instance("c", 18096, audit_key=None, key_file=True)
    C.start()
    try:
        req(C.port, "POST", "/reads", ING,
            {"plate": "KEY100", "state": "AR", "cam": "CAM-01",
             "conf": 0.9})
        key_file = C.db + ".audit_key"
        check("key: key file created on first boot",
              os.path.exists(key_file))
        if os.path.exists(key_file):
            mode = os.stat(key_file).st_mode & 0o777
            check("key: key file is 0600 (no TOCTOU window)",
                  mode == 0o600, oct(mode))
    finally:
        C.stop()
    os.remove(C.db + ".audit_key")
    C.start()
    try:
        s, h = req(C.port, "GET", "/health")
        check("key loss: Janus starts LOCKED, /health says key_missing",
              s == 200 and h.get("key_missing") is True
              and h["ok"] is False, h)
        s, b = req(C.port, "GET", "/stats", DET)
        check("key loss: data endpoints refuse (503), no silent mint",
              s == 503, b)
        check("key loss: no new key file was minted",
              not os.path.exists(C.db + ".audit_key"))
    finally:
        C.stop()


def suite_retention():
    """Item 20 + the brief's named test: after the retention purge,
    the statutory report still shows correct per-list counts (they
    derive from outcomes, which retention never deletes inside the
    18-month window), old reads are gone, case_searches rows are
    purged, and old tier3 fragments are scrubbed to their refs."""
    E = Instance("ret", 18095)
    E.start()
    try:
        p = E.port
        req(p, "POST", "/hotlist", DET,
            {"plate": "RET100", "state": "AR", "category": "stolen",
             "case": "2027-1014"})
        s, b = req(p, "POST", "/reads", ING,
                   {"plate": "RET100", "state": "AR", "cam": "CAM-01",
                    "conf": 0.9})
        h1 = b["hit_id"]
        s, b = req(p, "POST", "/reads", ING,
                   {"plate": "RET100", "state": "AR", "cam": "CAM-02",
                    "conf": 0.9})
        h2 = b["hit_id"]
        req(p, "POST", "/verify", DET,
            {"hit_id": h1, "decision": "confirm", "case": "2027-1014"})
        req(p, "POST", "/verify", DET,
            {"hit_id": h2, "decision": "reject", "case": "2027-1014"})
        db = sqlite3.connect(E.db)
        db.execute("INSERT INTO reads(ts,cam,plate,state,conf) "
                   "VALUES(?,?,?,?,?)",
                   (ago_iso(days=20), "CAM-01", "OLD999", "AR", 0.9))
        db.execute("INSERT INTO case_searches(case_no,day,frag) "
                   "VALUES('2027-1014',?, 'OLD999')",
                   (ago_iso(days=20)[:10],))
        db.execute("INSERT INTO tier3_requests(requester,case_no,why,"
                   "plate_fragment,auth_basis,basis_type,status,"
                   "created_ts) VALUES('det.okafor','2027-1014','x',"
                   "'RST417','w','warrant','EXECUTED',?)",
                   (ago_iso(days=20),))
        db.commit()
        db.close()
        env = dict(os.environ)
        env.update({"NOCTUA_DB": E.db, "NOCTUA_JANUS": E.url,
                    "NOCTUA_JOBS_USER": JOB, "NOCTUA_JOBS_KEY": KEYS[JOB],
                    "NOCTUA_AUDIT_KEY": AUDIT_KEY})
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "retention.py")],
            env=env, capture_output=True, text=True, timeout=120)
        check("retention: job runs clean", r.returncode == 0,
              r.stdout[-200:] + r.stderr[-300:])
        db = sqlite3.connect(E.db)
        old_reads = db.execute("SELECT COUNT(*) FROM reads WHERE "
                               "plate='OLD999'").fetchone()[0]
        old_cs = db.execute("SELECT COUNT(*) FROM case_searches"
                            ).fetchone()[0]
        frag = db.execute("SELECT plate_fragment FROM tier3_requests"
                          ).fetchone()[0]
        db.close()
        check("retention: reads past 14 days deleted", old_reads == 0)
        check("retention: case_searches past 14 days purged",
              old_cs == 0)
        check("retention: tier3 fragment scrubbed to its frag_ref",
              frag.startswith("pref:"), frag)
        s, b = req(p, "GET", "/report", AUD)
        lst = b["lists"]["Local agency list"]
        check("retention: report counts survive the purge (outcomes)",
              lst["confirmed_matches"] == 1
              and lst["non_corresponding"] == 1, lst)
        s, h = req(p, "GET", "/health")
        check("retention: heartbeat landed (job no longer overdue)",
              h["jobs"]["retention"]["ok"] is True
              and h["jobs"]["retention"]["overdue"] is False,
              h["jobs"]["retention"])
    finally:
        E.stop()


def suite_demo():
    D = Instance("demo", 18097)
    # the seeder writes its own users.json and refuses foreign users —
    # give the instance the demo-only user set from the start
    users = [{"user": u, "role": ROLES[u], "key_sha256": sha(KEYS[u])}
             for u in (DET, PAT, SUP, SUP2, AUD, ING, JOB)]
    with open(D.users, "w") as f:
        json.dump(users, f, indent=1)
    D.start()
    try:
        env = dict(os.environ)
        env.update({"NOCTUA_DB": D.db, "NOCTUA_USERS": D.users,
                    "NOCTUA_CASES": D.cases,
                    "NOCTUA_JANUS_URL": D.url})
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "demo", "seed_demo.py")],
            env=env, capture_output=True, text=True, timeout=300)
        check("demo: seed_demo completes against 1.1",
              r.returncode == 0 and "DEMO READY" in r.stdout,
              r.stdout[-300:] + r.stderr[-300:])
        s, stats = req(D.port, "GET", "/stats", DET)
        check("demo: totals match the walkthrough (9 hits, 7 pending, "
              "2 suppressed)", s == 200 and stats["hits"] == 9
              and stats["pending"] == 7
              and stats["suppressed_pending"] == 2, stats)
        s, b = req(D.port, "GET", "/suppressed-hits", SUP)
        check("demo: suppressed queue holds the two PRT208 hits",
              s == 200 and len(b["hits"]) == 2, b)
        s, b = req(D.port, "GET", "/search?plate=VIC309&case=2027-1040"
                   "&justification=demo+check&tier=2", SUP)
        check("demo: VIC309 invisible in search to a supervisor",
              s == 200 and b["reads"] == [], b)
    finally:
        D.stop()


if __name__ == "__main__":
    sys.exit(main())
