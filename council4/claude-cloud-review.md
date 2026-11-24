# NOCTUA 1.2 — Round 4 hostile review (Claude cloud seat)

Nov 24, 2026 · @Corey Spangler

**MODEL/EFFORT USED:** Claude Opus 5.5 (`claude-opus-5-5`), as this session reports itself. I can't see the UI's effort selector from inside the session, so please read the effort level off the UI and correct this line if it isn't Max. Fable 5.2 and credit-gated tiers were not used.

## Verdict: NOT CONVERGED

**NOCTUA 1.2 fixes most of round 3, but 39 defects reproduced against the shipped code, and two of them block any live deployment.** I ran 41 runtime attacks on an unmodified copy of the attached files: 39 reproduced a defect, one confirmed a 1.2 fix works, and one negative control behaved correctly. Each fix is small.

**Blocking (no live plate data until fixed):**

- **The nightly hot-list job empties the hot list (B-1).** `hotlist_sync.py` deactivates every entry that has no expiry date, then retention deletes the row. /health requires that job, so a green dashboard means an empty stolen-vehicle list.
- **The witness reports "witnessed" when nothing left the building (B-2).** With no repo configured, or with a repo whose `git commit` fails, the script exits 0 and /health shows the witness job ok.

**Compact-blocking (sharing stays off until fixed):**

- **A partner gets the full 14-day store by asking for tier 1 (B-3).** Only tier 3 is refused; tier 1, or `true`, runs the historical search.
- **One signed audit report can be replayed forever, and refiled under another partner's name (B-4).** The gate's "no cross-audit" leg is an attestation again.

**Critical (small, fix before deployment):**

- A protection order doesn't reach hits that existed before it; a detective still sees, verifies and exports them (B-5).
- The audit tool still anchors only the newest checkpoint, and `checkpoint.py` signs a rewritten chain without checking (B-6), which is round-3 B7.
- An account added while Janus is stopped goes live with no chain record (B-7), which is round-3 B9.

**What 1.2 got right, verified by reading and by running it:** the Tier 3 result archive is gone (C1), a broken chain now degrades /health (B3), suppression is canonical and state-blind (B1), a wrong audit key refuses to start (B2), the checkpoint parse is fixed (C2), restore never overwrites the live anchor (C3), retention runs by the registry, Ed25519 signing is separate from the HMAC key, the gate reads the latest audit row, the chain\_auditor fence holds, ingest stops fabricating state and confidence, and backups prune by default.

**Tally of new findings (section B):** 2 blocking, 2 Compact-blocking, 3 critical, 7 high, 9 medium, plus a group of low. Of my 26 round-3 findings, 10 are fixed, 9 are fixed but wrong, 3 are not fixed, 2 are open policy calls and 2 are mixed (section A).

## How I worked

**This round I could run the code, so most findings are reproduced, not inferred.** Round 3's session refused execution; this one didn't.

- **Read in full:** `janus.py` (3,935 lines), `sentinel.py` (712), all 12 scripts, `run_tests.py` (1,841), TRACK-12-REPORT, COMPACT.md, the round-3 synthesis, the brief, and my round-3 review.
- **The builders' suite, re-run in a sandbox** (Python 3.13.18, OpenSSL 3.0.13, git 2.43.0): 243 checks, 243 passed, exit 0. The 3 demo checks were skipped because `demo/seed_demo.py` isn't in the attachments. That matches the orchestrator's 246/246 less the demo.
- **My own attack suite** (Appendix; files delivered with this review), run against an unmodified copy of the attachments: 41 checks. 39 reproduced a defect, A9b confirmed a 1.2 fix works, and A27, a negative control, correctly did not reproduce. A clean end-to-end re-run gave the same result. The suite borrows the builders' helpers only to start servers and send requests.
- **Line numbers** refer to the attached 1.2 files. Script lines are per file, not per line of the combined batch file.

**Tags used below:**

- **runtime (A*n*)**: reproduced by attack A*n* in the Appendix.
- **static**: follows from the code as written; not run.
- **own claim**: judged against NOCTUA's docstrings, COMPACT.md, TRACK-12 or the round-3 dispositions.
- **statute**: judged against Ark. Code §§ 12-12-1801–1808 as compiled before Act 668 of 2025.

**Not checked, and why:** `deploy/` and `demo/` weren't attached. A12 uses Frigate's documented event shape, not a live Frigate 0.16 stream. Act 668 is flagged, not settled.

## A. My round-3 findings, checked against 1.2

**Of 26 findings, 10 are fixed, 9 are fixed but wrong, 3 are not fixed, 2 are open policy calls and 2 are mixed.** The forced change is built but doesn't yet meet its own acceptance criteria. Lines are janus.py unless another file is named.

| # | Round-3 finding | 1.2 status | Evidence in 1.2 | What's left |
| --- | --- | --- | --- | --- |
| B1 | Suppression keyed on state and raw text | FIXED | plate\_ref hashes the canonical plate only (sentinel L103–109); ingest stores canonical + raw (L1585, L1627–1631); search filters in SQL before LIMIT (L842–874); hot-list conflict check is canonical (L1731) | Hits from before an order stay visible (B-5). 1.1-era suppression refs are never re-keyed on upgrade (static) |
| B2 | Wrong audit key accepted | FIXED | Fingerprint pinned in meta, mismatch locks (L559–582); locked boot exits 3 (L3910–3916) | First boot over an older chain pins any key (A28); a locked boot eats the restore marker (A29) |
| B3 | /health ok on a broken chain | FIXED | chain\_ok in `degraded` and in `ok` (L3818–3843); alert\_check names it (alert\_check L98–101) | /health still says ok in other broken states: B-2, B-9, B-11, B-17 |
| B4 | Scrub after commit hides the actor | FIXED as raised | Scrubber sanitizes, never raises (sentinel L401–426); handler appends join the handler's transaction (sentinel L617–621) | Commit-before-log remains on seven paths (B-18) |
| B5 | Partner picks Tier 3 | FIXED-BUT-WRONG | tier above 2 refused (L3151–3159) | tier 1 or `true` runs the full-scope search (L3227): B-3 |
| B6 | Gate checks attestations, not audits | FIXED-BUT-WRONG | Latest row governs (L3164–3171, L1191–1194); receipts must name the newest checkpoint (L2870–2902); compact.py recomputes the chain (compact L94–119); Ed25519 key separate from the HMAC key | Signed reports replay and re-bind (B-4); the gate never rechecks receipt age (B-15); compact.py falls back to the checkpoint's own key (B-14); sentinel\_audit still labels the auditee's self-report "independent" (sentinel\_audit L207–209) |
| B7 | Anchors check only the newest checkpoint | NOT FIXED outside Janus | Janus's startup anchor checks every checkpoint (L622–662), confirmed by A9b | checkpoint.py signs without verifying (checkpoint L80–103); sentinel\_audit anchors only the newest (sentinel\_audit L75–89, L287–302): B-6 |
| B8 | Raw input reaches the chain | FIXED-BUT-WRONG | AUTH\_FAIL hashed (L740); categories are an enum (L198–205); case and why hashed (L268–269) | `agency` is scrubber-exempt, so any role writes raw text (B-13); AUTH\_FAIL grows per distinct name (A20); hashes are unsalted (A36); raw ids still chained (L1783, L2171) |
| B9 | Account and case changes unlogged | FIXED-BUT-WRONG | CONFIG\_CHANGED on a content change while running (L316–326) | Hash only, no structural diff; nothing chained for changes made while stopped (B-7); append failures swallowed (L325–326) |
| B10 | Suppression oracle and side door | FIXED-BUT-WRONG | Flagged hits verify and export only via supervisors (L1796–1807, L2408–2417) | Oracle at /hotlist (L1731–1740); suppressed counts on /stats for detectives (L1243–1245); sequential hit ids (L370–371); supervisor full-history export of a suppressed hit (L2439–2454); the stale flag (B-5) |
| B11 | Detectives read the chain | FIXED | /audit\* limited to supervisor, auditor, chain\_auditor (L194, L3394–3399) | Partners now read it all, and case hashes reverse in 0.05 s (B-21) |
| B12 | Tier 2 and share justifications kept nowhere | NOT FIXED for Tier 2 | Shares store `why` (L3228–3234) | Tier 2 chains only why\_hash; no table keeps the text (L3762–3791). Tier 3 and share text is nulled at 14 days: a policy call |
| B13 | Rotation seed decorative, wrong table | FIXED-BUT-WRONG | Seed now permutes (L3871–3907; rotation L62–85); dates and period validated (L3050–3059); two-key void | Publisher picks the seed; no-seed publish crashes; duty flags rounds that haven't started; witness duty is any-role and unchained (B-16) |
| B14 | § 1805 report residuals | FIXED | Snapshot body hash chained (L2030–2035); list registry (L1500–1518, L1741–1751); per-list "not yet reported" (L1087) | — |
| B15 | Sink spool fragile | NOT FIXED, now worse | Spool lines still parsed outside the try (sentinel L560–562) | A torn line now rolls back every ALERT read while /health stays green (B-9) |
| B16 | One supervisor can blind any plate | NOT FIXED (policy) | Single-supervisor placement unchanged (L1905–1962) | Now also empties already-executed Tier 3 results; the builders' suite tests it as a feature (run\_tests L860–869) |
| B17 | Who reads Tier 3 results | Partly answered (policy) | Auditor removed (L3566) | Any supervisor, the approver included, reads any set (L3584) |
| B18 | Smaller items | Mixed | Fixed: suppression filter before LIMIT (L866–874); cycle-start validation (L3050–3055); custody ints and HOLD hit ids (L1142, L1858–1863); /health authenticated | Not fixed: free-text expiry, now the cause of B-1 (L1761); one CLOCK\_SKEW per read when a camera runs ahead (L1694–1697); emergency path (L2286–2302) |
| C1 | Tier 3 results kept forever | FIXED | Ids only (L2187–2201, L2307–2316); retention nulls them (sentinel L199–212); live re-resolution (L3617–3667) | Hits re-resolve through the stale flag (B-5) |
| C2 | Witness never publishes | FIXED-BUT-WRONG | One JSON line on stdout (checkpoint L114–117); parsed (publish\_witness L74–79); heartbeat after publish (L99–100) | A local folder counts as witnessed (L81, L87); `git commit … \|\| true` (L89): B-2 |
| C3 | Restore swaps the anchor file | FIXED | Live checkpoints never overwritten (restore L182–189); RESTORE marker chained at boot (restore L224–227; L702–720) | Manifest still checked with the set's own keys (restore L78–85, L116–133), refusal after the swap (B-8); acceptance re-triggers (B-19); marker lost on a locked boot (B-20) |
| C4 | Holds and evidence never expire | FIXED-BUT-WRONG | Released bundles destroyed by retention (retention L222–241); re-export deletes its predecessor (L2479–2514) | Review dates uncapped (L1848–1850); a disposition with no export protects a hit forever (B-11); orphaned bundles undetected (B-17) |
| C5 | Ingest and bridge trust too much | FIXED-BUT-WRONG | Camera registry (L1586–1595); no fabricated state or confidence (L1600–1606; bridge L145–156); persistent dedupe (L1607–1616); bridge secret (bridge L197–204) | Dedupe keeps the first OCR guess and drops the final read (B-10); no camera-timestamp age limit (L1617–1626) |
| C6 | Backups and restore | FIXED as raised | Prune by default (backup L228–243); evidence included (backup L165–175); filter="data" (restore L201, L213); -wal and -shm moved aside (restore L165–167) | Sets still hold reads up to 2 × RETENTION\_DAYS (policy); B-8; B-17 |
| C7 | Retention scrub skips silently | FIXED | Key resolved like Janus, no key = failure (retention L245–252); one frag\_ref (sentinel L112–118); secure\_delete (retention L259) | — |
| C8 | Smaller script items | Mixed | Audit DB mode read-only (sentinel\_audit L253–258); default paths aligned | The purge still commits before RETENTION\_PURGE is chained (retention L278 vs L304); `deploy/` not attached, can't check |
| E | Forced change: PLATE\_DATA\_STORES | Built; acceptance not met | Registry (sentinel L146–266); retention by registry (retention L245–313); audit by registry (sentinel\_audit L92–161); /health (L1254–1338); schema test (run\_tests L1086–1123) | Of my four acceptance behaviours, the Tier 3 one is met; orphaned bundle not met (A35); expired backup set partly (A30, A35); "a new plate column fails the build" not met (A16). The test was written by the builders |

## B. Attacks on what's new

**The new machinery is real, but in several places it accepts the evidence's own word, and three shipped jobs report success on the wrong thing.** Findings are ordered by severity. Each names its standard, its tag, and the smallest fix.

**Where the brief's attack list landed:**

| Brief topic | Result | Findings |
| --- | --- | --- |
| Registry completeness, schema test | Incomplete; the test matches column names, not content | B-13, B-17, B-22 |
| Ed25519 via openssl | Signing and key separation work; three verifiers fall back to self-supplied keys | B-8, B-14, B-22; A27 negative control passed |
| chain\_auditor fence | The fence holds; what it can read and do through those five paths is too much | B-21 |
| Same-transaction appends | Handlers mostly fixed; seven paths still commit before logging | B-18, B-12, B-9 |
| Compact gate and receipts | Latest-row works; tier 1, report replay and receipt age break it | B-3, B-4, B-14, B-15 |
| Rotation | Seed permutes, but the publisher picks it; duty tracking measures the wrong thing | B-16 |
| Restore and the anchor file | Never-overwrite holds; the signature check is self-certifying | B-8, B-19, B-20 |
| Key-continuity lockout | Mismatch and missing key both refuse to start; gaps at upgrade and after restore | B-20 |

### Blocking

**B-1. The nightly hot-list job empties the hot list.** *Blocking · own claim (hotlist\_sync docstring: it sweeps memberships "whose expires\_ts has passed") · runtime A1, A1b*

- /hotlist stores a missing expiry as an empty string (L1761). hotlist\_sync deactivates rows where `expires_ts IS NOT NULL AND expires_ts < now` (hotlist\_sync L75–78), and `''` sorts before every timestamp.
- Run: a stolen-vehicle entry added with no expiry was deactivated and chained HOTLIST\_EXPIRED on the first sweep. The next read of that plate stored silently, with no ALERT. Once its added\_ts passed 14 days, retention deleted the row (A1b).
- /health counts hotlist\_sync as a required job (L181–183). The operator who makes the dashboard green runs the job that empties the list. Janus's own check at ingest handles `''` correctly (L1652), so only the script is wrong, and the builders' test never checks that a no-expiry entry survives (run\_tests L1723–1726).
- **Fix:** store NULL for no expiry; reject expiries that aren't ISO 8601 at /hotlist; migrate `''` to NULL at boot; add `AND expires_ts <> ''` to the sweep; test that an open-ended entry survives.

**B-2. "Witnessed" with no witness.** *Blocking · own claim (S6: the witness heartbeat is posted "ONLY after the publish actually succeeds"; the checkpoint is published "OUTSIDE the system") · runtime A6a, A6b*

- No repo configured: the default WITNESS\_REPO is created by `mkdir -p` (publish\_witness L81), and a folder without `.git` counts as published (L84–87). Run: exit 0, /health witness job ok.
- Repo configured, but `git commit` fails, as it does for a service account with no git identity: `commit … || true` (L89) hides it, and `git push` then succeeds with nothing to send (L90). Run: exit 0, witness ok; the remote still held only its initial commit, and the checkpoint sat uncommitted in the clone.
- The witness is the only defense against an insider who holds the server's key. This is round-3 C2 (silently absent) with a green light added. The builders' S18 test runs the script against a local folder and counts that as a pass (run\_tests L1193–1205).
- **Fix:** fail unless WITNESS\_REPO is a git repo with a remote; drop `|| true`; after the push, fetch and confirm the checkpoint's root is in the remote's file before posting the ok heartbeat.

### Compact-blocking

**B-3. Tier 1 is a full-history share.** *Compact-blocking · own claim (COMPACT.md: "Historical (Tier 3) data never moves through the Compact") and the open § 12-12-1804(d) question · runtime A2, A2b*

- The share path refuses a tier above 2 or below 1 (L3151–3159), then runs `run_search(frag, "tier2" if tier == 2 else "full")` (L3227). Tier 1, or JSON `true` (a Python int), takes the full branch.
- Run: tier 2 returned no reads; tier 1 returned a 25-hour-old and a 12-day-old read of the same plate; tier 3 got 403. SHARE\_OUT chains `"tier": 1` or `"tier": true`, so the chain never says the wall was skipped.
- **Fix:** refuse anything but integer 2 (reject booleans); always call `run_search(frag, "tier2")` on this path; test tier 1 and `true`.

**B-4. Signed audit reports replay forever and across partners.** *Compact-blocking · own claim (COMPACT.md: "a bare boolean is never accepted"; S8) · runtime A3*

- /compact/audit-result verifies the signature over `report`, then files the row under the body's `agency` (L2782, L2813–2818), stamped `now_iso()`. It never checks report.agency, report.ts, the checkpoint the report names, or whether that report hash is already on file.
- Run: a signed report dated 2025-01-01 was accepted and stamped today. The same signed body, re-posted by a supervisor with `agency: agency-c`, recorded a passing audit of agency-c, and /compact/partners showed agency-c `last_audit_ok: true`.
- One signed pass, captured once, keeps any partner's audit leg open for as long as someone re-posts it. That is round-3 B6, an attestation rather than an audit, behind a signature.
- **Fix:** require report.agency to equal the body's agency, report.ts within an hour of receipt, and report.checkpoint to equal that partner's newest checkpoint; refuse a report hash already on file; chain the audited root and entry count.

### Critical

**B-5. A protection order doesn't reach hits that already exist.** *Critical · own claim (L3446–3448: suppressed hits "are not listed here AT ALL"; S2: suppressed rows are excluded "NOW, not as they were when the search ran"; S3: verify and export only via the supervisor queue) · runtime A5*

- hits.suppressed is set once, at ingest (L1666). Nothing updates it when a suppression is placed. /hits (L3444), Tier 3 re-resolution of hits (L3641), /verify (L1796) and /evidence/export (L2408) all read that flag. Only /search uses the live join (L842–874), which is why the builders' tests pass.
- Run: a hit on PHS100, then a protection order on PHS100. A detective still saw the hit with its plate on /hits and in Tier 3 results, verified it, and exported it with its ±1 h reads. /search hid it.
- Who it serves: an officer who hot-listed a vehicle before its owner got an order keeps that vehicle's last 30 days of hits (camera and time) and can pull more through export.
- Statute: § 12-12-1808(b) allows disclosure "as the result of a match", so this breaks NOCTUA's own stricter promise rather than the statute.
- **Fix:** at placement, `UPDATE hits SET suppressed=1 WHERE read_plate=? OR entry_plate=?`; better, have /hits, Tier 3 hits, verify and export use the same live join search uses.

**B-6. The audit tool still reads only the newest checkpoint, and checkpoint.py signs anything.** *Critical · own claim (S6, S16) · runtime A9, A9b*

- Run: an insider rewrote entry 10, already covered by a checkpoint at entry 26, and recomputed every later hash. checkpoint.py signed the rewritten root without a check (checkpoint L80–103). `sentinel_audit --db` then reported 0 failures and 27 ok, because it anchors only the max-entries checkpoint (sentinel\_audit L75–89, L287–302).
- Janus's startup anchor flagged the same rewrite (A9b), so the round-3 fix landed in janus.py only. sentinel\_audit is the tool an auditor would point at the witness copy, and it never reads the older witnessed checkpoints that disagree. That is round-3 B7, unchanged where outside review needs it.
- **Fix:** sentinel\_audit checks the chain hash at every checkpoint line, in both modes, one indexed lookup each; checkpoint.py runs `verify_detached` and the same check, and refuses to sign on any disagreement.

**B-7. Accounts added while Janus is stopped leave no record.** *Critical · own claim (S13: account and case-list changes are "auditable events") · runtime A13*

- `_reload_config` chains CONFIG\_CHANGED only when a hash it already holds changes (L316–326). The first load at boot records the hash silently, and the SYSTEM entry carries no config hash (L3921–3930).
- Run: stopped Janus, added `ghost.sup` as a supervisor in users.json, started it. ghost.sup approved a Tier 3 search; the chain held no CONFIG\_CHANGED entry at all.
- Every two-key control assumes the set of keys is itself audited (round-3 B9). This also widens B-8: a restored users.json loads unchained.
- **Fix:** keep the last chained hash of users.json, cases.json and cameras.json in meta and in SYSTEM; at boot, chain CONFIG\_CHANGED with a structural diff (accounts added or removed; role, disabled and key changes; cases added or removed) when they differ.

### High

**B-8. Restore lets the backup set vouch for itself.** *High · own claim (restore docstring; S6) · runtime A7, A8*

- The Ed25519 check uses the set's own `signing_pub.pem` (restore L116–133), and the HMAC check prefers the set's own `audit_key` to the live one (restore L78–85). An attacker signs with a fresh key and drops the HMAC; nothing objects. This is round-3 C3's second point, unchanged.
- Run (A7): a set carrying an extra supervisor in users.json, signed with a new attacker key, restored with exit 0 and "manifest verified". It installed the extra account, and the attacker's key as the agency's signing key.
- Run (A8): a set the tar filter rejects prints "REFUSING TO RESTORE", but only after the live database and keys were moved aside and replaced (restore L165–168 run before L191–204). The 30-entry live chain became the 2-entry backup chain, with no restore marker.
- Who can do it: anyone who can write to the backup store, usually a NAS that is less protected than the server.
- **Fix:** verify against the live install's signing key, or a fingerprint the operator types, never the set's; unpack and check every tarball into a staging directory before any live file moves.

**B-9. One torn spool line silences hot-list alerts while /health says ok.** *High · own claim (S5 health truth; sentinel: sink failures "never raise") · runtime A11*

- `_stream` parses spool lines outside its try block (sentinel L560–562). Since 1.2, ALERT appends join the ingest transaction, so the exception rolls back the read and its hit.
- Run: sink configured, one truncated spool line. The stolen-plate read got a 500 and was lost; a plain read stored fine; /health said ok, sink\_up true, 0 errors.
- A power cut while the sink is down is enough to leave a torn line. The bridge doesn't queue, so those reads are gone.
- **Fix:** parse spool lines inside the try; move bad lines to `<spool>.bad`; record the error in sink\_state so /health degrades; write the spool through a temp file and rename.

**B-10. The bridge keeps Frigate's first OCR guess and drops the final one.** *High · own claim (bridge docstring: "end" carries the final OCR; S4 dedupe) · runtime A12, against Frigate's documented event shape; confirm on the pinned Frigate version*

- The bridge forwards "update" events (bridge L217). Janus dedupes on (camera, event\_id) and answers "duplicate" to every later post of that event (L1607–1616).
- Run: an update reading STL77 (0.61), then the end event reading STL777 (0.93, hot-listed). Janus stored STL77, answered "duplicate" to the end event, and raised no ALERT.
- Two harms: missed alerts on the plates the system exists to find, and a wrong plate stored against a real vehicle's time and place.
- **Fix:** forward "end" events only; or let Janus replace the event's read with a later, higher-confidence plate in the same transaction and re-run matching.

**B-11. Holds and dispositions keep plate data past 150 days, with green health.** *High · statute § 12-12-1804(a) (150 days) and (b) · runtime A19, A37*

- A hold's review date is whatever the caller sends (L1848–1850), and a hit hold needs no case (only case holds are gated, L1840–1847). A disposition needs no export and no case (L2622–2664), and retention spares any hit with an unconfirmed evidence row (retention L140–147).
- Run: two 400-day-old hits (plate, camera, time) survived retention, one under a hold dated 9999-12-31 and one under a detective's unconfirmed disposition. /health: ok, no breach, overdue\_holds 0. Overdue holds never enter `ok` (L3827–3829).
- A37: HOLD\_DAYS has no ceiling; only RETENTION\_DAYS and the Tier 2 window are capped (L169–177). HOLD\_DAYS=400 boots, a 300-day-old hit survives, and SYSTEM doesn't record hold\_days.
- **Fix:** cap review dates (for example 180 days, renewable with a chained entry); require an open case for hit holds and an export for dispositions; refuse HOLD\_DAYS above 150; degrade /health on overdue holds and on any held item older than 150 days; chain hold\_days in SYSTEM.

**B-12. The kind and ts columns are outside the hash.** *High · own claim (sentinel: editing any historical entry "breaks every hash after it") · runtime A10*

- verify() checks seq continuity, prev, and the hash of payload, nothing else (sentinel L429–442). The kind and ts columns drive custody excerpts (L1135–1138), the share rate limit (L3208–3212) and what /audit displays (sentinel L673–680).
- Run: changed the kind of an EVIDENCE\_EXPORT row and a SHARE\_OUT row to SYSTEM and their ts to 2001. verify() still said ok. Those entries would drop out of every later custody excerpt and rate-limit count.
- **Fix:** verify() also checks kind and ts against the payload, or those queries read them from the payload.

**B-13. Any logged-in account writes raw text into the permanent chain.** *High · own claim (sentinel: chain entries "NEVER contain plate text") · runtime A21, A21b*

- The scrubber exempts every field named `agency` (sentinel L385). When the caller isn't that partner, SHARE\_BLOCKED chains the request body's agency verbatim (L3138–3146).
- Run: patrol posted `{"agency": "ABC123"}` to /share/query, and the chain now holds "ABC123" verbatim. /compact/suspend of a partner that doesn't exist answers 200 and chains whatever text it's given (A21b).
- The chain can't be purged without breaking it, partners read it through /audit/range, and the audit table isn't in the registry. Text that lands there is permanent, unregistered storage.
- **Fix:** exempt `agency` only when it names a registered partner, and chain a hash otherwise; register the audit table as a store whose plate-free claim the canary test checks.

**B-14. compact.py and sentinel\_audit fall back to the checkpoint's own key.** *High (Compact) · own claim (S8: verify against "the partner's registered public key") · runtime A23*

- Both key flags are optional. With neither, compact.py verifies against the key the checkpoint carries (compact L184) and counts a missing fingerprint check as a pass (compact L230). sentinel\_audit's URL mode does the same (sentinel\_audit L214–217).
- Run: B's checkpoint re-signed with an unregistered key. With the registered key compact.py exited 2, correctly. With no flag it exited 0: checkpoint\_signature true, receipt posted, passing audit recorded.
- **Fix:** refuse to run without the registered key; better, read it from our own partners table, which already stores it (L2748–2759).

### Medium

**B-15. The share gate never rechecks a receipt's age.** *Medium (Compact) · own claim (COMPACT.md: each leg "fresh") · runtime A4.* Freshness is checked only when a receipt is posted (L2892–2902); the gate compares root and entries only (L3172–3180). Run: receipt rows dated 2020 still opened the gate. If a member's checkpoint job stalls, its partner's last receipt stays valid indefinitely. **Fix:** the gate also requires the receipt's checkpoint\_ts within 26 hours.

**B-16. Rotation: the publisher picks the seed, and duty tracking measures the wrong thing.** *Medium · own claim (COMPACT.md: "the anti-capture mechanism"; S12) · runtime A14a–c, A25*

- Seed: /compact/rotation takes any seed (L3083–3086). Over 200 trials, a chosen auditor for a chosen agency took 3.2 tries on average and 14 at most. rotation.py derives its seed from public inputs (rotation L62–64), so the two tools disagree on the property that matters.
- No seed: a 500, because `uuid` is never imported (L3085).
- Duty: each round counts receipts from, and our audits of, that round's auditor (L3264–3274). That is daily-gate traffic, not the round's assignment. A cycle starting 2027-01-04 already listed agency-a, -b and -d as delinquent, because rounds that haven't started count as "filed in neither" (L3287–3293).
- Witness duty: /compact/witness has no role check and no chain entry (L3002–3025). The ingest service account filed one for agency-a.
- Static: the publisher can't be in its own rotation unless it registers itself as its own partner (L3044–3049); the signature covers neither cycle\_start nor period\_days (L3090–3100); a void deletes the schedule row (L2991).
- **Fix:** derive the seed as rotation.py does, or from a public value fixed before publication; count only rounds that have started and involve us; role-check and chain witness attestations; sign the dates; mark voided cycles instead of deleting them.

**B-17. The registry's enforcement misses relocated and orphaned stores, and the schema test matches names.** *Medium · own claim (S1) and my round-3 forced change · runtime A16, A30, A35*

- A16: the builders' own `suite_schema` passed a database holding plate data in `reads.vehicle_tag`, a new `ocr_cache` table 400 days old, and a file beside the database. It matches column names against `plate|frag|results` and checks directories only (run\_tests L1099–1119).
- A30: with NOCTUA\_BACKUP\_DIR set, the natural off-box setup, a 40-day-old backup set is invisible to /health, which looks only beside the database (L1312–1326).
- A35: a 40-day-old orphaned bundle folder, on disk with no evidence row, passes both /health and sentinel\_audit. An expired backup set only warns in sentinel\_audit's DB mode (sentinel\_audit L152–155).
- Static: free text that never expires and isn't registered: `holds.reason`, `witness_attestations.detail`, `share_queries.case_ref`, and the audit table itself.
- **Fix:** the carried-over forced change in section C.

**B-18. Seven write paths still commit before they log.** *Medium · own claim (S11: data writes and chain appends "commit in ONE transaction") · static, plus runtime A25*

- Janus: /compact/suspend (commit L2925, append L2926); /compact/reinstate (L2960, L2961); both steps of /audit/anchor-accept (`_meta_set` commits at L556; L2074, L2075); both steps of /compact/rotation/void (L2994, L2995). /compact/witness never appends at all (A25).
- Scripts: retention commits the purge (retention L278), then runs the WAL checkpoint and VACUUM with retries before chaining RETENTION\_PURGE (retention L299–309). A crash or a VACUUM error such as a full disk leaves an unlogged purge. hotlist\_sync commits deactivations (hotlist\_sync L84) before chaining them (L87–92).
- Retention destroys overdue bundles with no per-hit EVIDENCE\_DESTROY entry (retention L222–241), so a custody record ends at release.
- Participating appends stream to the sink before the transaction commits (sentinel L664–665), so a rollback leaves a sink line the chain never got.
- **Fix:** open the transaction before the data write on these paths; in the scripts, append on the same connection inside the purge's transaction; chain one EVIDENCE\_DESTROY per bundle.

**B-19. After an accepted rollback, every restart re-raises the anchor alarm.** *Medium · own claim (S6: a restart on accepted state "does not re-trigger") · runtime A15.* Acceptance records the newest checkpoint's root and entries (L2068–2071) and matches on them (L676–687). The next good daily checkpoint changes "newest", so the old, accepted disagreement fires again. Run: rollback, mismatch, two-key accept, cleared; the chain grew, a good checkpoint was cut, and the restart raised the same mismatch (bad entries `['26']`). Alarm fatigue on the one alarm that catches a rollback. **Fix:** store the accepted set of bad checkpoint lines, and raise only on a line outside it.

**B-20. Key lockout: trust on first use at upgrade, and a lost RESTORE.** *Medium · own claim (TRACK-12: "any boot that cannot prove key continuity" is locked) · runtime A28, A29*

- A28: with no fingerprint stored, the first boot pins whatever key it gets (L569–571). Run: a pre-existing 5-entry chain and an arbitrary key started normally. That first 1.2 boot over a 1.1 chain is exactly the migration where round 3's wrong-key case happens, and 1.1's HMAC checkpoints could have tested the key.
- A29: `_consume_restore_marker` deletes the marker even when it can't chain RESTORE (L713–720). Run: restore, then a boot without the key exited 3 and deleted the marker; the next good boot chained no RESTORE.
- **Fix:** before pinning over an existing chain, test the key against a 1.1 HMAC checkpoint or a stored suppression ref, and lock on failure; keep the marker until RESTORE is chained.

**B-21. Partners can read case numbers and stall ingest.** *Medium · own claim (COMPACT.md: the chain\_auditor credential "cannot touch your data") · runtime A17, A18, A26, A36*

- The fence itself holds: chain\_auditor reaches only the five GET paths (L192–193, L3382–3386) and has no POST surface (L1470–1473). The builders' sweep and my reading agree.
- A36: case\_hash is unsalted SHA-256 (sentinel L121–125). Reading /audit/range, the case number behind a QUERY entry reversed in 0.05 s by trying all 110,000 "YYYY-NNNN" values for 2020–2030; it sits beside the officer's username and timestamp.
- A18: /audit/verify runs an uncached full verify on the shared connection under the global lock (L3408). At 600,003 entries one call took 1.18 s, and a hot-list read waited 1.14 s behind it (baseline 0.002 s). /health's "detached" verify also runs under that lock (L3354, L1154–1168), contrary to its docstring. Every /hits view and heartbeat grows the chain, and the bridge gives up at 10 s (extrapolated, not measured: about 5 million entries).
- A17: `/audit?limit=-1` returns the whole chain in one response (L3401–3403; `min(-1, 1000)` is −1, which SQLite reads as no limit).
- A26: sentinel\_audit's URL mode needs /health, which chain\_auditor can't read, so the tool "a member agency audits another member with" fails on the credential partners are issued.
- **Fix:** make case\_hash and why\_hash HMACs under the audit key (partners re-hash payload bytes; they never need to reverse them); cache /audit/verify with the health result, or verify incrementally; clamp limit to 1–1,000; give sentinel\_audit a chain\_auditor mode.

**B-22. Backups carry both keys that "never leave the box".** *Medium · own claim (S7, COMPACT.md: the audit key "never leaves the box") · static.* Every set copies the Ed25519 private key (backup L185–193) and, on key-file installs, the audit key (backup L178–184), unencrypted. The audit key can't be rotated without orphaning every plate\_ref, so a leaked set is a permanent leak, and partners hold the chain those refs sit in. **Fix:** leave both keys out of nightly sets and back them up once into the Clerk's custody; or encrypt sets with `openssl cms` to a recipient key held off the server.

**B-23. Smaller medium items.**

- DELETE /hotlist with a missing or different state answers 200 and chains HOTLIST\_REMOVE, while the entry stays active (A24; L3338–3349).
- A hit hold placed with ref "03" is chained as hit 3 and counted as held by /health, but retention compares text and deletes the hit (A34; retention L145 vs L1277–1280, L1858–1863).
- sentinel\_audit fails every legitimately held hit older than 30 days, because it ignores holds and evidence (A19b; sentinel\_audit L113), while /health excludes them. The two checkers disagree.
- No camera-timestamp age limit: a replayed 200-day-old read gets a fresh 14-day clock and enters the Tier 2 window (L1617–1626; static).
- 1.1-era suppression refs are never recomputed with 1.2's formula on upgrade, so `is_suppressed()` misses them (static).

### Low

- 300 distinct usernames add 300 permanent AUTH\_FAIL entries; the throttle is per name (A20; L743–757).
- `/report?snapshot=x` is a 500 (L3514); one CLOCK\_SKEW entry per read when a camera's clock runs ahead (L1694–1697); a partner's key isn't checked to be Ed25519 (L2737–2744); reinstate orders audits by ts while the gate orders by id (L2946 vs L3166).
- The Compact has no off switch in code. It is off only while no partner is registered and no partner account exists.
- Negative control A27: OpenSSL 3.0.13 creates the private key 0600 itself, so `ensure_signing_key`'s later chmod (sentinel L294–297) leaves no window on this version. Check on any OpenSSL 1.1.1 host.

## C. Convergence ruling: NOT CONVERGED

**Three of the four conditions fail; the fourth passes but doesn't prove enough.**

| Condition | Ruling | Why |
| --- | --- | --- |
| 1. No deployment-blocking or code-critical finding | Not met | B-1 and B-2 block deployment; B-3 and B-4 block the Compact; B-5, B-6 and B-7 are critical |
| 2. Every prior forced change implemented or answered | Partly met | The registry spine is built and is the best thing in 1.2, but its acceptance criteria aren't met (A16, A30, A35) and its tests were written by the builders. Gemini's 1,000-append test is done (run\_tests L1023–1042). ChatGPT's round-2 certification condition isn't in my attachments, so I can't rule on it |
| 3. Only CANT-DO limits and legal questions remain | Not met | Everything in sections B-1 to B-14 is a code defect with a small fix |
| 4. Re-tests pass | Met, but not sufficient | I reproduced 243/243 (246 less the 3 demo checks). None of the 39 reproduced defects is caught |

**What 246/246 proves, and what it doesn't.** It proves the happy paths and the 26 round-3 attacks as the builders framed them. Four tests encode the flaw they should catch:

- The witness test counts a local folder as a publication (run\_tests L1193–1205), which is B-2.
- The tar-slip test re-signs the manifest with the set's own key and calls it "validly re-signed" (run\_tests L1363–1405), which is B-8's hole stated as an assumption. It never checks whether the live database was already swapped.
- The hotlist\_sync test checks that the expired entry went, not that the open-ended one stayed (run\_tests L1723–1726), which is B-1.
- The schema test matches column names (run\_tests L1099–1119), which is B-17.

Two more can't see their defect: the URL-mode audit test uses an auditor account rather than chain\_auditor (B-21), and the rotation status test checks only the number of rounds (B-16). My round-2 and round-3 condition stands: the acceptance suite must be adversarial to the builders' assumptions and written by someone else. The Appendix suite is offered as a start.

### Carried over: finish round 3's forced change

The registry exists; make its completeness provable by content, not by name.

1. Replace the name-matching schema test with a canary test. Push known canary plates through every way in: ingest, the bridge, /hotlist, suppressions, Tier 3, shares, evidence, holds, partner case\_refs, chain fields.
2. Run every shipped job (hotlist\_sync, retention, backup, restore, checkpoint, publish\_witness) with the clock advanced past each class.
3. Scan every byte at rest for the canaries in raw, spaced and normalized forms: every column of every table, the audit chain included, and every file under the database, evidence, backup, sink and spool locations, wherever the environment puts them.
4. Fail on any canary outside a registered store, or inside one past its class age without a hold tied to an open case. /health and sentinel\_audit check orphans and relocated directories the same way.

### The round-4 forced change: nothing vouches for itself

**Binding condition: before live data, every verifier checks what it is given against an anchor it did not get from the thing being verified, and every "ok" is read back from where it claims to be.**

1. restore.py verifies manifests against the live install's signing key or an operator-typed fingerprint, never the set's own keys, and stages all extraction before any live file moves (B-8).
2. compact.py and sentinel\_audit verify partner checkpoints only against the registered key, which compact.py reads from our own partners table; no fallback (B-14).
3. /compact/audit-result binds each report to the partner, a fresh timestamp and that partner's newest checkpoint, and refuses a report hash it has already seen; the gate rechecks receipt age (B-4, B-15).
4. publish\_witness.sh reads the checkpoint back from the remote before it reports ok; a folder with no remote is a failure (B-2).
5. sentinel\_audit and checkpoint.py check every checkpoint line, local and witness copy, against the chain; checkpoint.py won't sign over a disagreement (B-6).
6. Rotation seeds come from inputs fixed before publication, using rotation.py's formula, not from the publisher (B-16).

**Acceptance:** `run_all.sh` from the Appendix, run by someone other than the builders, reports NOT REPRODUCED for A3, A4, A6a, A6b, A7, A8, A9, A14c and A23.

**Why this one:** round 3 found trust records that "attest rather than verify", and 1.2 was built to fix that (S8: "it VERIFIES rather than attests"). The verification machinery is now real: Ed25519, chain recompute, the latest-row gate. But in six places it still takes the evidence's word for which key, which partner, which time, or whether a copy exists. Each fix is small; together they make "verified" mean verified.

**Before live data, regardless of the forced change:** fix B-1, B-2, B-5, B-6 and B-7. Keep the Compact off, with no partner registered, until B-3, B-4 and B-14 are fixed.

**Runner-up, for the record:** hits.suppressed must follow the live suppression list (B-5). B-1 isn't a forced change only because it's a one-line bug, but it blocks deployment all the same.

## Routed out of the loop

**These are not code defects; they belong to the City Attorney, ACIC or the council.** None changes the ruling above.

**For the City Attorney (flagged, not settled):**

- **Act 668 of 2025** is still unverified against the enrolled bill. My statutory findings use the compilations round 3 relied on (below). Only B-11's threshold, 150 days, would move if Act 668 changed the cap; the unbounded-hold defect doesn't depend on it.
- **§ 1804(d):** whether reciprocal sharing is an "exchange". The question is sharper now that B-3 shows the code can share the full 14-day store.
- **§ 1804(b):** whether a hit hold with no open case, or an unconfirmed disposition, counts as an ongoing investigation (B-11).
- **§ 1808(b):** hits are disclosures "as the result of a match", so B-5 breaks NOCTUA's own rule, not the statute. Confirm the city wants the stricter rule it advertises.
- **§ 1805(b)(4):** the published retention rules must match practice. Backup sets hold reads up to 2 × RETENTION\_DAYS (28 days at 14), and Tier 3 and share justifications are nulled at 14 days. Disclose both or change them.
- Whether partners reading officer usernames, case numbers (B-21) and suppression timing through /audit/range fits the Compact agreement.

**For the city and council:**

- One supervisor can suppress any plate, which now also empties already-executed Tier 3 results (round-3 B16).
- Any supervisor reads any Tier 3 result set (round-3 B17).
- Whether Tier 2 justification text should be kept for complaint review (round-3 B12).
- Key custody: both keys ride in every backup set (B-22), so decide where keys live and who holds the backup store.
- Frigate's own media retention, outside the registry by design.
- Whether the Compact needs a hard off switch in code (it has none).

**For CANT-DO:**

- The audit key can't be rotated without orphaning every plate\_ref; a leak lasts as long as the chain.
- Heartbeats stay self-reported, witness included. B-2's fix narrows this but doesn't remove it.
- The chain is permanent: anything that reaches it (B-13) can't be purged without breaking it.

**Statute text relied on** (pre-Act 668 compilations; verify against the official current code): [§ 12-12-1804](https://law.justia.com/codes/arkansas/2020/title-12/subtitle-2/chapter-12/subchapter-18/section-12-12-1804/) (150-day cap; destruction when the investigation or action ends; no exchange), [§ 12-12-1805](https://codes.findlaw.com/ar/title-12-law-enforcement-emergency-management-and-military-affairs/ar-code-sect-12-12-1805/) (reports; published rules; exclusion), [§ 12-12-1806](https://codes.findlaw.com/ar/title-12-law-enforcement-emergency-management-and-military-affairs/ar-code-sect-12-12-1806/) (exclusion of derived evidence), [§ 12-12-1808](https://law.justia.com/codes/arkansas/2020/title-12/subtitle-2/chapter-12/subchapter-18/section-12-12-1808/) (protection orders: disclosure only as the result of a match). These are the same sources as my round-3 Appendix 2; I didn't re-fetch them this round.

## Appendix: the attack suite

**41 checks; a clean end-to-end run reproduced 39 defects, confirmed one 1.2 fix (A9b), and the negative control (A27) correctly did not reproduce.** The files ship with this review: `lib.py`, `attack1.py`, `attack2.py`, `attack2b.py`, `attack3.py`, `attack4.py`, `attack5.py` and `run_all.sh`.

**To run:** `NOCTUA12_TREE=/path/to/janus12 bash run_all.sh`. The tree needs `janus.py`, `sentinel.py`, `scripts/` and `tests/run_tests.py`; the suite borrows the builders' helpers only to start servers and send requests. It needs Python 3.12 or later, openssl, git and bash, uses loopback ports 19101–19163 and a temp directory, and took about 20 seconds here (two clean runs, identical outcomes). Each line prints CONFIRMED (the defect reproduced) or NOT REPRODUCED.

| Check | What it does | Result | Finding |
| --- | --- | --- | --- |
| A1 | Hot-list entry with no expiry, then hotlist\_sync | Entry deactivated; next read of the plate stored with no ALERT | B-1 |
| A1b | Same entry aged 20 days, then retention | Row deleted | B-1 |
| A2 | Share query at tier 2, 1, `true` and 3 | Tier 1 and `true` return 25 h and 12-day-old reads; only 3 refused | B-3 |
| A2b | SHARE\_OUT entries for those shares | Chained as tier 1 and tier true | B-3 |
| A3 | Signed report dated 2025, then the same body filed for agency-c | Both accepted; agency-c shows a passing audit | B-4 |
| A4 | Receipt rows re-dated to 2020 | Gate still opens | B-15 |
| A5 | Hit, then suppression on the same plate | Detective sees, verifies and exports it; Tier 3 re-resolves it | B-5 |
| A6a | publish\_witness with no repo configured | Exit 0; /health witness ok | B-2 |
| A6b | Witness repo, service account with no git identity | Exit 0; witness ok; remote got nothing | B-2 |
| A7 | Backup set with an extra supervisor, signed with an attacker key, HMAC dropped | Restored, "manifest verified", account and key installed | B-8 |
| A8 | Restore of a set the tar filter rejects | Prints REFUSING after the live DB (30 entries) became the backup's (2) | B-8 |
| A9 | Rewrite entry 10 under an older checkpoint, re-checkpoint, sentinel\_audit | checkpoint.py signs; audit reports 0 failures | B-6 |
| A9b | Janus startup on the same database | Anchor mismatch raised: the janus.py fix works | A-table B7 |
| A10 | Change kind and ts columns of two entries | verify() still ok | B-12 |
| A11 | One torn line in the sink spool, then ingest | Hot-list read 500 and lost; /health ok, sink\_up true | B-9 |
| A12 | Frigate "update" STL77, then "end" STL777 (hot-listed) | STL77 stored; end answered "duplicate"; no ALERT | B-10 |
| A13 | Add a supervisor while Janus is stopped | Account approves Tier 3; no CONFIG\_CHANGED | B-7 |
| A14a | Publish a rotation without a seed | 500, `uuid` not defined | B-16 |
| A14b | Status of a cycle starting 2027-01-04 | Three agencies already delinquent | B-16 |
| A14c | Grind seeds for a chosen auditor and audited pair | Mean 3.2 tries, maximum 14, over 200 trials | B-16 |
| A15 | Rollback, two-key accept, new good checkpoint, restart | Same mismatch raised again | B-19 |
| A16 | Builders' schema test on a DB with plate data in unregistered places | Passes | B-17 |
| A17 | `/audit?limit=-1` as chain\_auditor | Whole 1,201-entry chain returned | B-21 |
| A18 | /audit/verify on 600,003 entries during ingest | 1.18 s call; hot-list read waited 1.14 s (baseline 0.002 s) | B-21 |
| A19 | Hold to 9999-12-31 and an unconfirmed disposition on 400-day-old hits | Both survive retention; /health ok, no breach | B-11 |
| A19b | sentinel\_audit on the same DB | Fails the held hits; /health passes them | B-23 |
| A20 | 300 unauthenticated requests, 300 usernames | 300 AUTH\_FAIL entries | Low |
| A21 | Patrol posts `agency: "ABC123"` to /share/query | "ABC123" chained verbatim | B-13 |
| A21b | Suspend a partner that doesn't exist | 200; free text chained | B-13 |
| A23 | compact.py with and without the registered key, checkpoint signed by another key | Without the key: exit 0, audit recorded | B-14 |
| A24 | DELETE /hotlist without the entry's state | 200 and HOTLIST\_REMOVE; entry still active | B-23 |
| A25 | Ingest account posts a witness attestation | 201; nothing chained | B-16, B-18 |
| A26 | sentinel\_audit URL mode with chain\_auditor credentials | HTTP 403 on /health | B-21 |
| A27 | openssl genpkey file mode under umask 022 | 0600 at creation: no window (negative control) | Low |
| A28 | First boot over an existing chain with an arbitrary key | Starts and pins the key | B-20 |
| A29 | Restore, then a boot without the key, then a good boot | Marker deleted; no RESTORE chained | B-20 |
| A30 | 40-day-old backup set under NOCTUA\_BACKUP\_DIR | /health ok, no breach | B-17 |
| A34 | Hit hold with ref "03", hit aged, retention | Hit deleted while the chain says it's held | B-23 |
| A35 | 40-day-old orphaned bundle folder and backup set | Bundle seen by nothing; backup only a warning in sentinel\_audit | B-17 |
| A36 | Reverse case\_hash values read from /audit/range | "2027-1031" recovered in 0.05 s, with officer and time | B-21 |
| A37 | HOLD\_DAYS=400, a 300-day-old hit, retention | Boots; hit survives; /health ok | B-11 |

Timing in A18 will vary by machine. Everything else is deterministic.
