"""R5-12..R5-16: smaller defects, each reproduced.

R5-12 INGEST_REJECTED chains the caller's raw `cam` string
      (janus.py:1853-1855); `cam` is scrubber-exempt (sentinel.py:748)
      because REGISTERED camera ids are configuration — but this entry
      exists precisely because the camera is NOT registered. The A21
      fix (hash unregistered agency text) was not applied to cam.
      Unthrottled: every rejected read is a permanent chain entry.
R5-13 A28's 'verification' is a file-vs-env proxy: a WRONG key written
      into the key file over an unpinned legacy chain is pinned without
      complaint, although Janus could check it against keyed refs
      already in that chain.
R5-14 restore.py moves live keys aside with os.replace (mtime kept),
      then prunes '.pre-restore-' copies by mtime: the live audit key
      and signing key copies are deleted by the restore that just made
      them ('nothing is destroyed by a restore').
R5-15 fragments are not canonicalized like plates (S3): a search for
      'HYP-123' misses the stored canonical 'HYP123'.
R5-16 a Tier 3 request left pending past RETENTION_DAYS has its why /
      auth_basis nulled and its fragment scrubbed; the approver sees
      blanks (P12) and approval still EXECUTES — a search for the
      HMAC string, chained as an executed Tier 3 search."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def r5_12(A):
    p = A.port
    n0 = len(L.T.audit_kinds(p)[0])
    for cam in ("ABC1234", "Doe residence driveway, 12 Elm St"):
        req(p, "POST", "/reads", L.ING, {"plate": "X1", "cam": cam})
    for i in range(40):
        req(p, "POST", "/reads", L.ING, {"plate": "X1",
                                          "cam": "junk-%d" % i})
    kinds, entries = L.T.audit_kinds(p)
    rej = [e["fields"].get("cam") for e in entries
           if e["kind"] == "INGEST_REJECTED"]
    finding("R5-12", "INGEST_REJECTED writes the caller's raw cam text "
            "into the permanent chain (plate-shaped or free text, "
            "readable by partners' chain_auditors) with no throttle",
            "ABC1234" in rej and any("Elm St" in (c or "") for c in rej)
            and len(rej) >= 42,
            {"raw_cams_in_chain": rej[-2:] + rej[:0],
             "entries_added": len(kinds) - n0, "rejected_entries": len(rej)})


def r5_15(A):
    p = A.port
    s, b = req(p, "POST", "/reads", L.ING,
               {"plate": "HYP123", "state": "AR", "cam": "CAM-01"})
    assert s == 201, b
    _s, dash = req(p, "GET", "/search?plate=HYP-123&case=2027-1001"
                   "&justification=r5&tier=2", L.DET)
    _s, plain = req(p, "GET", "/search?plate=HYP123&case=2027-1001"
                    "&justification=r5&tier=2", L.DET)
    finding("R5-15", "a Tier 2 search typed with a hyphen ('HYP-123') "
            "misses the stored canonical plate 'HYP123' — fragments are "
            "not normalized like plates",
            dash.get("reads") == [] and len(plain.get("reads", [])) == 1,
            {"HYP-123": dash.get("reads"), "HYP123": plain.get("reads")})


def r5_16(A):
    p = A.port
    s, b = req(p, "POST", "/tier3/request", L.DET,
               {"plate_fragment": "OLD", "case_id": "2027-1014",
                "why": "robbery suspect vehicle", "basis_type": "warrant",
                "auth_basis": "SW-2027-88"})
    rid = b["request_id"]
    c = L.db(A)
    c.execute("UPDATE tier3_requests SET created_ts=? WHERE id=?",
              (L.ago(days=20), rid))
    c.commit()
    c.close()
    L.run_script("retention.py", L.script_env(A))
    _s, pend = req(p, "GET", "/tier3/pending", L.SUP)
    item = [x for x in pend["pending"] if x["id"] == rid]
    s2, b2 = req(p, "POST", "/tier3/approve", L.SUP2, {"request_id": rid})
    finding("R5-16", "a Tier 3 request pending past RETENTION_DAYS "
            "reaches the approver with why/auth_basis = null and the "
            "fragment scrubbed to an HMAC, and approval still EXECUTES "
            "(a search for the HMAC string, chained as a Tier 3 search)",
            item and item[0].get("why") is None
            and str(item[0].get("plate_fragment", "")).startswith("pref:")
            and s2 == 200 and b2.get("result") == "EXECUTED",
            {"approver_sees": item, "approve": (s2, b2)})


def r5_13():
    d = os.path.join(L.T.WORK, "r5-tofu")
    os.makedirs(d)
    env = dict(os.environ)
    env.pop("NOCTUA_AUDIT_KEY", None)
    env.update({"NOCTUA_DB": os.path.join(d, "janus.db"),
                "NOCTUA_USERS": os.path.join(d, "users.json"),
                "NOCTUA_CASES": os.path.join(d, "cases.json"),
                "NOCTUA_CAMERAS": os.path.join(d, "cameras.json"),
                "NOCTUA_PORT": "19281"})
    L.T.write_users(env["NOCTUA_USERS"])
    L.T.write_cases(env["NOCTUA_CASES"])
    L.T.write_cameras(env["NOCTUA_CAMERAS"])
    p = L.boot_script(L.JANUS11, env, 19281, d)
    try:
        s, b = req(19281, "GET", "/search?plate=KEY&case=2027-1014"
                   "&why=r5&justification=r5&tier=2", L.DET)
    finally:
        p.terminate()
        p.wait(timeout=10)
    kf = env["NOCTUA_DB"] + ".audit_key"
    k1 = open(kf).read().strip()
    c = sqlite3.connect(env["NOCTUA_DB"])
    chained = [json.loads(r[0]).get("plate_ref") for r in c.execute(
        "SELECT payload FROM audit WHERE kind='QUERY'")]
    c.close()
    k2 = "a-wrong-key-from-the-wrong-server"
    with open(kf, "w") as f:
        f.write(k2)
    # 1.2.2 RE-AIM (Q3): key pinning is verify-don't-proxy now — a
    # WRONG key over a chain whose stored refs do not recompute under
    # it is REFUSED at boot, so boot_script raising is the defended
    # outcome, not a harness failure. REPRODUCED only if Janus
    # actually comes up and serves with the wrong key pinned.
    served = True
    s_h = None
    try:
        p = L.boot_script(L.JANUS, env, 19281, d)
    except RuntimeError:
        served = False
        p = None
    if served:
        try:
            s_h, _b = req(19281, "GET", "/hits", L.DET)
        finally:
            p.terminate()
            p.wait(timeout=10)
    c = sqlite3.connect(env["NOCTUA_DB"])
    fp = c.execute("SELECT value FROM meta WHERE key="
                   "'audit_key_fingerprint'").fetchone()
    c.close()
    finding("R5-13", "over an unpinned 1.1 chain, a WRONG key placed in "
            "the key file is pinned and Janus serves (the A28 refusal "
            "covers env keys only) — although the chain's own QUERY "
            "plate_ref recomputes under the true key and not under this "
            "one",
            served and s_h == 200 and fp and fp[0] == hashlib.sha256(
                k2.encode()).hexdigest()
            and chained and chained[0] == L.sentinel.frag_ref(k1, "KEY")
            and chained[0] != L.sentinel.frag_ref(k2, "KEY"),
            {"served_after_wrong_key": s_h,
             "boot_refused_wrong_key": not served,
             "pinned_fp_is_wrong_key": bool(fp) and fp[0] ==
             hashlib.sha256(k2.encode()).hexdigest(),
             "chained_ref_matches_true_key":
                 bool(chained) and chained[0] ==
                 L.sentinel.frag_ref(k1, "KEY")})


def r5_14():
    A = L.instance("r5-rst", 19282, audit_key=None, key_file=True)
    A.start()
    A.stop()
    env = dict(A.env)
    out = os.path.join(A.dir, "backups")
    r = L.run_script("backup.py", env, ["--out", out, "--no-prune"])
    assert r.returncode == 0, r.stdout + r.stderr
    bset = os.path.join(out, sorted(os.listdir(out))[-1])
    old = time.time() - 60 * 86400   # keys created at install, 60d ago
    for suf in (".audit_key", ".signing_key.pem", ".signing_pub.pem"):
        os.utime(A.db + suf, (old, old))
    cfg = os.path.join(A.dir, "restored-config")
    r = L.run_script("restore.py", env, [bset, "--db", A.db,
                                         "--config-dir", cfg])
    aside = sorted(n for n in os.listdir(A.dir) if ".pre-restore-" in n)
    finding("R5-14", "a successful restore deletes the pre-restore "
            "copies of the live audit key and signing key it just moved "
            "aside (os.replace keeps their old mtime; the prune that "
            "follows is by mtime) — only the DB, -wal and -shm copies "
            "survive",
            r.returncode == 0 and not any(".audit_key" in n for n in aside)
            and any(n.startswith("janus.db.pre-restore-") for n in aside),
            {"restore_exit": r.returncode,
             "pruned_lines": [l for l in r.stdout.splitlines()
                              if "pruned" in l],
             "pre_restore_copies_left": aside})


def main():
    A = L.instance("r5-minor", 19280)
    A.start()
    try:
        for fn in (r5_12, r5_15, r5_16):
            try:
                fn(A)
            except Exception as exc:
                print("ERROR in %s: %r" % (fn.__name__, exc))
    finally:
        A.stop()
    for fn in (r5_13, r5_14):
        try:
            fn()
        except Exception as exc:
            print("ERROR in %s: %r" % (fn.__name__, exc))


if __name__ == "__main__":
    main()
    L.summary()
