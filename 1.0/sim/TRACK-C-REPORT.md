# Track C Report — NOCTUA 1.0 extended simulator

**Deliverable:** [`noctua_sim2.py`](noctua_sim2.py) in this folder (plus
`sim2_results.json`, the machine-readable results). Python stdlib only,
synthetic plates only. Run it with `python3 noctua_sim2.py` — the full
suite finishes in under a second and is fully deterministic
(seed 20261123, the audited core's seed, +1 per scenario).

**Method:** the audited v0.9 core is copied verbatim, not retuned —
P(match) = 688/8,040,000 (8.56/100k), 4,935.5 reads/camera/day, weighted
OCR 0.945. (Copied rather than imported: importing the v0.9 module
re-runs its simulation and rewrites its report file.) The suite opens by
re-reading the audited baseline (`simulation_report.json`: 333,033
reads, observed 8.41/100k vs CPD 8.56, chain verified) so every run
starts from the credibility anchor.

## Scenario results (actual outputs; full stdout in the appendix)

| # | Scenario | Verdict | Headline numbers |
|---|---|---|---|
| S1 | Camera outage | **PASS** | Random failures: 9 events vs 8.1 expected, 84,698 reads lost vs 79,956 expected, fleet availability 97.9%. Targeted 7-day outage of the busiest camera: 55,969 reads and **4.79 expected matches lost** (vs 2.96 for an average camera). |
| S2 | Backhaul drop | **PASS** | 671 alerts over 180 days; latency p50 26 s, p95 96 s, **max 5.2 h**. 2 alerts (0.30%) arrived after the 10-minute actionable window — both outage-caused; observed outage share 0.298% vs 0.375% expected. |
| S3 | Disk pressure | **PASS** | Growth 7.55 GB/day at full volume; working retention plateaus at 166 GB (33% of a 500 GB disk). Dead retention with no alarm: disk full on day 74 (500 GB) or **day 41 (250 GB)**. Dead retention with the dead-man alarm: peak 181 GB — a non-event. |
| S4 | Clock skew | **PASS** (with a design requirement — Finding 2) | Two-camera timeline inversions: 0 s → 0; +5 s → 1,456; **+30 s → 8,652 (1.75 per camera-B read)**; +10 min → 171,816 (34.7 per B read). Camera-keyed retention at ±10 min skew breaches the 14-day line both directions, ~34 reads/day/camera. Sentinel chain: unaffected (server-receipt ordering). |
| S5 | OCR degradation + base rate | **PASS** | Weather mix (rain day 0.90 / night 0.84, labeled assumptions) drops weighted OCR 0.9450 → 0.9355 and costs **6.5 extra missed true passes per 6 months** — minor. The false-alert math is not minor: at 0.01% false → 10 false/100k vs 8.56 true (1.17 false per true, 4.44/day); at **0.1% false → 100/100k, 11.7 false per true, 44.4/day, 2.2 officer-hours/day** of verification. |
| S6 | Hot-list staleness | **PASS** | 48 h sync outage, 2%/day churn assumption: 8.7 entries removed upstream. Fail-open: expected 0.30 stale alerts per outage, simulated mean 0.24, **P(≥1 stale alert) = 22%** over 300 simulated outages. Fail-closed: 9 legitimate queries blocked in the seeded run (~13 expected), all recoverable, zero stale alerts. |
| S7 | K8 emergency creep | **PASS with a caveat** (Finding 1) | +5%/month creep from 2.7/month: analytic K8 crossing (25% share operationalization) at month 19.5; simulated first trip month 15, sustained 15–16; emergencies exceed all granted Tier 3 at analytic month 38.7 / simulated 33. |
| S8 | § 12-12-1805 full run | **PASS** | 181 days, 9 cameras: 8,034,485 plates scanned (CPD: 8,040,000); 663 true passes drawn = 8.25/100k vs the 8.56 anchor (within noise, z ≈ −1.0); 625 confirmed post-OCR (expected ~627 given passes drawn); 130 non-correlating matches; 20 arrests (CPD: 19); 8 prosecutions (assumption-driven, Finding 6). **7,410,876 reads purged by retention; the regenerated report is byte-identical** — built only from counters + plate-free outcome records (no plate, no plate_ref). |
| S9 | Legal-hold lifecycle | **PASS — 11/11 checks** | Retention attempted deletion in VERIFIED, HELD, and EXPORTED states and was blocked every time; release without sign-off raised; export bundle hash verified, a 1-byte tamper was detected, restore verified; after sign-off + release the hit deleted exactly once. Chain verified end-to-end and contains **no plate text** (HMAC plate_ref only). |

**Overall: PASS** — all nine scenarios run and behave as the design
intends. The value of the suite is less in the passes than in the seven
design problems below, each of which the simulation surfaced rather than
assumed.

## Design problems the simulation exposed

These are defects or gaps in the *design/spec*, not in the simulator.
Ordered by how much they matter.

### Finding 1 — K8 is not yet a testable requirement, and a naive version false-trips
Spec v2's Metric 10 / kill condition K8 names emergency-flag
normalization but (on the record available to this track) pins no
number. S7 had to invent one (emergencies > 25% of Tier 3 actions in a
month). Worse, at Cabot-scale counts (single digits per month), Poisson
noise trips a single-month threshold well before the analytic crossing
— simulated first trip at month 15 vs the true creep crossing at 19.5 —
and could false-trip a healthy system. **Design action:** pin the K8
number in the spec, define it on a **3-month rolling share**, and have
the monthly report job compute it automatically. A kill condition
nobody calculates is not a kill condition.

### Finding 2 — Clock skew cannot be policed from the server side, and retention must key on receipt time
INTERFACE.md has the server flag camera clock skew > 5 s. S2 × S4
together show why that check is unreliable exactly when it matters:
store-and-forward makes arrivals legitimately hours late, so
arrival-vs-camera-timestamp comparison is unmeasurable during and
after any backhaul outage. Meanwhile S4 shows the stakes are real —
at Cabot's per-camera read rate (mean gap 17.5 s), a +30 s camera
clock already produces 1.75 timeline inversions per read on that
camera in a merged two-camera evidence view, and camera-keyed
retention would breach the 14-day policy line in both directions
(~34 reads/day/camera early or late). **Design actions:** (a) retention
keys on **server receipt time**, never camera time; (b) skew control
lives at the camera — NTP discipline plus a clock-offset field in the
camera heartbeat — with the server check as a secondary signal valid
only when the backhaul is healthy; (c) evidence exports should carry
both camera and server timestamps so a court sees the discrepancy
instead of discovering it.

### Finding 3 — The dead-man alarm needs an off-box witness, and the design already has one it isn't using as one
S3 branch (c) is the difference between a non-event and a full disk,
but it assumes "something notices the silence." Retention, the
checkpoint job, and `alert_check.py` all live on the same host; a host
failure silences all three together, and a cron job cannot report its
own death. The one signal that already leaves the box daily is the
**signed Sentinel checkpoint held by the Clerk/auditor**. **Design
action:** state explicitly that a *missed* daily checkpoint is itself
an alarm event on the Clerk/auditor side (a one-line procedure: if no
checkpoint by 09:00, call the System Administrator), and include
retention/checkpoint heartbeat status inside the signed checkpoint
payload so the off-box witness can see job health, not just chain
state.

### Finding 4 — Fail-closed freshness protects searches, not stops; stale alerts still look like alerts
Two halves of the same gap. (a) S6 prices the *search* side: the
freshness gate blocks Tier 2/3 during a sync outage — good. But Tier 1
alerting necessarily runs on the last synced list, so a hit raised
from a stale list reaches an officer before any gate applies. The
control that actually covers the recalled-warrant case is
verify-before-stop, so **verification must re-check list currency at
verification time**, not rely on sync freshness at read time.
(b) S2: ~0.3% of alerts (≈2 per 6 months, worst observed 5.2 h late)
arrive after the vehicle has plausibly left. **Design action:** the
console must display read age on every alert and visually demote
alerts older than the actionable window to "lead" status — otherwise
the first stale alert trains operators to discount all of them.

### Finding 5 — The pilot's binding accuracy metric is the false-alert rate, not OCR accuracy
S5 separates the two failure costs. Weather-driven OCR degradation is
a rounding error (≈6.5 extra missed passes per 6 months). A 0.1%
false-alert rate is an operational failure: 44 false alerts a day,
11.7 for every true one, 2.2 officer-hours/day spent clearing them —
and the predictable human response is to start rubber-stamping the
verify-before-stop step the whole control structure rests on.
**Design action:** the pilot accuracy protocol (spec Appendix C) and
its kill conditions should carry an explicit **false-alerts-per-100k
threshold** measured against ground truth, alongside plate-text and
jurisdiction accuracy. A system can pass an OCR-accuracy test and
still drown the queue.

### Finding 6 — The § 1805 prosecution line is a process, not a feature, and will silently read zero without one
S8 had to invent the prosecution rate (45% of arrests, labeled)
because no system data source exists — Janus cannot know what a
prosecutor filed. Track A's `/outcomes` endpoint is the right hook,
but unless the spec names an owner and a cadence for the prosecutor
feedback loop, the city will file its statutory six-month report with
a prosecution count of zero that means "never asked," not "none
occurred." **Design action:** the written policy should assign the
prosecution-feedback step to a named role with a per-period deadline
tied to the § 1805 report date.

### Finding 7 — Camera criticality is asymmetric; maintenance priority should be volume-weighted
S1: the busiest site (18% share assumption) loses ~1.6× an average
site's reads, and one dark week there costs ~4.8 expected matches —
about 0.7% of a full year's matches, from one camera, in one week.
**Design action:** spare-camera stocking, response-time targets, and
the S1-style outage metric in the monthly report should be weighted
by site volume; a uniform per-camera SLA spends the same effort
protecting 2.96 expected matches as 4.79.

## Honest limits of this suite
- Aggregate stochastic model (binomial/Poisson at day/event level). It
  does not model individual vehicles, correlated weather across sites,
  or operator behavior beyond the labeled rates.
- S8's "confirmed matches" line depends on where OCR loss is applied
  relative to CPD's reported 688 — the inherited v0.9 model applies
  OCR after the pass, so confirmed runs ~5.5% under passes by
  construction. The like-for-like anchor line is passes drawn
  (8.25/100k observed vs 8.56). Nobody should quote 625 against 688.
- Every non-Cabot number is a labeled assumption in the code, printed
  with the scenario that uses it. The rain accuracies, churn rate,
  snapshot size, dwell window, creep rate, and prosecution rate are
  the ones a skeptic should push on first — they are also the ones
  cheapest to replace with measured values during the pilot.

## Appendix — full suite output (actual run, Nov. 24, 2026)

```
Project NOCTUA 1.0 — Track C extended simulator
Locked core rates: P(match) = 0.00008557 (8.56/100k reads), 4935.5 reads/camera/day, weighted OCR 0.945 — identical to the audited core.
Audited v0.9 baseline: 333,033 reads, observed 8.41/100k vs CPD 8.56, chain verified True.

========================================================================
S1 camera outage (90 days, 9 cameras, full volume)
========================================================================
  assumptions: failure prob 0.01/camera-day, duration uniform (1, 2, 3) days, busiest-site share 0.18 of citywide reads
  random failures: events observed vs expected: 9 vs 8.1
  random failures: outage camera-days observed vs expected: 17 vs 16.2
  random failures: reads lost observed vs expected: 84,698 vs 79,956
  random failures: expected matches lost (reads x Cabot rate): 7.25 (expected 6.84)
  random failures: fleet availability: 97.90%
  targeted 7-day outage, BUSIEST camera: reads lost: 55,969
  targeted 7-day outage, busiest: expected matches lost: 4.79
  same 7 days, AVERAGE camera: reads / matches lost: 34,549 / 2.96
  reading: one week dark at the busiest site costs ~1.6x an average site and ~5 expected matches — the matches are not delayed, they are gone; the vehicle does not come back.

========================================================================
S2 backhaul drop / store-and-forward (180 days, 9 cameras)
========================================================================
  assumptions: actionable window 600 s after the read; normal latency lognormal median 25 s sigma 0.8; per-site outage 2%/site-day, uniform 1-8 h
  alerts simulated: 671 (expected ~684)
  latency p50 / p95 / max: 26 s / 96 s / 5.2 h
  alerts arriving after the actionable window: 2 (0.30%)
  of those, caused by a backhaul outage: 2
  expected share of alerts caught in an outage: 0.375% vs observed 0.298%
  per 6 months at Cabot volume, alerts arriving as history: ~2 (of ~671 total alerts)
  reading: store-and-forward preserves the RECORD perfectly and the ALERT barely at all: a queued hot-list alert is a Tier 2 lead by the time it lands. The design must show read age on every alert and never present a stale alert as live.

========================================================================
S3 disk pressure (9 cameras, full volume)
========================================================================
  assumptions: 170 KB retained per read (snapshot + crop), disk 500 GB, base system 60 GB, retention failure begins day 30 at plateau
  storage growth: 7.55 GB/day
  (a) retention works: steady-state disk use: 166 GB (33% of disk) — flat forever
  (b) retention dead, NO alarm: use after 7 silent days: 219 GB; disk 100% full on day 74 (500 GB) or day 41 (250 GB)
  (c) retention dead, dead-man alarm fires day 1, fixed day 2: peak use: 181 GB (36% of disk) — a non-event
  reading: the 14-day retention IS the disk-sizing control. On a 500 GB disk an unnoticed dead retention job takes ~6 weeks to fill the disk; on a 250 GB disk ~2 weeks. The dead-man alarm converts both into a rounding error — but only if something off the box notices the silence (see TRACK-C-REPORT findings).

========================================================================
S4 clock skew (two cameras, one day, ~9,971 merged reads)
========================================================================
  assumptions: camera B clock offset fixed per run; events are Poisson streams at the Cabot per-camera rate (mean gap 17.5 s/read)
  timeline inversions at offset 0 s / +5 s / +30 s / +10 min: 0 / 1456 / 8652 / 171816
  inversions per camera-B read at +30 s / +10 min: 1.75 / 34.7
  reads/day/camera retained PAST the 14-day line if retention keyed on a -10 min camera clock: 34 reads, each up to 10 min over policy
  reads/day/camera deleted EARLY on a +10 min clock: 34 (non-hit reads; verified hits are held separately and unaffected)
  chain effect: none — Sentinel appends in server-receipt order; a bad camera clock cannot rewrite or reorder the chain
  reading: at Cabot's per-camera rate, reads arrive every ~17 s, so even a +30 s skew — well inside what an undisciplined camera clock drifts to — inverts a visible share of a two-camera evidence timeline. Retention must key on server receipt time, and skew must be measured by camera NTP discipline, not inferred from arrivals (S2 shows arrivals can legitimately be hours late).

========================================================================
S5 OCR degradation + false-alert base rate
========================================================================
  assumptions: rain accuracy day 0.90 / night 0.84 (new); rain 15% of hours; alert verification takes 3 min of an officer's time per alert
  weighted OCR accuracy: clear-weather baseline vs weather mix: 0.9450 vs 0.9355
  true passes caught per 6 months (of 688): baseline / weather mix / all-rain-night: 650 / 644 / 578
  extra true passes MISSED by weather vs baseline: 6.5 per 6 months
  FALSE-ALERT MATH at Cabot's true rate of 8.56/100k reads: 
    false-alert rate 0.01% -> false alerts per 100k reads: 10 (vs 8.56 true) = 1.17 false per true alert
    false-alert rate 0.01% -> per day citywide: 4.44 false alerts/day, 13 min/day of verification time
    false-alert rate 0.1% -> false alerts per 100k reads: 100 (vs 8.56 true) = 11.7 false per true alert
    false-alert rate 0.1% -> per day citywide: 44.4 false alerts/day, 2.2 officer-hours/day of verification
  reading: weather costs a handful of missed passes; the false-alert rate costs the whole alert queue. At 0.1% false, officers would verify ~12 false alerts for every true one and the verify-before-stop step — the control everything else rests on — becomes the thing a tired operator starts skipping. The pilot accuracy protocol must measure the false-alert rate per 100k reads, not just OCR accuracy.

========================================================================
S6 hot-list staleness, 48 h sync outage
========================================================================
  assumptions: list churn 2%/day of 220 entries removed upstream
  entries removed upstream during the outage: 8.7
  true passes citywide during 48 h: 7.6
  FAIL OPEN: expected stale-list alerts (removed entries still alerting): 0.30 per outage; simulated mean 0.24; P(at least one) 22% over 300 simulated outages
  FAIL OPEN: passes on entries ADDED upstream (missed under both designs when the list is local): ~0.30
  FAIL CLOSED: legitimate queries blocked in 48 h: Tier 2 8 + Tier 3 applications 1 = 9 delayed (not lost — they re-run when sync returns); stale alerts 0
  reading: fail-closed converts a safety failure (acting on a recalled warrant) into an availability cost (expected ~13 delayed queries per 48 h outage — 9 in this seeded run — each recoverable). Fail-open is silent until the day it isn't: most outages produce no stale alert, which is exactly why the failure would go unnoticed until one does. That asymmetry is why the design fails closed.

========================================================================
S7 emergency-flag normalization (K8)
========================================================================
  assumptions: emergency use creeps +5%/month compounded from 2.6999999999999997/month baseline; K8 threshold operationalized as emergencies > 25% of Tier 3 actions in a month
  analytic: emergencies reach the K8 share at month: 19.5 (i.e., during month 20)
  simulated: first month over the K8 share: month 15
  simulated: first SUSTAINED trip (2 consecutive months): months 15-16
  analytic: emergencies exceed ALL granted Tier 3 searches at month: 38.7
  simulated: first month emergencies > granted Tier 3: month 33
  emergency uses/month at month 12 / 24 / 36: 4.8 / 8.7 / 15.6
  reading: 5%/month creep is invisible month to month and trips K8 in under two years. Nothing about the creep announces itself — K8 only fires if the monthly report COMPUTES the emergency share. A kill condition nobody calculates is not a kill condition.

========================================================================
S8 full run -> § 12-12-1805 six-month report
========================================================================
  window: 181 days, 9 cameras, full volume (the Cabot record window — expected values are CPD's own reported figures)
  assumption: prosecutions = 45% of arrests filed in-period (no Cabot source; the number must come from a prosecutor feedback loop in production — see findings)
  plates scanned: observed vs CPD reported: 8,034,485 vs 8,040,000
  true hot-list passes drawn (pre-OCR) vs CPD reported matches: 663 vs 688 (8.25/100k vs the 8.56 anchor — this is the like-for-like line)
  confirmed matches (post-OCR; the v0.9 model applies its 0.945 OCR factor after the pass, so this line runs ~5.5% under the pass count by construction): 625 (expected ~627)
  matches not correlating to an alert (wrong-state, rejected at verification): 130
  arrests: observed vs CPD reported: 20 vs 19
  prosecutions (assumption-driven): 8
  confirmed matches per list: arrest warrant: 160; custom (gated): 56; missing / endangered: 89; stolen plate: 103; stolen vehicle: 217
  reads purged by retention before report regeneration: 7,410,876 of 8,034,485
  report identical after purge: True (built from counters + plate-free outcomes only; outcome records carry no plate and no plate_ref)

========================================================================
S9 legal-hold lifecycle
========================================================================
  checks: 11/11 PASS
    [PASS] retention blocked on a VERIFIED hit (no release): 
    [PASS] retention blocked while HELD: 
    [PASS] release attempted before export/sign-off: blocked: release requires prosecutor sign-off
    [PASS] export bundle hash verification: 
    [PASS] tampered bundle detected: 
    [PASS] restored bundle verifies again: 
    [PASS] retention blocked while EXPORTED (no sign-off yet): 
    [PASS] release WITH sign-off succeeds: 
    [PASS] retention deletes the RELEASED hit: 
    [PASS] Sentinel chain verifies end-to-end: 
    [PASS] no plate text anywhere in the chain: plate_ref is HMAC-SHA256 only
  final state: DELETED
  reading: retention is not a timer on evidence. The hit survived four deletion attempts across four states and was deleted exactly once — after export, sign-off, and release, each step chained.

S8 report-survives-purge: True | S9 lifecycle: True
Results written to sim2_results.json
```
