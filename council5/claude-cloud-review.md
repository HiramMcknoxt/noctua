# NOCTUA Council Round 5 — Claude (cloud seat) review of 1.2.1

Nov 24, 2026 · Corey Spangler

**MODEL/EFFORT USED: Claude Opus 5.5 (model id claude-opus-5-5), effort Max.** Read from this session's runtime configuration, not a picker I can see — the owner should confirm it matches the UI. No Fable, no credit-gated tier.

## Verdict: NOT CONVERGED

1.2.1 delivers what its track report claims against the round-4 findings. Every round-4 reproduction flipped, and both suites give the claimed results. But most fixes were scoped to the reported input, and the invariant behind each one still fails one step over. I reproduced **17 new defects at runtime** against the shipped code: 2 deployment-blocking, 10 code-critical, 5 minor. A few more minor items come from code reading only and are labeled as such.

| Criterion | Vote | Why |
| --- | --- | --- |
| (1) No deployment-blocking or code-critical finding | **NO** | R5-01 (1.1 protection orders void after the blessed upgrade) and R5-02 (a US-format or epoch expiry silently disables a hot-list entry) are deployment-blocking. Ten more are code-critical, in all four core areas. |
| (2) Every round-4 forced change implemented or answered | **NO** | Cloud-seat condition 6 (rotation seed not publisher-chosen) is not met in substance (R5-07). Gemini's "close every fail-open boundary and registry contradiction" is not met (R5-02, R5-05, R5-06). The browser and ChatGPT forced changes are met. |
| (3) Only CANT-DO and legal/institutional items remain | **NO** | Code defects remain in retention, the Tier 3 gate, suppression and the Compact gate. |
| (4) Independent re-tests pass | **YES, with a caveat** | Both suites reproduce the claimed results on my machine. The builders' suite only completes with a `janus11/` sibling directory the public repo lacks. |

## What I ran

All runs used a clean copy of the public repo at commit 80d3715. The six attachments match that commit byte for byte.

- **Builders' suite: 312/312, but only in the builders' private layout.** From the public repo layout it passes 304 checks and then crashes. The P4 migration test boots `../janus11/janus.py`, a sibling directory the repo does not have (1.1 lives in `1.1/`). The P4 and demo checks never run and no final count prints. With a `janus11/` sibling added (byte-identical to `1.1/janus.py`) it is 312/312.
- **Round-4 attack suite vs 1.2.1: the claim holds exactly.** 32 verdicts print NOT REPRODUCED. The only CONFIRMED line is A9b, the contrast control. Eight print nothing. I read each server log: A28 and A18 die on `unpinned_key_over_existing_chain`, A37 on the HOLD_DAYS ceiling, A14b/A14c on the 400 for a client-supplied seed.

**My round-5 suite:** ten scripts under `council5/attacks-cloud/` (delivered with this review), built on the builders' own helpers like the round-4 suite. Each finding prints REPRODUCED or NOT REPRODUCED. Against 1.2.1: **17 of 17 REPRODUCED.** Two scripts boot the repo's real `1.1/janus.py` first and upgrade its database in place, the shape the builders bless for P4.

**Second check:** a separate agent that had not seen the work re-ran the suite twice (20 of 20 verdict lines REPRODUCED each time), probed three edges on its own, and checked every line citation against the code. It found nothing unsupported; I corrected the four wordings it flagged (R5-01, R5-02, R5-04, R5-05) and a few line numbers. The packaged suite also runs clean from the zip on a fresh copy of the repo.

## Round-4 verification

Of the 14 P-items, five are FIXED and nine are FIXED-BUT-WRONG: the reported reproduction flips, but the invariant fails one input over. Of the four forced changes, two are met, one partly, one not. "Flips" below means the round-4 attack now prints NOT REPRODUCED in my run. Line numbers are `1.2.1/janus.py` unless named.

| Item | Verdict | Evidence |
| --- | --- | --- |
| P1 share tier strict | FIXED | A2/A2b flip. Lines 3569-3573 accept only an int equal to 2. A missing tier defaults to 2 (ruled below). |
| P2 hot-list expiry | FIXED-BUT-WRONG | A1/A1b flip: '' becomes NULL, legacy rows migrate, the sweep is one transaction. But `expires` is still stored unvalidated (2021) and compared as a string (1804; hotlist_sync.py:88). R5-02. |
| P3 query-time suppression | FIXED for 1.2+ data | A5 flips; every disclosure path re-judges live (1060-1073). Two predicates do the judging, SQL text equality and the keyed ref, and they disagree on upgraded data. R5-01. |
| P4 migration repair | FIXED-BUT-WRONG | Reads and hits are normalized and MIGRATION is chained (624-678), so the plate-text SQL filters (search, share, Tier 3) hide legacy suppressions. But 1.1 keyed suppressions as HMAC(PLATE\|STATE) (1.1/janus.py:214-219). Nothing re-keys them, so every keyed check misses them. R5-01. |
| P5 witness proof | FIXED | A6a/A6b flip; the heartbeat waits for ls-remote equality. Minor: a same-box bare repo satisfies the proof; the builders' own test uses one. |
| P6 restore trust | FIXED-BUT-WRONG | A7/A8 flip; tarballs are validated before anything moves. Residual: on an env-key host restored from a shell without the key, a set HMAC'd under a key shipped inside it installs the attacker's users (R5-17). Restore also deletes the key copies it moved aside (R5-14). |
| P7 Compact binding | FIXED-BUT-WRONG | A3/A4 flip: agency and 26h binding, query-time gate, a missing checkpoint closes it. But the gate reads the latest row by filing order, so an older pass filed after a failure reopens it. R5-06. |
| P8 key pinning | FIXED | A23/A26 flip; compact.py, sentinel_audit URL mode and rotation.py --verify refuse without a pin. DB mode still defaults to the key beside the audited DB, which P8 did not cover. |
| P9 rotation | FIXED-BUT-WRONG | A14a/A25 flip; future rounds never count (builders' check passes). But the seed's inputs, cycle_start and the chain root, are publisher-controlled: mean 3.03 tries to pick a pair. R5-07. |
| P10 registry parity | FIXED-BUT-WRONG | The full-column allowlist works (A16 flips); A19b/A30/A35 flip. But retention.py still does its own date math (R5-05), and an exported bundle escapes both purge and check (R5-04). |
| P11 one contract, chain hardening | FIXED | A9/A10/A11/A13/A15 flip; all hashing goes through `sentinel.entry_hash`. Minor residuals: unsigned checkpoints pass Janus's anchor but fail sentinel_audit; `flush_deferred` runs outside DBLOCK on the shared connection; the A28 check is a file-vs-env proxy (R5-13). |
| P12 approver visibility | FIXED-BUT-WRONG | Supervisor approvers now see fragment, case, why and basis. R17 also named the post-hoc emergency review, which is still blind and can be pre-empted (R5-08). Stale requests reach approvers blank (R5-16). |
| P13 holds, delete, misc | FIXED-BUT-WRONG | A17/A19/A20/A24/A34/A36/A37 flip; A18 holds (builders' re-aimed check passes). The A12 fix opened new alert-loss paths (R5-03). Hit-scope holds still need no case (R5-09). `config_closed()` is still missing on several POST write routes (minor, listed below). |
| P14 docs | FIXED-BUT-WRONG | COMPACT.md is updated but still says "as implemented in NOCTUA 1.2". The docs overstate P9 (COMPACT.md: grinding "would require rewriting the chain itself") and P10 (sentinel.py and janus.py: "mirroring retention.py's purge semantics exactly"); the track report's 312/312 is layout-dependent. |
| FC Gemini: close every fail-open boundary and registry contradiction | NOT FIXED | R5-02, R5-05 and R5-06 are those classes. |
| FC cloud Claude: nothing may vouch for itself | FIXED-BUT-WRONG | Conditions 1-5 met, with the R5-17 residual on condition 1. Condition 6 (rotation seed not publisher-chosen) is not met. R5-07. |
| FC browser Claude: suppression at query time; removal deletes | FIXED | Both done; R5-01 is an identity (key) failure on upgraded data, not a timing one. |
| FC ChatGPT: one verification contract | FIXED | One hashing path; the checkpoint-acceptance policy still differs between Janus and sentinel_audit (minor). |

## New findings

Seventeen defects reproduced at runtime against 1.2.1, each by a named script in the appendix. Severity follows the brief: defects in retention, the Tier 3 gate, suppression and the Compact gate are never minor. Line numbers are `1.2.1/janus.py` unless named.

| ID | Severity | Area | Defect |
| --- | --- | --- | --- |
| R5-01 | Deployment-blocking (upgrades) | Suppression | 1.1 protection orders are void for every keyed check after the blessed upgrade |
| R5-02 | Deployment-blocking | Hot list | A US-format or epoch expiry is accepted, then disables the entry at first sighting |
| R5-03 | Code-critical | Hot list | The A12 supersede fix deletes stolen-plate alerts on ordinary OCR sequences |
| R5-04 | Code-critical | Retention | An exported bundle with no disposition on file becomes undestroyable once its hit passes 150 days |
| R5-05 | Code-critical | Retention | Purge and check disagree by up to a day: /health never green, cap enforced late |
| R5-06 | Code-critical | Compact gate | An older pass filed after a failure reopens the gate |
| R5-07 | Code-critical | Compact rotation | The derived seed is still chosen by the publisher |
| R5-08 | Code-critical | Tier 3 | The auditor's mandatory emergency review is blind and can be pre-empted |
| R5-09 | Code-critical | Retention | Holds need no case, any detective places them, one supervisor releases them |
| R5-10 | Code-critical | Case gate | A case list whose feed stopped never goes stale |
| R5-11 | Code-critical | Tier 3 | basis_type "other" runs a historical search with no judicial instrument |
| R5-17 | Code-critical | Restore | P6 residual: a self-HMAC'd set restores attacker accounts on env-key hosts |
| R5-12 | Minor | Chain | INGEST_REJECTED chains raw caller text, unthrottled |
| R5-13 | Minor | Keys | A wrong key in the key file is pinned over an unpinned chain |
| R5-14 | Minor | Restore | Restore deletes the key copies it just moved aside |
| R5-15 | Minor | Search | A hyphenated fragment misses canonical plates |
| R5-16 | Minor | Tier 3 | A request pending past 14 days reaches the approver blank and still executes |

**Written design choices.** Seven findings match a choice the 1.2.1 docs or comments state outright: R5-03 (TRACK-121-REPORT.md:185-187), R5-06 (janus.py:3283-3284, "filing order, not the … ts"), R5-08's auditor view (janus.py:4052), R5-10 (janus.py:343-345), R5-11 (TRACK-11-REPORT.md:186-187), R5-13 (janus.py:714-720) and R5-17 (restore.py:115-119). They stay findings because each breaks a promise made elsewhere: COMPACT.md:69-71 (R5-06), janus.py:1826-1828, "nothing deletes it" (R5-03), the pilot spec (R5-08, R5-10, R5-11), and round 4's own A28 and P6 goals (R5-13, R5-17). The council should rule on them as design critiques.

### Deployment-blocking

**R5-01 · A 1.1 protection order is void after the blessed upgrade.** 1.1 keyed suppressions as HMAC(PLATE|STATE) (1.1/janus.py:214-219); 1.2+ keys by HMAC of the canonical plate (sentinel.py:137-143). `_migrate_121` (624-678) normalizes plate text but never re-keys suppressions. So `is_suppressed` (1041), `hit_suppressed_now` (1060) and release (2258) all miss the order. Only the plate-text SQL filters (1048-1057), used by /search, share results and Tier 3 execution and results, still hide the plate; /search is the one behavior the P4 test checks.

- *Reproduced* (`r5_legacy_suppression.py`): the repo's 1.1 code places order PO-77 on PRT100, then 1.2.1 boots on that database with its key file. A detective hot-lists PRT100 (201), its read alerts, /hits shows plate, camera and time, and the detective verifies (200) and exports evidence (201). The supervisor queue is empty; release answers 404.
- *Fix:* re-key legacy suppressions at migration (the row still holds plate text), chain the count, and make SQL and Python share one predicate.

**R5-02 · A US-format or epoch expiry disables a hot-list entry at first sighting.** `expires` is stored as given (2021) and compared as a string at ingest (1804) and nightly (hotlist_sync.py:88). "12/31/2027" and 1798761600 both sort below any ISO timestamp, so the stolen car's first read deactivates its entry. A past date in words ("Dec 31 2025") never expires at all. Round 3 already raised free-text expiry (council3 cloud review, B18, rated Low); P2 special-cased the empty string instead.

- *Reproduced* (`r5_hotlist_expiry.py`): both adds answer 201 "added". Both cars' reads store with no ALERT and chain HOTLIST_EXPIRED; the ISO control alerts; hotlist_sync deactivates "06/30/2027" overnight, while "Dec 31 2025" still alerts and survives the sync.
- *Fix:* parse to canonical UTC at the door, refuse anything else with 400, compare parsed values.

### Code-critical

**R5-03 · The A12 fix deletes stolen-plate alerts.** Any redelivery under the same camera and event id with a different plate supersedes the stored read, whatever its confidence or order. It also deletes the PENDING hit and its outcome record (1893-1936). The bridge still drops a repeat of an earlier event-and-plate pair (frigate_bridge.py:233-239).

- *Reproduced* (`r5_supersede.py`): update A 0.80, update B 0.85, end A 0.90 (confidence rising throughout) ends with Janus holding B and no alert for A. A delayed 0.61 partial arriving after the 0.93 final overwrites it and deletes its alert. A same-plate redelivery re-creates the hit under a new id, so the id the officer was alerted with answers 409.
- *Fix:* supersede only on higher confidence (forward Frigate's event type too), mark hits superseded instead of deleting them, and drop the bridge dedupe now that Janus dedupes persistently.

**R5-04 · An exported, unreleased bundle becomes undestroyable after its hit's 150-day purge.** Retention deletes the hit once its age in whole days exceeds 150 (retention.py:166-168). Release and disposition then 404 for want of the hit row (2853, 2935), and destroy needs a release (2904). destroy_by is never set, and the registry check flags only destroyed-on-paper or overdue bundles (sentinel.py:588-599). Only a disposition filed before the purge still ends it, because confirm and destroy do not need the hit row (2966-2998, 2894-2922).

- *Reproduced* (`r5_evidence_deadend.py`): a verified, exported hit aged to 151 days is purged. Release 404, disposition 404, destroy 409; the bundle stays on disk while /health and sentinel_audit report the evidence store clean.
- *Fix:* key the evidence lifecycle on the evidence record, not the hit row, and flag an unreleased bundle whose hit is gone.

**R5-05 · Purge and check still disagree.** retention.py measures hit age in whole days (`.days`, 161-170) and case_searches by date (134). `registry_breaches` uses exact timestamps (sentinel.py:523-536, 575-580).

- *Reproduced* (`r5_parity.py`): after two retention runs, an unprotected 30.5-day hit and a cutoff-day case_searches row remain. /health, alert_check and sentinel_audit --db all name them as breaches. Each row is falsely flagged for under a day, but with at least one unprotected alert or case search a day, /health is never green. A held hit 150.5 days old survives both runs: the 150-day cap is enforced as "more than 150 whole days".
- *Fix:* one function selects the rows past class; the purge deletes exactly those and the check counts exactly those.

**R5-06 · An older pass filed after a failure reopens the Compact gate.** The gate and reinstate read the latest audit row by id (1432-1441, 3285-3288). P7 stores the report's ts, but nothing orders by it, and a report_hash already on file is accepted again (3141-3148).

- *Reproduced* (`r5_gate_order.py`): pass, then fail closes the gate (403); re-posting the identical pass reopens it (200). A 2-hour-old pass delivered late does the same. The reopened gate stays open until 26 hours after that report's own ts (1437-1439).
- *Fix:* refuse a report older than the newest on file and any repeated report_hash; evaluate the gate on report time.

**R5-07 · The rotation publisher still picks who audits whom.** The seed is SHA-256(members | cycle_start | chain root) (4424-4430). The publisher chooses cycle_start, any real date (3449-3454), and moves the root with any chained action.

- *Reproduced* (`r5_rotation_grind.py`): grinding cycle_start offline, or nudging the root with GET /hits, yields the wanted pair, and Janus publishes exactly the predicted schedule, signed. Mean 3.03 tries for one chosen pair among four members: the 1-in-3 base rate, unchanged from round 4's 3.21. The derivation removed the seed parameter, not the choice.
- *Fix:* fix the inputs before the randomness is known: a commit-reveal across members, or a public beacon value drawn after publication.

**R5-08 · The outside auditor's emergency review is blind and can be pre-empted.** Spec §8 requires post-hoc review of every emergency use "by the outside auditor in all cases". Any second supervisor's review clears the flag (2629-2672), and the auditor's views show no fragment, case, justification or basis, only case_hash, plate_ref, requester, time and basis_type (4077-4105). Round 3 already noted that any other supervisor's review clears the flag (council3 cloud review, B18).

- *Reproduced* (`r5_gates.py`): a second supervisor marks an emergency "justified" (200); the auditor's review then answers 409. The auditor never saw fragment, case, justification or basis.
- *Fix:* require the auditor's own review for every emergency, separate from any supervisor's, and show the auditor what it reviews.

**R5-09 · Holds need no case, any detective places them, one supervisor releases them.** Spec §4 and §9: holds are set "by the Administrator on a documented case basis" and released only on prosecutor-approved disposition. Here the case gate runs only for scope 'case' (2102), detectives may place holds (2092), and release takes one supervisor and no disposition (2157-2187).

- *Reproduced* (`r5_gates.py`): a detective holds a hit already REJECTED as a misread, with no case. Retention keeps that innocent driver's plate, camera and time past HOLD_DAYS while the unheld control is deleted; one supervisor then releases the hold (200).
- *Fix:* holds require a validated case (hit holds through the hit's case), the designated role, and release through a recorded disposition.

**R5-10 · A case list whose feed stopped never goes stale.** Spec §7 item 9: if the feed "has not refreshed within its configured window, the front door fails closed". 1.2.1 marks config stale only when a reload fails (376-413); a valid file that stopped updating stays fresh forever.

- *Reproduced* (`r5_gates.py`): cases.json last written 30 days ago; searches run and /health reports the config fresh.
- *Fix:* a configured freshness window on the case list (file age or a stamped export time) that fails closed and alarms.

**R5-11 · A Tier 3 historical search executes on basis_type "other".** Spec §7 item 3: Tier 3 unlocks "only on an entered judicial-authorization number with the signed authorization uploaded", and the front door "never invents its own instrument". BASIS_TYPES includes "other" (243), and any non-empty text passes (2394-2419); a missing basis_type defaults to "other" (2394).

- *Reproduced* (`r5_gates.py`): basis "other", auth_basis "verbal OK from the lieutenant"; a second supervisor approves; EXECUTED.
- *Fix:* make the accepted instruments configuration that defaults to none until the City Attorney rules, and require the authorization number plus a stored hash of the signed document.

**R5-17 · P6 residual: a self-HMAC'd backup restores attacker accounts on env-key hosts.** restore.py reads the host key from the restore shell's environment or a key file (restore.py:100-111). With neither, the set's own audit_key verifies the set's HMAC (114-126) and the set is accepted (226), although the host's signing_pub.pem is present.

- *Reproduced* (`r5_restore_envkey.py`): restore exits 0 and installs the attacker's supervisor; Janus boots on its real env key and the attacker account reads /hits (200).
- *Fix:* when the host has a signing public key, require a valid signature against it; use a key from inside a set only under an explicit lost-key recovery flag.

### Minor

- **R5-12** INGEST_REJECTED chains the caller's raw `cam` string (1853-1855). `cam` is scrubber-exempt (sentinel.py:748) because registered ids are configuration, but this entry exists because the camera is not registered. 42 bad reads made 42 permanent entries, one holding a street address. Hash it as the A21 fix does for agencies, and throttle.
- **R5-13** The A28 check is a file-versus-env proxy (714-738). A wrong key written to the key file over an unpinned 1.1 chain is pinned and Janus serves, although the chain's own QUERY ref recomputes under the true key only. See ruling 2.
- **R5-14** restore.py moves live files aside with `os.replace`, which keeps their mtime (259-261), then prunes copies by mtime (330-348). The live audit key and signing key copies are deleted by the restore that made them; only the DB, -wal and -shm copies survive, against restore.py's own "nothing is destroyed by a restore" (line 41).
- **R5-15** Fragments are not canonicalized like plates (1015-1026): "HYP-123" misses "HYP123", so an officer who types the hyphen gets no results.
- **R5-16** A Tier 3 request pending past RETENTION_DAYS has why and auth_basis nulled and its fragment scrubbed (sentinel.py:249-252, 267-276). The approver sees blanks, and approval still executes a search for the HMAC string.
- *Code reading only, not run:* `flush_deferred` runs after DBLOCK is released (1661-1664) on the shared connection, so it can stream another thread's uncommitted entry. Unsigned checkpoints skip the signature check in Janus's anchor (817-827) but fail sentinel_audit (sentinel_audit.py:107-108). /search uses a deny-list role gate (1000-1012), so an unknown role can search. `config_closed()` is not applied to POST /hotlist, /verify, /holds, /holds/release, /suppressions, /suppressions/release, /lists, /outcomes or /report/compile; it guards only /tier3/*, /evidence/* and /share/query. The scrubber and AUTH_FAIL still use unkeyed SHA-256 (sentinel.py:773, janus.py:946).

## Rulings on the flagged judgment calls

**1. P1, a share with no `tier` defaults to 2: ACCEPT.** Defaulting to the only legal value cannot widen access, and the strictness that matters, never running another tier's search, holds (A2 flips). One small ask, not a blocker: chain `tier_defaulted: true` on SHARE_OUT, so a partner client that omits the field shows up in the record.

**2. P4/A28, refusing to start on an env key over an unpinned chain: the refusal is right; the shipped ceremony is not a verification.** Fail-closed is the correct default, and it does not touch Cabot, whose first boot pins against an empty chain. But the blessed workaround, copying the key into the file, pins whatever key is in the file. R5-13 pins a wrong key over a 1.1 chain whose own QUERY ref proves it wrong. Before anyone upgrades:

- Verify, don't proxy. At an unpinned boot over a non-empty chain, recompute keyed refs the database can prove: suppression rows (plate text beside its ref, under either formula), tier3 fragments beside their TIER3_REQUEST refs, case_searches fragments beside their QUERY refs. Pin only on a match, and chain KEY_PINNED with the method and counts.
- If nothing is checkable, require an explicit two-key ceremony: an expected fingerprint recorded out of band at install, supplied by the operator, chained.
- Fix the refusal message. It tells an env-key operator to "restore the key (env NOCTUA_AUDIT_KEY …)", the variable they already set.

**3. The eight silent verdicts: a legitimate pass only where the refused setup is the attack itself.** That holds for A37 (HOLD_DAYS=400 is the attack) and A28 (trust on first use is the attack). For the other six the refusal is incidental, so the loop owes a re-aimed test. I ran or checked each one:

- A14c, re-aimed as R5-07: **still reproduces**. The seed is derived but still publisher-chosen.
- A14b: the builders' "future rounds never count" check passes in my run.
- A18: the builders' re-aimed check (key file, 250k entries, concurrent read under 1 s) passes in my run.
- A29 and A30: the builders' checks pass in my run.
- A27: negative control. I confirmed OpenSSL 3.0.13 creates the private key 0600 under umask 022.

Process ruling: a silent verdict should fail the harness, not pass it. Re-aim `council4/attacks` in-tree so every verdict prints.

## Forced change: test the invariant, not the finding

1.2.1 flipped every round-4 reproduction, yet 17 new defects reproduced on the first try. Each fix was aimed at the reported input rather than the property it protects. The empty string was special-cased instead of validating dates. A client seed was refused instead of making the seed unpredictable. Report time was stored but not ordered on; plate text was normalized but suppression keys were not; the breach check was "shared" while the purge kept its own date math.

**The forced change: 1.2.2 is accepted against invariant tests, not against the findings list.** Each invariant below ships as an adversarial test that drives the public API over generated inputs and delivery orders. Each must fail on 1.2.1 and pass on the patch, and the suite must run from the public repo layout.

1. **Hot list:** every expiry the API accepts is a parsed UTC instant, and an entry alerts on every read until that instant.
2. **Ingest:** no delivery order or redelivery of one event ends with less alerting than its best read, and no hit is ever deleted.
3. **Suppression:** on databases upgraded in place from the repo's real 1.1 and 1.2 builds, every hit-disclosing endpoint agrees with /search.
4. **Retention:** for any data age, a retention run followed by the check reports zero breaches, and every registered store, evidence bundles included, has an end the API can reach.
5. **Compact:** the gate is a function of audit time, not filing order, and the rotation publisher cannot predict the schedule before committing to its inputs.
6. **Spec gates (§§7-9):** the outside auditor reviews every emergency use and sees what it reviews; holds stand on a validated case; the case list fails closed by age; Tier 3 instruments are configuration that fails closed.

This is one change because it turns all 17 findings into a single acceptance standard. It is round 4's Gemini forced change, applied to invariants instead of reproductions.

## Routed out, not settled from the chair

These need a lawyer, a prosecutor or the Commission. None of my code findings depends on how they are answered.

- **Act 668 of 2025** stays flagged-not-settled.
- **The Tier 3 instrument (R5-11).** Which judicial instrument Arkansas law provides, and whether any non-judicial basis may ever unlock Tier 3. City Attorney (spec front matter, assumption 2).
- **Evidence past 150 days (R5-04, R5-05b).** Whether § 12-12-1804(b) lets a hit row or an exported bundle outlive 150 days while charges are pending, and what event ends it. City Attorney with the prosecuting attorney.
- **What "150 days" means against a daily purge.** Whether data reaching 150 days plus up to a day meets the cap, which sets the margin (for example, refusing RETENTION_DAYS or HOLD_DAYS above 149). City Attorney.
- **Hold authority (R5-09).** Who may place and release a legal hold, and whether early release without prosecutor sign-off risks discovery or exculpatory-evidence duties. Commission policy, with the prosecuting attorney.
- **Emergency follow-up deadline.** Spec §8 requires judicial notice or application within 48 hours; the code tracks only a post-hoc review and locks the path at 72 hours. Which deadline the law requires: City Attorney, with the receiving judges.
- **Suppression placement.** One supervisor can hide any plate from every search on a free-text order reference, while release takes two. Whether placement needs a second key or verification of the order: Commission policy.
- **Retention of order references and partner text.** `suppressions.order_ref` and `share_queries.case_ref` are kept forever by design. Whether that fits the records schedule: City Attorney.
- **The Compact during the pilot.** Spec §9 bars sharing during the pilot outside written, case-tied disclosures. Whether the Compact endpoints should ship disabled for Stage 1: Commission. § 12-12-1804(d) stays with Lane 2.
- **Unchanged from round 4:** key custody, witness-repo ownership (P5's proof accepts a same-box remote) and Frigate media retention are Commission decisions or CANT-DO. Account lockout after five failures and MFA (spec §7 items 1 and 5) are not in Janus; whether they belong there or in a front proxy follows the ACIC Path A/B answer.

## Appendix: reproduction

From a clone of github.com/HiramMcknoxt/noctua at 80d3715, with the round-5 suite placed at `council5/attacks-cloud/`:

```bash
# builders' suite: needs a janus11/ sibling of 1.2.1/ to finish
cp -a 1.1 janus11 && (cd 1.2.1 && python3 -I tests/run_tests.py)

# round-4 attack suite against 1.2.1
NOCTUA12_TREE=$PWD/1.2.1 bash council4/attacks/run_all.sh

# round-5 suite (this review)
NOCTUA121_TREE=$PWD/1.2.1 NOCTUA11_TREE=$PWD/1.1 \
  bash council5/attacks-cloud/run_all.sh
```

Builders' suite: "312 checks, 312 passed, 0 failed" with the sibling. Without it: 304 PASS lines, then `RuntimeError: boot failed for .../1.2.1/../janus11/janus.py`.

Round-4 suite: 32 NOT REPRODUCED, A9b CONFIRMED (control), 8 silent for the reasons in ruling 3.

Round-5 suite, shortened verdict lines (full evidence in `results-2026-11-24.log`):

```text
REPRODUCED R5-01  hot-list add 201 | detective /hits shows PRT100 | verify 200 | export 201 | queue empty | release 404 | /search reads []
REPRODUCED R5-02  "12/31/2027" 201, read stored, entry deactivated | epoch 1798761600 same | ISO control ALERT | "Dec 31 2025" ALERT, survives sync
REPRODUCED R5-03a A 0.80 > B 0.85 > end A 0.90: stored A8C1234, end-A dropped as duplicate, no pending hit for A
REPRODUCED R5-03b final STL777 0.93, then late STL77 0.61: stored STL77, alert deleted
REPRODUCED R5-03c redelivery at 0.90: new hit id 4 | verify hit 3: 409 | outcome rows for 3: 0
REPRODUCED R5-04  hit purged at 151 d | bundle on disk | release 404 | disposition 404 | destroy 409 | health and audit clean
REPRODUCED R5-05a after 2 retention runs: breach [case_searches.frag, hits.entry_plate, hits.read_plate] | alert_check 1 | sentinel_audit 2
REPRODUCED R5-05b held hit at 150.5 d survives both runs
REPRODUCED R5-06  share 200 | fail filed: 403 | same pass re-posted 201: 200 | late 2 h pass: 200 | duplicate report_hash x2
REPRODUCED R5-07  wanted pair published via cycle_start and via root nudges | prediction == published | mean 3.03 tries
REPRODUCED R5-08  second supervisor review 200 | auditor review 409 | auditor views hashes only
REPRODUCED R5-09  detective hold, no case, REJECTED hit: 201 | held survives 60 d, control deleted | release 200
REPRODUCED R5-10  cases.json 30 d old | search 200 | config.cases.stale false
REPRODUCED R5-11  basis "other", "verbal OK from the lieutenant": EXECUTED
REPRODUCED R5-12  42 rejected reads, 42 entries | raw cam "ABC1234", "Doe residence driveway, 12 Elm St"
REPRODUCED R5-13  wrong key in file: served 200 | pinned fingerprint is the wrong key | chained ref matches the true key
REPRODUCED R5-14  restore exit 0 | pre-restore copies of audit_key, signing_key, signing_pub pruned
REPRODUCED R5-15  "HYP-123" [] | "HYP123" 1 read
REPRODUCED R5-16  approver sees why null, auth_basis null, fragment pref:... | approve EXECUTED
REPRODUCED R5-17  restore exit 0 | evil.sup installed | Janus up | evil.sup GET /hits 200
```
