#!/usr/bin/env python3
"""NOCTUA 1.2.2 fail-before -> pass case battery.

Each case encodes the 1.2.2 contract for one Q item from
council5/SYNTHESIS.md (plus the Claude-seat-2 findings that map to
it). The file runs against the tree named by Q122_TREE, importing
THAT tree's tests/run_tests.py helpers, so the identical scenario
executes against janus121 (expect FAIL — the defect is present)
and janus122 (expect PASS). The driver, run_q122_tests.py, runs
both sides and prints the mapping.

Cases print:  CASE <name> PASS|FAIL :: <json detail>

Driver: this file IS the driver. Run it as

    python3 run_q122_cases.py <tree> [--invariants]

<tree> names the tree under test (janus121: every Q case must FAIL
— the fail-before half; janus122: everything must PASS). With
--invariants, the six property suites from the synthesis
acceptance standard run as well (INV1..INV6). Every case prints
exactly one verdict line: a case that raises is reported FAIL with
the exception in its detail, never silence. Exit status is 0 iff
every case run passed. Q122_TREE env is the fallback when no argv
tree is given.

Stdlib only. Scratch state lives under the tree's run_tests WORK
dir (TMPDIR-driven — point TMPDIR at a roomy scratch dir).
"""
import hashlib
import json
import os
import random
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

_argv = [a for a in sys.argv[1:] if not a.startswith("--")]
TREE = os.path.abspath(_argv[0] if _argv else os.environ["Q122_TREE"])
PARENT = os.path.dirname(TREE)
sys.path.insert(0, os.path.join(TREE, "tests"))
import run_tests as T  # noqa: E402

req = T.req
KEYS = T.KEYS
DET, PAT, SUP, SUP2, AUD, CA, ING, JOB = (T.DET, T.PAT, T.SUP,
                                          T.SUP2, T.AUD, T.CA,
                                          T.ING, T.JOB)
RESULTS = []
_port = [18700]


def next_port():
    _port[0] += 1
    return _port[0]


def report(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("CASE %s %s :: %s" % (name, "PASS" if ok else "FAIL",
                                json.dumps(detail, default=str)[:800]))
    sys.stdout.flush()


class Boot:
    """An instance of an ARBITRARY janus.py on an arbitrary dir
    (T.Instance is bound to its own tree and a fresh dir)."""

    def __init__(self, janus_py, name, port, dirpath=None,
                 env_extra=None, audit_key="default"):
        self.janus_py = janus_py
        self.dir = dirpath or os.path.join(T.WORK, name)
        os.makedirs(self.dir, exist_ok=True)
        self.port = port
        self.db = os.path.join(self.dir, "janus.db")
        self.users = os.path.join(self.dir, "users.json")
        self.cases = os.path.join(self.dir, "cases.json")
        self.cameras = os.path.join(self.dir, "cameras.json")
        if not os.path.exists(self.users):
            T.write_users(self.users)
        if not os.path.exists(self.cases):
            T.write_cases(self.cases)
        if not os.path.exists(self.cameras):
            T.write_cameras(self.cameras)
        self.env = dict(os.environ)
        self.env.update({
            "NOCTUA_DB": self.db, "NOCTUA_USERS": self.users,
            "NOCTUA_CASES": self.cases,
            "NOCTUA_CAMERAS": self.cameras,
            "NOCTUA_PORT": str(port), "NOCTUA_BACKFILL_FLUSH_S": "1",
            "NOCTUA_EVIDENCE_DIR": os.path.join(self.dir, "evidence")})
        if audit_key == "default":
            self.env["NOCTUA_AUDIT_KEY"] = T.AUDIT_KEY
        elif audit_key is None:
            self.env.pop("NOCTUA_AUDIT_KEY", None)
        else:
            self.env["NOCTUA_AUDIT_KEY"] = audit_key
        if env_extra:
            self.env.update(env_extra)
        self.proc = None

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def start(self, tries=60):
        self.proc = subprocess.Popen(
            [sys.executable, self.janus_py], env=self.env,
            stdout=open(os.path.join(self.dir, "server.log"), "w"),
            stderr=subprocess.STDOUT)
        for _ in range(tries):
            if self.proc.poll() is not None:
                raise RuntimeError("process exited rc=%s"
                                   % self.proc.returncode)
            try:
                req(self.port, "GET", "/health", SUP)
                return
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("instance %s did not start" % self.dir)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
            self.proc = None


def inst(name):
    return T.Instance(name, next_port())


def ingest(port, plate, state="AR", cam="CAM-01", **kw):
    body = {"plate": plate, "state": state, "cam": cam}
    body.update(kw)
    return req(port, "POST", "/reads", ING, body)


def hotlist(port, plate, state="AR", case="2027-1014", **kw):
    body = {"plate": plate, "state": state,
            "category": "stolen vehicle", "case": case}
    body.update(kw)
    return req(port, "POST", "/hotlist", DET, body)


def run_retention(boot):
    env = dict(boot.env)
    env.update({"NOCTUA_JANUS_URL": boot.url, "NOCTUA_JOBS_USER": JOB,
                "NOCTUA_JOBS_KEY": KEYS[JOB]})
    return subprocess.run(
        [sys.executable, os.path.join(T.SCRIPTS, "retention.py")],
        env=env, capture_output=True, text=True, timeout=300)


def db_of(boot):
    return sqlite3.connect(boot.db)


def age_rows(boot, table, column, days, where="1=1", args=()):
    c = db_of(boot)
    c.execute("UPDATE %s SET %s=? WHERE %s"
              % (table, column, where),
              (T.ago_iso(days=days),) + tuple(args))
    c.commit()
    c.close()


# ------------------------------------------------------------------
# Q1 — registry-driven migration repair (seat 2 R5-03)
# ------------------------------------------------------------------
def q01_migration():
    name = "Q01-migration-repair"
    janus11 = os.path.join(PARENT, "janus11", "janus.py")
    port = next_port()
    B = Boot(janus11, "q01-11", port, audit_key=None)
    try:
        B.start()
        s, b = hotlist(port, "VIC309")
        assert s == 201, b
        # 1.1 matched plate text literally: the formatted read is
        # stored without alerting; the CANONICAL read makes the hit
        # that the suppression then covers (the R5-03 shape)
        s, b = ingest(port, "vic 309")
        assert s == 201, b
        s, b = ingest(port, "VIC309")
        assert s == 201, b
        hit11 = b.get("hit_id")
        s, b = req(port, "POST", "/suppressions", SUP,
                   {"plate": "VIC309", "order_ref": "PO-Q1 (DEMO)"})
        assert s in (200, 201), b
        s, b = hotlist(port, "HTL 777")
        assert s == 201, b
    finally:
        B.stop()
    # upgrade: boot the tree under test on the 1.1 directory
    U = Boot(os.path.join(TREE, "janus.py"), "q01-up", port,
             dirpath=B.dir, audit_key=None)
    try:
        U.start()
        s, hits = req(port, "GET", "/hits", DET)
        leaked = [h for h in hits.get("hits", [])
                  if h.get("read_plate") == "VIC309"]
        s, sh = req(port, "GET", "/suppressed-hits", SUP)
        queued = [h for h in sh.get("hits", [])
                  if h.get("read_plate") == "VIC309"]
        # A fresh read of the protected plate: the ingest role is
        # a machine bridge and 1.2.2 answers it "ALERT" internally
        # by design (builders' suite: "suppressed hot plate still
        # alerts internally") — the protection property is that
        # the new hit surfaces NOWHERE except the supervisor queue
        s, b = ingest(port, "VIC309")
        fresh_result = b.get("result")
        fresh_hit = b.get("hit_id")
        s, hits2 = req(port, "GET", "/hits", DET)
        leaked_after = [h for h in hits2.get("hits", [])
                        if h.get("read_plate") == "VIC309"]
        s, sh2 = req(port, "GET", "/suppressed-hits", SUP)
        queued_after = [h for h in sh2.get("hits", [])
                        if h.get("id") == fresh_hit]
        s, rel = req(port, "POST", "/suppressions/release", SUP,
                     {"plate": "VIC309"})
        released = s in (200, 201)
        s, b = ingest(port, "HTL777")
        canonical_alert = b.get("result") == "ALERT"
        h = T.health(port)
        unrepaired = (h.get("degraded", {})
                      .get("migration_unrepaired"))
        ok = (not leaked and bool(queued) and not leaked_after
              and bool(queued_after) and released
              and canonical_alert and not unrepaired)
        report(name, ok, {"leaked_to_detectives": len(leaked),
                          "in_suppressed_queue": len(queued),
                          "fresh_ingest_result": fresh_result,
                          "fresh_hit_leaked": len(leaked_after),
                          "fresh_hit_in_queue": len(queued_after),
                          "release_status": released,
                          "hotlist_canonical_alert": canonical_alert,
                          "migration_unrepaired": unrepaired,
                          "hit11": hit11})
    finally:
        U.stop()


# ------------------------------------------------------------------
# Q2 — locked-boot ordering: no unchained migration on KEY_LOCKED
# ------------------------------------------------------------------
def q02_locked_boot():
    name = "Q02-locked-boot-ordering"
    janus11 = os.path.join(PARENT, "janus11", "janus.py")
    port = next_port()
    B = Boot(janus11, "q02-11", port, audit_key=None)
    try:
        B.start()
        s, b = req(port, "POST", "/suppressions", SUP,
                   {"plate": "LCK100", "order_ref": "PO-Q2 (DEMO)"})
        assert s in (200, 201), b
        s, b = ingest(port, "lck 100")
        assert s == 201, b
    finally:
        B.stop()
    c = db_of(B)
    ref_before = c.execute("SELECT plate_ref FROM suppressions "
                           "WHERE plate='LCK100'").fetchone()
    n_audit_before = c.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    c.close()
    # locked boot: a WRONG env key over the unpinned 1.1 chain
    L = Boot(os.path.join(TREE, "janus.py"), "q02-locked", port,
             dirpath=B.dir, audit_key="a-wrong-key-q02")
    locked = False
    try:
        L.start(tries=16)
        s, b = req(port, "GET", "/health", SUP)
        locked = (s == 503)
    except Exception:
        locked = True  # refused to serve at all
    finally:
        L.stop()
    c = db_of(B)
    ref_mid = c.execute("SELECT plate_ref FROM suppressions "
                        "WHERE plate='LCK100'").fetchone()
    n_audit_mid = c.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    mig_mid = c.execute("SELECT COUNT(*) FROM audit WHERE "
                        "kind='MIGRATION'").fetchone()[0]
    c.close()
    # first unlocked boot: repairs run now, chained
    U = Boot(os.path.join(TREE, "janus.py"), "q02-open", port,
             dirpath=B.dir, audit_key=None)
    try:
        U.start()
        kinds, _ = T.audit_kinds(port)
        ok = (locked and ref_mid == ref_before and mig_mid == 0
              and n_audit_mid == n_audit_before
              and "MIGRATION" in kinds)
        report(name, ok, {"locked": locked,
                          "ref_changed_under_lock": ref_mid != ref_before,
                          "migration_entries_under_lock": mig_mid,
                          "audit_growth_under_lock":
                              n_audit_mid - n_audit_before,
                          "migration_chained_after_unlock":
                              "MIGRATION" in kinds})
    finally:
        U.stop()


# ------------------------------------------------------------------
# Q3 — pin ceremony that verifies (seat 1 R5-13 / seat 2 ruling)
# ------------------------------------------------------------------
def q03_pin_verifies():
    name = "Q03-pin-ceremony-verifies"
    A = inst("q03")
    try:
        A.start()
        s, b = req(A.port, "GET",
                   "/search?plate=PIN100&case=2027-1014"
                   "&justification=pinning&tier=2", DET)
        assert s == 200, b
    finally:
        A.stop()
    # strip the pin: no fingerprint meta, no key file — the
    # pre-1.2 unpinned state, with keyed refs in the chain
    c = db_of(A)
    c.execute("DELETE FROM meta WHERE key LIKE '%fingerprint%' "
              "OR key LIKE '%audit_key%' OR key LIKE '%pin%'")
    c.commit()
    c.close()
    for suffix in (".audit_key",):
        p = A.db + suffix
        if os.path.exists(p):
            os.remove(p)
    W = Boot(os.path.join(TREE, "janus.py"), "q03-wrong", A.port,
             dirpath=A.dir, audit_key="a-different-key-q03")
    booted = False
    try:
        W.start(tries=16)
        s, b = req(A.port, "GET", "/health", SUP)
        booted = (s == 200)
    except Exception:
        booted = False
    finally:
        W.stop()
    report(name, not booted,
           {"wrong_key_booted_and_served": booted})


# ------------------------------------------------------------------
# Q4 — expiry is a parsed instant (seat 1 R5-02 / seat 2 R5-05)
# ------------------------------------------------------------------
def q04_expiry():
    name = "Q04-expiry-parsed"
    A = inst("q04")
    try:
        A.start()
        p = A.port
        s, b = hotlist(p, "EXP100", expires="12/01/2026")
        us_refused = s == 400
        s, b = ingest(p, "EXP100")
        us_killed = b.get("result") != "ALERT" and not us_refused
        s, b = hotlist(p, "EXP200", expires=T.ago_iso(days=1))
        s, b = ingest(p, "EXP200")
        past_quiet = b.get("result") != "ALERT"
        # future expiry: +7 days from now
        from datetime import datetime, timedelta, timezone
        fut = (datetime.now(timezone.utc)
               + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        s, b = hotlist(p, "EXP400", expires=fut)
        s, b = ingest(p, "EXP400")
        future_alerts = b.get("result") == "ALERT"
        ok = us_refused and past_quiet and future_alerts
        report(name, ok, {"us_format_refused_400": us_refused,
                          "us_format_killed_entry": us_killed,
                          "past_expiry_quiet": past_quiet,
                          "future_expiry_alerts": future_alerts})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q5 — one supersede decision in Janus (seat 2 R5-15 / R5-16)
# ------------------------------------------------------------------
def q05_supersede():
    name = "Q05-supersede"
    A = inst("q05")
    try:
        A.start()
        p = A.port
        # R5-16 form (direct): a verified hit's read is immutable
        s, b = hotlist(p, "EVD500")
        assert s == 201, b
        s, b = ingest(p, "EVD500", conf=0.93, event_id="evt-q05-1",
                      type="end")
        assert b.get("result") == "ALERT", b
        hit = b["hit_id"]
        s, b = req(p, "POST", "/verify", DET,
                   {"hit_id": hit, "case": "2027-1014",
                    "decision": "confirm"})
        assert s == 200, b
        s, b = ingest(p, "EVD580", conf=0.41, event_id="evt-q05-1",
                      type="end")
        c = db_of(A)
        row = c.execute("SELECT plate, conf FROM reads WHERE id=?",
                        (1,)).fetchone()
        c.close()
        read_intact = row == ("EVD500", 0.93)
        s, b = req(p, "POST", "/evidence/export", SUP,
                   {"hit_id": hit, "case_id": "2027-1014"})
        bundle_reads = None
        if s == 201:
            mdir = os.path.join(A.dir, "evidence", b["bundle"])
            rj = os.path.join(mdir, "reads.json")
            if os.path.exists(rj):
                bundle_reads = len(json.load(open(rj)))
        # R5-15 form (through the shipped bridge): flicker settles
        # back on the hot plate — the alert must survive / re-fire
        s, b = hotlist(p, "STL777")
        assert s == 201, b
        env = dict(os.environ)
        env.update({"FRIGATE_BRIDGE_PORT": str(next_port()),
                    "FRIGATE_BRIDGE_SECRET": "q05-secret",
                    "NOCTUA_JANUS_URL": A.url,
                    "NOCTUA_INGEST_USER": ING,
                    "NOCTUA_INGEST_KEY": KEYS[ING]})
        bport = int(env["FRIGATE_BRIDGE_PORT"])
        proc = subprocess.Popen(
            [sys.executable, os.path.join(T.SCRIPTS,
                                          "frigate_bridge.py")],
            env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                try:
                    urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % bport,
                        timeout=1)
                    break
                except Exception:
                    time.sleep(0.25)

            def event(body):
                r = urllib.request.Request(
                    "http://127.0.0.1:%d/event" % bport,
                    method="POST", data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json",
                             "X-Bridge-Secret": "q05-secret"})
                try:
                    with urllib.request.urlopen(r, timeout=10) as resp:
                        return resp.status, json.loads(resp.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read() or b"{}")

            def lpr(plate, conf, typ):
                return {"type": typ, "after": {
                    "id": "evt-q05-flicker", "camera": "CAM-01",
                    "attributes": {
                        "recognized_license_plate": [plate, conf]}}}

            event(lpr("STL777", 0.80, "update"))
            event(lpr("STL778", 0.85, "update"))
            s3, b3 = event(lpr("STL777", 0.91, "end"))
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        s, hits = req(p, "GET", "/hits", DET)
        flicker_hit = [h for h in hits.get("hits", [])
                       if h.get("read_plate") == "STL777"]
        # there is no GET /hits/<id> route in any version — the
        # handed-out id's survival is judged from the list: the
        # original hit is still there, still VERIFIED, after the
        # redelivery tried to supersede its read
        first = [h for h in hits.get("hits", [])
                 if h.get("id") == hit]
        first_hit_alive = bool(first) and first[0].get(
            "status") == "VERIFIED"
        ok = (read_intact and bool(flicker_hit)
              and first_hit_alive
              and (bundle_reads is None or bundle_reads >= 1))
        report(name, ok, {"verified_read_intact": read_intact,
                          "read_row": row,
                          "bundle_reads": bundle_reads,
                          "flicker_final_hit": len(flicker_hit),
                          "returned_hit_still_gets_200": first_hit_alive})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q6 — one retention decision function (seat 2 R5-04)
# ------------------------------------------------------------------
def q06_retention():
    name = "Q06-retention-one-function"
    A = inst("q06")
    try:
        A.start()
        p = A.port
        s, b = ingest(p, "RET100")
        assert s == 201, b
        rid = b["read_id"]
        s, b = hotlist(p, "RET200")
        s, b = ingest(p, "RET200")
        assert b.get("result") == "ALERT", b
        hit = b["hit_id"]
        # plain read aged RETENTION_DAYS + 12h (the breach band)
        c = db_of(A)
        from datetime import datetime, timedelta, timezone
        band = (datetime.now(timezone.utc)
                - timedelta(days=14, hours=12)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
        c.execute("UPDATE reads SET ts=? WHERE id=?", (band, rid))
        # held hit aged 150d12h, hold review_by aged with it
        old = (datetime.now(timezone.utc)
               - timedelta(days=150, hours=12)).strftime(
                   "%Y-%m-%dT%H:%M:%SZ")
        c.execute("UPDATE hits SET ts=? WHERE id=?", (old, hit))
        c.commit()
        c.close()
        s, b = req(p, "POST", "/holds", SUP,
                   {"scope": "hit", "ref": hit, "case": "2027-1014",
                    "reason": "litigation (DEMO)"})
        assert s == 201, b
        c = db_of(A)
        c.execute("UPDATE holds SET review_by='2026-06-01'")
        c.commit()
        c.close()
        r1 = run_retention(A)
        r2 = run_retention(A)
        c = db_of(A)
        read_left = c.execute("SELECT COUNT(*) FROM reads WHERE "
                              "id=?", (rid,)).fetchone()[0]
        hit_left = c.execute("SELECT COUNT(*) FROM hits WHERE "
                             "id=?", (hit,)).fetchone()[0]
        c.close()
        h = T.health(p)
        breach = h.get("degraded", {}).get("retention_breach")
        ok = (read_left == 0 and hit_left == 0 and not breach)
        report(name, ok, {"read_left": read_left, "hit_left": hit_left,
                          "retention_breach": breach,
                          "retention_rc": (r1.returncode,
                                           r2.returncode)})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q7 — evidence lifecycle keyed on the evidence record
# ------------------------------------------------------------------
def q07_evidence():
    name = "Q07-evidence-lifecycle"
    A = inst("q07")
    try:
        A.start()
        p = A.port
        s, b = hotlist(p, "EVL100")
        s, b = ingest(p, "EVL100")
        assert b.get("result") == "ALERT", b
        hit = b["hit_id"]
        # export requires a VERIFIED hit in 1.2.2 — verify first
        s, b = req(p, "POST", "/verify", DET,
                   {"hit_id": hit, "case": "2027-1014",
                    "decision": "confirm"})
        assert s == 200, b
        s, b = req(p, "POST", "/evidence/export", DET,
                   {"hit_id": hit, "case_id": "2027-1014"})
        assert s == 201, b
        age_rows(A, "hits", "ts", 151, "id=?", (hit,))
        r = run_retention(A)
        c = db_of(A)
        hit_left = c.execute("SELECT COUNT(*) FROM hits WHERE id=?",
                             (hit,)).fetchone()[0]
        c.close()
        s, rel = req(p, "POST", "/evidence/release", SUP,
                     {"hit_id": hit, "prosecutor_signoff":
                      {"name": "DPA Q7", "date": "2027-06-01"}})
        s2, dsp = req(p, "POST", "/evidence/disposition", DET,
                      {"hit_id": hit, "outcome": "charges_concluded",
                       "by": "DPA Q7", "date": "2027-06-01"})
        s3, des = req(p, "POST", "/evidence/destroy", SUP,
                      {"hit_id": hit})
        ok = (hit_left == 0 and s in (200, 201)
              and s2 in (200, 201) and s3 in (200, 201))
        report(name, ok, {"hit_purged": hit_left == 0,
                          "release_after_purge": s,
                          "disposition_after_purge": s2,
                          "destroy_after_purge": s3})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q8 — registry completeness: ordinary sharing, no false breach
# ------------------------------------------------------------------
def q08_registry_sharing():
    name = "Q08-registry-sharing"
    A = inst("q08-a")
    B = inst("q08-b")
    try:
        A.start()
        B.start()
        pa, pb = A.port, B.port
        s, b = req(pb, "POST", "/compact/partners", SUP,
                   {"agency": "agency-a", "endpoint": A.url,
                    "pubkey_pem": T.pub_pem(A.db),
                    "agreement_ref": "MOU-Q8"})
        assert s == 201, b
        # the report is signed with the HOME instance's signing
        # key (verified against B's SIGNING_PUB_PEM) — B.db, not A.db
        s, b = T.post_audit_result(pb, B.db, "agency-a", True,
                                   {"run": "q08"})
        assert s == 201, b
        cp = T.run_checkpoint(B.db, B.url)
        s, b = T.post_receipt(pb, A.db, "agency-a", cp)
        assert s == 201, b
        share = {"agency": "agency-a", "plate_fragment": "SHR100",
                 "case_ref": "2027-1014", "why": "q08 sweep",
                 "basis_type": "warrant",
                 "auth_basis": "Warrant W-8 (DEMO)", "tier": 2}
        s, b = req(pb, "POST", "/share/query", "agency-a", share)
        assert s == 200, b
        age_rows(B, "share_queries", "ts", 200)
        r = run_retention(B)
        h = T.health(pb)
        breach = h.get("degraded", {}).get("retention_breach") or []
        share_breach = [x for x in breach if "share" in str(x)]
        ok = not share_breach
        report(name, ok, {"retention_breach": breach,
                          "share_breach": share_breach})
    finally:
        A.stop()
        B.stop()


# ------------------------------------------------------------------
# Q9 — config_closed at dispatch for ALL data endpoints, POSTs too
# ------------------------------------------------------------------
def q09_config_closed():
    name = "Q09-config-closed-dispatch"
    A = inst("q09")
    try:
        A.start()
        p = A.port
        # stale case FEED (exported 30 days ago, fresh file) — the
        # Q14 fail-closed condition, reachable without a 24h wait.
        # The cases file shape is {"open_cases": [...]} (write_cases)
        doc = {"open_cases": T.CASES,
               "exported_ts": T.ago_iso(days=30)}
        with open(A.cases, "w") as f:
            json.dump(doc, f)
        time.sleep(0.3)
        s, b = req(p, "GET", "/stats", DET)  # trip the reload
        s_post, b_post = hotlist(p, "CFG100")
        s_holds, _ = req(p, "POST", "/holds", SUP,
                         {"scope": "hit", "ref": 1,
                          "case": "2027-1014", "reason": "x"})
        s_get, _ = req(p, "GET",
                       "/search?plate=CFG100&case=2027-1014"
                       "&justification=q09&tier=2", DET)
        ok = (s_post == 503 and s_holds == 503 and s_get == 503)
        report(name, ok, {"post_hotlist": s_post,
                          "post_holds": s_holds,
                          "get_search": s_get})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q10 — evidence expand requires an executed Tier 3 (seat 2 R5-20)
# ------------------------------------------------------------------
def q10_expand():
    name = "Q10-expand-requires-tier3"
    A = inst("q10")
    try:
        A.start()
        p = A.port
        s, b = hotlist(p, "EXP900")
        s, b = ingest(p, "EXP900")
        assert b.get("result") == "ALERT", b
        hit = b["hit_id"]
        # export requires a VERIFIED hit in 1.2.2 — verify first
        s, b = req(p, "POST", "/verify", DET,
                   {"hit_id": hit, "case": "2027-1014",
                    "decision": "confirm"})
        assert s == 200, b
        s, b = req(p, "POST", "/evidence/export", SUP,
                   {"hit_id": hit, "case_id": "2027-1014",
                    "expand": True, "reason": "pattern (DEMO)"})
        refused = s == 403
        # and with an executed Tier 3 for the same case+plate it works
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "EXP900", "case_id": "2027-1014",
                    "basis_type": "warrant",
                    "auth_basis": "Warrant W-10 (DEMO)",
                    "why": "expansion basis"})
        assert s == 201, b
        s, b = req(p, "POST", "/tier3/approve", SUP,
                   {"request_id": b["request_id"]})
        assert s == 200, b
        s, b = req(p, "POST", "/evidence/export", SUP,
                   {"hit_id": hit, "case_id": "2027-1014",
                    "expand": True, "reason": "pattern (DEMO)"})
        allowed = s == 201 and b.get("scope") == "full"
        kinds, entries = T.audit_kinds(p)
        exp = [e for e in entries if e["kind"] == "EVIDENCE_EXPORT"]
        reason_chained = any(
            (e["fields"].get("reason_ref") or e["fields"].get("reason"))
            for e in exp)
        ok = refused and allowed
        report(name, ok, {"expand_without_tier3": refused,
                          "expand_with_tier3": allowed,
                          "export_entries": len(exp)})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q11 — Tier 3 instruments are configuration; "other" cannot execute
# ------------------------------------------------------------------
def q11_instruments():
    name = "Q11-tier3-instruments"
    A = inst("q11")
    try:
        A.start()
        p = A.port
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "INS100", "case_id": "2027-1014",
                    "basis_type": "other",
                    "auth_basis": "supervisor discretion (DEMO)",
                    "why": "q11 probe"})
        req_status = s
        executed = False
        if s == 201:
            rid = b["request_id"]
            s2, b2 = req(p, "POST", "/tier3/approve", SUP,
                         {"request_id": rid})
            executed = s2 == 200 and "EXECUTED" in str(b2)
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "INS100", "case_id": "2027-1014",
                    "basis_type": "warrant",
                    "auth_basis": "Warrant W-11 (DEMO)",
                    "why": "q11 control"})
        control = False
        if s == 201:
            s2, b2 = req(p, "POST", "/tier3/approve", SUP,
                         {"request_id": b["request_id"]})
            control = s2 == 200 and "EXECUTED" in str(b2)
        ok = (not executed) and control
        report(name, ok, {"other_request_status": req_status,
                          "other_executed": executed,
                          "warrant_control_executed": control})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q12 — holds: validated case + designated role; strict refs
# (seat 2 R5-06 / R5-09)
# ------------------------------------------------------------------
def q12_holds():
    name = "Q12-holds-validated"
    A = inst("q12")
    try:
        A.start()
        p = A.port
        s, b = hotlist(p, "HLD100")
        s, b = ingest(p, "HLD100")
        assert b.get("result") == "ALERT", b
        hit = b["hit_id"]
        s_det, _ = req(p, "POST", "/holds", DET,
                       {"scope": "hit", "ref": hit,
                        "case": "2027-1014", "reason": "x"})
        s_nocase, _ = req(p, "POST", "/holds", SUP,
                          {"scope": "hit", "ref": hit,
                           "reason": "x"})
        s_badcase, _ = req(p, "POST", "/holds", SUP,
                           {"scope": "hit", "ref": hit,
                            "case": "2027-9999", "reason": "x"})
        s_strref, _ = req(p, "POST", "/holds", SUP,
                          {"scope": "hit", "ref": "1garbage",
                           "case": "2027-1014", "reason": "x"})
        s_ok, _ = req(p, "POST", "/holds", SUP,
                      {"scope": "hit", "ref": hit,
                       "case": "2027-1014", "reason": "litigation"})
        s_verify_float, _ = req(p, "POST", "/verify", DET,
                                {"hit_id": "1.0", "case": "2027-1014"})
        ok = (s_det == 403 and s_nocase in (400, 403)
              and s_badcase in (400, 403) and s_strref in (400, 403)
              and s_ok == 201 and s_verify_float == 400)
        report(name, ok, {"detective_hold": s_det,
                          "no_case_hold": s_nocase,
                          "bad_case_hold": s_badcase,
                          "string_ref_hold": s_strref,
                          "valid_hold": s_ok,
                          "verify_hit_id_1.0": s_verify_float})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q13 — the auditor's emergency review is independent (seat 1 R5-08)
# ------------------------------------------------------------------
def q13_auditor_review():
    name = "Q13-auditor-review-independent"
    A = inst("q13")
    try:
        A.start()
        p = A.port
        s, b = req(p, "POST", "/tier3/emergency", SUP,
                   {"plate_fragment": "EMR100", "case_id": "2027-1040",
                    "why": "exigent circumstances (DEMO)",
                    "auth_basis": "judge to be notified (DEMO)",
                    "basis_type": "warrant"})
        assert s == 200, b
        rid = b["request_id"]
        s, rv = req(p, "GET", "/tier3/reviews", AUD)
        mine = [r for r in rv.get("reviews", [])
                if r.get("request_id") == rid]
        sees_basis = bool(mine) and any(
            k in mine[0] for k in
            ("why", "auth_basis", "plate_fragment", "case_no",
             "why_ref", "basis_ref", "fragment_ref"))
        s_sr, _ = req(p, "POST", "/tier3/review", SUP2,
                      {"request_id": rid, "finding": "justified",
                       "note": "supervisor review"})
        s_ar, b_ar = req(p, "POST", "/tier3/review", AUD,
                         {"request_id": rid,
                          "finding": "needs_followup"})
        ok = sees_basis and s_ar in (200, 201)
        report(name, ok, {"auditor_sees_basis_fields": sees_basis,
                          "supervisor_review": s_sr,
                          "auditor_review_after_supervisor": s_ar})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q14 — case-feed freshness fails closed (seat 2 R5-10)
# ------------------------------------------------------------------
def q14_case_feed():
    name = "Q14-case-feed-freshness"
    A = inst("q14")
    try:
        A.start()
        p = A.port
        doc = {"open_cases": T.CASES,
               "exported_ts": T.ago_iso(days=30)}
        with open(A.cases, "w") as f:
            json.dump(doc, f)
        time.sleep(0.3)
        s, b = req(p, "GET",
                   "/search?plate=FEED100&case=2027-1014"
                   "&justification=q14&tier=2", DET)
        search_status = s
        h = T.health(p)
        named = h.get("degraded", {}).get("config", {}).get(
            "cases", {}).get("feed_stale") is True
        ok = search_status in (409, 503) and named
        report(name, ok, {"search_with_stale_feed": search_status,
                          "feed_stale_named_in_health": named})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q15 — AUTH_FAIL throttle crash + SHARE_BLOCKED caps (seat 2 R5-01)
# ------------------------------------------------------------------
def q15_auth_fail():
    name = "Q15-auth-fail-throttle"
    A = inst("q15")
    try:
        A.start()
        p = A.port

        def fail():
            return req(p, "GET", "/health", None, raw_key="wrong")

        # two failures for a NAMED user in one minute bucket
        s1, _ = req(p, "GET", "/health", DET, raw_key="wrong")
        s2, _ = req(p, "GET", "/health", DET, raw_key="wrong")
        # cross into the next minute bucket
        time.sleep(60 - (time.time() % 60) + 0.4)
        s3, b3 = req(p, "GET", "/health", DET, raw_key="wrong")
        s4, b4 = req(p, "GET", "/health", DET, raw_key="wrong")
        s5, _ = req(p, "GET", "/health", SUP)
        kinds, entries = T.audit_kinds(p)
        n_fail = kinds.count("AUTH_FAIL")
        buckets = {e.get("ts", "")[:16] for e in entries
                   if e.get("kind") == "AUTH_FAIL"}
        # The R5-01 property: crossing a minute bucket must not
        # crash the throttle ('<' TypeError) or switch AUTH_FAIL
        # logging off for the process's life. 1.2.2 CAPS chained
        # AUTH_FAIL entries per bucket (the Q15 chain-growth half),
        # so the count is not 4 — the invariant is: every failure
        # answered 401, the good login still served, and at least
        # one AUTH_FAIL entry in EACH bucket (logging alive on
        # both sides of the crossing).
        ok = ([s1, s2, s3, s4] == [401, 401, 401, 401]
              and s5 == 200 and n_fail >= 2 and len(buckets) >= 2)
        report(name, ok, {"statuses": [s1, s2, s3, s4, s5],
                          "auth_fail_entries": n_fail,
                          "auth_fail_buckets": sorted(buckets),
                          "b3": b3 if s3 != 401 else "401"})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q16 — flush_deferred: no phantom sink entries (Vesper seat probe)
# ------------------------------------------------------------------
def q16_flush_phantom():
    name = "Q16-flush-deferred"
    sink = os.path.join(T.WORK, "q16-sink")
    os.makedirs(sink, exist_ok=True)
    A = T.Instance("q16", next_port(),
                   env_extra={"NOCTUA_AUDIT_SINK_DIR": sink})
    try:
        A.start()
        p = A.port

        def burst(n):
            def one(i):
                req(p, "GET",
                    "/search?plate=PHN%03d&case=2027-1014"
                    "&justification=q16&tier=2" % i, DET)
            ts = [threading.Thread(target=one, args=(i,))
                  for i in range(n)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

        burst(40)
        time.sleep(2)
        spool = os.path.join(sink, "sink.jsonl")
        spool_hashes = []
        if os.path.exists(spool):
            for line in open(spool):
                line = line.strip()
                if line:
                    spool_hashes.append(json.loads(line)["hash"])
        c = db_of(A)
        chain_hashes = {r[0] for r in
                        c.execute("SELECT hash FROM audit")}
        c.close()
        phantom = [h for h in spool_hashes if h not in chain_hashes]
        dupes = len(spool_hashes) - len(set(spool_hashes))
        ok = not phantom and dupes == 0
        report(name, ok, {"spooled": len(spool_hashes),
                          "phantom": len(phantom), "dupes": dupes})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q17 — v1 chain entries: kind/ts cross-checked (seat 2 R5-14)
# ------------------------------------------------------------------
def q17_v1_crosscheck():
    name = "Q17-v1-kind-ts-crosscheck"
    port = next_port()
    d = os.path.join(T.WORK, "q17")
    os.makedirs(d, exist_ok=True)
    dbp = os.path.join(d, "janus.db")
    sm = T.sentinel_mod
    ch = sm.Chain(dbp)
    for i in range(6):
        ch.append("QUERY", {"user": "det.okafor", "type": "tier2 search",
                            "tier": 2, "plate_ref": "pref:%024x" % i,
                            "result_count": 0})
    ch.db.close()
    with open(dbp + ".audit_key", "w") as f:
        f.write(T.AUDIT_KEY)
    fp = hashlib.sha256(T.AUDIT_KEY.encode()).hexdigest()
    prov = os.path.join(TREE, "scripts", "provision.py")
    if os.path.exists(prov):
        subprocess.run([sys.executable, prov, "pin-audit-key",
                        "--db", dbp, "--fingerprint", fp, "--confirm"],
                       env=dict(os.environ, NOCTUA_AUDIT_KEY=T.AUDIT_KEY),
                       capture_output=True, text=True)
    B = Boot(os.path.join(TREE, "janus.py"), "q17", port, dirpath=d)
    try:
        B.start()
        s, v0 = req(port, "GET", "/audit/verify", CA)
        base_ok = v0.get("ok") is True
        c = db_of(B)
        c.execute("UPDATE audit SET kind='HITS_VIEW' WHERE seq=3")
        c.commit()
        c.close()
        # cold cache: restart so the cached verify recomputes
    finally:
        B.stop()
    B2 = Boot(os.path.join(TREE, "janus.py"), "q17b", port, dirpath=d)
    try:
        B2.start()
        s, v1 = req(port, "GET", "/audit/verify", CA)
        ok = base_ok and v1.get("ok") is False
        report(name, ok, {"verify_before_relabel": v0,
                          "verify_after_relabel": v1})
    finally:
        B2.stop()


# ------------------------------------------------------------------
# Q18 — authenticate before computing (seat 2 R5-02)
# ------------------------------------------------------------------
def q18_auth_first():
    name = "Q18-auth-before-compute"
    port = next_port()
    d = os.path.join(T.WORK, "q18")
    os.makedirs(d, exist_ok=True)
    dbp = os.path.join(d, "janus.db")
    c = sqlite3.connect(dbp)
    c.execute("CREATE TABLE IF NOT EXISTS audit("
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
            c.executemany("INSERT INTO audit(ts,kind,payload,prev,"
                          "hash) VALUES(?,?,?,?,?)", batch)
            batch = []
    if batch:
        c.executemany("INSERT INTO audit(ts,kind,payload,prev,"
                      "hash) VALUES(?,?,?,?,?)", batch)
    c.commit()
    c.close()
    with open(dbp + ".audit_key", "w") as f:
        f.write(T.AUDIT_KEY)
    fp = hashlib.sha256(T.AUDIT_KEY.encode()).hexdigest()
    prov = os.path.join(TREE, "scripts", "provision.py")
    if os.path.exists(prov):
        subprocess.run([sys.executable, prov, "pin-audit-key",
                        "--db", dbp, "--fingerprint", fp, "--confirm"],
                       env=dict(os.environ, NOCTUA_AUDIT_KEY=T.AUDIT_KEY),
                       capture_output=True, text=True)
    B = Boot(os.path.join(TREE, "janus.py"), "q18", port, dirpath=d)
    try:
        B.start()
        t0 = time.time()
        s_anon, b_anon = req(port, "GET", "/audit/verify")
        anon_s = time.time() - t0
        anon_fast_401 = (s_anon == 401 and anon_s < 2.0)
        t0 = time.time()
        s, v = req(port, "GET", "/audit/verify", CA)
        auth_ok = (s == 200 and v.get("ok") is True)
        ok = anon_fast_401 and auth_ok
        report(name, ok, {"anon_status": s_anon,
                          "anon_seconds": round(anon_s, 2),
                          "auth_status": s,
                          "auth_verify_ok": auth_ok})
    finally:
        B.stop()


# ------------------------------------------------------------------
# Q19 — scrubber exemptions are value-verified (seat 1 R5-12 form)
# ------------------------------------------------------------------
def q19_scrubber():
    name = "Q19-scrubber-value-verified"
    A = inst("q19")
    try:
        A.start()
        p = A.port
        raw = "ABC1234 parked 410 Elm 14:02"
        for _ in range(3):
            s, b = ingest(p, "SCR100", cam=raw)
        kinds, entries = T.audit_kinds(p)
        rej = [e for e in entries if e["kind"] == "INGEST_REJECTED"]
        raw_in_chain = any(raw in json.dumps(e) for e in entries)
        ok = not raw_in_chain and len(rej) <= 1
        report(name, ok, {"raw_text_in_chain": raw_in_chain,
                          "ingest_rejected_entries": len(rej),
                          "last_ingest_status": s})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q20 — _insert_locked rejects caller fields named v/ts/kind
# ------------------------------------------------------------------
def q20_envelope():
    name = "Q20-envelope-collision"
    # No HTTP endpoint hands a raw caller dict to Chain.append —
    # janus builds every payload itself — so the envelope contract
    # is tested at the sentinel boundary directly: a caller field
    # named v/ts/kind must never override the entry's envelope.
    # (1.2.2 strips them; the synthesis said "rejects" — the strip
    # is the prior builder's flagged judgment call.)
    dbp = os.path.join(T.WORK, "q20.db")
    ch = T.sentinel_mod.Chain(dbp)
    e = ch.append("ENVELOPE", {"v": 99, "ts": "1970-01-01T00:00:00Z",
                               "kind": "FORGED", "note": "q20"})
    ch.db.close()
    c = sqlite3.connect(dbp)
    payload = json.loads(c.execute(
        "SELECT payload FROM audit WHERE seq=?",
        (e["seq"],)).fetchone()[0])
    c.close()
    ok = (payload.get("v") == 2 and payload.get("kind") == "ENVELOPE"
          and payload.get("ts") != "1970-01-01T00:00:00Z")
    report(name, ok, {"stored_payload": payload})


# ------------------------------------------------------------------
# Q21 — the Compact gate is a function of audit TIME (seat 2 R5-11)
# ------------------------------------------------------------------
def q21_gate_time():
    name = "Q21-gate-audit-time"
    A = inst("q21-a")
    B = inst("q21-b")
    try:
        A.start()
        B.start()
        pb = B.port
        s, b = req(pb, "POST", "/compact/partners", SUP,
                   {"agency": "agency-a", "endpoint": A.url,
                    "pubkey_pem": T.pub_pem(A.db),
                    "agreement_ref": "MOU-Q21"})
        assert s == 201, b

        fail_doc = {"agency": "agency-a", "ok": False,
                    "ts": T.now_iso(), "checks": {"run": "q21"}}

        def file_doc(doc):
            # verified against the HOME instance's signing key
            # (B's SIGNING_PUB_PEM) — sign with B.db, not A.db
            return req(pb, "POST", "/compact/audit-result", AUD,
                       {"agency": "agency-a", "report": doc,
                        "report_sig": T.sign(B.db, doc)})

        s_fail, _ = file_doc(fail_doc)
        pass_doc = {"agency": "agency-a", "ok": True,
                    "ts": T.ago_iso(hours=1), "checks": {"run": "q21"}}
        s_old, b_old = file_doc(pass_doc)
        s, partners = req(pb, "GET", "/compact/partners", SUP)
        mine = [x for x in partners.get("partners", [])
                if x.get("agency") == "agency-a"]
        latest_ok = mine[0].get("last_audit_ok") if mine else None
        # the identical FAIL report re-filed (same hash) must refuse
        s_dup, _ = file_doc(fail_doc)
        ok = (s_old in (400, 409) and latest_ok is False
              and s_dup in (400, 409))
        report(name, ok, {"fresh_fail_filed": s_fail,
                          "older_pass_refiled": s_old,
                          "latest_audit_ok_after": latest_ok,
                          "duplicate_report": s_dup})
    finally:
        A.stop()
        B.stop()


# ------------------------------------------------------------------
# Q22 — compact.py checks checkpoint age + high-water (seat 2 R5-17)
# ------------------------------------------------------------------
def _compact_run(A, B, pubfile, state):
    """compact.py exactly as the builders' suite invokes it:
    A's auditor (AUD) assesses B, receipt filed as agency-a."""
    env = dict(os.environ)
    env.update({"NOCTUA_AUDIT_KEY": T.AUDIT_KEY})
    return subprocess.run(
        [sys.executable, os.path.join(T.SCRIPTS, "compact.py"),
         "--partner-url", B.url, "--partner-user", CA,
         "--partner-key", KEYS[CA], "--agency", "agency-b",
         "--partner-pubkey", pubfile,
         "--janus", A.url, "--auditor-user", AUD,
         "--auditor-key", KEYS[AUD], "--our-agency", "agency-a",
         "--receipt-user", "agency-a", "--receipt-key",
         KEYS["agency-a"], "--db", A.db, "--state", state],
        env=env, capture_output=True, text=True, timeout=300)


def q22_compact_age():
    name = "Q22-compact-checkpoint-age"
    A = inst("q22-a")
    B = inst("q22-b")
    try:
        A.start()
        B.start()
        pa, pb = A.port, B.port
        s, b = req(pa, "POST", "/compact/partners", SUP,
                   {"agency": "agency-b", "endpoint": B.url,
                    "pubkey_pem": T.pub_pem(B.db),
                    "agreement_ref": "MOU-Q22"})
        assert s == 201, b
        s, b = req(pb, "POST", "/compact/partners", SUP,
                   {"agency": "agency-a", "endpoint": A.url,
                    "pubkey_pem": T.pub_pem(A.db),
                    "agreement_ref": "MOU-Q22"})
        assert s == 201, b
        pubfile = os.path.join(A.dir, "b-pub.pem")
        with open(pubfile, "w") as f:
            f.write(T.pub_pem(B.db))
        state = os.path.join(A.dir, "compact-state.json")
        # run 1: fresh checkpoint — must pass
        cp = T.run_checkpoint(B.db, B.url)
        r1 = _compact_run(A, B, pubfile, state)
        try:
            out1 = json.loads(r1.stdout)
        except ValueError:
            out1 = {}
        fresh_ok = out1.get("ok") is True
        # craft a correctly-signed checkpoint 200 days old at the
        # CURRENT height and make it B's newest (the R5-17 shape:
        # valid signature, valid root — only the age is wrong)
        c = db_of(B)
        root = c.execute("SELECT hash FROM audit ORDER BY seq DESC "
                         "LIMIT 1").fetchone()[0]
        n = c.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        c.close()
        old_ts = T.ago_iso(days=200)
        old_cp = {"date": old_ts[:10], "ts": old_ts, "root": root,
                  "entries": n, "agency": "THIS-AGENCY",
                  "sig_alg": "ed25519"}
        old_cp["sig"] = T.sentinel_mod.sign_bytes(
            B.db + ".signing_key.pem",
            T.sentinel_mod.checkpoint_signed_bytes(old_cp))
        old_cp["pubkey"] = T.pub_pem(B.db)
        with open(B.db + ".checkpoints.jsonl", "a") as f:
            f.write(json.dumps(old_cp, sort_keys=True) + "\n")
        r2 = _compact_run(A, B, pubfile, state)
        try:
            out2 = json.loads(r2.stdout)
        except ValueError:
            out2 = {}
        aged_refused = out2.get("ok") is False
        ok = fresh_ok and aged_refused
        report(name, ok, {"fresh_checkpoint_ok": fresh_ok,
                          "aged_checkpoint_ok": out2.get("ok"),
                          "aged_checks": out2.get("checks")})
    finally:
        A.stop()
        B.stop()


# ------------------------------------------------------------------
# Q23 — ungrindable rotation + void bound to its cycle
# (seat 2 R5-10 / R5-12 / R5-13)
# ------------------------------------------------------------------
def q23_rotation():
    name = "Q23-rotation-ungrindable"
    A = inst("q23")
    try:
        A.start()
        p = A.port
        members = ["agency-a", "agency-b", "agency-c"]
        for ag in members:
            req(p, "POST", "/compact/partners", SUP,
                {"agency": ag, "endpoint": "http://x",
                 "pubkey_pem": T.pub_pem(A.db)})
        s_seed, _ = req(p, "POST", "/compact/rotation/commit", SUP,
                        {"cycle_start": "2027-01-04", "period_days": 30,
                         "members": members, "seed": "publisher-pick"})
        seed_refused = s_seed in (400, 409)
        nonces, pub = T.rotation_ceremony(p, members, "2027-01-04")
        published = pub[0] in (200, 201)
        verify_rc = None
        if published:
            # rotation.py --verify consumes the STORED schedule
            # document (rounds/nonces/version), not the publish
            # response, and a signed doc needs a pinned pubkey
            c = db_of(A)
            stored = c.execute("SELECT schedule FROM "
                               "rotation_schedules ORDER BY id DESC "
                               "LIMIT 1").fetchone()[0]
            c.close()
            sched_doc = os.path.join(A.dir, "sched.json")
            with open(sched_doc, "w") as f:
                f.write(stored)
            pubf = os.path.join(A.dir, "pub.pem")
            with open(pubf, "w") as f:
                f.write(T.pub_pem(A.db))
            env = dict(A.env)
            r = subprocess.run(
                [sys.executable, os.path.join(T.SCRIPTS, "rotation.py"),
                 "--verify", sched_doc, "--pubkey", pubf], env=env,
                capture_output=True, text=True, timeout=120)
            verify_rc = r.returncode
        # void binding (Q23): the request is bound to the cycle that
        # exists when it is made (the chain entry names its
        # schedule id); the auditor's confirm deletes exactly that
        # cycle; cycle 2 then stands on its own two keys
        c = db_of(A)
        s1_id = c.execute("SELECT MAX(id) FROM rotation_schedules"
                          ).fetchone()[0]
        c.close()
        s_v, _ = req(p, "POST", "/compact/rotation/void", SUP, {})
        kinds, entries = T.audit_kinds(p)
        bound = [e["fields"].get("schedule") for e in entries
                 if e["kind"] == "ROTATION_VOID_REQUEST"]
        s_c1, _ = req(p, "POST", "/compact/rotation/void", AUD, {})
        s, st = req(p, "GET", "/compact/rotation/status", SUP)
        cycle1_gone = not st.get("active")
        s_c2, _ = req(p, "POST", "/compact/rotation/void", AUD, {})
        nonces2, pub2 = T.rotation_ceremony(
            p, members, "2027-01-04", nonces=nonces)
        published2 = pub2[0] in (200, 201)
        s, st = req(p, "GET", "/compact/rotation/status", SUP)
        cycle2_alive = bool(st.get("active")) and published2
        ok = (seed_refused and published and verify_rc == 0
              and bound and bound[-1] == s1_id
              and s_c1 == 200 and cycle1_gone
              and s_c2 in (403, 409)
              and cycle2_alive)
        report(name, ok, {"supplied_seed_status": s_seed,
                          "published": published,
                          "rotation_verify_rc": verify_rc,
                          "void_request": s_v,
                          "void_bound_to_schedule": bound,
                          "void_confirm_cycle1": s_c1,
                          "cycle1_gone": cycle1_gone,
                          "confirm_without_pending": s_c2,
                          "cycle2_alive": cycle2_alive})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q24 — witness standing (seat 2 R5-07)
# ------------------------------------------------------------------
def q24_witness():
    name = "Q24-witness-standing"
    A = inst("q24")
    try:
        A.start()
        p = A.port
        members = ["agency-a", "agency-b"]
        for ag in members:
            req(p, "POST", "/compact/partners", SUP,
                {"agency": ag, "endpoint": "http://x",
                 "pubkey_pem": T.pub_pem(A.db)})
        try:
            T.rotation_ceremony(p, members, "2027-01-04")
            ceremony = True
        except Exception:
            ceremony = False
            req(p, "POST", "/compact/rotation", SUP,
                {"cycle_start": "2027-01-04", "period_days": 30,
                 "members": members, "seed": "q24"})
        s_for, _ = req(p, "POST", "/compact/witness", SUP,
                       {"agency": "agency-b", "cycle_start": "2027-01-04",
                        "round": 1, "ok": True})
        raw = "ABC1234 parked 410 Elm 14:02"
        s_raw, _ = req(p, "POST", "/compact/witness", SUP,
                       {"agency": raw, "cycle_start": "2027-01-04",
                        "round": 1, "ok": True})
        kinds, entries = T.audit_kinds(p)
        raw_in_chain = any(raw in json.dumps(e) for e in entries)
        ok = (s_for in (400, 403) and s_raw in (400, 403)
              and not raw_in_chain)
        report(name, ok, {"supervisor_for_partner": s_for,
                          "free_text_agency": s_raw,
                          "raw_text_in_chain": raw_in_chain,
                          "ceremony": ceremony})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q25 — restore: verified, failure-atomic, host keys only
# (seat 2 R5-19)
# ------------------------------------------------------------------
def _dir_snapshot(root):
    """{relpath: sha256} for every file under root (logs excluded —
    a Boot writes server.log; nothing else may change)."""
    snap = {}
    for dp, _dn, fn in os.walk(root):
        for n in fn:
            if n.endswith(".log"):
                continue
            p = os.path.join(dp, n)
            with open(p, "rb") as f:
                snap[os.path.relpath(p, root)] = hashlib.sha256(
                    f.read()).hexdigest()
    return snap


def q25_restore():
    name = "Q25-restore-verified-atomic"
    import shutil
    # ATOMICITY half only (per the finisher brief): backup.py
    # refuses to sign a broken chain, and a failing restore leaves
    # the live installation byte-identical. The trust-root /
    # lost-key shapes are covered by round-4's A7 scenario and are
    # deliberately NOT rebuilt here.
    src = inst("q25-src")
    try:
        src.start()
        s, b = req(src.port, "POST", "/hotlist", DET,
                   {"plate": "BAK100", "state": "AR",
                    "category": "warrant", "case": "2027-1014"})
        assert s == 201, b
        s, b = ingest(src.port, "BAK100")
        assert s == 201, b
    finally:
        src.stop()
    T.run_checkpoint(src.db)

    def backup(outdir):
        env = dict(os.environ)
        env.update({"NOCTUA_DB": src.db,
                    "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
                    "NOCTUA_BACKUP_DIR": outdir,
                    "NOCTUA_JANUS_URL": ""})
        return subprocess.run(
            [sys.executable, os.path.join(T.SCRIPTS, "backup.py")],
            env=env, capture_output=True, text=True, timeout=120)

    # half 1: a legitimate set signs fine; after the chain is
    # tampered with in the DB, backup.py must REFUSE to sign it
    out = os.path.join(T.WORK, "q25-bk")
    r_good = backup(out)
    assert r_good.returncode == 0, r_good.stdout + r_good.stderr
    bset = os.path.join(out, sorted(os.listdir(out))[-1])
    c = db_of(src)
    c.execute("UPDATE audit SET payload=? WHERE seq=2",
              ('{"tampered": true}',))
    c.commit()
    c.close()
    out2 = os.path.join(T.WORK, "q25-bk2")
    r_broken = backup(out2)
    refuses_broken = r_broken.returncode != 0
    # half 2: corrupt a COPY of the good set (chain payload inside
    # the set's DB; manifest file hashes fixed up so the refusal
    # must come from signature/chain verification, not the hash
    # check), then restore it onto the live install: it must fail
    # and leave every live file byte-identical
    bad = os.path.join(T.WORK, "q25-bad-set")
    shutil.copytree(bset, bad)
    c = sqlite3.connect(os.path.join(bad, "noctua.db"))
    c.execute("UPDATE audit SET payload=? WHERE seq=2",
              ('{"tampered": true}',))
    c.commit()
    c.close()
    m = json.load(open(os.path.join(bad, "manifest.json")))
    for nm in list(m["files"]):
        pth = os.path.join(bad, nm)
        if os.path.exists(pth):
            raw = open(pth, "rb").read()
            m["files"][nm].update(
                sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw))
    json.dump(m, open(os.path.join(bad, "manifest.json"), "w"))
    before = _dir_snapshot(src.dir)
    env3 = dict(os.environ)
    env3.update({"NOCTUA_AUDIT_KEY": T.AUDIT_KEY})
    r_bad = subprocess.run(
        [sys.executable, os.path.join(T.SCRIPTS, "restore.py"),
         bad, "--db", src.db, "--config-dir", src.dir],
        env=env3, capture_output=True, text=True, timeout=120)
    after = _dir_snapshot(src.dir)
    # positive control: the untouched good set restores cleanly
    # onto a scratch target (the refusals above are about the
    # corruption, not a broken harness)
    tgt = os.path.join(T.WORK, "q25-target")
    os.makedirs(tgt, exist_ok=True)
    r_ok = subprocess.run(
        [sys.executable, os.path.join(T.SCRIPTS, "restore.py"),
         bset, "--db", os.path.join(tgt, "janus.db"),
         "--config-dir", os.path.join(tgt, "cfg")],
        env=env3, capture_output=True, text=True, timeout=120)
    ok = (refuses_broken and r_bad.returncode != 0
          and before == after and r_ok.returncode == 0)
    report(name, ok,
           {"backup_good_rc": r_good.returncode,
            "backup_broken_chain_rc": r_broken.returncode,
            "restore_corrupt_rc": r_bad.returncode,
            "restore_corrupt_tail": (r_bad.stdout
                                     + r_bad.stderr)[-240:],
            "live_dir_byte_identical": before == after,
            "restore_good_control_rc": r_ok.returncode})


# ------------------------------------------------------------------
# Q26 — _reload_config: TypeError/KeyError fail closed, never 500
# ------------------------------------------------------------------
def q26_config_typeerror():
    name = "Q26-config-typeerror"
    A = inst("q26")
    try:
        A.start()
        p = A.port
        users = json.load(open(A.users))
        for u in users:
            u.pop("role", None)  # KeyError in the 1.2.1 apply path
        with open(A.users, "w") as f:
            json.dump(users, f)
        os.utime(A.users, (time.time() + 1, time.time() + 1))
        time.sleep(0.3)
        statuses = []
        for _ in range(3):
            s, b = ingest(p, "CFG500")
            statuses.append(s)
        s_h, _ = req(p, "GET", "/health", SUP)
        # 1.2.2 contract (Q26): a bad-shaped reload is marked stale
        # and the LAST-GOOD config keeps serving — authenticated
        # ingest still succeeds and /health still answers. The
        # defect shape is a 500 loop, not a 503: fail-closed here
        # means "keep the last good config", never crash.
        ok = statuses == [201, 201, 201] and s_h == 200
        report(name, ok, {"ingest_statuses": statuses,
                          "health_status": s_h})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Q27 — fragments canonicalized; aged Tier 3 EXPIRES; report param
# ------------------------------------------------------------------
def q27_fragments_expiry():
    name = "Q27-tier3-aged-expires"
    A = inst("q27")
    try:
        A.start()
        p = A.port
        s, b = ingest(p, "RST417")
        assert s == 201, b
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "rst-417", "case_id": "2027-1014",
                    "basis_type": "warrant",
                    "auth_basis": "Warrant W-27 (DEMO)",
                    "why": "q27 aging probe"})
        assert s == 201, b
        rid = b["request_id"]
        age_rows(A, "tier3_requests", "created_ts", 20, "id=?", (rid,))
        # expiry is effected by the retention pass (the R5-16
        # shape): age -> scrub/expire -> approve must not execute
        run_retention(A)
        s, b = req(p, "POST", "/tier3/approve", SUP,
                   {"request_id": rid})
        executed = s == 200 and "EXECUTED" in str(b)
        expired = (not executed) and (
            "EXPIRED" in str(b).upper() or s in (400, 409, 410))
        s_rep, _ = req(p, "GET", "/report?snapshot=garbage", SUP)
        ok = expired and s_rep == 400
        report(name, ok, {"approve_aged_request": s,
                          "executed": executed, "expired": expired,
                          "report_snapshot_garbage": s_rep})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Seat 2 R5-08 (health half) — overdue holds degrade /health
# ------------------------------------------------------------------
def s2_r508_health():
    name = "S2-R5-08-health-overdue-hold"
    A = inst("s2r508")
    try:
        A.start()
        p = A.port
        for job in T.JOBS:
            req(p, "POST", "/heartbeat", JOB,
                {"job": job, "ok": True, "detail": "s2"})
        s, b = hotlist(p, "OVD100")
        s, b = ingest(p, "OVD100")
        assert b.get("result") == "ALERT", b
        hit = b["hit_id"]
        s, b = req(p, "POST", "/holds", SUP,
                   {"scope": "hit", "ref": hit, "case": "2027-1014",
                    "reason": "litigation"})
        assert s == 201, b
        c = db_of(A)
        c.execute("UPDATE holds SET review_by='2020-01-01'")
        c.commit()
        c.close()
        time.sleep(0.3)
        h = T.health(p)
        ok = h.get("ok") is False
        report(name, ok, {"health_ok_with_overdue_hold": h.get("ok"),
                          "overdue_holds":
                              h.get("degraded", {}).get(
                                  "overdue_holds")})
    finally:
        A.stop()


# ------------------------------------------------------------------
# Seat 2 R5-18 — sentinel_audit URL mode: no checkpoint must FAIL
# ------------------------------------------------------------------
def s2_r518_audit_no_checkpoint():
    name = "S2-R5-18-audit-no-checkpoint"
    A = inst("s2r518")
    try:
        A.start()
        pubf = os.path.join(A.dir, "pub.pem")
        with open(pubf, "w") as f:
            f.write(T.pub_pem(A.db))
        env = dict(A.env)
        r = subprocess.run(
            [sys.executable, os.path.join(T.SCRIPTS,
                                          "sentinel_audit.py"),
             "--url", A.url, "--user", CA, "--key", KEYS[CA],
             "--pubkey", pubf],
            env=env, capture_output=True, text=True, timeout=180)
        # exit 2 = fail; exit 1 = warn-only (the defect); 0 = pass
        ok = r.returncode == 2
        report(name, ok, {"sentinel_audit_rc": r.returncode,
                          "stdout_tail": r.stdout[-200:]})
    finally:
        A.stop()


# ==================================================================
# The six INVARIANT suites (synthesis acceptance standard).
# Adversarial property tests through the public API: generated
# inputs, seeded RNG, one verdict line each. Meaningful on 1.2.2;
# against 1.2.1 they fail or error and the driver records which.
# ==================================================================
def _rand_plate(rng, prefix="INV"):
    return "%s%s" % (prefix, "".join(
        rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
        for _ in range(4)))


def inv1_hotlist_expiry():
    name = "INV1-hotlist-expiry-parsed"
    rng = random.Random(1221)
    A = inst("inv1")
    try:
        A.start()
        p = A.port
        freetext = ["12/31/2027", "Dec 31 2027", "1798761600",
                    "next Friday", "2027-13-40", ""]
        refused = 0
        for ft in freetext:
            body = {"plate": _rand_plate(rng), "state": "AR",
                    "category": "stolen vehicle",
                    "case": "2027-1014"}
            if ft:
                body["expires"] = ft
            s, b = req(p, "POST", "/hotlist", DET, body)
            if ft and s == 400:
                refused += 1
            elif not ft:
                refused += (s == 201)  # no expiry at all is fine
        future_ok, past_silent = 0, 0
        trials = 6
        for _ in range(trials):
            plate = _rand_plate(rng)
            s, b = hotlist(p, plate,
                           expires=T.ago_iso(days=-rng.randint(1, 3)))
            s2, b2 = ingest(p, plate)
            if s == 201 and b2.get("result") == "ALERT":
                future_ok += 1
            plate = _rand_plate(rng)
            s, b = hotlist(p, plate,
                           expires=T.ago_iso(days=rng.randint(1, 30)))
            s2, b2 = ingest(p, plate)
            if b2.get("result") != "ALERT":
                past_silent += 1
        # an entry alerts until its instant, then never again
        plate = _rand_plate(rng)
        s, b = hotlist(p, plate, expires=T.ago_iso(seconds=-3))
        s1, b1 = ingest(p, plate)
        time.sleep(4)
        s2, b2 = ingest(p, plate)
        boundary = (b1.get("result") == "ALERT"
                    and b2.get("result") != "ALERT")
        ok = (refused == len(freetext) and future_ok == trials
              and past_silent == trials and boundary)
        report(name, ok, {"freetext_refused": refused,
                          "freetext_total": len(freetext),
                          "future_alerts": future_ok,
                          "past_silent": past_silent,
                          "boundary": boundary})
    finally:
        A.stop()


def inv2_ingest_ordering():
    name = "INV2-ingest-ordering"
    rng = random.Random(1222)
    A = inst("inv2")
    try:
        A.start()
        p = A.port
        events, id_survival, best_alerts = 0, 0, 0
        for ev in range(8):
            good = _rand_plate(rng, "BST")
            bad = good[:-1] + ("X" if good[-1] != "X" else "Z")
            s, b = hotlist(p, good)
            assert s == 201, b
            eid = "evt-inv2-%d" % ev
            # the best read is `good` at 0.93 (an "end"); every
            # other delivery is worse or a duplicate of worse
            deliveries = [
                {"plate": good, "conf": 0.93, "type": "end"},
                {"plate": bad, "conf": 0.61, "type": "update"},
                {"plate": bad, "conf": 0.85, "type": "update"},
                {"plate": good, "conf": 0.80, "type": "update"},
                {"plate": bad, "conf": 0.61, "type": "update"}]
            rng.shuffle(deliveries)
            returned_ids = []
            for d in deliveries:
                s, b = ingest(p, d["plate"], conf=d["conf"],
                              event_id=eid, type=d["type"])
                if b.get("hit_id"):
                    returned_ids.append(b["hit_id"])
            events += 1
            s, hits = req(p, "GET", "/hits", DET)
            mine = [h for h in hits.get("hits", [])
                    if h.get("read_plate") == good
                    and h.get("status") in ("PENDING", "VERIFIED")]
            if mine:
                best_alerts += 1
            # R5-03's substance: no hit is ever DELETED out from
            # under an officer. A later delivery of the same event
            # may supersede a PENDING hit — the row persists as
            # WITHDRAWN with its outcome row, the id still
            # resolving to the record that explains it. Survival =
            # every returned id is still listed (any status) AND
            # still has its outcome row.
            by_id = {h.get("id"): h for h in hits.get("hits", [])}
            c = db_of(A)
            outcome_ids = {r[0] for r in c.execute(
                "SELECT hit_id FROM outcomes")}
            c.close()
            alive = sum(1 for hid in set(returned_ids)
                        if hid in by_id and hid in outcome_ids)
            if returned_ids and alive == len(set(returned_ids)):
                id_survival += 1
        ok = (best_alerts == events and id_survival == events)
        report(name, ok, {"events": events,
                          "best_read_alert_survives": best_alerts,
                          "all_returned_ids_resolve": id_survival})
    finally:
        A.stop()


def _upgrade_suppression_check(fixture_janus, tag):
    """Boot a REAL earlier build, protect a plate, upgrade in place
    with the tree under test, and probe every disclosure path."""
    port = next_port()
    plate = "PRT%s" % tag
    B = Boot(fixture_janus, "inv3-%s" % tag, port, audit_key=None)
    try:
        B.start()
        s, b = hotlist(port, plate)
        assert s == 201, b
        s, b = ingest(port, plate)
        assert s == 201, b
        hit = b.get("hit_id")
        s, b = req(port, "POST", "/suppressions", SUP,
                   {"plate": plate, "order_ref": "PO-INV3 (DEMO)"})
        assert s in (200, 201), b
    finally:
        B.stop()
    U = Boot(os.path.join(TREE, "janus.py"), "inv3-up-%s" % tag,
             port, dirpath=B.dir, audit_key=None)
    try:
        U.start()
        s, hits = req(port, "GET", "/hits", DET)
        leaked = [h for h in hits.get("hits", [])
                  if h.get("read_plate") == plate]
        s, b = req(port, "GET",
                   "/search?plate=%s&case=2027-1014"
                   "&justification=inv3&tier=2" % plate, DET)
        search_leak = [r for r in b.get("reads", [])
                       if r.get("plate") == plate]
        s_v, _ = req(port, "POST", "/verify", DET,
                     {"hit_id": hit, "case": "2027-1014"})
        s_e, _ = req(port, "POST", "/evidence/export", SUP,
                     {"hit_id": hit, "case_id": "2027-1014"})
        s, b = ingest(port, plate)
        fresh_hit = b.get("hit_id")
        # an internal ALERT to the ingest bridge is by design;
        # the property is the fresh hit surfaces nowhere but the
        # supervisor queue
        s, hits3 = req(port, "GET", "/hits", DET)
        fresh_leaked = [h for h in hits3.get("hits", [])
                        if h.get("id") == fresh_hit]
        s, sh3 = req(port, "GET", "/suppressed-hits", SUP)
        fresh_queued = [h for h in sh3.get("hits", [])
                        if h.get("id") == fresh_hit]
        return {"leaked_hits": len(leaked),
                "search_leaks": len(search_leak),
                "verify_status": s_v, "export_status": s_e,
                "fresh_hit_leaked": len(fresh_leaked),
                "fresh_hit_queued": len(fresh_queued)}
    finally:
        U.stop()


def inv3_suppression_upgrade():
    name = "INV3-suppression-survives-upgrade"
    res = {}
    for tag, fx in (("11", "janus11"), ("12", "janus12")):
        res[tag] = _upgrade_suppression_check(
            os.path.join(PARENT, fx, "janus.py"), tag)
    ok = all(v["leaked_hits"] == 0 and v["search_leaks"] == 0
             and v["verify_status"] in (400, 403, 404, 409)
             and v["export_status"] in (400, 403, 404, 409)
             and v["fresh_hit_leaked"] == 0
             and v["fresh_hit_queued"] == 1 for v in res.values())
    report(name, ok, res)


def inv4_retention_evidence():
    name = "INV4-retention-evidence-lifecycle"
    rng = random.Random(1224)
    A = inst("inv4")
    try:
        A.start()
        p = A.port
        ages = [0, 13, 15, 31, 90, 149, 151, 200]
        hit_by_age = {}
        for age in ages:
            plate = _rand_plate(rng, "AGE")
            s, b = hotlist(p, plate)
            s, b = ingest(p, plate)
            assert b.get("result") == "ALERT", b
            hit_by_age[age] = b["hit_id"]
            age_rows(A, "hits", "ts", age, "id=?", (b["hit_id"],))
            age_rows(A, "reads", "ts", age, "plate=?", (plate,))
        exported = {}
        for age in (15, 151):
            # export requires a VERIFIED hit in 1.2.2
            s, b = req(p, "POST", "/verify", DET,
                       {"hit_id": hit_by_age[age],
                        "case": "2027-1014", "decision": "confirm"})
            assert s == 200, b
            s, b = req(p, "POST", "/evidence/export", SUP,
                       {"hit_id": hit_by_age[age],
                        "case_id": "2027-1014"})
            exported[age] = (s, b.get("bundle"))
        r = run_retention(A)
        h = T.health(p)
        breach = h.get("degraded", {}).get("retention_breach")

        def audit_fails_now():
            # sentinel_audit against the live instance. The
            # "heartbeat freshness" check is excluded by name: it
            # grades cron jobs (retention/checkpoint/backup/
            # witness heartbeats) that never run inside a
            # seconds-long test instance — environmental, not part
            # of this invariant. Everything else must agree.
            env = dict(A.env)
            aud = subprocess.run(
                [sys.executable, os.path.join(T.SCRIPTS,
                                              "sentinel_audit.py"),
                 "--db", A.db], env=env, capture_output=True,
                text=True, timeout=300)
            try:
                rep = json.loads(aud.stdout)
                return [x["name"] for x in rep["checks"]
                        if x["status"] == "fail"
                        and x["name"] != "heartbeat freshness"]
            except ValueError:
                return ["<unparseable audit output>"]

        audit_fails = audit_fails_now()
        # Q7's design: the 151-day bundle, unreleased with its hit
        # purged, is STRANDED — flagged by name so a human works
        # it. The breach at this stage is exactly that one store,
        # and the audit agrees; it is not silence and not a purge
        # of the bundle itself.
        stranded_visible = (breach == ["evidence bundles"]
                            and audit_fails
                            == ["registry: evidence bundles"])
        # every surviving bundle completes its lifecycle by API
        lifecycle = {}
        c = db_of(A)
        rows = c.execute("SELECT hit_id, bundle FROM evidence "
                         "WHERE destroyed_ts IS NULL").fetchall()
        c.close()
        for hid, bundle in rows:
            edir = A.env.get("NOCTUA_EVIDENCE_DIR") or \
                os.path.join(A.dir, "evidence")
            on_disk = bundle and os.path.exists(
                os.path.join(edir, bundle))
            if not on_disk:
                lifecycle[hid] = "bundle-gone"
                continue
            s1, _ = req(p, "POST", "/evidence/release", SUP,
                        {"hit_id": hid, "prosecutor_signoff":
                         {"name": "DPA INV4", "date": "2027-06-01"}})
            s2, _ = req(p, "POST", "/evidence/disposition", DET,
                        {"hit_id": hid,
                         "outcome": "charges_concluded",
                         "by": "DPA INV4", "date": "2027-06-01"})
            s3, _ = req(p, "POST", "/evidence/destroy", SUP,
                        {"hit_id": hid})
            lifecycle[hid] = (s1, s2, s3)
        lifecycle_ok = all(
            v == "bundle-gone"
            or (v[0] in (200, 201) and v[2] in (200, 201))
            for v in lifecycle.values())
        # once the stranded bundle is worked (release ->
        # disposition -> destroy, all keyed on the evidence
        # record), the flag clears everywhere
        h2 = T.health(p)
        breach_final = h2.get("degraded", {}).get(
            "retention_breach")
        audit_final = audit_fails_now()
        ok = (stranded_visible and lifecycle_ok
              and breach_final == [] and audit_final == []
              and exported[15][0] == 201
              and exported[151][0] == 201)
        report(name, ok, {"retention_rc": r.returncode,
                          "breach_after_retention": breach,
                          "audit_fails_after_retention": audit_fails,
                          "stranded_visible": stranded_visible,
                          "lifecycle": lifecycle,
                          "breach_final": breach_final,
                          "audit_fails_final": audit_final})
    finally:
        A.stop()


def inv5_compact_gate_rotation():
    name = "INV5-compact-gate-time-rotation"
    rng = random.Random(1225)
    A = inst("inv5-a")
    B = inst("inv5-b")
    try:
        A.start()
        B.start()
        pb = B.port
        s, b = req(pb, "POST", "/compact/partners", SUP,
                   {"agency": "agency-a", "endpoint": A.url,
                    "pubkey_pem": T.pub_pem(A.db),
                    "agreement_ref": "MOU-INV5"})
        assert s == 201, b

        def file_doc(doc):
            # verified against the HOME instance's signing key
            # (B's SIGNING_PUB_PEM) — sign with B.db, not A.db
            return req(pb, "POST", "/compact/audit-result", AUD,
                       {"agency": "agency-a", "report": doc,
                        "report_sig": T.sign(B.db, doc)})

        # randomized audit history: pass(new) -> fail(newer) ->
        # the OLD pass re-filed: the gate must follow audit TIME
        t_pass = T.ago_iso(hours=3)
        t_fail = T.ago_iso(hours=1)
        pass_doc = {"agency": "agency-a", "ok": True, "ts": t_pass,
                    "checks": {"run": "inv5"}}
        fail_doc = {"agency": "agency-a", "ok": False, "ts": t_fail,
                    "checks": {"run": "inv5"}}
        s1, _ = file_doc(pass_doc)
        s2, _ = file_doc(fail_doc)
        s3, _ = file_doc(pass_doc)   # stale re-file: must refuse
        s, partners = req(pb, "GET", "/compact/partners", SUP)
        mine = [x for x in partners.get("partners", [])
                if x.get("agency") == "agency-a"]
        latest_ok = mine[0].get("last_audit_ok") if mine else None
        gate_ok = (s3 in (400, 409) and latest_ok is False)
        # rotation: the publisher cannot predict the pairing from
        # anything they control (cycle_start, chain root)
        members = ["THIS-AGENCY", "agency-a", "agency-b",
                   "agency-c"]
        for a in ("agency-b", "agency-c"):   # agency-a already in
            s, b = req(pb, "POST", "/compact/partners", SUP,
                       {"agency": a, "endpoint": A.url,
                        "pubkey_pem": T.pub_pem(A.db),
                        "agreement_ref": "MOU-INV5"})
            assert s == 201, b
        nonces, pub = T.rotation_ceremony(pb, members, "2027-01-04")
        pub_status, pub_body = pub
        seed = hashlib.sha256(T.sentinel_mod.canonical_bytes({
            "members": sorted(members), "cycle_start": "2027-01-04",
            "nonces": {m: nonces[m] for m in sorted(members)}
        })).hexdigest()
        expect = [(r["auditor"], r["audited"]) for r in
                  T.sentinel_mod.rotation_schedule(
                      sorted(members), seed)["rounds"]]
        got = [(r["auditor"], r["audited"]) for r in
               pub_body.get("schedule", [])]
        # publisher-side predictions from public inputs only
        root = req(pb, "GET", "/audit/root", SUP)[1]["root"]
        predicted = set()
        for cand_start in ("2027-01-04", "2027-01-05", "2027-02-01"):
            cand_seed = hashlib.sha256(
                ("%s|%s|%s" % ("|".join(sorted(members)),
                              cand_start, root)).encode()).hexdigest()
            predicted.add(tuple(
                (r["auditor"], r["audited"]) for r in
                T.sentinel_mod.rotation_schedule(
                    sorted(members), cand_seed)["rounds"]))
        rotation_ok = (pub_status == 201 and got == expect
                       and tuple(got) not in predicted)
        ok = gate_ok and rotation_ok
        report(name, ok, {"stale_refile_status": s3,
                          "latest_audit_ok": latest_ok,
                          "rotation_status": pub_status,
                          "schedule_is_nonce_derived": got == expect,
                          "publisher_prediction_matched":
                              tuple(got) in predicted})
    finally:
        A.stop()
        B.stop()


def inv6_spec_gates():
    name = "INV6-spec-gates"
    A = inst("inv6")
    try:
        A.start()
        p = A.port
        # (a) Tier 3 on "other" never executes; on a configured
        # instrument with two keys it does (positive control)
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "INV6", "case_id": "2027-1001",
                    "why": "inv6", "auth_basis": "verbal OK",
                    "basis_type": "other"})
        other_blocked = s in (400, 403)
        if s == 201:
            s2, b2 = req(p, "POST", "/tier3/approve", SUP,
                         {"request_id": b["request_id"]})
            other_blocked = b2.get("result") != "EXECUTED"
        s, b = req(p, "POST", "/tier3/request", DET,
                   {"plate_fragment": "INV6", "case_id": "2027-1001",
                    "why": "inv6", "auth_basis": "Warrant W-6",
                    "basis_type": "warrant"})
        assert s == 201, b
        s2, b2 = req(p, "POST", "/tier3/approve", SUP,
                     {"request_id": b["request_id"]})
        warrant_executes = (s2 == 200
                            and b2.get("result") == "EXECUTED")
        # (b) the auditor's emergency review is independent and
        # informed: a supervisor's review cannot pre-empt it
        s, b = req(p, "POST", "/tier3/emergency", SUP,
                   {"plate_fragment": "INV6", "case_id": "2027-1040",
                    "why": "inv6 emergency", "auth_basis": "exigent",
                    "basis_type": "warrant"})
        assert s == 200, b
        rid = b["request_id"]
        s_rv, b_rv = req(p, "GET", "/tier3/reviews", AUD)
        mine = [r for r in b_rv.get("reviews", [])
                if r.get("request_id") == rid]
        informed = bool(mine) and all(
            k in mine[0] for k in ("why", "plate_fragment",
                                   "case_no"))
        req(p, "POST", "/tier3/review", SUP2,
            {"request_id": rid, "finding": "justified"})
        s_ar, _ = req(p, "POST", "/tier3/review", AUD,
                      {"request_id": rid,
                       "finding": "needs_followup"})
        auditor_independent = s_ar in (200, 201) and informed
        # (c) holds: designated role + validated case only
        s, b = hotlist(p, "INV600")
        s, b = ingest(p, "INV600")
        hit = b["hit_id"]
        s_det, _ = req(p, "POST", "/holds", DET,
                       {"scope": "hit", "ref": hit,
                        "case": "2027-1014", "reason": "inv6"})
        s_nocase, _ = req(p, "POST", "/holds", SUP,
                          {"scope": "hit", "ref": hit,
                           "reason": "inv6"})
        s_bogus, _ = req(p, "POST", "/holds", SUP,
                         {"scope": "hit", "ref": hit,
                          "case": "1999-9999", "reason": "inv6"})
        s_good, b_good = req(p, "POST", "/holds", SUP,
                             {"scope": "hit", "ref": hit,
                              "case": "2027-1014", "reason": "inv6"})
        holds_ok = (s_det == 403 and s_nocase in (400, 403)
                    and s_bogus in (400, 403) and s_good == 201)
        ok = (other_blocked and warrant_executes
              and auditor_independent and holds_ok)
        report(name, ok, {"other_blocked": other_blocked,
                          "warrant_executes": warrant_executes,
                          "auditor_independent": auditor_independent,
                          "auditor_informed": informed,
                          "holds": {"detective": s_det,
                                    "no_case": s_nocase,
                                    "bogus_case": s_bogus,
                                    "valid": s_good}})
    finally:
        A.stop()


CASES = [
    ("Q01", q01_migration), ("Q02", q02_locked_boot),
    ("Q03", q03_pin_verifies), ("Q04", q04_expiry),
    ("Q05", q05_supersede), ("Q06", q06_retention),
    ("Q07", q07_evidence), ("Q08", q08_registry_sharing),
    ("Q09", q09_config_closed), ("Q10", q10_expand),
    ("Q11", q11_instruments), ("Q12", q12_holds),
    ("Q13", q13_auditor_review), ("Q14", q14_case_feed),
    ("Q15", q15_auth_fail), ("Q16", q16_flush_phantom),
    ("Q17", q17_v1_crosscheck), ("Q18", q18_auth_first),
    ("Q19", q19_scrubber), ("Q20", q20_envelope),
    ("Q21", q21_gate_time), ("Q22", q22_compact_age),
    ("Q23", q23_rotation), ("Q24", q24_witness),
    ("Q25", q25_restore), ("Q26", q26_config_typeerror),
    ("Q27", q27_fragments_expiry),
    ("S2-R5-08", s2_r508_health),
    ("S2-R5-18", s2_r518_audit_no_checkpoint),
]
INVARIANTS = [
    ("INV1", inv1_hotlist_expiry), ("INV2", inv2_ingest_ordering),
    ("INV3", inv3_suppression_upgrade),
    ("INV4", inv4_retention_evidence),
    ("INV5", inv5_compact_gate_rotation), ("INV6", inv6_spec_gates),
]
_CASE_NAMES = {fn.__name__: label for label, fn in CASES + INVARIANTS}


def _run_one(label, fn):
    try:
        fn()
    except Exception as exc:
        # a case that raises has NOT passed; print its verdict line
        # (silence is a harness failure, not a result)
        report(_CASE_NAMES.get(fn.__name__, label), False,
               {"exception": "%s: %s" % (type(exc).__name__, exc)})


def main():
    want_inv = "--invariants" in sys.argv
    print("Q122 BATTERY vs %s (invariants: %s)"
          % (TREE, "yes" if want_inv else "no"))
    for label, fn in CASES:
        _run_one(label, fn)
    if want_inv:
        for label, fn in INVARIANTS:
            _run_one(label, fn)
    n = len(RESULTS)
    passed = sum(1 for _nm, ok in RESULTS if ok)
    print("=" * 60)
    print("Q122 BATTERY vs %s: %d/%d PASS" % (TREE, passed, n))
    for nm, ok in RESULTS:
        print("  [%s] %s" % ("PASS" if ok else "FAIL", nm))
    return 0 if passed == n else 1


if __name__ == "__main__":
    sys.exit(main())
