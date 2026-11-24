# NOCTUA 1.1 — Round 3 hostile review (Claude cloud seat)

Nov 24, 2026 · @Corey Spangler

## Verdict

**NOCTUA 1.1 is not deployable as published.** Most of the round-2 fixes to Janus landed, and section A confirms them line by line. But the scripts round 2 never saw break three of the system's central promises. Each fix is small; none needs a redesign.

- **The 14-day promise.** Every Tier 3 search stores its full results in the database: up to 200 reads and 50 hits, each with plate, camera and time. Nothing ever deletes them, so they outlive the 14-day policy on day 15 and the 150-day statutory cap on day 151 (C1).
- **The tamper-evidence promise.** The script that publishes checkpoints outside the building fails on every run, after the checkpoint job has already reported healthy (C2). The shipped restore tool replaces the file the startup anchor checks, so a rollback raises no flag (C3). A chain that fails verification still reports `ok: true` (B3).
- **The protection-order promise.** Suppressions match on plate and state, but the camera bridge stamps nearly every read "AR". A suppression entered with any other state, or with "Arkansas" spelled out, silently matches nothing (B1).

Keep the new Compact switched off until two more problems are fixed. A partner can request Tier 3 and skip the two-key process (B5). The "no cross-audit, no data" gate checks that an attestation record exists, not that an audit happened (B6).

**Tally:** 6 blocking, 2 blocking for the Compact, 4 critical, 6 high, 6 medium, 2 groups of low. Section D lists each with its smallest fix. I couldn't run the code in this session, so every finding comes from reading it (next section).

## How I worked, and proof of reading

I read every file below at commit f64b4fa; I could not execute any of it. I tried to run the shipped suite and my own attack checks on a scratch copy, and this session's permission layer refused, as it did in round 2. So I have not re-run the 184 checks, and every finding comes from the code as written.

Tags used throughout:

- **static**: follows deterministically from the code as written.
- **runtime**: depends on behavior I could not observe; it needs a runtime test.
- **own claim**: judged against NOCTUA's own claims (docstrings, TRACK-11, COMPACT.md) and its rule that every action mediated by Janus is logged.
- **statute**: judged against Ark. Code §§ 12-12-1801–1808 as compiled before Act 668 (Appendix 2).

| File | Lines | Two functions (line) | Read |
| --- | --- | --- | --- |
| council2/synthesis.md | 156 | sections "Convergent findings", "Forced-change dispositions" | Full |
| 1.1/janus.py | 2,829 | `run_search()` L585, `_share_query()` L2214 | Full |
| 1.1/sentinel.py | 317 | `_scrub_scan()` L80, `Chain.verify()` L298 | Full |
| scripts/retention.py | 187 | `main()` L93, `frag_ref()` L65 | Full |
| scripts/compact.py | 133 | `main()` L61, `report_hash()` L56 | Full |
| scripts/rotation.py | 194 | `build_schedule()` L78, `_rounds_for()` L58 | Full |
| scripts/sentinel\_audit.py | 290 | `audit_url()` L87, `audit_db()` L163 | Full |
| scripts/backup.py | 200 | `main()` L91, `config_paths()` L79 | Full |
| scripts/restore.py | 148 | `main()` L59, `refuse()` L54 | Full |
| scripts/checkpoint.py | 127 | `_audit_key()` L50, `heartbeat()` L78 | Full |
| scripts/frigate\_bridge.py | 204 | `extract()` L80, `forward()` L126 | Full |
| scripts/provision.py | 130 | `issue_key()` L67, `save()` L52 | Full |
| scripts/alert\_check.py | 97 | `notify()` L35, `main()` L51 | Full |
| scripts/publish\_witness.sh | 62 | bash, no functions: checkpoint step L42–45, push L51–55 | Full |
| 1.1/COMPACT.md | 137 | sections "How it works", "Audit rotation" | Full |
| 1.1/TRACK-11-REPORT.md | 342 | items 1–35, "Not live-tested" | Full |
| 1.1/tests/run\_tests.py | 1,214 | `suite_compact()` L946, `suite_retention()` L1102 | Partial: L810–1176, plus a search of the rest |

Not read: TRACK-A-REPORT.md (145 lines), demo/seed\_demo.py (298) and demo/DEMO-DATA.md (364). Consulted for context only: deploy/docker-compose.yml, deploy/README.md, the 1.0 janus.py QUERY entries, and the 1.0 and deploy copies of checkpoint.py. Line numbers refer to 1.1 files unless another file is named.

## A. My round-2 findings, checked against 1.1

Of my seat's 19 round-2 findings, 9 are fixed, 5 are partly fixed, 4 are fixed but wrong and 1 is not fixed. Two of the "fixed" ones (S1 and S7) created new problems. Rows 1–12 are the convergent findings my seat co-raised; S1–S7 were mine alone.

| # | Round-2 finding | 1.1 status | Evidence |
| --- | --- | --- | --- |
| 1 | Tier 2 unbounded | Fixed | Window applied in SQL on receipt time (L598–606, L2711); /search refuses tier 3 (L2643–2655). Residual: a backfilled or re-posted read gets a fresh receipt time and lands inside the window (C5). |
| 2 | /hits, /hotlist and failed logins unlogged | Fixed | HITS\_VIEW L2468, HOTLIST\_VIEW L2504, AUTH\_FAIL L920–928. Residual: AUTH\_FAIL writes the raw attempted username into the chain (B8). |
| 3 | QUERY doesn't record what was searched | Fixed | plate\_ref and result\_count on every QUERY (L2715–2718, L1573–1577, L1690–1694) and on SHARE\_OUT (L2283–2285). Matching a ref to a case file needs the audit key, so key custody decides whether an auditor can use it. Regression: B12. |
| 4 | Suppression is an oracle and a sieve | Fixed but wrong | Stubs are gone from search (L611–617). The sieve reopened through state keys and raw ingest text (B1); the oracle moved (B10). |
| 5 | Evidence export is a permanent bypass | Partly fixed | Verified hit and case match (L1776–1791), ±1 h scope (L1792–1822), release needs an export (L1903–1914), destroy exists (L1925–1961), paged custody excerpt (L832–853). But the "matching case" is whatever the verifier typed at /verify (L1157–1160); bundles never expire (C4); suppressed hits export (B10). |
| 6 | Chain integrity weaker than claimed | Partly fixed | Atomic append (sentinel L228–258), persistent sink state with a spool (L176–212) and the sequence-gap check (L298–317) are fixed. The outside anchor is not (C2, C3, B7). |
| 7 | Health lies by omission | Fixed but wrong | Explicit ok (L1077), split roles, silent cameras, retention cross-check (L2368–2377). Chain verification is left out of health (B3), and the checkpoint job reports healthy before its witness step (C2). |
| 8 | § 1805 report defects | Fixed, with residuals | Outcome-based counts (L775–828), lists\_checked (L1002–1006), "not yet reported" (L816), K8 share (L742–772), snapshots (L1396–1416). Residuals in B14. |
| 9 | § 1804(b) second exit missing; holds never expire | Partly fixed | Disposition with a second-supervisor confirm (L1962–2040), honored by retention (retention L115–122). Holds still never expire (C4). |
| 10 | Hot-list hygiene | Partly fixed | Expiry checked at ingest (L1013–1021) but compared as free text (B18); one shared case gate (L525–533); the hotlist\_sync heartbeat (L159–160) proves the job ran, not that the list is current. |
| 11 | Ingest trusts too much | Not fixed | State defaults to "AR" (L980; bridge L128); confidence defaults to 0.95 (L997; bridge L129) and lands in evidence bundles (L1806–1825); any camera name is accepted (L981); no dedupe. My ask to key plate\_ref by state was right for the hot list and wrong for suppression (B1). |
| 12 | Doc-vs-code drift | Fixed; new drift | Binds 127.0.0.1 (L143); retention settings read from env (L153–154). New drift: COMPACT.md overclaims the audit (B6); TRACK-11 item 18 says the case gate runs on /evidence/\*, but only export runs it; item 19 says non-requesters are refused, but supervisors and the auditor aren't (L2736); the bridge docstring says replays show as clock skew (bridge L51–53); deploy/ builds a pre-1.0 Janus (C8). |
| S1 | Tier 3 results reach only the approver | Fixed; side effect C1 | The requester fetches results from GET /tier3/results (L1578–1583, L2721–2752). The stored results are never deleted (C1), and every supervisor and the auditor can read them (B17). |
| S2 | Approve doesn't re-check the case | Fixed | L1544–1554. |
| S3 | Emergency needs no auth\_basis and is unlimited | Partly fixed | auth\_basis required (L1635–1643). An unreviewed emergency older than 72 h blocks the next (L1656–1672). Use is still unlimited inside 72 h, and any other supervisor's review clears the lock whatever the finding. |
| S4 | Suppression format mismatch fails silently | Fixed but wrong | Placement normalizes (L1297) and warns about variants already on file (L1316–1332). Ingest doesn't normalize (L979), so later variants are never suppressed, and placement can't key the variant it warns about. State mismatches get no warning at all (B1). |
| S5 | Suppression needs a criminal case | Fixed | order\_ref required, case optional (L1284–1296). |
| S6 | CLOCK\_SKEW floods on backfill | Fixed | Backfill is aggregated (L1052–1054, L701–727). A camera clock running ahead still logs one CLOCK\_SKEW per read (L1048–1051). |
| S7 | Free text carries plate text into the chain | Fixed but wrong | The prose fields left the chain, but raw input still reaches it on eight paths, one of them unauthenticated (B8). Side effects: a scrub hit after commit hides the action (B4), and Tier 2 justifications are now recorded nowhere (B12). |

**My round-2 binding condition is met, except for partner shares and two acceptance tests.**

- Roles limited on every data route: met by allowlists (e.g., L2627–2629, L2452, L2495), except that partners can choose Tier 3 (B5).
- A chain entry with user, case, ref and count before data leaves: met on read paths. Write paths commit first and chain second (B4).
- Wildcards and short fragments refused: met (L555–566). Tier 2 bounded: met.
- Acceptance test "/hits fails as auditor": not met, by design. The auditor is a data role (L167, L2452). I flag it in B17 rather than reopen it.
- "An independent tester on the release build": not met. The suite ships as part of the build, and deploy/ doesn't build 1.1 (C8, Appendix 1).

## B. Attacks on what's new

The new controls mostly hold against an honest operator. They fail against a careless operator, a hostile insider or an abuser with a legitimate login. Severity scale: **Blocking** means no live plate data until fixed; **Compact-blocking** means sharing stays off until fixed; **Critical** means small and fixed before deployment; then High, Medium and Low.

### B1. Protection-order suppression matches on a state the cameras don't report

*Blocking · statute § 12-12-1808(b) and own claim (item 5) · static*

A suppression matches only when a read's plate text and state both equal the suppression's. The bridge sends "AR" whenever Frigate reports no state, and its own docstring says Frigate doesn't report state reliably (bridge L43–47, L127–129). Janus ingest also defaults to "AR" (L980).

- Placement keys `plate_ref(plate, state)` on whatever state the supervisor types, uppercased and unvalidated (L1298, L1301).
- Search, Tier 3, partner shares and /hits filter on the stored plate and state (L611–617, L2462–2463).
- So a suppression entered as "TX" (the state on the order) or "ARKANSAS" never matches a read stored as "AR". The protected plate stays fully searchable.
- The hot-list conflict check uses the same key (L1106). An abuser can hot-list the plate as "AR" and watch every pass on /hits.
- The near-match warning compares plate text only, never state (L1321–1329), so this case gets no warning.

The text-format version (S4) is still open too: ingest stores the camera's raw text (L979), so "VIC 999" never matches a suppression keyed "VIC999". This hole came from my seat's round-2 ask to key plate\_ref by state. That is right for the hot list, where a false match is the danger; for suppression, only an over-broad match is safe.

**Fix:** suppression identity is `normalize_plate(plate)` alone, ignoring state. Use it in placement, release, `is_suppressed`, the search and /hits filters, and the hot-list conflict check. Normalize at ingest (L979), and recompute existing suppression refs at startup from the plaintext plate the table already stores (L333–337). Validate state as a two-letter code everywhere else.

### B2. A wrong audit key is accepted silently

*Critical · own claim (item 30) · static*

Item 30 locks Janus when no key exists, and its comment states the principle: "a wrong key is worse than no service" (L180–183). But `_audit_key()` accepts any NOCTUA\_AUDIT\_KEY or key file without checking it against the key the chain was built with (L184–189). Nothing stores a fingerprint; the meta table holds anchor state only (L455–468).

Scenario: an operator moves a key-file install into the Docker deploy, whose instructions say to put an audit key in .env (deploy/docker-compose.yml L7). Janus starts unlocked with the new key. Every suppression silently stops matching, old plate\_refs no longer join, and old checkpoints fail their HMAC.

**Fix:** store a key fingerprint in meta on first use. Start locked, with `key_mismatch` in /health, when the resolved key's fingerprint differs.

### B3. /health reports ok on a chain that fails verification

*Blocking · own claim (item 24) · static*

/health computes `chain_ok` (L2379) but leaves it out of `degraded` (L2374–2377), and `ok` means only "not degraded and not locked" (L2394). alert\_check.py alarms only on `ok` (alert\_check L65) and never reads `chain_ok`. So when verify() detects tampering, the dead-man check prints "OK: janus healthy." Item 24 promises /health never reports ok while degraded.

**Fix:** add `or not chain_ok` to `degraded`, and a "chain verification failed" reason to alert\_check.py. One line each.

### B4. A scrubber hit after the write hides who did what

*Blocking · own claim (every action mediated by Janus is logged) · static; confirm at runtime*

Write handlers commit to the database first and append to the chain second, for lock-ordering reasons. /hotlist commits at L1124 and appends at L1125–1128; /holds commits at L1237 and appends at L1238; /reads commits the read and hit at L1043, then appends the ALERT at L1060. If an append trips the scrubber, Sentinel records only `CHAIN_SCRUB_BLOCKED` with the entry kind and field name (sentinel L264–272): no actor, plate\_ref, case, hit or camera. The handler returns 500 (L960–962), but the committed write stands.

The attack: a detective hot-lists a target with the category "ABC 123", which normalizes to a plate shape (sentinel L89–91).

- The entry is live, and HOTLIST\_ADD is never written.
- Every later pass of the target commits a read and a hit. Its ALERT copies the category (L1061), so it is blocked too.
- The chain fills with anonymous blocked entries while the hits show normally on /hits. Only the editable `hotlist.added_by` column names the detective.

**Fix:** run the scrub check on the payload before the first database write in every write handler, and record the actor and action in `CHAIN_SCRUB_BLOCKED`. Better still, accept only coded values for category, hold ref and review date (B8).

### B5. A partner can request Tier 3 and skip the two-key process

*Compact-blocking · own claim (two-key Tier 3; COMPACT.md) and a statutory question · static*

/share/query takes the partner's requested tier (L2270–2275) and runs a full-store search for tier 3 (L2281). There is no request, no second key, no auth\_basis, no case check and no rate limit. The required `why` is checked and then discarded (L2249–2256). With 3-character fragments allowed (L555–566), one partner key can walk the store.

TRACK-11 flags this as an open call (L298–304), on the theory that the cross-audit vouches for the partner's own two-key process. It doesn't: compact.py checks chain integrity only (compact L93–108), not whether a partner's Tier 3 queries were approved. COMPACT.md says shares run "under the same rules as a local search," with the justification recorded (L49–51); neither is true.

For the City Attorney, not settled: § 12-12-1804(d) bars selling, trading or exchanging captured plate data. It lets law enforcement share only data that "indicates evidence of an offense." A reciprocal-access compact is structurally an exchange, and a fragment search returns mostly reads that indicate nothing.

**Fix (answering the builder's question):** cap partner shares at Tier 2, the one-line change TRACK-11 offers. Store the partner's justification against the SHARE\_OUT entry, and rate-limit each partner. Pending legal review, consider sharing hits (matches) only, not raw reads.

### B6. The cross-audit gate checks that an attestation exists, not that an audit happened

*Compact-blocking · own claim ("enforced by the software, not by trust," COMPACT.md L19–20) · static*

1. **Our leg is a bare assertion.** /compact/audit-result accepts `{"ok": true}` from the jobs service account or any single supervisor, with no evidence (L2110–2132). The suite's own Compact test opens the gate exactly this way (run\_tests L968–971). The chain entry records only the agency and the user (L2129–2130).
2. **A later failure doesn't close the gate.** The gate counts any passing row from the last 26 hours (L2239–2243), not the latest result.
3. **Their leg can be replayed.** A receipt is accepted for any checkpoint ever published (L2084–2093), and freshness is measured from when it arrives (L2244–2248). A partner who audited once can post the same old receipt every day.
4. **The audit asks the auditee.** compact.py asks the partner's server whether its chain verifies, then compares two values the same server supplies (compact L93–108). The checkpoint comes from the partner's local file (janus L2603–2621), not its witness, and its signature is passed along unchecked (compact L113–115). COMPACT.md says the auditor "verified B's chain end to end" (L33–35), but nothing is recomputed. sentinel\_audit.py's URL mode labels the same self-report "chain integrity (independent)" (L128–132).

Underneath all four: checkpoints are HMAC-signed with the plate\_ref key (checkpoint L113–114). A partner can verify one only by holding the key that de-pseudonymizes every plate\_ref in your chain. The audit report's "auditor's own key" signature can't be checked by the audited agency either, and it falls back to the auditor's own plate\_ref key (sentinel\_audit L19–21, L273–279).

**Fix:**

1. Gate on the latest audit result for each partner.
2. Accept a receipt only for a checkpoint dated within 26 hours.
3. Put the report hash and the audited root and entry count in the CROSS\_AUDIT\_OK entry. A supervisor's manual "ok" becomes a two-key override that doesn't count toward the gate.
4. Have compact.py fetch the partner's checkpoint from its witness copy and recompute hashes locally. Janus needs a paged `/audit?after_seq=` read for that.
5. Sign checkpoints with a separate key, or rely on witness publication instead of HMAC.

### B7. Every anchor check looks only at the newest checkpoint

*Critical · own claim (item 7) · static*

- The startup anchor reads only the last line of the local checkpoints file (L479–486).
- compact.py fetches only the newest checkpoint (compact L93–94).
- sentinel\_audit verifies every HMAC but anchors only the newest line (L67–84, L190–199).
- checkpoint.py signs the current root without running verify() or checking earlier checkpoints (checkpoint L104–115).

So an insider rewrites history in the morning, lets the nightly checkpoint sign the rewritten root, and restarts. There is no startup mismatch, and the DB-mode audit and the cross-audit both come back clean. Only an older witnessed checkpoint would disagree, and nothing reads those back. The startup anchor also fails open: with no checkpoints file, or one unparseable line, it does nothing (L477–478, L485–486).

**Fix:** every check tests every checkpoint line (`hash_at_seq(entries) == root`), one lookup per day of history. checkpoint.py refuses to sign, and reports failure, if verify() fails or any earlier checkpoint no longer matches. A missing or unreadable checkpoints file raises `anchor_mismatch` instead of skipping.

### B8. Raw input, some of it unauthenticated, still reaches the permanent chain

*Critical · own claim (item 26; Sentinel docstring) · static*

Sentinel says chain entries never contain plate text and carry only coded fields (sentinel L8–17). Raw caller text still reaches the chain on at least eight paths:

- AUTH\_FAIL logs the X-Noctua-User header of any request: unauthenticated, unbounded and not rate-limited (L920–928).
- SHARE\_BLOCKED logs the body's `agency` for any logged-in role (L2223–2232).
- BLOCKED logs a rejected case\_id (L1490–1492, L1646–1648) and raw hit and request ids as sent (e.g., L1141–1144, L1758–1761).
- HOLD\_PLACE logs a free-text ref and review date (L1238–1242).
- HOTLIST\_ADD and ALERT log a free-text category (L1125–1128, L1060–1061).
- SHARE\_OUT logs the partner's case\_ref (L2283–2285).
- HEARTBEAT logs any job name (L1085).
- BACKFILL and CLOCK\_SKEW log any camera name.

The scrubber catches only a whole string that is uppercase and fits one of three US plate shapes (sentinel L76–95). "abc123", "plate ABC123", vanity plates and many out-of-state formats all pass. Any string starting with "pref:" is exempt by construction (L87–88), so "pref:ABC123" passes too.

Two consequences follow:

- Anyone who can reach the port can write arbitrary text into a permanent log that is published and handed to partners.
- Every AUTH\_FAIL grows the chain, and /health re-verifies the whole chain on every unauthenticated call while holding the global lock (L2342, L2379). Item 25 moved that ingest stall from /audit/verify to /health. Its cost grows with chain length (runtime).

**Fix:** AUTH\_FAIL records the username only if the account exists, otherwise "unknown," aggregated per minute. Every chained field is an enum, an integer, a known case number or a ref, validated at input. /health verifies incrementally from the last verified entry.

### B9. Account and case-list changes are applied with no chain entry

*Critical · own claim (two-key controls; everything mediated by Janus is logged) · static*

On a successful reload, `_reload_config` swaps in the new users.json or cases.json and writes nothing (L262–270); only failures are chained. provision.py's issuance record is a line printed to the terminal (provision L16–19, L67–72). So a new account, a patrol-to-supervisor promotion, a re-enabled account, a key rotation or a newly "opened" case leaves no trace.

Whoever can write the config folder can mint a second supervisor and approve their own Tier 3 requests through it. The chain shows two names and no record of when the second appeared. Every two-key control assumes the set of keys is itself audited.

**Fix:** on every successful reload, chain a CONFIG\_APPLIED entry with a structural diff: accounts added or removed, role and disabled changes, key-hash changes, cases added and removed. Show account changes from the last 24 hours on /health.

### B10. The suppression oracle moved, and suppressed hits have a side door

*High · statute § 12-12-1808(b) and own claim (item 5) · static*

- /hotlist tells any detective "that plate is under a protection-order suppression" (L1106–1115). That confirms a car belongs to a protected person. If the plate isn't suppressed, the detective can simply hot-list it.
- /stats gives detectives and the auditor the counts of active suppressions and of suppressed pending hits (L2519–2527).
- /hits returns sequential ids with suppressed rows removed (L2455–2467). A gap marks a suppressed hit and brackets its time.
- Side door: /verify and /evidence/export never check whether a hit is suppressed (L1146–1148, L1764–1767). Patrol or a detective can verify a suppressed hit by id under any open case, and a detective can then export it.
- A supervisor's expanded export pulls the protected plate's full 14-day history (L1805–1810), which no search can return.

**Fix:** answer a blocked hot-list add with a generic refusal, and give the reason only to supervisors and the chain. Show suppression counts to supervisors only, and use non-sequential hit ids. /verify and /evidence/export refuse suppressed hits except from the supervisor queue, and never expand them.

### B11. Detectives can read the audit chain

*High · own claim (the chain watches its users) · static*

GET /audit serves detectives the newest 1,000 entries, or any entry by sequence number (L2419–2448). Those entries show who searched what (by ref), under which case, who placed suppressions and who was blocked. A detective who searches their own plate once learns its ref, then can watch for anyone else searching it.

**Fix:** detectives see only the entries where they are the user or actor.

### B12. Tier 2 and share justifications are now recorded nowhere

*High · own claim (item 26) · static*

1.0 chained the Tier 2 justification (1.0 janus L1035–1038). 1.1 took it out of the chain under item 26, which says free text "lives in the DB tables" (L90–93). But for /search (L2656–2665) and /share/query (L2249–2256), no table stores it either, so the auditor can no longer read why a Tier 2 search ran. This is a side effect of the fix to my own round-2 finding S7.

**Fix:** store justifications in a table keyed to the QUERY or SHARE\_OUT entry, kept for the audit horizon. Decide in policy whether plate-shaped words are masked.

### B13. Rotation: the seed is decorative and the duty check reads the wrong table

*Medium · own claim (COMPACT.md; rotation.py docstring) · static*

- The seed is computed and published (rotation L53–55, L82) but never used. The schedule depends only on the sorted member list (L58–75, L94–97). Every cycle repeats the same alphabetical schedule, and the cycle start changes nothing, though COMPACT.md says the schedule is a function of the seed (L99–103).
- Janus checks only that a submitted schedule recomputes from its own submitted member list (L2181–2189). Nothing reconciles the members with the partners table or with other agencies' copies, and one supervisor publishes it.
- /compact/rotation/status checks duties owed to us against our audits of them, not their receipts, with no time limit in either direction (L2781–2788, L2806–2809). `rotation_delinquent` can never fire for an agency we have audited once.
- The witness duty isn't implemented anywhere.
- With three members and 90-day rounds, each round holds one deep audit. A member can go 360 days unaudited at the start of each 540-day cycle.

**Fix:** use the seed to shuffle slot order each cycle, and reconcile members with the partners table. Read compact\_receipts within each round's dates. For three or more members, consider a per-round assignment in which every member is audited every round.

### B14. Report residuals under § 1805

*Medium · statute § 12-12-1805 and own claim (item 11) · static*

- REPORT\_COMPILE chains only the snapshot id (L1412–1413), so the "immutable" body can be edited in the database undetected. Chain its sha256.
- The list-name sanitizer strips one case-number shape, `\d{4}-\d+` (L737). Local list names are free text (L1116–1117) and print in the public report. Use a list registry.
- Per-list prosecutions read 0 when nothing has been reported (L796, L806), while the total says "not yet reported."

### B15. The sink spool is fragile

*Medium · own claim (item 6) · static and runtime*

- A truncated spool line makes `_stream` raise outside its try block (sentinel L183–185). The spool rewrite isn't atomic (L200–205), so a power loss mid-rewrite can cause it. After that, every append raises after its commit, and every chained request fails until someone repairs the file (runtime).
- Janus, retention and checkpoint each hold only an in-process lock, so they can write the sink out of chain order, contrary to L177.
- A crash between commit and stream drops that entry from the sink permanently.
- The shipped compose file puts the sink on the database's own volume (deploy/docker-compose.yml L26–29). That copy is not a witness.

### B16. One supervisor can blind the system to any plate

*Medium, a policy call · own claim (two-key design) · static*

A single supervisor can place a suppression with an unverified order reference (L1272–1315). The plate then vanishes from every search, warrant-backed Tier 3 included. Any future hot-list entry for it is refused (L1106–1115), stolen-vehicle and AMBER entries included. Releasing it takes two supervisors (L1355–1383). Failing toward protection is right, but nothing reviews the order.

**Fix:** the auditor confirms the order within 72 hours, or /health degrades. Ask counsel whether excluding warrant searches is required; § 1808(b) allows disclosure "as the result of a match."

### B17. Who can read Tier 3 results

*Medium, a design call · own claim (item 19; the auditor "does not search") · static*

Any supervisor and the auditor can fetch any Tier 3 result set at any time, with no case check (L2736–2744). That includes the approver, so item 19's "the approver does NOT receive the results" is one more call away, though the call is chained. The auditor also reads plate data through /hits, /hotlist and Tier 3 results (L167). Decide this in policy rather than leave it implicit.

### B18. Smaller items

*Low · static unless marked*

- Hot-list expiry is free text compared to ISO time (L1013, L1123): "12/01/2026" expires at once, and "Dec 1" never does. Expiry is checked lazily, so an expired list still counts as "checked" for § 1805 (L1002–1006).
- A camera clock running ahead logs one CLOCK\_SKEW per read (L1048–1051).
- LIMIT is applied before the suppression filter (L604–617, L2455–2463), so a short page reveals suppressed rows.
- /compact/rotation accepts any cycle start (L2169–2173), but status parses it as a date (L2769). One bad publication breaks the status endpoint.
- `custody_excerpt` matches the hit id as an integer (L846–850), but VERIFY and EVIDENCE entries chain the id as the client sent it (L1177, L1921). A string id drops those events from the excerpt (runtime). HOLD\_PLACE entries carry `ref`, not `hit`, so holds never appear (L1238–1242).
- Emergency searches are unlimited within 72 hours, and any other supervisor's review clears the lock whatever the finding (L1656–1672, L1699–1742).
- Unauthenticated /health publishes each camera's last-read time (L2390), a small timing side channel.
- A design call, not a defect: any detective can hot-list any plate under any open case, with expiry optional (L1088–1129). Every pass then shows on /hits to all data roles, which makes the hot list a one-key real-time tracker. The council should decide whether local adds need supervisor approval or a mandatory expiry.

## C. The scripts round 2 never saw

The scripts carry half of the six blocking findings. Retention misses a whole class of stored plate data, the witness publisher hasn't worked since 1.0, and restore defeats the startup anchor.

### C1. Retention never deletes Tier 3 result sets

*Blocking · statute § 12-12-1804(a) and own claim (14-day policy; item 20) · static*

Approving a Tier 3 request stores its results as JSON in `tier3_requests.results` (janus L1562–1568). That is up to 200 reads and 50 hits (L604–610), each with plate, state, camera and time. Every emergency search does the same (L1675–1684).

- retention.py scrubs only the fragment column (retention L135–154) and says outright that "Rows are never deleted by this job" (L24). No code anywhere clears the results.
- GET /tier3/results serves them to the requester, any supervisor and the auditor, with no age check (janus L2721–2752).
- The suite's retention test plants a Tier 3 row with no results, so it cannot see this (run\_tests L1134–1138).
- sentinel\_audit's retention check reads only the reads table (L200–209), so an audit would certify compliance.

So every Tier 3 search makes a permanent, browsable archive of plate reads. It outlives the 14-day policy on day 15 and the statute on day 151: § 12-12-1804(a) bars keeping captured plate data longer than 150 days, and nothing ties these rows to the § 1804(b) investigation exception. § 12-12-1806 bars captured plate data and derived evidence from proceedings where disclosure would violate the subchapter. The city's § 1805(b)(4)(A) retention rules cannot truthfully describe this store.

This is the fix to my own round-2 S1: storing the results so the requester can fetch them created the store.

**Fix:** retention clears results older than RETENTION\_DAYS: `UPDATE tier3_requests SET results=NULL WHERE results IS NOT NULL AND COALESCE(decided_ts, created_ts) < cutoff`. GET /tier3/results refuses older requests, and a test plants a 15-day-old result set. Anything that must outlive that goes through evidence export, under the custody rules.

### C2. The witness never publishes

*Blocking · own claim (publish\_witness.sh L10–15; deploy README) · static and deterministic; one manual run would confirm it*

publish\_witness.sh parses checkpoint.py's whole output as one JSON document (L42–45), under `set -euo pipefail` (L35). But checkpoint.py prints the checkpoint (checkpoint L121) and then always a second line: "heartbeat sent," "skipped" or "FAILED" (L84–85, L98, L100–101). Parsing fails with "Extra data," so the script exits at L43 on every run. That is before the witness-repo append (L48), the git push (L51–55) and the Clerk email (L57–61).

By then checkpoint.py has written its local file and reported the checkpoint job healthy (checkpoint L116–122), so /health stays green.

The break arrived in 1.0, when checkpoint.py gained its heartbeat; the pre-1.0 deploy copy printed only the JSON. No test runs publish\_witness.sh. The key sits on the server by default (checkpoint L13–17), so the outside witness is the only defense against a privileged insider, and it is silently absent. Run by hand, the script fails loudly; under cron it fails silently unless cron mails its output. The deploy README tells operators to run it to "prove the witness path works."

**Fix:** send checkpoint.py's heartbeat messages to stderr, or parse only the first line. Post a separate "witness" heartbeat only after the push succeeds, and have Janus monitor it like the other jobs. Add a test that runs the script.

### C3. restore.py replaces the file the startup anchor checks

*Blocking · own claim (item 7; round-2 finding 6) · static*

restore.py moves the live checkpoints file aside and installs the backup set's own copy (restore L113–115, L122–124). The startup anchor compares the chain only with that local file's last line (janus L477–495). Restore a five-day-old set, and the newest local checkpoint matches the restored chain. No mismatch is raised, and five days of searches, alerts and blocks vanish without a flag. If the set has no checkpoints file, the live one is still moved aside and the anchor skips entirely (L477–478).

The manifest HMAC is checked with the key packed inside the same set (restore L78–82; backup L124–131), so it proves nothing about who altered the set. This is round-2 finding 6, "a restore rolls the chain back invisibly," now done by the project's own tool.

**Fix:** never move or overwrite an existing live checkpoints file; install the set's copy only when none exists. Append a RESTORE entry. The startup anchor then flags the rollback for the two-key accept, since a checkpoint with more entries than the chain already counts as a mismatch (L490–495). Better still, anchor against the witness copy.

### C4. Holds and evidence never actually expire

*High · statute § 12-12-1804(b) and own claims (items 9–10) · static*

- A hold's review date is whatever the caller sends (L1229–1231), so "9999-12-31" never comes due. Overdue holds only show in /health (L682–687), and retention ignores review dates (retention L115–122).
- Posting a disposition needs no export and no case check (L1962–2004). Left unconfirmed, it exempts its hit from deletion indefinitely (retention L116–118): a hold with no hold record and no review date. Re-posting also un-confirms a confirmed disposition (L1988–1993).
- Retention never touches the evidence folder, so a released bundle lives until a supervisor destroys it by hand (L1925–1961).
- Re-export points the record at a new bundle folder and never removes the old one (L1836–1841, L1864–1876). Those orphan copies are beyond the reach of destroy.

§ 1804(b) requires destruction when the investigation or the criminal action concludes. Nothing in the code connects "still held" to "case still open."

**Fix:** the retention exemption requires an actual export. Holds, bundles and dispositions whose case has left cases.json degrade /health and appear in /report. Review dates are capped, for example at 180 days. Retention deletes released bundles and orphan folders, and a re-export deletes its predecessor.

### C5. Ingest and the bridge still trust too much

*High · own claims (14-day policy; Tier 2 window) · static unless marked*

- Round-2 finding 11 stands: state and confidence defaults, any camera name, no dedupe.
- Nothing limits how old a camera timestamp may be (L986–994). A read captured 200 days ago is accepted with a fresh receipt time and kept another 14 days.
- Re-posting old reads moves them into the Tier 2 window and restarts their 14-day clock. The bridge relays Frigate replays with their original times (bridge L48–53), and Frigate keeps its own event history.
- The bridge forwards "update" events as well as "end" events (bridge L168). Partial OCR guesses may become separate stored reads and inflate the § 1805 plates-scanned count (runtime: check against Frigate 0.16 event streams).
- Cameras are derived from reads (L670–671), so a camera silent longer than retention drops off /health entirely.
- The bridge's POST /event has no authentication (bridge L159–196); it is safe only while bound to localhost.

**Fix:** enforce a camera registry at ingest, and reject reads whose camera time is older than RETENTION\_DAYS. Store confidence as empty when unknown. Dedupe on camera, plate and camera time, and forward "end" events only.

### C6. Backups and restore

*High · own claim (backup docstring) · static unless marked*

- `--prune` is opt-in (backup L92, L181–196), and the heartbeat says ok either way (L157–179). Sets holding reads, Tier 3 results, user key hashes, camera credentials and the audit key can pile up unnoticed.
- Even pruned at 14 days, a set holds reads up to 28 days old.
- The evidence folder isn't backed up, so a disk loss destroys unreleased evidence.
- restore unpacks config.tar.gz with no extraction filter (restore L130–134). Before Python 3.14, a doctored set can write outside the config folder.
- restore moves aside only the database, key and checkpoints (L113–115), not `noctua.db-wal` or `-shm`. A stale WAL left by a crashed Janus may replay onto the restored database (runtime).

**Fix:** prune by default, and report the oldest set's age to Janus. Back up bundles on the evidence schedule. Extract with `filter="data"`, and move the -wal and -shm files aside too.

### C7. Retention's fragment scrub skips silently on default installs

*Medium · own claim (item 20) · static*

retention.py reads the audit key only from the environment (retention L62, L69–70), while Janus by default uses the key file. When it skips, it prints a line and still reports ok (L146–150, L183). When it does run, it writes the full 64-character digest (L71–73), but the chain uses 24 characters (janus L226–228), so scrubbed rows never join their TIER3\_REQUEST entries. The test passes only because it sets the environment key and checks the `pref:` prefix (run\_tests L1141–1162).

**Fix:** resolve the key the way checkpoint.py does, truncate to 24 characters, and report failure when the scrub is skipped.

### C8. Smaller script items

*Low · static*

- If VACUUM fails after the purge commits, the purge stands but RETENTION\_PURGE is never chained (retention L156–165).
- Default database paths and ports differ from Janus's (retention L51–53; compact L69–71; janus L140, L144).
- Scripts stream to the sink only if cron's environment carries NOCTUA\_SENTINEL\_SINK.
- sentinel\_audit's "read-only" DB mode opens the target through `sentinel.Chain` (L165), whose constructor creates tables and inserts a row (sentinel L115–136). That alters a furnished forensic copy.
- deploy/ builds a 557-line pre-1.0 Janus, so 1.1 has no install path yet.

## D. Convergence

**Yes: deployment-blocking and code-critical findings remain.** None is architectural, and each fix runs from a few lines to a few dozen. The design holds; three scripts and a handful of handlers don't yet live up to it.

| Severity | Finding | Smallest fix |
| --- | --- | --- |
| Blocking | C1. Tier 3 results kept forever | Retention clears results past RETENTION\_DAYS; the GET refuses older ones |
| Blocking | C2. Witness never publishes | Heartbeat text to stderr; a witness heartbeat only after the push |
| Blocking | C3. Restore swaps the anchor file | Keep the live checkpoints file; chain a RESTORE entry |
| Blocking | B1. Suppression keyed on state and raw text | State-blind, normalized suppression identity; normalize at ingest |
| Blocking | B3. Health ignores chain verification | Add `not chain_ok` to degraded |
| Blocking | B4. Scrub after commit hides the action | Scrub before the write; record the actor in the blocked entry |
| Compact-blocking | B5. Partner picks Tier 3 | Cap shares at Tier 2 |
| Compact-blocking | B6. Gate checks attestations, not audits | Latest result governs; fresh receipts only; evidence in the chain; local recompute; separate signing key |
| Critical | B2. Wrong audit key accepted | Key fingerprint in meta; lock on mismatch |
| Critical | B7. Anchors check only the newest checkpoint | Check every checkpoint; checkpoint.py verifies before signing |
| Critical | B8. Raw input reaches the chain | Coded fields only; "unknown" for failed logins; incremental verify |
| Critical | B9. Account changes unlogged | Chain a config diff on every reload |

What remains is not a code defect.

**Legal questions for the City Attorney**

- § 1804(d): whether reciprocal sharing is an "exchange," and whether raw-read shares fit the "evidence of an offense" exception.
- § 1808(b): its text covers a vehicle registered, solely or jointly, to the person the order is against. The code's suppression is broader, which the statute allows. Excluding warrant-backed Tier 3 results is a policy choice, not a command of the statute.
- Derived data: whether plate\_refs are captured plate data. The question is sharper now, because verifying a partner's checkpoint requires its plate\_ref key.
- Exclusion risk under § 1806 from C1-type retention, and under § 1805(b)(4)(B) if the published rules don't match practice.
- Act 668 of 2025, still unverified against the enrolled bill. No finding here depends on it, since 14 days is under both caps it reportedly sets. If it added Attorney General enforcement, C1 is the kind of violation that enforcement would reach.

**Decisions for the city and the council**

- Key custody: Clerk-side or on the server.
- Who owns the witness repo and checks it.
- Supervisor approval or a mandatory expiry for local hot-list adds.
- A second key, or auditor review, for suppressions.
- How much plate data the auditor role can see.
- Frigate's own retention settings, which keep plates outside NOCTUA's 14 days unless set.
- Who decides Compact membership.
- Whether partner shares are capped at Tier 2. My answer is yes.

**Accepted limitations to state in CANT-DO**

- A same-box insider who holds the key and controls the sink can rewrite up to a day of chain.
- Two colluding supervisors defeat any two-key control.
- Heartbeats are self-reported, except retention's.
- The case gate checks that a case is open, not that it is yours.
- The retention clock runs from receipt, not from capture.
- Stdlib-only Python has no public-key signatures, so third-party verification has to come from witness publication, not HMAC.

## E. Forced change

**Binding condition: no city puts live plate data into NOCTUA until the code declares, in one registry, every place that can hold captured plate data, and retention and the audit tool enforce it.**

1. janus.py declares a `PLATE_DATA_STORES` registry. It lists every table, column and folder that can hold plate text, or plate-derived time and place, with its retention class:
   - reads: 14 days
   - hits: 30 days unless held
   - Tier 3 results: 14 days
   - evidence bundles: until release, then destroyed
   - backups: the reads class
   - spool and sink: plate-free
   - Frigate media: external, with its settings documented
2. retention.py deletes by the registry, not by a hand-kept list.
3. sentinel\_audit.py checks the oldest item in every registered store against its class and fails on any breach.
4. A schema test fails the build when a column or folder that holds plate data is missing from the registry.

**Acceptance:** an adversarial test, written by someone other than the builders, fails on 1.1 as published and passes after the fix. It shows that:

- a 15-day-old Tier 3 result set is gone after retention, and GET /tier3/results refuses it;
- a 15-day-old orphaned bundle folder and an expired backup set both fail the audit;
- adding a new plate-bearing column without a registry entry fails the build.

**Why this one:** C1 is not a slip. It happens every time a fix copies plate data somewhere new so someone can see it: round 2's Tier 3 handoff (my own finding), evidence bundles, backups. The 14-day promise is only as true as the list of places retention looks, and today that list exists nowhere in the code. Round 2's forced change sent every read through one door; this one makes every copy answer to one ledger.

**Runner-up, for the record:** the outside anchor (C2, C3, B3, B7) must publish, be checked across its whole history, and raise an alarm when it fails. Each of those fixes is small and already on the blocking or critical list.

## Appendix 1: what "184/184" does and doesn't show

No test in the suite exercises any of the six blocking findings. I could not re-run the suite, because execution was refused in this session, so this comes from reading it.

- No test runs publish\_witness.sh or restore.py. A search of the suite finds no test of `chain_ok` in /health, Tier 3 results under retention, a non-AR suppression, a partner Tier 3 share, a replayed receipt, a failed audit after a passing one, the rotation seed, AUTH\_FAIL content or a scrub after commit.
- Three tests encode the flaw they should catch:
  - The Compact test opens the gate by posting `ok: true` by hand (L968–971).
  - The retention test plants a Tier 3 row with no results and sets the environment key (L1134–1144).
  - The URL-mode audit test asserts that the auditee's self-report is "independent" (L1029–1032).
- The anchor test rewrites the newest entry (L907–923). It doesn't test a restore, or a rewrite followed by a new checkpoint.
- Round 2 accepted a condition that the suite be written by someone other than the builders. This suite ships as part of the build (TRACK-11 L334–342), so that condition is unmet.

## Appendix 2: statute text relied on

I read these sections in compilations that predate Act 668 of 2025: Justia's 2020 code, and FindLaw's, current as of March 28, 2024. Verify against the official current code before relying on any of it.

- [§ 12-12-1804](https://law.justia.com/codes/arkansas/2020/title-12/subtitle-2/chapter-12/subchapter-18/section-12-12-1804/): (a) use and sharing limited to § 1803(b) purposes, kept no more than 150 days; (b) investigation data destroyed when the investigation ends without charges or the criminal action concludes; (d)(1) no selling, trading or exchanging; (d)(2) data indicating evidence of an offense may be shared with other law enforcement agencies.
- [§ 12-12-1805](https://codes.findlaw.com/ar/title-12-law-enforcement-emergency-management-and-military-affairs/ar-code-sect-12-12-1805/): six-month compilations kept for 18 months; plates scanned, lists checked and matches per list; (b)(4)(A) published rules on obtaining, retaining and destroying data; (b)(4)(B) failure is grounds to exclude evidence.
- [§ 12-12-1806](https://codes.findlaw.com/ar/title-12-law-enforcement-emergency-management-and-military-affairs/ar-code-sect-12-12-1806/): data and derived evidence excluded where disclosure would violate the subchapter.
- [§ 12-12-1808](https://law.justia.com/codes/arkansas/2020/title-12/subtitle-2/chapter-12/subchapter-18/section-12-12-1808/): (a)(1) disclosure only to the registered owner, with the owner's written consent, or as the Driver's Privacy Protection Act permits; (b) under a valid protection order, no disclosure except as the result of a match.
