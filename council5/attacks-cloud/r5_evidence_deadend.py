"""R5-04: an exported, not-yet-released evidence bundle protects its
hit only until the 150-day cap (sentinel.HIT_PROTECTED_SQL /
retention.py:166). When retention then deletes the hit row, the
bundle's whole exit path dies with it: /evidence/release and
/evidence/disposition both require the hit row (janus.py:2853, 2935)
and /evidence/destroy requires a release (janus.py:2904). destroy_by
is never set, so retention never destroys the bundle and the registry
check never flags it (sentinel.py:588-599 only flags destroyed-on-
paper or past-destroy_by bundles). Every exported bundle whose case
outlives 150 days becomes a permanent plate+time+place archive that
no endpoint can release or destroy and no check reports."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def main():
    A = L.instance("r5-ev", 19230)
    A.start()
    try:
        p = A.port
        s, b = req(p, "POST", "/hotlist", L.DET,
                   {"plate": "EVD150", "state": "AR",
                    "category": "felony_warrant", "case": "2027-1023"})
        assert s == 201, b
        s, b = req(p, "POST", "/reads", L.ING,
                   {"plate": "EVD150", "state": "AR", "cam": "CAM-05"})
        hit = b["hit_id"]
        s, b = req(p, "POST", "/verify", L.DET,
                   {"hit_id": hit, "decision": "confirm",
                    "case": "2027-1023"})
        assert s == 200, b
        s, b = req(p, "POST", "/evidence/export", L.DET,
                   {"hit_id": hit, "case_id": "2027-1023"})
        assert s == 201, b
        bundle = b["bundle"]
        bundle_path = os.path.join(A.env["NOCTUA_EVIDENCE_DIR"], bundle)
        # The prosecution runs past day 150 (a felony trial date).
        c = L.db(A)
        c.execute("UPDATE hits SET ts=? WHERE id=?",
                  (L.ago(days=151), hit))
        c.commit()
        c.close()
        r = L.run_script("retention.py", L.script_env(A))
        c = L.db(A)
        hit_left = c.execute("SELECT COUNT(*) FROM hits WHERE id=?",
                             (hit,)).fetchone()[0]
        ev_row = c.execute("SELECT bundle, released_ts, destroy_by, "
                           "destroyed_ts FROM evidence WHERE hit_id=?",
                           (hit,)).fetchone()
        c.close()
        # Charges conclude; the agency tries to close the loop.
        s_rel, b_rel = req(p, "POST", "/evidence/release", L.SUP,
                           {"hit_id": hit, "prosecutor_signoff": {
                               "name": "DPA Example", "date": "2027-06-01"}})
        s_dsp, b_dsp = req(p, "POST", "/evidence/disposition", L.DET,
                           {"hit_id": hit, "outcome": "charges_concluded",
                            "by": "DPA Example", "date": "2027-06-01"})
        s_des, b_des = req(p, "POST", "/evidence/destroy", L.SUP,
                           {"hit_id": hit})
        L.heartbeat_all(p)
        h = L.T.health(p)
        aud = L.run_script("sentinel_audit.py", dict(A.env),
                           ["--db", A.db])
        import json
        rep = json.loads(aud.stdout)
        ev_check = [x for x in rep["checks"]
                    if x["name"] == "registry: evidence bundles"]
    finally:
        A.stop()
    finding("R5-04", "an exported, unreleased evidence bundle outlives "
            "its hit's 150-day purge and then can never be released "
            "(404), dispositioned (404) or destroyed (409); destroy_by is "
            "never set, retention never destroys it, and /health and "
            "sentinel_audit both report the evidence store clean",
            hit_left == 0 and os.path.isdir(bundle_path)
            and s_rel == 404 and s_dsp == 404 and s_des == 409
            and "evidence bundles" not in
            h["degraded"]["retention_breach"]
            and ev_check and ev_check[0]["status"] == "ok",
            {"retention": r.stdout.strip()[-200:], "hit_rows_left":
             hit_left, "evidence_row": ev_row,
             "bundle_on_disk": os.path.isdir(bundle_path),
             "release": (s_rel, b_rel), "disposition": (s_dsp, b_dsp),
             "destroy": (s_des, b_des),
             "health_retention_breach":
                 h["degraded"]["retention_breach"],
             "sentinel_audit_evidence": ev_check})


if __name__ == "__main__":
    main()
    L.summary()
