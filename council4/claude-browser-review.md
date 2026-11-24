# NOCTUA 1.2 — Round 4 hostile review (Claude, browser seat)

Nov 24, 2026 · Claude (browser seat) · for @Corey Spangler

**MODEL/EFFORT USED:** Opus 5.5 (model ID claude-opus-5-5), per this session's own system information. The effort level shown in the UI is not visible from inside the session; please read it off the picker when filing this. Fable was not used.

## Verdict: NOT CONVERGED

1.2 fixes most of what round 3 asked for, and the registry spine is real. But this session could run code, and I reproduced **38 defects at runtime** against the attached files, with 2 positive controls holding. The builders' suite catches none of them.

Five block any live-data deployment:

1. **Suppression stops at an ingest-time stamp.** Hits made before a protection order stay in /hits, in Tier 3 results, and open to detective verify and export, with plate, camera and time (R02).
2. **Upgrading a 1.1 database voids every existing suppression** at ingest, hot-list add and release, silently (R24).
3. **One detective can keep any hit past 150 days** with a junk hold review date or an unconfirmed disposition, while /health stays green (R03, \[both\]).
4. **Hot-list removal says “membership deactivated” and removes nothing**, so a recovered car keeps alerting (R11).
5. **The two-key Tier 3 approver can't see what they approve**: no fragment, case, justification or warrant reaches them (R17).

For the Compact, two more block activation. A partner sending `tier: 1` gets the full-history Tier 3 scope (R01). On a million-entry chain, the partner-held chain\_auditor credential holds the global lock long enough to delay each ingest by 5–7 seconds (R15).

My one forced change is a single live disclosure gate. It is the third part of round 3's forced change, the part 1.2 never built (section C).

## How I worked

Unlike round 3, this session could execute code, so findings marked (runtime) were reproduced on live scratch instances of the attached files. Nothing was edited.

- **Tree.** I rebuilt `janus12/` from the attachments; line counts match the uploads.
- **Builders' suite.** 244 of 246 pass here. The two failures are the demo checks: `demo/seed_demo.py` was not attached. That matches the orchestrator's 246/246.
- **My harness.** `round4_attacks.py` plus `janus_wrapper.py` (attached), 40 checks: 38 defects CONFIRMED, 2 positive controls HOLD, 0 not reproduced. A clean full run took 1 min 49 s.
- **Fault injection.** The wrapper imports `janus.py` unmodified and patches one function in memory (R18, R22, R41).
- **Upgrade test.** I fetched the published 1.1 `janus.py` and `sentinel.py`, ran 1.1 to build a real database, then booted 1.2 on it (R24).
- **Tags.** \[claim\] = against NOCTUA's own claims; \[statute\] = against Ark. Code §§ 12-12-1801–1808; \[both\]. R-numbers point to the harness transcript. (static) = read from code, not executed.
- **Line cites** are per file, as the files will be published under `1.2/`.

**Proof of reading**

| File | Lines | Read | Two functions |
| --- | --- | --- | --- |
| janus.py | 3,935 | full | `run_search()` 847, `_share_query()` 3122 |
| sentinel.py | 712 | full | `_sanitize()` 401, `verify_detached()` 445 |
| scripts/retention.py | 324 | full | `purge_store()` 103, `prune_backup_sets()` 188 |
| scripts/backup.py | 248 | full | `config_paths()` 89, `heartbeat()` 100 |
| scripts/restore.py | 261 | full | `_find_audit_key()` 78, `main()` 88 |
| scripts/checkpoint.py | 122 | full | `heartbeat()` 47, `main()` 74 |
| scripts/compact.py | 273 | full | `recompute()` 94, `main()` 122 |
| scripts/rotation.py | 223 | full | `permute()` 67, `build_schedule()` 88 |
| scripts/sentinel\_audit.py | 371 | full | `registry_checks_db()` 92, `audit_url()` 164 |
| scripts/frigate\_bridge.py | 260 | full | `extract()` 99, `forward()` 145 |
| scripts/hotlist\_sync.py | 108 | full | `heartbeat()` 48, `main()` 66 |
| scripts/provision.py | 134 | full | `issue_key()` 71, `main()` 79 |
| scripts/alert\_check.py | 134 | full | `notify()` 47, `main()` 72 |
| scripts/publish\_witness.sh | 101 | full | `witness_heartbeat()` 44, `fail()` 65 |
| tests/run\_tests.py | 1,841 | full | `suite_schema()` 1086, `suite_compact()` 1428 |
| TRACK-12-REPORT, COMPACT.md, SYNTHESIS, BRIEF, my round-3 review | — | full | (prose) |

## A. My round-3 findings, re-verified against 1.2

Most janus.py items are FIXED. What remains clusters where round 3 found it: suppression scope, the outside anchor, and backups. Cites are janus.py unless a file is named.

**My six round-2 items, as round 3 left them**

| # | Round-3 residual | 1.2 verdict | Evidence |
| --- | --- | --- | --- |
| 1 | Negative Content-Length passes the 1 MB cap, pre-auth | NOT FIXED | 1383–1391; bridge 209–213. R26: CL `-1` with 5 MB → 401 after reading it all; honest CL → 413 |
| 2 | “Confirm” recorded as REJECTED | FIXED | 1775 |
| 3 | Non-numeric tier crashes | FIXED | 3722–3726 |
| 4 | Wrong or missing audit key | FIXED in Janus; FIXED-BUT-WRONG overall | Fingerprint 559–582, refuse-to-start 3911–3916. Scripts never check it (R16). The probe error still mints a key file before locking (226–243), now harmless |
| 5 | /tier3/pending shows everyone everything | FIXED, then overcorrected | Own-requests filter 3529–3541; approvers now see only hashes (R17) |
| 6 | Review closes on “ok” | Enum FIXED; note still optional | 2342–2346; 2368 |

**Round-3 findings my seat raised or shared**

| Finding | 1.2 verdict | Evidence |
| --- | --- | --- |
| Tier 2 window: env with no ceiling, unrecorded | FIXED | 173–177; SYSTEM entry 3922–3930 |
| Tier 2 window runs on receipt time | NOT FIXED | 864; `ts = now_iso()` 1617 |
| Tier 2 accepts 3-character substrings | NOT FIXED | 818 (my round-2 condition; never an S-item) |
| Refusals not chained | PARTLY FIXED | Still unchained: /lists 1501–1503, /outcomes 1522–1524, /verify role 1771–1773, Tier 3 results 3584–3587 |
| Suppression keyed on state | FIXED for fresh data | Suite; an upgraded database breaks it (R24) |
| Formatting variants (“VIC 309”) | FIXED for fresh data; NOT FIXED for migrated rows | 1585; R24 |
| Wrong key voids every suppression | FIXED | Fingerprint 559–582 |
| Search drops suppressed rows after the LIMIT | FIXED | 842–844, 866–874 |
| /verify and export route around the queue | FIXED-BUT-WRONG | Only for hits stamped at ingest (1796, 2408); hits made before the order go through (R02) |
| ALERT carries the camera for suppressed hits | NOT FIXED | 1682; now read by partners' chain\_auditor (194), no longer by detectives |
| /stats shows suppressed\_pending to detectives | NOT FIXED | 1243; R27 |
| Hot-list refusal reveals a protection order | NOT FIXED | 1731–1740; R27 |
| Re-export orphans the old bundle | FIXED | 2479–2514 |
| Released bundles never destroyed or flagged | FIXED | 2567–2573, 967–973; retention 222 |
| Custody excerpt type drift; HOLD without hit | FIXED | 1142; 1858–1863 |
| Evidence not backed up | FIXED | backup 165–175 (but see R06) |
| publish\_witness dies on checkpoint output | FIXED | checkpoint stdout is one line; suite and R45 |
| Witness heartbeat before publication | FIXED-BUT-WRONG | A same-host plain folder counts as published (publish\_witness 85–100; R45) |
| Restore rolls the anchor back | FIXED | restore never overwrites the live file; suite |
| Root and count read in two statements | FIXED | checkpoint 83–85 |
| Anchor fails open on a missing file | FIXED-BUT-WRONG | Still open if Janus never booted with a checkpoint (634–638; R09) |
| Anchor checks newest only, no signatures | FIXED | 640–662 |
| Anchor runs only at boot | NOT FIXED | 691–699, called once at 724 |
| /health unauthenticated | FIXED | 3388–3393 |
| verify() under the global lock | FIXED-BUT-WRONG | Cached ≤60 s, but a miss computes inside do\_GET's lock; /audit/verify uncached (3407–3408; R15) |
| Camera health from stored reads | FIXED, does not alert | Registry-based (926–956) but excluded from `ok` (3827–3829; R34) |
| hotlist\_sync never shipped | FIXED | scripts/hotlist\_sync.py |
| Retention heartbeat ok with the scrub skipped | FIXED for a missing key; NOT FIXED for a wrong one | R16 |
| REPORT\_COMPILE chains no hash; free-text list names | FIXED | 2033–2035; list registry 1500–1518, 1741–1751 |
| Hold review\_by unvalidated | NOT FIXED | 1848–1850; R03 |
| Hot-list expiry optional, unbounded | NOT FIXED | 1761 |
| Ingest fabricates AR/0.95; any camera; no dedupe | FIXED | 1600–1606, 1586–1595, 1607–1616 |
| B1: our leg is a bare boolean | FIXED-BUT-WRONG | Signature verified (2794–2807) but report.agency and ts ignored; row timestamped now (2813–2818; R33) |
| B1: their leg accepts any old receipt | FIXED, opens on a bad file | Newest checkpoint + ts + signature (2858–2902); `if newest and …` (3178, 1207; R32) |
| B1: compact.py trusts self-verify | FIXED | Real recompute (compact 94–119, 206–223); unpinned by default (compact 184, 230; R30) |
| B1: sentinel\_audit's “independent” label | NOT FIXED | sentinel\_audit 207 is the target's own /audit/verify |
| B2: a partner's audit account reads data | FIXED for compact.py; NOT FIXED for sentinel\_audit | Fence 192–193, 3382–3386; sentinel\_audit URL mode needs /health, so the auditor data role (165; R31) |
| B3: shares get Tier 3 on one key | FIXED-BUT-WRONG | Tier 3 refused, tier 1 gets full scope (3152, 3227; R01). Why stored, rate limit added |
| B4: checkpoint signed with the plate key | FIXED | Ed25519, sentinel 290–364; custody and rotation gaps R06, R44 |
| B5: the seed does nothing | FIXED | R39 positive control; grinding R40 |
| B5: duty reads the wrong table, no window | FIXED-BUT-WRONG | Windows added; delinquency compares adjacent rounds (3290–3293; R21); witness filed by anyone (3002–3025; R19) |
| B6: writes commit before logging | FIXED on the data paths | R29 holds; six paths still commit first (R22) |
| B6: raw usernames and free text in the chain | PARTLY FIXED | AUTH\_FAIL hashed but unbounded (732–758; R13); free text still enters (R12); badge-style usernames still scrubbed (R25) |
| B8: no RETENTION\_DAYS ceiling | FIXED | 169–172 |
| B8: fail-closed covers only search | FIXED-BUT-WRONG | Extended, but /tier3/results missed (R18) |
| C2: Tier 3 results kept forever | FIXED | Ids only (2191–2201), nulled at class age (sentinel 199–212); live resolution misses hits (R02) |
| C2: key-file fallback, two frag\_refs, secure\_delete | FIXED | sentinel 89–100, 112–118; retention 259 |
| C2: deletes by receipt time | NOT FIXED | retention 132 |
| C3: the key travels with the data | NOT FIXED in substance | Now the Ed25519 private key travels (backup 186–193) and restore verifies against the set's own public key (restore 117–133; R06) |
| C3: tar-slip; pruning opt-in | FIXED | `filter="data"`; prune on by default. A set still holds reads up to 2× RETENTION\_DAYS old; off-box sets invisible (R42) |
| C4: bridge, provision, alert\_check | FIXED, with residuals | Bridge negative CL (R26); no username rule (R25); alert\_check inherits /health blind spots (R34) |

**My round-3 forced change**

| Part | Verdict | Evidence |
| --- | --- | --- |
| (a) Match on the normalized plate alone, in SQL before any LIMIT, at ingest, search, /hits, /share, Tier 3, export | FIXED-BUT-WRONG | Search, share and Tier 3 reads are live (842–844, 3623–3632). /hits (3444), Tier 3 hits (3641), /verify (1796) and export (2408, 2461–2466) trust an ingest-time flag (R02) |
| (b) Store the normalized plate | FIXED for new rows; NOT FIXED for migrated rows | 1585, 1627–1631; migration copies plate into plate\_raw only (496; R24) |
| (c) Boot-time key check | FIXED, by another mechanism | Fingerprint; an upgraded database enrolls whatever key its first 1.2 boot sees (570–571) |
| (d) No camera on suppressed ALERTs; suppressed counts supervisor-only | NOT FIXED | 1682; 1243 |
| Its three acceptance tests | PASS | Suite |

## B1. Blocking for any live-data deployment

Five defects block a live-data pilot. Each has a small fix, and each passes the builders' suite.

### R02 — Suppression stops at an ingest-time stamp \[claim\] (runtime)

A suppression placed after a hit exists never reaches that hit. `/suppressions` (1905–1962) does not update `hits.suppressed`. /hits (3444), Tier 3 hit resolution (3641), /verify (1796) and export (2408) all trust that stamp, and export's ±1 h reads query (2461–2466) has no suppression filter at all.

- **Run:** hot-list PRV100; three reads make hits 1–3 at CAM-03/04/05; then a supervisor suppresses it.
- A detective's GET /hits still returns all three with plate and camera; so does the auditor's. The supervisor queue holds none of them.
- Tier 2 /search returns nothing (it filters live) — the contrast. GET /tier3/results re-resolves its reads (0) but returns all three hits.
- The detective verifies hit 1 (200) and exports it (201). The bundle's reads.json lists PRV100 at CAM-03, CAM-04 and CAM-05 with times.

This is the natural order of events: a vehicle is hot-listed first (for example, reported stolen by an estranged partner) and the protection order arrives later. For HOLD\_DAYS (30 by default), every detective and auditor can read where the protected vehicle was.

**Fix:** evaluate suppression live everywhere, with the same `NOT EXISTS` predicate search uses (842–844) on `read_plate` and `entry_plate`. In SUPPRESSION\_PLACE's own transaction, set `suppressed=1` on existing hits of that plate. Filter the bundle's reads the same way.

### R24 — Upgrading a 1.1 database voids every suppression \[claim\] (runtime)

1.1 keyed suppressions by HMAC of `plate|state` (1.1 janus.py 217) and stored reads as typed (1.1 line 979). 1.2's migration (455–515) never recomputes `suppressions.plate_ref` and never normalizes `reads.plate` or `hits.read_plate`. Its comment says pre-1.2 rows were “already normalized-by-convention” (494–495); 1.1 line 979 shows they were not.

- **Run:** the published 1.1 Janus places a suppression on VIC309 and ingests “VIC 309”. I booted 1.2 on that database with the same key.
- A detective hot-lists VIC309 → 201. A fresh 1.2 install answers 403.
- The next read alerts and appears in the detective's /hits as VIC309 at CAM-04.
- Patrol's fragment search “VIC” returns the legacy “VIC 309” row.
- The supervisor's release of the order → 404 “no active suppression for that plate”.

`is_suppressed()` (835–839) checks stored refs only, so ingest flagging, hot-list conflict and release all miss. Search half-works because it compares plate text. Scope: only installs that upgrade a 1.0/1.1 database; fresh installs are unaffected.

**Fix:** at migration, recompute every suppression's ref from its stored plate, and normalize `reads.plate`, `hits.read_plate`, `hits.entry_plate` and `hotlist_members.plate`, keeping the typed text in `plate_raw`. Make `is_suppressed()` a lookup on plate text.

### R03 — One detective keeps any hit past 150 days \[both\] (runtime)

Two paths need no second key and no case. A hold's `review_by` is whatever the caller sends (1848–1850); “9999-12-31” or “never” never sorts below now, so `overdue_holds()` (959–964) never flags it. An unconfirmed disposition (2622–2664) creates an evidence row with no export and no release — exactly what retention treats as protected (retention 141–147).

- **Run:** four hits aged to 200 days. Three protected by a detective: a hold dated 9999-12-31, a hold dated “never”, an unconfirmed `no_charges` disposition. One control.
- After retention.py (exit 0), the three survive and the control is gone.
- /health: ok true, retention\_breach empty, overdue\_holds 0. The chain records `review_by` “never” verbatim.

**Statute:** § 12-12-1804(a) bars preserving captured plate data beyond 150 days. Subsection (b) allows it only during an ongoing investigation, with destruction at its conclusion. The disposition path inverts (b): recording “no charges” — the conclusion — keeps the data until someone confirms it.

§ 1805(b)(4) adds a consequence: retention beyond 150 days must follow published rules, and noncompliance is grounds to exclude the evidence. A hold that /health cannot see is retention nobody can show followed them.

**Fix:** parse `review_by` as a timestamp no later than now + 90 days, extended only by a supervisor. Guard hits only by evidence rows that have an export. Have /health name any plate-bearing row older than 150 days, whatever guards it.

### R11 — Hot-list removal reports success and removes nothing \[claim\] (runtime)

DELETE /hotlist matches state and list exactly (3342–3344), never checks the row count, chains HOTLIST\_REMOVE and answers “membership deactivated” (3345–3349). Ingest matching is state-tolerant (1645–1649), so the entry keeps matching.

- **Run:** hot-list STL100 with state AR. DELETE `{plate: STL100}` → 200 “membership deactivated”, HOTLIST\_REMOVE chained.
- GET /hotlist still lists it; the next read → ALERT.

The usual reason to remove an entry is that the car was recovered or the warrant served. A false “deactivated” keeps officers alerting on a lawful driver, while the chain says the entry is gone. Omitting `list_name` for an entry on another list fails the same way.

**Fix:** apply ingest's rule (an omitted state or list matches all), return 404 when nothing was deactivated, and chain the rows actually changed.

### R17 — The two-key approver can't see what they approve \[claim\] (runtime)

1.2 closed round 3's leak by removing the substance. /tier3/pending (3522–3547) and /tier3/reviews (3548–3562) return requester, `case_hash`, a keyed `plate_ref`, `basis_type` and dates. No endpoint returns the fragment, case number, justification or `auth_basis`. Approve selects them (2155–2158) and executes without showing them.

- **Run:** a detective requests fragment BLD12 under 2027-1023, warrant “W-77 (DEMO)”, with a stated reason.
- The supervisor's pending entry and the auditor's review entry contain none of those strings.

The second key exists to check the basis and its scope, such as a short fragment under a warrant naming one plate. As built, a supervisor approves on trust, and the post-hoc emergency review grades a justification it cannot read.

**Fix:** a supervisor- and auditor-only GET /tier3/request/\<id> returning the plaintext, chained as a view. Accountability comes from logging the read, not from hiding the request.

## B2. Blocking for Compact activation

The Compact ships with no partners registered, so these block activation, not a pilot. The first is a one-line fix with a large consequence.

### R01 — `tier: 1` gets the full Tier 3 scope \[claim\] (runtime)

/share/query accepts any integer tier from 1 to 2 (3152), then maps every value except 2 to scope “full” (3227). `true` passes too, because a Python bool is an int.

- **Run:** gate opened as the suite opens it; a 30-hour-old read HIS777 and a fresh HIS778.
- `tier: 2` → \[HIS778\]. `tier: 1` → \[HIS777, HIS778\]. `tier: true` → the same.
- SHARE\_OUT records tier 1, so the permanent record understates what left.

This contradicts S10 and COMPACT.md (“Historical (Tier 3) data never moves through the Compact”). It also widens the § 1804(d) question already routed to counsel. **Fix:** refuse anything but 2, or drop `tier` from the request entirely.

### R15 with R13 and R12 — The partner credential can freeze the service \[claim\] (runtime)

/audit/verify runs `chain.verify()` on the shared connection inside do\_GET's global lock, uncached (3407–3408). /audit clamps with `min(limit, 1000)`, so `limit=-1` returns the whole chain (3401–3402). Both are open to chain\_auditor, the credential partners hold.

- **Run:** a valid 1,000,000-entry chain (290 MB). One /audit/verify takes 2.57 s.
- Ingest latency goes from 0.002 s to a median 5.44 s and a max 7.20 s while two loops call /audit/verify.
- `/audit?limit=-1` returns 1,000,001 entries in 11.6 s.
- The bridge's forward timeout is 10 s (bridge 162); past it the read is dropped with a 502, by design no queue.

Growing the chain needs no partner. An unauthenticated client adds one permanent AUTH\_FAIL per invented username: 600 in 0.8 s, because the throttle keys on the attacker's chosen name (732–758). A patrol login added 840 KB in one request through SHARE\_BLOCKED's `agency` (3136–3146), a field the scrubber exempts (sentinel 385).

**Fix:** cache /audit/verify like /health, and compute both off the lock, incrementally from the last verified seq. Clamp `limit` to 1–1000. Give AUTH\_FAIL a global per-minute budget. Chain `rec["user"]`, never the body's agency.

### R30–R33 — Verification that defaults to trust \[claim\] (runtime)

- **R30.** compact.py verifies a checkpoint against the key the checkpoint itself carries unless `--partner-pubkey` or `--partner-fingerprint` is given (compact 184, 230). With an impostor key: no pin → exit 0 (ok); the registered fingerprint → exit 2. It could read that fingerprint from our own GET /compact/partners.
- **R31.** sentinel\_audit's URL mode starts with /health (sentinel\_audit 165), which chain\_auditor cannot read: 403, exit 1. Cross-agency use therefore needs the `auditor` data role, the very access S9 took from compact.py.
- **R32.** The receipt leg tests `if newest and …` (3178; same at 1207), so with no readable checkpoint any old receipt passes. A stale receipt → 403; one malformed line appended to the checkpoints file → 200. The leg never re-checks freshness at query time either, so a stopped checkpoint job leaves the last receipt valid indefinitely (static).
- **R33.** /compact/audit-result verifies the signature but ignores `report.agency` and `report.ts`, and timestamps the row now (2808–2818). agency-a's signed report filed for agency-z → 201; a report dated 2020-01-01 → 201. A captured signed report is a reusable, transferable pass.

**Fix:** require a pin in compact.py; give chain\_auditor a reduced /health or let sentinel\_audit skip it; block when no checkpoint is readable and when the newest is over 26 h old; require `report.agency` to match, `report.ts` within minutes, and a unique report hash.

### R19–R21 and R40 — Rotation and witness duty \[claim\] (runtime)

- **R19.** POST /compact/witness has no role check and no chain entry (3002–3025). Patrol and ingest both file attestations (201), the chain gains nothing, and status shows agency-x's witness duty as filed.
- **R20.** Publishing without a seed → 500 “name 'uuid' is not defined” (3085; nothing imports uuid, 119–133). A one-member cycle publishes a self-audit (3897–3906).
- **R21.** Delinquency compares adjacent rounds, which belong to different agencies (3290–3293). With four silent agencies, the flag names three and spares round 1's auditor. And a Janus cannot see whether X audited Y unless it is Y, so for most rounds the measure is unrelated to the duty.
- **R40.** The publisher picks the seed (Janus) or the start date (rotation.py). “agency-b audits agency-a” appears at seed-8, and on 8 of 31 January 2027 start dates. COMPACT.md's “schedule neither side controls” needs a seed nobody picks: a commit-reveal among members, or a public randomness beacon value fixed in advance.

**What holds (R39):** Janus's `build_schedule` and rotation.py agree on 300 of 300 random member sets when given sorted members and the derived seed. The suite never cross-checks them, although rotation.py line 16 says it does.

## B3. Code-critical: fix before release

None of these blocks a pilot alone, but each breaks a specific 1.2 claim and each has a small fix. All are (runtime) unless marked.

**Backups, anchor, witness and keys**

| R | Finding | Std | Evidence | Fix |
| --- | --- | --- | --- | --- |
| R06 | The backup manifest is self-certifying. The set carries the signing **private** key (backup 186–193); restore verifies against the set's own public key (restore 117–133) | \[claim\] | Planted read FAKE01 in a set, re-signed with its own key, HMAC dropped → “manifest verified … restored OK”; boot clean; /search serves FAKE01 | Verify against the live install's key or a pinned fingerprint; keep keys out of data sets (custody is the city's call) |
| R07 | The RESTORE marker is deleted even when boot is refused (702–720) | \[claim\] | Wrong env key → exit 3, marker gone; right key → no RESTORE ever chained | Remove the marker only after the RESTORE entry commits |
| R08 | Anchor acceptance is keyed to the newest checkpoint (676–687) | \[claim\] | Accept → clear; one routine checkpoint plus a restart → mismatch again | Key acceptance on the bad checkpoint set alone |
| R09 | The anchor fails open if Janus never booted while a checkpoint existed (634–638) | \[claim\] | Rewrite history, delete the checkpoints file, restart → anchor ok, chain\_ok true | Infer “a checkpoint existed” from the chain's checkpoint heartbeats, not a boot-time flag |
| R45 | A same-host plain folder counts as “witnessed” (publish\_witness 85–100) | \[claim\] | Exit 0; witness job ok, “witnessed checkpoint …” | Count only a successful push to a remote, or a sent email |
| R44 | No signing-key rotation path (643–652) | \[claim\] | Replace the key → permanent anchor mismatch | A key history with validity windows; a rotation entry signed by the old key |
| R16 | Scripts skip the key-continuity check | \[claim\] | Stale env key: retention and hotlist\_sync exit 0, refs match nothing, heartbeats ok | Compare the key's hash to `meta.audit_key_fingerprint` (read-only); refuse on mismatch |
| R42 | Off-box backups are invisible to /health (1312–1326 looks only under the DB folder); BACKUP\_RETENTION\_DAYS has no ceiling (backup 71–72) | \[both\] | A 40-day-old set in NOCTUA\_BACKUP\_DIR → breach empty; the same set locally → \["backups"\] | Check the configured folder; cap at RETENTION\_DAYS |
| R05 | HOLD\_DAYS has no ceiling and is missing from the SYSTEM entry (161, 3922–3930) | \[statute\] | HOLD\_DAYS=3650 starts; RETENTION\_DAYS=151 is refused | A ceiling of 150; record it at boot |

A backup set also holds reads up to 2× RETENTION\_DAYS old: 28 days at the default, past the cap whenever RETENTION\_DAYS exceeds 75 (static).

**Registry, chain, health and input**

| R | Finding | Std | Evidence | Fix |
| --- | --- | --- | --- | --- |
| R43 | Registry gaps, and the schema test only sees column names matching `plate\|frag\|results` (run\_tests 1099) | \[claim\]; \[statute\] if kept | Six free-text entries deleted → still passes; new table share\_log(query\_text) → passes. holds.reason keeps “VIC 309” after release, 200 days and a retention run | Register holds.reason, share\_queries.case\_ref, witness\_attestations.detail, heartbeats.detail; make the test cover every TEXT column, each registered or explicitly exempt |
| R10 | sentinel\_audit DB mode fails a healthy system forever (sentinel\_audit 112–138 checks hits unguarded and scrubbed fragments as live, 139–151 counts every destroyed bundle) | \[claim\] | Four failures (held hit, scrubbed fragment, destroyed bundle) while /health is ok and alert\_check exits 0 | Reuse Janus's breach rules |
| R22 | Commit-before-log on six paths: suspend (2923–2926), reinstate (2958–2961), rotation void (2982, 2991–2995), anchor accept (2053, 2068–2075, via the committing `_meta_set` 552–556), startup anchor (695) | \[claim\] | With the chain write failing: suspension and void committed, unlogged. /hotlist rolled back (the S11 path works) | No commit before the append; a non-committing `_meta_set` |
| R12 | Arbitrary text enters the permanent chain: SHARE\_BLOCKED.agency from any role but chain\_auditor, unscrubbed; BLOCKED.hit (1783, 2393); HOLD\_PLACE.review\_by (1857); HEARTBEAT.job (1494) | \[claim\]; \[statute\] if a plate lands there | “VIC 309 parked nightly behind 12 Oak St” in four entries, one of them 840 KB | Chain only validated ints, enums and hashes, never request values |
| R41 | The sink receives entries from rolled-back transactions (sentinel 665) | \[claim\] | A failed COMMIT leaves HOTLIST\_ADD seq 1 in the sink, not in the chain | Stream after commit |
| R18 | /tier3/results skips the stale-config fail-closed rule (3563–3667; every other data route checks it) | \[claim\] | Fail-closed: /hits 503; /tier3/results 200 with plates | One line; also covered by the forced change |
| R26 | Negative Content-Length bypasses the cap (1383–1391; bridge 209–213) | \[claim\] | CL `-1` plus 5 MB → read to EOF, then 401 | Refuse negative lengths |
| R34 | /health `ok` ignores silent cameras and overdue holds (3827–3829) | \[claim\] | ok true with never-reported cameras and a hold 30 days past review | Put overdue holds (at least) into `ok` |
| R36 | INGEST\_REJECTED chains a per-read `plate_ref` with camera and time (1590–1592) | \[claim\] | A missing cameras.json turns every read into a permanent pseudonymous location record | Chain a count per camera per hour |
| R37 | `case_hash` and `why_hash` are unkeyed SHA-256 (sentinel 121–125), read by partners | \[claim\] | “2027-1014” recovered in at most 10,000 tries | HMAC under the audit key |
| R25 | Badge-style usernames are hashed out of their own entries (the scrubber does not exempt `user`/`by`) | \[claim\] | QUERY.user = SHA-256 of “PD1234” | Exempt identity fields, or restrict names in provision.py |

## B4. What holds, minor items, and one new limitation

Most of the round-3 machinery now works. These held under attack, not just in the suite:

- **Same-transaction logging on the data paths (R29).** 400 HTTP views, 200 alerting reads and a 600-append external writer interleaved. The chain verified at 1,202 entries with exact counts.
- **Rollback when the chain write fails** on /hotlist (R22's contrast): the data did not land.
- **Ed25519 hygiene.** openssl writes the private key 0600 at creation, even under umask 022. Checkpoint signatures verify; replayed receipts are refused; a newer failing audit closes the gate (suite).
- **compact.py recomputes for real**, from its own stored `(seq, hash)`, and extends to the live root (compact 94–119, 206–223).
- **Tier 3 results** are ids only, nulled at class age, and re-gated by case at read (3594–3602).
- **Fresh-install suppression** is state-blind and normalized; R23's control shows VIC309 itself hidden.
- Also confirmed: registry-driven retention with one `frag_ref`; refuse-to-start on a wrong or missing key; restore keeps the live checkpoints and filters tar members; publish\_witness parses its input; the camera registry; no fabricated state or confidence; `destroy_by` on release.

**Minor items and doc drift** (static unless an R-number is given)

- Tier 2's window and retention both run on receipt time (864, 1617; retention 132), so a replayed backlog stays Tier 2-visible for 24 h after arrival.
- Tier 2 still accepts 3-character substrings (818). This was my round-2 condition, never made an S-item.
- The review note is optional (2368); hot-list expiry is optional and unbounded (1761).
- A rotation void request is not bound to a schedule id (2980–3001), so a stale request voids whatever is current.
- Re-export after destruction recreates the bundle and clears `destroyed_ts` (2515–2526).
- The scrubber's replacement is an unkeyed SHA-256 (sentinel 410), so a plate-shaped value is reversible by enumeration.
- Restore's config copies (`/config/*.pre-restore-*`, old .env camera credentials included) are never pruned; its prune loop covers only the DB folder (restore 229–247).
- OpenSSL 3.0 or later is required (`pkeyutl -rawin`, sentinel 329, 358). Nothing I received says so; I did not test 1.1.1 (this sandbox has 3.0.13).
- If Janus sits behind a reverse proxy, GET /search puts the plate fragment, case number and justification in its access log, an unregistered store. NETWORK.md was not attached this round. Fix: POST, or a logged format without query strings.
- Doc drift: the migration comment “already normalized-by-convention” (494–495) is contradicted by 1.1 line 979. rotation.py line 16 says the suite cross-checks the two schedulers; it does not. sentinel\_audit's “chain integrity (independent)” (207) is the target's self-report. Restore's docstring calls the set's own key “fingerprintable … out-of-band” (restore 111–115), but nothing compares it.

**New limitation, not a regression: OCR-confusable misreads (R23) \[claim\]**

Suppression matches exact canonical text, so misreads of a protected plate are not suppressed. With VIC309 suppressed, patrol's searches for “309” and “VIC3” return V1C309, VIC3O9 and VIC3D9, each with its camera. Those misreads are exactly what an abuser who knows the plate will search for.

The options are to fold confusable characters (0/O/D/Q, 1/I/L, 8/B, 5/S, 2/Z) into a suppression key matched in SQL, or at minimum to add a CANT-DO entry and show confusable variants in the near-match warning. Folding over-suppresses a few innocent plates, which is the safe direction for a protection order. That trade-off is the Commission's call; I would fold.

## C. Convergence: NOT CONVERGED

All four criteria fail, or pass while proving too little.

| Criterion | Holds? | Why |
| --- | --- | --- |
| (1) No seat raises a deployment-blocking or code-critical finding | No | Five live-data blockers (R02, R24, R03, R11, R17); Compact blockers (R01, R15, R30–R33, R19–R21); the B3 list. All reproduced at runtime |
| (2) Every forced change implemented or answered in writing | No | Round 3's forced change had three parts: an inventory, an enforced expiration, and “a shared authorization boundary for disclosure.” 1.2 built the first two. The third is neither built nor answered in TRACK-12. My round-3 forced change is FIXED-BUT-WRONG (section A). Gemini's 1,000-write test is implemented |
| (3) What remains is CANT-DO or routed legal and institutional questions | No | The remainder is code defects with small fixes. Only the items listed under “Routed” below belong in other lanes |
| (4) The orchestrator's re-tests pass, and prove enough | Pass; prove too little | 244/246 here, the 2 failures being the unattached demo file. All 38 defects pass the suite (next section) |

### The one forced change: one live disclosure gate

**Binding condition.** No live-data deployment until every response carrying plate text or plate-derived time and place is assembled by one function, the disclosure gate, which:

1. takes its scope from the endpoint's fixed purpose, never from the request: a share is Tier 2, and nothing maps an unrecognized tier to “full”;
2. applies, in SQL before any LIMIT, the tier window and live suppression on the canonical plate text — never a flag stamped at ingest, never a stored ref;
3. applies the stale-config fail-closed rule; and
4. chains the disclosure.

It covers /search, /share/query, /hits, /suppressed-hits, GET /hotlist, /tier3/results, /tier3/emergency, /verify and /evidence/export, including the bundle's reads. The migration recomputes every suppression's ref from its stored plate, and normalizes legacy `reads.plate`, `hits.read_plate`, `hits.entry_plate` and `hotlist_members.plate`, keeping the typed text in `plate_raw`.

**Acceptance tests.** Each fails against 1.2 as attached; all are in round4\_attacks.py.

- **R01:** a partner's `tier: 1` and `tier: true` shares return only the 24-hour window.
- **R02:** a suppression placed after the hit removes it from /hits, Tier 3 hits and the bundle, and detective verify and export are refused.
- **R18:** /tier3/results answers 503 while the surface is fail-closed.
- **R24:** on an upgraded 1.1 database, hot-listing the protected plate → 403, /hits shows nothing, “VIC 309” is invisible, and release → 200.
- **Route test:** walk every route in the dispatcher and fail if any plate-bearing response is built outside the gate.

**Why this one.** It is the unbuilt third of the forced change two seats issued independently in round 3. Every disclosure bug this round is two endpoints disagreeing: /search filters live while /hits trusts a stamp, and /search refuses tier 1 while /share maps it to full scope. Hand-rolled checks will keep drifting apart; one gate cannot.

The other blockers stand either way. R03, R11 and R17 each need their own fix (B1).

### Routed: not code defects

- **Act 668 of 2025:** flagged, not settled (Appendix 1). No finding here changes direction under the secondary source's reading.
- **§ 1804(d):** whether reciprocal shares are an “exchange” stays with counsel (Lane 2). Until R01 is fixed, a share can carry far more than the question assumes.
- **Key custody:** who holds the signing and audit keys, and where backups live, is the Commission's or city's decision. It determines how R06 and R44 get fixed.
- **OCR-confusable folding (R23):** a policy choice about over-suppression.
- **Accepted limitations, unchanged:** a same-box insider with key and sink; colluding supervisors; a typed prosecutor sign-off; K8 reported, not enforced; consequences of Compact delinquency.

## Do the re-tests prove enough? No

The suite tests the exact attack forms round 3 named, and this round's defects sit one step to the side of each. Passing 246/246 proves those forms are closed, not their neighbors.

| Suite check (run\_tests.py) | What it tests | The neighbor it misses |
| --- | --- | --- |
| “S10 share: Tier 3 refused” | `tier: 3` → 403 | `tier: 1` and `tier: true` → full scope (R01) |
| “hot-listed AND suppressed” (PRT208) | Order placed before the read | Order placed after the hit (R02) |
| “S18 non-AR suppression honored” | Fresh 1.2 data | A 1.1 database upgraded (R24) |
| “S6 anchor: health recovers after acceptance” | Acceptance clears the flag | The next checkpoint plus a restart re-alarms (R08) |
| “S16 sentinel\_audit DB mode: zero failures” | Instance B, which never exported evidence or ran Tier 3 | Any system that has fails forever (R10) |
| “S1 schema” | Column names matching `plate\|frag\|results` | Free-text columns and new tables (R43) |
| “S18 publish\_witness … local witness directory” | A same-host folder | That a same-host folder counts as witnessed (R45) |
| “S18 wrong audit key at boot ⇒ refuses” | Janus | The scripts with the same wrong key (R16) |
| “keyloss: refuses to start” | The refusal | The restore marker that refusal deletes (R07) |
| “S9 chain\_auditor barred from …” | The data endpoints | What its allowed endpoints cost the service (R15) |
| “S18 compact.py end-to-end” | Run with `--partner-pubkey` | Run without a pin (R30) |
| “S18 1,000 concurrent appends” | Chain across two processes | Janus plus an external writer: holds (R29) |

My round-2 and round-3 acceptance condition stands: the acceptance suite should be adversarial to the builders' assumptions and written by non-authors. The attached harness is one such suite, ready for Vesper to run on a scratch install.

## Appendix 1: Statute text relied on

I read the codified §§ 1804 and 1805 on Justia. Act 668 is flagged from a secondary source and not checked against the enrolled act.

| Provision | What it says (paraphrased unless quoted) | Findings it bears on |
| --- | --- | --- |
| [§ 12-12-1804(a)](https://law.justia.com/codes/arkansas/2020/title-12/subtitle-2/chapter-12/subchapter-18/section-12-12-1804/) | Captured plate data “shall not be preserved for more than one hundred fifty (150) days” | R03, R05, R42, R43, R12 |
| § 1804(b) | Data may be kept during an ongoing investigation and must be destroyed when it ends, with no charges filed or a concluded criminal action | R03: an unconfirmed “no charges” disposition keeps the data |
| § 1804(c) | Update the data every 24 hours if updates are available | Nit: hotlist\_sync is monitored at 26 h (181–183) |
| § 1804(d)(1)–(2) | No selling, trading or exchanging; data indicating evidence of an offense may be shared with other agencies | R01; the exchange question stays with counsel |
| [§ 12-12-1805(a)–(b)(3)](https://law.justia.com/codes/arkansas/2019/title-12/subtitle-2/chapter-12/subchapter-18/section-12-12-1805/) | Every six months, compile plates scanned, list names, and per check the confirmed matches, matches that did not correlate, and matches leading to arrest and prosecution; keep for 18 months | No new finding against `compute_report` |
| § 1805(b)(4) | Published rules must govern any retention beyond 150 days; failing that is grounds to exclude evidence | Sharpens R03: retention past 150 days that /health cannot see cannot be shown to follow those rules |

**Act 668 of 2025 (SB 446), flagged, not settled.** The Legislature's [bill page](https://arkleg.state.ar.us/Bills/Detail?id=sb446) records it as Act 668, dated April 2025. A [secondary source](https://www.recordinglaw.com/us-laws/automated-license-plate-readers/arkansas-alpr-laws/) says it amended §§ 1802–1805 and 1807, kept 150 days for governmental entities while setting 60 for private users, and struck purpose-limiting words from § 1804(a). If that reading holds, NOCTUA's 150-day ceiling (169–172) is unchanged for a municipal agency, and no finding here changes direction. The City Attorney should confirm against the enrolled act.

**Other sources used:** the published 1.1 [janus.py](https://raw.githubusercontent.com/HiramMcknoxt/noctua/main/1.1/janus.py) and [sentinel.py](https://raw.githubusercontent.com/HiramMcknoxt/noctua/main/1.1/sentinel.py), fetched only to build a real 1.1 database for R24.

## Appendix 2: Reproducing every finding

One command reproduces every (runtime) finding against a scratch copy of the attached tree. Nothing under `janus12/` is modified.

```bash
python3 round4_attacks.py /path/to/janus12 --ref11 /path/to/1.1-refs
```

- `--ref11` names a folder holding `1.1_janus.py` and `1.1_sentinel.py` from the repo's `1.1/`. Without it, R24 is skipped.
- `--only R01,R02` runs a subset. `--big-chain N` sizes R15 (default 1,000,000 entries, about 290 MB, built in about 8 s).
- `janus_wrapper.py` must sit beside the harness. It runs `janus.py` unmodified and patches one function in memory for R18, R22 and R41.
- Needs Python 3.12+ (tested on 3.13), OpenSSL 3.x on PATH, and free loopback ports from 18401. The harness refuses to run if a port is taken.
- My full run: 1 min 49 s, 40 checks, 38 CONFIRMED, 2 HOLDS. Exit status is 1 while any defect reproduces, by design.

**Index** (gaps in the numbering are unused ids)

| R | Finding | Section |
| --- | --- | --- |
| R01 | Share `tier: 1` gets the full Tier 3 scope | B2 |
| R02 | Suppression stops at an ingest-time stamp | B1 |
| R03 | One detective keeps any hit past 150 days | B1 |
| R05 | HOLD\_DAYS uncapped, unrecorded | B3 |
| R06 | Self-certifying backup manifest | B3 |
| R07 | RESTORE marker lost on a refused boot | B3 |
| R08 | Anchor acceptance re-alarms | B3 |
| R09 | Anchor fails open on a never-restarted install | B3 |
| R10 | sentinel\_audit DB mode fails healthy systems | B3 |
| R11 | Hot-list removal reports success, removes nothing | B1 |
| R12 | Arbitrary text into the permanent chain | B3, B2 |
| R13 | Unauthenticated AUTH\_FAIL flood | B2 |
| R15 | chain\_auditor stalls the service | B2 |
| R16 | Scripts skip key continuity | B3 |
| R17 | Two-key approver sees only hashes | B1 |
| R18 | /tier3/results skips fail-closed | B3, C |
| R19 | Witness duty filed by anyone, unchained | B2 |
| R20 | No-seed rotation 500s; one-member self-audit | B2 |
| R21 | Delinquency attributed by adjacency | B2 |
| R22 | Commit-before-log on six paths | B3 |
| R23 | OCR-confusable misreads unsuppressed | B4 |
| R24 | 1.1 → 1.2 upgrade voids suppressions | B1 |
| R25 | Badge-style usernames scrubbed | B3 |
| R26 | Negative Content-Length | B3 |
| R27 | Protection-order oracles | A |
| R29 | Same-transaction appends hold (positive) | B4 |
| R30 | compact.py unpinned by default | B2 |
| R31 | sentinel\_audit URL mode needs a data role | B2 |
| R32 | Receipt leg fails open | B2 |
| R33 | Signed reports replayable and unbound | B2 |
| R34 | /health ok ignores cameras and overdue holds | B3 |
| R36 | INGEST\_REJECTED per-read location record | B3 |
| R37 | Unkeyed case\_hash | B3 |
| R39 | Janus and rotation.py schedulers agree (positive) | B2 |
| R40 | Seed grinding | B2 |
| R41 | Sink forks on a failed COMMIT | B3 |
| R42 | Off-box backups invisible; uncapped | B3 |
| R43 | Registry gaps; schema test blind spot | B3 |
| R44 | No signing-key rotation | B3 |
| R45 | Same-host folder counts as witnessed | B3 |
