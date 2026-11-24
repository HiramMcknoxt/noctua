# NOCTUA Demo Data — Presenter Sheet (Janus 1.2)

**Everything on this page is DEMO data.** The users, keys, cases,
plates, warrants, and people are invented for demonstration. The demo
keys below are published on purpose — they are only ever valid on a
throwaway demo install seeded by `seed_demo.py`, and they must never
be used on a production system (production keys are random and issued
in person by `scripts/provision.py`).

Timestamps, audit sequence numbers, and hashes in the sample outputs
will differ on your install. The shapes, statuses, and values that
carry the point will match — every step below was executed against a
live seeded 1.2 server and the outputs pasted from that run.

## Setup (5 minutes)

```bash
# terminal 1 — Janus on fresh demo paths (files need not exist yet)
NOCTUA_DB=/tmp/demo/noctua.db NOCTUA_USERS=/tmp/demo/users.json \
NOCTUA_CASES=/tmp/demo/cases.json NOCTUA_CAMERAS=/tmp/demo/cameras.json \
NOCTUA_PORT=8080 \
  python3 ../janus.py

# terminal 2 — seed it
NOCTUA_DB=/tmp/demo/noctua.db NOCTUA_USERS=/tmp/demo/users.json \
NOCTUA_CASES=/tmp/demo/cases.json NOCTUA_CAMERAS=/tmp/demo/cameras.json \
NOCTUA_JANUS_URL=http://127.0.0.1:8080 python3 seed_demo.py

export JANUS=http://localhost:8080
```

(The seed writes the users/cases/cameras config itself, including
the 1.2 camera registry — Janus refuses reads from any camera not
listed in it.)

**New in 1.2, in one breath:** every place plate data can live is in
one registry (`PLATE_DATA_STORES`) and retention purges *by the
registry*; Tier 3 results are stored as bare read/hit ids and
re-resolved live at read time, so a later suppression or a retention
run empties them honestly; checkpoints, audit reports, and rotation
schedules are Ed25519-signed (the plate-HMAC key never leaves the
box); a `chain_auditor` role can verify the chain and nothing else;
and liveness moved to an unauthenticated `GET /ping` that answers
only `{"alive": true}` — `/health` itself now requires auth.

The seed loads 4,453 reads: 4,442 background reads (one day at 1/10 of
Cabot's real 44,420 reads/day, across all 9 cameras, backfilled
directly into the database with matching report counters — Janus has
no backfill API, by design) plus 11 demo-plate passes through the live
API, which produced 9 real alerts. One hit is already VERIFIED (with
an arrest), one is REJECTED (a misread), five sit PENDING in the
normal queue and two more in the supervisor-only suppressed queue
(step (f)) — seven unresolved in all.

## Demo users (all keys DEMO-ONLY)

| User | Role | Key | Used for |
|---|---|---|---|
| det.okafor | detective | `DEMO-KEY-DETECTIVE` | hot list, verify, Tier 3 requests, evidence |
| ofc.chen | patrol | `DEMO-KEY-PATROL` | Tier 2 searches |
| sgt.reyes | supervisor | `DEMO-KEY-SUPERVISOR` | approvals, emergency path, suppressions |
| capt.voss | supervisor | `DEMO-KEY-SUPERVISOR2` | the *second* key in two-key demos |
| auditor.external | auditor | `DEMO-KEY-AUDITOR` | read-only audit/report; closes post-hoc reviews |
| ingest.local | ingest | `DEMO-KEY-INGEST` | camera ingest only — cannot read anything back |
| jobs.local | jobs | `DEMO-KEY-JOBS` | job heartbeats only — cannot read anything back |

**Say:** the two service identities are *write-only*. The account the
cameras use cannot search the database it feeds, and the account the
nightly jobs use cannot either. In 1.0 a single "system" account could
do both jobs and read; 1.1 split it and walled both halves off.

## Demo cases (all DEMO)

| Case | Subject |
|---|---|
| 2027-1001 | Burglary investigation (DEMO) |
| 2027-1014 | Stolen vehicle (DEMO) |
| 2027-1023 | Missing person (DEMO) |
| 2027-1031 | Felony warrant service (DEMO) |
| 2027-1040 | Protection order (DEMO) |
| 2027-1052 | Narcotics investigation (DEMO) |

A case number not on this list fails validation. Case numbers
containing PATROL, TEST, ADMIN, or DUTY are banned outright as
catch-alls — see step (c).

## Demo hot list (all plates synthetic, Arkansas format)

| Plate | List reason | Case |
|---|---|---|
| RST417 | Stolen vehicle | 2027-1014 |
| MNA238 | Missing person | 2027-1023 |
| WNT556 | Felony warrant | 2027-1031 |
| AMB771 | AMBER alert | 2027-1023 |
| PRT208 | Felony warrant | 2027-1031 |

Plus two suppressed plates (protection orders — step (f)): **VIC309**,
not on the hot list, and **PRT208**, which is on it *and* suppressed.

---

## The walkthrough

### (a) A Tier 2 search on a valid case returns reads

```bash
curl -s "$JANUS/search?plate=RST417&case=2027-1014&why=stolen+vehicle+recovery&tier=2" \
  -H "X-Noctua-User: ofc.chen" -H "X-Noctua-Key: DEMO-KEY-PATROL"
```

Expected (HTTP 200) — the stolen vehicle's three passes today, and
its three hit records (one already VERIFIED, two PENDING):

```json
{"reads": [{"ts": "…", "cam": "CAM-01", "plate": "RST417", "state": "AR"},
           {"ts": "…", "cam": "CAM-02", "plate": "RST417", "state": "AR"},
           {"ts": "…", "cam": "CAM-01", "plate": "RST417", "state": "AR"}],
 "hits":  [{"…": "…", "plate": "RST417", "status": "VERIFIED"}, … 2 × PENDING]}
```

Tier 2 is the *contemporaneous* tier: the search only reaches reads
received in the last 24 hours (configurable). Older reads exist in
the store, but this endpoint cannot see them — that wall is in the
SQL, not in the presentation layer.

Sentinel entry written:

```json
{"kind": "QUERY", "fields": {"user": "ofc.chen", "type": "tier2 search",
 "tier": 2, "case_hash": "7f4a…", "why_hash": "9404…",
 "plate_ref": "pref:…", "result_count": 6, "window_hours": 24}}
```

**Say:** the chain is permanent, so 1.2 chains *hashes of* the
case number and the justification (`case_hash`, `why_hash`), never
the text itself — free text in the chain could carry plate text and
outlive every retention rule. What the entry does record in the
clear is *how much came back* (`result_count`) and the keyed plate
reference. The justification is still required, still stored with
the request — in the database, not in the permanent chain.

### (b) The same search with no case number → blocked, and logged

```bash
curl -s "$JANUS/search?plate=RST417&why=stolen+vehicle+recovery&tier=2" \
  -H "X-Noctua-User: ofc.chen" -H "X-Noctua-Key: DEMO-KEY-PATROL"
```

Expected (HTTP 403):

```json
{"error": "BLOCKED: case number failed validation"}
```

Sentinel entry written — blocked attempts are audited too:

```json
{"kind": "BLOCKED", "payload": {"user": "ofc.chen", "action": "search",
 "reason": "case_invalid"}}
```

### (c) A catch-all case number → blocked

```bash
curl -s "$JANUS/search?plate=RST417&case=PATROL-7&why=routine+check&tier=2" \
  -H "X-Noctua-User: ofc.chen" -H "X-Noctua-Key: DEMO-KEY-PATROL"
```

Expected (HTTP 403):

```json
{"error": "BLOCKED: catch-all case numbers are banned"}
```

**Say:** this is the anti-laundering rule. A "routine patrol" case
that any search can hide inside is how case gates get defeated in
real systems; here it cannot be used at all — on any endpoint, because
every endpoint runs the same shared case gate.

### (d) Tier 3 historical search — two keys or nothing, results to the requester only

A historical search cannot be run directly at all. It is requested,
and a *different* supervisor approves it. Since 1.1 the request also
names the *kind* of authorization (`basis_type`: warrant /
court_order / other); the warrant's own words stay in the database
and never enter the chain.

```bash
# 1. the detective requests (nothing is searched yet)
curl -s -X POST "$JANUS/tier3/request" \
  -H "X-Noctua-User: det.okafor" -H "X-Noctua-Key: DEMO-KEY-DETECTIVE" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "2027-1014",
       "why": "trace the stolen vehicle’s movements since Monday",
       "plate_fragment": "RST417",
       "auth_basis": "Warrant 2027-W-118 (DEMO), Judge A. Demo",
       "basis_type": "warrant"}'
# → {"result": "PENDING — nothing was searched", "request_id": 1}
```

Sentinel entry: `TIER3_REQUEST` — note it carries a keyed
`"plate_ref": "pref:…"` and the coded `"basis_type": "warrant"`, and
**never the plate text**; the audit chain is permanent, so plate text
in it would outlive every retention rule.

```bash
# 2. a supervisor asks for one too — then tries to approve her OWN
curl -s -X POST "$JANUS/tier3/request" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "2027-1014", "why": "supervisor-originated trace",
       "plate_fragment": "RST417",
       "auth_basis": "Court order 2027-CR-042 (DEMO)",
       "basis_type": "court_order"}'
# → {"result": "PENDING — nothing was searched", "request_id": 2}

curl -s -X POST "$JANUS/tier3/approve" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR" \
  -H "Content-Type: application/json" -d '{"request_id": 2}'
# → HTTP 403 {"error": "BLOCKED: the two-key rule forbids approving
#    your own Tier 3 request"}   (+ a BLOCKED chain entry)

# 3. the second supervisor approves both, and the searches execute
curl -s -X POST "$JANUS/tier3/approve" \
  -H "X-Noctua-User: capt.voss" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR2" \
  -H "Content-Type: application/json" -d '{"request_id": 2}'
curl -s -X POST "$JANUS/tier3/approve" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR" \
  -H "Content-Type: application/json" -d '{"request_id": 1}'
# → {"result": "EXECUTED", "request_id": 1, "results_count": 6,
#    "results_url": "/tier3/results/1"}

# 4. the approver does NOT get the results — the requester retrieves
#    them, and the retrieval itself is chained (TIER3_RESULTS_VIEW)
curl -s "$JANUS/tier3/results/1" \
  -H "X-Noctua-User: det.okafor" -H "X-Noctua-Key: DEMO-KEY-DETECTIVE"
# → {"result": "ok", "request_id": 1, "results":
#    {"reads": [ …the three RST417 reads… ], "hits": [ … ]},
#    "results_count": 6, "stored_count": 6, "expired": false}

**Say:** new in 1.2 — nothing about those results is *stored* except
the ids of the reads and hits that matched. The response above was
re-resolved live, through today's suppression filter: suppress the
plate now and the same URL answers with a plate-free summary and
`"expired": true` instead. A Tier 3 result is no longer a permanent
plate archive with an API on top.
```

Sentinel entries: `TIER3_APPROVE` (approver, requester, case,
basis_type), then a `QUERY` with `"tier": 3`, `"result_count": 6` and
`"via_request": 1` — the search itself is attributed to the approval,
not just the request.

*(Request IDs 1 and 2 assume a fresh seed and this order; on a reused
demo they will be higher — read them from the responses.)*

### (e) Emergency Tier 3 — runs now, judged later, on a finding with substance

The emergency path requires an `auth_basis` too — exigency explains
speed, not the absence of a basis.

```bash
curl -s -X POST "$JANUS/tier3/emergency" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "2027-1023",
       "why": "missing person — exigent, time-critical",
       "plate_fragment": "MNA238",
       "auth_basis": "exigent circumstances (DEMO)",
       "basis_type": "other"}'
# → {"result": "EXECUTED — flagged EMERGENCY, post-hoc review queued",
#    "request_id": 3, "results": {"reads": [ …MNA238 at CAM-03 and
#    CAM-05… ], "hits": [ … ]}}

curl -s "$JANUS/tier3/pending-reviews" \
  -H "X-Noctua-User: auditor.external" -H "X-Noctua-Key: DEMO-KEY-AUDITOR"
# → {"pending_reviews": [{"id": 3, "requester": "sgt.reyes",
#    "case_no": "2027-1023", "status": "EMERGENCY", …}]}
```

Closing the review takes a real finding — `justified`,
`unjustified`, or `needs_followup`. A bare `"ok"` is refused with a
400, and sgt.reyes cannot review her own use:

```bash
curl -s -X POST "$JANUS/tier3/review" \
  -H "X-Noctua-User: auditor.external" -H "X-Noctua-Key: DEMO-KEY-AUDITOR" \
  -H "Content-Type: application/json" \
  -d '{"request_id": 3, "finding": "justified",
       "note": "exigency documented (DEMO)"}'
# → {"result": "REVIEWED", "request_id": 3}
```

**Say:** the emergency path is never blocked in the moment — and it
is never free. It sits in the auditor's queue until someone who is
*not* the person who used it closes it with a finding. And if a
supervisor leaves an emergency use unreviewed for more than 72 hours,
the emergency path locks *for that supervisor* until it is reviewed.

### (f) Suppressed (protection-order) plates — invisible means invisible

1.1 redesigned suppression after the round-2 review flagged the old
behavior against § 12-12-1808(b). A suppression is now placed against
the **protection order's reference**, not a case number. And a
suppressed plate is excluded from search results for **every** role —
no stub, no marker, no supervisor view. An empty result for a
suppressed plate is indistinguishable from a plate that was never
read, because anything else leaks the one fact the order exists to
protect: that the plate is in the system at all.

VIC309 belongs to a protected person. The plate was read twice today
at CAM-04. Watch what every role gets for the identical query:

```bash
curl -s "$JANUS/search?plate=VIC309&case=2027-1040&why=protection+order+compliance+check&tier=2" \
  -H "X-Noctua-User: ofc.chen" -H "X-Noctua-Key: DEMO-KEY-PATROL"
# → {"reads": [], "hits": []}

curl -s "$JANUS/search?plate=VIC309&case=2027-1040&why=protection+order+compliance+check&tier=2" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR"
# → {"reads": [], "hits": []}     ← identical. On purpose.
```

Disclosure happens only through the match workflow. PRT208 is on the
hot list *and* suppressed; its two passes today produced hits that
exist in exactly one place — the supervisor-only queue:

```bash
curl -s "$JANUS/suppressed-hits" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR"
# → {"hits": [{"id": …, "read_plate": "PRT208", "cam": "CAM-06",
#    "category": "felony warrant", "status": "PENDING",
#    "suppressed": true}, …]}

curl -s "$JANUS/suppressed-hits" \
  -H "X-Noctua-User: det.okafor" -H "X-Noctua-Key: DEMO-KEY-DETECTIVE"
# → HTTP 403 {"error": "the suppressed-hit queue is supervisor-only"}
```

Viewing the queue is itself chained (`SUPPRESSED_HITS_VIEW`). Trying
to hot-list a suppressed plate is refused and chained
(`SUPPRESSION_CONFLICT`). Releasing a suppression takes the order
reference **and a second supervisor** — the supervisor who requests
the release cannot confirm it.

**Say:** in 1.0, patrol got a `{"suppressed": true}` stub and
supervisors got the full record with a marker — which meant anyone
with a login could confirm a protected person was being tracked.
1.1's answer is stricter than the old design in both directions:
nobody learns anything from search, and the one queue that knows is
supervisor-only and audited.

## Also try

```bash
# the statutory report — the numbers a city must publish every 6 months.
# Prosecutions are reported as "not yet reported" until a disposition
# is actually on file. In 1.2 every hit carries an outcome row from
# the moment it alerts, so the coverage denominator is all 9 hits:
# one outcome has been reported (prosecution: false), eight have not.
curl -s "$JANUS/report" -H "X-Noctua-User: auditor.external" \
  -H "X-Noctua-Key: DEMO-KEY-AUDITOR"
# → {"plates_scanned": 4453,
#    "lists": {"Local agency list": {"confirmed_matches": 1,
#      "non_corresponding": 1, "unresolved": 7, "arrests": 1,
#      "prosecutions": 0, "prosecutions_reported": 1,
#      "arrests_and_prosecutions": 0}},
#    "confirmed_matches": 1, "matches_not_corresponding": 1,
#    "arrests": 1, "prosecutions": 0,
#    "prosecutions_coverage": {"reported": 1, "total": 9},
#    "unresolved": 7,
#    "tier3": {"emergency_share": …, "rolling_3mo": {"share": …,
#      "threshold": 0.25, "state": "ok|tripped"}}, …}

# prove the audit chain, end to end, in front of the audience
# (1.1: this now requires the auditor's key — it is not public)
curl -s "$JANUS/audit/verify" -H "X-Noctua-User: auditor.external" \
  -H "X-Noctua-Key: DEMO-KEY-AUDITOR"
# → {"ok": true, "entries": …}

# the hit queue the console's Hit Review screen is built on
# (suppressed hits are NOT here — see step (f))
curl -s "$JANUS/hits" -H "X-Noctua-User: det.okafor" \
  -H "X-Noctua-Key: DEMO-KEY-DETECTIVE"
```

## Resetting the demo

Stop Janus, delete the demo database/config directory, restart, and
re-run `seed_demo.py`. The seeder refuses to run against a database
that already holds reads, so a reset is always a clean slate.
