"""Batch 3: anchor acceptance after a rollback, schema-test evasion,
/audit limit, AUTH_FAIL growth, holds/dispositions vs the 150-day
cap, hold-ref mismatch, compact.py key fallback, sentinel_audit URL
mode for partners, key TOFU on a pre-1.2 chain, restore marker on a
locked boot, configurable backup dir vs /health."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import T, req, finding

sentinel = T.sentinel_mod


def grow(port, n):
    for _ in range(n):
        req(port, "POST", "/heartbeat", lib.JOB,
            {"job": "retention", "ok": True, "detail": "grow"})


def a15_anchor_retrigger():
    Y = lib.instance("anc", 19131)
    Y.start()
    try:
        lib.heartbeat_all(Y.port)
        grow(Y.port, 20)
    finally:
        Y.stop()
    cp1 = T.run_checkpoint(Y.db)
    n1 = cp1["entries"]
    n0 = n1 - 6
    c = sqlite3.connect(Y.db)            # what a restore of an older set does
    c.execute("DELETE FROM audit WHERE seq > ?", (n0,))
    c.execute("UPDATE sqlite_sequence SET seq=? WHERE name='audit'", (n0,))
    c.commit()
    c.close()
    Y.start()
    try:
        h = T.health(Y.port)
        first = h["anchor_mismatch"]
        req(Y.port, "POST", "/audit/anchor-accept", lib.SUP, {})
        req(Y.port, "POST", "/audit/anchor-accept", lib.AUD, {})
        cleared = T.health(Y.port)["anchor_mismatch"] is False
        lib.heartbeat_all(Y.port)
        grow(Y.port, 15)                 # the chain grows past cp1 again
    finally:
        Y.stop()
    cp2 = T.run_checkpoint(Y.db)          # a GOOD checkpoint of the new chain
    Y.start()
    try:
        h = T.health(Y.port)
        finding("A15 after a restore-style rollback is two-key ACCEPTED, the "
                "next good checkpoint makes the same old disagreement "
                "re-trigger at every restart (acceptance is pinned to the "
                "newest checkpoint's root, which changes daily)",
                first and cleared and h["anchor_mismatch"] is True,
                {"first_mismatch": first, "cleared_after_accept": cleared,
                 "cp1": (n1, cp1["root"][:12]), "cp2": (cp2["entries"],
                                                      cp2["root"][:12]),
                 "after_restart": h["degraded"]["anchor_detail"]})
    finally:
        Y.stop()


def a16_schema_test_evasion():
    """Run the builders' own suite_schema() against a 1.2 database to which
    a plate-bearing column, table and file have been added under names
    its regex does not know."""
    X = lib.instance("schema", 19132)
    X.start()
    X.stop()
    c = sqlite3.connect(X.db)
    c.execute("ALTER TABLE reads ADD COLUMN vehicle_tag TEXT")
    c.execute("CREATE TABLE ocr_cache(raw_event TEXT, seen TEXT)")
    c.execute("INSERT INTO ocr_cache VALUES(?,?)",
              ('{"after":{"recognized_license_plate":"VIC309"}}',
               lib.ago(days=400)))
    c.commit()
    c.close()
    with open(X.db + ".alerts.jsonl", "w") as f:
        f.write('{"plate":"VIC309","cam":"CAM-04"}\n')
    before = len(T.RESULTS)
    T.suite_schema(X)
    res = T.RESULTS[before:]
    finding("A16 the builders' schema test passes a database that holds "
            "plate data in an unregistered column (reads.vehicle_tag), an "
            "unregistered table (ocr_cache.raw_event, 400 days old) and an "
            "unregistered file beside the DB — it matches column NAMES "
            "against plate|frag|results and looks only at directories",
            all(ok for _n, ok in res), res)


def a17_a20_chain_surface():
    Z = lib.instance("surf", 19133)
    Z.start()
    try:
        grow(Z.port, 1200)
        s, b = req(Z.port, "GET", "/audit?limit=-1", lib.CA)
        total = sqlite3.connect(Z.db).execute(
            "SELECT COUNT(*) FROM audit").fetchone()[0]
        finding("A17 /audit?limit=-1 returns the whole chain in one "
                "response under the global lock (the 1,000 clamp is "
                "min(limit, 1000), and SQLite treats LIMIT -1 as "
                "unlimited) — reachable by a partner's chain_auditor",
                s == 200 and len(b["entries"]) == total > 1000,
                {"returned": len(b.get("entries", [])), "chain": total})
        n0 = sqlite3.connect(Z.db).execute(
            "SELECT COUNT(*) FROM audit WHERE kind='AUTH_FAIL'"
        ).fetchone()[0]
        import urllib.request
        for i in range(300):
            r = urllib.request.Request("http://127.0.0.1:%d/hits" % Z.port,
                                       headers={"X-Noctua-User": "u%05d" % i,
                                                "X-Noctua-Key": "x"})
            try:
                urllib.request.urlopen(r, timeout=5)
            except Exception:
                pass
        n1 = sqlite3.connect(Z.db).execute(
            "SELECT COUNT(*) FROM audit WHERE kind='AUTH_FAIL'"
        ).fetchone()[0]
        finding("A20 unauthenticated requests with 300 distinct usernames "
                "append 300 permanent AUTH_FAIL entries (the throttle is "
                "per username per minute)", n1 - n0 >= 300,
                {"auth_fail_added": n1 - n0})
    finally:
        Z.stop()


def a19_a34_retention_escapes():
    H = lib.instance("hold", 19134)
    H.start()
    try:
        p = H.port
        req(p, "POST", "/hotlist", lib.DET,
            {"plate": "HLD100", "state": "AR", "category": "warrant",
             "case": "2027-1014"})
        ids = []
        for cam in ("CAM-01", "CAM-02", "CAM-03"):
            s, b = req(p, "POST", "/reads", lib.ING,
                       {"plate": "HLD100", "state": "AR", "cam": cam})
            ids.append(b["hit_id"])
        h_hold, h_disp, h_pad = ids
        s1, b1 = req(p, "POST", "/holds", lib.DET,
                     {"scope": "hit", "ref": h_hold, "reason": "x",
                      "review_by": "9999-12-31T00:00:00Z"})
        s2, b2 = req(p, "POST", "/evidence/disposition", lib.DET,
                     {"hit_id": h_disp, "outcome": "no_charges",
                      "by": "x", "date": "2027-01-01"})
        s3, b3 = req(p, "POST", "/holds", lib.DET,
                     {"scope": "hit", "ref": "0%d" % h_pad, "reason": "y"})
        c = sqlite3.connect(H.db)
        c.execute("UPDATE hits SET ts=? WHERE id IN (?,?,?)",
                  (lib.ago(days=400), h_hold, h_disp, h_pad))
        c.commit()
        c.close()
        lib.heartbeat_all(p)
        hb = T.health(p)
        env = {"NOCTUA_DB": H.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
               "NOCTUA_JANUS_URL": H.url, "NOCTUA_JOBS_USER": lib.JOB,
               "NOCTUA_JOBS_KEY": lib.KEYS[lib.JOB]}
        r = lib.run_script("retention.py", env)
        left = [x[0] for x in sqlite3.connect(H.db).execute(
            "SELECT id FROM hits ORDER BY id")]
        ha = T.health(p)
        hold_entries = [e["fields"] for e in lib.chain_entries(p)
                        if e["kind"] == "HOLD_PLACE"]
        finding("A19 a hit hold with review_by 9999-12-31 and an "
                "unconfirmed disposition (no export, no case) each keep a "
                "400-day-old hit — plate, camera, time — past the 150-day "
                "statutory cap; /health stays ok with no retention breach",
                h_hold in left and h_disp in left and ha["ok"] is True
                and ha["degraded"]["retention_breach"] == [],
                {"hold": (s1, b1.get("review_by")), "disposition": s2,
                 "hits_left_after_retention": left,
                 "health_ok": ha["ok"],
                 "retention_breach": ha["degraded"]["retention_breach"],
                 "overdue_holds_in_health": ha["overdue_holds"]})
        finding("A34 a hold placed with ref '0%d' chains HOLD_PLACE hit=%d "
                "and /health counts the hit as held, but retention compares "
                "the text and deletes it" % (h_pad, h_pad),
                h_pad not in left and any(f.get("hit") == h_pad
                                          for f in hold_entries)
                and hb["degraded"]["retention_breach"] == [],
                {"hold_entries": hold_entries, "hits_left": left})
        r = lib.run_script("sentinel_audit.py", {}, args=("--db", H.db))
        rep = json.loads(r.stdout)
        hits_chk = [x for x in rep["checks"] if "hits." in x["name"]]
        finding("A19b ...while sentinel_audit DB mode fails the same "
                "database on hits (it ignores holds and evidence), so the "
                "two registry checkers disagree on every legitimate hold",
                any(x["status"] == "fail" for x in hits_chk), hits_chk)
    finally:
        H.stop()


def a23_compact_key_fallback():
    A = lib.instance("kfA", 19135)
    B = lib.instance("kfB", 19136)
    A.start()
    B.start()
    try:
        s, b = req(B.port, "POST", "/compact/partners", lib.SUP,
                   {"agency": "agency-a", "endpoint": A.url,
                    "pubkey_pem": T.pub_pem(A.db)})
        assert s == 201, b
        s, b = req(A.port, "POST", "/compact/partners", lib.SUP,
                   {"agency": "agency-b", "endpoint": B.url,
                    "pubkey_pem": T.pub_pem(B.db)})
        assert s == 201, b
        registered_pub = os.path.join(T.WORK, "b-registered.pem")
        shutil.copy(B.db + ".signing_pub.pem", registered_pub)
        # B's checkpoints are now signed by a key nobody registered
        os.remove(B.db + ".signing_key.pem")
        os.remove(B.db + ".signing_pub.pem")
        lib.heartbeat_all(B.port)
        T.run_checkpoint(B.db, B.url)

        def run(extra):
            return lib.run_script("compact.py", {
                "NOCTUA_AUDIT_KEY": T.AUDIT_KEY}, args=(
                "--partner-url", B.url, "--partner-user", lib.CA,
                "--partner-key", lib.KEYS[lib.CA], "--agency", "agency-b",
                "--janus", A.url, "--auditor-user", lib.AUD,
                "--auditor-key", lib.KEYS[lib.AUD], "--our-agency",
                "agency-a", "--receipt-user", "agency-a", "--receipt-key",
                lib.KEYS["agency-a"], "--db", A.db, "--state",
                os.path.join(T.WORK, "st-%d.json" % len(extra)), *extra),
                timeout=180)
        good = run(["--partner-pubkey", registered_pub])
        bare = run([])
        rep = json.loads(bare.stdout) if bare.stdout.strip() else {}
        finding("A23 compact.py with neither --partner-pubkey nor "
                "--partner-fingerprint verifies the checkpoint against the "
                "key the checkpoint carries: a checkpoint signed by an "
                "UNREGISTERED key passes and a passing audit is recorded",
                good.returncode != 0 and bare.returncode == 0,
                {"with_registered_key_exit": good.returncode,
                 "without_key_exit": bare.returncode,
                 "checks": rep.get("checks")})
        r = lib.run_script("sentinel_audit.py", {}, args=(
            "--url", B.url, "--user", lib.CA, "--key", lib.KEYS[lib.CA]))
        finding("A26 sentinel_audit URL mode — 'the tool a member uses to "
                "audit another member' — cannot run on the chain_auditor "
                "credential partners are issued (/health is refused)",
                r.returncode != 0 and "403" in (r.stdout + r.stderr),
                (r.stdout + r.stderr).strip()[-160:])
    finally:
        A.stop()
        B.stop()


def a28_key_tofu_and_a29_marker():
    # A28: a chain with history but no pinned fingerprint (any pre-1.2 db)
    d = os.path.join(T.WORK, "tofu")
    os.makedirs(d)
    dbp = os.path.join(d, "janus.db")
    ch = sentinel.Chain(dbp)
    for i in range(5):
        ch.append("QUERY", {"i": i})
    ch.db.close()
    Q = T.Instance.__new__(T.Instance)
    Q.dir, Q.port, Q.db = d, 19137, dbp
    Q.users, Q.cases, Q.cameras = (os.path.join(d, n) for n in
                                   ("users.json", "cases.json",
                                    "cameras.json"))
    T.write_users(Q.users)
    T.write_cases(Q.cases)
    T.write_cameras(Q.cameras)
    Q.env = dict(os.environ, NOCTUA_DB=dbp, NOCTUA_USERS=Q.users,
                 NOCTUA_CASES=Q.cases, NOCTUA_CAMERAS=Q.cameras,
                 NOCTUA_PORT="19137",
                 NOCTUA_AUDIT_KEY="whatever-key-the-operator-typed")
    Q.proc = None
    Q.start()
    up = True
    Q.stop()
    finding("A28 the first 1.2 boot over an existing chain pins WHATEVER "
            "key it is given (trust on first use) — the upgrade boot is "
            "exactly the moment round 3's wrong-key scenario happens",
            up, "booted and pinned an arbitrary key over 5 existing entries")

    # A29: a restore whose key is missing at boot loses its RESTORE entry
    R = lib.instance("mk", 19138)
    R.start()
    R.stop()
    out = os.path.join(T.WORK, "mk-bk")
    env = {"NOCTUA_DB": R.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
           "NOCTUA_BACKUP_DIR": out, "NOCTUA_JANUS_URL": ""}
    assert lib.run_script("backup.py", env).returncode == 0
    bset = os.path.join(out, sorted(os.listdir(out))[-1])
    tdir = os.path.join(T.WORK, "mk-target")
    os.makedirs(tdir)
    tdb = os.path.join(tdir, "janus.db")
    r = lib.run_script("restore.py", {"NOCTUA_AUDIT_KEY": T.AUDIT_KEY},
                       args=(bset, "--db", tdb, "--config-dir",
                             os.path.join(tdir, "cfg")))
    assert r.returncode == 0, r.stdout
    had_marker = os.path.exists(tdb + ".restore_marker")
    M = T.Instance.__new__(T.Instance)
    M.dir, M.port, M.db = tdir, 19139, tdb
    M.users, M.cases, M.cameras = R.users, R.cases, R.cameras
    M.env = dict(os.environ, NOCTUA_DB=tdb, NOCTUA_USERS=R.users,
                 NOCTUA_CASES=R.cases, NOCTUA_CAMERAS=R.cameras,
                 NOCTUA_PORT="19139")
    M.env.pop("NOCTUA_AUDIT_KEY", None)   # the unit file forgot the key
    locked = subprocess.run([sys.executable, lib.JANUS], env=M.env,
                            capture_output=True, text=True, timeout=60)
    marker_after_lock = os.path.exists(tdb + ".restore_marker")
    M.env["NOCTUA_AUDIT_KEY"] = T.AUDIT_KEY
    M.proc = None
    M.start()
    try:
        kinds = [e["kind"] for e in lib.chain_entries(M.port)]
    finally:
        M.stop()
    finding("A29 a key-locked boot after a restore deletes the restore "
            "marker without chaining RESTORE; the next good boot has no "
            "record that a restore ever happened",
            had_marker and locked.returncode == 3 and not marker_after_lock
            and "RESTORE" not in kinds,
            {"locked_exit": locked.returncode,
             "marker_before": had_marker,
             "marker_after_locked_boot": marker_after_lock,
             "RESTORE_in_chain": "RESTORE" in kinds})


def a30_backup_dir():
    elsewhere = os.path.join(T.WORK, "nas-backups")
    V = lib.instance("bkd", 19140,
                     env_extra={"NOCTUA_BACKUP_DIR": elsewhere})
    V.start()
    try:
        lib.heartbeat_all(V.port)
    finally:
        V.stop()
    env = {"NOCTUA_DB": V.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
           "NOCTUA_BACKUP_DIR": elsewhere, "NOCTUA_JANUS_URL": ""}
    assert lib.run_script("backup.py", env).returncode == 0
    old = time.time() - 40 * 86400
    for dp, dn, fn in os.walk(elsewhere):
        for n in fn + dn:
            os.utime(os.path.join(dp, n), (old, old))
        os.utime(dp, (old, old))
    V.start()
    try:
        lib.heartbeat_all(V.port)
        h = T.health(V.port)
        finding("A30 with NOCTUA_BACKUP_DIR set (the obvious off-box "
                "setup), a 40-day-old backup set — a full DB copy — is "
                "invisible to /health: the registry's 'backups' folder is "
                "resolved beside the DB only",
                h["ok"] is True and h["degraded"]["retention_breach"] == [],
                {"backup_dir": elsewhere, "health_ok": h["ok"],
                 "retention_breach": h["degraded"]["retention_breach"]})
    finally:
        V.stop()


def a27_genpkey_mode():
    d = os.path.join(T.WORK, "gp")
    os.makedirs(d)
    p = os.path.join(d, "k.pem")
    subprocess.run(["bash", "-c", "umask 022; openssl genpkey -algorithm "
                    "ED25519 -out %s" % p], check=True, capture_output=True)
    mode = oct(os.stat(p).st_mode & 0o777)
    finding("A27 (check) openssl 3 creates the private key 0600 itself, "
            "so ensure_signing_key's later chmod leaves no window here",
            mode != "0o600", {"mode_as_created": mode,
                              "note": "NOT a defect on OpenSSL 3.0.13"})


if __name__ == "__main__":
    a15_anchor_retrigger()
    a16_schema_test_evasion()
    a17_a20_chain_surface()
    a19_a34_retention_escapes()
    a23_compact_key_fallback()
    a28_key_tofu_and_a29_marker()
    a30_backup_dir()
    a27_genpkey_mode()
    lib.summary()
