"""R5-01: a protection-order suppression placed under 1.1 is honored by
/search after the blessed 1.1 -> 1.2.1 upgrade (the P4 test checks
exactly that) but is invisible to every check that uses the keyed
plate_ref: 1.1 keyed suppressions by HMAC(PLATE|STATE), 1.2+ by
HMAC(canonical plate). Nothing re-keys the legacy rows.

Upgrade shape is the one the builders bless for P4/A28: a 1.1
key-FILE deployment (no env key), upgraded in place."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding


def main():
    d = os.path.join(L.T.WORK, "r5-legacy")
    os.makedirs(d)
    env = dict(os.environ)
    env.pop("NOCTUA_AUDIT_KEY", None)
    env.update({"NOCTUA_DB": os.path.join(d, "janus.db"),
                "NOCTUA_USERS": os.path.join(d, "users.json"),
                "NOCTUA_CASES": os.path.join(d, "cases.json"),
                "NOCTUA_CAMERAS": os.path.join(d, "cameras.json"),
                "NOCTUA_PORT": "19201",
                "NOCTUA_EVIDENCE_DIR": os.path.join(d, "evidence")})
    L.T.write_users(env["NOCTUA_USERS"])
    L.T.write_cases(env["NOCTUA_CASES"])
    L.T.write_cameras(env["NOCTUA_CAMERAS"])

    # ---- life under 1.1: a protection order on PRT100 ----
    p = L.boot_script(L.JANUS11, env, 19201, d)
    try:
        s, b = req(19201, "POST", "/suppressions", L.SUP,
                   {"plate": "PRT100", "order_ref": "PO-77 (DEMO)"})
        assert s in (200, 201), (s, b)
    finally:
        p.terminate()
        p.wait(timeout=10)
    import sqlite3
    c = sqlite3.connect(env["NOCTUA_DB"])
    legacy = c.execute("SELECT plate_ref, plate, state, active FROM "
                       "suppressions").fetchall()
    c.close()

    # ---- upgrade in place to 1.2.1 ----
    p = L.boot_script(L.JANUS, env, 19201, d)
    try:
        key = open(env["NOCTUA_DB"] + ".audit_key").read().strip()
        canonical_ref = L.sentinel.plate_ref(key, "PRT100")
        # a detective puts the protected vehicle on the hot list
        s_add, b_add = req(19201, "POST", "/hotlist", L.DET,
                           {"plate": "PRT100", "state": "AR",
                            "category": "warrant", "case": "2027-1031"})
        # the protected person drives past a camera
        s_rd, b_rd = req(19201, "POST", "/reads", L.ING,
                         {"plate": "PRT100", "state": "AR",
                          "cam": "CAM-02"})
        hit_id = b_rd.get("hit_id")
        s_h, b_h = req(19201, "GET", "/hits", L.DET)
        visible = [h for h in b_h.get("hits", [])
                   if h.get("read_plate") == "PRT100"]
        s_v, b_v = req(19201, "POST", "/verify", L.DET,
                       {"hit_id": hit_id, "decision": "confirm",
                        "case": "2027-1031"}) if hit_id else (None, None)
        s_x, b_x = req(19201, "POST", "/evidence/export", L.DET,
                       {"hit_id": hit_id, "case_id": "2027-1031"}) \
            if hit_id else (None, None)
        s_q, b_q = req(19201, "GET", "/suppressed-hits", L.SUP)
        in_queue = [h for h in b_q.get("hits", []) if h["id"] == hit_id]
        s_rel, b_rel = req(19201, "POST", "/suppressions/release", L.SUP,
                           {"plate": "PRT100",
                            "order_ref": "PO-77 (DEMO)"})
        s_s, b_s = req(19201, "GET", "/search?plate=PRT100&case="
                       "2027-1031&justification=r5&tier=2", L.DET)
    finally:
        p.terminate()
        p.wait(timeout=10)

    finding("R5-01", "after the blessed 1.1->1.2.1 upgrade a 1.1 "
            "protection-order suppression is void for every keyed check: "
            "a detective hot-lists the protected plate, sees its hit with "
            "plate+camera+time in /hits, verifies it and exports it; the "
            "supervisor queue is empty and the order cannot be released "
            "(404). Only the plate-text SQL filters (/search here; share "
            "and Tier 3 use the same filter) still hide the plate.",
            s_add == 201 and bool(visible) and s_v == 200
            and s_x == 201 and not in_queue and s_rel == 404
            and s_s == 200 and b_s.get("reads") == [],
            {"legacy_row": legacy,
             "legacy_ref_equals_canonical_ref":
                 bool(legacy) and legacy[0][0] == canonical_ref,
             "hotlist_add": s_add, "read": b_rd,
             "hits_visible_to_detective": visible,
             "detective_verify": s_v, "detective_export": s_x,
             "supervisor_queue_has_hit": bool(in_queue),
             "release": (s_rel, b_rel),
             "search_reads": b_s.get("reads")})


if __name__ == "__main__":
    main()
    L.summary()
