#!/usr/bin/env python3
"""Sentinel audit — NOCTUA 1.2 (S1, S16). A standalone audit of a
Janus deployment, usable against a deployment you do not operate —
which is the entire point of the Compact: a member agency audits
another member with this tool and nothing else.

Two input modes:
  URL mode:  --url https://partner.example --user auditor.x --key KEY
             (an auditor-role account on the target Janus; /health
             requires auth since 1.2, and the same account serves)
  DB mode:   --db /path/janus.db --checkpoints /path/checkpoints.jsonl
             (for auditing your own server, or a furnished copy)

1.2 truth rules (S16):
  * DB mode opens the database READ-ONLY (sqlite URI mode=ro) and
    verifies with sentinel.verify_detached — it NEVER instantiates
    Chain: 1.1's audit tool created tables and took the write path
    on the very database it was attesting.
  * URL mode: a checkpoint claiming MORE entries than the chain has
    is a FAILURE (truncation) — 1.1 skipped the anchor check in
    exactly that case. /health degraded flags are findings, named.
  * Checkpoint signatures are Ed25519 (S7) and are verified with
    the ASSESSED system's public key — a parameter (--pubkey), in
    DB mode defaulting to the signing_pub.pem beside the database —
    never with the auditor's own keys, and never with the audit
    key, which signs nothing and never leaves its box.
  * Retention is checked BY THE REGISTRY (S1): the oldest item in
    every registered store is compared to its class, in both modes
    (URL mode reads Janus's own registry computation from /health).

The JSON report is Ed25519-signed when SENTINEL_AUDIT_SIGNING_KEY
names the AUDITOR's private key file; otherwise it is unsigned and
says so. Exit codes: 0 clean, 1 warnings, 2 failures.
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

JOB_MAX_AGE_H = {"retention": 26, "checkpoint": 26,
                 "hotlist_sync": 26, "backup": 30, "witness": 26}

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


def verify_checkpoint_sigs(cps, pub_pem):
    """(newest_by_entries, bad_count) over Ed25519 checkpoint sigs."""
    newest, bad = None, 0
    for cp in cps:
        if cp.get("sig_alg") == "ed25519":
            if not pub_pem or not sentinel.verify_bytes(
                    pub_pem, sentinel.checkpoint_signed_bytes(cp),
                    cp.get("sig", "")):
                bad += 1
        else:
            bad += 1  # an unsigned/legacy checkpoint is not verified
        if newest is None or cp.get("entries", -1) > newest.get(
                "entries", -1):
            newest = cp
    return newest, bad


def registry_checks_db(db_path, retention_days, hold_days):
    """S1: the oldest item in every registered store vs its class,
    over a read-only connection."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for e in sentinel.PLATE_DATA_STORES:
            days = sentinel.class_days(e, retention_days, hold_days)
            name = "registry: " + e["store"]
            if e["kind"] == "table":
                if e["table"] not in tables:
                    check(name, "fail",
                          "registered table %s is MISSING" % e["table"])
                    continue
                if days is None:
                    check(name, "ok",
                          "class %s — lifetime-governed, no age check"
                          % e["class"])
                    continue
                ts_col = e.get("ts_col") or e.get("day_col")
                where = "1=1"
                if e["action"] in ("null_columns", "scrub_fragment"):
                    where = f"{e['column']} IS NOT NULL"
                if e["class"] == "hotlist":
                    where = "active=0"
                row = db.execute(
                    f"SELECT MIN({ts_col}) FROM {e['table']} "
                    f"WHERE {where}").fetchone()
                if not row or not row[0]:
                    check(name, "ok", "store empty")
                    continue
                oldest = str(row[0])
                if e.get("day_col"):
                    age_d = (now().date() - datetime.strptime(
                        oldest, "%Y-%m-%d").date()).days
                else:
                    age_d = (now() - parse_ts(oldest)).total_seconds() \
                        / 86400
                if age_d <= days + 1:  # 1 day of run-cadence grace
                    check(name, "ok",
                          "oldest item %.1f days old (class %d)"
                          % (age_d, days))
                else:
                    check(name, "fail",
                          "oldest item %.1f days old exceeds its "
                          "class (%d days)" % (age_d, days))
            elif e["kind"] == "folder" and e["folder"] == "evidence":
                # Evidence: a bundle on disk whose row says destroyed,
                # or past destroy_by, is a breach.
                n = db.execute(
                    "SELECT COUNT(*) FROM evidence WHERE bundle IS NOT "
                    "NULL AND (destroyed_ts IS NOT NULL OR "
                    "(destroy_by IS NOT NULL AND destroy_by < ?))",
                    (sentinel.now_iso(),)).fetchone()[0] \
                    if "evidence" in tables else 0
                check(name, "fail" if n else "ok",
                      "%d bundle(s) destroyed-on-paper or past "
                      "destroy_by still on record" % n if n else
                      "no overdue bundles")
            elif e["kind"] in ("folder", "glob"):
                check(name, "warn",
                      "filesystem store — oldest-item age is checked "
                      "by Janus /health (retention_breach)")
            else:
                check(name, "ok",
                      "asserted %s — plate-free/external by "
                      "construction" % e["class"])
    finally:
        db.close()


def audit_url(a):
    health = http(a.url, "/health", a.user, a.key)
    check("health reachable", "ok",
          "version %s, %s chain entries" % (health.get("version"),
                                            health.get("chain_entries")))
    # S16: degraded flags are findings, named — not a single ok bit.
    deg = health.get("degraded", {})
    if health.get("chain_ok"):
        check("chain integrity (self-report)", "ok",
              "Janus verify() passes")
    else:
        check("chain integrity (self-report)", "fail",
              "Janus verify() FAILS on its own chain")
    if deg.get("anchor_mismatch"):
        check("anchor consistency", "fail",
              "/health reports anchor_mismatch — the chain disagrees "
              "with a published checkpoint")
    if deg.get("jobs_overdue"):
        check("heartbeat freshness", "fail",
              "overdue/failing jobs: " + ", ".join(
                  deg["jobs_overdue"]))
    else:
        check("heartbeat freshness", "ok",
              "all monitored jobs fresh and ok")
    cfg = deg.get("config", {})
    if cfg.get("fail_closed"):
        check("config freshness", "fail",
              "configuration stale >24h — the data surface is closed")
    breach = deg.get("retention_breach") or []
    check("retention registry (self-report)", "fail" if breach else "ok",
          ("breached stores: " + ", ".join(breach)) if breach
          else "no registered store past its class")
    if deg.get("evidence_destroy_overdue"):
        check("evidence destruction", "fail",
              "%d released bundle(s) past destroy_by" %
              deg["evidence_destroy_overdue"])
    if health.get("registry_version") != sentinel.REGISTRY_VERSION:
        check("registry version", "warn",
              "assessed system reports registry %s; this tool knows %s"
              % (health.get("registry_version"),
                 sentinel.REGISTRY_VERSION))
    root = http(a.url, "/audit/root", a.user, a.key)
    verify = http(a.url, "/audit/verify", a.user, a.key)
    check("chain integrity (independent)", "ok" if verify.get("ok")
          else "fail", "/audit/verify via auditor account: %s"
          % verify.get("ok"))
    try:
        cp = http(a.url, "/compact/checkpoint", a.user, a.key)[
            "checkpoint"]
        pub_pem = None
        if a.pubkey:
            pub_pem = open(a.pubkey).read()
        elif cp.get("pubkey"):
            pub_pem = cp["pubkey"]
            if a.pubkey_fingerprint and \
                    sentinel.pubkey_fingerprint(pub_pem) \
                    != a.pubkey_fingerprint:
                check("checkpoint public key", "fail",
                      "the checkpoint's public key does not match the "
                      "registered fingerprint")
                pub_pem = None
        _n, bad = verify_checkpoint_sigs([cp], pub_pem)
        check("checkpoint signature", "fail" if bad else "ok",
              "newest checkpoint Ed25519 signature %s"
              % ("does not verify" if bad else "verifies"))
        if cp["entries"] > root["entries"]:
            # S16: this is TRUNCATION, the case 1.1 silently skipped.
            check("anchor consistency", "fail",
                  "checkpoint claims %d entries but the chain has %d "
                  "— the chain was truncated after the checkpoint was "
                  "published" % (cp["entries"], root["entries"]))
        else:
            page = http(a.url, "/audit/range?from_seq=%d&to_seq=%d"
                        % (cp["entries"], cp["entries"]),
                        a.user, a.key)
            entries = page.get("entries", [])
            if entries and entries[0]["hash"] == cp["root"]:
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
    # S16: read-only, verify_detached — no Chain, no writes, ever.
    result = sentinel.verify_detached(a.db)
    check("chain integrity + seq continuity",
          "ok" if result["ok"] else "fail",
          "verify_detached over the read-only database: %s" % result)
    db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    root_row = db.execute(
        "SELECT seq, hash FROM audit ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    n_entries, root = (root_row[0], root_row[1]) if root_row \
        else (0, "GENESIS")
    pub_pem = None
    if a.pubkey:
        pub_pem = open(a.pubkey).read()
    else:
        _priv, pub = sentinel.signing_paths(a.db)
        if os.path.exists(pub):
            pub_pem = open(pub).read()
    newest = None
    cp_path = a.checkpoints or (a.db + ".checkpoints.jsonl")
    if os.path.exists(cp_path):
        cps = [json.loads(line) for line in open(cp_path)
               if line.strip()]
        newest, bad = verify_checkpoint_sigs(cps, pub_pem)
        if not pub_pem:
            check("checkpoint signatures", "warn",
                  "no public key available — signatures not verified")
        elif bad:
            check("checkpoint signatures", "fail",
                  "%d checkpoint signature(s) do not verify" % bad)
        else:
            check("checkpoint signatures", "ok",
                  "all checkpoint Ed25519 signatures verify")
    if newest:
        if newest["entries"] > n_entries:
            check("anchor consistency", "fail",
                  "checkpoint claims %d entries but the chain has %d "
                  "— truncation" % (newest["entries"], n_entries))
        else:
            at = db.execute("SELECT hash FROM audit WHERE seq=?",
                            (newest["entries"],)).fetchone()
            if at and at[0] == newest["root"]:
                check("anchor consistency", "ok",
                      "chain hash at entry %d equals the newest "
                      "checkpoint root" % newest["entries"])
            else:
                check("anchor consistency", "fail",
                      "chain hash at entry %d does NOT equal the "
                      "newest checkpoint root" % newest["entries"])
    registry_checks_db(a.db, a.retention_days, a.hold_days)
    try:
        rows = db.execute("SELECT job, ok, ts FROM heartbeats").fetchall()
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
    ap.add_argument("--pubkey", help="the ASSESSED system's Ed25519 "
                                     "public key PEM file (S7/S16)")
    ap.add_argument("--pubkey-fingerprint",
                    help="registered fingerprint to cross-check the "
                         "checkpoint's embedded public key (URL mode)")
    ap.add_argument("--retention-days", type=int,
                    default=int(os.environ.get("RETENTION_DAYS", "14")))
    ap.add_argument("--hold-days", type=int,
                    default=int(os.environ.get("HOLD_DAYS", "30")))
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
    report = {"tool": "sentinel_audit", "version": "1.2",
              "ts": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": mode,
              "checks": CHECKS,
              "summary": {"fail": fails, "warn": warns,
                          "ok": len(CHECKS) - fails - warns}}
    sign_priv = os.environ.get("SENTINEL_AUDIT_SIGNING_KEY")
    if sign_priv and os.path.exists(sign_priv):
        report["sig"] = sentinel.sign_bytes(
            sign_priv, sentinel.canonical_bytes(report))
        report["sig_alg"] = "ed25519"
    else:
        report["sig"] = None
        report["signing_note"] = (
            "unsigned — set SENTINEL_AUDIT_SIGNING_KEY to the "
            "auditor's Ed25519 private key to sign reports (S7)")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 2 if fails else (1 if warns else 0)


if __name__ == "__main__":
    sys.exit(main())
