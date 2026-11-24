#!/usr/bin/env python3
"""Compact audit rotation — NOCTUA 1.2.2 (S12 + Q23).

1.2.2: the schedule builder is sentinel.rotation_schedule —
imported, not reimplemented (the two 1.2.1 copies had diverged at
n=2). The seed is no longer derived from publisher-chosen inputs:
an official cycle seed comes from Janus's commit-reveal ceremony
(every member commits a nonce hash, then reveals; the seed is
SHA-256 over the revealed nonces). This tool's generator accepts
--seed or --nonces for planning documents and says plainly that a
ceremony seed is the only official one. --verify accepts Janus-
published documents (recomputing the seed from the nonces when
they are present, and the rounds from the seed) as well as legacy
1.2 documents. The signed portion covers members, seed, rounds,
cycle_start AND period_days (sentinel.rotation_signed_portion).

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
    """LEGACY (pre-1.2.2) derived seed, kept only so --verify can
    recompute 1.2-era documents. Never used for a new schedule:
    the publisher could grind cycle_start against it (Q23)."""
    canon = ",".join(sorted(members)) + "|" + cycle_start + "|" \
        + chain_root
    return hashlib.sha256(canon.encode()).hexdigest()


def _legacy_rounds(members, seed):
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
    return [{"round": r + 1, "auditor": order[r],
             "audited": order[(r + 1) % len(order)]}
            for r in range(len(order))]


def seed_from_nonces(members, cycle_start, nonces):
    """The ceremony seed (Q23): SHA-256 over the canonical form of
    the sorted members, the cycle start, and every member's
    revealed nonce — the same computation Janus publishes with."""
    return hashlib.sha256(sentinel.canonical_bytes({
        "members": sorted(set(members)), "cycle_start": cycle_start,
        "nonces": {m: nonces[m] for m in sorted(set(members))}}
    )).hexdigest()


def build_schedule(members, cycle_start, period_days=DEFAULT_PERIOD_DAYS,
                   chain_root="", seed=None, nonces=None):
    """Build a schedule document. The rounds come from
    sentinel.rotation_schedule — the ONE builder (Q23)."""
    members = sorted(set(members))
    if seed is None and nonces is not None:
        seed = seed_from_nonces(members, cycle_start, nonces)
    if seed is None:
        seed = seed_for(members, cycle_start, chain_root)
    built = sentinel.rotation_schedule(members, seed)
    base = {"version": "1.2.2", "cycle_start": cycle_start,
            "period_days": int(period_days), "members": members,
            "seed": seed, "chain_root": chain_root}
    if nonces is not None:
        base["nonces"] = {m: nonces[m] for m in members}
    note = None
    if built["mode"] == "inactive":
        note = "Fewer than 2 members — no audits to rotate."
    elif built["mode"] == "static":
        note = ("Two members: the pairing is STATIC — each audits "
                "the other. Rotation activates at 3+ members.")
    else:
        note = ("Auditor order is the seed's Fisher-Yates "
                "permutation of the members; each round's auditor "
                "audits the next member in the order (cyclically), "
                "so every member audits and is audited exactly "
                "once per cycle.")
    return {**base, "mode": built["mode"], "rounds": built["rounds"],
            "note": note}


def signed_portion(schedule):
    """The dict the signature covers — sentinel's, shared with
    Janus (Q23): members, seed, rounds, cycle_start, period_days."""
    return sentinel.rotation_signed_portion(schedule)


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
    ap.add_argument("--seed", help="the cycle seed (from the "
                        "commit-reveal ceremony) to build from")
    ap.add_argument("--nonces", metavar="FILE",
                    help="JSON file {agency: nonce} — derive the "
                         "ceremony seed from the revealed nonces")
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
        members = sorted(set(sched["members"]))
        if sched.get("nonces"):
            seed = seed_from_nonces(members, sched["cycle_start"],
                                    sched["nonces"])
            if seed != sched.get("seed"):
                print("MISMATCH: the seed does not recompute from "
                      "the published nonces — do not trust it")
                return 2
        built = sentinel.rotation_schedule(members,
                                           sched.get("seed", ""))
        expected = {"members": members, "seed": sched.get("seed"),
                    "rounds": built["rounds"],
                    "cycle_start": sched["cycle_start"],
                    "period_days": sched["period_days"]}
        if sched.get("version", "").startswith("1.2.2"):
            portion_ok = sentinel.canonical_bytes(
                signed_portion(expected)) == sentinel.canonical_bytes(
                signed_portion(sched))
        else:
            # Legacy document: recompute under the pre-1.2.2 rules.
            legacy = build_schedule(members, sched["cycle_start"],
                                    sched["period_days"],
                                    sched.get("chain_root", ""))
            portion_ok = sentinel.canonical_bytes(
                signed_portion(legacy)) == sentinel.canonical_bytes(
                signed_portion(sched))
        if not portion_ok:
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
            # A legacy (pre-1.2.2) signature covers the OLD portion
            # — members, seed, rounds only; a 1.2.2 signature covers
            # sentinel's portion (which adds cycle_start and
            # period_days). Verify against the portion the document
            # was actually signed under.
            if sched.get("version", "").startswith("1.2.2"):
                portion = signed_portion(sched)
            else:
                portion = {"members": sched["members"],
                           "seed": sched["seed"],
                           "rounds": sched["rounds"]}
            if not sentinel.verify_bytes(
                    pub, sentinel.canonical_bytes(portion),
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
    nonces = None
    if a.nonces:
        with open(a.nonces) as f:
            nonces = json.load(f)
    sched = build_schedule(members, a.cycle_start, a.period_days,
                           seed=a.seed, nonces=nonces)
    if not a.seed and not nonces:
        print("note: this planning document's seed uses the LEGACY "
              "derivation — an official cycle seed comes only from "
              "Janus's commit-reveal ceremony (Q23)",
              file=sys.stderr)
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
