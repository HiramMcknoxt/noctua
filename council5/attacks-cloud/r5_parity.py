"""R5-05: P10 says registry_breaches 'mirrors retention.py's purge
semantics exactly'. It does not. The purge measures hit age in WHOLE
days (retention.py:161-170: `.days` floors, then `> days`), the check
measures it to the second (sentinel.py:525-530: `ts < now - days`).
case_searches is purged by DATE (`day < cutoff[:10]`, retention.py:134)
but checked against a full TIMESTAMP (a bare 'YYYY-MM-DD' sorts below
'YYYY-MM-DDTHH:MM:SSZ', sentinel.py:575-578).

Consequences, all on a healthy deployment with a daily retention run:
  * an unprotected hit 30.5 days old is a 'breach' that the purge
    leaves alone — with >=1 alert a day there is always one, so /health
    is permanently degraded, alert_check pages hourly, and
    sentinel_audit --db FAILS;
  * same for any case_searches row on the cutoff date;
  * a protected hit 150.5 days old survives the purge: the 150-day
    statutory cap is enforced as 'older than 151 whole days'."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib5 as L  # noqa: E402
from lib5 import req, finding  # noqa: E402


def main():
    A = L.instance("r5-par", 19240)
    A.start()
    try:
        p = A.port
        s, b = req(p, "POST", "/hotlist", L.DET,
                   {"plate": "PAR100", "state": "AR",
                    "category": "stolen_vehicle", "case": "2027-1014"})
        assert s == 201, b
        h1 = req(p, "POST", "/reads", L.ING,
                 {"plate": "PAR100", "state": "AR", "cam": "CAM-06"}
                 )[1]["hit_id"]
        h2 = req(p, "POST", "/reads", L.ING,
                 {"plate": "PAR100", "state": "AR", "cam": "CAM-07"}
                 )[1]["hit_id"]
        # h2 is under a valid, freshly placed hold (review_by default)
        s, b = req(p, "POST", "/holds", L.DET,
                   {"scope": "hit", "ref": str(h2),
                    "reason": "pending court date"})
        assert s == 201, b
        s, b = req(p, "GET", "/search?plate=PAR100&case=2027-1014"
                   "&justification=r5&tier=2", L.DET)
        assert s == 200, b
        c = L.db(A)
        c.execute("UPDATE hits SET ts=? WHERE id=?",
                  (L.ago(days=30, hours=12), h1))
        c.execute("UPDATE hits SET ts=? WHERE id=?",
                  (L.ago(days=150, hours=12), h2))
        cut_day = L.ago(days=14)[:10]
        c.execute("UPDATE case_searches SET day=?", (cut_day,))
        c.commit()
        c.close()
        env = L.script_env(A)
        r1 = L.run_script("retention.py", env)
        r2 = L.run_script("retention.py", env)   # run it again
        c = L.db(A)
        left = [r[0] for r in c.execute("SELECT id FROM hits ORDER BY id")]
        cs_left = c.execute("SELECT day FROM case_searches").fetchall()
        c.close()
        L.heartbeat_all(p)
        h = L.T.health(p)
        alert = L.run_script("alert_check.py", env)
        aud = L.run_script("sentinel_audit.py", dict(A.env),
                           ["--db", A.db])
        rep = json.loads(aud.stdout)
        fails = [x["name"] for x in rep["checks"] if x["status"] == "fail"]
    finally:
        A.stop()
    finding("R5-05a", "with retention just run (twice), an unprotected "
            "30.5-day-old hit and a cutoff-day case_searches row are left "
            "by the purge but named as breaches by /health, alert_check "
            "and sentinel_audit --db — the 'one implementation' disagrees "
            "with the purger, so a healthy busy deployment is "
            "permanently red",
            h1 in left and bool(cs_left)
            and "hits.read_plate" in h["degraded"]["retention_breach"]
            and "case_searches.frag" in
            h["degraded"]["retention_breach"]
            and "RETENTION BREACH" in alert.stdout
            and "registry: hits.read_plate" in fails
            and "registry: case_searches.frag" in fails,
            {"retention_runs": [r1.stdout.strip()[-120:],
                                r2.stdout.strip()[-120:]],
             "hits_left": left, "case_searches_left": cs_left,
             "health_ok": h["ok"],
             "retention_breach": h["degraded"]["retention_breach"],
             "alert_check": alert.stdout.strip()[-260:],
             "sentinel_audit_fails": fails})
    finding("R5-05b", "a held hit 150.5 days old survives two retention "
            "runs: the statutory 150-day cap is enforced as 'more than "
            "150 WHOLE days' (up to ~2 days late with a daily run)",
            h2 in left, {"hit_ages_days": {h1: 30.5, h2: 150.5},
                         "hits_left": left})


if __name__ == "__main__":
    main()
    L.summary()
