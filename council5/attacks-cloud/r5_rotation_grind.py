"""R5-07 (A14c re-aimed): P9 replaced the publisher-supplied seed with
seed = SHA-256(sorted members | cycle_start | current chain root) and
claims 'nobody can grind it without rewriting the chain itself'. But
the publishing supervisor CHOOSES cycle_start (any real date) and can
move the chain root at will (any chained action — a GET /hits chains
HITS_VIEW). build_schedule is public and deterministic, so the
publisher tries candidates offline and publishes the one that pairs
the auditor they want with the agency they want."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402

HOME = "THIS-AGENCY"   # janus.py default NOCTUA_AGENCY


def rounds(members, cycle_start, root):
    seed = L.rotation.seed_for(members, cycle_start, root)
    order = L.rotation.permute(members, seed)
    n = len(order)
    return [(order[r], order[(r + 1) % n]) for r in range(n)]


def pairs(members, cycle_start, root):
    return set(rounds(members, cycle_start, root))


def register(inst, agencies):
    pem = L.T.pub_pem(inst.db)
    for a in agencies:
        s, b = req(inst.port, "POST", "/compact/partners", L.SUP,
                   {"agency": a, "endpoint": "https://%s.example" % a,
                    "pubkey_pem": pem, "agreement_ref": "MOU"})
        assert s == 201, b


def main():
    members = [HOME, "agency-a", "agency-b", "agency-c"]
    want = ("agency-a", "agency-b")         # the cozy pair
    B = L.instance("r5-rot", 19260)
    C = L.instance("r5-rot2", 19261)
    B.start()
    C.start()
    try:
        register(B, members[1:])
        register(C, members[1:])
        # --- grind 1: cycle_start, chain untouched ---
        root = req(B.port, "GET", "/audit/root", L.SUP)[1]["root"]
        tries, start = 0, None
        for k in range(0, 400):
            tries += 1
            cand = (date(2027, 1, 1) + timedelta(days=k)).isoformat()
            if want in pairs(members, cand, root):
                start = cand
                break
        s, b = req(B.port, "POST", "/compact/rotation", L.SUP,
                   {"members": members, "cycle_start": start,
                    "period_days": 30})
        got = {(r["auditor"], r["audited"]) for r in b.get("schedule", [])}
        exact1 = [(r["auditor"], r["audited"]) for r in
                  b.get("schedule", [])] == rounds(members, start, root)
        # --- grind 2: fixed cycle_start, move the chain root ---
        fixed = "2027-01-01"
        root_tries = 0
        while True:
            root_tries += 1
            root2 = req(C.port, "GET", "/audit/root", L.SUP)[1]["root"]
            if want in pairs(members, fixed, root2):
                break
            req(C.port, "GET", "/hits", L.SUP)   # chains HITS_VIEW
            if root_tries > 60:
                break
        s2, b2 = req(C.port, "POST", "/compact/rotation", L.SUP,
                     {"members": members, "cycle_start": fixed,
                      "period_days": 30})
        got2 = {(r["auditor"], r["audited"]) for r in b2.get("schedule",
                                                             [])}
        exact2 = [(r["auditor"], r["audited"]) for r in
                  b2.get("schedule", [])] == rounds(members, fixed, root2)
    finally:
        B.stop()
        C.stop()
    # expected tries for one chosen directed pair among 4 members: 3
    trials, total = 300, 0
    for t in range(trials):
        r = "%064x" % (t * 7919)
        for k in range(1, 400):
            cand = (date(2027, 1, 1) + timedelta(days=k)).isoformat()
            if want in pairs(members, cand, r):
                total += k
                break
    finding("R5-07", "the publishing supervisor still chooses who "
            "audits whom: grinding cycle_start offline (chain untouched) "
            "or nudging the chain root with an ordinary chained GET "
            "yields the wanted pair in a few tries, and Janus publishes "
            "it 201 with a valid signature",
            s == 201 and want in got and s2 == 201 and want in got2
            and exact1 and exact2,
            {"wanted": want, "cycle_start_tries": tries,
             "published_with_cycle_start": start, "publish": s,
             "pair_in_schedule": want in got,
             "root_nudges_needed": root_tries, "publish2": s2,
             "pair_in_schedule2": want in got2,
             "offline_prediction_equals_published": [exact1, exact2],
             "mean_tries_over_%d_trials" % trials:
                 round(total / trials, 2)})


if __name__ == "__main__":
    main()
    L.summary()
