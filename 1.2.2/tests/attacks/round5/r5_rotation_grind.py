"""R5-07 (A14c re-aimed): P9 replaced the publisher-supplied seed with
seed = SHA-256(sorted members | cycle_start | current chain root) and
claims 'nobody can grind it without rewriting the chain itself'. But
the publishing supervisor CHOOSES cycle_start (any real date) and can
move the chain root at will (any chained action — a GET /hits chains
HITS_VIEW). build_schedule is public and deterministic, so the
publisher tries candidates offline and publishes the one that pairs
the auditor they want with the agency they want.

1.2.2 RE-AIM (Q23): publishing is a commit-reveal ceremony now. The
seed is SHA-256 over the members' REVEALED nonces, each committed by
hash BEFORE any reveal; cycle_start is fixed by the commit (a second
commit naming a different start is refused while one is open, and
the chaining rule fixes later cycles), and the chain root is not a
seed input at all. The attack target is unchanged — can the
publishing supervisor still choose who audits whom? — and the
verdict asserts the defended behavior on each original vector:

  * publish with no ceremony open            -> refused (409)
  * publish carrying a publisher-chosen seed -> refused (400)
  * publish before every member revealed     -> refused (409)
  * re-commit a different cycle_start after
    the reveals (shopping the start once the
    seed is knowable)                        -> refused (409)
  * chain-root nudges between commit and
    publish change the published pairing     -> must NOT
  * the published schedule is exactly
    sentinel.rotation_schedule over the
    nonce-derived seed (member secrets are
    the deciding input, nothing the
    publisher controls is)

REPRODUCED iff any refusal above fails, or the root nudges move the
pairing, or the published schedule is not the nonce-derived one.
"""
import hashlib
import os
import secrets
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402

HOME = "THIS-AGENCY"   # janus.py default NOCTUA_AGENCY


def register(inst, agencies):
    pem = L.T.pub_pem(inst.db)
    for a in agencies:
        s, b = req(inst.port, "POST", "/compact/partners", L.SUP,
                   {"agency": a, "endpoint": "https://%s.example" % a,
                    "pubkey_pem": pem, "agreement_ref": "MOU"})
        assert s == 201, b


def nonce_seed(members, cycle_start, nonces):
    return hashlib.sha256(L.sentinel.canonical_bytes({
        "members": members, "cycle_start": cycle_start,
        "nonces": {m: nonces[m] for m in members}})).hexdigest()


def pairs_of(body):
    return [(r["auditor"], r["audited"]) for r in body.get("schedule",
                                                           [])]


def main():
    members = [HOME, "agency-a", "agency-b", "agency-c"]
    # the members' secrets — chosen by the members, unknown to the
    # publisher at commit time (only their hashes are on file)
    nonces = {m: "nonce-%s-%s" % (m, secrets.token_hex(8))
              for m in members}
    start = (date.today() + timedelta(days=30)).isoformat()
    start2 = (date.today() + timedelta(days=31)).isoformat()
    B = L.instance("r5-rot", 19260)
    C = L.instance("r5-rot2", 19261)
    B.start()
    C.start()
    try:
        register(B, members[1:])
        register(C, members[1:])
        # --- vector 0: no ceremony / publisher seed / early publish
        s_nocer, _b = req(B.port, "POST", "/compact/rotation", L.SUP,
                          {"members": members, "cycle_start": start,
                           "period_days": 30})
        s_seed, _b = req(B.port, "POST", "/compact/rotation", L.SUP,
                         {"members": members, "cycle_start": start,
                          "period_days": 30, "seed": "ab" * 32})
        # --- the ceremony on B, with root nudges mid-flight ---
        s, b = req(B.port, "POST", "/compact/rotation/commit", L.SUP,
                   {"members": members, "cycle_start": start,
                    "period_days": 30,
                    "nonce_hashes": {m: L.T.sha(nonces[m])
                                     for m in members}})
        assert s == 201, b
        s_early, _b = req(B.port, "POST", "/compact/rotation",
                          L.SUP, {"members": members,
                                  "cycle_start": start,
                                  "period_days": 30})
        root0 = req(B.port, "GET", "/audit/root", L.SUP)[1]["root"]
        for _i in range(3):
            req(B.port, "GET", "/hits", L.SUP)   # chains HITS_VIEW
        root1 = req(B.port, "GET", "/audit/root", L.SUP)[1]["root"]
        for m in members:
            s, b = req(B.port, "POST", "/compact/rotation/reveal",
                       L.SUP, {"cycle_start": start, "agency": m,
                               "nonce": nonces[m]})
            assert s == 201, b
        # shopping the start once the seed is knowable:
        s_reshop, _b = req(B.port, "POST", "/compact/rotation/commit",
                           L.SUP, {"members": members,
                                   "cycle_start": start2,
                                   "period_days": 30,
                                   "nonce_hashes": {
                                       m: L.T.sha(nonces[m])
                                       for m in members}})
        s_pub_b, body_b = req(B.port, "POST", "/compact/rotation",
                              L.SUP, {"members": members,
                                      "cycle_start": start,
                                      "period_days": 30})
        # --- the same ceremony on C: same nonces, same start, NO
        # root nudges — the pairing must come out identical ---
        _n, (s_pub_c, body_c) = L.T.rotation_ceremony(
            C.port, members, start, 30, nonces=nonces)
    finally:
        B.stop()
        C.stop()
    seed = nonce_seed(members, start, nonces)
    expect = [(r["auditor"], r["audited"]) for r in
              L.sentinel.rotation_schedule(members, seed)["rounds"]]
    got_b, got_c = pairs_of(body_b), pairs_of(body_c)
    refusals_ok = (s_nocer == 409 and s_seed == 400
                   and s_early == 409 and s_reshop == 409)
    reproduced = not refusals_ok \
        or got_b != expect or got_c != expect or got_b != got_c
    finding("R5-07", "the publishing supervisor still chooses who "
            "audits whom: grinding cycle_start offline (chain "
            "untouched) or nudging the chain root with an ordinary "
            "chained GET yields the wanted pair in a few tries, and "
            "Janus publishes it 201 with a valid signature",
            reproduced,
            {"publish_without_ceremony": s_nocer,
             "publish_with_publisher_seed": s_seed,
             "publish_before_reveals": s_early,
             "recommit_different_start_after_reveals": s_reshop,
             "root_before_nudges": root0[:16],
             "root_after_nudges": root1[:16],
             "publish_b": s_pub_b, "publish_c": s_pub_c,
             "schedule_is_nonce_derived": got_b == expect,
             "root_nudges_changed_pairing": got_b != got_c,
             "published_pairs": got_b})


if __name__ == "__main__":
    main()
    L.summary()
