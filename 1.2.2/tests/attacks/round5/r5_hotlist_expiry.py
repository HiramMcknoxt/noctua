"""R5-02: POST /hotlist stores `expires` as whatever string arrives
(janus.py:2021) and expiry is a STRING comparison against an ISO
timestamp (janus.py:1804 at ingest; hotlist_sync.py:88 nightly). P2
special-cased '' -> NULL; it did not validate the field. A US-format
date — the way an American officer writes one — sorts before every
ISO timestamp ('1' < '2'), so the entry is 'expired' at the first
sighting: the stolen car drives past the camera, the entry is
deactivated, and nobody is alerted. The API answered 201 'added'."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def main():
    A = L.instance("r5-exp", 19210)
    A.start()
    try:
        p = A.port
        # The entry a records clerk types for a car stolen today,
        # "good through" the end of next year, US style.
        s1, b1 = req(p, "POST", "/hotlist", L.DET,
                     {"plate": "STL501", "state": "AR",
                      "category": "stolen_vehicle", "case": "2027-1014",
                      "expires": "12/31/2027"})
        # Control: the same entry with an ISO date.
        s2, b2 = req(p, "POST", "/hotlist", L.DET,
                     {"plate": "STL502", "state": "AR",
                      "category": "stolen_vehicle", "case": "2027-1014",
                      "expires": "2027-12-31"})
        # A third natural form: a date already PAST, written in words,
        # never expires at all ('D' sorts after every digit).
        s3, b3 = req(p, "POST", "/hotlist", L.DET,
                     {"plate": "STL503", "state": "AR",
                      "category": "stolen_vehicle", "case": "2027-1014",
                      "expires": "Dec 31 2025"})
        # A feed that sends Unix epoch seconds (2027-01-01T00:00:00Z).
        s5, b5 = req(p, "POST", "/hotlist", L.DET,
                     {"plate": "STL505", "state": "AR",
                      "category": "stolen_vehicle", "case": "2027-1014",
                      "expires": 1798761600})
        r5 = req(p, "POST", "/reads", L.ING,
                 {"plate": "STL505", "state": "AR", "cam": "CAM-04"})[1]
        r1 = req(p, "POST", "/reads", L.ING,
                 {"plate": "STL501", "state": "AR", "cam": "CAM-04"})[1]
        r2 = req(p, "POST", "/reads", L.ING,
                 {"plate": "STL502", "state": "AR", "cam": "CAM-04"})[1]
        r3 = req(p, "POST", "/reads", L.ING,
                 {"plate": "STL503", "state": "AR", "cam": "CAM-04"})[1]
        c = L.db(A)
        rows = c.execute("SELECT plate, expires_ts, active FROM "
                         "hotlist_members ORDER BY plate").fetchall()
        c.close()
        kinds, entries = L.T.audit_kinds(p)
        expired = [e["fields"] for e in entries
                   if e["kind"] == "HOTLIST_EXPIRED"]
        # And the nightly job: every US-format entry dies on schedule.
        s4, b4 = req(p, "POST", "/hotlist", L.DET,
                     {"plate": "STL504", "state": "AR",
                      "category": "stolen_vehicle", "case": "2027-1014",
                      "expires": "06/30/2027"})
        r = L.run_script("hotlist_sync.py", L.script_env(A))
        c = L.db(A)
        after_sync = c.execute("SELECT plate, active FROM "
                               "hotlist_members WHERE plate='STL504'"
                               ).fetchall()
        past_words_after_sync = c.execute(
            "SELECT plate, active FROM hotlist_members WHERE "
            "plate='STL503'").fetchall()
        c.close()
    finally:
        A.stop()
    finding("R5-02", "a hot-list entry whose expiry is typed as a US "
            "date (12/31/2027) is accepted 201 and then treated as "
            "already expired (so is a Unix epoch value): the stolen "
            "car's first read stores silently, the entry deactivates, no ALERT; hotlist_sync "
            "kills such entries nightly. A PAST date in words "
            "('Dec 31 2025') never expires: it still alerts and survives "
            "the sync.",
            s1 == 201 and r1.get("result") == "stored"
            and s5 == 201 and r5.get("result") == "stored"
            and r2.get("result") == "ALERT"
            and after_sync == [("STL504", 0)]
            and r3.get("result") == "ALERT"
            and past_words_after_sync == [("STL503", 1)],
            {"add_us_date": (s1, b1), "read_us_date": r1,
             "read_iso_date": r2, "add_past_date_in_words": s3,
             "read_past_date_in_words": r3,
             "past_date_in_words_after_sync": past_words_after_sync,
             "add_epoch": s5, "read_epoch": r5,
             "rows": rows, "HOTLIST_EXPIRED": expired,
             "sync": r.stdout.strip(), "STL504_after_sync": after_sync})


if __name__ == "__main__":
    main()
    L.summary()
