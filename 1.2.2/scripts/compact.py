#!/usr/bin/env python3
"""Compact cross-audit runner — NOCTUA 1.2.1 (S8; P8 pinning).

Run by a member agency against a PARTNER agency. It performs our
half of the reciprocal audit, and in 1.2 it VERIFIES rather than
attests:

  1. Fetch the partner's newest published checkpoint
     (GET /compact/checkpoint) with the chain_auditor account the
     partner issued us — that role can read the chain and nothing
     else, which is all an audit needs (S9).
  2. Verify the checkpoint's Ed25519 signature with the partner's
     registered public key: the PEM the checkpoint carries must hash
     to --partner-fingerprint (the fingerprint we registered when
     the partner joined), and the signature must verify over the
     canonical checkpoint bytes.
  3. INDEPENDENTLY RECOMPUTE the partner's chain: starting from the
     last (seq, hash) THIS script stored for the partner (state
     file), page GET /audit/range and re-hash every entry —
     prev-linkage and sha(prev|payload) — up to the checkpoint. The
     recomputed hash at the checkpoint's entry count must equal the
     checkpoint's root. /audit/verify is also consulted, but the
     recompute is the check; a partner that reports ok about itself
     has told us nothing.
  4. POST our checkpoint-receipt to the partner: an Ed25519
     signature — with OUR signing key — over (root, entries,
     checkpoint_ts, agency), naming the partner's NEWEST checkpoint.
     A replayed old receipt is refused by their Janus (S8).
  5. Record the outcome on OUR Janus (POST /compact/audit-result)
     as a SIGNED report: the report object is signed with our
     signing key, and our Janus verifies the signature and records
     the report's hash. A failure is recorded exactly like a
     success — the share gate reads the LATEST row, so a failure
     posted after a success closes the gate with no manual
     suspension (S8). If the partner is unreachable, a signed
     ok:false report is still posted.

The state file maps agency -> {"seq": n, "hash": h}: the furthest
point we have independently verified. It lives at
$NOCTUA_COMPACT_STATE (default ~/.noctua-compact-state.json). Losing
it costs a full re-verify from GENESIS, not correctness.

Env: NOCTUA_JANUS_URL (our Janus), NOCTUA_AUDITOR_USER /
     NOCTUA_AUDITOR_KEY (our auditor account on OUR Janus),
     NOCTUA_DB (to find our signing key), NOCTUA_SIGNING_KEY
     (explicit private-key path override), NOCTUA_COMPACT_STATE,
     NOCTUA_AGENCY_ID (our agency id in the partner's system).
Args: --partner-url, --partner-user, --partner-key (our
      chain_auditor account AT the partner), --agency (the
      partner's agency id in OUR system), --partner-pubkey /
      --partner-fingerprint (the partner's registered Ed25519
      public key / its fingerprint), --receipt-user/--receipt-key
      (our partner-role identity at the partner, for the receipt).
"""
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402


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


def load_state(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def recompute(base, user, key, from_seq, from_hash, to_seq):
    """Re-hash the partner's chain from (from_seq, from_hash) up to
    to_seq over /audit/range. Returns (ok, last_seq, last_hash,
    detail). Hashing goes through sentinel.entry_hash — the ONE
    verification contract (P11): v1 and v2 entries both recompute,
    and this script keeps no private copy of the formula."""
    prev = from_hash
    seq = from_seq
    while seq < to_seq:
        chunk_end = min(seq + 1000, to_seq)
        page = http(base, "/audit/range?from_seq=%d&to_seq=%d"
                    % (seq + 1, chunk_end), user, key)
        entries = page.get("entries", [])
        if not entries:
            return False, seq, prev, "range page empty at seq %d" % seq
        for e in entries:
            if e["seq"] != seq + 1:
                return False, seq, prev, \
                    "sequence gap at %d" % e["seq"]
            if e["prev"] != prev:
                return False, seq, prev, \
                    "prev linkage broken at seq %d" % e["seq"]
            if sentinel.entry_hash(prev, e["ts"], e["kind"],
                                   e["payload"]) != e["hash"]:
                return False, seq, prev, \
                    "hash mismatch at seq %d" % e["seq"]
            prev = e["hash"]
            seq = e["seq"]
    return True, seq, prev, "recomputed %d entries" % (seq - from_seq)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--partner-url", required=True)
    ap.add_argument("--partner-user", required=True,
                    help="our chain_auditor account AT the partner")
    ap.add_argument("--partner-key", required=True)
    ap.add_argument("--agency", required=True,
                    help="the partner's agency id in OUR system")
    ap.add_argument("--partner-pubkey",
                    help="file holding the partner's Ed25519 public "
                         "key PEM (as registered)")
    ap.add_argument("--partner-fingerprint",
                    help="the registered fingerprint of the partner's "
                         "public key")
    ap.add_argument("--janus", default=os.environ.get(
        "NOCTUA_JANUS_URL", "http://127.0.0.1:8080"),
        help="OUR Janus base URL")
    ap.add_argument("--auditor-user", default=os.environ.get(
        "NOCTUA_AUDITOR_USER", "auditor.external"))
    ap.add_argument("--auditor-key", default=os.environ.get(
        "NOCTUA_AUDITOR_KEY", ""))
    ap.add_argument("--our-agency", default=os.environ.get(
        "NOCTUA_AGENCY_ID", ""),
        help="REQUIRED (P8): OUR agency id in the PARTNER's system "
             "(for the receipt). 1.2 fell back to the PARTNER's "
             "agency name when it was omitted — a receipt signed "
             "under the wrong identity")
    ap.add_argument("--signing-key", default=os.environ.get(
        "NOCTUA_SIGNING_KEY", ""),
        help="explicit path to OUR Ed25519 private key — the key "
             "the report and the receipt are signed with (P8). "
             "Defaults to the key beside --db, which is also ours; "
             "it is never defaulted to any partner credential")
    ap.add_argument("--receipt-user", default="",
                    help="our PARTNER-role username at the partner "
                         "(default: --our-agency)")
    ap.add_argument("--receipt-key", default="",
                    help="key for --receipt-user (default: "
                         "--partner-key)")
    ap.add_argument("--state", default=os.environ.get(
        "NOCTUA_COMPACT_STATE",
        os.path.expanduser("~/.noctua-compact-state.json")))
    ap.add_argument("--db", default=os.environ.get(
        "NOCTUA_DB", "/data/noctua.db"),
        help="OUR database path (to find our signing key)")
    a = ap.parse_args()
    if not a.auditor_key:
        print("compact: NOCTUA_AUDITOR_KEY not set — cannot record "
              "the audit result on our Janus", file=sys.stderr)
        return 2
    # P8/A23: key pinning is MANDATORY. Without --partner-pubkey or
    # --partner-fingerprint the only key available is the one the
    # checkpoint itself carries — a document vouching for itself.
    # Refuse to run at all.
    if not a.partner_pubkey and not a.partner_fingerprint:
        print("compact: refusing to run without --partner-pubkey or "
              "--partner-fingerprint — the partner's key must be "
              "pinned out-of-band, never taken from the checkpoint "
              "being verified (P8)", file=sys.stderr)
        return 2
    if not a.our_agency:
        print("compact: --our-agency is required — the receipt is "
              "signed under OUR identity, never defaulted to the "
              "partner's name (P8)", file=sys.stderr)
        return 2
    priv = a.signing_key
    if not priv:
        priv, _pub = sentinel.signing_paths(a.db)
    if not os.path.exists(priv):
        print("compact: no Ed25519 signing key at %s — cannot sign "
              "the report or the receipt" % priv, file=sys.stderr)
        return 2
    partner_pub = None
    if a.partner_pubkey:
        partner_pub = open(a.partner_pubkey).read()
    elif a.partner_fingerprint:
        partner_pub = None  # fingerprint-only: cross-check the PEM
        # the checkpoint itself carries, below.

    checks = {}
    ok = False
    cp = None
    try:
        cp = http(a.partner_url, "/compact/checkpoint",
                  a.partner_user, a.partner_key)["checkpoint"]
        # (2) checkpoint signature against the REGISTERED key.
        cp_pub = partner_pub or cp.get("pubkey")
        if a.partner_fingerprint and cp.get("pubkey"):
            checks["pubkey_fingerprint"] = (
                sentinel.pubkey_fingerprint(cp["pubkey"])
                == a.partner_fingerprint)
        elif a.partner_fingerprint:
            checks["pubkey_fingerprint"] = False
        if cp_pub:
            checks["checkpoint_signature"] = sentinel.verify_bytes(
                cp_pub, sentinel.checkpoint_signed_bytes(cp),
                cp.get("sig", ""))
        else:
            checks["checkpoint_signature"] = False
        # (3) independent recompute from our stored point.
        # 1.2.2 (Q22): the checkpoint must be FRESH — 1.2.1 verified
        # a correctly signed 200-day-old checkpoint and passed it
        # (round 5, Claude R5-17): a stale checkpoint proves the
        # partner WAS sound, not that it IS.
        try:
            cp_age_h = (datetime.now(timezone.utc) - datetime.
                        fromisoformat(str(cp["ts"]).replace(
                            "Z", "+00:00"))).total_seconds() / 3600.0
        except (KeyError, TypeError, ValueError):
            cp_age_h = None
        checks["checkpoint_fresh"] = bool(
            cp_age_h is not None and cp_age_h <= 26)
        checks["checkpoint_age_hours"] = (
            round(cp_age_h, 2) if cp_age_h is not None else None)
        state = load_state(a.state)
        mark = state.get(a.agency, {"seq": 0, "hash": "GENESIS"})
        rok, rseq, rhash, rdetail = recompute(
            a.partner_url, a.partner_user, a.partner_key,
            int(mark["seq"]), mark["hash"], int(cp["entries"]))
        checks["chain_recompute"] = rok
        checks["recompute_detail"] = rdetail
        checks["anchor_root"] = bool(rok) and rhash == cp["root"]
        root = http(a.partner_url, "/audit/root",
                    a.partner_user, a.partner_key)
        # The partner's LIVE root is normally AHEAD of the checkpoint
        # (its own heartbeat lands after the checkpoint was cut, and
        # it keeps working). Comparing the live root to the
        # checkpoint-height recompute would fail every healthy
        # partner — so extend the recompute to the live height and
        # compare there. A live height BEHIND the checkpoint is a
        # rewind and fails.
        live_seq, live_hash = rseq, rhash
        if rok and int(root.get("entries", -1)) >= rseq:
            xok, xseq, xhash, _xd = recompute(
                a.partner_url, a.partner_user, a.partner_key,
                rseq, rhash, int(root["entries"]))
            checks["root_matches"] = bool(
                xok and xseq == int(root["entries"])
                and xhash == root.get("root"))
            if checks["root_matches"]:
                live_seq, live_hash = xseq, xhash
        else:
            checks["root_matches"] = False
        verify = http(a.partner_url, "/audit/verify",
                      a.partner_user, a.partner_key)
        checks["partner_self_verify"] = bool(verify.get("ok"))
        ok = all(checks.get(k) for k in (
            "checkpoint_signature", "checkpoint_fresh",
            "chain_recompute", "anchor_root",
            "root_matches", "partner_self_verify")) \
            and checks.get("pubkey_fingerprint", True)
        if ok:
            # Q22: the high-water mark advances to the LIVE
            # verified height, not just the checkpoint's — 1.2.1
            # saved the checkpoint height, so entries above it were
            # re-read fresh (and self-consistently) on every audit,
            # and a rewrite in that band was invisible forever.
            state[a.agency] = {"seq": live_seq, "hash": live_hash}
            save_state(a.state, state)
            # (4) the receipt: our signature over the partner's
            # newest checkpoint facts, posted to THEIR Janus.
            payload = {"agency": a.our_agency,
                       "checkpoint_ts": cp["ts"],
                       "entries": cp["entries"], "root": cp["root"]}
            receipt = {
                "agency": payload["agency"],
                "checkpoint_root": cp["root"],
                "checkpoint_entries": cp["entries"],
                "checkpoint_ts": cp["ts"],
                "signature": sentinel.sign_bytes(
                    priv, sentinel.canonical_bytes(payload))}
            http(a.partner_url, "/compact/checkpoint-receipt",
                 a.receipt_user or receipt["agency"],
                 a.receipt_key or a.partner_key, body=receipt)
            checks["receipt_posted"] = True
    except Exception as exc:
        checks["error"] = str(exc)
        ok = False
    # (5) the signed report to OUR Janus — posted on failure too:
    # the gate reads the LATEST row, and a failure that is never
    # recorded never closes anything.
    report = {"agency": a.agency, "ok": ok, "ts": sentinel.now_iso(),
              "checks": checks,
              "checkpoint": ({"root": cp["root"],
                              "entries": cp["entries"],
                              "ts": cp["ts"]} if cp else None)}
    report_sig = sentinel.sign_bytes(
        priv, sentinel.canonical_bytes(report))
    res = http(a.janus, "/compact/audit-result", a.auditor_user,
               a.auditor_key,
               body={"agency": a.agency, "report": report,
                     "report_sig": report_sig})
    print(json.dumps({"agency": a.agency, "ok": ok, "checks": checks,
                      "recorded": res}, indent=1, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
