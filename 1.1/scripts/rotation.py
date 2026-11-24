#!/usr/bin/env python3
"""Compact audit rotation — NOCTUA 1.1 (item 35).

Fixed audit pairs go cozy; rotation is the anti-capture mechanism.
This module generates the cross-audit rotation schedule for the
Data-Sharing Compact. It is a PURE FUNCTION of a published seed:

    seed = SHA-256(cycle_start + "|" + ",".join(sorted(members)))

Anyone holding the member list and the cycle start date recomputes
the identical schedule — the rotation cannot be rigged after the
fact, because there is nothing in it to choose.

Method (circle method + mirrored half):
  * Members are placed in slots (an odd count gets one bye slot).
  * Base rounds: hold slot 0, rotate the rest; pair slot i with slot
    S-1-i. The member earlier in the round's rotated order audits the
    other, so a round NEVER contains a same-round mutual pair.
  * Mirrored half: the same pairings repeat with orientation flipped.
    Base + mirror together mean every member audits every other
    member EXACTLY ONCE per cycle (every ordered pair exactly once).
  * Odd N: the member paired with the bye slot is that round's
    WITNESS — their duty is to verify every member published their
    checkpoint that period. The bye is a job, not a rest.

Activation: rotation is ACTIVE only at >= 3 members. At 2 members the
pairing is static (each audits the other) and the output says so
plainly. At 0-1 members it is inactive. Joins and leaves take effect
at the NEXT cycle only — a published cycle never reshuffles.

One round = one audit period (COMPACT_ROTATION_PERIOD_DAYS, default
90). Rotation governs the periodic deep-audit duty; it does NOT
change the daily checkpoint reciprocity gate on /share/query.

Usage:
  rotation.py --members cabot,lonoke,conway --cycle-start 2027-01-01
  rotation.py --members ... --cycle-start ... --table
  rotation.py --verify schedule.json
The schedule JSON is HMAC-signed with the publisher's key
(env ROTATION_SIGN_KEY, else NOCTUA_AUDIT_KEY) when one is available.
"""
import argparse
import hashlib
import hmac
import json
import os
import sys

DEFAULT_PERIOD_DAYS = int(os.environ.get("COMPACT_ROTATION_PERIOD_DAYS",
                                         "90"))


def seed_for(members, cycle_start):
    canon = cycle_start + "|" + ",".join(sorted(members))
    return hashlib.sha256(canon.encode()).hexdigest()


def _rounds_for(slots):
    """slots: member list with None as the bye slot (even length).
    Returns base rounds: [{pairs: [[auditor, auditee], ...],
    witness: member-or-None}]."""
    s = len(slots)
    rounds = []
    ring = list(slots[1:])
    for r in range(s - 1):
        rotated = [slots[0]] + ring[r:] + ring[:r]
        pairs, witness = [], None
        for i in range(s // 2):
            a, b = rotated[i], rotated[s - 1 - i]
            if a is None or b is None:
                witness = b if a is None else a
            else:
                pairs.append([a, b])  # earlier in rotated order audits
        rounds.append({"pairs": pairs, "witness": witness})
    return rounds


def build_schedule(members, cycle_start, period_days=DEFAULT_PERIOD_DAYS):
    members = sorted(members)
    base = {"version": "1.1", "cycle_start": cycle_start,
            "period_days": int(period_days), "members": members,
            "seed": seed_for(members, cycle_start)}
    if len(members) < 2:
        return {**base, "mode": "inactive", "rounds": [],
                "note": "Fewer than 2 members — no audits to rotate."}
    if len(members) == 2:
        a, b = members
        return {**base, "mode": "static",
                "rounds": [{"round": 1, "pairs": [[a, b], [b, a]],
                            "witness": None}],
                "note": "Two members: the pairing is STATIC — each "
                        "audits the other. Rotation activates at 3+ "
                        "members."}
    slots = list(members)
    if len(slots) % 2 == 1:
        slots.append(None)  # bye slot
    base_rounds = _rounds_for(slots)
    rounds = []
    for i, r in enumerate(base_rounds):
        rounds.append({"round": i + 1, "pairs": r["pairs"],
                       "witness": r["witness"]})
    # Mirrored half: same pairings, orientation flipped — this is
    # what makes every ORDERED pair occur exactly once per cycle.
    for i, r in enumerate(base_rounds):
        rounds.append({"round": len(base_rounds) + i + 1,
                       "pairs": [[b, a] for a, b in r["pairs"]],
                       "witness": r["witness"]})
    return {**base, "mode": "rotation", "rounds": rounds,
            "note": "Every member audits every other member exactly "
                    "once per cycle; no round contains a mutual pair. "
                    "The bye member each round is the cycle witness: "
                    "they verify all members published their "
                    "checkpoints that period."}


def canonical(schedule):
    """The byte form signatures and hashes are computed over: the
    schedule minus its signature, keys sorted, no whitespace."""
    return json.dumps({k: v for k, v in schedule.items() if k != "sig"},
                      sort_keys=True, separators=(",", ":"))


def sign(schedule, key):
    return hmac.new(key.encode(), canonical(schedule).encode(),
                    hashlib.sha256).hexdigest()


def table(schedule):
    lines = ["Rotation schedule — cycle %s, %d members, %d-day rounds, "
             "mode: %s" % (schedule["cycle_start"],
                           len(schedule["members"]),
                           schedule["period_days"], schedule["mode"]),
             "seed: %s" % schedule["seed"]]
    if schedule.get("note"):
        lines.append(schedule["note"])
    for r in schedule.get("rounds", []):
        pairs = "; ".join("%s audits %s" % (a, b) for a, b in r["pairs"])
        w = ("  [witness: %s]" % r["witness"]) if r.get("witness") else ""
        lines.append("Round %d: %s%s" % (r["round"], pairs, w))
    return "\n".join(lines)


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
                         "(and its HMAC, if a key is available)")
    a = ap.parse_args()
    key = os.environ.get("ROTATION_SIGN_KEY") or os.environ.get(
        "NOCTUA_AUDIT_KEY")
    if a.verify:
        with open(a.verify) as f:
            sched = json.load(f)
        expected = build_schedule(sched["members"], sched["cycle_start"],
                                  sched["period_days"])
        if canonical(expected) != canonical(sched):
            print("MISMATCH: the schedule does not recompute from its "
                  "seed — do not trust it")
            return 2
        if key and sched.get("sig"):
            if not hmac.compare_digest(sign(sched, key), sched["sig"]):
                print("MISMATCH: schedule HMAC does not verify")
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
    if key:
        sched["sig"] = sign(sched, key)
    print(json.dumps(sched, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
