#!/usr/bin/env python3
# VESPER · the evening watch
"""NOCTUA dead-man check — run every hour (cron / systemd timer).

Reads GET /health from Janus. Exit 0 = healthy. Exit 1 = something
needs a human, and the reason is printed — NAMED (S5): a broken
audit chain and a retention breach are first-class alert reasons,
not footnotes in a degraded blob.

1.2: /health requires auth (supervisor/auditor/jobs). This check
authenticates as the jobs identity (NOCTUA_JOBS_USER /
NOCTUA_JOBS_KEY) and probes liveness FIRST via the unauthenticated
GET /ping, so "Janus is down" and "Janus is up but degraded" stay
distinguishable.

Reasons checked, each printed by name:
  * Janus unreachable (the /ping probe itself fails), or
  * chain_ok is false — the audit chain does not verify, or
  * retention_breach — a registered plate-data store holds data
    older than its retention class (the stores are named), or
  * a required job is overdue/failing (retention, checkpoint,
    hotlist_sync, backup, witness), or
  * startup anchor mismatch, stale-config fail-closed, sink down,
    or released evidence bundles past their destroy_by date.

The mechanism for reaching a human is deliberately NOT built in
beyond one optional webhook: no vendor is assumed anywhere in
NOCTUA. Wire the exit code to whatever the city already has:

    MAILTO=duty-officer@example.gov
    17 * * * *  /srv/noctua/scripts/alert_check.py

Env: NOCTUA_JANUS_URL (default http://127.0.0.1:8080),
     NOCTUA_JOBS_USER / NOCTUA_JOBS_KEY,
     NOCTUA_ALERT_WEBHOOK (optional).
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("NOCTUA_JANUS_URL", "http://127.0.0.1:8080")
WEBHOOK = os.environ.get("NOCTUA_ALERT_WEBHOOK")
JOBS_USER = os.environ.get("NOCTUA_JOBS_USER", "jobs.local")
JOBS_KEY = os.environ.get("NOCTUA_JOBS_KEY", "")


def notify(alert):
    print(alert["message"])
    for r in alert.get("reasons", []):
        print(f"  - {r}")
    if WEBHOOK:
        try:
            req = urllib.request.Request(
                WEBHOOK, data=json.dumps(alert).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
            print(f"alert posted to webhook {WEBHOOK}")
        except Exception as e:
            print(f"webhook post FAILED ({e}) — the alert above is "
                  f"the record; exit code is still 1")


def get(path, auth=False):
    req = urllib.request.Request(URL.rstrip("/") + path)
    if auth:
        req.add_header("X-Noctua-User", JOBS_USER)
        req.add_header("X-Noctua-Key", JOBS_KEY)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    try:
        get("/ping")
    except Exception as e:
        notify({"message": f"NOCTUA ALERT: Janus unreachable at {URL} "
                           f"({e}) — the front door is down",
                "reasons": ["liveness probe /ping failed"]})
        return 1
    if not JOBS_KEY:
        notify({"message": "NOCTUA ALERT: NOCTUA_JOBS_KEY not set — "
                           "/health requires auth in 1.2 and this "
                           "check cannot read it",
                "reasons": ["alert_check is unconfigured"]})
        return 1
    try:
        health = get("/health", auth=True)
    except Exception as e:
        notify({"message": f"NOCTUA ALERT: /health unreadable ({e})",
                "reasons": ["health endpoint failed"]})
        return 1
    if health.get("ok", False):
        print("OK: janus healthy, chain verifies, jobs current, "
              "no retention breach")
        return 0
    deg = health.get("degraded", {})
    reasons = []
    # S5: the two reasons round 3 demanded be checked EXPLICITLY.
    if deg.get("chain_ok") is False or health.get("chain_ok") is False:
        reasons.append("CHAIN VERIFICATION FAILED — the audit chain "
                       "does not verify (chain_ok=false)")
    if deg.get("retention_breach"):
        reasons.append("RETENTION BREACH — registered stores past "
                       "their class: " + ", ".join(
                           deg["retention_breach"]))
    if deg.get("jobs_overdue"):
        jobs = health.get("jobs", {})
        reasons.append("jobs overdue/failing: " + ", ".join(
            f"{j} (status={jobs.get(j, {}).get('status')}, "
            f"last={jobs.get(j, {}).get('last')})"
            for j in deg["jobs_overdue"]))
    if deg.get("anchor_mismatch"):
        reasons.append("STARTUP ANCHOR MISMATCH — the chain "
                       "disagrees with a published checkpoint")
    if deg.get("sink_up") is False:
        reasons.append("sentinel sink failing (spooling)")
    cfg = deg.get("config", {})
    if cfg.get("fail_closed"):
        # 1.2.4 (S9): name the ACTUAL closure. Since R12 the fence
        # is cause-aware — a stale case-list FEED closes only the
        # disclosure surface (ingest and safety writes continue),
        # while a stale config FILE closes the data surface. 1.2.3
        # printed FAIL-CLOSED for both (Gemini secondary).
        cr = cfg.get("closed_reasons") or {}
        if cr.get("files"):
            reasons.append("configuration file(s) stale >24h (%s) "
                           "— the data surface is FAIL-CLOSED"
                           % ", ".join(cr["files"]))
        elif cr.get("feed_stale"):
            reasons.append("case-list feed stale (%.1fh) — the "
                           "DISCLOSURE surface is closed; ingest "
                           "and safety writes continue"
                           % (cr.get("feed_age_hours") or 0))
        else:
            reasons.append("configuration stale >24h — the data "
                           "surface is FAIL-CLOSED")
    if deg.get("evidence_destroy_overdue"):
        reasons.append("%d released evidence bundle(s) past their "
                       "destroy_by date" % deg["evidence_destroy_overdue"])
    if deg.get("cameras_silent"):
        reasons.append("cameras silent: "
                       + ", ".join(deg["cameras_silent"]))
    # 1.2.2: three more named reasons (round 5, Claude R5-08 —
    # 1.2.1's /health REPORTED overdue holds but neither health's
    # ok bit nor this check counted them).
    if deg.get("overdue_holds"):
        reasons.append("%d hold(s) past their review date — a "
                       "prosecutor sign-off or case closure is "
                       "owed" % deg["overdue_holds"])
    if deg.get("cameras_silent_after_report"):
        reasons.append("cameras that reported and went silent: "
                       + ", ".join(
                           deg["cameras_silent_after_report"]))
    if deg.get("migration_unrepaired"):
        reasons.append("the upgrade migration left legacy rows it "
                       "could not repair: %s"
                       % deg["migration_unrepaired"])
    notify({"message": "NOCTUA ALERT: janus degraded",
            "reasons": reasons or ["health ok=false, no named reason "
                                    "— inspect /health manually"]})
    return 1


if __name__ == "__main__":
    sys.exit(main())
