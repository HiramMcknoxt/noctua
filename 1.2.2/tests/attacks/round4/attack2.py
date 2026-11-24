"""Batch 2: post-hoc suppression, witness publication (unconfigured
repo), restore, chain column tamper, sink spool, bridge OCR updates,
config changes across a restart. (A6b and A9 are in attack2b.py.)"""
import hashlib
import hmac
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import T, req, finding

sentinel = T.sentinel_mod


def a5_posthoc_suppression():
    S = lib.instance("sup", 19111)
    S.start()
    try:
        p = S.port
        s, b = req(p, "POST", "/hotlist", lib.DET,
                   {"plate": "PHS100", "state": "AR", "category": "warrant",
                    "case": "2027-1031"})
        assert s == 201, b
        s, b = req(p, "POST", "/reads", lib.ING,
                   {"plate": "PHS100", "state": "AR", "cam": "CAM-03"})
        hit = b["hit_id"]
        s, b = req(p, "POST", "/tier3/request", lib.DET,
                   {"plate_fragment": "PHS100", "case_id": "2027-1031",
                    "basis_type": "warrant", "auth_basis": "W-9",
                    "why": "locate"})
        rid = b["request_id"]
        s, b = req(p, "POST", "/tier3/approve", lib.SUP, {"request_id": rid})
        assert s == 200, b
        # the protection order arrives AFTER the hit
        s, b = req(p, "POST", "/suppressions", lib.SUP,
                   {"plate": "PHS100", "order_ref": "PO-1 (DEMO)"})
        assert s == 201, b
        s, b = req(p, "GET", "/hits", lib.DET)
        listed = [h for h in b["hits"] if h["id"] == hit]
        s3, b3 = req(p, "GET", "/tier3/results/%d" % rid, lib.DET)
        t3_hits = b3.get("results", {}).get("hits", [])
        s4, b4 = req(p, "POST", "/verify", lib.DET,
                     {"hit_id": hit, "decision": "confirm",
                      "case": "2027-1031"})
        s5, b5 = req(p, "POST", "/evidence/export", lib.DET,
                     {"hit_id": hit, "case_id": "2027-1031"})
        s6, b6 = req(p, "GET", "/search?plate=PHS100&case=2027-1031"
                     "&justification=x&tier=2", lib.DET)
        finding("A5 a suppression placed after a hit leaves that hit "
                "fully visible: /hits shows the plate to detectives, Tier 3 "
                "results re-resolve it, and a detective verifies and "
                "exports it — while /search hides it",
                listed and listed[0]["read_plate"] == "PHS100"
                and any(h["read_plate"] == "PHS100" for h in t3_hits)
                and s4 == 200 and s5 == 201,
                {"/hits": listed, "tier3_hits": t3_hits,
                 "detective_verify": (s4, b4),
                 "detective_export": (s5, b5.get("result")),
                 "search_hits": b6.get("hits")})
    finally:
        S.stop()


def a6_witness():
    W = lib.instance("wit", 19112)
    W.start()
    try:
        lib.heartbeat_all(W.port)
        base = {"NOCTUA_DB": W.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
                "NOCTUA_JANUS_URL": W.url, "NOCTUA_JOBS_USER": lib.JOB,
                "NOCTUA_JOBS_KEY": lib.KEYS[lib.JOB]}
        # (a) an unconfigured witness: a directory that does not exist
        wdir = os.path.join(T.WORK, "never-configured-witness")
        env = dict(os.environ, **base, WITNESS_REPO=wdir)
        r = subprocess.run(["bash", os.path.join(lib.SCRIPTS,
                                                 "publish_witness.sh")],
                           env=env, capture_output=True, text=True,
                           timeout=120)
        h = T.health(W.port)
        finding("A6a with no witness repo configured, publish_witness "
                "creates a same-box directory, exits 0, and /health "
                "shows the witness job ok", r.returncode == 0
                and h["jobs"]["witness"]["ok"] is True and h["ok"] is True,
                {"exit": r.returncode, "stdout": r.stdout.strip()[-160:],
                 "witness_job": h["jobs"]["witness"]})
    finally:
        W.stop()


def make_backup(inst, out):
    env = {"NOCTUA_DB": inst.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
           "NOCTUA_BACKUP_DIR": out, "NOCTUA_JANUS_URL": "",
           "NOCTUA_USERS": inst.users, "NOCTUA_CASES": inst.cases,
           "NOCTUA_CAMERAS": inst.cameras,
           "NOCTUA_EVIDENCE_DIR": os.path.join(inst.dir, "evidence")}
    r = lib.run_script("backup.py", env)
    assert r.returncode == 0, r.stdout + r.stderr
    return os.path.join(out, sorted(os.listdir(out))[-1])


def a7_a8_restore():
    R = lib.instance("rst", 19113)
    R.start()
    try:
        req(R.port, "POST", "/hotlist", lib.DET,
            {"plate": "BAK100", "state": "AR", "category": "warrant",
             "case": "2027-1014"})
    finally:
        R.stop()
    T.run_checkpoint(R.db)
    bset = make_backup(R, os.path.join(T.WORK, "bk"))
    # ---- A7: attacker-built set, signed with the attacker's OWN key ----
    evil = os.path.join(T.WORK, "evil-set")
    shutil.copytree(bset, evil)
    users = json.load(open(R.users))
    users.append({"user": "evil.sup", "role": "supervisor",
                  "key_sha256": hashlib.sha256(b"EVIL").hexdigest()})
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for arc, data in (("users.json", json.dumps(users).encode()),
                          ("cases.json", open(R.cases, "rb").read()),
                          ("cameras.json", open(R.cameras, "rb").read())):
            ti = tarfile.TarInfo(arc)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    open(os.path.join(evil, "config.tar.gz"), "wb").write(buf.getvalue())
    kdir = os.path.join(T.WORK, "attacker-key")
    os.makedirs(kdir)
    priv = os.path.join(kdir, "k.pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519", "-out",
                    priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out",
                    os.path.join(evil, "signing_pub.pem")], check=True,
                   capture_output=True)
    shutil.copy(priv, os.path.join(evil, "signing_key.pem"))
    m = json.load(open(os.path.join(evil, "manifest.json")))
    for name in list(m["files"]):
        pth = os.path.join(evil, name)
        raw = open(pth, "rb").read()
        m["files"][name].update(sha256=hashlib.sha256(raw).hexdigest(),
                                size=len(raw))
    body = {k: v for k, v in m.items()
            if k not in ("manifest_hmac", "manifest_sig", "sig_alg")}
    m["manifest_hmac"] = None   # the attacker does not know the HMAC key
    m["manifest_sig"] = sentinel.sign_bytes(
        priv, sentinel.canonical_bytes(body))
    json.dump(m, open(os.path.join(evil, "manifest.json"), "w"))
    tdir = os.path.join(T.WORK, "restore-target")
    os.makedirs(tdir)
    tdb = os.path.join(tdir, "noctua.db")
    cfg = os.path.join(tdir, "config")
    r = lib.run_script("restore.py", {"NOCTUA_AUDIT_KEY": T.AUDIT_KEY},
                       args=(evil, "--db", tdb, "--config-dir", cfg))
    restored_users = json.load(open(os.path.join(cfg, "users.json"))) \
        if os.path.exists(os.path.join(cfg, "users.json")) else []
    finding("A7 restore.py accepts a set re-signed with an ATTACKER's key "
            "(it verifies against the set's own signing_pub.pem), drops "
            "the HMAC without complaint, and installs the attacker's "
            "users.json (an extra supervisor) and signing key",
            r.returncode == 0
            and any(u["user"] == "evil.sup" for u in restored_users),
            {"exit": r.returncode, "stdout": r.stdout.strip()[-300:],
             "users_restored": [u["user"] for u in restored_users]})
    # ---- A8: a REFUSED restore has already swapped the live database ----
    live = os.path.join(T.WORK, "live2")
    os.makedirs(live)
    ldb = os.path.join(live, "noctua.db")
    ch = sentinel.Chain(ldb)
    for i in range(30):
        ch.append("TEST", {"i": i})
    ch.db.close()
    live_entries = 30
    slip = os.path.join(T.WORK, "slip-set")
    shutil.copytree(bset, slip)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        ti = tarfile.TarInfo("../evil.txt")
        ti.size = 5
        tf.addfile(ti, io.BytesIO(b"pwned"))
    open(os.path.join(slip, "config.tar.gz"), "wb").write(buf.getvalue())
    m = json.load(open(os.path.join(slip, "manifest.json")))
    raw = buf.getvalue()
    m["files"]["config.tar.gz"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    body = {k: v for k, v in m.items()
            if k not in ("manifest_hmac", "manifest_sig", "sig_alg")}
    m["manifest_sig"] = sentinel.sign_bytes(
        os.path.join(slip, "signing_key.pem"),
        sentinel.canonical_bytes(body))
    m["manifest_hmac"] = hmac.new(T.AUDIT_KEY.encode(),
                                  sentinel.canonical_bytes(body),
                                  hashlib.sha256).hexdigest()
    json.dump(m, open(os.path.join(slip, "manifest.json"), "w"))
    r = lib.run_script("restore.py", {"NOCTUA_AUDIT_KEY": T.AUDIT_KEY},
                       args=(slip, "--db", ldb, "--config-dir",
                             os.path.join(live, "config")))
    now_entries = sentinel.verify_detached(ldb).get("entries")
    asides = [f for f in os.listdir(live) if ".pre-restore-" in f]
    finding("A8 a restore that prints REFUSING (tar-slip) has ALREADY "
            "replaced the live database and keys, and leaves no restore "
            "marker", r.returncode != 0 and now_entries != live_entries
            and not os.path.exists(ldb + ".restore_marker"),
            {"exit": r.returncode, "stdout": r.stdout.strip()[-220:],
             "live_entries_before": live_entries,
             "entries_after_refusal": now_entries,
             "moved_aside": asides,
             "marker": os.path.exists(ldb + ".restore_marker")})


def a10_kind_column():
    d = os.path.join(T.WORK, "kind")
    os.makedirs(d)
    dbp = os.path.join(d, "noctua.db")
    ch = sentinel.Chain(dbp)
    ch.append("ALERT", {"hit": 7, "cam": "CAM-01", "category": "warrant"})
    ch.append("EVIDENCE_EXPORT", {"hit": 7, "by": "det.okafor"})
    ch.append("SHARE_OUT", {"agency": "agency-a", "tier": 2})
    ch.db.close()
    c = sqlite3.connect(dbp)
    c.execute("UPDATE audit SET kind='SYSTEM', ts='2001-01-01T00:00:00Z' "
              "WHERE kind IN ('EVIDENCE_EXPORT','SHARE_OUT')")
    c.commit()
    kinds = [r[0] for r in c.execute("SELECT kind FROM audit ORDER BY seq")]
    c.close()
    v = sentinel.verify_detached(dbp)
    finding("A10 the audit table's kind and ts COLUMNS are outside the "
            "hash: rewriting them leaves verify() ok, while custody "
            "excerpts, the share rate limit and /audit read the columns",
            v["ok"] is True and kinds.count("SYSTEM") == 2,
            {"verify": v, "kinds_now": kinds})


def a11_spool():
    sink = os.path.join(T.WORK, "sinkdir", "sink.jsonl")
    os.makedirs(os.path.dirname(sink))
    K = lib.instance("spool", 19114,
                     env_extra={"NOCTUA_SENTINEL_SINK": sink})
    K.start()
    try:
        p = K.port
        s, b = req(p, "POST", "/hotlist", lib.DET,
                   {"plate": "SPL100", "state": "AR", "category": "stolen",
                    "case": "2027-1014"})
        assert s == 201, b
        lib.heartbeat_all(p)
        # a spool left half-written by a power cut while the sink was down
        with open(sink + ".spool", "w") as f:
            f.write('{"seq": 99, "kind": "ALE')
        s1, b1 = req(p, "POST", "/reads", lib.ING,
                     {"plate": "SPL100", "state": "AR", "cam": "CAM-01"})
        s2, b2 = req(p, "POST", "/reads", lib.ING,
                     {"plate": "ZZZ999", "state": "AR", "cam": "CAM-01"})
        n_spl = lib.db(K).execute("SELECT COUNT(*) FROM reads WHERE "
                                  "plate='SPL100'").fetchone()[0]
        h = T.health(p)
        finding("A11 one torn line in the sink spool makes every chained "
                "write fail: the stolen-plate read is rejected (500) and "
                "lost, a plain read still succeeds, and /health stays "
                "ok:true with sink_up:true",
                s1 == 500 and n_spl == 0 and s2 == 201
                and h["ok"] is True and h["degraded"]["sink_up"] is True,
                {"stolen_plate_read": (s1, b1), "plain_read": (s2, b2),
                 "stolen_reads_stored": n_spl, "health_ok": h["ok"],
                 "sink": h["sink"]})
    finally:
        K.stop()


def a12_bridge_update_end():
    G = lib.instance("brg", 19115)
    G.start()
    env = dict(os.environ, FRIGATE_BRIDGE_PORT="19116",
               FRIGATE_BRIDGE_SECRET="s3cret", NOCTUA_JANUS_URL=G.url,
               NOCTUA_INGEST_USER=lib.ING,
               NOCTUA_INGEST_KEY=lib.KEYS[lib.ING])
    proc = subprocess.Popen([sys.executable,
                             os.path.join(lib.SCRIPTS, "frigate_bridge.py")],
                            env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        import urllib.request
        for _ in range(40):
            try:
                urllib.request.urlopen("http://127.0.0.1:19116/health",
                                       timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        s, b = req(G.port, "POST", "/hotlist", lib.DET,
                   {"plate": "STL777", "state": "AR", "category": "stolen",
                    "case": "2027-1014"})
        assert s == 201, b

        def event(body):
            r = urllib.request.Request(
                "http://127.0.0.1:19116/event", method="POST",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json",
                         "X-Bridge-Secret": "s3cret"})
            with urllib.request.urlopen(r, timeout=10) as resp:
                return json.loads(resp.read())
        upd = event({"type": "update", "after": {
            "id": "1700000000.1-abc", "camera": "CAM-01",
            "attributes": {"recognized_license_plate": ["STL77", 0.61]}}})
        end = event({"type": "end", "after": {
            "id": "1700000000.1-abc", "camera": "CAM-01",
            "attributes": {"recognized_license_plate": ["STL777", 0.93]}}})
        c = lib.db(G)
        stored = c.execute("SELECT plate, conf FROM reads").fetchall()
        hits = c.execute("SELECT COUNT(*) FROM hits").fetchone()[0]
        finding("A12 bridge forwards Frigate's partial 'update' OCR; Janus "
                "dedupes on (camera, event_id) so the corrected 'end' read "
                "is dropped as a duplicate — the stolen plate never alerts",
                hits == 0 and stored == [("STL77", 0.61)],
                {"update": upd.get("janus"), "end": end.get("janus"),
                 "reads_stored": stored, "hits": hits})
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        G.stop()


def a13_config_across_restart():
    Cf = lib.instance("cfg", 19117)
    Cf.start()
    Cf.stop()
    users = json.load(open(Cf.users))
    users.append({"user": "ghost.sup", "role": "supervisor",
                  "key_sha256": hashlib.sha256(b"GHOST").hexdigest()})
    json.dump(users, open(Cf.users, "w"))
    Cf.start()
    try:
        p = Cf.port
        s, b = req(p, "POST", "/tier3/request", lib.DET,
                   {"plate_fragment": "ABC", "case_id": "2027-1014",
                    "basis_type": "warrant", "auth_basis": "W",
                    "why": "x"})
        rid = b["request_id"]
        s, b = req(p, "POST", "/tier3/approve", "ghost.sup",
                   {"request_id": rid}, raw_key="GHOST")
        kinds = [e["kind"] for e in lib.chain_entries(p)]
        finding("A13 an account added while Janus is stopped is live at "
                "boot with no CONFIG_CHANGED entry (first load is never "
                "chained; SYSTEM carries no config hash) — here it "
                "approves a Tier 3 search",
                s == 200 and "CONFIG_CHANGED" not in kinds,
                {"ghost_approve": (s, b.get("result")),
                 "config_entries": [k for k in kinds if "CONFIG" in k]})
    finally:
        Cf.stop()


if __name__ == "__main__":
    a5_posthoc_suppression()
    a6_witness()
    a7_a8_restore()
    a10_kind_column()
    a11_spool()
    a12_bridge_update_end()
    a13_config_across_restart()
    lib.summary()
