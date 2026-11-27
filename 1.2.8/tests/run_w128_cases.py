#!/usr/bin/env python3
#  ___
# (o o)   VESPER · the evening watch
# (   )   Vesper, for Corey Spangler — Cabot, Arkansas
#  ^^^
"""W battery — the 1.2.8 acceptance cases (council round 10).

Each case runs against the TEST tree (janus128) and the BASELINE
tree (janus127) and passes only when the invariant HOLDS on the
test tree and does NOT hold on the baseline (the discrimination
standard of the Q/R/S/T/U/V batteries). Cases are keyed to the
commission in council10/SYNTHESIS.md section 6:

  W1  V5 reason promotion: a checkpoint disagreement evaluated
      while the anchor fence stands for a file-state reason is
      PROMOTED into the fence record (ANCHOR_REASON_PROMOTED
      chained first), and a later clean evaluation does NOT
      auto-clear — the disagreement was never accepted. (The
      chair's C02 sequence / Claude B's r01.)
  W1b the promotion is atomic with its chain entry: with
      chain.append forced to fail, the file-state record stands
      unpromoted (unit level).
  W2  ceremony warning suppression: in the ceremony state a
      suppression placement returns the bare acknowledgment —
      no warning_near_matches — while the order still places
      and chains. (R10-C01a.)
  W3  ceremony hold uniformity: in the ceremony state a
      hit-scope hold placement answers identically whether the
      hit exists or not; the hold is placed only for a real hit.
      (R10-C01b.)
  W4  ceremony releases fenced: /holds/release and
      /suppressions/release refuse 503 + CEREMONY_REFUSED in the
      ceremony state; the protection they guard stays in place.
  W5  G1 reactivation: re-submitting an expired (inactive)
      listing under the same key reactivates it into the
      supervisor pending queue, and the chain entry's effect
      field says "reactivated".

Usage: python3 tests/run_w128_cases.py [test_tree] [baseline_tree]
       [name-filter]
"""
import importlib.util
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_TREE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 \
    else os.path.dirname(HERE)
BASE_TREE = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 \
    else os.path.join(os.path.dirname(TEST_TREE), "janus127")
ONLY = sys.argv[3] if len(sys.argv) > 3 else None


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _load("t_battery_harness", os.path.join(HERE, "run_t125_cases.py"))
Boot, req, audit_kinds = T.Boot, T.req, T.audit_kinds
ingest, run_checkpoint = T.ingest, T.run_checkpoint
DET, PAT, SUP, SUP2, AUD, CA, ING, JOB = (T.DET, T.PAT, T.SUP,
                                         T.SUP2, T.AUD, T.CA,
                                         T.ING, T.JOB)
KEYS = T.KEYS
WORK = os.path.join(TEST_TREE, "scratch", "w-battery")
os.makedirs(WORK, exist_ok=True)
RESULTS = []


def report(name, ok, detail):
    RESULTS.append((name, ok))
    print("CASE %s %s :: %s" % (name, "PASS" if ok else "FAIL",
                                json.dumps(detail)[:1600]))
    sys.stdout.flush()


def run_unit(tree, code, env_extra=None):
    """Run a python snippet against a tree's modules in a
    subprocess; the snippet prints one JSON object. Returns
    (rc, parsed-or-None, raw_stdout, stderr_tail)."""
    d = os.path.join(WORK, "unit-%d" % (abs(hash(code)) % 99999))
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "unit.py")
    with open(path, "w") as f:
        f.write(code)
    env = dict(os.environ)
    env.update({"NOCTUA_DB": os.path.join(d, "u.db"),
                "NOCTUA_AUDIT_KEY": "w-battery-audit-key",
                "NOCTUA_SENTINEL_SINK": os.path.join(d, "sink.log"),
                "PYTHONPATH": tree})
    if env_extra:
        env.update(env_extra)
    import subprocess
    r = subprocess.run([sys.executable, path], env=env,
                       capture_output=True, text=True, timeout=600)
    parsed = None
    for line in reversed(r.stdout.strip().splitlines()):
        try:
            parsed = json.loads(line)
            break
        except ValueError:
            continue
    return r.returncode, parsed, r.stdout, r.stderr[-400:]


def audit_payloads(A, kind):
    try:
        return [json.loads(r[0]) for r in A.sql(
            "SELECT payload FROM audit WHERE kind=?", (kind,))]
    except Exception:
        return []


def _wait_unfenced(A, timeout=20):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        s, _b = req(A.port, "GET", "/hits", DET)
        last = s
        if s != 503:
            return True, s
        time.sleep(0.5)
    return False, last


def _wait_fenced(A, timeout=20):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        s, _b = req(A.port, "GET", "/hits", DET)
        last = s
        if s == 503:
            return True, s
        time.sleep(0.5)
    return False, last


def _anchor_record(A):
    rows = A.sql("SELECT value FROM meta WHERE "
                 "key='anchor_mismatch'")
    if not rows:
        return {}
    try:
        return json.loads(rows[0][0])
    except ValueError:
        return {}


def _wait_record_reason(A, reason, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        req(A.port, "GET", "/hits", DET)  # drives the 5s cadence
        if _anchor_record(A).get("reason") == reason:
            return True
        time.sleep(0.6)
    return False


def _ceremony_boot(tree, tag, side, seedfn):
    """Seed under LAB, then reboot the copied directory with the
    lab flag explicitly off: a ceremony-state install that has
    data but has never completed provisioning (the v4 pattern)."""
    L = Boot(tree, "%s-lab-%s" % (tag, side)).start()
    try:
        seedfn(L)
    finally:
        L.stop()
    d2 = os.path.join(WORK, "%s-cer-%s" % (tag, side))
    shutil.rmtree(d2, ignore_errors=True)
    shutil.copytree(L.dir, d2)
    return Boot(tree, "%s-cer-%s" % (tag, side), dirpath=d2,
                env_extra={"NOCTUA_LAB": "0"}).start()


# ------------------------------------------------------------------
# W1 — V5 reason promotion (the C02 / r01 sequence)
# ------------------------------------------------------------------
def w1_reason_promotion(tree, side):
    """Torn line fences as checkpoints_malformed; a genuine
    disagreement is then evaluated during the same episode; the
    record must PROMOTE to checkpoint_disagreement (bad_ids
    recorded, ANCHOR_REASON_PROMOTED chained); restoring the good
    file must NOT auto-clear; the two-key accept then clears."""
    A = Boot(tree, "w1-%s" % side).start()
    B = Boot(tree, "w1x-%s" % side).start()
    try:
        p = A.port
        ingest(p, "W1A111")
        run_checkpoint(A)
        ingest(B.port, "W1B999")
        run_checkpoint(B)
        cp_path = A.db + ".checkpoints.jsonl"
        good = open(cp_path).read()
        foreign = open(B.db + ".checkpoints.jsonl").read()
        with open(cp_path, "a") as f:
            f.write('{"seq": 99, "root": "abc')
        fenced1, _s = _wait_fenced(A)
        rec1 = _anchor_record(A)
        with open(cp_path, "w") as f:
            f.write(good + foreign)
        promoted = _wait_record_reason(A, "checkpoint_disagreement")
        rec2 = _anchor_record(A)
        kinds = audit_kinds(A)
        with open(cp_path, "w") as f:
            f.write(good)
        time.sleep(8)  # past the 5s evaluation cadence
        s, _b = req(p, "GET", "/hits", DET)
        still_fenced = (s == 503)
        s1, _b = req(p, "POST", "/audit/anchor-accept", SUP, {})
        s2, _b = req(p, "POST", "/audit/anchor-accept", AUD, {})
        cleared, _s = _wait_unfenced(A)
        ok = (fenced1
              and rec1.get("reason") == "checkpoints_malformed"
              and promoted
              and bool(rec2.get("bad_ids"))
              and rec2.get("promoted_from") == "checkpoints_malformed"
              and "ANCHOR_REASON_PROMOTED" in kinds
              and still_fenced and cleared)
        return ok, {"torn_fenced": fenced1,
                    "record_after_torn": rec1.get("reason"),
                    "promoted": promoted,
                    "record_after_foreign": rec2.get("reason"),
                    "bad_ids_recorded": bool(rec2.get("bad_ids")),
                    "promotion_chained":
                        "ANCHOR_REASON_PROMOTED" in kinds,
                    "still_fenced_after_repair": still_fenced,
                    "accept_statuses": (s1, s2),
                    "cleared_after_accept": cleared}
    finally:
        A.stop()
        B.stop()


# ------------------------------------------------------------------
# W1b — the promotion is atomic with its chain entry
# ------------------------------------------------------------------
_W1B_CODE = r"""
import json, os, sys
d = os.path.dirname(os.environ["NOCTUA_DB"])
users = [{"user": "det.okafor", "role": "detective",
          "key_sha256": "x" * 64}]
for name, obj in (("users.json", users),
                  ("cases.json", {"open_cases": ["2027-1001"]}),
                  ("cameras.json", {"cameras": ["CAM-01"]})):
    with open(os.path.join(d, name), "w") as f:
        json.dump(obj, f)
os.environ.update({
    "NOCTUA_USERS": os.path.join(d, "users.json"),
    "NOCTUA_CASES": os.path.join(d, "cases.json"),
    "NOCTUA_CAMERAS": os.path.join(d, "cameras.json"),
    "NOCTUA_PORT": "0"})
sys.path.insert(0, os.environ["PYTHONPATH"])
import janus
out = {}
DETAIL = {"reason": "checkpoint_disagreement",
          "bad_ids": [[7, "deadbeefcafe"]], "bad_entries": ["7"],
          "checkpoint_entries": 7, "chain_entries": 3}
FILE_STATE = {"reason": "checkpoints_malformed",
              "detected": "2027-01-01T00:00:00Z",
              "malformed_lines": 1}
# leg 1: a working append — the promotion lands, chained
janus._meta_set("anchor_mismatch", json.dumps(FILE_STATE))
janus._anchor_apply(True, dict(DETAIL))
rec = json.loads(janus._meta_get("anchor_mismatch"))
out["promoted"] = (
    rec.get("reason") == "checkpoint_disagreement"
    and rec.get("bad_ids") == [[7, "deadbeefcafe"]]
    and rec.get("promoted_from") == "checkpoints_malformed")
kinds = [r[0] for r in janus.db.execute(
    "SELECT kind FROM audit").fetchall()]
out["promotion_chained"] = "ANCHOR_REASON_PROMOTED" in kinds
# leg 2: a failing append — the record stands unpromoted
janus._meta_set("anchor_mismatch", json.dumps(FILE_STATE))
real_append = janus.chain.append
def boom(*a, **k):
    raise RuntimeError("injected chain failure")
janus.chain.append = boom
try:
    janus._anchor_apply(True, dict(DETAIL))
finally:
    janus.chain.append = real_append
rec2 = json.loads(janus._meta_get("anchor_mismatch"))
out["abort_kept_record"] = (
    rec2.get("reason") == "checkpoints_malformed")
print(json.dumps(out))
"""


def w1b_promotion_atomicity(tree, side):
    """With chain.append working, _anchor_apply promotes a
    file-state record to the disagreement (chained); with
    chain.append forced to fail, the promotion does not land —
    the file-state record stands. (1.2.7 has no promotion at
    all, so leg 1 fails there.)"""
    rc, out, _raw, err = run_unit(tree, _W1B_CODE)
    ok = (rc == 0 and out and out.get("promoted") is True
          and out.get("promotion_chained") is True
          and out.get("abort_kept_record") is True)
    return ok, {"unit": out, "rc": rc, "stderr": err[-300:]}


# ------------------------------------------------------------------
# W2 — ceremony warning suppression
# ------------------------------------------------------------------
def w2_ceremony_warning(tree, side):
    """Historical reads exist under raw variant forms of a plate.
    In the ceremony state a key-only supervisor's suppression
    placement succeeds and chains, but the response carries NO
    warning_near_matches. (1.2.7 returns the variants.)"""
    def seed(L):
        for raw in ("CAB 123", "CAB-123", "cab123", "CAB123",
                    "ZZZ999"):
            ingest(L.port, raw)
    C = _ceremony_boot(tree, "w2", side, seed)
    try:
        p = C.port
        s, hb = req(p, "GET", "/health", JOB)
        state = (hb.get("totp") or {}).get("state")
        s, _b = req(p, "GET", "/search", SUP)
        fenced = s
        s, b = req(p, "POST", "/suppressions", SUP,
                   {"plate": "CAB123", "order_ref": "PO-W2"})
        placed = s
        rows = C.sql("SELECT active FROM suppressions")
        kinds = audit_kinds(C)
        ok = (state == "ceremony" and fenced == 503
              and placed == 201
              and b.get("result") == "suppression placed"
              and "warning_near_matches" not in b
              and rows and rows[0][0] == 1
              and "SUPPRESSION_PLACE" in kinds)
        return ok, {"totp_state": state, "search_status": fenced,
                    "placement_status": placed,
                    "response_keys": sorted(b.keys()),
                    "suppression_active": rows[0][0] if rows else None,
                    "place_chained": "SUPPRESSION_PLACE" in kinds}
    finally:
        C.stop()


# ------------------------------------------------------------------
# W3 — ceremony hold uniformity
# ------------------------------------------------------------------
def w3_ceremony_hold_uniform(tree, side):
    """A real hit exists. In the ceremony state, hold placements
    on the existing hit and on a nonexistent id return the SAME
    status and body; the hold is placed (and chained) only for
    the real hit. (1.2.7 splits 201 vs 404.)"""
    seeded = {}

    def seed(L):
        req(L.port, "POST", "/hotlist", SUP,
            {"plate": "W3H111", "state": "AR",
             "category": "stolen vehicle", "case": "2027-1001",
             "expires": "2030-01-01"})
        ingest(L.port, "W3H111")
        rows = L.sql("SELECT id, case_no FROM hits")
        seeded["hit_id"] = rows[0][0]
        seeded["case"] = rows[0][1] or "2027-1001"

    C = _ceremony_boot(tree, "w3", side, seed)
    try:
        p = C.port
        hid = seeded["hit_id"]
        case = seeded["case"]
        s1, b1 = req(p, "POST", "/holds", SUP,
                     {"scope": "hit", "ref": hid, "case": case})
        s2, b2 = req(p, "POST", "/holds", SUP,
                     {"scope": "hit", "ref": 999999, "case": case})
        real = C.sql("SELECT COUNT(*) FROM holds WHERE scope='hit' "
                     "AND ref=?", (str(hid),))[0][0]
        ghost = C.sql("SELECT COUNT(*) FROM holds WHERE ref='999999'"
                      )[0][0]
        ok = (s1 == 201 and s2 == 201 and b1 == b2
              and "hold_id" not in b1
              and real == 1 and ghost == 0)
        return ok, {"existing_status": s1, "existing_body": b1,
                    "missing_status": s2, "missing_body": b2,
                    "bodies_identical": b1 == b2,
                    "holds_for_real_hit": real,
                    "holds_for_ghost": ghost}
    finally:
        C.stop()


# ------------------------------------------------------------------
# W4 — ceremony releases fenced
# ------------------------------------------------------------------
def w4_ceremony_releases_fenced(tree, side):
    """A suppression and a hold stand. In the ceremony state both
    release endpoints refuse 503 (CEREMONY_REFUSED chained) to a
    key-only supervisor, and both protections remain in place.
    (1.2.7 serves the releases.)"""
    seeded = {}

    def seed(L):
        req(L.port, "POST", "/suppressions", SUP,
            {"plate": "W4R111", "order_ref": "PO-W4"})
        s, b = req(L.port, "POST", "/holds", SUP,
                   {"scope": "case", "ref": "2027-1001"})
        seeded["hold_id"] = b.get("hold_id")

    C = _ceremony_boot(tree, "w4", side, seed)
    try:
        p = C.port
        s1, b1 = req(p, "POST", "/suppressions/release", SUP,
                     {"plate": "W4R111", "order_ref": "PO-W4"})
        s2, b2 = req(p, "POST", "/holds/release", SUP,
                     {"hold_id": seeded["hold_id"],
                      "authority": "case_closed",
                      "authority_ref": "W4-REL"})
        kinds = audit_kinds(C)
        sup_active = C.sql("SELECT active FROM suppressions")[0][0]
        hold_active = C.sql("SELECT active FROM holds")[0][0]
        ok = (s1 == 503 and s2 == 503
              and "CEREMONY_REFUSED" in kinds
              and sup_active == 1 and hold_active == 1)
        return ok, {"suppression_release_status": s1,
                    "hold_release_status": s2,
                    "ceremony_refused_chained":
                        "CEREMONY_REFUSED" in kinds,
                    "suppression_still_active": sup_active,
                    "hold_still_active": hold_active}
    finally:
        C.stop()


# ------------------------------------------------------------------
# W5 — G1 reactivation
# ------------------------------------------------------------------
def w5_g1_reactivation(tree, side):
    """A supervisor's listing expires and the sync sweep makes it
    inactive. A detective re-submits the same plate/case: the row
    must re-enter the supervisor queue (active=1, pending=1),
    appear in GET /hotlist/pending, and the chained
    HOTLIST_ADD_PENDING must carry effect="reactivated".
    (1.2.7 silently drops the submission.)"""
    A = Boot(tree, "w5-%s" % side).start()
    try:
        p = A.port
        past = (datetime.now(timezone.utc)
                - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        future = (datetime.now(timezone.utc)
                  + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        s, _b = req(p, "POST", "/hotlist", SUP,
                    {"plate": "W5G111", "state": "AR",
                     "category": "stolen vehicle",
                     "case": "2027-1014", "expires": past})
        listed = s
        r = A.script_run("hotlist_sync.py")
        rows = A.sql("SELECT active, pending FROM hotlist_members "
                     "WHERE plate='W5G111'")
        swept = rows[0] if rows else None
        s, _b = req(p, "POST", "/hotlist", DET,
                    {"plate": "W5G111", "state": "AR",
                     "category": "stolen vehicle",
                     "case": "2027-1014", "expires": future})
        submitted = s
        s, pb = req(p, "GET", "/hotlist/pending", SUP)
        in_queue = "W5G111" in json.dumps(pb)
        rows = A.sql("SELECT active, pending FROM hotlist_members "
                     "WHERE plate='W5G111'")
        after = rows[0] if rows else None
        effects = [pl.get("effect") for pl in
                   audit_payloads(A, "HOTLIST_ADD_PENDING")]
        ok = (listed == 201 and swept == (0, 0) and submitted == 202
              and in_queue and after == (1, 1)
              and "reactivated" in effects)
        return ok, {"listed": listed, "after_sweep": swept,
                    "sync_rc": r.returncode,
                    "resubmission_status": submitted,
                    "in_pending_queue": in_queue,
                    "row_after_resubmission": after,
                    "chain_effects": effects}
    finally:
        A.stop()


# ------------------------------------------------------------------
# runner
# ------------------------------------------------------------------
CASES_TABLE = [
    ("w1_reason_promotion", w1_reason_promotion),
    ("w1b_promotion_atomicity", w1b_promotion_atomicity),
    ("w2_ceremony_warning", w2_ceremony_warning),
    ("w3_ceremony_hold_uniform", w3_ceremony_hold_uniform),
    ("w4_ceremony_releases_fenced", w4_ceremony_releases_fenced),
    ("w5_g1_reactivation", w5_g1_reactivation),
]


def run_case(name, fn):
    try:
        test_ok, test_detail = fn(TEST_TREE, "test")
    except Exception as exc:
        test_ok, test_detail = False, {"exception": repr(exc)[:400]}
    try:
        base_ok, base_detail = fn(BASE_TREE, "base")
    except Exception as exc:
        base_ok, base_detail = False, {"exception": repr(exc)[:400]}
    ok = test_ok and not base_ok
    report(name, ok, {"baseline_127": {"ok": base_ok,
                                       "detail": base_detail},
                      "test_128": {"ok": test_ok,
                                   "detail": test_detail},
                      "discriminating": not base_ok})


def main():
    print("W battery: test=%s baseline=%s" % (TEST_TREE, BASE_TREE))
    for name, fn in CASES_TABLE:
        if ONLY and ONLY not in name:
            continue
        run_case(name, fn)
    failed = [n for n, ok in RESULTS if not ok]
    print("=" * 60)
    print("W battery: %d/%d cases pass" % (
        len(RESULTS) - len(failed), len(RESULTS)))
    if failed:
        print("FAILED: %s" % ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
