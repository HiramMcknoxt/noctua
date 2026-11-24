"""R5-03: the 1.2.1 supersede path (janus.py:1881-1936, the P13/A12
fix) replaces the stored read whenever a redelivery under the same
(camera, event_id) carries a DIFFERENT plate — whatever its
confidence, whatever its order — and withdraws (DELETES) any PENDING
hit the earlier OCR produced. Combined with the bridge's own
(event_id, plate) dedupe (frigate_bridge.py:233-239), Frigate's normal
update stream can end on its WORST guess with the stolen-plate alert
deleted.

  a) update A (0.80) -> update B (0.85, a misread the OCR briefly
     preferred) -> end A (0.90), confidence rising throughout: the
     bridge drops end-A as a duplicate of update-A; Janus is left
     holding B, the ALERT for A withdrawn.
  b) end (final, 0.93) arrives, then a delayed/replayed partial
     update (0.61, different text): the partial overwrites the final
     and withdraws its ALERT.
  c) a redelivery of the SAME plate at higher confidence (bridge
     restart, Frigate replay) deletes the PENDING hit and re-creates
     it under a new id: the hit id an officer was handed now 409s."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def lpr(eid, cam, plate, conf, typ):
    return {"type": typ, "after": {
        "id": eid, "camera": cam,
        "attributes": {"recognized_license_plate": [plate, conf]}}}


def main():
    A = L.instance("r5-sup", 19220)
    A.start()
    proc, event = L.bridge(A.url, 19221)
    try:
        p = A.port
        for plate in ("ABC1234", "STL777", "VAN555"):
            s, b = req(p, "POST", "/hotlist", L.DET,
                       {"plate": plate, "state": "AR",
                        "category": "stolen_vehicle",
                        "case": "2027-1014"})
            assert s == 201, b
        # ---- a) A -> B -> A through the bridge ----
        e = "1732460000.1-aaa"
        a1 = event(lpr(e, "CAM-01", "ABC1234", 0.80, "update"))
        a2 = event(lpr(e, "CAM-01", "A8C1234", 0.85, "update"))
        a3 = event(lpr(e, "CAM-01", "ABC1234", 0.90, "end"))
        c = L.db(A)
        read_a = c.execute("SELECT plate, conf FROM reads WHERE "
                           "event_id=?", (e,)).fetchall()
        pend_a = c.execute("SELECT id FROM hits WHERE read_plate="
                           "'ABC1234' AND status='PENDING'").fetchall()
        c.close()
        finding("R5-03a", "Frigate's update stream A(0.80) -> B(0.85) -> "
                "end A(0.90), confidence rising throughout, ends with "
                "Janus holding the misread B and the stolen-plate ALERT "
                "for A deleted (the bridge drops end-A as a duplicate of "
                "update-A)",
                read_a == [("A8C1234", 0.85)] and not pend_a,
                {"update_A": a1.get("janus"), "update_B": a2.get("janus"),
                 "end_A": a3, "stored": read_a,
                 "pending_hits_for_A": pend_a})
        # ---- b) final first, late partial second ----
        e = "1732460000.2-bbb"
        b1 = event(lpr(e, "CAM-02", "STL777", 0.93, "end"))
        b2 = event(lpr(e, "CAM-02", "STL77", 0.61, "update"))
        c = L.db(A)
        read_b = c.execute("SELECT plate, conf FROM reads WHERE "
                           "event_id=?", (e,)).fetchall()
        pend_b = c.execute("SELECT id FROM hits WHERE read_plate="
                           "'STL777' AND status='PENDING'").fetchall()
        c.close()
        finding("R5-03b", "a delayed partial OCR (0.61) arriving after "
                "the final read (0.93) overwrites it and deletes the "
                "stolen-plate ALERT — 'different plate' supersedes "
                "regardless of confidence or event order",
                read_b == [("STL77", 0.61)] and not pend_b,
                {"end": b1.get("janus"), "late_update": b2.get("janus"),
                 "stored": read_b, "pending_hits_for_final": pend_b})
        # ---- c) same plate, higher confidence, direct redelivery ----
        e = "1732460000.3-ccc"
        s1, c1 = req(p, "POST", "/reads", L.ING,
                     {"plate": "VAN555", "state": "AR", "cam": "CAM-03",
                      "conf": 0.80, "event_id": e})
        first_hit = c1.get("hit_id")
        s2, c2 = req(p, "POST", "/reads", L.ING,
                     {"plate": "VAN555", "state": "AR", "cam": "CAM-03",
                      "conf": 0.90, "event_id": e})
        sv, bv = req(p, "POST", "/verify", L.PAT,
                     {"hit_id": first_hit, "decision": "confirm",
                      "case": "2027-1014"})
        c = L.db(A)
        outcome_first = c.execute("SELECT COUNT(*) FROM outcomes WHERE "
                                  "hit_id=?", (first_hit,)).fetchone()[0]
        c.close()
        finding("R5-03c", "a same-plate redelivery at higher confidence "
                "deletes the PENDING hit (and its outcome record) and "
                "re-creates it under a new id: the officer verifying the "
                "hit id they were alerted with gets 409",
                c2.get("hit_id") not in (None, first_hit) and sv == 409
                and outcome_first == 0,
                {"first": c1, "redelivery": c2,
                 "verify_original_id": (sv, bv),
                 "outcome_rows_for_original": outcome_first})
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        A.stop()


if __name__ == "__main__":
    main()
    L.summary()
