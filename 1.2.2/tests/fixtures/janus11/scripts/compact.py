#!/usr/bin/env python3
"""Compact cross-audit runner — NOCTUA 1.1 (item 22).

Run by a member agency against a PARTNER agency. It performs our
half of the reciprocal audit:

  1. Fetch the partner's newest published checkpoint
     (GET /compact/checkpoint) and their chain root
     (GET /audit/root), using the read-only AUDITOR account the
     partner issued us. (The receipt in step 3 uses a second account:
     our agency's PARTNER-role identity in the partner's system —
     a receipt is an attestation by the agency, not by an auditor.)
  2. Verify their chain independently (GET /audit/verify) and check
     anchor consistency: the chain hash at the checkpoint's entry
     count (GET /audit?seq=N) equals the checkpoint's root.
  3. POST our checkpoint-receipt to the partner: we attest that we
     verified THE checkpoint identified by (root, entries).
  4. Record the outcome on OUR Janus (POST /compact/audit-result,
     jobs role) — Janus chains it as CROSS_AUDIT_OK / CROSS_AUDIT_FAIL.

The /share/query gate reads both halves: our CROSS_AUDIT_OK for the
partner (step 4) and the partner's receipt for us (their run of this
script, step 3 in the other direction). No cross-audit, no data — in
both directions, enforced by the software, not by trust.

For a deeper periodic audit, run scripts/sentinel_audit.py against
the partner (URL mode) — that is the rotation duty's tool (item 35).

Env: NOCTUA_JANUS_URL (our Janus), NOCTUA_JOBS_USER / NOCTUA_JOBS_KEY,
     NOCTUA_AGENCY_ID (our agency id in the partner's system).
Args: --partner-url, --partner-user, --partner-key, --agency
      (the partner's agency id in OUR system).
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request


def http(base, path, user=None, key=None, body=None):
    req = urllib.request.Request(base.rstrip("/") + path,
                                 method="POST" if body is not None
                                 else "GET")
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    if user:
        req.add_header("X-Noctua-User", user)
        req.add_header("X-Noctua-Key", key or "")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def report_hash(obj):
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--partner-url", required=True)
    ap.add_argument("--partner-user", required=True,
                    help="our auditor account AT the partner")
    ap.add_argument("--partner-key", required=True)
    ap.add_argument("--agency", required=True,
                    help="the partner's agency id in OUR system")
    ap.add_argument("--janus", default=os.environ.get(
        "NOCTUA_JANUS_URL", "http://127.0.0.1:8471"),
        help="OUR Janus base URL")
    ap.add_argument("--jobs-user", default=os.environ.get(
        "NOCTUA_JOBS_USER", "jobs.local"))
    ap.add_argument("--jobs-key", default=os.environ.get(
        "NOCTUA_JOBS_KEY", ""))
    ap.add_argument("--our-agency", default=os.environ.get(
        "NOCTUA_AGENCY_ID", ""),
        help="OUR agency id in the PARTNER's system (for the receipt)")
    ap.add_argument("--receipt-user", default="",
                    help="our PARTNER-role username at the partner "
                         "(default: --our-agency)")
    ap.add_argument("--receipt-key", default="",
                    help="key for --receipt-user (default: "
                         "--partner-key)")
    a = ap.parse_args()
    if not a.jobs_key:
        print("compact: NOCTUA_JOBS_KEY not set — cannot record the "
              "audit result on our Janus", file=sys.stderr)
        return 2
    detail = {}
    ok = False
    try:
        cp = http(a.partner_url, "/compact/checkpoint",
                  a.partner_user, a.partner_key)["checkpoint"]
        root = http(a.partner_url, "/audit/root",
                    a.partner_user, a.partner_key)
        verify = http(a.partner_url, "/audit/verify",
                      a.partner_user, a.partner_key)
        detail = {"checkpoint_entries": cp["entries"],
                  "chain_entries": root["entries"],
                  "chain_verify": verify.get("ok")}
        anchor_ok = False
        if cp["entries"] <= root["entries"]:
            entry = http(a.partner_url, "/audit?seq=%d" % cp["entries"],
                         a.partner_user, a.partner_key).get("entry")
            anchor_ok = bool(entry) and entry["hash"] == cp["root"]
        detail["anchor_ok"] = anchor_ok
        ok = bool(verify.get("ok")) and anchor_ok
        if ok:
            # Our attestation lands on THEIR books: we verified the
            # checkpoint identified by (root, entries). Posted with
            # our agency's partner-role identity at the partner.
            receipt = {"agency": a.our_agency or a.agency,
                       "root": cp["root"], "entries": cp["entries"],
                       "sig": cp.get("sig")}
            http(a.partner_url, "/compact/checkpoint-receipt",
                 a.receipt_user or receipt["agency"],
                 a.receipt_key or a.partner_key, body=receipt)
            detail["receipt_posted"] = True
    except Exception as exc:
        detail["error"] = str(exc)
        ok = False
    res = http(a.janus, "/compact/audit-result", a.jobs_user, a.jobs_key,
               body={"agency": a.agency, "ok": ok,
                     "detail": json.dumps(detail)[:280],
                     "report_hash": report_hash(detail)})
    print(json.dumps({"agency": a.agency, "ok": ok, "detail": detail,
                      "recorded": res}, indent=1, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
