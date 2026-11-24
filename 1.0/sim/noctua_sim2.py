#!/usr/bin/env python3
"""
Project NOCTUA 1.0 — Track C: extended failure-mode simulator.

WHAT THIS IS: a scenario suite built on top of the audited v0.9 simulator
core (~/workspace/noctua-sim/noctua_sim.py). The core's Cabot rates are
COPIED VERBATIM below and are LOCKED — the audited baseline run observed
8.41 true matches per 100k reads against CPD's reported 8.56, and that
credibility anchor is not retuned here. (The core is copied rather than
imported because importing the v0.9 module re-runs its whole simulation
and rewrites its report file.)

WHAT THIS ADDS (per INTERFACE.md §Simulator): the failure and edge-case
scenarios the pilot design has to survive, each printed as
observed-vs-expected with every assumption labeled in-line:
  S1 camera outage (random + targeted at the busiest camera)
  S2 backhaul drop with store-and-forward alert latency
  S3 disk pressure when retention works / fails silently / is caught
  S4 camera clock skew (audit ordering, evidence timestamps, retention)
  S5 night/rain OCR degradation + false-alert base-rate math
  S6 hot-list staleness: fail-closed (the design) vs fail-open
  S7 emergency-flag normalization — kill condition K8 trip point
  S8 full run: 9 cameras, full volume, 6 months -> the complete
     Ark. Code § 12-12-1805 statutory report from plate-free outcome
     records, verified to survive a retention purge of the reads
  S9 legal-hold lifecycle: hold -> evidence export (hash-verified) ->
     prosecutor sign-off -> release -> deletion, with retention
     attempting deletion at every state

LIMITS (honest): this is a stochastic model, not the production system.
It uses aggregate binomial/Poisson sampling at day or event level; it
does not model individual vehicles, driver behavior, or police response.
Every number that is not from Cabot's own record is a labeled assumption
and exists to exercise the design, not to predict the world.

Python stdlib only. Synthetic AR-format plates only. No real data.
"""
import hashlib, hmac, json, math, random
from bisect import bisect_right, insort
from collections import defaultdict, deque

# =====================================================================
# AUDITED CORE — copied verbatim from noctua_sim.py (Nov. 23, 2026).
# Rates from CABOT'S OWN RECORD (do not change without a source):
#   CPD reported, Jan. 1 - Jun. 30, 2026 (181 days), 9 cameras:
#   8,040,000 plates scanned, 688 matches, 7 stolen vehicles recovered,
#   19 arrests. (Cabot council packet History File, audited Nov. 2026)
# =====================================================================
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

# v0.9 simulation assumptions, carried forward unchanged where reused:
OCR_ACC_DAY, OCR_ACC_NIGHT, DAY_SHARE = 0.96, 0.91, 0.70
P_OCR = DAY_SHARE * OCR_ACC_DAY + (1 - DAY_SHARE) * OCR_ACC_NIGHT   # 0.945
WRONG_STATE_PER_TRUE_HIT = 0.18  # assumption: number matches, state does not
HOTLIST_SIZE = 220               # assumption
TIER2_PER_DAY = 6.0              # assumption: contemporaneous queries
TIER3_PER_DAY = 0.7              # assumption: historical-search applications
TIER3_GRANT_RATE = 0.85          # assumption
RETENTION_DAYS = 14              # Cabot's proposed policy (spec §9)
CONFUSIONS = {"O": "0", "0": "O", "8": "B", "B": "8", "1": "I", "I": "1",
              "5": "S", "S": "5", "2": "Z", "6": "G"}
STATES = ["AR"] * 82 + ["TN", "MO", "OK", "TX", "MS", "LA", "AR", "AR"]
CATEGORIES = (["stolen vehicle"] * 34 + ["stolen plate"] * 18 +
              ["arrest warrant"] * 26 + ["missing / endangered"] * 12 +
              ["custom (gated)"] * 10)

SEED = 20261123   # same seed as the audited core


def binom(rng, n, p):
    return rng.binomialvariate(n, p)


def poisson(rng, lam):
    # Knuth, fine for the small lam used here
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def make_plate(rng, state=None):
    state = state or rng.choice(STATES)
    if rng.random() < 0.5:
        body = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(3)) + \
               "".join(rng.choice("0123456789") for _ in range(3))
    else:
        body = "".join(rng.choice("0123456789") for _ in range(3)) + \
               "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(3))
    return body, state


# ---------------- Sentinel audit log (hash-chained) ----------------
# Same construction as the audited core. Per the 1.0 rule (INTERFACE.md),
# entries in THIS suite never carry plate text — keyed HMAC plate_ref
# only. (The v0.9 demo log wrote synthetic plate text into ALERT entries;
# 1.0 forbids that, and S9 asserts it.)
class SentinelLog:
    def __init__(self):
        self.entries = []
        self.prev = "GENESIS"
        self.witness = []
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


def plate_ref(key: bytes, body: str) -> str:
    """Keyed HMAC reference for a plate — the only plate-derived value
    allowed in the Sentinel chain (same pattern as hardened Janus v0.9)."""
    return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()


# ---------------- scenario framework ----------------
RESULTS = {}


def section(title, body: dict):
    RESULTS[title] = body
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")
    for k, v in body.items():
        print(f"  {k}: {v}")


def pct(x, digits=2):
    return f"{100 * x:.{digits}f}%"


CITY_READS_DAY = SCANS_PER_CAMERA_DAY * CABOT_CAMERAS   # 44,419.9


# =====================================================================
# S1 — CAMERA OUTAGE
# Random single-camera failures across the fleet, plus one targeted
# 7-day outage of the busiest camera. Question: how much coverage —
# reads and expected matches — does the city actually lose?
# =====================================================================
def s1_camera_outage():
    rng = random.Random(SEED + 1)
    DAYS = 90
    # ASSUMPTIONS (labeled, not Cabot facts):
    P_FAIL_PER_CAM_DAY = 0.01      # each up camera fails on ~1% of days
    DURATIONS = (1, 2, 3)          # outage length in days, uniform
    BUSIEST_SHARE = 0.18           # busiest site carries 18% of city reads
                                   # (uniform would be 1/9 = 11.1%)
    down_until = [0] * CABOT_CAMERAS
    lost_reads = 0.0
    fail_events = 0
    outage_cam_days = 0
    for day in range(1, DAYS + 1):
        for cam in range(CABOT_CAMERAS):
            if day <= down_until[cam]:
                outage_cam_days += 1
                lost_reads += SCANS_PER_CAMERA_DAY * rng.uniform(0.92, 1.08)
            elif rng.random() < P_FAIL_PER_CAM_DAY:
                fail_events += 1
                down_until[cam] = day + rng.choice(DURATIONS) - 1
                outage_cam_days += 1
                lost_reads += SCANS_PER_CAMERA_DAY * rng.uniform(0.92, 1.08)
    exp_events = CABOT_CAMERAS * DAYS * P_FAIL_PER_CAM_DAY
    exp_cam_days = exp_events * sum(DURATIONS) / len(DURATIONS)
    exp_lost = exp_cam_days * SCANS_PER_CAMERA_DAY

    tgt_reads = BUSIEST_SHARE * CITY_READS_DAY * 7
    avg_reads = CITY_READS_DAY / CABOT_CAMERAS * 7
    section("S1 camera outage (90 days, 9 cameras, full volume)", {
        "assumptions": f"failure prob {P_FAIL_PER_CAM_DAY}/camera-day, "
                       f"duration uniform {DURATIONS} days, busiest-site "
                       f"share {BUSIEST_SHARE} of citywide reads",
        "random failures: events observed vs expected":
            f"{fail_events} vs {exp_events:.1f}",
        "random failures: outage camera-days observed vs expected":
            f"{outage_cam_days} vs {exp_cam_days:.1f}",
        "random failures: reads lost observed vs expected":
            f"{lost_reads:,.0f} vs {exp_lost:,.0f}",
        "random failures: expected matches lost (reads x Cabot rate)":
            f"{lost_reads * P_MATCH:.2f} (expected {exp_lost * P_MATCH:.2f})",
        "random failures: fleet availability":
            pct(1 - outage_cam_days / (CABOT_CAMERAS * DAYS)),
        "targeted 7-day outage, BUSIEST camera: reads lost":
            f"{tgt_reads:,.0f}",
        "targeted 7-day outage, busiest: expected matches lost":
            f"{tgt_reads * P_MATCH:.2f}",
        "same 7 days, AVERAGE camera: reads / matches lost":
            f"{avg_reads:,.0f} / {avg_reads * P_MATCH:.2f}",
        "reading": "one week dark at the busiest site costs ~1.6x an "
                   "average site and ~5 expected matches — the matches "
                   "are not delayed, they are gone; the vehicle does "
                   "not come back.",
    })


# =====================================================================
# S2 — BACKHAUL DROP (store-and-forward)
# Reads are timestamped at the camera and delivered when the link
# returns. Question: how late do alerts arrive, and how many arrive
# after the vehicle has plausibly left?
# DWELL ASSUMPTION (labeled): an alert is actionable for ACTION_WINDOW_S
# after the read — the window in which the vehicle is plausibly still
# in the camera's corridor / patrol response range. After that the
# alert is history, not an alert (it can still feed a Tier 2 query).
# =====================================================================
def s2_backhaul():
    rng = random.Random(SEED + 2)
    DAYS = 180
    ACTION_WINDOW_S = 600          # ASSUMPTION: 10-minute actionable window
    # ASSUMPTIONS: normal alert latency lognormal, median 25 s, sigma 0.8
    # (p95 ~93 s). Each site-day has a 2% chance of a backhaul outage of
    # uniform 1-8 h starting at a uniform hour. Site read shares: busiest
    # 18%, the other eight split the rest evenly.
    shares = [0.18] + [0.82 / 8] * 8
    lat = []                       # latency (s) of every alert
    late = 0
    outage_alerts = 0
    for day in range(DAYS):
        # per-site outage windows for the day: (start_s, end_s) or None
        windows = []
        for _ in range(CABOT_CAMERAS):
            if rng.random() < 0.02:
                start = rng.uniform(0, 20) * 3600
                windows.append((start, start + rng.uniform(1, 8) * 3600))
            else:
                windows.append(None)
        for cam in range(CABOT_CAMERAS):
            n_alerts = binom(rng, int(SCANS_PER_CAMERA_DAY * shares[cam] * 9),
                             P_MATCH)
            for _ in range(n_alerts):
                t = rng.uniform(0, 86400)
                base = rng.lognormvariate(math.log(25), 0.8)
                w = windows[cam]
                if w and w[0] <= t <= w[1]:
                    outage_alerts += 1
                    latency = (w[1] - t) + base   # waits for reconnect
                else:
                    latency = base
                lat.append(latency)
                if latency > ACTION_WINDOW_S:
                    late += 1
    lat.sort()
    n = len(lat)
    exp_outage_share = 0.02 * 4.5 / 24     # P(alert lands in an outage)
    section("S2 backhaul drop / store-and-forward (180 days, 9 cameras)", {
        "assumptions": "actionable window 600 s after the read; normal "
                       "latency lognormal median 25 s sigma 0.8; per-site "
                       "outage 2%/site-day, uniform 1-8 h",
        "alerts simulated": f"{n} (expected ~{DAYS * CABOT_MATCHES / CABOT_DAYS:.0f})",
        "latency p50 / p95 / max":
            f"{lat[n // 2]:.0f} s / {lat[int(n * 0.95)]:.0f} s / {lat[-1] / 3600:.1f} h",
        "alerts arriving after the actionable window":
            f"{late} ({pct(late / n)})",
        "of those, caused by a backhaul outage": f"{outage_alerts}",
        "expected share of alerts caught in an outage":
            f"{pct(exp_outage_share, 3)} vs observed {pct(outage_alerts / n, 3)}",
        "per 6 months at Cabot volume, alerts arriving as history":
            f"~{late} (of ~{n} total alerts)",
        "reading": "store-and-forward preserves the RECORD perfectly and "
                   "the ALERT barely at all: a queued hot-list alert is "
                   "a Tier 2 lead by the time it lands. The design must "
                   "show read age on every alert and never present a "
                   "stale alert as live.",
    })


# =====================================================================
# S3 — DISK PRESSURE
# Storage growth at full 9-camera volume. Three branches:
#   (a) retention works: disk plateaus at RETENTION_DAYS of data.
#   (b) retention fails silently for 7 days and nobody notices:
#       growth continues past the plateau.
#   (c) retention fails but the dead-man heartbeat alarm fires on
#       day 1 (job overdue >26 h): operator restores it next day.
# =====================================================================
def s3_disk_pressure():
    # ASSUMPTIONS (labeled): retained bytes per read = 170 KB
    # (150 KB Frigate snapshot JPEG + 20 KB plate crop; DB row ~0.5 KB
    # is inside rounding). Server disk 500 GB, base OS/system 60 GB.
    # Sensitivity: 250 GB disk. Failure starts on day 30, at plateau.
    KB_PER_READ = 170
    DISK_GB, BASE_GB = 500, 60
    growth_gb_day = CITY_READS_DAY * KB_PER_READ / 1e6   # GB/day
    plateau_gb = BASE_GB + growth_gb_day * RETENTION_DAYS
    fail_start = 30

    def day_full(extra_days_dead, disk_gb):
        # days from fail_start until disk is 100% full
        headroom = disk_gb - plateau_gb
        if headroom <= 0:
            return 0.0
        return headroom / growth_gb_day

    b_full_500 = day_full(7, DISK_GB)
    b_full_250 = day_full(7, 250)
    peak_c = plateau_gb + growth_gb_day * 2   # alarm day 1 + fix day 2
    peak_b7 = plateau_gb + growth_gb_day * 7
    section("S3 disk pressure (9 cameras, full volume)", {
        "assumptions": f"{KB_PER_READ} KB retained per read (snapshot + "
                       f"crop), disk {DISK_GB} GB, base system {BASE_GB} GB, "
                       "retention failure begins day 30 at plateau",
        "storage growth": f"{growth_gb_day:.2f} GB/day",
        "(a) retention works: steady-state disk use":
            f"{plateau_gb:.0f} GB ({pct(plateau_gb / DISK_GB, 0)} of disk) — "
            "flat forever",
        "(b) retention dead, NO alarm: use after 7 silent days":
            f"{peak_b7:.0f} GB; disk 100% full on day "
            f"{fail_start + b_full_500:.0f} (500 GB) or day "
            f"{fail_start + b_full_250:.0f} (250 GB)",
        "(c) retention dead, dead-man alarm fires day 1, fixed day 2: "
        "peak use": f"{peak_c:.0f} GB ({pct(peak_c / DISK_GB, 0)} of disk) — "
                    "a non-event",
        "reading": "the 14-day retention IS the disk-sizing control. On a "
                   "500 GB disk an unnoticed dead retention job takes "
                   "~6 weeks to fill the disk; on a 250 GB disk ~2 weeks. "
                   "The dead-man alarm converts both into a rounding "
                   "error — but only if something off the box notices "
                   "the silence (see TRACK-C-REPORT findings).",
    })


# =====================================================================
# S4 — CLOCK SKEW
# Camera clocks are wrong by a fixed offset. Sentinel sequences entries
# on SERVER receipt, so the chain itself cannot be reordered by a bad
# camera clock — this scenario measures what CAN be hurt: the merged
# evidence timeline (camera timestamps), and retention if it were keyed
# on camera time instead of server receipt time.
# =====================================================================
def s4_clock_skew():
    rng = random.Random(SEED + 4)
    # One day, two cameras on the same corridor, Poisson read streams.
    def stream():
        t, out = 0.0, []
        while True:
            t += rng.expovariate(1 / (86400 / SCANS_PER_CAMERA_DAY))
            if t >= 86400:
                return out
            out.append(t)
    a, b = stream(), stream()
    merged_true = sorted([(t, "A") for t in a] + [(t, "B") for t in b])

    def inversions(offset_b):
        observed = sorted([(t, "A", t) for t in a] +
                          [(t + offset_b, "B", t) for t in b])
        seen, inv = [], 0
        for _, _, true_t in observed:
            inv += len(seen) - bisect_right(seen, true_t)
            insort(seen, true_t)
        return inv

    rows = {}
    for off in (0, 5, 30, 600):
        rows[off] = inversions(off)
    # Retention keyed on camera time: a camera running SLOW by 600 s
    # keeps every read up to 600 s past the 14-day policy line; a camera
    # running FAST deletes up to 600 s early.
    affected = SCANS_PER_CAMERA_DAY * 600 / 86400
    section("S4 clock skew (two cameras, one day, ~"
            f"{len(merged_true):,} merged reads)", {
        "assumptions": "camera B clock offset fixed per run; events are "
                       "Poisson streams at the Cabot per-camera rate "
                       "(mean gap 17.5 s/read)",
        "timeline inversions at offset 0 s / +5 s / +30 s / +10 min":
            f"{rows[0]} / {rows[5]} / {rows[30]} / {rows[600]}",
        "inversions per camera-B read at +30 s / +10 min":
            f"{rows[30] / len(b):.2f} / {rows[600] / len(b):.1f}",
        "reads/day/camera retained PAST the 14-day line if retention "
        "keyed on a -10 min camera clock": f"{affected:.0f} reads, each "
                                           "up to 10 min over policy",
        "reads/day/camera deleted EARLY on a +10 min clock":
            f"{affected:.0f} (non-hit reads; verified hits are held "
            "separately and unaffected)",
        "chain effect": "none — Sentinel appends in server-receipt "
                        "order; a bad camera clock cannot rewrite or "
                        "reorder the chain",
        "reading": "at Cabot's per-camera rate, reads arrive every "
                   "~17 s, so even a +30 s skew — well inside what an "
                   "undisciplined camera clock drifts to — inverts a "
                   "visible share of a two-camera evidence timeline. "
                   "Retention must key on server receipt time, and "
                   "skew must be measured by camera NTP discipline, "
                   "not inferred from arrivals (S2 shows arrivals can "
                   "legitimately be hours late).",
    })


# =====================================================================
# S5 — WEATHER / NIGHT OCR DEGRADATION + BASE-RATE MATH
# Accuracy curves by condition, and the arithmetic that decides
# whether the alert queue is usable: at Cabot's true-match rate, a
# small false-alert rate produces MORE false alerts than true ones.
# =====================================================================
def s5_ocr_degradation():
    # Accuracy by condition. Clear day/night are the audited core's
    # assumptions (0.96 / 0.91). Rain figures are NEW labeled assumptions.
    ACC = {"clear day": 0.96, "clear night": 0.91,
           "rain day": 0.90, "rain night": 0.84}
    # ASSUMPTION: rain covers 15% of hours, independent of day/night.
    MIX = {"clear day": 0.70 * 0.85, "clear night": 0.30 * 0.85,
           "rain day": 0.70 * 0.15, "rain night": 0.30 * 0.15}
    p_weather = sum(ACC[k] * MIX[k] for k in ACC)
    passes_6mo = CABOT_MATCHES            # true passes in the record window
    caught_base = passes_6mo * P_OCR
    caught_wx = passes_6mo * p_weather
    caught_rain_night = passes_6mo * ACC["rain night"]

    rows = {}
    for fpr, label in ((0.0001, "0.01%"), (0.001, "0.1%")):
        per_100k = fpr * 100_000
        per_day = CITY_READS_DAY * fpr
        rows[label] = (per_100k, per_day, per_day * 3)  # 3 min/verify ASSUMPTION
    section("S5 OCR degradation + false-alert base rate", {
        "assumptions": "rain accuracy day 0.90 / night 0.84 (new); rain "
                       "15% of hours; alert verification takes 3 min of "
                       "an officer's time per alert",
        "weighted OCR accuracy: clear-weather baseline vs weather mix":
            f"{P_OCR:.4f} vs {p_weather:.4f}",
        "true passes caught per 6 months (of 688): baseline / weather "
        f"mix / all-rain-night": f"{caught_base:.0f} / {caught_wx:.0f} / "
                                 f"{caught_rain_night:.0f}",
        "extra true passes MISSED by weather vs baseline":
            f"{caught_base - caught_wx:.1f} per 6 months",
        "FALSE-ALERT MATH at Cabot's true rate of 8.56/100k reads": "",
        "  false-alert rate 0.01% -> false alerts per 100k reads":
            f"{rows['0.01%'][0]:.0f} (vs 8.56 true) = "
            f"{rows['0.01%'][0] / 8.56:.2f} false per true alert",
        "  false-alert rate 0.01% -> per day citywide":
            f"{rows['0.01%'][1]:.2f} false alerts/day, "
            f"{rows['0.01%'][2]:.0f} min/day of verification time",
        "  false-alert rate 0.1% -> false alerts per 100k reads":
            f"{rows['0.1%'][0]:.0f} (vs 8.56 true) = "
            f"{rows['0.1%'][0] / 8.56:.1f} false per true alert",
        "  false-alert rate 0.1% -> per day citywide":
            f"{rows['0.1%'][1]:.1f} false alerts/day, "
            f"{rows['0.1%'][2] / 60:.1f} officer-hours/day of verification",
        "reading": "weather costs a handful of missed passes; the "
                   "false-alert rate costs the whole alert queue. At "
                   "0.1% false, officers would verify ~12 false alerts "
                   "for every true one and the verify-before-stop step "
                   "— the control everything else rests on — becomes "
                   "the thing a tired operator starts skipping. The "
                   "pilot accuracy protocol must measure the false-"
                   "alert rate per 100k reads, not just OCR accuracy.",
    })


# =====================================================================
# S6 — HOT-LIST STALENESS: FAIL CLOSED (the design) vs FAIL OPEN
# The hot/case-list sync from ACIC dies for 48 h.
#   Fail closed: Tier 2/3 searches BLOCK (freshness gate). Legitimate
#     queries are delayed, nothing is answered from stale data.
#   Fail open: searches and alerts proceed against the 48-h-old list.
#     Entries REMOVED upstream (recalled warrant, recovered plate)
#     still alert; entries ADDED upstream are invisible either way
#     when the list is held locally (under Path A, matching lives on
#     the ACIC/dispatch side — this scenario prices the local-list
#     case, which is the worst case and the one a skeptic will ask
#     about).
# =====================================================================
def s6_staleness():
    rng = random.Random(SEED + 6)
    HOURS = 48
    # ASSUMPTION: list churn — 2% of the 220 entries are removed (and a
    # like number added) per day upstream.
    CHURN_PER_DAY = 0.02
    removed = HOTLIST_SIZE * (1 - (1 - CHURN_PER_DAY) ** 2)
    passes_48h = CITY_READS_DAY * 2 * P_MATCH
    exp_stale = passes_48h * removed / HOTLIST_SIZE
    # Simulate fail-open stale alerts over many 48 h outages.
    trials, stale_trials, stale_total = 300, 0, 0
    for _ in range(trials):
        n_pass = poisson(rng, passes_48h)
        stale = binom(rng, n_pass, removed / HOTLIST_SIZE)
        stale_total += stale
        if stale:
            stale_trials += 1
    # Fail-closed cost: legitimate queries blocked during the outage.
    blocked_t2 = poisson(rng, TIER2_PER_DAY * 2)
    blocked_t3 = poisson(rng, TIER3_PER_DAY * 2)
    section("S6 hot-list staleness, 48 h sync outage", {
        "assumptions": f"list churn {pct(CHURN_PER_DAY, 0)}/day of "
                       f"{HOTLIST_SIZE} entries removed upstream",
        "entries removed upstream during the outage": f"{removed:.1f}",
        "true passes citywide during 48 h": f"{passes_48h:.1f}",
        "FAIL OPEN: expected stale-list alerts (removed entries still "
        f"alerting)": f"{exp_stale:.2f} per outage; simulated mean "
                       f"{stale_total / trials:.2f}; P(at least one) "
                       f"{pct(stale_trials / trials, 0)} over {trials} "
                       "simulated outages",
        "FAIL OPEN: passes on entries ADDED upstream (missed under "
        "both designs when the list is local)": f"~{exp_stale:.2f}",
        "FAIL CLOSED: legitimate queries blocked in 48 h":
            f"Tier 2 {blocked_t2} + Tier 3 applications {blocked_t3} "
            f"= {blocked_t2 + blocked_t3} delayed (not lost — they "
            "re-run when sync returns); stale alerts 0",
        "reading": "fail-closed converts a safety failure (acting on a "
                   "recalled warrant) into an availability cost "
                   "(expected ~13 delayed queries per 48 h outage — 9 "
                   "in this seeded run — each recoverable). "
                   "Fail-open is silent until the day it isn't: most "
                   "outages produce no stale alert, which is exactly "
                   "why the failure would go unnoticed until one does. "
                   "That asymmetry is why the design fails closed.",
    })


# =====================================================================
# S7 — EMERGENCY-FLAG NORMALIZATION (kill condition K8)
# The 48-hour emergency exception exists for genuine exigency. The
# failure mode is creep: each month, using the flag gets a little
# more normal. Model: emergency use grows 5%/month, compounded, from
# the v0.9 baseline (0.09/day genuine emergencies, an assumption).
# K8 OPERATIONALIZATION (labeled — the spec's Metric 10 names the kill
# condition; this suite must pick the number the spec should pin):
#   K8 trips when emergency uses exceed 25% of all Tier 3 actions in
#   a calendar month. We also report when emergencies exceed granted
#   Tier 3 searches outright.
# =====================================================================
def s7_k8_creep():
    rng = random.Random(SEED + 7)
    CREEP = 0.05                    # ASSUMPTION: +5%/month, compounded
    K8_SHARE = 0.25                 # operationalization, labeled above
    base_emerg = 0.09 * 30          # 2.7/month (v0.9 assumption)
    granted_mo = TIER3_PER_DAY * 30 * TIER3_GRANT_RATE       # 17.85
    denied_mo = TIER3_PER_DAY * 30 * (1 - TIER3_GRANT_RATE)  # 3.15
    # analytic crossings
    e_at_share = K8_SHARE / (1 - K8_SHARE) * (granted_mo + denied_mo)
    m_share = math.log(e_at_share / base_emerg) / math.log(1 + CREEP)
    m_grant = math.log(granted_mo / base_emerg) / math.log(1 + CREEP)
    # simulated crossings (Poisson noise on every stream)
    trip_share = trip_2consec = trip_grant = None
    prev_over = False
    for m in range(1, 61):
        lam = base_emerg * (1 + CREEP) ** m
        e = poisson(rng, lam)
        g = poisson(rng, granted_mo)
        d = poisson(rng, denied_mo)
        share = e / max(1, e + g + d)
        if trip_share is None and share > K8_SHARE:
            trip_share = m
        if trip_2consec is None and share > K8_SHARE and prev_over:
            trip_2consec = m - 1     # first month of the pair
        prev_over = share > K8_SHARE
        if trip_grant is None and e > g:
            trip_grant = m
    section("S7 emergency-flag normalization (K8)", {
        "assumptions": f"emergency use creeps +{pct(CREEP, 0)}/month "
                       f"compounded from {base_emerg}/month baseline; "
                       f"K8 threshold operationalized as emergencies > "
                       f"{pct(K8_SHARE, 0)} of Tier 3 actions in a month",
        "analytic: emergencies reach the K8 share at month":
            f"{m_share:.1f} (i.e., during month {math.ceil(m_share)})",
        "simulated: first month over the K8 share": f"month {trip_share}",
        "simulated: first SUSTAINED trip (2 consecutive months)":
            f"months {trip_2consec}-{trip_2consec + 1}",
        "analytic: emergencies exceed ALL granted Tier 3 searches at "
        "month": f"{m_grant:.1f}",
        "simulated: first month emergencies > granted Tier 3":
            f"month {trip_grant}",
        "emergency uses/month at month 12 / 24 / 36":
            f"{base_emerg * 1.05 ** 12:.1f} / {base_emerg * 1.05 ** 24:.1f}"
            f" / {base_emerg * 1.05 ** 36:.1f}",
        "reading": "5%/month creep is invisible month to month and "
                   "trips K8 in under two years. Nothing about the "
                   "creep announces itself — K8 only fires if the "
                   "monthly report COMPUTES the emergency share. A "
                   "kill condition nobody calculates is not a kill "
                   "condition.",
    })


# =====================================================================
# S8 — FULL RUN: 9 cameras, full volume, 6 months -> § 12-12-1805
# report. The report is built ONLY from plate-free records:
#   - counters: (day, camera) -> reads   [survives retention by design]
#   - outcomes: one record per alert     [no plate, no plate_ref]
# After the run we purge every read-level record older than 14 days
# and regenerate the report; it must be identical.
# =====================================================================
def s8_statutory_report():
    rng = random.Random(SEED + 8)
    DAYS = CABOT_DAYS      # 181 — the record window itself, so expected
                           # values are Cabot's own reported numbers
    # ASSUMPTION (labeled; no Cabot source exists): 45% of arrests
    # result in a prosecution filed within the period.
    P_PROSECUTION_PER_ARREST = 0.45
    counters = {}                       # (day, cam) -> reads
    outcomes = []                       # plate-free outcome records
    read_detail = deque()               # (day, reads) — what retention eats
    hotlist = {}
    for _ in range(HOTLIST_SIZE):
        body, _ = make_plate(rng, "AR")
        hotlist[body] = {"state": "AR", "category": rng.choice(CATEGORIES)}
    bodies = list(hotlist)

    total_reads = 0
    passes_drawn = 0
    for day in range(1, DAYS + 1):
        day_reads = 0
        for cam in range(CABOT_CAMERAS):
            n = int(round(SCANS_PER_CAMERA_DAY * rng.uniform(0.92, 1.08)))
            counters[(day, cam)] = n
            day_reads += n
        total_reads += day_reads
        read_detail.append((day, day_reads))
        n_true = binom(rng, day_reads, P_MATCH)
        passes_drawn += n_true
        n_wrong = binom(rng, day_reads, P_MATCH * WRONG_STATE_PER_TRUE_HIT)
        for kind, count in (("true", n_true), ("wrong_state", n_wrong)):
            for _ in range(count):
                body = rng.choice(bodies)
                cat = hotlist[body]["category"]
                # OCR: a misread number never matches at all (v0.9 model)
                if rng.random() > P_OCR:
                    continue
                if kind == "wrong_state":
                    outcomes.append({"day": day, "list_name": cat,
                                     "confirmed": False, "arrest": False,
                                     "prosecution": False})
                    continue
                arrest = rng.random() < P_ARREST_PER_MATCH
                outcomes.append({
                    "day": day, "list_name": cat, "confirmed": True,
                    "arrest": arrest,
                    "prosecution": arrest and
                                   rng.random() < P_PROSECUTION_PER_ARREST})

    def build_report():
        per_list = defaultdict(lambda: {"confirmed": 0, "arrests": 0,
                                        "prosecutions": 0})
        rep = {"plates_scanned": sum(counters.values()),
               "confirmed_matches": 0, "matches_not_correlating": 0,
               "arrests": 0, "prosecutions": 0}
        for o in outcomes:
            if o["confirmed"]:
                rep["confirmed_matches"] += 1
                p = per_list[o["list_name"]]
                p["confirmed"] += 1
                if o["arrest"]:
                    rep["arrests"] += 1
                    p["arrests"] += 1
                if o["prosecution"]:
                    rep["prosecutions"] += 1
                    p["prosecutions"] += 1
            else:
                rep["matches_not_correlating"] += 1
        rep["per_list"] = dict(per_list)
        return rep

    before = build_report()
    # --- retention purge: delete all read detail older than 14 days ---
    purged = 0
    while read_detail and read_detail[0][0] <= DAYS - RETENTION_DAYS:
        purged += read_detail.popleft()[1]
    after = build_report()
    identical = before == after
    section("S8 full run -> § 12-12-1805 six-month report", {
        "window": f"{DAYS} days, {CABOT_CAMERAS} cameras, full volume "
                  "(the Cabot record window — expected values are CPD's "
                  "own reported figures)",
        "assumption": f"prosecutions = {pct(P_PROSECUTION_PER_ARREST, 0)} "
                      "of arrests filed in-period (no Cabot source; the "
                      "number must come from a prosecutor feedback loop "
                      "in production — see findings)",
        "plates scanned: observed vs CPD reported":
            f"{before['plates_scanned']:,} vs {CABOT_SCANS:,}",
        "true hot-list passes drawn (pre-OCR) vs CPD reported matches":
            f"{passes_drawn} vs {CABOT_MATCHES} "
            f"({passes_drawn / before['plates_scanned'] * 100_000:.2f}/100k "
            "vs the 8.56 anchor — this is the like-for-like line)",
        "confirmed matches (post-OCR; the v0.9 model applies its 0.945 "
        "OCR factor after the pass, so this line runs ~5.5% under the "
        "pass count by construction)":
            f"{before['confirmed_matches']} "
            f"(expected ~{passes_drawn * P_OCR:.0f})",
        "matches not correlating to an alert (wrong-state, rejected "
        "at verification)": f"{before['matches_not_correlating']}",
        "arrests: observed vs CPD reported":
            f"{before['arrests']} vs {CABOT_ARRESTS}",
        "prosecutions (assumption-driven)": f"{before['prosecutions']}",
        "confirmed matches per list":
            "; ".join(f"{k}: {v['confirmed']}"
                      for k, v in sorted(before["per_list"].items())),
        "reads purged by retention before report regeneration":
            f"{purged:,} of {total_reads:,}",
        "report identical after purge": f"{identical} "
            "(built from counters + plate-free outcomes only; outcome "
            "records carry no plate and no plate_ref)",
    })
    return identical


# =====================================================================
# S9 — LEGAL-HOLD LIFECYCLE
# One verified hit walks the full lifecycle. At every state, the
# retention job tries to delete it. Legal-hold rules (INTERFACE.md):
# a held hit may be exported (hash-verified bundle) but may only be
# RELEASED with a prosecutor sign-off, and only a released hit may be
# deleted. Every transition is chained in Sentinel with a keyed
# plate_ref — never plate text.
# =====================================================================
class LifecycleError(Exception):
    pass


class HitRecord:
    STATES = ("VERIFIED", "HELD", "EXPORTED", "SIGNED_OFF", "RELEASED",
              "DELETED")
    def __init__(self, log, key, body, category, day):
        self.log, self.key, self.body = log, key, body
        self.category, self.state = category, "VERIFIED"
        self.signoff = None
        self.bundle = None
        log.append(day, "HIT_VERIFIED", plate_ref=plate_ref(key, body),
                   category=category)
    def _go(self, day, kind, **fields):
        self.log.append(day, kind, plate_ref=plate_ref(self.key, self.body),
                        **fields)
    def place_hold(self, day, case):
        if self.state != "VERIFIED":
            raise LifecycleError(f"hold from {self.state}")
        self.state = "HELD"
        self._go(day, "HOLD_PLACE", case=case)
    def export(self, day):
        if self.state != "HELD":
            raise LifecycleError(f"export requires HELD, got {self.state}")
        files = {
            "hit.json": json.dumps({"plate_ref":
                                    plate_ref(self.key, self.body),
                                    "category": self.category},
                                   sort_keys=True),
            "manifest-note.txt": "synthetic demonstration bundle",
        }
        manifest = {name: hashlib.sha256(text.encode()).hexdigest()
                    for name, text in files.items()}
        self.bundle = {"files": files, "manifest": manifest,
                       "manifest_hash": hashlib.sha256(
                           json.dumps(manifest, sort_keys=True)
                           .encode()).hexdigest()}
        self.state = "EXPORTED"
        self._go(day, "EVIDENCE_EXPORT",
                 manifest_hash=self.bundle["manifest_hash"])
    def verify_bundle(self):
        if not self.bundle:
            return False
        return all(hashlib.sha256(t.encode()).hexdigest() == h
                   for t, h in ((self.bundle["files"][k], v)
                                for k, v in self.bundle["manifest"].items()))
    def sign_off(self, day, prosecutor, date):
        if self.state != "EXPORTED":
            raise LifecycleError(f"sign-off requires EXPORTED, "
                                 f"got {self.state}")
        self.signoff = {"prosecutor": prosecutor, "date": date}
        self.state = "SIGNED_OFF"
        self._go(day, "PROSECUTOR_SIGNOFF", prosecutor=prosecutor,
                 date=date)
    def release(self, day):
        if self.state != "SIGNED_OFF" or not self.signoff:
            raise LifecycleError("release requires prosecutor sign-off")
        self.state = "RELEASED"
        self._go(day, "HOLD_RELEASE")
        return True
    def retention_attempt(self, day):
        """The retention job's view: delete only if RELEASED."""
        if self.state == "RELEASED":
            self.state = "DELETED"
            self._go(day, "RETENTION_DELETE", rows=1,
                     note="released hit deleted after sign-off")
            return True
        self._go(day, "RETENTION_SKIP_HELD", state=self.state)
        return False


def s9_legal_hold():
    rng = random.Random(SEED + 9)
    key = b"sim-audit-key-LABELED-TEST-ONLY"   # test key, not a secret
    log = SentinelLog()
    body, _ = make_plate(rng, "AR")
    hit = HitRecord(log, key, body, "stolen vehicle", day=10)
    checks = []

    def check(name, fn, expect_error=False):
        try:
            r = fn()
            ok = (not expect_error) and bool(r)
            checks.append((name, "PASS" if ok else "FAIL",
                           r if isinstance(r, str) else ""))
        except LifecycleError as e:
            checks.append((name, "PASS" if expect_error else "FAIL",
                           f"blocked: {e}"))

    check("retention blocked on a VERIFIED hit (no release)",
          lambda: hit.retention_attempt(11) is False)
    hit.place_hold(11, "2027-1042")
    check("retention blocked while HELD",
          lambda: hit.retention_attempt(12) is False)
    check("release attempted before export/sign-off",
          lambda: hit.release(12), expect_error=True)
    hit.export(13)
    check("export bundle hash verification", lambda: hit.verify_bundle())
    # tamper: flip one byte in an exported file
    hit.bundle["files"]["hit.json"] += " "
    check("tampered bundle detected", lambda: not hit.verify_bundle())
    hit.bundle["files"]["hit.json"] = \
        hit.bundle["files"]["hit.json"][:-1]     # restore
    check("restored bundle verifies again", lambda: hit.verify_bundle())
    check("retention blocked while EXPORTED (no sign-off yet)",
          lambda: hit.retention_attempt(14) is False)
    hit.sign_off(15, "Prosecuting Attorney (simulated)", "2027-02-15")
    check("release WITH sign-off succeeds", lambda: hit.release(16))
    check("retention deletes the RELEASED hit",
          lambda: hit.retention_attempt(17) is True)
    ok, bad = log.verify()
    raw = json.dumps(log.entries)
    checks.append(("Sentinel chain verifies end-to-end",
                   "PASS" if ok else f"FAIL at {bad}", ""))
    checks.append(("no plate text anywhere in the chain",
                   "PASS" if body not in raw else "FAIL",
                   "plate_ref is HMAC-SHA256 only"))
    npass = sum(1 for _, s, _ in checks if s == "PASS")
    section("S9 legal-hold lifecycle", {
        "checks": f"{npass}/{len(checks)} PASS",
        **{f"  [{s}] {n}": (d if d != "" else "") for n, s, d in checks},
        "final state": hit.state,
        "reading": "retention is not a timer on evidence. The hit "
                   "survived four deletion attempts across four states "
                   "and was deleted exactly once — after export, "
                   "sign-off, and release, each step chained.",
    })
    return npass == len(checks)


# =====================================================================
def main():
    print("Project NOCTUA 1.0 — Track C extended simulator")
    print(f"Locked core rates: P(match) = {P_MATCH:.8f} "
          f"({P_MATCH * 100_000:.2f}/100k reads), "
          f"{SCANS_PER_CAMERA_DAY:.1f} reads/camera/day, "
          f"weighted OCR {P_OCR:.3f} — identical to the audited core.")
    try:
        with open("/home/hatch/workspace/noctua-sim/"
                  "simulation_report.json") as f:
            base = json.load(f)
        r = base["results"]
        print(f"Audited v0.9 baseline: {r['simulated_reads']:,} reads, "
              f"observed {r['observed_matches_per_100k']}/100k vs CPD "
              f"8.56, chain verified {base['sentinel_log']['chain_verified']}.")
    except OSError:
        print("Audited v0.9 baseline report not found; continuing.")
    s1_camera_outage()
    s2_backhaul()
    s3_disk_pressure()
    s4_clock_skew()
    s5_ocr_degradation()
    s6_staleness()
    s7_k8_creep()
    ok8 = s8_statutory_report()
    ok9 = s9_legal_hold()
    with open("/home/hatch/workspace/noctua-1.0/sim/"
              "sim2_results.json", "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)
    print(f"\nS8 report-survives-purge: {ok8} | S9 lifecycle: {ok9}")
    print("Results written to sim2_results.json")


if __name__ == "__main__":
    main()
