#!/usr/bin/env python3
"""Sentinel audit — NOCTUA 1.1 (item 21). A standalone, READ-ONLY
audit of a Janus deployment, usable against a deployment you do not
operate — which is the entire point of the Compact: a member agency
audits another member with this tool and nothing else.

Two input modes:
  URL mode:  --url https://partner.example --user auditor.x --key KEY
             (an auditor-role read-only account on the target Janus)
  DB mode:   --db /path/janus.db --checkpoints /path/checkpoints.jsonl
             (for auditing your own server, or a furnished copy)

Checks: chain integrity + seq continuity; checkpoint HMACs; anchor
consistency (the chain hash at the newest checkpoint's entry count
equals the checkpoint's root); retention compliance (oldest read age
vs policy; derived-data purge state — case_searches emptied and tier3
fragments scrubbed past 14 days); heartbeat freshness.

The JSON report is HMAC-signed with the AUDITOR'S OWN key
(env SENTINEL_AUDIT_KEY, else NOCTUA_AUDIT_KEY) so the audited agency
can verify the report came from the auditor who signed it.

Exit codes: 0 clean, 1 warnings, 2 failures.
"""
import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

JOB_MAX_AGE_H = {"retention": 26, "checkpoint": 26,
                 "hotlist_sync": 26, "backup": 30}
PURGE_DAYS = 14

CHECKS = []


def check(name, status, detail):
    CHECKS.append({"name": name, "status": status, "detail": detail})


def now():
    return datetime.now(timezone.utc)


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def http(base, path, user=None, key=None):
    req = urllib.request.Request(base.rstrip("/") + path)
    if user:
        req.add_header("X-Noctua-User", user)
        req.add_header("X-Noctua-Key", key or "")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def verify_checkpoints(lines, audit_key):
    """Returns (newest_checkpoint, bad_count)."""
    newest, bad = None, 0
    for line in lines:
        if not line.strip():
            continue
        cp = json.loads(line)
        if audit_key:
            canonical = json.dumps(
                {"date": cp["date"], "root": cp["root"],
                 "entries": cp["entries"]},
                sort_keys=True, separators=(",", ":"))
            expect = hmac.new(audit_key.encode(), canonical.encode(),
                              hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expect, cp.get("sig", "")):
                bad += 1
        newest = cp
    return newest, bad


def audit_url(a):
    health = http(a.url, "/health")
    check("health reachable", "ok",
          "version %s, %s chain entries" % (health.get("version"),
                                            health.get("chain_entries")))
    if health.get("key_missing"):
        check("audit key present", "fail",
              "Janus reports key_missing — it is running LOCKED")
    if health.get("chain_ok"):
        check("chain integrity (self-report)", "ok",
              "Janus verify() passes")
    else:
        check("chain integrity (self-report)", "fail",
              "Janus verify() FAILS on its own chain")
    if health.get("anchor_mismatch"):
        check("anchor consistency", "fail",
              "/health reports anchor_mismatch — the chain root does "
              "not match the newest checkpoint")
    jobs = health.get("jobs", {})
    stale = [j for j, s in jobs.items()
             if s.get("overdue") or not s.get("ok")]
    check("heartbeat freshness",
          "fail" if stale else "ok",
          ("stale/failing jobs: " + ", ".join(stale)) if stale
          else "all monitored jobs fresh and ok")
    age = health.get("retention_oldest_read_age_h")
    limit = a.retention_days * 24
    if age is None:
        check("retention compliance", "ok", "no reads on file")
    elif age <= limit + 26:
        check("retention compliance", "ok",
              "oldest read %.1fh old (policy %dh + 26h grace)"
              % (age, limit))
    else:
        check("retention compliance", "fail",
              "oldest read %.1fh old exceeds the %d-day policy"
              % (age, a.retention_days))
    check("derived-data purge state", "warn",
          "not visible through the API — audit in DB mode to verify "
          "case_searches purge and tier3 fragment scrubbing")
    # Independent chain checks with the auditor account.
    root = http(a.url, "/audit/root", a.user, a.key)
    verify = http(a.url, "/audit/verify", a.user, a.key)
    check("chain integrity (independent)", "ok" if verify.get("ok")
          else "fail", "/audit/verify via auditor account: %s"
          % verify.get("ok"))
    try:
        cp_wrap = http(a.url, "/compact/checkpoint", a.user, a.key)
        cp = cp_wrap["checkpoint"]
        audit_key = a.audit_key or os.environ.get("NOCTUA_AUDIT_KEY")
        _n, bad = verify_checkpoints([json.dumps(cp)], audit_key)
        if not audit_key:
            check("checkpoint HMAC", "warn",
                  "no audit key supplied — signature not verified")
        elif bad:
            check("checkpoint HMAC", "fail",
                  "newest checkpoint signature does not verify")
        else:
            check("checkpoint HMAC", "ok",
                  "newest checkpoint signature verifies")
        if cp["entries"] <= root["entries"]:
            entry = http(a.url, "/audit?seq=%d" % cp["entries"],
                         a.user, a.key)["entry"]
            if entry and entry["hash"] == cp["root"]:
                check("anchor consistency", "ok",
                      "chain hash at entry %d equals the published "
                      "checkpoint root" % cp["entries"])
            else:
                check("anchor consistency", "fail",
                      "chain hash at entry %d does NOT equal the "
                      "published checkpoint root" % cp["entries"])
    except Exception as exc:
        check("checkpoint read", "warn", "could not read the published "
              "checkpoint: %s" % exc)


def audit_db(a):
    import sentinel
    chain = sentinel.Chain(a.db)
    ok = chain.verify()["ok"]
    check("chain integrity + seq continuity", "ok" if ok else "fail",
          "verify() over %d entries" % chain.count())
    root, n = chain.root(), chain.count()
    db = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True)
    audit_key = a.audit_key or os.environ.get("NOCTUA_AUDIT_KEY")
    if not audit_key:
        kf = a.db + ".audit_key"
        if os.path.exists(kf):
            audit_key = open(kf).read().strip()
    newest = None
    if a.checkpoints and os.path.exists(a.checkpoints):
        with open(a.checkpoints) as f:
            lines = f.readlines()
        newest, bad = verify_checkpoints(lines, audit_key)
        if not audit_key:
            check("checkpoint HMACs", "warn",
                  "no audit key available — signatures not verified")
        elif bad:
            check("checkpoint HMACs", "fail",
                  "%d checkpoint signature(s) do not verify" % bad)
        else:
            check("checkpoint HMACs", "ok",
                  "all checkpoint signatures verify")
    if newest:
        at = chain.hash_at_seq(newest["entries"])
        if at == newest["root"]:
            check("anchor consistency", "ok",
                  "chain hash at entry %d equals the newest checkpoint "
                  "root" % newest["entries"])
        else:
            check("anchor consistency", "fail",
                  "chain hash at entry %d does NOT equal the newest "
                  "checkpoint root" % newest["entries"])
    row = db.execute("SELECT MIN(ts) FROM reads").fetchone()
    if not row or not row[0]:
        check("retention compliance", "ok", "no reads on file")
    else:
        age_h = (now() - parse_ts(row[0])).total_seconds() / 3600
        limit = a.retention_days * 24
        check("retention compliance", "ok" if age_h <= limit + 26
              else "fail",
              "oldest read %.1fh old (policy %dh + 26h grace)"
              % (age_h, limit))
    cut = (now() - timedelta(days=PURGE_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    cut_day = (now() - timedelta(days=PURGE_DAYS)).strftime("%Y-%m-%d")
    old_cs = db.execute("SELECT COUNT(*) FROM case_searches WHERE "
                        "day < ?", (cut_day,)).fetchone()[0]
    old_frag = db.execute(
        "SELECT COUNT(*) FROM tier3_requests WHERE created_ts < ? "
        "AND plate_fragment NOT LIKE 'pref:%'", (cut,)).fetchone()[0]
    if old_cs == 0 and old_frag == 0:
        check("derived-data purge state", "ok",
              "no stale case_searches; all old tier3 fragments scrubbed")
    else:
        check("derived-data purge state", "fail",
              "%d case_searches rows and %d unscrubbed tier3 fragments "
              "older than %d days" % (old_cs, old_frag, PURGE_DAYS))
    try:
        rows = db.execute("SELECT job, ok, ts FROM heartbeats "
                          "ORDER BY ts").fetchall()
    except sqlite3.Error:
        rows = []
    seen = {r[0]: (r[1], r[2]) for r in rows}
    stale = []
    for job, max_h in JOB_MAX_AGE_H.items():
        if job not in seen:
            stale.append(job + " (never)")
        else:
            okf, ts = seen[job]
            age_h = (now() - parse_ts(ts)).total_seconds() / 3600
            if age_h > max_h or not okf:
                stale.append(job)
    check("heartbeat freshness", "fail" if stale else "ok",
          ("stale/failing jobs: " + ", ".join(stale)) if stale
          else "all monitored jobs fresh and ok")
    db.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", help="Janus base URL (URL mode)")
    ap.add_argument("--user", help="auditor username on the target")
    ap.add_argument("--key", help="auditor key on the target")
    ap.add_argument("--db", help="Janus DB path (DB mode)")
    ap.add_argument("--checkpoints", help="checkpoints .jsonl path")
    ap.add_argument("--audit-key", help="the deployment's audit key, "
                                        "for checkpoint HMAC checks")
    ap.add_argument("--retention-days", type=int,
                    default=int(os.environ.get("RETENTION_DAYS", "14")))
    a = ap.parse_args()
    if a.url:
        audit_url(a)
        mode = "url"
    elif a.db:
        audit_db(a)
        mode = "db"
    else:
        ap.error("give --url (with --user/--key) or --db")
    fails = sum(1 for c in CHECKS if c["status"] == "fail")
    warns = sum(1 for c in CHECKS if c["status"] == "warn")
    report = {"tool": "sentinel_audit", "version": "1.1",
              "ts": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": mode,
              "checks": CHECKS,
              "summary": {"fail": fails, "warn": warns,
                          "ok": len(CHECKS) - fails - warns}}
    sign_key = os.environ.get("SENTINEL_AUDIT_KEY") or os.environ.get(
        "NOCTUA_AUDIT_KEY")
    if sign_key:
        canonical = json.dumps(report, sort_keys=True,
                               separators=(",", ":"))
        report["sig"] = hmac.new(sign_key.encode(), canonical.encode(),
                                 hashlib.sha256).hexdigest()
    else:
        report["sig"] = None
        report["signing_note"] = ("unsigned — set SENTINEL_AUDIT_KEY "
                                  "to sign reports with the auditor's "
                                  "own key")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 2 if fails else (1 if warns else 0)


if __name__ == "__main__":
    sys.exit(main())
