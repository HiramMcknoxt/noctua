#!/usr/bin/env python3
"""NOCTUA demo seeder — loads a complete, safe demonstration dataset.

    # 1. start Janus pointed at fresh demo paths (files need not exist yet)
    NOCTUA_DB=/tmp/demo/noctua.db NOCTUA_USERS=/tmp/demo/users.json \
    NOCTUA_CASES=/tmp/demo/cases.json NOCTUA_PORT=8080 python3 ../janus.py &
    # 2. seed it
    NOCTUA_DB=/tmp/demo/noctua.db NOCTUA_USERS=/tmp/demo/users.json \
    NOCTUA_CASES=/tmp/demo/cases.json \
    NOCTUA_JANUS_URL=http://127.0.0.1:8080 python3 seed_demo.py

WHAT IT LOADS
  * Demo users (scripts/provision.py's record format and hashing; the
    keys are FIXED and PUBLISHED in DEMO-DATA.md — demo-only, never
    usable anywhere real, which is exactly why this script does not use
    provision.py's random keys),
  * the demo case list (all cases are DEMO cases),
  * the demo hot list, demo-plate reads, one confirmed hit, one
    rejected hit, and two protection-order suppressions (one on a
    plain plate, one on a hot-listed plate, so its hits land in the
    supervisor-only suppressed queue) — all through the Janus API,
    so the Sentinel chain shows real entries,
  * one day of background traffic at 1/10 of Cabot's real volume
    (4,442 of 44,420 reads/day; the rates, camera count, and match
    frequency are the real ones from the Cabot record — see
    INTERFACE.md). Background reads are inserted directly into SQLite
    WITH matching counters rows, in one transaction. That bypass is
    deliberate and documented: Janus has no backfill API, by design —
    history cannot be fabricated through the front door. Only
    non-hot-list plates are backfilled, so no ALERT is missing from
    the chain; every hit in the demo was produced live through /reads.

SAFETY / IDEMPOTENCY: fresh-target only. The script REFUSES (exit 2)
if users.json already contains anyone outside the demo set, or if the
database already holds reads — unless --force is given, in which case
the API steps repeat (duplicate demo hits) and background traffic
doubles. Run it against a throwaway database. All plates are synthetic
Arkansas-format; all cases are demo cases; nothing here is real data.
"""
import hashlib
import json
import os
import random
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

DB = os.environ.get("NOCTUA_DB", "/data/noctua.db")
USERS_PATH = os.environ.get("NOCTUA_USERS", "/config/users.json")
CASES_PATH = os.environ.get("NOCTUA_CASES", "/config/cases.json")
JANUS = os.environ.get("NOCTUA_JANUS_URL", "http://127.0.0.1:8080")
FORCE = "--force" in sys.argv

# --- the demo cast (published in DEMO-DATA.md; demo-only keys) ---------
DEMO_USERS = [
    ("det.okafor", "detective", "DEMO-KEY-DETECTIVE"),
    ("ofc.chen", "patrol", "DEMO-KEY-PATROL"),
    ("sgt.reyes", "supervisor", "DEMO-KEY-SUPERVISOR"),
    ("capt.voss", "supervisor", "DEMO-KEY-SUPERVISOR2"),
    ("auditor.external", "auditor", "DEMO-KEY-AUDITOR"),
    # 1.1: the old 'system' role is split in two (item 8) — ingest
    # posts reads and nothing else; jobs posts heartbeats and
    # nothing else. Neither can read data back (item 23).
    ("ingest.local", "ingest", "DEMO-KEY-INGEST"),
    ("jobs.local", "jobs", "DEMO-KEY-JOBS"),
]
KEYS = {u: k for u, _r, k in DEMO_USERS}

DEMO_CASES = {
    "2027-1001": "burglary investigation (DEMO)",
    "2027-1014": "stolen vehicle (DEMO)",
    "2027-1023": "missing person (DEMO)",
    "2027-1031": "felony warrant service (DEMO)",
    "2027-1040": "protection order (DEMO)",
    "2027-1052": "narcotics investigation (DEMO)",
}

HOTLIST = [
    ("RST417", "stolen vehicle", "2027-1014"),
    ("MNA238", "missing person", "2027-1023"),
    ("WNT556", "felony warrant", "2027-1031"),
    ("AMB771", "AMBER alert", "2027-1023"),
]
SUPPRESSED_PLATE = "VIC309"   # protection order, case 2027-1040
SUPPRESSED_CASE = "2027-1040"
SUPPRESSED_ORDER = "PO-2027-0117, Lonoke County Circuit Court (DEMO)"
# A plate that is BOTH hot-listed and suppressed (1.1, item 5): its
# hits route to the supervisor-only suppressed queue and are invisible
# everywhere else.
PROTECTED_HOT = "PRT208"
PROTECTED_ORDER = "PO-2027-0131, Lonoke County Circuit Court (DEMO)"

# Demo-plate passes through the API: (plate, camera)
PASSES = [
    ("RST417", "CAM-01"), ("RST417", "CAM-02"), ("RST417", "CAM-01"),
    ("MNA238", "CAM-03"), ("MNA238", "CAM-05"),
    ("WNT556", "CAM-07"),
    ("AMB771", "CAM-02"),
    (SUPPRESSED_PLATE, "CAM-04"), (SUPPRESSED_PLATE, "CAM-04"),
    (PROTECTED_HOT, "CAM-06"), (PROTECTED_HOT, "CAM-06"),
]

CAMS = [f"CAM-{i:02d}" for i in range(1, 10)]
BACKGROUND_READS = 4442  # 1/10 of Cabot's 44,420 reads/day (INTERFACE.md)


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def call(method, path, user, body=None):
    req = urllib.request.Request(JANUS + path, method=method)
    req.add_header("X-Noctua-User", user)
    req.add_header("X-Noctua-Key", KEYS[user])
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def guard():
    if FORCE:
        return
    if os.path.exists(USERS_PATH):
        existing = {u["user"] for u in json.load(open(USERS_PATH))}
        extra = existing - set(KEYS)
        if extra:
            print(f"REFUSING: {USERS_PATH} already contains non-demo "
                  f"users {sorted(extra)}. The demo seeder only "
                  f"writes demo files. (Override: --force)",
                  file=sys.stderr)
            sys.exit(2)
    if os.path.exists(DB):
        db = sqlite3.connect(DB)
        try:
            n = db.execute("SELECT COUNT(*) FROM reads").fetchone()[0]
        except sqlite3.Error:
            n = 0
        db.close()
        if n:
            print(f"REFUSING: {DB} already holds {n} reads. Seed a "
                  f"fresh database. (Override: --force)", file=sys.stderr)
            sys.exit(2)


def write_config():
    users = [{"user": u, "role": r, "key_sha256": sha(k)}
             for u, r, k in DEMO_USERS]
    with open(USERS_PATH, "w") as f:
        json.dump(users, f, indent=1)
    with open(CASES_PATH, "w") as f:
        json.dump({"_comment": "DEMO case list — every case here is a "
                               "demonstration case, not a real case.",
                   "open_cases": sorted(DEMO_CASES)}, f, indent=1)
    print(f"wrote demo users.json ({len(users)} users) and cases.json "
          f"({len(DEMO_CASES)} cases)")


def wait_for_janus():
    # /health is unauthenticated — and in 1.1 the ingest identity
    # could not call /stats anyway (service accounts never read).
    for _ in range(60):
        try:
            req = urllib.request.Request(JANUS + "/health")
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.5)
    sys.exit(f"Janus did not answer at {JANUS} — start Janus first "
             f"(see this file's header).")


def api_load():
    for plate, category, case in HOTLIST:
        s, r = call("POST", "/hotlist", "det.okafor",
                    {"plate": plate, "state": "AR", "category": category,
                     "case": case})
        assert s == 201, (plate, s, r)
    print(f"hot list loaded via API: {len(HOTLIST)} entries")
    # PRT208 goes on the hot list FIRST, then under a protection-order
    # suppression — so its passes below produce hits that only the
    # supervisor queue may ever see (1.1, item 5).
    s, r = call("POST", "/hotlist", "det.okafor",
                {"plate": PROTECTED_HOT, "state": "AR",
                 "category": "felony warrant", "case": "2027-1031"})
    assert s == 201, (s, r)
    s, r = call("POST", "/suppressions", "sgt.reyes",
                {"plate": PROTECTED_HOT, "order_ref": PROTECTED_ORDER})
    assert s == 201, (s, r)
    # Protection-order suppression for VIC309 (placed before its
    # passes, so even its plain reads stay out of search results).
    # 1.1: a suppression is placed against the ORDER reference, not a
    # case number (the case is optional file context).
    s, r = call("POST", "/suppressions", "sgt.reyes",
                {"plate": SUPPRESSED_PLATE, "order_ref": SUPPRESSED_ORDER,
                 "case": SUPPRESSED_CASE})
    assert s == 201, (s, r)
    print(f"suppressions placed on {SUPPRESSED_PLATE} and "
          f"{PROTECTED_HOT} (protection orders)")
    hits = {}
    for plate, cam in PASSES:
        s, r = call("POST", "/reads", "ingest.local",
                    {"plate": plate, "state": "AR", "cam": cam,
                     "conf": 0.97})
        assert s == 201, (plate, s, r)
        if r["result"] == "ALERT":
            hits.setdefault(plate, []).append(r["hit_id"])
    print(f"demo passes ingested via API: {len(PASSES)} reads, "
          f"{sum(len(v) for v in hits.values())} alerts")
    # One confirmed hit (the stolen vehicle is worked and confirmed)...
    s, r = call("POST", "/verify", "det.okafor",
                {"hit_id": hits["RST417"][0], "decision": "confirm",
                 "case": "2027-1014"})
    assert s == 200 and r["result"] == "VERIFIED", (s, r)
    call("POST", "/outcomes", "det.okafor",
         {"hit_id": hits["RST417"][0], "arrest": True,
          "prosecution": False})
    # ...and one rejected hit (the AMBER plate was a misread), so the
    # statutory report shows a non-corresponding match too.
    s, r = call("POST", "/verify", "det.okafor",
                {"hit_id": hits["AMB771"][0], "decision": "reject",
                 "case": "2027-1023"})
    assert s == 200 and r["result"] == "REJECTED", (s, r)
    print("worked one hit to VERIFIED (+arrest) and one to REJECTED")
    return hits


def background_load():
    rng = random.Random(2027)
    letters = "ABCDEFGHJKMNPRSTUVWXYZ"  # no I/O/Q — OCR-confusable-light
    demo_plates = {p for p, _c, _k in HOTLIST} | {SUPPRESSED_PLATE,
                                                  PROTECTED_HOT}
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    span = max(1, int((now - day_start).total_seconds()))
    day = now.strftime("%Y-%m-%d")
    db = sqlite3.connect(DB)
    db.execute("PRAGMA secure_delete = ON")
    counts = {}
    rows = []
    while len(rows) < BACKGROUND_READS:
        plate = (rng.choice(letters) + rng.choice(letters)
                 + rng.choice(letters) + str(rng.randint(100, 999)))
        if plate in demo_plates:
            continue
        cam = rng.choice(CAMS)
        ts = day_start.timestamp() + rng.randint(0, span)
        ts_s = datetime.fromtimestamp(ts, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        state = "AR" if rng.random() < 0.92 else rng.choice(
            ["MO", "TX", "OK", "TN", "MS"])
        rows.append((ts_s, cam, plate, state,
                     round(rng.uniform(0.82, 0.99), 2)))
        counts[cam] = counts.get(cam, 0) + 1
    db.executemany(
        "INSERT INTO reads(ts,cam,plate,state,conf) VALUES(?,?,?,?,?)",
        rows)
    for cam, n in counts.items():
        db.execute(
            "INSERT INTO counters(day,camera_id,reads,alerts) "
            "VALUES(?,?,?,0) ON CONFLICT(day,camera_id) DO UPDATE SET "
            "reads=reads+excluded.reads", (day, cam, n))
    db.commit()
    db.close()
    print(f"background traffic: {len(rows)} reads across "
          f"{len(counts)} cameras (direct insert + counters — see "
          f"header for why)")


def main():
    guard()
    write_config()
    wait_for_janus()
    hits = api_load()
    background_load()
    s, stats = call("GET", "/stats", "det.okafor")
    s2, report = call("GET", "/report", "auditor.external")
    print("\nDEMO READY")
    print(f"  reads in store: {stats['reads']} "
          f"(report plates_scanned: {report['plates_scanned']})")
    print(f"  hits: {stats['hits']} total, {stats['pending']} pending "
          f"({stats['suppressed_pending']} of them in the "
          f"supervisor-only suppressed queue)")
    print("  presenter sheet: DEMO-DATA.md (same folder)")


if __name__ == "__main__":
    main()
