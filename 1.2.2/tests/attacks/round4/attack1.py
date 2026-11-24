"""Batch 1: hot list sweep, Compact share tier, signed-report replay,
receipt age, raw text into the chain, hot-list removal no-op,
witness attestations, rotation publish/status."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *  # noqa: F401,F403
import lib
from lib import T, req, finding


def a1_hotlist_sync_wipes_open_ended():
    E = lib.instance("hs", 19101)
    E.start()
    try:
        p = E.port
        s, b = req(p, "POST", "/hotlist", lib.DET,
                   {"plate": "OPN100", "state": "AR",
                    "category": "stolen vehicle", "case": "2027-1014"})
        assert s == 201, b
        s, b = req(p, "POST", "/hotlist", lib.DET,
                   {"plate": "FUT200", "state": "AR", "category": "warrant",
                    "case": "2027-1014", "expires": lib.ahead(days=30)})
        assert s == 201, b
        row = lib.db(E).execute(
            "SELECT expires_ts FROM hotlist_members WHERE plate='OPN100'"
        ).fetchone()
        r = lib.run_script("hotlist_sync.py", {
            "NOCTUA_DB": E.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
            "NOCTUA_JANUS_URL": E.url, "NOCTUA_JOBS_USER": lib.JOB,
            "NOCTUA_JOBS_KEY": lib.KEYS[lib.JOB]})
        s, b = req(p, "GET", "/hotlist", lib.SUP)
        active = sorted(e["plate"] for e in b["entries"])
        s2, b2 = req(p, "POST", "/reads", lib.ING,
                     {"plate": "OPN100", "state": "AR", "cam": "CAM-01"})
        kinds = [e["kind"] for e in lib.chain_entries(p)]
        finding("A1 hotlist_sync deactivates every hot-list entry that "
                "has NO expiry (expires_ts stored as '')",
                "OPN100" not in active and b2.get("result") == "stored",
                {"stored_expires_ts": row, "sync_stdout": r.stdout.strip(),
                 "active_after_sync": active,
                 "ingest_of_stolen_plate": b2,
                 "HOTLIST_EXPIRED_entries": kinds.count("HOTLIST_EXPIRED")})
        # then retention deletes the deactivated membership outright once
        # its added_ts is older than RETENTION_DAYS
        c = lib.db(E)
        c.execute("UPDATE hotlist_members SET added_ts=? WHERE "
                  "plate='OPN100'", (lib.ago(days=20),))
        c.commit()
        c.close()
        r = lib.run_script("retention.py", {
            "NOCTUA_DB": E.db, "NOCTUA_AUDIT_KEY": T.AUDIT_KEY,
            "NOCTUA_JANUS_URL": E.url, "NOCTUA_JOBS_USER": lib.JOB,
            "NOCTUA_JOBS_KEY": lib.KEYS[lib.JOB]})
        n = lib.db(E).execute("SELECT COUNT(*) FROM hotlist_members "
                              "WHERE plate='OPN100'").fetchone()[0]
        finding("A1b ...and retention then deletes the wiped membership "
                "row (20-day-old stolen-vehicle entry)", n == 0,
                {"rows_left": n, "retention": r.stdout.strip()[-200:]})
    finally:
        E.stop()


def compact_pair(pa, pb, na, nb):
    A = lib.instance(na, pa)
    B = lib.instance(nb, pb)
    A.start()
    B.start()
    return A, B


def a2_a3_a4_compact(A, B):
    pb = B.port
    lib.open_gate(B, A, "agency-a")
    # a historical read, 25 h old (outside the Tier 2 window)
    c = lib.db(B)
    c.execute("INSERT INTO reads(ts,cam,plate,plate_raw,state,conf) "
              "VALUES(?,?,?,?,?,?)",
              (lib.ago(hours=25), "CAM-02", "HIS777", "HIS777", "AR", 0.9))
    c.execute("INSERT INTO reads(ts,cam,plate,plate_raw,state,conf) "
              "VALUES(?,?,?,?,?,?)",
              (lib.ago(days=12), "CAM-05", "HIS777", "HIS777", "AR", 0.9))
    c.commit()
    c.close()
    share = {"agency": "agency-a", "plate_fragment": "HIS",
             "case_ref": "AGA-55", "why": "regional sweep",
             "basis_type": "warrant"}
    s2, b2 = req(pb, "POST", "/share/query", "agency-a", dict(share, tier=2))
    s1, b1 = req(pb, "POST", "/share/query", "agency-a", dict(share, tier=1))
    sT, bT = req(pb, "POST", "/share/query", "agency-a",
                 dict(share, tier=True))
    s3, b3 = req(pb, "POST", "/share/query", "agency-a", dict(share, tier=3))
    finding("A2 partner share with tier=1 (or tier=true) runs a FULL-scope "
            "historical search; only tier=3 is refused",
            s1 == 200 and len(b1["results"]["reads"]) == 2
            and len(b2["results"]["reads"]) == 0,
            {"tier2_reads": len(b2.get("results", {}).get("reads", [])),
             "tier1_status": s1,
             "tier1_reads": [(r["ts"], r["plate"]) for r in
                             b1.get("results", {}).get("reads", [])],
             "tier_true_reads": len(bT.get("results", {}).get("reads", [])),
             "tier3_status": s3})
    ents = lib.chain_entries(pb)
    outs = [e["fields"] for e in ents if e["kind"] == "SHARE_OUT"][:3]
    finding("A2b the chain records the tier-1 share as tier 1 — no entry "
            "says the Tier 2 wall was skipped",
            any(f.get("tier") == 1 for f in outs), outs)

    # A3: signed report replay across time and across partners
    s, b = req(pb, "POST", "/compact/partners", lib.SUP,
               {"agency": "agency-c", "endpoint": "http://c.example",
                "pubkey_pem": T.pub_pem(A.db), "agreement_ref": "MOU-C"})
    assert s == 201, b
    old_report = {"agency": "agency-a", "ok": True,
                  "ts": "2025-01-01T00:00:00Z", "checks": {}}
    sig = T.sign(B.db, old_report)
    s, b = req(pb, "POST", "/compact/audit-result", lib.AUD,
               {"agency": "agency-a", "report": old_report,
                "report_sig": sig})
    first = (s, b)
    # replay the SAME signed body under another partner's name
    s, b = req(pb, "POST", "/compact/audit-result", lib.SUP,
               {"agency": "agency-c", "report": old_report,
                "report_sig": sig})
    second = (s, b)
    rows = lib.db(B).execute(
        "SELECT agency, ok, ts, substr(detail,1,60) FROM compact_audits "
        "ORDER BY id DESC LIMIT 2").fetchall()
    s, b = req(pb, "GET", "/compact/partners", lib.SUP)
    c_row = [x for x in b["partners"] if x["agency"] == "agency-c"]
    finding("A3 a signed audit report from 2025 is accepted today and "
            "stamped fresh; the same signed body is re-filed as a "
            "passing audit of a DIFFERENT partner (agency-c) by a "
            "supervisor",
            first[0] == 201 and second[0] == 201
            and c_row and c_row[0]["last_audit_ok"] is True,
            {"first": first, "second": second, "rows": rows,
             "agency_c_partner_row": c_row})

    # A4: the gate never looks at the receipt's age
    c = lib.db(B)
    c.execute("UPDATE compact_receipts SET checkpoint_ts=?, received_ts=? "
              "WHERE agency='agency-a'", ("2020-01-01T00:00:00Z",
                                         "2020-01-01T00:00:00Z"))
    c.commit()
    c.close()
    T.post_audit_result(B.port, B.db, "agency-a", True)
    s, b = req(pb, "POST", "/share/query", "agency-a", dict(share, tier=2))
    finding("A4 share gate opens on a receipt whose checkpoint is years "
            "old (gate checks root/entries only; freshness is checked "
            "only when the receipt is POSTed)", s == 200, (s, b))

    # A21: raw text into the permanent chain through an exempt field
    s, b = req(pb, "POST", "/share/query", lib.PAT,
               {"agency": "ABC123", "plate_fragment": "ABC"})
    ents = lib.chain_entries(pb)
    sb = [e["fields"] for e in ents if e["kind"] == "SHARE_BLOCKED"][:1]
    finding("A21 any logged-in role (here patrol) writes a raw "
            "plate-shaped string into the permanent chain via "
            "SHARE_BLOCKED.agency (scrubber-exempt field)",
            sb and sb[0].get("agency") == "ABC123", sb)
    s, b = req(pb, "POST", "/compact/suspend", lib.SUP,
               {"agency": "no such partner ABC 123"})
    ents = lib.chain_entries(pb)
    ps = [e["fields"] for e in ents if e["kind"] == "PARTNER_SUSPEND"][:1]
    finding("A21b /compact/suspend of a partner that does not exist "
            "answers 200 and chains PARTNER_SUSPEND with the raw text",
            s == 200 and ps and "ABC 123" in ps[0].get("agency", ""),
            (s, ps))

    # A25: witness attestations — any role, no chain entry
    before = len(lib.chain_entries(pb))
    s, b = req(pb, "POST", "/compact/witness", lib.ING,
               {"agency": "agency-a", "cycle_start": "2027-01-04",
                "round": 1, "ok": True, "detail": "ingest says so"})
    after = len(lib.chain_entries(pb))
    finding("A25 the ingest service account files a witness attestation "
            "for another agency; nothing is chained",
            s == 201 and after == before, {"status": s, "body": b,
                                           "chain_delta": after - before})


def a24_hotlist_delete_noop(A):
    p = A.port
    s, b = req(p, "POST", "/hotlist", lib.DET,
               {"plate": "DEL100", "state": "AR", "category": "stolen vehicle",
                "case": "2027-1014"})
    assert s == 201, b
    s, b = req(p, "DELETE", "/hotlist", lib.SUP, {"plate": "DEL100"})
    s2, b2 = req(p, "GET", "/hotlist", lib.SUP)
    still = any(e["plate"] == "DEL100" for e in b2["entries"])
    kinds = [e["kind"] for e in lib.chain_entries(p)]
    finding("A24 DELETE /hotlist without the entry's state answers 200 "
            "'membership deactivated' and chains HOTLIST_REMOVE while the "
            "entry stays active", s == 200 and still
            and "HOTLIST_REMOVE" in kinds, (s, b, "still active:", still))


def a14_rotation(A):
    p = A.port
    for ag in ("agency-a", "agency-b", "agency-c", "agency-d"):
        req(p, "POST", "/compact/partners", lib.SUP,
            {"agency": ag, "endpoint": "http://x",
             "pubkey_pem": T.pub_pem(A.db)})
    members = ["agency-a", "agency-b", "agency-c", "agency-d"]
    s, b = req(p, "POST", "/compact/rotation", lib.SUP,
               {"cycle_start": "2027-01-04", "period_days": 30,
                "members": members})
    finding("A14a rotation publish without an explicit seed is a 500 "
            "(uuid is never imported in janus.py)",
            s == 500 and "uuid" in json.dumps(b), (s, b))
    # 1.2.2 RE-AIM (Q23): publishing is a commit-reveal ceremony
    # now; a publisher-supplied seed is refused at the door. The
    # A14b/A14c intents are preserved against the new contract:
    # A14b checks a legitimately published FUTURE cycle's status;
    # A14c checks the publisher still cannot pick the pairing —
    # supplied seed refused, the published seed recomputes from
    # ALL members' revealed nonces, and a reveal that does not
    # match its commitment is refused.
    s_seed, b_seed = req(p, "POST", "/compact/rotation/commit",
                         lib.SUP,
                         {"cycle_start": "2027-01-04", "period_days": 30,
                          "members": members, "seed": "s1"})
    nonces, pub = T.rotation_ceremony(p, members, "2027-01-04")
    assert pub[0] in (200, 201), pub
    s, b = req(p, "GET", "/compact/rotation/status", lib.SUP)
    finding("A14b a cycle that has not started yet already lists "
            "delinquent agencies (future rounds count as 'filed in "
            "neither')", s == 200 and b.get("delinquent_agencies"),
            {"delinquent_agencies": b.get("delinquent_agencies"),
             "rounds": [(r["round"], r["auditor"], r["window_start"],
                         r["delinquent"]) for r in b.get("rounds", [])]})
    import hashlib as _hl
    seed_expect = _hl.sha256(T.sentinel_mod.canonical_bytes(
        {"members": sorted(members), "cycle_start": "2027-01-04",
         "nonces": nonces})).hexdigest()
    seed_ok = pub[1].get("seed") == seed_expect
    # a reveal swapped after seeing the other commitments:
    start2 = "2027-02-03"  # chained: previous cycle's end
    fake = {m: "nonce-%s" % m for m in members}
    hashes = {m: _hl.sha256(n.encode()).hexdigest()
              for m, n in fake.items()}
    s_c, b_c = req(p, "POST", "/compact/rotation/commit", lib.SUP,
                   {"cycle_start": start2, "period_days": 30,
                    "members": members, "nonce_hashes": hashes})
    s_r, b_r = req(p, "POST", "/compact/rotation/reveal", lib.SUP,
                   {"cycle_start": start2, "agency": "agency-a",
                    "nonce": "a-swapped-nonce"})
    finding("A14c the publishing supervisor picks the seed: getting a "
            "chosen auditor for a chosen agency takes a handful of tries",
            s_seed in (200, 201) or not seed_ok or s_r in (200, 201),
            {"supplied_seed_status": s_seed, "supplied_seed_body": b_seed,
             "seed_recomputes_from_nonces": seed_ok,
             "commit2_status": s_c, "swapped_reveal_status": s_r,
             "swapped_reveal_body": b_r})


def _load_janus_build_schedule():
    """janus.build_schedule, exec'd from the shipped janus.py source text
    (importing janus would open a database and boot a server module);
    the function is pure."""
    import hashlib
    src = open(lib.JANUS).read()
    start = src.index("def build_schedule(members, seed):")
    end = src.index('if __name__ == "__main__":', start)
    ns = {"hashlib": hashlib}
    exec(src[start:end], ns)
    return ns["build_schedule"]


_JB = None


def A_build(members, seed):
    global _JB
    if _JB is None:
        _JB = _load_janus_build_schedule()
    return _JB(members, seed)


if __name__ == "__main__":
    a1_hotlist_sync_wipes_open_ended()
    A, B = compact_pair(19102, 19103, "ca", "cb")
    try:
        a2_a3_a4_compact(A, B)
        a24_hotlist_delete_noop(A)
        a14_rotation(A)
    finally:
        A.stop()
        B.stop()
    lib.summary()
