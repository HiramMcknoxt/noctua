# NOCTUA Demo Data — Presenter Sheet

**Everything on this page is DEMO data.** The users, keys, cases,
plates, warrants, and people are invented for demonstration. The demo
keys below are published on purpose — they are only ever valid on a
throwaway demo install seeded by `seed_demo.py`, and they must never
be used on a production system (production keys are random and issued
in person by `scripts/provision.py`).

Timestamps, audit sequence numbers, and hashes in the sample outputs
will differ on your install. The shapes, statuses, and values that
carry the point will match — every step below was executed against a
live seeded server and the outputs pasted from that run.

## Setup (5 minutes)

```bash
# terminal 1 — Janus on fresh demo paths (files need not exist yet)
NOCTUA_DB=/tmp/demo/noctua.db NOCTUA_USERS=/tmp/demo/users.json \
NOCTUA_CASES=/tmp/demo/cases.json NOCTUA_PORT=8080 \
  python3 ../janus.py

# terminal 2 — seed it
NOCTUA_DB=/tmp/demo/noctua.db NOCTUA_USERS=/tmp/demo/users.json \
NOCTUA_CASES=/tmp/demo/cases.json \
NOCTUA_JANUS_URL=http://127.0.0.1:8080 python3 seed_demo.py

export JANUS=http://localhost:8080
```

The seed loads 4,451 reads: 4,442 background reads (one day at 1/10 of
Cabot's real 44,420 reads/day, across all 9 cameras, backfilled
directly into the database with matching report counters — Janus has
no backfill API, by design) plus 9 demo-plate passes through the live
API, which produced 7 real alerts. One hit is already VERIFIED (with
an arrest), one is REJECTED (a misread), five sit PENDING.

## Demo users (all keys DEMO-ONLY)

| User | Role | Key | Used for |
|---|---|---|---|
| det.okafor | detective | `DEMO-KEY-DETECTIVE` | hot list, verify, Tier 3 requests, evidence |
| ofc.chen | patrol | `DEMO-KEY-PATROL` | Tier 2 searches |
| sgt.reyes | supervisor | `DEMO-KEY-SUPERVISOR` | approvals, emergency path, suppressions |
| capt.voss | supervisor | `DEMO-KEY-SUPERVISOR2` | the *second* key in two-key demos |
| auditor.external | auditor | `DEMO-KEY-AUDITOR` | read-only audit/report; closes post-hoc reviews |
| ingest.local | system | `DEMO-KEY-SYSTEM` | camera ingest + job heartbeats only |

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

Plus one plate that is **not** on the hot list: **VIC309**, suppressed
under a protection order (case 2027-1040) — see step (f).

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

Sentinel entry written:

```json
{"kind": "QUERY", "fields": {"user": "ofc.chen", "type": "read search",
 "tier": 2, "case": "2027-1014", "justification": "stolen vehicle recovery",
 "emergency": false}}
```

**Say:** the justification is not decoration — it is in the permanent
audit record, next to the searcher's name.

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
{"kind": "BLOCKED", "fields": {"user": "ofc.chen", "action": "search",
 "tier": 2, "case": "", "reason": "case number failed validation"}}
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

Sentinel entry: `BLOCKED` with `"case": "PATROL-7"` and
`"reason": "catch-all case numbers are banned"`.

**Say:** this is the anti-laundering rule. A "routine patrol" case
that any search can hide inside is how case gates get defeated in
real systems; here it cannot be used at all.

### (d) Tier 3 historical search — two keys or nothing

A historical search cannot be run directly at all. It is requested,
and a *different* supervisor approves it.

```bash
# 1. the detective requests (nothing is searched yet)
curl -s -X POST "$JANUS/tier3/request" \
  -H "X-Noctua-User: det.okafor" -H "X-Noctua-Key: DEMO-KEY-DETECTIVE" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "2027-1014",
       "why": "trace the stolen vehicle’s movements since Monday",
       "plate_fragment": "RST417",
       "auth_basis": "Warrant 2027-W-118 (DEMO), Judge A. Demo"}'
# → {"result": "PENDING — nothing was searched", "request_id": 1}
```

Sentinel entry: `TIER3_REQUEST` — note it carries a keyed
`"plate_ref": "pref:…"` and **never the plate text**; the audit chain
is permanent, so plate text in it would outlive every retention rule.

```bash
# 2. a supervisor asks for one too — then tries to approve her OWN
curl -s -X POST "$JANUS/tier3/request" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "2027-1014", "why": "supervisor-originated trace",
       "plate_fragment": "RST417",
       "auth_basis": "Court order 2027-CR-042 (DEMO)"}'
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
# → {"result": "EXECUTED", "request_id": 1, "results": {"reads": [ …the
#    three RST417 reads… ], "hits": [ … ]}}
```

Sentinel entries: `TIER3_APPROVE` (approver, requester, case, basis),
then a `QUERY` with `"tier": 3` and `"via_request": 1` — the search
itself is attributed to the approval, not just the request.

*(Request IDs 1 and 2 assume a fresh seed and this order; on a reused
demo they will be higher — read them from the responses.)*

### (e) Emergency Tier 3 — runs now, judged later

```bash
curl -s -X POST "$JANUS/tier3/emergency" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "2027-1023",
       "why": "missing person — exigent, time-critical",
       "plate_fragment": "MNA238",
       "auth_basis": "exigent circumstances (DEMO)"}'
# → {"result": "EXECUTED — flagged EMERGENCY, post-hoc review queued",
#    "request_id": 3, "results": {"reads": [ …MNA238 at CAM-03 and
#    CAM-05… ], "hits": [ … ]}}

curl -s "$JANUS/tier3/pending-reviews" \
  -H "X-Noctua-User: auditor.external" -H "X-Noctua-Key: DEMO-KEY-AUDITOR"
# → {"pending_reviews": [{"id": 3, "requester": "sgt.reyes",
#    "case_no": "2027-1023", "plate_fragment": "MNA238",
#    "status": "EMERGENCY", "needs_review": 1, …}]}
```

Sentinel entries: `TIER3_EMERGENCY` (with
`"review": "mandatory post-hoc review queued"`), then a `QUERY` with
`"emergency": true`.

**Say:** the emergency path is never blocked in the moment — and it
is never free. It sits in the auditor's queue until someone who is
*not* the person who used it closes it with a written finding
(`POST /tier3/review`). Try reviewing it as sgt.reyes: that is
refused too.

### (f) A suppressed (protection-order) plate

VIC309 belongs to a protected person. The plate was read twice today
at CAM-04. Watch what each role gets for the identical query:

```bash
curl -s "$JANUS/search?plate=VIC309&case=2027-1040&why=protection+order+compliance+check&tier=2" \
  -H "X-Noctua-User: ofc.chen" -H "X-Noctua-Key: DEMO-KEY-PATROL"
# → {"reads": [{"suppressed": true}, {"suppressed": true}], "hits": []}

curl -s "$JANUS/search?plate=VIC309&case=2027-1040&why=protection+order+compliance+check&tier=2" \
  -H "X-Noctua-User: sgt.reyes" -H "X-Noctua-Key: DEMO-KEY-SUPERVISOR"
# → {"reads": [{"ts": "…", "cam": "CAM-04", "plate": "VIC309",
#    "state": "AR", "marker": "SUPPRESSED — protection order"}, …],
#    "hits": []}
```

**Say:** patrol learns only that the plate is protected — no time, no
camera, nothing an abuser could use. A supervisor can work the record,
and the query is chained either way. This protection exists *before*
any registered-owner lookup feature, on purpose.

## Also try

```bash
# the statutory report — the numbers a city must publish every 6 months
curl -s "$JANUS/report" -H "X-Noctua-User: auditor.external" \
  -H "X-Noctua-Key: DEMO-KEY-AUDITOR"
# → {"plates_scanned": 4451, "confirmed_matches": 1,
#    "matches_not_corresponding": 1, "arrests": 1, "prosecutions": 0, …}

# prove the audit chain, end to end, in front of the audience
curl -s "$JANUS/audit/verify"
# → {"ok": true, "entries": …, "root": "…"}

# the hit queue the console's Hit Review screen is built on
curl -s "$JANUS/hits?status=PENDING" -H "X-Noctua-User: det.okafor" \
  -H "X-Noctua-Key: DEMO-KEY-DETECTIVE"
```

## Resetting the demo

Stop Janus, delete the demo database/config directory, restart, and
re-run `seed_demo.py`. The seeder refuses to run against a database
that already holds reads, so a reset is always a clean slate.
