#!/usr/bin/env python3
"""
Project NOCTUA — Cabot open-source ALPR pilot simulator.

Implements the design in the Nov. 23, 2026 pilot spec:
  cameras -> OCR -> read store -> hot-list match -> Janus front door
  (tiered access, validated case numbers) -> Sentinel hash-chained
  audit log with an external witness -> retention job (14-day delete).

RATES THAT COME FROM CABOT'S OWN RECORD (do not change without a source):
  CPD reported, Jan. 1 - Jun. 30, 2026 (181 days), 9 cameras:
    8,040,000 plates scanned, 688 matches, 7 stolen vehicles recovered,
    19 arrests.  (Cabot council packet History File, audited Nov. 2026)
  Derived:
    scans/day citywide      = 8,040,000 / 181        = 44,419.9
    scans/day per camera    = 44,419.9 / 9           =  4,935.5
    match rate              = 688 / 8,040,000        =  0.00008557
                            = 8.56 matches per 100,000 reads
                            = 1 match per 11,686 reads
    matches/day citywide    = 688 / 181              =  3.80
    stolen-recovery / match = 7 / 688                =  1.02%
    arrest / match          = 19 / 688               =  2.76%

SCALING (what Corey asked for): the match *frequency* above is kept
exactly. Only the *volume* is scaled down (SCALE, default 0.25) and the
pilot runs 3 cameras instead of 9, so a 90-day pilot is ~333k simulated
reads instead of 1.33M — same hit rate, smaller pile.

EVERYTHING ELSE IS A LABELLED SIMULATION ASSUMPTION, not a Cabot fact:
  OCR accuracy (96% day / 91% night, 70/30 mix), wrong-state number-only
  matches (0.18 per true hit pass), hot-list size (220), Janus query
  demand (Tier 2 ~6/day, Tier 3 ~0.7/day, grant rate 85%), abuse-attempt
  rates, investigation hold (30 days). These exist to exercise the
  controls, and the report prints them as assumptions.

All plates are synthetic. No real plate, person, or case is used.
"""
import hashlib, json, random, sys
from collections import deque

# ---------------- Cabot record (sourced) ----------------
CABOT_SCANS = 8_040_000
CABOT_MATCHES = 688
CABOT_DAYS = 181
CABOT_CAMERAS = 9
CABOT_STOLEN_RECOVERED = 7
CABOT_ARRESTS = 19

P_MATCH = CABOT_MATCHES / CABOT_SCANS                 # 0.00008557...
SCANS_PER_CAMERA_DAY = CABOT_SCANS / CABOT_DAYS / CABOT_CAMERAS
P_STOLEN_PER_MATCH = CABOT_STOLEN_RECOVERED / CABOT_MATCHES
P_ARREST_PER_MATCH = CABOT_ARRESTS / CABOT_MATCHES

# ---------------- Simulation assumptions (labelled) ----------------
PILOT_CAMERAS = 3
PILOT_DAYS = 90
SCALE = 0.25                    # volume scale only; frequency unchanged
SEED = 20261123
RETENTION_DAYS = 14             # Cabot's proposed policy (spec §9)
INVESTIGATION_HOLD_DAYS = 30    # assumption: hit records held, then deleted+logged
OCR_ACC_DAY, OCR_ACC_NIGHT, DAY_SHARE = 0.96, 0.91, 0.70
P_OCR = DAY_SHARE * OCR_ACC_DAY + (1 - DAY_SHARE) * OCR_ACC_NIGHT   # 0.945
WRONG_STATE_PER_TRUE_HIT = 0.18  # assumption: number matches, state does not
HOTLIST_SIZE = 220               # assumption
TIER2_PER_DAY = 6.0              # assumption: contemporaneous queries
TIER3_PER_DAY = 0.7              # assumption: historical-search applications
TIER3_GRANT_RATE = 0.85          # assumption
INVALID_CASE_ATTEMPTS_PER_DAY = 0.35   # assumption: Janus must reject these
UNAUTH_TIER3_ATTEMPTS_PER_DAY = 0.12   # assumption: locked-door tests
CONFUSIONS = {"O": "0", "0": "O", "8": "B", "B": "8", "1": "I", "I": "1",
              "5": "S", "S": "5", "2": "Z", "6": "G"}
STATES = ["AR"] * 82 + ["TN", "MO", "OK", "TX", "MS", "LA", "AR", "AR"]
CATEGORIES = (["stolen vehicle"] * 34 + ["stolen plate"] * 18 +
              ["arrest warrant"] * 26 + ["missing / endangered"] * 12 +
              ["custom (gated)"] * 10)

rng = random.Random(SEED)

def binom(n, p):
    return rng.binomialvariate(n, p) if hasattr(rng, "binomialvariate") else \
        sum(1 for _ in range(n) if rng.random() < p)

def poisson(lam):
    # Knuth, fine for small lam
    import math
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1

def make_plate(state=None):
    state = state or rng.choice(STATES)
    fmt = rng.random()
    if fmt < 0.5:
        body = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(3)) + \
               "".join(rng.choice("0123456789") for _ in range(3))
    else:
        body = "".join(rng.choice("0123456789") for _ in range(3)) + \
               "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(3))
    return body, state

def ocr_read(body, state):
    """Return (read_body, read_state, correct). One-char confusion on error."""
    if rng.random() < P_OCR:
        return body, state, True
    chars = list(body)
    idxs = [i for i, c in enumerate(chars) if c in CONFUSIONS]
    if idxs:
        i = rng.choice(idxs)
        chars[i] = CONFUSIONS[chars[i]]
    return "".join(chars), state, False

# ---------------- Sentinel audit log (hash-chained, witnessed) ----------------
class SentinelLog:
    def __init__(self):
        self.entries = []
        self.prev = "GENESIS"
        self.witness = []          # (day, root_hash) published outside the system
    def append(self, day, kind, **fields):
        payload = json.dumps({"day": day, "kind": kind, **fields},
                             sort_keys=True, default=str)
        h = hashlib.sha256((self.prev + "|" + payload).encode()).hexdigest()
        self.entries.append({"seq": len(self.entries), "day": day, "kind": kind,
                             "fields": fields, "prev": self.prev, "hash": h})
        self.prev = h
        return h
    def publish_witness(self, day):
        self.witness.append({"day": day, "root_hash": self.prev})
        return self.prev
    def verify(self):
        prev = "GENESIS"
        for e in self.entries:
            payload = json.dumps({"day": e["day"], "kind": e["kind"], **e["fields"]},
                                 sort_keys=True, default=str)
            h = hashlib.sha256((prev + "|" + payload).encode()).hexdigest()
            if h != e["hash"] or e["prev"] != prev:
                return False, e["seq"]
            prev = h
        return True, None

# ---------------- Janus front door ----------------
class Janus:
    """The only query path. Enforces case validation + tier rules in code."""
    def __init__(self, log, open_cases):
        self.log = log
        self.open_cases = open_cases      # set of valid case numbers
        self.stats = {"tier1_alerts": 0, "tier2_ok": 0, "tier3_granted": 0,
                      "tier3_denied": 0, "tier3_emergency": 0,
                      "blocked_invalid_case": 0, "blocked_no_auth": 0,
                      "blocked_shared_account": 0}
    def query(self, day, user, tier, case, authorization=None, emergency=False):
        if user in ("shared", "generic", "vendor"):
            self.stats["blocked_shared_account"] += 1
            self.log.append(day, "BLOCKED", user=user, tier=tier,
                            reason="shared/generic account")
            return "BLOCKED: shared account"
        if tier in (2, 3) and case not in self.open_cases:
            self.stats["blocked_invalid_case"] += 1
            self.log.append(day, "BLOCKED", user=user, tier=tier, case=case,
                            reason="case number failed validation")
            return "BLOCKED: invalid case"
        if tier == 3 and not authorization and not emergency:
            self.stats["blocked_no_auth"] += 1
            self.log.append(day, "BLOCKED", user=user, tier=3, case=case,
                            reason="Tier 3 without judicial authorization")
            return "BLOCKED: no authorization"
        key = {1: "tier1_alerts", 2: "tier2_ok"}.get(tier)
        if tier == 3:
            key = "tier3_emergency" if emergency else "tier3_granted"
        self.stats[key] += 1
        self.log.append(day, "QUERY", user=user, tier=tier, case=case,
                        authorization=authorization, emergency=emergency)
        return "OK"

# ---------------- Build the world ----------------
hotlist = {}
for _ in range(HOTLIST_SIZE):
    body, _ = make_plate("AR")
    hotlist[body] = {"state": "AR", "category": rng.choice(CATEGORIES)}
hotlist_bodies = list(hotlist)

log = SentinelLog()
open_cases = {f"2027-{1000+i}" for i in range(400)}
janus = Janus(log, open_cases)
USERS = ["ofc.alvarez", "ofc.chen", "det.okafor", "sgt.reyes"]

tot = {"reads": 0, "ocr_correct": 0, "true_hit_passes": 0,
       "wrong_state_passes": 0, "alerts_number_match": 0,
       "missed_by_ocr": 0, "verified_hits": 0, "rejected_wrong_state": 0,
       "rejected_misread": 0, "stolen_recoveries": 0, "arrests": 0,
       "reads_deleted": 0, "hits_deleted_after_hold": 0}
hit_events = []            # sample of match records for the report
retained = deque()         # (day, count) of non-hit reads still inside 14 days
hit_holds = deque()        # (expiry_day, count) verified-hit records on hold

log.append(0, "SYSTEM", event="pilot start", cameras=PILOT_CAMERAS,
           scale=SCALE, retention_days=RETENTION_DAYS)

for day in range(1, PILOT_DAYS + 1):
    base = SCANS_PER_CAMERA_DAY * PILOT_CAMERAS
    n_reads = int(round(base * SCALE * rng.uniform(0.92, 1.08)))
    tot["reads"] += n_reads
    retained.append((day, n_reads))   # hits are a rounding-level subset

    # --- OCR accuracy across all reads (aggregate) ---
    tot["ocr_correct"] += binom(n_reads, P_OCR)

    # --- True hot-list passes and wrong-state number matches ---
    n_true = binom(n_reads, P_MATCH)
    n_wrong = binom(n_reads, P_MATCH * WRONG_STATE_PER_TRUE_HIT)
    tot["true_hit_passes"] += n_true
    tot["wrong_state_passes"] += n_wrong

    for kind, count in (("true", n_true), ("wrong_state", n_wrong)):
        for _ in range(count):
            body = rng.choice(hotlist_bodies)
            entry = hotlist[body]
            true_state = entry["state"] if kind == "true" else \
                rng.choice(["TN", "MO", "OK", "TX", "MS", "LA"])
            read_body, read_state, correct = ocr_read(body, true_state)
            matched = (read_body == body)   # system matches on what it read
            if not matched:
                tot["missed_by_ocr"] += 1
                continue
            tot["alerts_number_match"] += 1
            janus.stats["tier1_alerts"] += 1
            # --- ASP verify-before-action: check state + characters ---
            if read_state != entry["state"]:
                tot["rejected_wrong_state"] += 1
                outcome = "REJECTED at verification: right number, wrong state"
            else:
                tot["verified_hits"] += 1
                outcome = "VERIFIED HIT"
                hit_holds.append((day + INVESTIGATION_HOLD_DAYS, 1))
                if entry["category"] == "stolen vehicle" and \
                        rng.random() < P_STOLEN_PER_MATCH / 0.34:
                    tot["stolen_recoveries"] += 1
                if rng.random() < P_ARREST_PER_MATCH:
                    tot["arrests"] += 1
            log.append(day, "ALERT", plate=read_body, state=read_state,
                       category=entry["category"], outcome=outcome)
            if len(hit_events) < 12:
                hit_events.append({"day": day, "plate": read_body,
                                   "state": read_state,
                                   "category": entry["category"],
                                   "outcome": outcome})

    # --- Janus demand: Tier 2, Tier 3, emergencies, abuse attempts ---
    for _ in range(poisson(TIER2_PER_DAY * SCALE + TIER2_PER_DAY * (1 - SCALE))):
        janus.query(day, rng.choice(USERS), 2, rng.choice(sorted(open_cases)))
    for _ in range(poisson(TIER3_PER_DAY)):
        case = rng.choice(sorted(open_cases))
        if rng.random() < TIER3_GRANT_RATE:
            janus.query(day, rng.choice(USERS), 3, case,
                        authorization=f"WO-2027-{day:03d}")
        else:
            janus.stats["tier3_denied"] += 1
            log.append(day, "TIER3_DENIED", case=case,
                       note="application denied; logged; no search ran")
    for _ in range(poisson(0.09)):  # rare genuine emergency (assumption)
        janus.query(day, rng.choice(USERS), 3, rng.choice(sorted(open_cases)),
                    emergency=True)
    for _ in range(poisson(INVALID_CASE_ATTEMPTS_PER_DAY)):
        janus.query(day, rng.choice(USERS), 2, f"BOGUS-{rng.randint(1,9999)}")
    for _ in range(poisson(UNAUTH_TIER3_ATTEMPTS_PER_DAY)):
        janus.query(day, rng.choice(USERS), 3, rng.choice(sorted(open_cases)))
    if day % 17 == 0:   # someone tries the old shared login, twice in 90 days-ish
        janus.query(day, "shared", 2, rng.choice(sorted(open_cases)))

    # --- Retention job: hard-delete non-hit reads past 14 days ---
    deleted = 0
    while retained and retained[0][0] <= day - RETENTION_DAYS:
        deleted += retained.popleft()[1]
    if deleted:
        tot["reads_deleted"] += deleted
        log.append(day, "RETENTION_DELETE", rows=deleted,
                   oldest_remaining_day=retained[0][0] if retained else day)
    while hit_holds and hit_holds[0][0] <= day:
        hit_holds.popleft()
        tot["hits_deleted_after_hold"] += 1
        log.append(day, "HIT_HOLD_DELETE", rows=1,
                   note="investigation hold ended; deletion logged (ASP 6(e) pattern)")

    # --- Sentinel witness: weekly root-hash publication ---
    if day % 7 == 0:
        root = log.publish_witness(day)
        log.append(day, "WITNESS", root_hash=root, witness="City Clerk + public repo")

ok, bad = log.verify()
remaining = sum(c for _, c in retained)
expected_matches = tot["reads"] * P_MATCH

report = {
    "simulation": "Project NOCTUA — 90-day, 3-camera pilot, volume scale "
                  f"{SCALE} (frequency unscaled)",
    "seed": SEED,
    "cabot_record_rates": {
        "scans_per_camera_day": round(SCANS_PER_CAMERA_DAY, 1),
        "match_rate_per_100k_reads": round(P_MATCH * 100_000, 2),
        "one_match_per_reads": round(1 / P_MATCH),
        "matches_per_day_citywide_9cam": round(CABOT_MATCHES / CABOT_DAYS, 2),
        "expected_matches_per_day_pilot_3cam": round(
            SCANS_PER_CAMERA_DAY * PILOT_CAMERAS * P_MATCH, 3)},
    "results": {
        "simulated_reads": tot["reads"],
        "full_scale_equivalent_reads": int(tot["reads"] / SCALE),
        "ocr_accuracy_observed": round(tot["ocr_correct"] / tot["reads"], 4),
        "true_hotlist_passes": tot["true_hit_passes"],
        "expected_matches_at_cabot_rate": round(expected_matches, 1),
        "alerts_raised": tot["alerts_number_match"],
        "missed_by_ocr_misread": tot["missed_by_ocr"],
        "verified_hits": tot["verified_hits"],
        "rejected_wrong_state": tot["rejected_wrong_state"],
        "observed_matches_per_100k": round(
            tot["true_hit_passes"] / tot["reads"] * 100_000, 2),
        "stolen_recoveries_modelled": tot["stolen_recoveries"],
        "arrests_modelled": tot["arrests"],
        "reads_deleted_by_retention": tot["reads_deleted"],
        "reads_still_inside_14d_window": remaining,
        "hit_records_deleted_after_hold": tot["hits_deleted_after_hold"],
        "hit_records_still_on_hold": len(hit_holds)},
    "janus_front_door": janus.stats,
    "sentinel_log": {
        "entries": len(log.entries),
        "witness_publications": len(log.witness),
        "chain_verified": ok, "first_bad_entry": bad,
        "final_root_hash": log.prev[:16] + "..."},
    "sample_hit_events": hit_events,
    "assumptions_not_cabot_facts": {
        "ocr_accuracy_weighted": P_OCR, "wrong_state_per_true_hit":
        WRONG_STATE_PER_TRUE_HIT, "hotlist_size": HOTLIST_SIZE,
        "tier2_per_day": TIER2_PER_DAY, "tier3_per_day": TIER3_PER_DAY,
        "tier3_grant_rate": TIER3_GRANT_RATE,
        "investigation_hold_days": INVESTIGATION_HOLD_DAYS},
}
print(json.dumps(report, indent=2))
with open("simulation_report.json", "w") as f:
    json.dump(report, f, indent=2)
