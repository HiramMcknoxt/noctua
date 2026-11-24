#!/usr/bin/env python3
"""NOCTUA Janus 1.2 live test suite.

Spins up scratch Janus instances on loopback ports with throwaway
databases and exercises every council-round-3 fix (S1-S18) over
HTTP, plus the standalone scripts (sentinel concurrency/scrubber/
sink, checkpoint + witness + anchor, backup/restore, rotation,
sentinel_audit, compact, bridge, provision, hotlist_sync) and the
demo seed.

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
sys.path.insert(0, ROOT)
sys.path.insert(0, SCRIPTS)
import sentinel as sentinel_mod  # noqa: E402
import rotation as rotation_mod  # noqa: E402

WORK = tempfile.mkdtemp(prefix="noctua12-tests-")
AUDIT_KEY = "test-audit-key-0123456789abcdef"

KEYS = {
    "det.okafor": "DEMO-KEY-DETECTIVE",
    "ofc.chen": "DEMO-KEY-PATROL",
    "sgt.reyes": "DEMO-KEY-SUPERVISOR",
    "capt.voss": "DEMO-KEY-SUPERVISOR2",
    "auditor.external": "DEMO-KEY-AUDITOR",
    "ca.external": "DEMO-KEY-CHAINAUDITOR",
    "ingest.local": "DEMO-KEY-INGEST",
    "jobs.local": "DEMO-KEY-JOBS",
    "agency-a": "KEY-PARTNER-A",
    "agency-b": "KEY-PARTNER-B",
}
ROLES = {
    "det.okafor": "detective", "ofc.chen": "patrol",
    "sgt.reyes": "supervisor", "capt.voss": "supervisor",
    "auditor.external": "auditor", "ca.external": "chain_auditor",
    "ingest.local": "ingest", "jobs.local": "jobs",
    "agency-a": "partner", "agency-b": "partner",
}
CASES = ["2027-1001", "2027-1014", "2027-1023", "2027-1031",
         "2027-1040", "2027-1052"]
CAMERAS = ["CAM-%02d" % i for i in range(1, 10)] + ["CAM-101"]
JOBS = ("retention", "checkpoint", "hotlist_sync", "backup", "witness")

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


def write_cameras(path, cams=CAMERAS):
    with open(path, "w") as f:
        json.dump(cams, f)


class Instance:
    def __init__(self, name, port, audit_key=AUDIT_KEY, env_extra=None,
                 key_file=False):
        self.dir = os.path.join(WORK, name)
        os.makedirs(self.dir)
        self.port = port
        self.db = os.path.join(self.dir, "janus.db")
        self.users = os.path.join(self.dir, "users.json")
        self.cases = os.path.join(self.dir, "cases.json")
        self.cameras = os.path.join(self.dir, "cameras.json")
        write_users(self.users)
        write_cases(self.cases)
        write_cameras(self.cameras)
        self.env = dict(os.environ)
        self.env.update({
            "NOCTUA_DB": self.db, "NOCTUA_USERS": self.users,
            "NOCTUA_CASES": self.cases, "NOCTUA_CAMERAS": self.cameras,
            "NOCTUA_PORT": str(port),
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
                s, _b = req(self.port, "GET", "/ping")
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


def health(port, user="sgt.reyes"):
    s, b = req(port, "GET", "/health", user)
    assert s == 200, b
    return b


def audit_kinds(port, limit=1000):
    s, b = req(port, "GET", "/audit?limit=%d" % limit, "auditor.external")
    assert s == 200, b
    return [e["kind"] for e in b["entries"]], b["entries"]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ago_iso(**kw):
    return (datetime.now(timezone.utc)
            - timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


def pub_pem(db_path):
    return open(db_path + ".signing_pub.pem").read()


def sign(db_path, obj):
    return sentinel_mod.sign_bytes(
        db_path + ".signing_key.pem",
        sentinel_mod.canonical_bytes(obj))


def post_audit_result(port, db_path, agency, ok, checks=None):
    """A signed Compact audit report, as compact.py posts it."""
    report = {"agency": agency, "ok": ok,
              "ts": sentinel_mod.now_iso(), "checks": checks or {}}
    return req(port, "POST", "/compact/audit-result", AUD,
               {"agency": agency, "report": report,
                "report_sig": sign(db_path, report)})


def post_receipt(port, from_db, agency, cp):
    """A signed checkpoint receipt, as a partner's compact.py posts it."""
    payload = {"agency": agency, "checkpoint_ts": cp["ts"],
               "entries": cp["entries"], "root": cp["root"]}
    return req(port, "POST", "/compact/checkpoint-receipt", agency,
               {"agency": agency, "checkpoint_root": cp["root"],
                "checkpoint_entries": cp["entries"],
                "checkpoint_ts": cp["ts"],
                "signature": sign(from_db, payload)})


def run_checkpoint(db_path, url=None):
    env = dict(os.environ)
    env.update({"NOCTUA_DB": db_path, "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    if url:
        env.update({"NOCTUA_JANUS_URL": url, "NOCTUA_JOBS_USER": JOB,
                    "NOCTUA_JOBS_KEY": KEYS[JOB]})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "checkpoint.py")],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    lines = [l for l in r.stdout.splitlines() if l.startswith("{")]
    assert len(lines) == 1, r.stdout
    return json.loads(lines[0])


DET, PAT, SUP, SUP2, AUD, CA, ING, JOB = (
    "det.okafor", "ofc.chen", "sgt.reyes", "capt.voss",
    "auditor.external", "ca.external", "ingest.local", "jobs.local")


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
    suite_p121()
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
    # ---------- health truth (S5) ----------
    s, b = req(p, "GET", "/ping")
    check("S5 ping: unauthenticated liveness answers alive only",
          s == 200 and b == {"alive": True}, b)
    s, b = req(p, "GET", "/health")
    check("S5 health: unauthenticated /health refused",
          s == 401, s)
    h = health(p)
    check("health: fresh instance is degraded (jobs never reported)",
          h["ok"] is False and len(h["degraded"]["jobs_overdue"]) == 5,
          h["degraded"])
    check("health: exposes retention days + tier2 window + registry",
          h["retention_days"] == 14 and h["tier2_window_hours"] == 24
          and h["registry_version"] == "1.2.1", h)
    check("S5 health: registered camera that never reported is "
          "named never_reported",
          h["cameras"]["CAM-101"]["status"] == "never_reported",
          h["cameras"].get("CAM-101"))
    for job in JOBS:
        s, b = req(p, "POST", "/heartbeat", JOB,
                   {"job": job, "ok": True, "detail": "test"})
        assert s == 200, b
    h = health(p)
    check("health: ok:true once all five jobs report ok",
          h["ok"] is True, h)
    # alert_check against the healthy instance + a dead port (S5)
    env = dict(os.environ)
    env.update({"NOCTUA_JANUS_URL": A.url, "NOCTUA_JOBS_USER": JOB,
                "NOCTUA_JOBS_KEY": KEYS[JOB]})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "alert_check.py")],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    check("S5 alert_check: healthy instance exits 0",
          r.returncode == 0, r.stdout + r.stderr)
    env["NOCTUA_JANUS_URL"] = "http://127.0.0.1:19999"
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "alert_check.py")],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    check("S5 alert_check: dead Janus exits 1 naming unreachability",
          r.returncode == 1 and "unreachable" in r.stdout, r.stdout)
    s, b = req(p, "POST", "/heartbeat", JOB,
               {"job": "backup", "detail": "no ok field"})
    check("heartbeat: missing ok recorded as failure",
          s == 200 and b["ok"] is False, b)
    h = health(p)
    check("health: missing-ok heartbeat degrades immediately",
          h["ok"] is False and h["jobs"]["backup"]["ok"] is False)
    s, b = req(p, "POST", "/heartbeat", JOB,
               {"job": "backup", "ok": False, "detail": "disk full"})
    h = health(p)
    check("health: ok:false heartbeat degrades immediately",
          h["ok"] is False and h["jobs"]["backup"]["status"]
          == "reported failure")
    req(p, "POST", "/heartbeat", JOB,
        {"job": "backup", "ok": True, "detail": "recovered"})
    # ---------- service-role walls ----------
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
    kinds, entries = audit_kinds(p)
    check("auth: failed attempt chained as AUTH_FAIL",
          "AUTH_FAIL" in kinds)
    af = [e for e in entries if e["kind"] == "AUTH_FAIL"]
    check("S18 AUTH_FAIL chains no raw username (hashed + counted)",
          af and all("user_hash" in e["fields"]
                     and "det.okafor" not in json.dumps(e["fields"])
                     for e in af), af[:1])
    s, b = req(p, "GET", "/audit?limit=5000", AUD)
    check("P13 audit: limit >1000 refused with 400 (1.2 clamped "
          "silently; SQLite LIMIT -1 was the whole chain)",
          s == 400, b)
    s, b = req(p, "GET", "/audit?limit=-1", AUD)
    check("P13 audit: negative limit refused with 400", s == 400, b)
    s, b = req(p, "GET", "/audit?limit=abc", AUD)
    check("P13 audit: non-integer limit refused with 400",
          s == 400, b)
    s, b = req(p, "GET", "/audit?limit=1000", AUD)
    check("audit: limit=1000 still served",
          s == 200 and len(b["entries"]) <= 1000,
          len(b.get("entries", [])))
    # ---------- hotlist, ingest, temporal wall ----------
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "RST417", "state": "AR",
                "category": "stolen vehicle", "case": "2027-1014"})
    check("hotlist: add ok", s == 201, b)
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "RST417", "state": "AR", "category": "x",
                "case": "PATROL-7"})
    check("hotlist: banned case refused (shared gate)", s == 403, b)
    s, b = req(p, "POST", "/hotlist", DET,
               {"plate": "QQQ111", "state": "AR", "category": "x",
                "case": "2027-1014", "list_name": "Unregistered list"})
    check("S14 hotlist: unregistered list_name refused",
          s == 400, b)
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "RST417", "state": "AR", "cam": "CAM-01",
                "conf": 0.97})
    check("ingest: hot plate alerts", s == 201
          and b["result"] == "ALERT", b)
    hit1 = b["hit_id"]
    # S18: CAM-101 — a camera id the 1.1 scrubber would have eaten —
    # works end to end: ingest -> alert -> chain, no 500.
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "RST417", "state": "AR", "cam": "CAM-101",
                "conf": 0.9})
    check("S18 CAM-101 camera works end to end (ingest -> ALERT)",
          s == 201 and b["result"] == "ALERT", b)
    kinds, entries = audit_kinds(p)
    alerts = [e for e in entries if e["kind"] == "ALERT"]
    check("S18 CAM-101: ALERT chain entry carries the camera id "
          "verbatim (scrubber-exempt field)",
          any(e["fields"].get("cam") == "CAM-101" for e in alerts),
          alerts[:2])
    # S4: ingest honesty — no fabricated state/conf; dedupe on event id
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "HON100", "cam": "CAM-02",
                "event_id": "evt-hon-1"})
    check("S4 ingest: read without state/conf stored", s == 201, b)
    hon_id = b["read_id"]
    db = sqlite3.connect(A.db)
    row = db.execute("SELECT state, conf FROM reads WHERE id=?",
                     (hon_id,)).fetchone()
    check("S4 ingest: missing state stored as '' and conf as NULL "
          "(no AR/0.95 fabrication)", row == ("", None), row)
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "HON100", "cam": "CAM-02",
                "event_id": "evt-hon-1"})
    check("S4 ingest: redelivered event returns the original read id",
          s == 200 and b["result"] == "duplicate"
          and b["read_id"] == hon_id, b)
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "HON100", "cam": "CAM-999"})
    check("S4 ingest: unregistered camera refused 403",
          s == 403, b)
    kinds, _ = audit_kinds(p)
    check("S4 ingest: refusal chained as INGEST_REJECTED",
          "INGEST_REJECTED" in kinds)
    db.close()
    # a 25h-old read, inserted directly (no backfill API by design)
    db = sqlite3.connect(A.db)
    db.execute("INSERT INTO reads(ts,cam,plate,plate_raw,state,conf) "
               "VALUES(?,?,?,?,?,?)",
               (ago_iso(hours=25), "CAM-02", "OLD111", "OLD111", "AR",
                0.9))
    db.execute("INSERT INTO reads(ts,cam,plate,plate_raw,state,conf) "
               "VALUES(?,?,?,?,?,?)",
               (ago_iso(hours=25), "CAM-02", "RST417", "RST417", "AR",
                0.9))
    db.commit()
    db.close()
    s, b = req(p, "GET", "/search?plate=OLD111&case=2027-1014"
               "&justification=wall+test&tier=2", PAT)
    check("temporal wall: Tier 2 cannot see a 25h-old read",
          s == 200 and b["reads"] == [], b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=wall+test&tier=2", PAT)
    check("temporal wall: Tier 2 sees the fresh reads only",
          s == 200 and len(b["reads"]) == 2, b)
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
    check("search: tier=1 refused at /search (Tier 2 only)",
          s == 400, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014&tier=2",
               PAT)
    check("search: missing justification blocked", s == 403, b)
    s, b = req(p, "GET", "/search?plate=RST417&case=2027-1014"
               "&justification=x&tier=2", AUD)
    check("search: auditor cannot search (verifies, not searches)",
          s == 403, b)
    kinds, entries = audit_kinds(p)
    queries = [e for e in entries if e["kind"] == "QUERY"]
    check("logging: QUERY entries carry plate_ref + result_count + "
          "case_hash (tier-2 entries also why_hash; no raw case or "
          "justification anywhere)",
          queries and all(
              str(e["fields"].get("plate_ref", "")).startswith("pref:")
              and "result_count" in e["fields"]
              and "case_hash" in e["fields"]
              and "2027-1014" not in json.dumps(e["fields"])
              and ("why_hash" in e["fields"]
                   or e["fields"].get("tier") == 3)
              for e in queries), queries[:1])
    # ---------- hits / hotlist views ----------
    s, b = req(p, "GET", "/hits", DET)
    check("hits: detective can view", s == 200
          and any(h["id"] == hit1 for h in b["hits"]), b)
    s, b = req(p, "GET", "/hotlist", AUD)
    check("hotlist: auditor can view", s == 200, b)
    kinds, _ = audit_kinds(p)
    check("logging: HITS_VIEW and HOTLIST_VIEW chained",
          "HITS_VIEW" in kinds and "HOTLIST_VIEW" in kinds)
    suite_bridge(A)
    suite_a2(A, hit1)


def suite_bridge(A):
    """S4/S18: the Frigate bridge — secret gate, no fabrication,
    event-id forwarding — against the live instance A."""
    p = A.port
    env = dict(os.environ)
    env.update({"FRIGATE_BRIDGE_PORT": "18091",
                "FRIGATE_BRIDGE_SECRET": "bridge-secret-test",
                "NOCTUA_JANUS_URL": A.url,
                "NOCTUA_INGEST_USER": ING, "NOCTUA_INGEST_KEY": KEYS[ING]})
    proc = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPTS, "frigate_bridge.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(40):
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:18091/health",
                        timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.25)

        def event(body, secret=None):
            r = urllib.request.Request(
                "http://127.0.0.1:18091/event", method="POST",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            if secret is not None:
                r.add_header("X-Bridge-Secret", secret)
            try:
                with urllib.request.urlopen(r, timeout=10) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b"{}")

        s, b = event({"plate": "BRG100", "camera": "CAM-101"})
        check("S4 bridge: /event without the secret refused",
              s == 401, s)
        s, b = event({"plate": "BRG100", "camera": "CAM-101"},
                     secret="wrong")
        check("S4 bridge: /event with the wrong secret refused",
              s == 401, s)
        s, b = event({"plate": "BRG100", "camera": "CAM-101",
                      "id": "evt-bridge-1", "type": "end"},
                     secret="bridge-secret-test")
        check("S4 bridge: valid event forwarded",
              s == 200 and b.get("forwarded") is True, b)
        db = sqlite3.connect(A.db)
        row = db.execute("SELECT state, conf, event_id FROM reads "
                         "WHERE plate='BRG100'").fetchone()
        db.close()
        check("S4 bridge: no state/conf fabricated downstream either "
              "(stored '' / NULL, event id forwarded)",
              row == ("", None, "evt-bridge-1"), row)
        s, b = event({"plate": "BRG100", "camera": "CAM-101",
                      "id": "evt-bridge-1", "type": "end"},
                     secret="bridge-secret-test")
        check("S4 bridge: same event deduped, not re-ingested",
              s == 200 and b.get("forwarded") is False, b)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def suite_a2(A, hit1):
    p = A.port
    # ---------- suppression (S3) ----------
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
    # S18 named attack: a FRAGMENT search must not surface the
    # suppressed vehicle's reads either — "VIC" vs stored "VIC 309".
    for user, label in ((PAT, "patrol"), (SUP, "supervisor"),
                        (DET, "detective"), (AUD, "auditor")):
        if user == AUD:
            continue  # auditors cannot search at all (403 above)
        s, b = req(p, "GET", "/search?plate=VIC&case=2027-1040"
                   "&justification=frag+check&tier=2", user)
        check("S18 fragment 'VIC' vs stored 'VIC 309': suppressed, "
              "invisible to %s" % label,
              s == 200 and b["reads"] == [] and b["hits"] == [], b)
    # S18 named attack: suppression identity is state-blind — the
    # order names TX, the camera reports AR; the vehicle is the same.
    s, b = req(p, "POST", "/suppressions", SUP,
               {"plate": "TXS200", "state": "TX",
                "order_ref": "PO-2027-0200 (DEMO)"})
    assert s == 201, b
    s, b = req(p, "POST", "/reads", ING,
               {"plate": "TXS200", "state": "AR", "cam": "CAM-04",
                "conf": 0.9})
    assert s == 201, b
    s, b = req(p, "GET", "/search?plate=TXS200&case=2027-1040"
               "&justification=check&tier=2", DET)
    check("S18 non-AR suppression honored (state-blind identity)",
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
    # S3: a suppressed hit moves ONLY via the supervisor queue —
    # verify and export by a detective are refused even with the id.
    s, b = req(p, "POST", "/verify", DET,
               {"hit_id": prt_hit, "decision": "confirm",
                "case": "2027-1031"})
    check("S3 suppressed hit: detective verify refused (queue only)",
          s == 403, b)
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": prt_hit, "case_id": "2027-1031"})
    check("S3 suppressed hit: detective export refused (queue only)",
          s == 403, b)
    s, b = req(p, "POST", "/verify", SUP,
               {"hit_id": prt_hit, "decision": "confirm",
                "case": "2027-1031"})
    check("S3 suppressed hit: supervisor verifies via the queue",
          s == 200 and b["result"] == "VERIFIED", b)
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": prt_hit, "case_id": "2027-1031"})
    check("S3 suppressed hit: export still supervisor-only after "
          "verification", s == 403, b)
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
          s == 200 and len(b["reads"]) == 2, b)
    # ---------- verify / outcomes / report (S14) ----------
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
          and b["prosecutions_coverage"] == {"reported": 0, "total": 3},
          b.get("prosecutions_coverage"))
    check("S14 report: outcomes born at ALERT time — the still-"
          "unverified CAM-101 hit already counts as unresolved",
          b["unresolved"] == 1, b.get("unresolved"))
    check("report: per-list counts from outcomes",
          b["lists"]["Local agency list"]["confirmed_matches"] == 2, b)
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
    s, b = req(p, "POST", "/lists", SUP, {"list_name": "State list"})
    check("S14 lists: supervisor registers a list name", s == 201, b)
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
    kinds, entries = audit_kinds(p)
    comp = [e for e in entries if e["kind"] == "REPORT_COMPILE"]
    check("S14 report: REPORT_COMPILE chains the snapshot body hash",
          comp and len(str(comp[0]["fields"].get("body_hash", ""))) == 64,
          comp[:1])
    req(p, "POST", "/reads", ING,
        {"plate": "RST417", "state": "AR", "cam": "CAM-03",
         "conf": 0.9})
    s, b = req(p, "GET", "/report?snapshot=%d" % snap_id, AUD)
    check("report: snapshot is immutable after new data",
          s == 200 and json.dumps(b, sort_keys=True) == snap_body, b)
    suite_a3(A, hit1)


def suite_a3(A, hit1):
    p = A.port
    ev_dir = os.path.join(A.dir, "evidence")
    # ---------- evidence (S17) ----------
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": hit1, "case_id": "2027-1014"})
    check("evidence: export ok", s == 201, b)
    bundle1 = os.path.join(ev_dir, b["bundle"])
    check("evidence: bundle dir + manifest on disk",
          os.path.isdir(bundle1) and os.path.isfile(
              os.path.join(bundle1, "manifest.json")), b)
    time.sleep(1.1)  # bundle names are second-resolution
    s, b = req(p, "POST", "/evidence/export", DET,
               {"hit_id": hit1, "case_id": "2027-1014",
                "expand": True})
    check("evidence: expand by detective refused", s == 403, b)
    s, b = req(p, "POST", "/evidence/export", SUP,
               {"hit_id": hit1, "case_id": "2027-1014",
                "expand": True})
    check("evidence: expand without reason refused", s == 400, b)
    s, b = req(p, "POST", "/evidence/export", SUP,
               {"hit_id": hit1, "case_id": "2027-1014",
                "expand": True, "reason": "pattern across days (DEMO)"})
    check("evidence: supervisor expand with reason ok",
          s == 201 and b["scope"] == "full", b)
    bundle2 = os.path.join(ev_dir, b["bundle"])
    # S17: the re-export deleted the PRIOR bundle in the same
    # operation — no orphaned plate archive on disk.
    check("S17 evidence: re-export deleted the prior bundle "
          "(no orphans)", not os.path.exists(bundle1)
          and os.path.isdir(bundle2), bundle1)
    # holds: HOLD_PLACE carries the hit id as an int (S17)
    s, b = req(p, "POST", "/holds", DET,
               {"scope": "hit", "ref": hit1,
                "reason": "litigation (DEMO)"})
    check("holds: placed on a hit", s == 201, b)
    kinds, entries = audit_kinds(p)
    hold_entries = [e for e in entries if e["kind"] == "HOLD_PLACE"]
    check("S17 evidence: HOLD entries carry the hit id as an int",
          hold_entries and hold_entries[0]["fields"].get("hit") == hit1
          and isinstance(hold_entries[0]["fields"].get("hit"), int),
          hold_entries[:1])
    # destroy is gated on a release first
    s, b = req(p, "POST", "/evidence/destroy", SUP,
               {"hit_id": hit1})
    check("evidence: destroy before release refused", s == 409, b)
    # disposition: posted by the detective, confirmed by a supervisor
    s, b = req(p, "POST", "/evidence/disposition", DET,
               {"hit_id": hit1, "outcome": "no_charges",
                "by": "PA Demo", "date": "2027-01-06",
                "note": "declined (DEMO)"})
    check("evidence: disposition posted", s == 201, b)
    s, b = req(p, "POST", "/evidence/disposition/confirm", DET,
               {"hit_id": hit1})
    check("evidence: disposition confirm is supervisor-only",
          s == 403, b)
    s, b = req(p, "POST", "/evidence/disposition/confirm", SUP,
               {"hit_id": hit1})
    check("evidence: disposition confirmed, destroy_by set "
          "(release + 30d)", s == 200 and b.get("destroy_by"), b)
    db = sqlite3.connect(A.db)
    db.execute("UPDATE evidence SET destroy_by=? WHERE hit_id=?",
               (ago_iso(days=1), hit1))
    db.commit()
    db.close()
    h = health(p)
    check("S17 evidence: overdue bundle destruction surfaces in "
          "/health", h["degraded"]["evidence_destroy_overdue"] >= 1, h)
    s, b = req(p, "POST", "/evidence/destroy", SUP,
               {"hit_id": hit1})
    check("evidence: destroy after confirmed disposition ok",
          s == 200, b)
    check("evidence: bundle gone from disk",
          not os.path.exists(bundle2), bundle2)
    suite_a4(A)


def suite_a4(A):
    p = A.port
    # ---------- Tier 3 (S2/S9) ----------
    s, b = req(p, "POST", "/tier3/request", DET,
               {"plate_fragment": "OLD111", "case_id": "2027-1023",
                "basis_type": "warrant",
                "auth_basis": "Warrant W-1 (DEMO)",
                "why": "locate the suspect vehicle"})
    check("tier3: request ok", s == 201, b)
    rid_old = b["request_id"]
    s, b = req(p, "GET", "/tier3/pending", SUP)
    check("tier3: pending visible to supervisor",
          s == 200 and any(r.get("id") == rid_old
                            for r in b["pending"]), b)
    s, b = req(p, "POST", "/tier3/approve", SUP,
               {"request_id": rid_old})
    check("tier3: approve executes", s == 200, b)
    s, b = req(p, "GET", "/tier3/results/%d" % rid_old, DET)
    check("tier3: results show the 25h-old read (no Tier 2 wall)",
          s == 200 and any(r["plate"] == "OLD111"
                           for r in b["results"]["reads"]), b)
    kinds, _ = audit_kinds(p)
    check("S2 tier3: result views chain as TIER3_RESULTS_VIEW",
          "TIER3_RESULTS_VIEW" in kinds)
    s, b = req(p, "GET", "/tier3/results/%d" % rid_old, AUD)
    check("S9 tier3: auditor loses body access to results",
          s == 403, b)
    # S2 named behavior: suppress the plate NOW — the stored result
    # ids must re-resolve through the live shaping layer and vanish.
    s, b = req(p, "POST", "/suppressions", SUP,
               {"plate": "OLD111", "order_ref": "PO-2027-0999 (DEMO)"})
    assert s == 201, b
    s, b = req(p, "GET", "/tier3/results/%d" % rid_old, DET)
    check("S2 tier3: stored ids re-resolve live — post-hoc "
          "suppression empties the detail, summary says expired",
          s == 200 and b.get("expired") is True
          and "results" not in b, b)
    s, b = req(p, "POST", "/tier3/request", DET,
               {"plate_fragment": "OLD111", "case_id": "2027-1023",
                "basis_type": "warrant",
                "auth_basis": "Warrant W-1 (DEMO)",
                "why": "second pass"})
    check("tier3: second request for the same fragment ok",
          s == 201, b)
    rid2 = b["request_id"]
    s, b = req(p, "POST", "/tier3/approve", SUP2,
               {"request_id": rid2})
    check("tier3: second supervisor approves", s == 200, b)
    kinds, entries = audit_kinds(p)
    t3 = [e for e in entries if e["kind"] == "QUERY"
          and e["fields"].get("tier") == 3]
    check("logging: executed Tier 3 searches chain QUERY entries "
          "carrying frag_ref + result_count",
          t3 and all(str(e["fields"].get("plate_ref", "")).startswith(
              "pref:") and "result_count" in e["fields"]
              for e in t3), t3[:1])
    s, b = req(p, "POST", "/tier3/request", DET,
               {"plate_fragment": "OLD111", "case_id": "2027-1023",
                "basis_type": "consent", "why": "x",
                "auth_basis": "Consent C-1 (DEMO)"})
    check("tier3: consent basis refused for Tier 3", s == 400, b)
    s, b = req(p, "POST", "/tier3/request", DET,
               {"plate_fragment": "OLD111", "case_id": "personal notes",
                "basis_type": "warrant",
                "auth_basis": "Warrant W-1 (DEMO)", "why": "x"})
    check("tier3: free-text case_id refused by the shared case gate",
          s == 403, b)
    s, b = req(p, "GET", "/tier3/pending", PAT)
    check("tier3: patrol sees only its own requests (none)",
          s == 200 and b["pending"] == [], b)
    suite_a5(A)


def suite_a5(A):
    p = A.port
    # ---------- Compact rotation over HTTP (S12) ----------
    pub = pub_pem(A.db)
    for agency in ("agency-a", "agency-b", "agency-c", "agency-d"):
        s, b = req(p, "POST", "/compact/partners", SUP,
                   {"agency": agency, "endpoint": "http://x",
                    "pubkey_pem": pub,
                    "agreement_ref": "MOU-DEMO"})
        assert s in (201, 409), b
    members = ["agency-a", "agency-b", "agency-c", "agency-d"]
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": members + ["agency-zzz"]})
    check("S12 rotation: member outside the partner registry refused",
          s == 400, b)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-02-30", "period_days": 30,
                "members": members})
    check("S12 rotation: impossible calendar date refused",
          s == 400, b)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 3,
                "members": members})
    check("S12 rotation: period outside 7-120 refused", s == 400, b)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": members, "seed": "publisher-chosen"})
    check("P9 rotation: a publisher-supplied seed is refused — the "
          "seed is DERIVED from members + cycle_start + chain root",
          s == 400 and "derived" in b.get("error", ""), b)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": ["agency-a"]})
    check("P9 rotation: fewer than 2 members refused", s == 400, b)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": members})
    check("S12 rotation: publish ok and SIGNED (Ed25519)",
          s == 201 and b.get("sig"), b)
    sched1 = json.dumps(b["schedule"], sort_keys=True)
    seed1 = b.get("seed")
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": members})
    check("S12 rotation: second publish over an active cycle refused",
          s == 409, b)
    s, b = req(p, "POST", "/compact/rotation/void", SUP, {})
    check("S12 rotation void: first supervisor requests",
          s == 200 and "auditor must confirm" in b.get("result", ""), b)
    s, b = req(p, "POST", "/compact/rotation/void", SUP2, {})
    check("S12 rotation void: second supervisor cannot confirm "
          "(auditor required)", s == 403, b)
    s, b = req(p, "POST", "/compact/rotation/void", AUD, {})
    check("S12 rotation void: auditor confirms (two-key)",
          s == 200 and "voided" in b.get("result", ""), b)
    kinds, _ = audit_kinds(p)
    check("S12 rotation void: ROTATION_VOID chained",
          "ROTATION_VOID" in kinds)
    s, b = req(p, "POST", "/compact/rotation", SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": members})
    check("S18 rotation: republish succeeds after the void",
          s == 201, b)
    sched2 = json.dumps(b["schedule"], sort_keys=True)
    check("P9 rotation: the derived seed moves with the chain root "
          "(the void rewrote the inputs, so the seed — and with it "
          "the schedule — is recomputed, never chosen)",
          b.get("seed") != seed1, (seed1, b.get("seed")))
    s, b = req(p, "GET", "/compact/rotation/status", SUP)
    check("S12 rotation status: active cycle with per-round windows",
          s == 200 and b["active"] is True and len(b["rounds"]) == 4, b)
    # ---------- config discipline (S13) ----------
    write_cases(A.cases, CASES + ["2027-2000"])
    s, b = req(p, "GET", "/stats", DET)
    kinds, _ = audit_kinds(p)
    check("S13 config: users/cases content change chains "
          "CONFIG_CHANGED", "CONFIG_CHANGED" in kinds)
    write_cases(A.cases)
    req(p, "GET", "/stats", DET)
    with open(A.cases, "w") as f:
        f.write("{broken json")
    time.sleep(0.2)
    req(p, "GET", "/stats", DET)  # any authed request trips the reload
    h = health(p)
    check("S13 config: failed reload degrades health and surfaces "
          "as config_stale (fail-closed follows at 24h stale, per "
          "config_closed on every data endpoint)",
          h["config_stale"] is True and h["ok"] is False, h)
    kinds, _ = audit_kinds(p)
    check("S13 config: CONFIG_STALE chained", "CONFIG_STALE" in kinds)
    write_cases(A.cases)
    time.sleep(0.2)
    s, b = req(p, "GET", "/stats", DET)
    h = health(p)
    check("S13 config: clean reload clears staleness, service resumes",
          s == 200 and h["config_stale"] is False, h)


def suite_scripts(A):
    # ---------- rotation math (S12), pure ----------
    m5 = ["a1", "a2", "a3", "a4", "a5"]
    seed1 = rotation_mod.seed_for(m5, "2027-01-04")
    seed2 = rotation_mod.seed_for(m5, "2027-02-01")
    doc1 = rotation_mod.build_schedule(m5, "2027-01-04", 30)
    doc1b = rotation_mod.build_schedule(m5, "2027-01-04", 30)
    doc2 = rotation_mod.build_schedule(m5, "2027-02-01", 30)
    check("S18 rotation: cycle_start changes the seed and the order",
          seed1 != seed2
          and doc1["rounds"] != doc2["rounds"])
    check("S18 rotation: identical inputs reproduce byte-identically",
          sentinel_mod.canonical_bytes(rotation_mod.signed_portion(doc1))
          == sentinel_mod.canonical_bytes(
              rotation_mod.signed_portion(doc1b)))
    rounds = doc1["rounds"]
    check("S12 rotation: in an n-round cycle each member audits "
          "exactly once and is audited exactly once",
          len(rounds) == 5
          and sorted(r["auditor"] for r in rounds) == m5
          and sorted(r["audited"] for r in rounds) == m5, rounds)
    check("S12 rotation: nobody audits themselves",
          all(r["auditor"] != r["audited"] for r in rounds))
    doc_n2 = rotation_mod.build_schedule(["x", "y"], "2027-01-04", 30)
    check("S12 rotation: N=2 is a static mutual pair",
          len(doc_n2["rounds"]) == 2
          and doc_n2["rounds"][0]["auditor"]
          == doc_n2["rounds"][1]["audited"])
    doc_n1 = rotation_mod.build_schedule(["x"], "2027-01-04", 30)
    check("S12 rotation: N<2 is inactive",
          doc_n1["rounds"] == [] and doc_n1["mode"] == "inactive")
    # ---------- sentinel: 1,000 concurrent appends (S18) ----------
    conc_db = os.path.join(WORK, "conc.db")
    code = ("import sys; sys.path.insert(0, %r); import sentinel; "
            "c = sentinel.Chain(%r); "
            "[c.append('TEST', {'i': i}) for i in range(500)]"
            % (ROOT, conc_db))
    procs = [subprocess.Popen([sys.executable, "-c", code],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
             for _ in range(2)]
    outs = [pr.communicate(timeout=300) for pr in procs]
    check("S18 sentinel: two writer processes exit clean",
          all(pr.returncode == 0 for pr in procs),
          [o[1][-200:] for o in outs])
    import importlib
    sm = importlib.import_module("sentinel")
    v = sm.Chain(conc_db).verify()
    check("S18 sentinel: 1,000 concurrent appends across two "
          "processes verify clean",
          v["ok"] is True and v["entries"] == 1000, v)
    # ---------- sentinel: scrubber flags, never raises (S11) ----------
    scr_db = os.path.join(WORK, "scrub.db")
    ch = sm.Chain(scr_db)
    ch.append("TEST", {"plate": "ABC123"})
    ents = ch.entries()
    stored = [e for e in ents if e["kind"] == "TEST"]
    flags = [e for e in ents if e["kind"] == "CHAIN_SCRUB_FLAG"]
    check("S11 scrubber: plate-shaped value is hashed, not raised, "
          "and a CHAIN_SCRUB_FLAG is chained",
          stored and stored[0]["fields"].get("plate") == sha("ABC123")
          and flags, ents)
    ch.append("TEST", {"cam": "CAM-101", "agency": "CPD-1001"})
    ents = ch.entries()
    coded = [e for e in ents if e["kind"] == "TEST"][0]  # newest first
    check("S11 scrubber: legitimate ids CAM-101 / CPD-1001 pass "
          "through unchanged (fault-injection)",
          coded["fields"].get("cam") == "CAM-101"
          and coded["fields"].get("agency") == "CPD-1001", coded)
    # ---------- sentinel: sink spool (carried from 1.1) ----------
    sinkfile = os.path.join(WORK, "sink.jsonl")
    os.environ["NOCTUA_SENTINEL_SINK"] = sinkfile
    try:
        ch2 = sm.Chain(os.path.join(WORK, "sink.db"))
        ch2.append("TEST", {"n": 1})
        check("sink: entry streamed to the sink file",
              os.path.isfile(sinkfile)
              and json.loads(open(sinkfile).readline())["kind"]
              == "TEST")
        os.environ["NOCTUA_SENTINEL_SINK"] = os.path.join(
            WORK, "dead", "sink.jsonl")
        ch3 = sm.Chain(os.path.join(WORK, "sink2.db"))
        ch3.append("TEST", {"n": 2})
        st = ch3.sink_status()
        check("sink: dead sink path never blocks appends",
              st["enabled"] is True and st["ok"] is False, st)
    finally:
        os.environ.pop("NOCTUA_SENTINEL_SINK", None)
    suite_witness_backup(A)
    suite_chain_broken()
    suite_schema(A)
    suite_provision_alert()


def suite_schema(A):
    """S1 + P10: the registry is complete BY CONSTRUCTION — a
    FULL-COLUMN ALLOWLIST. Every column of every table is either a
    registered plate store or named in sentinel.NON_PLATE_COLUMNS;
    every file and folder under the data root is either a declared
    file store, a config file, or a registered folder. 1.2's test
    pattern-matched column NAMES (plate|frag|results), so a column
    named vehicle_tag or a whole new table sailed through (A16)."""
    db = sqlite3.connect(A.db)
    unregistered = sentinel_mod.schema_unregistered(db)
    db.close()
    check("P10 schema: EVERY column of EVERY table is registered "
          "or in NON_PLATE_COLUMNS", not unregistered,
          ["%s.%s" % tc for tc in unregistered])
    folders = {e.get("folder")
               for e in sentinel_mod.PLATE_DATA_STORES
               if e["kind"] == "folder"}
    on_disk = {d for d in os.listdir(A.dir)
               if os.path.isdir(os.path.join(A.dir, d))}
    check("S1 schema: every folder under the data root is a "
          "registered store", on_disk <= folders,
          (on_disk, folders))
    # Loose FILES under the data root (P10): the DB itself and its
    # declared sidecars (WAL family, keys, checkpoints, restore
    # marker, pre-restore copies), plus the config files the
    # harness wrote. Anything else — an unregistered sidecar like
    # <db>.alerts.jsonl — fails.
    base = os.path.basename(A.db)
    allowed_files = {"users.json", "cases.json", "cameras.json",
                     "server.log"}
    # The DB's declared sidecars — exactly the suffixes the
    # registry's file-stores name. A generic "<db>.<anything>"
    # allowance is how <db>.alerts.jsonl hid in 1.2 (A16).
    sidecar_suffixes = ("-wal", "-shm", "-journal", ".audit_key",
                        ".signing_key.pem", ".signing_pub.pem",
                        ".checkpoints.jsonl", ".restore_marker",
                        ".lock")
    loose = []
    for name in os.listdir(A.dir):
        p = os.path.join(A.dir, name)
        if os.path.isdir(p):
            continue
        if name in allowed_files or name == base:
            continue
        if name.startswith(base) and (
                name[len(base):] in sidecar_suffixes
                or name[len(base):].startswith(".pre-restore-")):
            continue
        loose.append(name)
    check("P10 schema: no unregistered loose files under the data "
          "root", not loose, loose)
    check("P10 registry: version 1.2.1, holds.reason and "
          "witness_attestations.detail registered (class derived)",
          sentinel_mod.REGISTRY_VERSION == "1.2.1"
          and any(e.get("table") == "holds"
                  and e.get("column") == "reason"
                  for e in sentinel_mod.PLATE_DATA_STORES)
          and any(e.get("table") == "witness_attestations"
                  and e.get("column") == "detail"
                  for e in sentinel_mod.PLATE_DATA_STORES),
          sentinel_mod.REGISTRY_VERSION)


def suite_chain_broken():
    """S18: a chain that fails verification makes /health say so."""
    import shutil
    src = os.path.join(WORK, "a")
    dst = os.path.join(WORK, "broken")
    os.makedirs(dst)
    for f in os.listdir(src):
        if f.startswith("janus.db"):
            shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    dbp = os.path.join(dst, "janus.db")
    db = sqlite3.connect(dbp)
    db.execute("UPDATE audit SET payload=? WHERE seq=2",
               ('{"kind":"TEST","ts":"tampered"}',))
    db.commit()
    db.close()
    users = os.path.join(dst, "users.json")
    cases = os.path.join(dst, "cases.json")
    cameras = os.path.join(dst, "cameras.json")
    write_users(users)
    write_cases(cases)
    write_cameras(cameras)
    env = dict(os.environ)
    env.update({"NOCTUA_DB": dbp, "NOCTUA_USERS": users,
                "NOCTUA_CASES": cases, "NOCTUA_CAMERAS": cameras,
                "NOCTUA_PORT": "18092", "NOCTUA_AUDIT_KEY": AUDIT_KEY,
                "NOCTUA_EVIDENCE_DIR": os.path.join(dst, "evidence")})
    proc = subprocess.Popen([sys.executable, JANUS], env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                s, _b = req(18092, "GET", "/ping")
                if s == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        h = health(18092)
        check("S18 chain_ok false => /health ok false",
              h["ok"] is False
              and h["degraded"]["chain_ok"] is False, h["degraded"])
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def suite_witness_backup(A):
    # ---------- checkpoint + witness + anchor (S6/S7) ----------
    env = dict(os.environ)
    env.update({"NOCTUA_DB": A.db, "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "checkpoint.py")],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    lines = [l for l in r.stdout.splitlines() if l.startswith("{")]
    check("S6 checkpoint: stdout is exactly one JSON line",
          r.returncode == 0 and len(lines) == 1, r.stdout[:200])
    cp = json.loads(lines[0])
    check("S7 checkpoint: Ed25519-signed, public key embedded",
          cp.get("sig_alg") == "ed25519" and cp.get("sig")
          and "BEGIN PUBLIC KEY" in cp.get("pubkey", ""), cp.keys())
    ok = sentinel_mod.verify_bytes(
        cp["pubkey"],
        sentinel_mod.checkpoint_signed_bytes(cp), cp["sig"])
    check("S7 checkpoint: signature verifies against the embedded key",
          ok)
    # publish_witness end-to-end (P5): the witness repo is a real
    # git clone with a local bare remote — publication is PROVEN
    # against the remote before the script may report success.
    witness = os.path.join(WORK, "witness")
    remote = os.path.join(WORK, "witness-remote.git")
    subprocess.run(["git", "init", "--bare", remote], check=True,
                   capture_output=True)
    subprocess.run(["git", "clone", "-q", remote, witness],
                   check=True, capture_output=True)
    for k, v in (("user.email", "witness@test.invalid"),
                 ("user.name", "Witness Test"),
                 ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", witness, "config", k, v],
                       check=True, capture_output=True)
    with open(os.path.join(witness, "README"), "w") as f:
        f.write("witness repo\n")
    subprocess.run(["git", "-C", witness, "add", "README"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", witness, "commit", "-qm", "init"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", witness, "push", "-q", "origin",
                    "HEAD"], check=True, capture_output=True)
    env2 = dict(env)
    env2.update({"WITNESS_REPO": witness, "NOCTUA_JANUS_URL": ""})
    r = subprocess.run(["bash",
                        os.path.join(SCRIPTS, "publish_witness.sh")],
                       env=env2, capture_output=True, text=True,
                       timeout=120)
    wfile = os.path.join(witness, "checkpoints.jsonl")
    check("P5 publish_witness end-to-end: checkpoint committed, "
          "pushed, and verified ON THE REMOTE",
          r.returncode == 0 and os.path.isfile(wfile),
          r.stdout + r.stderr)
    # P5/A6a: no git repo at all -> failure, never a same-box
    # "publication" with a success report.
    env3 = dict(env)
    env3.update({"WITNESS_REPO": os.path.join(WORK, "witness-plain"),
                 "NOCTUA_JANUS_URL": ""})
    os.makedirs(os.path.join(WORK, "witness-plain"))
    r = subprocess.run(["bash",
                        os.path.join(SCRIPTS, "publish_witness.sh")],
                       env=env3, capture_output=True, text=True,
                       timeout=120)
    check("P5 publish_witness: a plain directory is NOT a witness "
          "(nonzero exit, no success claim)",
          r.returncode != 0
          and "published" not in r.stdout,
          r.stdout + r.stderr)
    # P5/A6b: a commit that cannot happen (no identity) fails the
    # run instead of being swallowed by || true.
    witness2 = os.path.join(WORK, "witness-noident")
    subprocess.run(["git", "clone", "-q", remote, witness2],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", witness2, "config",
                    "commit.gpgsign", "false"],
                   check=True, capture_output=True)
    env4 = dict(env)
    env4.update({"WITNESS_REPO": witness2, "NOCTUA_JANUS_URL": "",
                 "GIT_CONFIG_NOSYSTEM": "1",
                 "HOME": os.path.join(WORK, "empty-home")})
    os.makedirs(os.path.join(WORK, "empty-home"))
    r = subprocess.run(["bash",
                        os.path.join(SCRIPTS, "publish_witness.sh")],
                       env=env4, capture_output=True, text=True,
                       timeout=120)
    check("P5 publish_witness: uncommittable checkpoint fails the "
          "run (no || true)", r.returncode != 0,
          r.stdout + r.stderr)
    if os.path.isfile(wfile):
        last = json.loads(open(wfile).read().strip().splitlines()[-1])
        ok = sentinel_mod.verify_bytes(
            last["pubkey"],
            sentinel_mod.checkpoint_signed_bytes(last), last["sig"])
        check("S6 witness: published checkpoint is the signed one",
              ok)
    # anchor: tamper with the newest entry's payload (recomputing its
    # hash with the CURRENT v2 formula so the chain itself still
    # verifies — the attacker has the public code; what they cannot
    # fix is the published checkpoint) -> anchor must refuse.
    db = sqlite3.connect(A.db)
    seq, ets, ekind, payload, h = db.execute(
        "SELECT seq, ts, kind, payload, hash FROM audit ORDER BY "
        "seq DESC LIMIT 1").fetchone()
    doc = json.loads(payload)
    doc["tampered"] = True
    newp = json.dumps(doc, separators=(",", ":"), sort_keys=True)
    prev = db.execute("SELECT hash FROM audit WHERE seq=?",
                      (seq - 1,)).fetchone()
    prev = prev[0] if prev else sm_genesis()
    newh = sentinel_mod.entry_hash(prev, ets, ekind, newp)
    db.execute("UPDATE audit SET payload=?, hash=? WHERE seq=?",
               (newp, newh, seq))
    db.commit()
    db.close()
    A.start()
    try:
        h = health(A.port)
        check("S6 anchor: checkpoint over a tampered history refuses "
              "(anchor_mismatch)", h["anchor_mismatch"] is True
              and h["ok"] is False, h["degraded"])
        s, b = req(A.port, "POST", "/audit/anchor-accept", SUP, {})
        check("S6 anchor: supervisor records acceptance (two-key: "
              "auditor must confirm)",
              s == 200 and "auditor must confirm" in b.get("result", ""),
              b)
        h = health(A.port)
        check("S6 anchor: still mismatched until the auditor confirms",
              h["anchor_mismatch"] is True)
        s, b = req(A.port, "POST", "/audit/anchor-accept", AUD, {})
        check("S6 anchor: auditor confirms, acceptance recorded",
              s == 200, b)
        h = health(A.port)
        check("S6 anchor: health recovers after acceptance",
              h["anchor_mismatch"] is False)
    finally:
        A.stop()
    suite_backup_restore(A)


def sm_genesis():
    return "GENESIS"


def suite_backup_restore(A):
    # ---------- backup + restore (S6/S17) ----------
    fake_ev = os.path.join(WORK, "fake-evidence")
    bundle_dir = os.path.join(fake_ev, "EV-TEST-1")
    os.makedirs(bundle_dir)
    with open(os.path.join(bundle_dir, "manifest.json"), "w") as f:
        f.write("{}")
    bout = os.path.join(WORK, "backups")
    env = dict(os.environ)
    env.update({"NOCTUA_DB": A.db, "NOCTUA_AUDIT_KEY": AUDIT_KEY,
                "NOCTUA_BACKUP_DIR": bout, "NOCTUA_JANUS_URL": "",
                "NOCTUA_EVIDENCE_DIR": fake_ev})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "backup.py")],
                       env=env, capture_output=True, text=True,
                       timeout=120)
    sets = sorted(os.listdir(bout)) if os.path.isdir(bout) else []
    check("S17 backup: set created incl. evidence + signing keys",
          r.returncode == 0 and sets, r.stdout + r.stderr)
    if not sets:
        return
    bset = os.path.join(bout, sets[-1])
    manifest = json.load(open(os.path.join(bset, "manifest.json")))
    check("S7 backup: manifest carries an Ed25519 signature",
          bool(manifest.get("manifest_sig")), manifest.keys())
    check("S17 backup: evidence.tar.gz inside the set",
          "evidence.tar.gz" in manifest["files"], manifest["files"])
    # restore into a fresh dir that has its OWN live checkpoints file
    rdir = os.path.join(WORK, "restored")
    os.makedirs(rdir)
    rdb = os.path.join(rdir, "noctua.db")
    small = sentinel_mod.Chain(rdb)
    small.append("TEST", {"note": "pre-restore live db"})
    run_checkpoint(rdb)
    live_cp_text = open(rdb + ".checkpoints.jsonl").read()
    env_r = dict(os.environ)
    env_r.update({"NOCTUA_AUDIT_KEY": AUDIT_KEY})
    # P6: the small live DB has its OWN signing key, so the set's
    # signature cannot verify against the host's — the operator
    # passes the set's registered public key EXPLICITLY (a pinned
    # copy held outside the set). 1.2 silently trusted the key
    # inside the set; 1.2.1 never does.
    pinned_pub = os.path.join(WORK, "operator-pinned-a-pub.pem")
    with open(pinned_pub, "w") as f:
        f.write(open(os.path.join(bset, "signing_pub.pem")).read())
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "restore.py"),
                        bset, "--db", rdb, "--pubkey", pinned_pub],
                       env=env_r, capture_output=True, text=True,
                       timeout=120)
    check("restore: succeeds and verifies the chain",
          r.returncode == 0 and "restored OK" in r.stdout,
          r.stdout + r.stderr)
    check("S18 restore keeps the anchor: the live checkpoints file "
          "is untouched",
          open(rdb + ".checkpoints.jsonl").read() == live_cp_text)
    evidence = [f for f in os.listdir(rdir)
                if f.startswith("noctua.db.checkpoints.jsonl"
                                ".from-backup-")]
    check("S6 restore: the backup's checkpoints are kept as evidence, "
          "not state", len(evidence) == 1, os.listdir(rdir))
    check("S6 restore: restore marker written for Janus to chain",
          os.path.isfile(rdb + ".restore_marker"))
    check("S6 restore: restored files are 0600",
          (os.stat(rdb).st_mode & 0o777) == 0o600,
          oct(os.stat(rdb).st_mode))
    # boot Janus on the restored DB: RESTORE must be chained (S6)
    R = Instance.__new__(Instance)
    R.dir, R.port, R.db = rdir, 18093, rdb
    R.users = os.path.join(rdir, "users.json")
    R.cases = os.path.join(rdir, "cases.json")
    R.cameras = os.path.join(rdir, "cameras.json")
    write_users(R.users)
    write_cases(R.cases)
    write_cameras(R.cameras)
    R.env = dict(os.environ)
    R.env.update({"NOCTUA_DB": rdb, "NOCTUA_USERS": R.users,
                  "NOCTUA_CASES": R.cases, "NOCTUA_CAMERAS": R.cameras,
                  "NOCTUA_PORT": "18093",
                  "NOCTUA_EVIDENCE_DIR": os.path.join(rdir, "evidence"),
                  "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    R.proc = None
    R.start()
    try:
        kinds, _ = audit_kinds(18093)
        check("S18 restore: Janus chains RESTORE from the marker at "
              "boot", "RESTORE" in kinds)
        check("S6 restore: marker consumed after chaining",
              not os.path.exists(rdb + ".restore_marker"))
    finally:
        R.stop()
    # unsigned manifest refused (S18)
    import shutil
    uset = os.path.join(WORK, "set-unsigned")
    shutil.copytree(bset, uset)
    mpath = os.path.join(uset, "manifest.json")
    m = json.load(open(mpath))
    m["manifest_sig"] = None
    m["manifest_hmac"] = None
    json.dump(m, open(mpath, "w"), indent=1, sort_keys=True)
    rdb2 = os.path.join(WORK, "restored2", "noctua.db")
    os.makedirs(os.path.dirname(rdb2))
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "restore.py"),
                        uset, "--db", rdb2],
                       env=env_r, capture_output=True, text=True,
                       timeout=120)
    check("S18 unsigned backup manifest refused",
          r.returncode != 0
          and "REFUSING TO RESTORE" in (r.stdout + r.stderr),
          r.stdout + r.stderr)
    # tar-slip refused even with a validly re-signed manifest (S18)
    import io
    import tarfile
    sset = os.path.join(WORK, "set-slip")
    shutil.copytree(bset, sset)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = b"pwned"
        info = tarfile.TarInfo("../evil.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    cpath = os.path.join(sset, "config.tar.gz")
    open(cpath, "wb").write(buf.getvalue())
    m = json.load(open(os.path.join(sset, "manifest.json")))
    raw = open(cpath, "rb").read()
    m["files"]["config.tar.gz"] = {
        "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
    body = {"created": m["created"], "noctua": "1.2",
            "source_db": m["source_db"], "files": m["files"]}
    m["manifest_sig"] = sentinel_mod.sign_bytes(
        os.path.join(sset, "signing_key.pem"),
        sentinel_mod.canonical_bytes(body))
    import hmac as _hmac
    m["manifest_hmac"] = _hmac.new(
        AUDIT_KEY.encode(),
        sentinel_mod.canonical_bytes(body),
        hashlib.sha256).hexdigest()
    json.dump(m, open(os.path.join(sset, "manifest.json"), "w"),
              indent=1, sort_keys=True)
    rdb3 = os.path.join(WORK, "restored3", "noctua.db")
    os.makedirs(os.path.dirname(rdb3))
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "restore.py"),
                        sset, "--db", rdb3],
                       env=env_r, capture_output=True, text=True,
                       timeout=120)
    check("S18 tar-slip backup refused at extraction",
          r.returncode != 0
          and not os.path.exists(os.path.join(WORK, "restored3",
                                              "evil.txt"))
          and not os.path.exists(os.path.join(
              os.path.dirname(rdb3), "..", "evil.txt")),
          r.stdout + r.stderr)


def suite_provision_alert():
    # ---------- provision: chain_auditor issuable (S9/S18) ----------
    pu = os.path.join(WORK, "prov-users.json")
    env = dict(os.environ)
    env.update({"NOCTUA_USERS": pu, "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "provision.py"),
                        "add-user", "ca.test", "chain_auditor"],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    r2 = subprocess.run([sys.executable,
                         os.path.join(SCRIPTS, "provision.py"),
                         "list-users"],
                        env=env, capture_output=True, text=True,
                        timeout=60)
    check("S18 provision: chain_auditor role issuable and listed",
          r.returncode == 0 and "chain_auditor" in r2.stdout,
          r.stdout + r.stderr + r2.stdout)


def suite_compact(A, B):
    pa, pb = A.port, B.port
    # B registers A as a partner, with A's Ed25519 public key (S7).
    s, b = req(pb, "POST", "/compact/partners", SUP,
               {"agency": "agency-a", "endpoint": A.url,
                "pubkey_pem": pub_pem(A.db),
                "agreement_ref": "MOU-DEMO-2027"})
    check("compact: partner registered with a public key",
          s == 201, b)
    kinds, _ = audit_kinds(pb)
    check("compact: PARTNER_ADD chained", "PARTNER_ADD" in kinds)
    share = {"agency": "agency-a", "plate_fragment": "RST417",
             "case_ref": "2027-1014",
             "why": "regional stolen-vehicle sweep",
             "basis_type": "warrant",
                "auth_basis": "Warrant W-1 (DEMO)", "tier": 2}
    s, b = req(pb, "POST", "/share/query", "agency-a", share)
    check("S8 share: no audit on file -> blocked at cross_audit_ok",
          s == 403 and b.get("missing") == "cross_audit_ok", b)
    kinds, _ = audit_kinds(pb)
    check("S8 share: refusal chained as SHARE_BLOCKED",
          "SHARE_BLOCKED" in kinds)
    # a signed passing audit report from OUR auditor closes leg one
    s, b = post_audit_result(pb, B.db, "agency-a", True)
    check("S8 compact: signed audit-result accepted", s == 201, b)
    s, b = req(pb, "POST", "/share/query", "agency-a", share)
    check("S8 share: audit on file -> blocked at checkpoint_receipt",
          s == 403 and b.get("missing") == "checkpoint_receipt", b)
    cp1 = run_checkpoint(B.db, B.url)
    s, b = post_receipt(pb, A.db, "agency-a", dict(cp1, root="0" * 64))
    check("S8 receipt: wrong root refused", s == 409, b)
    s, b = req(pb, "POST", "/compact/checkpoint-receipt", DET,
               {"agency": "agency-a", "checkpoint_root": cp1["root"],
                "checkpoint_entries": cp1["entries"],
                "checkpoint_ts": cp1["ts"], "signature": "x"})
    check("S8 receipt: only the partner itself may file it",
          s == 403, b)
    s, b = post_receipt(pb, A.db, "agency-a", cp1)
    check("S8 receipt: signed receipt for the newest checkpoint ok",
          s == 201, b)
    kinds, _ = audit_kinds(pb)
    check("S8 receipt: COMPACT_RECEIPT chained",
          "COMPACT_RECEIPT" in kinds)
    s, b = req(pb, "POST", "/share/query", "agency-a", share)
    check("share: full gate passes -> Tier 2 answer",
          s == 200 and b["results"]["reads"] == []
          and b["results"]["hits"] == [], b)
    # S18 named attack: a replayed OLD receipt is refused once a
    # newer checkpoint exists.
    cp2 = run_checkpoint(B.db, B.url)
    s, b = post_receipt(pb, A.db, "agency-a", cp1)
    check("S18 replayed old checkpoint receipt refused",
          s == 409, b)
    s, b = post_receipt(pb, A.db, "agency-a", cp2)
    check("S8 receipt: fresh receipt for the new checkpoint ok",
          s == 201, b)
    # shares carry their own discipline (S10)
    s, b = req(pb, "POST", "/share/query", "agency-a",
               dict(share, tier=3))
    check("S10 share: Tier 3 refused at the share endpoint",
          s == 403, b)
    s, b = req(pb, "POST", "/share/query", "agency-a",
               dict(share, basis_type=""))
    check("S10 share: partner basis_type required",
          s == 403 and b.get("missing") == "basis_type", b)
    s, b = req(pb, "POST", "/share/query", "agency-a",
               dict(share, case_ref=""))
    check("S10 share: case_ref required non-empty", s == 403, b)
    s, b = req(pb, "POST", "/share/query", "agency-a",
               dict(share, case_ref="PATROL-7"))
    check("S10 share: partner case_ref still passes the banned-"
          "pattern gate", s == 403, b)
    # S18 named attack: a NEWER failing audit closes the gate at once
    s, b = post_audit_result(pb, B.db, "agency-a", False)
    check("S8 compact: signed failing audit-result accepted",
          s == 201, b)
    s, b = req(pb, "POST", "/share/query", "agency-a", share)
    check("S18 fail-after-ok closes the share gate with no manual "
          "suspension", s == 403
          and b.get("missing") == "cross_audit_ok", b)
    s, b = post_audit_result(pb, B.db, "agency-a", True)
    assert s == 201, b
    s, b = req(pb, "POST", "/share/query", "agency-a", share)
    check("S8 share: a fresh passing audit reopens the gate",
          s == 200, b)
    kinds, entries = audit_kinds(pb)
    outs = [e for e in entries if e["kind"] == "SHARE_OUT"]
    check("S10 share: SHARE_OUT chains hashes, never the raw why",
          outs and all("why_hash" in e["fields"]
                       and "regional stolen-vehicle sweep"
                       not in json.dumps(e["fields"]) for e in outs),
          outs[:1])
    # suspension / reinstatement
    s, b = req(pb, "POST", "/compact/suspend", SUP,
               {"agency": "agency-a"})
    check("compact: suspend ok", s == 200, b)
    s, b = req(pb, "POST", "/share/query", "agency-a", share)
    check("share: suspended partner blocked as partner_inactive",
          s == 403 and b.get("missing") == "partner_inactive", b)
    s, b = req(pb, "POST", "/compact/reinstate", SUP,
               {"agency": "agency-a"})
    check("compact: reinstate with a fresh passing audit ok",
          s == 200, b)
    # S10 rate limit: 60/hour per partner
    statuses = []
    for _ in range(70):
        s, b = req(pb, "POST", "/share/query", "agency-a", share)
        statuses.append(s)
        if s == 429:
            break
    check("S10 share: per-partner rate limit trips at 60/hour",
          429 in statuses and statuses.count(200) <= 60, statuses[-3:])
    kinds, _ = audit_kinds(pb)
    check("S10 share: the trip chains SHARE_RATE_LIMIT",
          "SHARE_RATE_LIMIT" in kinds)
    # S9: the chain_auditor fence on B
    s, b = req(pb, "GET", "/audit?limit=5", CA)
    check("S9 chain_auditor: /audit allowed", s == 200, b)
    s, b = req(pb, "GET", "/audit/range?from_seq=1&to_seq=3", CA)
    check("S9 chain_auditor: /audit/range allowed",
          s == 200 and len(b["entries"]) == 3, b)
    s, b = req(pb, "GET", "/compact/checkpoint", CA)
    check("S9 chain_auditor: /compact/checkpoint allowed",
          s == 200, b)
    for path, label in (("/hits", "hits"), ("/search?plate=RST417",
                         "search"), ("/tier3/pending", "tier3"),
                        ("/stats", "stats"), ("/report", "report"),
                        ("/hotlist", "hotlist")):
        s, b = req(pb, "GET", path, CA)
        check("S9 chain_auditor: barred from /%s" % label,
              s == 403, b)
    s, b = req(pb, "POST", "/reads", CA,
               {"plate": "XXX111", "cam": "CAM-01"})
    check("S9 chain_auditor: barred from ingest", s == 403, b)
    # sentinel_audit: URL mode + DB mode against B (S16)
    for job in JOBS:
        req(pb, "POST", "/heartbeat", JOB,
            {"job": job, "ok": True, "detail": "audit run"})
    env = dict(os.environ)
    env.update({"NOCTUA_AUDIT_KEY": AUDIT_KEY})
    bpub = os.path.join(WORK, "b-pub-early.pem")
    with open(bpub, "w") as f:
        f.write(pub_pem(B.db))
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "sentinel_audit.py"),
                        "--url", B.url, "--user", AUD,
                        "--key", KEYS[AUD], "--pubkey", bpub],
                       env=env, capture_output=True, text=True,
                       timeout=120)
    check("S16 sentinel_audit URL mode: healthy partner passes",
          r.returncode == 0, r.stdout[-400:] + r.stderr[-200:])
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "sentinel_audit.py"),
                        "--url", B.url, "--user", AUD,
                        "--key", KEYS[AUD]],
                       env=env, capture_output=True, text=True,
                       timeout=120)
    check("P8 sentinel_audit URL mode: no key pin, no run",
          r.returncode != 0, r.stdout[-200:] + r.stderr[-200:])
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "sentinel_audit.py"),
                        "--db", B.db],
                       env=env, capture_output=True, text=True,
                       timeout=120)
    # exit contract: 0 clean, 1 warnings only, 2 failures. The two
    # filesystem stores warn by design in DB mode (their ages are
    # /health's job) — what "passes" means is zero FAILURES.
    try:
        rep = json.loads(r.stdout)
        fails = rep["summary"]["fail"]
    except Exception:
        fails = -1
    check("S16 sentinel_audit DB mode (read-only): healthy DB has "
          "zero failures", r.returncode in (0, 1) and fails == 0,
          r.stdout[-400:] + r.stderr[-200:])
    # compact.py end-to-end: A's auditor assesses B (S8)
    s, b = req(pa, "POST", "/compact/partners", SUP,
               {"agency": "agency-b", "endpoint": B.url,
                "pubkey_pem": pub_pem(B.db),
                "agreement_ref": "MOU-DEMO-2027"})
    assert s == 201, b
    pubfile = os.path.join(WORK, "b-pub.pem")
    with open(pubfile, "w") as f:
        f.write(pub_pem(B.db))
    env = dict(os.environ)
    env.update({"NOCTUA_AUDIT_KEY": AUDIT_KEY})
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "compact.py"),
         "--partner-url", B.url, "--partner-user", CA,
         "--partner-key", KEYS[CA], "--agency", "agency-b",
         "--partner-pubkey", pubfile,
         "--janus", A.url, "--auditor-user", AUD,
         "--auditor-key", KEYS[AUD], "--our-agency", "agency-a",
         "--receipt-user", "agency-a", "--receipt-key",
         KEYS["agency-a"], "--db", A.db,
         "--state", os.path.join(WORK, "compact-state.json")],
        env=env, capture_output=True, text=True, timeout=180)
    check("S18 compact.py end-to-end: independent recompute + signed "
          "report + receipt, exit 0", r.returncode == 0,
          r.stdout[-300:] + r.stderr[-300:])
    kinds, _ = audit_kinds(pa)
    check("S8 compact.py: COMPACT_AUDIT_RESULT chained on our side",
          "COMPACT_AUDIT_RESULT" in kinds)
    s, b = req(pb, "GET", "/compact/partners", SUP)
    row = [x for x in b["partners"] if x["agency"] == "agency-a"]
    check("S8 compact.py: B now shows agency-a's share gate open",
          row and row[0]["share_gate_open"] is True, b)


def suite_keyloss():
    C = Instance("c", 18096, audit_key=None, key_file=True)
    C.start()
    s, b = req(C.port, "POST", "/reads", ING,
               {"plate": "KEY100", "state": "AR", "cam": "CAM-01"})
    check("keyloss setup: key-file instance accepts reads",
          s == 201, b)
    C.stop()
    keyfile = C.db + ".audit_key"
    check("keyloss setup: audit key file minted at first boot",
          os.path.isfile(keyfile))
    saved = open(keyfile).read()
    # S18 named attack: booting with a DIFFERENT audit key against an
    # existing chain refuses outright (exit 3, never serves).
    env = dict(C.env)
    env["NOCTUA_AUDIT_KEY"] = "a-different-key-9999999999999999"
    r = subprocess.run([sys.executable, JANUS], env=env,
                       capture_output=True, text=True, timeout=60)
    check("S18 wrong audit key at boot => refuses to start "
          "(KEY_LOCKED)", r.returncode == 3
          and "REFUSES TO START" in r.stderr,
          r.stderr[-300:])
    # and with NO key at all: the boot refuses too, and nothing is
    # minted over the existing chain.
    os.remove(keyfile)
    r = subprocess.run([sys.executable, JANUS], env=dict(C.env),
                       capture_output=True, text=True, timeout=60)
    check("keyloss: missing key over an existing chain refuses to "
          "start (KEY_LOCKED)", r.returncode == 3
          and "REFUSES TO START" in r.stderr, r.stderr[-300:])
    check("keyloss: no new key minted over an existing chain",
          not os.path.exists(keyfile))
    with open(keyfile, "w") as f:
        f.write(saved)
    C.start()
    try:
        s, b = req(C.port, "GET", "/search?plate=KEY100"
                   "&case=2027-1001&justification=restore+check"
                   "&tier=2", DET)
        check("keyloss: original key restores service, data intact",
              s == 200 and len(b["reads"]) == 1, b)
    finally:
        C.stop()


def suite_retention():
    E = Instance("e", 18095)
    E.start()
    try:
        p = E.port
        s, b = req(p, "POST", "/hotlist", DET,
                   {"plate": "RET100", "state": "AR",
                    "category": "stolen vehicle", "case": "2027-1014"})
        assert s == 201, b
        hits = []
        for cam in ("CAM-01", "CAM-02"):
            s, b = req(p, "POST", "/reads", ING,
                       {"plate": "RET100", "state": "AR", "cam": cam,
                        "conf": 0.95})
            assert b["result"] == "ALERT", b
            hits.append(b["hit_id"])
        req(p, "POST", "/verify", DET,
            {"hit_id": hits[0], "decision": "confirm",
             "case": "2027-1014"})
        req(p, "POST", "/verify", DET,
            {"hit_id": hits[1], "decision": "reject",
             "case": "2027-1014"})
        # Tier 3 over RET100, executed while the reads are fresh (S2)
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "RET100", "case_id": "2027-1014",
                    "basis_type": "warrant",
                "auth_basis": "Warrant W-1 (DEMO)",
                    "why": "retention lifecycle test"})
        assert s == 201, b
        rid = b["request_id"]
        s, b = req(p, "POST", "/tier3/approve", SUP,
                   {"request_id": rid})
        assert s == 200, b
        s, b = req(p, "GET", "/tier3/results/%d" % rid, DET)
        check("retention setup: tier3 results live before aging",
              s == 200 and len(b["results"]["reads"]) == 2, b)
        # an expired hotlist membership for hotlist_sync (S5)
        s, b = req(p, "POST", "/hotlist", DET,
                   {"plate": "EXP200", "state": "AR",
                    "category": "watch", "case": "2027-1001",
                    "expires": ago_iso(hours=1)})
        assert s == 201, b
        env = dict(E.env)
        env["NOCTUA_JANUS_URL"] = E.url
        env["NOCTUA_JOBS_USER"] = JOB
        env["NOCTUA_JOBS_KEY"] = KEYS[JOB]
        r = subprocess.run([sys.executable,
                            os.path.join(SCRIPTS, "hotlist_sync.py")],
                           env=env, capture_output=True, text=True,
                           timeout=60)
        check("S18 hotlist_sync: expiry sweep runs clean",
              r.returncode == 0, r.stdout + r.stderr)
        s, b = req(p, "GET", "/hotlist", SUP)
        check("S5 hotlist_sync: expired membership deactivated",
              s == 200 and all(e["plate"] != "EXP200"
                               for e in b["entries"]), b)
        kinds, _ = audit_kinds(p)
        check("S5 hotlist_sync: expiry chained as HOTLIST_EXPIRED",
              "HOTLIST_EXPIRED" in kinds)
        h = health(p)
        check("S5 hotlist_sync: the monitored job now exists and "
              "reports ok", h["jobs"]["hotlist_sync"]["ok"] is True, h)
        # age the world past RETENTION_DAYS
        db = sqlite3.connect(E.db)
        old = ago_iso(days=20)
        db.execute("INSERT INTO reads(ts,cam,plate,plate_raw,state,"
                   "conf) VALUES(?,?,?,?,?,?)",
                   (old, "CAM-03", "OLD999", "OLD999", "AR", 0.9))
        db.execute("INSERT INTO case_searches(case_no, day, frag) "
                   "VALUES(?,?,?)",
                   ("2027-1014",
                    (datetime.now(timezone.utc)
                     - timedelta(days=20)).strftime("%Y-%m-%d"),
                    "OLD999"))
        db.execute("UPDATE reads SET ts=? WHERE plate='RET100'",
                   (old,))
        db.execute("UPDATE tier3_requests SET created_ts=? WHERE "
                   "id=?", (old, rid))
        db.execute("INSERT INTO tier3_requests(requester, "
                   "plate_fragment, case_no, basis_type, why, status, "
                   "results, results_count, created_ts) VALUES"
                   "('det.okafor','LEGACY','2027-1014','warrant','x',"
                   "'EXECUTED','{\"reads\":[{\"plate\":\"LEGACY1\"}]}'"
                   ",1,?)", (old,))
        legacy_id = db.execute("SELECT MAX(id) FROM tier3_requests"
                               ).fetchone()[0]
        db.commit()
        db.close()
        r = subprocess.run([sys.executable,
                            os.path.join(SCRIPTS, "retention.py")],
                           env=env, capture_output=True, text=True,
                           timeout=120)
        check("retention: registry-driven run exits 0",
              r.returncode == 0, r.stdout + r.stderr)
        db = sqlite3.connect(E.db)
        n_old = db.execute("SELECT COUNT(*) FROM reads WHERE "
                           "plate='OLD999'").fetchone()[0]
        n_cs = db.execute("SELECT COUNT(*) FROM case_searches"
                          ).fetchone()[0]
        frag = db.execute("SELECT plate_fragment FROM tier3_requests "
                          "WHERE id=?", (rid,)).fetchone()[0]
        legacy = db.execute("SELECT results FROM tier3_requests "
                            "WHERE id=?", (legacy_id,)).fetchone()[0]
        n_hits = db.execute("SELECT COUNT(*) FROM hits").fetchone()[0]
        db.close()
        check("retention: 20d-old read purged by registry class",
              n_old == 0)
        check("retention: case_searches purged", n_cs == 0)
        check("retention: tier3 fragment scrubbed to a ref at class "
              "age", frag.startswith("pref:"), frag)
        check("S2 retention: legacy serialized results body NULLed "
              "past class age", legacy is None, legacy)
        check("retention: hits survive (30d class, younger)",
              n_hits == 2)
        s, b = req(p, "GET", "/tier3/results/%d" % rid, DET)
        check("S18 populated Tier 3 results across a retention run: "
              "detail gone, plate-free summary served",
              s == 200 and b.get("expired") is True
              and "results" not in b, b)
        s, b = req(p, "GET", "/report", AUD)
        check("retention: report still counts the outcomes (K-ledger "
              "is permanent)", s == 200
              and b["lists"]["Local agency list"]["confirmed_matches"]
              == 1 and b["lists"]["Local agency list"]
              ["non_corresponding"] == 1, b)
        h = health(p)
        check("retention: heartbeat posted ok",
              h["jobs"]["retention"]["ok"] is True)
        check("S1 health: no retention breach after the run",
              h["degraded"]["retention_breach"] == [], h["degraded"])
    finally:
        E.stop()


def suite_p121():
    """1.2.1 patch items P1-P13: each check names the round-4
    finding it closes. Fail-before-fix: every one of these failed
    against janus12 (the cloud seat's attack suite numbers are
    cited per item)."""
    import socket as _socket
    import threading as _threading

    # ---------- unit level: chain v2 + spool + schema (P11/P10) --
    udir = os.path.join(WORK, "p121-unit")
    os.makedirs(udir)
    udb = os.path.join(udir, "u.db")
    ch = sentinel_mod.Chain(udb)
    ch.append("ONE", {"n": 1})
    ch.append("TWO", {"n": 2})
    v = ch.verify()
    check("P11 chain v2: fresh chain verifies", v["ok"] is True, v)
    c = sqlite3.connect(udb)
    c.execute("UPDATE audit SET kind='FORGED' WHERE seq=1")
    c.commit()
    v = ch.verify()
    check("P11 chain v2: rewriting the kind COLUMN breaks verify "
          "(A10 — kind/ts are inside the v2 hash)",
          v["ok"] is False and v["broken_at"] == 1, v)
    c.execute("UPDATE audit SET kind='ONE', ts='1999-01-01T00:00:00Z' "
              "WHERE seq=1")
    c.commit()
    v = ch.verify()
    check("P11 chain v2: rewriting the ts COLUMN breaks verify",
          v["ok"] is False and v["broken_at"] == 1, v)
    c.close()
    ch.db.close()
    # spool quarantine: a torn line must never fail a chained write
    sink = os.path.join(udir, "sinkdir")  # a DIRECTORY: writes fail
    spool = sink + ".spool"
    os.makedirs(sink)
    os.environ["NOCTUA_SENTINEL_SINK"] = sink
    try:
        ch2 = sentinel_mod.Chain(os.path.join(udir, "u2.db"))
        ch2.append("ONE", {"n": 1})  # sink down -> entry spools
        assert os.path.exists(spool)
        with open(spool, "a") as f:
            f.write('{"seq": 2, "hash": "torn-partial-line')
        os.rmdir(sink)  # sink comes back (path now free for a file)
        ch2.append("TWO", {"n": 2})  # drains the spool; must NOT raise
        kinds = [r[0] for r in ch2.db.execute(
            "SELECT kind FROM audit ORDER BY seq")]
        check("P11 spool: torn spool line quarantined, chained "
              "write succeeds, SPOOL_QUARANTINE chained (A11)",
              "SPOOL_QUARANTINE" in kinds
              and os.path.exists(spool + ".bad"), kinds)
        ch2.db.close()
    finally:
        os.environ.pop("NOCTUA_SENTINEL_SINK", None)
    # schema allowlist bites on a poisoned schema (A16)
    pdb = os.path.join(udir, "poison.db")
    pc = sqlite3.connect(pdb)
    pc.execute("CREATE TABLE reads(id INTEGER, plate TEXT, "
               "vehicle_tag TEXT)")
    pc.execute("CREATE TABLE ocr_cache(id INTEGER, raw_event TEXT)")
    pc.commit()
    unreg = {"%s.%s" % tc for tc in sentinel_mod.schema_unregistered(pc)}
    pc.close()
    check("P10 schema allowlist: unregistered column AND table "
          "both named (A16)",
          "reads.vehicle_tag" in unreg and "ocr_cache.raw_event"
          in unreg, unreg)
    # rotation.py --verify pin (P8)
    sdb = os.path.join(udir, "sched.db")
    sentinel_mod.ensure_signing_key(sdb)
    doc = rotation_mod.build_schedule(["a1", "a2", "a3"],
                                      "2027-01-04", 30)
    doc["sig"] = sentinel_mod.sign_bytes(
        sdb + ".signing_key.pem",
        sentinel_mod.canonical_bytes(rotation_mod.signed_portion(doc)))
    doc["sig_alg"] = "ed25519"
    doc["pubkey"] = pub_pem(sdb)
    spath = os.path.join(udir, "sched.json")
    with open(spath, "w") as f:
        json.dump(doc, f)
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "rotation.py"),
                        "--verify", spath],
                       capture_output=True, text=True, timeout=60)
    check("P8 rotation --verify: signed schedule without a pin is "
          "refused (never verify against the embedded key)",
          r.returncode == 2, r.stdout + r.stderr)
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "rotation.py"),
                        "--verify", spath, "--pubkey",
                        sdb + ".signing_pub.pem"],
                       capture_output=True, text=True, timeout=60)
    check("P8 rotation --verify: pinned key verifies",
          r.returncode == 0, r.stdout + r.stderr)
    # compact.py pin refusal (P8)
    env = dict(os.environ)
    env.update({"NOCTUA_AUDITOR_KEY": "x"})
    r = subprocess.run([sys.executable,
                        os.path.join(SCRIPTS, "compact.py"),
                        "--partner-url", "http://127.0.0.1:1",
                        "--partner-user", "ca.external",
                        "--partner-key", "x",
                        "--agency", "agency-b", "--our-agency",
                        "agency-a", "--janus", "http://127.0.0.1:1",
                        "--auditor-user", "auditor.external",
                        "--db", udb],
                       env=env, capture_output=True, text=True,
                       timeout=60)
    check("P8 compact.py: no --partner-pubkey/--partner-fingerprint, "
          "no run (A23)", r.returncode == 2
          and "refusing to run" in r.stderr, r.stderr[-200:])

    # ---------- server-level ----------
    P = Instance("p121", 18097)
    P.start()
    p = P.port
    try:
        # P11/A13: first config load chained, SYSTEM carries hash
        _k, entries = audit_kinds(p)
        cc = [e for e in entries if e["kind"] == "CONFIG_CHANGED"]
        sys_e = [e for e in entries if e["kind"] == "SYSTEM"]
        check("P11 first boot chains CONFIG_CHANGED carrying the "
              "config hash; SYSTEM carries it too (A13)",
              cc and cc[0]["fields"].get("config_hash")
              and sys_e and sys_e[0]["fields"].get("config_hash"),
              (cc[:1], sys_e[:1]))
        # P3: suppression placed AFTER the hit (A5)
        s, b = req(p, "POST", "/hotlist", DET,
                   {"plate": "P121AA", "state": "AR",
                    "category": "stolen vehicle", "case": "2027-1014"})
        assert s == 201, b
        s, b = req(p, "POST", "/reads", ING,
                   {"plate": "P121AA", "cam": "CAM-01"})
        assert s == 201 and b["result"] == "ALERT", b
        hit = b["hit_id"]
        s, b = req(p, "GET", "/hits", DET)
        check("P3 setup: hit visible before the order",
              any(h["id"] == hit for h in b["hits"]))
        s, b = req(p, "POST", "/suppressions", SUP,
                   {"plate": "P121AA",
                    "order_ref": "PO-P121 (DEMO)"})
        assert s in (200, 201), b
        s, b = req(p, "GET", "/hits", DET)
        check("P3 suppression is query-time: the pre-existing hit "
              "leaves /hits the moment the order lands (A5)",
              s == 200 and all(h["id"] != hit for h in b["hits"]), b)
        s, b = req(p, "GET", "/suppressed-hits", SUP)
        check("P3: the hit routes to the supervisor queue instead",
              s == 200 and any(h["id"] == hit for h in b["hits"]), b)
        s, b = req(p, "POST", "/verify", DET,
                   {"hit_id": hit, "decision": "confirm",
                    "case": "2027-1014"})
        check("P3: detective verify of a now-suppressed hit refused",
              s == 403, b)
        s, b = req(p, "POST", "/evidence/export", DET,
                   {"hit_id": hit, "case_id": "2027-1014"})
        check("P3: detective export of a now-suppressed hit refused",
              s == 403, b)
        # P12: approver visibility (R17)
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "P121", "case_id": "2027-1023",
                    "basis_type": "warrant",
                    "auth_basis": "Warrant W-P121 (DEMO)",
                    "why": "locate the suspect vehicle"})
        assert s == 201, b
        rid = b["request_id"]
        s, b = req(p, "GET", "/tier3/pending", SUP)
        row = next((r for r in b["pending"] if r.get("id") == rid),
                   {})
        check("P12 supervisor approver sees fragment, case, why, "
              "basis, tier, requester (R17)",
              all(row.get(k) for k in ("plate_fragment", "case_no",
                                       "why", "auth_basis"))
              and row.get("tier") == 3 and row.get("requester"),
              row)
        s, b = req(p, "GET", "/tier3/pending", PAT)
        check("P12 patrol still sees only its own requests, "
              "plate-free",
              s == 200 and all("plate_fragment" not in r
                               for r in b["pending"]), b)
        # P13: holds validation
        s, b = req(p, "POST", "/holds", DET,
                   {"scope": "hit", "ref": hit, "reason": "demo",
                    "review_by": "2020-01-01"})
        check("P13 hold: review_by in the past refused", s == 400, b)
        s, b = req(p, "POST", "/holds", DET,
                   {"scope": "hit", "ref": hit, "reason": "demo",
                    "review_by": "not-a-date"})
        check("P13 hold: non-date review_by refused", s == 400, b)
        far = (datetime.now(timezone.utc).date()
               + timedelta(days=40)).isoformat()
        s, b = req(p, "POST", "/holds", DET,
                   {"scope": "hit", "ref": hit, "reason": "demo",
                    "review_by": far})
        check("P13 hold: review_by beyond HOLD_DAYS (30) refused",
              s == 400, b)
        near = (datetime.now(timezone.utc).date()
                + timedelta(days=10)).isoformat()
        s, b = req(p, "POST", "/holds", DET,
                   {"scope": "hit", "ref": hit, "reason": "demo",
                    "review_by": near})
        check("P13 hold: in-window review_by accepted", s == 201, b)
        # P13: DELETE /hotlist deletes the row (A24)
        s, b = req(p, "POST", "/hotlist", DET,
                   {"plate": "DEL121", "state": "AR",
                    "category": "stolen vehicle", "case": "2027-1014"})
        assert s == 201, b
        s, b = req(p, "DELETE", "/hotlist", SUP,
                   {"plate": "NOPE99", "state": "AR"})
        check("P13 DELETE /hotlist: no match is a 404, never a "
              "success message (A24)", s == 404, b)
        s, b = req(p, "DELETE", "/hotlist", SUP,
                   {"plate": "DEL121", "state": "AR"})
        check("P13 DELETE /hotlist: the membership is DELETED",
              s == 200, b)
        dbc = sqlite3.connect(P.db)
        n = dbc.execute("SELECT COUNT(*) FROM hotlist_members "
                        "WHERE plate='DEL121'").fetchone()[0]
        dbc.close()
        check("P13 DELETE /hotlist: row gone from the table (not "
              "merely deactivated)", n == 0, n)
        _k, entries = audit_kinds(p)
        rm = [e for e in entries if e["kind"] == "HOTLIST_REMOVE"]
        check("P13 DELETE /hotlist: HOTLIST_REMOVE chained with "
              "plate_ref", rm and rm[0]["fields"].get("plate_ref"),
              rm[:1])
        # P2: hotlist_sync — '' means NO expiry (A1)
        s, b = req(p, "POST", "/hotlist", DET,
                   {"plate": "KEEP121", "state": "AR",
                    "category": "stolen vehicle", "case": "2027-1014"})
        assert s == 201, b
        s, b = req(p, "POST", "/hotlist", DET,
                   {"plate": "GONE121", "state": "AR",
                    "category": "stolen vehicle", "case": "2027-1014",
                    "expires": ago_iso(days=1)})
        assert s == 201, b
        env = dict(os.environ)
        env.update({"NOCTUA_DB": P.db, "NOCTUA_JANUS_URL": "",
                    "NOCTUA_AUDIT_KEY": AUDIT_KEY})
        r = subprocess.run([sys.executable, os.path.join(
            SCRIPTS, "hotlist_sync.py")], env=env,
            capture_output=True, text=True, timeout=60)
        dbc = sqlite3.connect(P.db)
        keep = dbc.execute("SELECT active FROM hotlist_members "
                           "WHERE plate='KEEP121'").fetchone()[0]
        gone = dbc.execute("SELECT active FROM hotlist_members "
                           "WHERE plate='GONE121'").fetchone()[0]
        dbc.close()
        check("P2 hotlist_sync: an entry with NO expiry survives "
              "the sweep; a past-expiry entry is swept (A1)",
              r.returncode == 0 and keep == 1 and gone == 0,
              (r.stdout[-150:], keep, gone))
        _k, entries = audit_kinds(p)
        check("P2 hotlist_sync: HOTLIST_EXPIRED chained",
              "HOTLIST_EXPIRED" in _k)
        # P1: share tier strict (A2)
        s, b = req(p, "POST", "/compact/partners", SUP,
                   {"agency": "agency-a", "endpoint": "http://x",
                    "pubkey_pem": pub_pem(P.db),
                    "agreement_ref": "MOU-P121"})
        assert s in (201, 409), b
        for tier, label in ((1, "tier=1"), (True, "tier=true"),
                            ("2", "tier='2' (string)"),
                            (2.0, "tier=2.0 (float)")):
            s, b = req(p, "POST", "/share/query", "agency-a",
                       {"agency": "agency-a", "tier": tier,
                        "plate_fragment": "P121",
                        "case_ref": "2027-1014", "why": "audit",
                        "basis_type": "court_order"})
            check("P1 share: %s refused as SHARE_BLOCKED/tier (A2)"
                  % label, s == 403 and b.get("missing") == "tier",
                  b)
        _k, entries = audit_kinds(p)
        sb = [e for e in entries if e["kind"] == "SHARE_BLOCKED"
              and e["fields"].get("missing") == "tier"]
        check("P1 share: refused tiers chained as coded values",
              len(sb) >= 4 and all("tier_refused" in e["fields"]
                                   for e in sb), sb[:1])
        # P7: audit-result binding (A3)
        s, b = post_audit_result(p, P.db, "agency-a", True)
        check("P7 audit-result: a fresh, correctly-bound report is "
              "accepted", s == 201, b)
        report = {"agency": "agency-b", "ok": True,
                  "ts": sentinel_mod.now_iso(), "checks": {}}
        s, b = req(p, "POST", "/compact/audit-result", AUD,
                   {"agency": "agency-a", "report": report,
                    "report_sig": sign(P.db, report)})
        check("P7 audit-result: a report naming a DIFFERENT agency "
              "than it is filed under is refused (A3)",
              s == 400, b)
        report = {"agency": "agency-a", "ok": True,
                  "ts": ago_iso(days=2), "checks": {}}
        s, b = req(p, "POST", "/compact/audit-result", AUD,
                   {"agency": "agency-a", "report": report,
                    "report_sig": sign(P.db, report)})
        check("P7 audit-result: a report older than 26h is refused "
              "as stale (A3)", s == 409, b)
        # P9: rotation delinquency + witness (A25)
        s, b = req(p, "POST", "/compact/partners", SUP,
                   {"agency": "agency-b", "endpoint": "http://x",
                    "pubkey_pem": pub_pem(P.db),
                    "agreement_ref": "MOU-P121"})
        assert s in (201, 409), b
        past = (datetime.now(timezone.utc).date()
                - timedelta(days=40)).isoformat()
        s, b = req(p, "POST", "/compact/rotation", SUP,
                   {"cycle_start": past, "period_days": 7,
                    "members": ["THIS-AGENCY", "agency-a"]})
        check("P9 rotation: home agency may be a member without "
              "registering as its own partner", s == 201, b)
        s, b = req(p, "GET", "/compact/rotation/status", SUP)
        check("P9 delinquency: completed rounds with no filing "
              "mark BOTH direction-correct debtors delinquent",
              s == 200 and b["delinquent_agencies"] ==
              ["THIS-AGENCY", "agency-a"]
              and all(r["completed"] and r["delinquent"]
                      for r in b["rounds"]), b)
        s, b = req(p, "POST", "/compact/witness", ING,
                   {"agency": "agency-a", "cycle_start": past,
                    "round": 1, "ok": True})
        check("P9 witness: the ingest service account cannot "
              "attest (A25)", s == 403, b)
        s, b = req(p, "POST", "/compact/witness", DET,
                   {"agency": "agency-a", "cycle_start": past,
                    "round": 1, "ok": True})
        check("P9 witness: an unsigned non-supervisor attestation "
              "is refused (A25)", s == 403, b)
        s, b = req(p, "POST", "/compact/witness", SUP,
                   {"agency": "agency-a", "cycle_start": past,
                    "round": 1, "ok": True})
        check("P9 witness: a supervisor attestation is recorded",
              s == 201, b)
        _k, entries = audit_kinds(p)
        check("P9 witness: WITNESS_ATTEST chained",
              "WITNESS_ATTEST" in _k)
        # partner-key signed attestation
        wdb = os.path.join(WORK, "p121-witness-key.db")
        sentinel_mod.ensure_signing_key(wdb)
        s, b = req(p, "POST", "/compact/partners", SUP,
                   {"agency": "agency-w", "endpoint": "http://x",
                    "pubkey_pem": pub_pem(wdb),
                    "agreement_ref": "MOU-P121"})
        assert s in (201, 409), b
        att = {"agency": "agency-w", "cycle_start": past,
               "round": 1, "ok": True}
        sig = sentinel_mod.sign_bytes(
            wdb + ".signing_key.pem",
            sentinel_mod.canonical_bytes(att))
        s, b = req(p, "POST", "/compact/witness", AUD,
                   dict(att, signature=sig))
        check("P9 witness: the partner's registered auditor "
              "identity attests with a valid Ed25519 signature",
              s == 201, b)
        # void + future cycle: future rounds never delinquent
        req(p, "POST", "/compact/rotation/void", SUP, {})
        s, b = req(p, "POST", "/compact/rotation/void", AUD, {})
        assert s == 200, b
        future = (datetime.now(timezone.utc).date()
                  + timedelta(days=30)).isoformat()
        s, b = req(p, "POST", "/compact/rotation", SUP,
                   {"cycle_start": future, "period_days": 7,
                    "members": ["THIS-AGENCY", "agency-a"]})
        assert s == 201, b
        s, b = req(p, "GET", "/compact/rotation/status", SUP)
        check("P9 delinquency: future rounds NEVER count",
              s == 200 and b["delinquent_agencies"] == []
              and all(not r["completed"] for r in b["rounds"]), b)
        # P13: negative Content-Length (raw socket)
        sock = _socket.create_connection(("127.0.0.1", p), timeout=5)
        sock.sendall(("POST /reads HTTP/1.1\r\nHost: x\r\n"
                      "Content-Length: -5\r\n"
                      "X-Noctua-User: %s\r\nX-Noctua-Key: %s\r\n"
                      "\r\n" % (ING, KEYS[ING])).encode())
        resp = sock.recv(4096).decode("utf-8", "replace")
        sock.close()
        check("P13: negative Content-Length refused with 400",
              " 400 " in resp.splitlines()[0], resp.splitlines()[:1])
        # P13: route enumeration — every GET data route applies
        # the stale-config fail-close
        src = open(JANUS).read()
        get_region = src[src.index("def _get(self):"):]
        import re as _re
        segments = _re.split(r"\n        if (?=base|path)", get_region)
        data_routes = ("/search", "/hits", "/suppressed-hits",
                       "/hotlist", "/stats", "/report",
                       "/tier3/pending", "/tier3/reviews",
                       "/tier3/results")
        missing = []
        for seg in segments:
            named = [r for r in data_routes if '"%s"' % r in seg
                     or 'startswith("%s' % r in seg]
            if named and "config_closed" not in seg:
                missing.extend(named)
        check("P13 route enumeration: every GET data route (incl. "
              "tier3 results) applies config_closed()",
              not missing, missing)
    finally:
        P.stop()
    suite_p121_boots()


def suite_p121_boots():
    """Boot-shaped 1.2.1 checks: HOLD_DAYS ceiling (P13/A37), the
    restore marker under KEY_LOCKED (A29), NOCTUA_BACKUP_DIR in the
    breach check (A30), the A18 verify stall, and the P4 migration
    from a database actually built by janus11."""
    import threading as _threading

    # P13/A37: HOLD_DAYS above the statutory ceiling refuses to start
    d = os.path.join(WORK, "p121-hd")
    os.makedirs(d)
    env = dict(os.environ)
    env.update({"NOCTUA_DB": os.path.join(d, "x.db"),
                "NOCTUA_USERS": os.path.join(d, "u.json"),
                "NOCTUA_CASES": os.path.join(d, "c.json"),
                "NOCTUA_CAMERAS": os.path.join(d, "cam.json"),
                "NOCTUA_PORT": "18088", "HOLD_DAYS": "400",
                "NOCTUA_AUDIT_KEY": AUDIT_KEY})
    write_users(env["NOCTUA_USERS"])
    write_cases(env["NOCTUA_CASES"])
    write_cameras(env["NOCTUA_CAMERAS"])
    r = subprocess.run([sys.executable, JANUS], env=env,
                       capture_output=True, text=True, timeout=15)
    check("P13 HOLD_DAYS=400: Janus refuses to start above the "
          "150-day ceiling (A37)", r.returncode != 0
          and "HOLD_DAYS" in (r.stdout + r.stderr),
          (r.stdout + r.stderr)[-200:])

    # A30: NOCTUA_BACKUP_DIR honored by /health retention_breach
    bkdir = os.path.join(WORK, "p121-backups")
    old_set = os.path.join(bkdir, "backup-20261001T000000Z")
    os.makedirs(old_set)
    old = time.time() - 40 * 86400
    os.utime(old_set, (old, old))
    B2 = Instance("p121-bk2", 18090, env_extra={
        "NOCTUA_BACKUP_DIR": bkdir})
    B2.start()
    try:
        h = health(B2.port)
        check("P10 /health retention_breach honors "
              "NOCTUA_BACKUP_DIR (A30)",
              "backups" in h["degraded"]["retention_breach"],
              h["degraded"]["retention_breach"])
    finally:
        B2.stop()

    # A29: a KEY_LOCKED boot must not consume the restore marker
    M = Instance("p121-marker", 18088)
    M.start()
    M.stop()
    marker = M.db + ".restore_marker"
    with open(marker, "w") as f:
        f.write(json.dumps({"restored_from": "test"}))
    env = dict(M.env)
    env["NOCTUA_AUDIT_KEY"] = "the-wrong-key-entirely"
    proc = subprocess.Popen([sys.executable, JANUS], env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=10)
    check("A29 setup: wrong-key boot is KEY_LOCKED (process exits)",
          proc.returncode not in (0, None), proc.returncode)
    check("P11/A29: the KEY_LOCKED boot did NOT consume the "
          "restore marker", os.path.exists(marker))
    M.start()
    try:
        kinds, _ = audit_kinds(M.port)
        check("A29: the next good boot chains RESTORE from the "
              "surviving marker", "RESTORE" in kinds, kinds[-6:])
        check("A29: marker consumed after the successful boot",
              not os.path.exists(marker))
    finally:
        M.stop()

    # A18: /audit/verify must not stall ingest behind DBLOCK
    G = Instance("p121-big", 18091)
    gdb = sqlite3.connect(G.db)
    gdb.execute("CREATE TABLE IF NOT EXISTS audit("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT "
                "NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, "
                "prev TEXT NOT NULL, hash TEXT NOT NULL)")
    prev, batch = "GENESIS", []
    for i in range(250000):
        payload = json.dumps(
            {"ts": "2026-06-01T00:00:00Z", "kind": "QUERY",
             "user": "det.okafor", "type": "tier2 search", "tier": 2,
             "case_hash": "%064x" % i, "why_hash": "%064x" % (i * 7),
             "plate_ref": "pref:%024x" % i, "result_count": i % 9,
             "window_hours": 24.0}, sort_keys=True,
            separators=(",", ":"))
        hh = hashlib.sha256((prev + "|" + payload).encode()).hexdigest()
        batch.append(("2026-06-01T00:00:00Z", "QUERY", payload,
                      prev, hh))
        prev = hh
        if len(batch) == 50000:
            gdb.executemany("INSERT INTO audit(ts,kind,payload,prev,"
                            "hash) VALUES(?,?,?,?,?)", batch)
            batch = []
    if batch:
        gdb.executemany("INSERT INTO audit(ts,kind,payload,prev,"
                        "hash) VALUES(?,?,?,?,?)", batch)
    gdb.commit()
    gdb.close()
    with open(G.db + ".audit_key", "w") as f:
        f.write(AUDIT_KEY)
    G.start()
    try:
        out = {}

        def call_verify():
            out["verify"] = req(G.port, "GET", "/audit/verify", CA)
        t = _threading.Thread(target=call_verify)
        t.start()
        time.sleep(0.3)
        t0 = time.time()
        s, b = req(G.port, "GET", "/hits", DET)
        dt = time.time() - t0
        alive = t.is_alive()
        t.join(timeout=120)
        check("P13 /audit/verify on a 250k-entry chain does not "
              "stall a concurrent read behind DBLOCK (A18)",
              s == 200 and dt < 1.0 and alive,
              {"read_s": round(dt, 3), "verify_alive": alive})
        check("A18: the detached verify itself completes ok",
              out.get("verify", (None, {}))[1].get("ok") is True,
              out.get("verify"))
    finally:
        G.stop()

    # P4: migration from a database built by the 1.1 code
    janus11 = os.path.join(ROOT, "..", "janus11", "janus.py")
    d = os.path.join(WORK, "p121-mig")
    os.makedirs(d)
    mdb = os.path.join(d, "janus.db")
    menv = dict(os.environ)
    # The 1.1 deployment shape the A28 fix blesses: NO env key —
    # janus11 mints the audit key FILE beside the DB at first
    # boot, and 1.2.1 pins from that file on upgrade. (An env-key
    # 1.1 deployment upgrades by placing the same key in the file;
    # an unverifiable env key over an existing unpinned chain is
    # refused — that refusal IS the A28 fix.)
    menv.pop("NOCTUA_AUDIT_KEY", None)
    menv.update({"NOCTUA_DB": mdb,
                 "NOCTUA_USERS": os.path.join(d, "users.json"),
                 "NOCTUA_CASES": os.path.join(d, "cases.json"),
                 "NOCTUA_CAMERAS": os.path.join(d, "cameras.json"),
                 "NOCTUA_PORT": "18089",
                 "NOCTUA_EVIDENCE_DIR": os.path.join(d, "evidence")})
    write_users(menv["NOCTUA_USERS"])
    write_cases(menv["NOCTUA_CASES"])
    write_cameras(menv["NOCTUA_CAMERAS"])

    def boot(script, env):
        proc = subprocess.Popen([sys.executable, script], env=env,
                                stdout=open(os.path.join(
                                    d, "boot.log"), "w"),
                                stderr=subprocess.STDOUT)
        for _ in range(60):
            if proc.poll() is not None:
                break
            try:
                # janus11 has no /ping; any HTTP answer means up.
                req(18089, "GET", "/health", SUP)
                return proc
            except Exception:
                pass
            time.sleep(0.25)
        proc.terminate()
        raise RuntimeError("boot failed for %s" % script)

    proc = boot(janus11, menv)
    try:
        s, b = req(18089, "POST", "/reads", ING,
                   {"plate": "vic 309", "cam": "CAM-01"})
        assert s == 201, b
        s, b = req(18089, "POST", "/reads", ING,
                   {"plate": "ctl 100", "cam": "CAM-01"})
        assert s == 201, b
        s, b = req(18089, "POST", "/suppressions", SUP,
                   {"plate": "VIC309", "order_ref": "PO-P4 (DEMO)"})
        assert s in (200, 201), b
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    dbc = sqlite3.connect(mdb)
    legacy = dbc.execute("SELECT plate FROM reads WHERE "
                         "plate LIKE 'VIC%'").fetchone()[0]
    dbc.close()
    check("P4 setup: the 1.1 code stored the read unnormalized",
          legacy == "VIC 309", legacy)
    proc = boot(JANUS, menv)
    try:
        dbc = sqlite3.connect(mdb)
        row = dbc.execute("SELECT plate, plate_raw FROM reads "
                          "WHERE plate LIKE 'VIC%'").fetchone()
        dbc.close()
        check("P4 migration: legacy reads.plate normalized at "
              "first 1.2.1 boot, original preserved in plate_raw",
              row == ("VIC309", "VIC 309"), row)
        kinds, entries = audit_kinds(18089)
        mig = [e for e in entries if e["kind"] == "MIGRATION"]
        check("P4 migration: MIGRATION chained with row counts",
              mig and mig[0]["fields"].get(
                  "reads_plate_normalized", 0) >= 1, mig[:1])
        s, b = req(18089, "GET",
                   "/search?plate=VIC309&case=2027-1014"
                   "&justification=migration&tier=2", DET)
        check("P4 migration: the pre-upgrade suppression matches "
              "the legacy read again (search excludes it)",
              s == 200 and b["reads"] == [], b)
        s, b = req(18089, "GET",
                   "/search?plate=CTL100&case=2027-1014"
                   "&justification=migration&tier=2", DET)
        check("P4 migration: the un-suppressed legacy read is "
              "found, normalized", s == 200
              and len(b["reads"]) == 1
              and b["reads"][0]["plate"] == "CTL100", b)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def suite_demo():
    D = Instance("demo", 18094)
    users = [{"user": u, "role": ROLES[u], "key_sha256": sha(k)}
             for u, k in KEYS.items() if u in (
                 "det.okafor", "ofc.chen", "sgt.reyes",
                 "auditor.external", "ingest.local", "jobs.local")]
    with open(D.users, "w") as f:
        json.dump(users, f, indent=1)
    D.start()
    try:
        env = dict(os.environ)
        env.update({"NOCTUA_DB": D.db, "NOCTUA_USERS": D.users,
                    "NOCTUA_CASES": D.cases,
                    "NOCTUA_CAMERAS": D.cameras,
                    "NOCTUA_JANUS_URL": D.url,
                    "NOCTUA_INGEST_KEY": KEYS["ingest.local"],
                    "NOCTUA_SUPERVISOR_KEY": KEYS["sgt.reyes"],
                    "NOCTUA_DETECTIVE_KEY": KEYS["det.okafor"]})
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "demo", "seed_demo.py")],
                           env=env, capture_output=True, text=True,
                           timeout=600)
        check("demo: seed runs clean against 1.2.1",
              r.returncode == 0, (r.stdout + r.stderr)[-500:])
        s, b = req(D.port, "GET", "/stats", "sgt.reyes")
        check("demo: stats carry reads/hits/pending/"
              "suppressed_pending", s == 200 and all(
                  k in b for k in ("reads", "hits", "pending",
                                   "suppressed_pending")), b)
        check("demo: suppressed queue holds the protected vehicle's "
              "hits", b.get("suppressed_pending") == 2, b)
    finally:
        D.stop()


if __name__ == "__main__":
    sys.exit(main())
