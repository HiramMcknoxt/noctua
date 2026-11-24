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
    if health.get("degraded"):
        jobs = health.get("jobs", {})
        detail = "; ".join(
            f"{j}: last={jobs.get(j, {}).get('last')}, "
            f"status={jobs.get(j, {}).get('status', 'overdue')}"
            for j in health.get("overdue_jobs", []))
        notify({"message": "NOCTUA ALERT: dead-man switch tripped — "
                           + detail,
                "overdue_jobs": health.get("overdue_jobs", [])})
        return 1
    print(f"OK: janus healthy, jobs current "
          f"({', '.join(sorted(health.get('jobs', {})))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
