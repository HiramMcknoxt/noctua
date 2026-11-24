#!/usr/bin/env python3
"""Compact audit rotation — NOCTUA 1.2 (S12).

Fixed audit pairs go cozy; rotation is the anti-capture mechanism.
This module generates the cross-audit rotation schedule for the
Data-Sharing Compact. It is a PURE FUNCTION of its inputs:

    seed = SHA-256(cycle_start + "|" + ",".join(sorted(members)))

and — the 1.2 change — THE SEED ACTUALLY DRIVES THE SCHEDULE.
Round 3 found that 1.1's schedule was the same circle-method
pairing no matter what the seed said: the seed was published,
reproducible, and irrelevant. Here the seed permutes the slots:

  ALGORITHM (the same one Janus's POST /compact/rotation uses —
  janus.build_schedule; the two are kept in lockstep and the test
  suite cross-checks them): members are sorted, then permuted by a
  Fisher-Yates shuffle driven by the SHA-256(seed) byte stream —
  bytes consumed two at a time (big-endian uint16), swap index
  j = value % (i+1), i walking from n-1 down to 1; the stream is
  extended with SHA-256(stream-so-far) when exhausted. Round r's
  auditor is permuted[r]; they audit permuted[(r+1) % n]. The same
  (members, cycle_start) reproduces the schedule byte-identically;
  a different cycle_start yields a different seed and, with
  overwhelming probability, a different permutation.

Activation: rotation is ACTIVE only at >= 3 members. At 2 members
the pairing is static (each audits the other) and the output says
so plainly. At 0-1 members it is inactive. Joins and leaves take
effect at the NEXT cycle only — a published cycle never reshuffles.
(Janus enforces the same rule server-side: publishing over an
active cycle is refused; voiding takes supervisor + auditor.)

One round = one audit period (COMPACT_ROTATION_PERIOD_DAYS,
default 90; Janus accepts 7-120). Rotation governs the periodic
deep-audit duty; it does NOT change the daily checkpoint
reciprocity gate on /share/query.

Usage:
  rotation.py --members cabot,lonoke,conway --cycle-start 2027-01-01
  rotation.py --members ... --cycle-start ... --table
  rotation.py --verify schedule.json
The schedule JSON is Ed25519-signed (S7) when a signing key is
available (env NOCTUA_SIGNING_KEY, else the key beside
NOCTUA_DB); the public key is embedded so --verify needs nothing
else. The 1.1 HMAC form is gone — the audit key signs nothing.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sentinel  # noqa: E402

DEFAULT_PERIOD_DAYS = int(os.environ.get("COMPACT_ROTATION_PERIOD_DAYS",
                                         "90"))


def seed_for(members, cycle_start, chain_root=""):
    """The derived seed — the SAME canonical form Janus uses
    (janus.rotation_seed, P9): SHA-256 over the sorted members, the
    cycle start, and the chain root at publication. A schedule
    published by Janus carries its seed, and its root input is the
    chain root just before its ROTATION_PUBLISH entry — public
    chain state any partner can recompute."""
    canon = ",".join(sorted(members)) + "|" + cycle_start + "|" \
        + chain_root
    return hashlib.sha256(canon.encode()).hexdigest()


def permute(members, seed):
    """Fisher-Yates over the sorted members, driven by the seed's
    SHA-256 byte stream. Identical to janus.build_schedule."""
    order = sorted(members)
    stream = bytearray(hashlib.sha256(seed.encode()).digest())
    pos = 0

    def next16():
        nonlocal pos
        while pos + 2 > len(stream):
            stream.extend(hashlib.sha256(bytes(stream)).digest())
        v = (stream[pos] << 8) | stream[pos + 1]
        pos += 2
        return v

    for i in range(len(order) - 1, 0, -1):
        j = next16() % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def build_schedule(members, cycle_start, period_days=DEFAULT_PERIOD_DAYS,
                   chain_root=""):
    members = sorted(set(members))
    seed = seed_for(members, cycle_start, chain_root)
    base = {"version": "1.2", "cycle_start": cycle_start,
            "period_days": int(period_days), "members": members,
            "seed": seed, "chain_root": chain_root}
    if len(members) < 2:
        return {**base, "mode": "inactive", "rounds": [],
                "note": "Fewer than 2 members — no audits to rotate."}
    if len(members) == 2:
        a, b = members
        return {**base, "mode": "static",
                "rounds": [{"round": 1, "auditor": a, "audited": b},
                           {"round": 2, "auditor": b, "audited": a}],
                "note": "Two members: the pairing is STATIC — each "
                        "audits the other. Rotation activates at 3+ "
                        "members."}
    order = permute(members, seed)
    rounds = [{"round": r + 1, "auditor": order[r],
               "audited": order[(r + 1) % len(order)]}
              for r in range(len(order))]
    return {**base, "mode": "rotation", "rounds": rounds,
            "note": "Auditor order is the seed's Fisher-Yates "
                    "permutation of the members; each round's "
                    "auditor audits the next member in the order "
                    "(cyclically), so every member audits and is "
                    "audited exactly once per cycle."}


def signed_portion(schedule):
    """The dict the signature covers: members, seed, rounds."""
    return {"members": schedule["members"], "seed": schedule["seed"],
            "rounds": schedule["rounds"]}


def table(schedule):
    lines = ["Rotation schedule — cycle %s, %d members, %d-day rounds, "
             "mode: %s" % (schedule["cycle_start"],
                           len(schedule["members"]),
                           schedule["period_days"], schedule["mode"]),
             "seed: %s" % schedule["seed"]]
    if schedule.get("note"):
        lines.append(schedule["note"])
    for r in schedule.get("rounds", []):
        lines.append("Round %d: %s audits %s"
                     % (r["round"], r["auditor"], r["audited"]))
    return "\n".join(lines)


def _signing_priv():
    p = os.environ.get("NOCTUA_SIGNING_KEY")
    if p:
        return p
    db = os.environ.get("NOCTUA_DB", "/data/noctua.db")
    priv, _pub = sentinel.signing_paths(db)
    return priv if os.path.exists(priv) else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--members", help="comma-separated agency ids")
    ap.add_argument("--members-file", help="JSON file: list of agency ids")
    ap.add_argument("--cycle-start", help="YYYY-MM-DD")
    ap.add_argument("--period-days", type=int,
                    default=DEFAULT_PERIOD_DAYS)
    ap.add_argument("--table", action="store_true",
                    help="print the human-readable table instead of JSON")
    ap.add_argument("--verify", metavar="FILE",
                    help="recompute the schedule in FILE from its seed "
                         "inputs and check it matches byte-for-byte "
                         "(and its Ed25519 signature, if present)")
    ap.add_argument("--pubkey",
                    help="the publisher's Ed25519 public key PEM "
                         "file, as registered (P8: --verify of a "
                         "SIGNED schedule requires a pin)")
    ap.add_argument("--pubkey-fingerprint",
                    help="the registered fingerprint of the "
                         "publisher's public key (P8)")
    a = ap.parse_args()
    if a.verify:
        with open(a.verify) as f:
            sched = json.load(f)
        expected = build_schedule(sched["members"], sched["cycle_start"],
                                  sched["period_days"],
                                  sched.get("chain_root", ""))
        if sentinel.canonical_bytes(signed_portion(expected)) != \
                sentinel.canonical_bytes(signed_portion(sched)):
            print("MISMATCH: the schedule does not recompute from its "
                  "seed — do not trust it")
            return 2
        if sched.get("sig"):
            # P8: a signature is verified ONLY against a pinned key.
            # 1.2 verified against the public key EMBEDDED IN the
            # schedule — the document vouching for itself.
            if not a.pubkey and not a.pubkey_fingerprint:
                print("MISMATCH: schedule is signed but no --pubkey "
                      "or --pubkey-fingerprint pin was given — "
                      "refusing to verify a signature against the "
                      "key embedded in the document itself (P8)")
                return 2
            if sched.get("sig_alg") != "ed25519":
                print("MISMATCH: signature present but not Ed25519")
                return 2
            pub = None
            if a.pubkey:
                pub = open(a.pubkey).read()
            elif sched.get("pubkey"):
                if sentinel.pubkey_fingerprint(sched["pubkey"]) \
                        != a.pubkey_fingerprint:
                    print("MISMATCH: the schedule's embedded public "
                          "key does not match the registered "
                          "fingerprint")
                    return 2
                pub = sched["pubkey"]
            if not pub:
                print("MISMATCH: no pinned public key available")
                return 2
            if not sentinel.verify_bytes(
                    pub,
                    sentinel.canonical_bytes(signed_portion(sched)),
                    sched["sig"]):
                print("MISMATCH: schedule signature does not verify "
                      "against the pinned key")
                return 2
        print("OK: schedule recomputes byte-for-byte from the seed")
        return 0
    if a.members_file:
        with open(a.members_file) as f:
            members = json.load(f)
    elif a.members:
        members = [m.strip() for m in a.members.split(",") if m.strip()]
    else:
        ap.error("--members or --members-file is required")
    if not a.cycle_start:
        ap.error("--cycle-start is required")
    sched = build_schedule(members, a.cycle_start, a.period_days)
    if a.table:
        print(table(sched))
        return 0
    priv = _signing_priv()
    if priv:
        sched["sig"] = sentinel.sign_bytes(
            priv, sentinel.canonical_bytes(signed_portion(sched)))
        sched["sig_alg"] = "ed25519"
        _p, pub = sentinel.signing_paths(
            os.environ.get("NOCTUA_DB", "/data/noctua.db"))
        if os.environ.get("NOCTUA_SIGNING_KEY"):
            # Derive the public half from the explicit private key.
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pem") as f:
                pub_path = f.name
            subprocess.run(["openssl", "pkey", "-in", priv, "-pubout",
                            "-out", pub_path], check=True,
                           capture_output=True, timeout=30)
            sched["pubkey"] = open(pub_path).read()
            os.remove(pub_path)
        elif os.path.exists(pub):
            sched["pubkey"] = open(pub).read()
    print(json.dumps(sched, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
