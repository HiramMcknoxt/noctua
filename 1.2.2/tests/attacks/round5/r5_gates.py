"""R5-08..R5-11: the human gates around Tier 3, holds and the case
list, checked against pilot-spec-v2 (spec/pilot-spec-v2.md):

R5-08 (spec section 8, Emergency row; round-4 R17): 'every emergency
      use receives post-hoc review ... by the outside auditor in all
      cases.' In 1.2.1 any OTHER supervisor's review clears the flag,
      after which the auditor's review is refused (409); and the
      auditor's only views (/tier3/pending, /tier3/reviews) carry
      hashes — no fragment, case, justification or basis — so an
      auditor who does get there first grades blind.
R5-09 (spec section 4 'settable by the Administrator on a documented
      case basis'; section 9 'a suspicion, a query, or a bulk hold is
      not an investigation'): a DETECTIVE places a scope='hit' hold
      with no case on a hit that was REJECTED as a misread; retention
      keeps the innocent driver's record past HOLD_DAYS. One
      supervisor releases a hold without any disposition.
R5-10 (spec section 7 item 9): 'If the case-list / RMS feed has not
      refreshed within its configured window, the front door fails
      closed.' 1.2.1 marks config stale only when a reload FAILS; a
      case export that simply stopped a month ago leaves every case
      open and /health green.
R5-11 (spec section 7 item 3 and front matter 2): Tier 3 'unlock[s]
      only on an entered judicial-authorization number with the
      signed authorization uploaded ... The front door never invents
      its own instrument.' basis_type='other' with free text executes."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def r5_08(A):
    p = A.port
    # 1.2.2 RE-AIM (Q11): the emergency SETUP can no longer use
    # basis_type "other" — Tier 3 executes only on a configured
    # instrument now. The setup uses "warrant"; the attack targets
    # (auditor pre-emption, auditor blindness) are unchanged.
    s, b = req(p, "POST", "/tier3/emergency", L.SUP,
               {"plate_fragment": "EMR4", "case_id": "2027-1040",
                "why": "abducted child, suspect vehicle partial",
                "auth_basis": "exigent - judge to be notified",
                "basis_type": "warrant"})
    assert s == 200, b
    rid = b["request_id"]
    s_rv, b_rv = req(p, "GET", "/tier3/reviews", L.AUD)
    s_pd, b_pd = req(p, "GET", "/tier3/pending", L.AUD)
    aud_view = [r for r in b_rv.get("reviews", []) if r["request_id"]
                == rid] + [r for r in b_pd.get("pending", [])
                           if r["id"] == rid]
    blind = all(not any(k in r for k in ("why", "auth_basis",
                                         "plate_fragment", "case_no"))
                for r in aud_view)
    s_sr, b_sr = req(p, "POST", "/tier3/review", L.SUP2,
                     {"request_id": rid, "finding": "justified",
                      "note": "ok"})
    s_ar, b_ar = req(p, "POST", "/tier3/review", L.AUD,
                     {"request_id": rid, "finding": "needs_followup"})
    finding("R5-08", "the outside auditor's mandatory post-hoc review "
            "of an EMERGENCY Tier 3 search is pre-empted: a second "
            "supervisor marks it justified and the auditor is then "
            "refused (409); the auditor's own views show only hashes",
            blind and s_sr == 200 and s_ar == 409,
            {"auditor_view": aud_view, "supervisor_review": s_sr,
             "auditor_review": (s_ar, b_ar)})


def r5_09(A):
    p = A.port
    s, b = req(p, "POST", "/hotlist", L.DET,
               {"plate": "HLD100", "state": "AR",
                "category": "stolen_vehicle", "case": "2027-1052"})
    assert s == 201, b
    h_held = req(p, "POST", "/reads", L.ING,
                 {"plate": "HLD100", "state": "AR", "cam": "CAM-08"}
                 )[1]["hit_id"]
    h_ctl = req(p, "POST", "/reads", L.ING,
                {"plate": "HLD100", "state": "AR", "cam": "CAM-09"}
                )[1]["hit_id"]
    # both were misreads: rejected at the roadside
    for h in (h_held, h_ctl):
        s, b = req(p, "POST", "/verify", L.PAT,
                   {"hit_id": h, "decision": "reject",
                    "case": "2027-1052"})
        assert s == 200, b
    s_h, b_h = req(p, "POST", "/holds", L.DET,
                   {"scope": "hit", "ref": str(h_held),
                    "reason": "just in case"})
    c = L.db(A)
    for h in (h_held, h_ctl):
        c.execute("UPDATE hits SET ts=? WHERE id=?",
                  (L.ago(days=60), h))
    c.commit()
    c.close()
    L.run_script("retention.py", L.script_env(A))
    c = L.db(A)
    left = [r[0] for r in c.execute("SELECT id FROM hits WHERE id IN "
                                    "(?,?)", (h_held, h_ctl))]
    c.close()
    s_rel, b_rel = req(p, "POST", "/holds/release", L.SUP,
                       {"hold_id": b_h.get("hold_id")})
    finding("R5-09", "a detective places a hold with NO case on a hit "
            "already REJECTED as a misread; retention keeps the innocent "
            "driver's plate/camera/time past HOLD_DAYS (control hit "
            "deleted); one supervisor then releases the hold with no "
            "disposition",
            s_h == 201 and h_held in left and h_ctl not in left
            and s_rel == 200,
            {"hold": (s_h, b_h), "hits_left_after_retention": left,
             "held": h_held, "control": h_ctl, "release": s_rel})


def r5_10():
    A = L.instance("r5-stale", 19271)
    # the nightly case export stopped 30 days ago; the file is intact
    old = time.time() - 30 * 86400
    os.utime(A.cases, (old, old))
    A.start()
    try:
        L.heartbeat_all(A.port)
        s, b = req(A.port, "GET", "/search?plate=ZZZ&case=2027-1001"
                   "&justification=r5&tier=2", L.DET)
        h = L.T.health(A.port)
    finally:
        A.stop()
    finding("R5-10", "a case list whose feed stopped 30 days ago never "
            "goes stale: searches run against it and /health reports the "
            "config fresh (staleness = failed reload only)",
            s == 200 and not h["degraded"]["config"]["cases"]["stale"],
            {"search": s, "config": h["degraded"]["config"]})


def r5_11(A):
    # 1.2.2 RE-AIM (Q11): basis_type "other" can no longer execute —
    # Tier 3 runs only on a configured instrument. The verdict now
    # asserts exactly that refusal: REPRODUCED only if the search
    # EXECUTES on "other" (via the request path here, or the
    # emergency path below). The original execution form is also
    # covered by the builders'/Q-case suites.
    p = A.port
    s, b = req(p, "POST", "/tier3/request", L.DET,
               {"plate_fragment": "OTH", "case_id": "2027-1001",
                "why": "curious about this car",
                "auth_basis": "verbal OK from the lieutenant",
                "basis_type": "other"})
    s2, b2 = (None, {})
    if s == 201:
        s2, b2 = req(p, "POST", "/tier3/approve", L.SUP,
                     {"request_id": b["request_id"]})
    s3, b3 = req(p, "POST", "/tier3/emergency", L.SUP,
                 {"plate_fragment": "OTH", "case_id": "2027-1001",
                  "why": "curious about this car",
                  "auth_basis": "verbal OK from the lieutenant",
                  "basis_type": "other"})
    executed = (s2 == 200 and b2.get("result") == "EXECUTED") or \
        (s3 == 200 and str(b3.get("result", "")).startswith("EXECUTED"))
    finding("R5-11", "a Tier 3 historical search executes on "
            "basis_type='other' with free-text auth_basis ('verbal OK "
            "from the lieutenant'): no judicial instrument, no number, "
            "no uploaded authorization",
            executed,
            {"request": (s, b), "approve": (s2, b2),
             "emergency": (s3, b3)})


def main():
    A = L.instance("r5-gates", 19270)
    A.start()
    try:
        for fn in (r5_08, r5_09, r5_11):
            try:
                fn(A)
            except Exception as exc:  # one attack must not hide others
                print("ERROR in %s: %r" % (fn.__name__, exc))
    finally:
        A.stop()
    try:
        r5_10()
    except Exception as exc:
        print("ERROR in r5_10: %r" % exc)


if __name__ == "__main__":
    main()
    L.summary()
