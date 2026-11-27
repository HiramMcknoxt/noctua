#!/usr/bin/env python3
# VESPER · the evening watch
"""Sentinel audit — NOCTUA 1.2.4 (S1, S16; P8/P10/P11; Q-audit; R8 shared verification).

1.2.2 changes:
  * URL MODE RECOMPUTES (round 5, Vesper F5 / Claude R5-14): the
    headline chain check no longer reports the target's own
    /audit/verify answer as "independent" — this tool now pages
    /audit/range itself and recomputes every hash, exactly as
    compact.py does. The target's answer is reported, labeled a
    self-report. And a target with NO published checkpoint FAILS:
    1.2.1 warned and passed it, but a checkpoint is the outside
    anchor the whole design stands on.
  * DB MODE KEY HONESTY: when the signing public key is taken
    from beside the audited database (the default), the report
    WARNS that the key came with the evidence — pin it with
    --pubkey for an independent audit. A standalone
audit of a Janus deployment, usable against a deployment you do not
operate — which is the entire point of the Compact: a member agency
audits another member with this tool and nothing else.

1.2.1 changes:
  * REGISTRY PARITY (P10): the registry checks are
    sentinel.registry_breaches — the ONE implementation, shared with
    Janus /health and mirroring retention.py's purge semantics.
    1.2's private copy failed every legitimate hold, excused
    orphaned evidence bundles, and warned where it should have
    failed; two checkers disagreeing about the same database is a
    finding in itself, and now there is one checker.
  * EVERY CHECKPOINT ANCHORS (P11/A9): DB mode recomputes the root
    at EVERY checkpoint's entry count. 1.2 anchored only the newest
    — a rewrite of old history that kept the newest checkpoint
    intact passed this tool while Janus's own startup check caught
    it.
  * KEY PINNING (P8/A26): URL mode refuses to run without --pubkey
    or --pubkey-fingerprint — the assessed system's key is pinned
    out-of-band, never taken from the checkpoint being verified.
    And URL mode no longer dies on /health: a chain_auditor
    credential (what partners are actually issued) cannot read
    /health, so the health-derived checks degrade to a named
    warning and the chain checks — the ones that matter — proceed
    on the endpoints the credential CAN read.

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
import urllib.error
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


# 1.2.5 (T1): the chain_auditor is a TOTP-capable HUMAN role —
# on a provisioned install this tool owes a second factor like
# everyone else. Set NOCTUA_TOTP_SECRET (the account's base32
# secret) in the audit job's environment; each request carries
# the current step's code.
TOTP_SECRET = os.environ.get("NOCTUA_TOTP_SECRET", "")


def http(base, path, user=None, key=None):
    def _once():
        req = urllib.request.Request(base.rstrip("/") + path)
        if user:
            req.add_header("X-Noctua-User", user)
            req.add_header("X-Noctua-Key", key or "")
            if TOTP_SECRET:
                req.add_header("X-Noctua-TOTP", sentinel.totp_code(
                    TOTP_SECRET, sentinel.totp_counter_now()))
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    try:
        return _once()
    except urllib.error.HTTPError as e:
        if e.code == 401 and TOTP_SECRET:
            # Counters are strictly increasing: an earlier request
            # in this run consumed this step's code. Wait for the
            # next step and retry ONCE with its code.
            import time as _time
            _time.sleep(30 - (int(_time.time()) % 30) + 1)
            return _once()
        raise


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
    """S1 + P10: the registry verdict is sentinel.registry_breaches
    — the same function Janus /health runs, with retention.py's
    purge semantics. One check row per registered store: fail when
    the shared implementation names it breached, ok otherwise
    (filesystem stores included — the shared implementation checks
    them on disk, so an orphaned evidence bundle or an expired
    backup set FAILS here, where 1.2 only warned)."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        breaches = sentinel.registry_breaches(
            db, retention_days, hold_days, db_path=db_path)
    finally:
        db.close()
    for e in sentinel.PLATE_DATA_STORES:
        name = "registry: " + e["store"]
        if e["store"] in breaches:
            check(name, "fail", breaches[e["store"]])
        elif e["kind"] == "asserted":
            check(name, "ok",
                  "asserted %s — plate-free/external by "
                  "construction" % e["class"])
        elif e["kind"] == "file":
            check(name, "ok",
                  "declared file store — class follows the DB")
        else:
            check(name, "ok",
                  "within its class (%s) per the shared registry "
                  "check" % e["class"])


def audit_url(a):
    # P8/A26: /health requires supervisor/auditor/jobs — the
    # chain_auditor credential partners are issued cannot read it,
    # and 1.2's URL mode died on that refusal before checking
    # anything. Health-derived findings are valuable when readable
    # and explicitly WAIVED when not; the chain checks below run on
    # endpoints every auditor credential can read.
    health = None
    try:
        health = http(a.url, "/health", a.user, a.key)
    except urllib.error.HTTPError as exc:
        if exc.code not in (401, 403):
            raise
        check("health detail", "warn",
              "/health is not readable with this credential (HTTP "
              "%d) — health-derived checks waived; the independent "
              "chain checks below are the audit" % exc.code)
    if health is not None:
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
    check("chain integrity (self-report)", "ok" if verify.get("ok")
          else "fail", "the target's own /audit/verify answer: %s "
          "— a self-report, weighed as one" % verify.get("ok"))
    # 1.2.2: the INDEPENDENT check — page the chain and recompute
    # every hash locally (the compact.py standard). 1.2.3 (R8):
    # the recompute goes through sentinel.verify_chain_rows — the
    # ONE verification implementation, v1 kind/ts cross-check
    # included. This loop's private copy recomputed hashes and
    # linkage but never cross-checked a v1 entry's columns against
    # its payload, so a relabeled v1 chain passed BOTH 'independent'
    # tools (round 6, Gemini F7) — and a tool that calls itself
    # independent while reimplementing the check is how that
    # happens (round 5, Vesper F5).
    try:
        total = int(root.get("entries", 0))
        prev, seq, rok, rdetail = "GENESIS", 0, True, ""
        while seq < total:
            chunk_end = min(seq + 1000, total)
            page = http(a.url, "/audit/range?from_seq=%d&to_seq=%d"
                        % (seq + 1, chunk_end), a.user, a.key)
            entries = page.get("entries", [])
            if not entries:
                rok, rdetail = False, "range page empty at %d" % seq
                break
            res = sentinel.verify_chain_rows(
                entries, start_seq=seq, start_prev=prev)
            if not res.get("ok"):
                rok, rdetail = False, "verify failed at seq %s: %s" % (
                    res.get("broken_at"), res.get("reason"))
                break
            prev, seq = entries[-1]["hash"], entries[-1]["seq"]
        if rok and prev != root.get("root"):
            rok, rdetail = False, "recomputed root != /audit/root"
        check("chain integrity (independent recompute)",
              "ok" if rok else "fail",
              rdetail or "recomputed %d entries to the live root"
              % total)
    except Exception as exc:
        check("chain integrity (independent recompute)", "fail",
              "could not page the chain: %s" % exc)
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
        elif cp["entries"] == 0:
            # 1.2.3 (Gemini M11): a zero-entry checkpoint anchors at
            # GENESIS — 1.2.2 paged for entry 0, got nothing, and
            # reported a healthy fresh install as inconsistent.
            check("anchor consistency",
                  "ok" if cp["root"] == "GENESIS" else "fail",
                  "zero-entry checkpoint root is %s"
                  % ("GENESIS, as an empty chain requires"
                     if cp["root"] == "GENESIS"
                     else "not GENESIS — an empty chain cannot "
                          "have another root"))
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
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # 1.2.2: no checkpoint is a FAILURE, not a warning —
            # the checkpoint is the outside anchor; a system that
            # has never published one has nothing anchoring it.
            check("checkpoint read", "fail",
                  "the target has published NO checkpoint — there "
                  "is no outside anchor for its chain")
        else:
            check("checkpoint read", "warn",
                  "could not read the published checkpoint: HTTP %d"
                  % exc.code)
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
            check("checkpoint public key", "warn",
                  "the signing public key was taken from beside "
                  "the audited database — it came WITH the evidence; "
                  "pin it with --pubkey for an independent audit")
    if pub_pem and a.pubkey_fingerprint and \
            sentinel.pubkey_fingerprint(pub_pem) \
            != a.pubkey_fingerprint:
        check("checkpoint public key", "fail",
              "the public key in use does not match "
              "--pubkey-fingerprint")
        pub_pem = None
    cps = []
    cp_path = a.checkpoints or (a.db + ".checkpoints.jsonl")
    if os.path.exists(cp_path):
        cps = [json.loads(line) for line in open(cp_path)
               if line.strip()]
        _newest, bad = verify_checkpoint_sigs(cps, pub_pem)
        if not pub_pem:
            check("checkpoint signatures", "warn",
                  "no public key available — signatures not verified")
        elif bad:
            check("checkpoint signatures", "fail",
                  "%d checkpoint signature(s) do not verify" % bad)
        else:
            check("checkpoint signatures", "ok",
                  "all checkpoint Ed25519 signatures verify")
    if cps:
        # P11/A9: anchor against EVERY checkpoint — recompute the
        # root at each checkpoint's entry count. 1.2 anchored only
        # the newest, so a rewrite of OLD history (recomputed
        # forward, newest checkpoint re-signed or left consistent)
        # passed here while Janus's own startup check caught it.
        bad_anchors = []
        for cp in cps:
            n = cp.get("entries")
            if not isinstance(n, int):
                bad_anchors.append("a checkpoint with no entry count")
                continue
            if n > n_entries:
                bad_anchors.append(
                    "checkpoint at %d entries exceeds the chain's %d "
                    "— truncation" % (n, n_entries))
                continue
            if n == 0:
                if cp.get("root") != "GENESIS":
                    bad_anchors.append("checkpoint at 0 entries has "
                                       "a non-GENESIS root")
                continue
            at = db.execute("SELECT hash FROM audit WHERE seq=?",
                            (n,)).fetchone()
            if not at or at[0] != cp.get("root"):
                bad_anchors.append(
                    "chain hash at entry %d does not equal the "
                    "checkpoint root published for it" % n)
        if bad_anchors:
            check("anchor consistency", "fail",
                  "; ".join(bad_anchors[:3])
                  + (" (+%d more)" % (len(bad_anchors) - 3)
                     if len(bad_anchors) > 3 else ""))
        else:
            check("anchor consistency", "ok",
                  "chain hash equals the published root at EVERY "
                  "one of %d checkpoint(s)" % len(cps))
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
        # P8: URL mode verifies a signature, so the assessed
        # system's key must be PINNED — without a pin the only key
        # on offer is the one embedded in the checkpoint itself.
        if not a.pubkey and not a.pubkey_fingerprint:
            ap.error("URL mode requires --pubkey or "
                     "--pubkey-fingerprint: the assessed system's "
                     "key is pinned out-of-band, never taken from "
                     "the checkpoint being verified (P8)")
        audit_url(a)
        mode = "url"
    elif a.db:
        audit_db(a)
        mode = "db"
    else:
        ap.error("give --url (with --user/--key) or --db")
    fails = sum(1 for c in CHECKS if c["status"] == "fail")
    warns = sum(1 for c in CHECKS if c["status"] == "warn")
    report = {"tool": "sentinel_audit", "version": "1.2.8",
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
