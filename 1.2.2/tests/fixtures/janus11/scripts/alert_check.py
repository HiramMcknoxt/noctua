#!/usr/bin/env python3
"""NOCTUA dead-man check — run every hour (cron / systemd timer).

Reads GET /health from Janus. Exit 0 = healthy. Exit 1 = something
needs a human, and the reason is printed:

  * Janus unreachable (the front door itself is down), or
  * a required job is overdue — retention or checkpoint has not
    heartbeated within 26 hours, or never has.

The mechanism for reaching a human is deliberately NOT built in beyond
one optional webhook: no vendor is assumed anywhere in NOCTUA. Wire the
exit code to whatever the city already has:

    # cron, mailing the output on failure (cron mails non-empty output
    # when MAILTO is set — the classic, vendor-free route):
    MAILTO=duty-officer@example.gov
    17 * * * *  /srv/noctua/scripts/alert_check.py

    # or a systemd service with OnFailure=, or set
    # NOCTUA_ALERT_WEBHOOK=https://… to also POST the alert JSON there.

Env: NOCTUA_JANUS_URL (default http://127.0.0.1:8080),
     NOCTUA_ALERT_WEBHOOK (optional).
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("NOCTUA_JANUS_URL", "http://127.0.0.1:8080")
WEBHOOK = os.environ.get("NOCTUA_ALERT_WEBHOOK")


def notify(alert):
    print(alert["message"])
    for job in alert.get("overdue_jobs", []):
        print(f"  overdue: {job}")
    if WEBHOOK:
        try:
            req = urllib.request.Request(
                WEBHOOK, data=json.dumps(alert).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
            print(f"alert posted to webhook {WEBHOOK}")
        except Exception as e:
            print(f"webhook post FAILED ({e}) — the alert above is the "
                  f"record; exit code is still 1")


def main():
    try:
        with urllib.request.urlopen(URL.rstrip("/") + "/health",
                                    timeout=10) as r:
            health = json.loads(r.read())
    except Exception as e:
        notify({"message": f"NOCTUA ALERT: Janus unreachable at {URL} "
                           f"({e}) — the front door is down",
                "overdue_jobs": []})
        return 1
    # 1.1 (item 24): /health's ok flag is authoritative — it is never
    # true while degraded. Alert on ok:false for ANY reason: a job
    # overdue or reporting failure, sink down, anchor mismatch, stale
    # config, silent cameras, or a missing audit key.
    if not health.get("ok", False):
        jobs = health.get("jobs", {})
        bad = [j for j, s in jobs.items()
               if s.get("overdue") or not s.get("ok")]
        reasons = []
        if bad:
            reasons.append("jobs not current/ok: " + ", ".join(
                f"{j} (last={jobs[j].get('last')}, "
                f"status={jobs[j].get('detail')})" for j in bad))
        if health.get("anchor_mismatch"):
            reasons.append("STARTUP ANCHOR MISMATCH — chain root does "
                           "not match the newest checkpoint")
        if health.get("config_stale"):
            reasons.append("config stale since "
                           + str(health.get("config_stale_since")))
        if health.get("sentinel_sink_ok") is False:
            reasons.append("sentinel sink failing (spooling)")
        if health.get("cameras_silent"):
            reasons.append("cameras silent >6h: "
                           + ", ".join(health["cameras_silent"]))
        if health.get("key_missing"):
            reasons.append("AUDIT KEY MISSING — Janus is locked")
        notify({"message": "NOCTUA ALERT: " + ("; ".join(reasons)
                                               or "health not ok"),
                "overdue_jobs": bad})
        return 1
    print(f"OK: janus healthy, jobs current "
          f"({', '.join(sorted(health.get('jobs', {})))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
