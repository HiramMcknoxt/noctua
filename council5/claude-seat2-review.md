MODEL/EFFORT USED: Claude Opus 5.5 (claude-opus-5-5), reasoning effort Max — taken from this session's configuration; I can't see the picker UI myself, so confirm it against what the screen showed. No Fable, no credit-gated tier.

# NOCTUA Council — Round 5 — Claude (cloud seat): review of 1.2.1

## 1. Verdict: NOT CONVERGED

| Criterion | Vote | Basis |
|---|---|---|
| (1) No deployment-blocking or code-critical finding | **FAIL** | 20 new findings, every one reproduced at runtime against the unmodified 1.2.1 tree, twice: 1 deployment-blocking (any in-place upgrade from 1.1), 10 code-critical, 9 minor. |
| (2) Every round-4 forced change implemented or answered | **FAIL** | Three are fixed-but-wrong in ways that reproduce: query-time suppression on upgraded data (R5-03), restore's host trust root in the lost-key path (R5-19), a publisher-proof rotation seed (R5-12). "Nothing may vouch for itself" is broken again by compact.py's freshness gap (R5-17). |
| (3) Only CANT-DO / legal-institutional items remain | **FAIL** | What remains is code. |
| (4) Independent re-tests pass | **FAIL** | Both builder claims re-ran exactly as stated (below). They don't cover what fails: my own harness against the same tree gives 20 CONFIRMED and 1 control HOLDS. |

**Claims 1 and 2 verified as stated. Claim 3 is not.**

- Builders' suite, unmodified, `python3 -I tests/run_tests.py`: **312 checks, 312 passed, exit 0** (14.6 s).
- Round-4 attack suite (`council4/attacks`), unmodified, `NOCTUA12_TREE=janus121`: **32 NOT REPRODUCED, 1 CONFIRMED (A9b, the contrast control), 8 silent.** attack1 dies at its seed-publish assert (A14b, A14c), attack3 at the A28 instance start (A28, A29, A30, A27), attack4 at setup (A18), attack5 at the HOLD_DAYS=400 start (A37).
- The attachments are byte-identical to the repo's `1.2.1/` at commit 80d3715 (the scripts differ from the combined file only by trailing blank lines).
- Claim 3 fails on P2, P3, P4, P6, P9, P10 and the P13 new code (table below).

Harness: `attacks-cloud-r5/` (10 check files, `run_all.sh`, README), clean run in `results-2026-11-24.log` (1m59s). Every number below is from that log.

## 2. Round-4 verification

| Item | Status | Evidence |
|---|---|---|
| P1 Share tier strict | **FIXED** | A2/A2b not reproduced. janus.py:3569-3573 accepts only an int equal to 2. Observed: no tier → runs and is chained as tier 2 (O-1). |
| P2 Hot-list expiry | **FIXED-BUT-INCOMPLETE** | '' → NULL and the sweep predicate are fixed (A1/A1b not reproduced). The cause survives: expiry is unvalidated text compared as a string (R5-05). |
| P3 Query-time suppression | **FIXED-BUT-WRONG on upgraded data** | Correct for suppressions created by 1.2+ (A5 not reproduced). On a 1.1-built database the live check never matches a pre-upgrade order, and it *un-hides* hits that 1.2 still hid (R5-03). |
| P4 Migration repair | **FIXED-BUT-WRONG** | reads/hits text normalization works (builders' P4 checks pass). Legacy suppression refs are never re-keyed: 1.1 hashed `PLATE\|STATE`, 1.2+ hashes the bare canonical plate (R5-03). The builders' P4 test checks only /search, the one path that still works. |
| P5 Witness proof | **FIXED** (caveat) | A6a/A6b not reproduced. Heartbeat only after ls-remote + tree read-back (publish_witness.sh:108-113). Caveat: a same-machine bare remote satisfies the proof; the builders' own test uses one (run_tests.py:1239-1244). Whether the remote is off-box is a deployment fact, routed in §6. |
| P6 Restore trust | **FIXED-BUT-WRONG** | A7/A8 not reproduced, and a host that still has its audit key refuses an attacker set (R5-19 control). In the documented lost-key recovery path the set's own key vouches for the set, and the host's real signing key is pruned in the same run (R5-19). |
| P7 Compact binding | **FIXED** (minor gap) | A3/A4 not reproduced. janus.py:3121-3148 binds agency + report ts; one gate helper at query time (1415-1461). Minor: reports aren't ordered or deduped (R5-11). |
| P8 Key pinning | **FIXED** for pinning; the same principle fails on freshness | A23/A26 not reproduced. compact.py:179-189, sentinel_audit.py:364-368 and rotation.py:190-195 refuse to run unpinned. But compact.py never checks the partner checkpoint's age (R5-17), and URL-mode sentinel_audit passes a system with no checkpoint as a warning (R5-18). DB mode still defaults to the public key sitting beside the database it audits (sentinel_audit.py:264-269), which is self-vouching for a furnished copy. |
| P9 Rotation | **PARTIAL** | Fixed: the uuid NameError (A14a not reproduced), completed-rounds-only and direction-correct delinquency, and witness role + signature (A25 not reproduced). Wrong: the derived seed is still the publisher's choice (R5-12). Still open: the shipped verifier rejects genuine schedules (R5-13), the void two-key isn't bound to a cycle (R5-10), and the supervisor witness path chains free text (R5-07). |
| P10 Registry parity | **FIXED-BUT-WRONG** | A16/A19b/A30/A35 not reproduced. The *protection* predicate is shared, but purge and breach use different *age* arithmetic (R5-04). holds.ref free text is allowlisted as non-plate (R5-09). |
| P11 Verification contract + chain | **FIXED** (minor residual) | A9/A10/A11/A13/A15 not reproduced; one `entry_hash` (sentinel.py:792). Pre-1.2.1 (v1) entries keep kind/ts outside the hash, and verify never cross-checks them (R5-14). |
| P12 Approver visibility | **FIXED** | janus.py:4055-4087; builders' R17 checks pass. |
| P13 Holds / delete / misc | **MOSTLY FIXED; two regressions in new code, one latent crash** | A17, A19, A24, A34, A37 not reproduced; C-A28 holds. Regressions: the A18 fix runs the verify before authentication (R5-02). The A12 supersede loses alerts behind the shipped bridge (R5-15) and overwrites a verified hit's read (R5-16). The AUTH_FAIL rework kept a crash that has been latent since 1.2 (R5-01). Overdue holds "surface" but never alarm (R5-08). |
| P14 Docs | **FIXED** with inaccuracies | TRACK says DELETE /hotlist identifies a membership "by id", but the code has no membership id (janus.py:3785-3816). COMPACT.md says "nobody picks it" (false, R5-12) and "identical inputs reproduce the schedule byte-identically" (the shipped verifier doesn't, R5-13). restore.py's docstring says "nothing is destroyed by a restore" (R5-19). |

**Round-4 forced changes**

- **Gemini** — close every fail-open boundary, each proven fail-before-fix: **PARTIAL.** The named instances closed; the classes didn't. R5-05 is P2's class; R5-17 and R5-18 are fail-open freshness.
- **Claude cloud (this seat)** — nothing may vouch for itself:
  - (i) restore trusts host keys: **FIXED-BUT-WRONG** (R5-19)
  - (ii) compact key pinning: **FIXED**
  - (iii) audit-result agency + freshness binding: **FIXED** (R5-11 minor)
  - (iv) witness proof of publication: **FIXED** (same-box caveat)
  - (v) the audit tool anchors every checkpoint: **FIXED** (DB mode)
  - (vi) rotation seed not publisher-chosen: **FIXED-BUT-WRONG** (R5-12)
  - New self-vouching: R5-17.
- **Claude browser** — suppression is a query-time property of the plate: **FIXED** for 1.2+ data, **broken** on upgraded 1.1 data (R5-03). Hot-list removal deletes the row: **FIXED.**
- **ChatGPT** — one verification contract in sentinel.py: **FIXED** (minor residual, R5-14).

## 3. New findings

Reproduce with `NOCTUA_TREE=/path/to/janus121 bash attacks-cloud-r5/run_all.sh` (layout in its README). Line numbers are 1.2.1 at commit 80d3715.

### Deployment-blocking

**R5-03 — An in-place 1.1 → 1.2.1 upgrade voids every pre-upgrade protection order on the live paths.** *Deployment-blocking for any upgrade from 1.1; code-critical otherwise.*

1.1 keyed suppressions by HMAC(`PLATE|STATE`) (janus11/janus.py:214-219). 1.2+ keys them by HMAC(canonical plate) (sentinel.py:137-143). Neither 1.2 nor 1.2.1 re-keys the old rows: `_migrate_121` (janus.py:624-678) touches reads, hits and hotlist only. /search still hides the plate, because its SQL compares the plaintext `suppressions.plate` column (janus.py:1048-1057). Every P3 path instead asks whether `plate_ref(plate)` is among the active refs (`hit_suppressed_now` :1060, `is_suppressed` :1041), and a 1.1 row never matches.

Reproduced on a database written by the actual 1.1 code (the builders' own P4 method):

- Under 1.1 the protected plate's hit is hidden (control).
- After the upgrade, a detective's GET /hits shows it with plate text and `"suppressed": 0`. It never reaches /suppressed-hits.
- A new read of the plate → ALERT, listed in /hits. A detective can verify it (200) and export evidence (201).
- POST /suppressions/release → 404 "no active suppression for that plate", while /health reports `active_suppressions: 1`. The order can't be released.

P3 made this worse than 1.2. 1.2's /hits filtered on the stored stamp (janus12/janus.py:3443-3444), which kept hiding the 1.1-era hit. 1.2.1's live check overrides the stamp and exposes it.

**Fix:** re-key at boot — recompute `plate_ref` from `suppressions.plate` under the current formula, chain MIGRATION with counts, and refuse to boot on a row whose plate is NULL. Then have the SQL filter and `hit_suppressed_now` read one identity.

### Code-critical

**R5-01 — Four failed logins switch off AUTH_FAIL logging for the life of the process, and every later failed login becomes a 500.**

janus.py:947 prunes the throttle dict with `k[1] < bucket - 1`. But :952 stores `("flushed", user, bucket)` keys in the same dict, and their `k[1]` is the username, so the comparison is str < int → TypeError. The trigger is any user failing twice in one minute and once in the next — an ordinary mistyped key — or an anonymous caller doing it on purpose.

Reproduced: the next failure → 500 `"internal: '<' not supported between instances of 'str' and 'int'"`. The real account det.okafor with a wrong key → 500, 500. AUTH_FAIL entries freeze at 3. Valid logins still return 200, so nobody notices.

The bug has been latent since 1.2 (janus12/janus.py:741-746); the A20 rework missed it.

**Fix:** keep the flushed markers in a separate set (or prune on the bucket field), and add a test that crosses a minute boundary.

**R5-02 — The A18 fix moved the full-chain verify in front of authentication, with no single-flight.**

`do_GET` computes `chain_ok_cached()` for /health and /audit/verify before `_get()` authenticates (janus.py:3833-3836). 1.2 authenticated first (janus12/janus.py:3352-3374). The 60-second cache (janus.py:1387-1401) has no lock, so every request that arrives while a verify is running starts another one. `verify_detached` loads every audit row into memory (sentinel.py:828-839).

On a 250k-entry chain:

- One anonymous request → 401 after 1.52 s, so the scan ran before the 401.
- Six concurrent anonymous requests on a cold cache → six 401s after 8.9–14.8 s. Janus memory went from 32 MB to 1,139 MB.
- An alert-producing ingest read slowed from 3 ms to 42 ms.

That's about 180 MB per concurrent anonymous caller, growing linearly with chain length. ThreadingHTTPServer has no caller limit, and the Compact requires partners to reach /audit/verify.

**Fix:** authenticate before computing anything; single-flight the refresh and serve the stale result meanwhile; stream rows instead of `fetchall`.

**R5-04 — Retention and the "one" breach predicate disagree by up to a day. Healthy deployments report RETENTION BREACH, and held hits live to 151 days.**

retention.py:158-171 deletes when the floored day count `(now − ts).days` exceeds HOLD_DAYS (or 150 for the cap). sentinel.py:524-536 flags `ts < now − HOLD_DAYS` and `ts < now − 150d` using exact timestamps.

Reproduced: a hit aged HOLD_DAYS + 12 h, and a held hit aged 150 d 12 h, survived two consecutive retention runs ("purged by registry: nothing"). Meanwhile all three checks fired:

- /health: ok:false, retention_breach `[hits.entry_plate, hits.read_plate]`
- `sentinel_audit --db`: exit 2
- alert_check: exit 1, RETENTION BREACH

With hits arriving most days, every hit spends 24–48 hours in that breach band. That is round 4's complaint that the audit tool fails a healthy deployment, back again. The purge's own arithmetic also keeps a protected hit until it is 151 or more days old; only the check that nothing acts on enforces 150.

**Fix:** the purge deletes exactly what the predicate flags — same SQL, same timestamps.

**R5-05 — Hot-list expiry is still free text compared as a string; a US-format date kills the entry at its first sighting.**

P2 turned '' into NULL but kept the cause. `d.get("expires") or None` (janus.py:2021) stores anything. Ingest checks `m_exp <= ts` (:1804) and the sweep checks `expires_ts < now` (hotlist_sync.py:88); both are string comparisons.

Reproduced with two entries set to expire one week out as `12/01/2026`. The sighted one produced no ALERT and was deactivated, with HOTLIST_EXPIRED chained. The unsighted one was swept that night.

Any value that sorts below "2" (`1/5/27`, `-`, a space) does the same. `N/A` or `none` never expires.

**Fix:** parse to ISO-8601 on input and refuse anything else with a 400; migrate stored values; compare datetimes, not strings.

**R5-12 — P9's "derived" seed is still the publisher's choice.**

The seed is SHA-256 of the members, `cycle_start` and the chain root (janus.py:4424-4430). But `cycle_start` is any real date the supervisor posts (:3449-3454), and the root changes on any chained read.

The publisher computes schedules offline and posts the date that gives the pairing they want. Making agency-b the auditor of agency-a took 3 candidate dates in the clean run (1 in the first run), and the published schedule contained `(agency-b → agency-a)`. A GET /hits (which chains HITS_VIEW) also changes the root input.

COMPACT.md's "nobody picks it … grinding it would require rewriting the chain itself" is false.

**Fix:** take `cycle_start` from the previous cycle's end (or fix it in the agreement), and draw the randomness from something no single member controls — for example, a hash of every member's signed commitment, or a checkpoint root committed to before publication.

**R5-15 — OCR flicker through the shipped bridge loses the stolen-plate alert.**

The bridge dedupes in memory on `(event_id, plate)` (frigate_bridge.py:233-239). 1.2.1 Janus supersedes whenever a redelivery's plate differs, whatever the confidence (janus.py:1900). Superseding withdraws the pending hits and deletes their outcome rows (:1911-1918).

Reproduced with three Frigate events for one vehicle, sent through the real bridge: update ABC123 (0.80) → update ABC128 (0.85) → end ABC123 (0.91).

- Event 1: ALERT.
- Event 2: "superseded"; the alert is withdrawn.
- Event 3: the bridge drops it as a duplicate of event 1.
- Result: no pending hit; the stored read is ABC128; the chain shows ALERT, then READ_SUPERSEDED, and nothing after.
- Control: the same final event sent straight to Janus re-alerts.

P13's "the corrected final OCR wins" fails exactly when the OCR settles back on an earlier guess. Deleting the withdrawn hit's outcome row also contradicts S14's "nothing deletes it".

**Fix:** decide duplicate-versus-supersede in one place (Janus, by confidence and event phase). The bridge forwards every update/end with its event id. Never delete an ALERT's outcome — mark it superseded.

**R5-16 — A late redelivery overwrites the read behind a VERIFIED hit, and the evidence bundle loses it.**

The supersede UPDATE rewrites `plate` and `plate_raw` in place (janus.py:1903-1907), even when the read already produced a verified hit. A different plate wins even at lower confidence. READ_SUPERSEDED records only the new plate_ref (:1919-1922).

Reproduced:

- When its hit was verified, read 2 was ("EVD500", raw "EVD 500", conf 0.93).
- A redelivery reading "EVD580" at 0.41 confidence changed it to ("EVD580", "EVD580", 0.41).
- The hit still says VERIFIED / EVD500.
- The evidence export made afterwards has `reads.json = []`, because the ±1 h read query matches on plate (:2764).

The camera's original reading — what the officer acted on — is no longer on file anywhere.

**Fix:** make reads append-only; a correction is a new row linked to the old one, and a verified hit pins its source read.

**R5-17 — The cross-audit never checks the partner's checkpoint age; only the audited partner's own server does.**

compact.py (:207-260) verifies the pinned signature and recomputes the partner's chain, but never looks at the checkpoint's `ts`. The 26-hour freshness rule lives only in the partner's own `/compact/checkpoint-receipt` (janus.py:3222-3232) — the audited party vouching for itself. compact.py also saves its state mark at the checkpoint height (:259), so entries past the checkpoint are never anchored.

Reproduced against a mock partner serving a correctly signed checkpoint dated 200 days ago and accepting the receipt (i.e. a modified partner build, the threat the cross-audit exists for):

- Run 1: ok:true.
- The partner then rewrote every entry after the checkpoint.
- Run 2: ok:true ("recomputed 0 entries").
- Our Janus recorded both as passing audits.

**Fix:** compact.py fails when the checkpoint is older than 26 hours, and advances its mark to the verified live height so post-checkpoint history is anchored by the auditor too.

**R5-19 — A lost-key restore trusts the backup set's own key, then deletes the host's signing key.**

When the host has no audit key — the case restore.py's docstring calls the supported recovery path — `_find_audit_key` falls back to `<set>/audit_key` (restore.py:114-126), and the no-host-key branch accepts the HMAC alone (:226). The manifest signature is checked only when present (:197-202). So an attacker set that omits `manifest_sig` and carries its own key plus a matching HMAC installs, even with the host's `signing_pub.pem` sitting beside the database.

Reproduced:

- Exit 0, "restored OK".
- The attacker's users.json is installed, including an extra supervisor account `evil.admin`.
- The audit key and signing key are both replaced with the attacker's.

`os.replace` keeps the original file mtimes (:261), and the prune runs right after (:330-348). So the host's real signing and public keys, moved aside seconds earlier, are deleted ("pruned pre-restore copy …signing_key.pem… (> 14 days)") two lines before the script prints "previous live files kept".

Control: the same set against a host that still has its audit key → REFUSING.

**Fix:** when a host `signing_pub.pem` (or `--pubkey`) exists, require a signature that verifies against it. Never let a key supplied by the set verify the set. Exempt moved-aside key files from the prune, or touch them when moving.

**R5-20 — One supervisor can pull a plate's full retained history with no Tier 3 request.**

Evidence export with `expand=true` is supervisor-only and needs only a free-text reason (janus.py:2740-2755). It returns every retained read of the hit's plates (:2753). The hit itself needs only a hot-list membership (any open case, one key) and a verification (one key — the same person).

Reproduced with sgt.reyes acting alone: hot-list TGT100 → ALERT → verify own hit → export with expand → 11 reads over 11 days from 9 cameras.

- No TIER3 entry, no tier-3 QUERY, no auth_basis.
- EVIDENCE_EXPORT chains `expanded: true` but not the reason (:2828-2831).
- Control: the same supervisor's tier=3 search → 403.

Round 3 raised expand only for suppressed plates. The general case is a side door around the two-key judicial gate.

**Fix:** expand requires an executed Tier 3 request for the same case and plate (two keys + basis); otherwise cap it at the Tier 2 window, or remove it.

### Minor (all reproduced)

- **R5-06** — Verifying with `hit_id` sent as `"1.0"` works (SQLite coerces it to hit 1) and is chained raw. `_as_int("1.0")` (janus.py:1350) then fails, so the custody excerpt in the court bundle drops the VERIFY entry (excerpt kinds: `["ALERT"]`). **Fix:** normalize ids at the API boundary (int, or 400).
- **R5-07** — The /compact/witness supervisor path accepts any `agency` string (janus.py:3376) and chains it in a scrubber-exempt field (sentinel.py:748). `"ABC1234 parked 410 Elm 14:02"` is now permanent chain text that partners' chain_auditors read. **Fix:** require a registered partner or AGENCY; hash anything else.
- **R5-08** — /health `ok` (janus.py:4379) and alert_check ignore `cameras_silent` and `overdue_holds`. With all 10 registered cameras never having reported and one hold past review: `ok: true`, alert_check exit 0 "healthy". **Fix:** fold both into `ok`, or give them their own named alert reason.
- **R5-09** — POST /holds with scope=hit accepts free text as the hit ref (janus.py:2139). `holds.ref` is allowlisted as non-plate (sentinel.py:380), so after retention the reason is nulled and the ref text stays forever, while the schema test passes. **Fix:** validate the ref as a hit id; register the column.
- **R5-10** — The rotation-void two-key isn't bound to a cycle (janus.py:3314-3349). sgt.reyes requested a void of a cycle that had already ended; capt.voss then published a new cycle; the auditor's confirmation deleted the new one. **Fix:** bind the request to the cycle id, expire it, and clear it on publish.
- **R5-11** — Re-filing an earlier signed pass after a newer fail (both inside 26 h) makes the pass the latest row again (janus.py:3144). This contradicts COMPACT.md's "a pass from yesterday does not survive a failure from this morning". **Fix:** refuse reports older than the latest recorded one for that agency; dedupe on report_hash.
- **R5-13** — `rotation.py --verify` rejects genuine Janus schedules: always when the members were posted unsorted (rotation.py:97 vs janus.py:3487), and for 2-member cycles whenever Janus shuffled them (2 of 6 here; rotation.py:105). The published document also omits the chain root used. **Fix:** one shared builder; publish the root.
- **R5-14** — Pre-1.2.1 (v1) chain entries keep kind and ts outside the hash. I rewrote both columns on a 1.2-written EVIDENCE_EXPORT entry and verify still said ok (the v2 control breaks). **Fix:** for v1 entries, verify cross-checks the columns against the payload's own ts and kind (sentinel.py:811).
- **R5-18** — URL-mode sentinel_audit passes a system that has published no checkpoint with a warning (exit 1; sentinel_audit.py:247). The gate treats the same state as CLOSED. **Fix:** fail.

Code-read notes (minor, not separately run):

- The hot-list-add refusal still tells any detective that a plate is under a protection order (janus.py:1998-2000). This was round 3's oracle item.
- retention.py commits the purge (:302), then chains RETENTION_PURGE on a new connection (:323-332): commit before log.
- Bundles destroyed by retention are chained only as a count (:246-265), so custody excerpts never show their destruction.

## 4. Rulings on the three judgment calls

**P1 — a share with no `tier` field defaults to tier 2: ACCEPT.** Observed: no tier → 200, chained as tier 2 (O-1). The default can only produce the one lawful scope, so it can't widen access. Optional: chain `tier_defaulted: true` so partner conformance stays visible.

**P4/A28 — env-key 1.1 deployments are refused at boot: the refusal is right, but shipping it without a ceremony is not.**

C-A28 holds: exit 3, `unpinned_key_over_existing_chain`. Two problems remain:

- The message tells the operator to "restore the key (env NOCTUA_AUDIT_KEY or the key file beside the database)". An env-key operator has already done the first, and the real remedy isn't stated.
- Forcing the key into a file beside the database changes the custody model for an agency that injects it from a secret store.

Ruling: keep the refusal; add an explicit, chained pin ceremony and document it. For example, `janus.py --pin-existing-chain <fingerprint>`: the operator supplies the fingerprint of the key they intend, checked out-of-band against the 1.1 key or a backup, and Janus pins it and chains KEY_PINNED. Separately, R5-03 is the bigger blocker on this path: no 1.1 database should be upgraded to 1.2.1 at all until it is fixed.

**Eight silent verdicts — not a pass on their own.** A harness that died because its setup was refused proves the setup's input is refused, not that the harm is closed. Each silent verdict needs a re-aimed test that attempts the same harm by a route the patch still allows.

- **A28, A37:** the refusal is the fix. A37 has a positive assertion (run_tests.py:2349). A28 had only a comment; I added C-A28, which holds.
- **A29, A30, A14b:** legitimately re-aimed by the builders (run_tests.py:2372-2401, 2354-2370, 2289-2292).
- **A27:** a negative control; fine.
- **A14c:** never re-aimed, and its loader can no longer find the renamed `build_schedule`. Re-aimed, it **reproduces** (R5-12).
- **A18:** the builders re-aimed it with one authenticated caller. Re-aimed with anonymous concurrent callers, the fix has a new hole (R5-02).

Two of the eight fail once re-aimed.

## 5. ONE forced change

**One invariant, one decision — proven differentially, on an upgraded database, through the shipped ingest path.**

Wherever two components decide the same question, there is exactly one decision function, and every consumer calls it. Round 6's acceptance must include a differential test that drives both consumers over the same inputs and fails on any disagreement. That test runs on a database built by the 1.1 code and upgraded in place, with reads entering through frigate_bridge.py rather than straight to /reads.

1.2.1's worst defects are all one invariant decided twice:

- **Is this plate protected?** — plaintext SQL vs plate_ref (R5-03)
- **Is this hit past retention?** — floored days vs exact timestamps (R5-04)
- **Is this event a duplicate or a correction?** — bridge vs Janus (R5-15)
- **Does this schedule reproduce?** — rotation.py vs `janus.build_schedule` (R5-13)

Concretely:

- Re-key suppressions to one identity, and have the SQL filter and `hit_suppressed_now` read it.
- Make the purge delete exactly what `registry_breaches` flags.
- Decide duplicate vs supersede only in Janus.
- Have rotation.py import the one schedule builder.

312 checks passed because each was written against the same implementation it checked. The other code-critical items (R5-01, -02, -05, -12, -16, -17, -19, -20) must also be fixed in the next patch. They're listed above; this forced change is the condition that stops the class from recurring.

## 6. Legal / institutional questions — routed, not settled

1. **Act 668 of 2025** stays flagged-not-settled. Nothing in round 5 changes that.
2. **§ 12-12-1804(a) and batch purging (R5-04).** The purge's own arithmetic deletes held hits only at 151+ days of age, plus up to a day of scheduling slack. Whether that satisfies the 150-day cap is for the City Attorney. The code fix is trivial either way.
3. **Full-history evidence export (R5-20).** Is exporting every retained read of a plate, on one supervisor's key, a search that needs the Tier 3 basis (warrant or court order) and two keys? → City Attorney and the Commission's written policy (§ 12-12-1808(b) scope is already in Lane 2).
4. **Corrected OCR after reliance (R5-16).** What record must the City keep when a camera read that produced a verified alert is later corrected? (Discovery and chain of custody.) → City Attorney / prosecutor.
5. **Plate text in the permanent chain (R5-07).** A hash chain can't delete an entry without breaking. Is chain text that names a plate "captured plate data" under the 150-day cap? → City Attorney.
6. **Existing 1.1 data (R5-03).** If any 1.1 database holds real protection orders, it must not be upgraded to 1.2.1. If one already was, the orders have not been enforced on the live paths since the upgrade; who must be told is for counsel. → City Attorney.
7. **Compact operations (O-2).** The receipt leg requires the partner's latest receipt to name our newest checkpoint, so the share gate closes at every daily checkpoint until that partner re-audits. Audit timing relative to checkpoint publication is a term for the Compact agreement, not code.
8. **Witness-remote independence and key custody (P5, R5-19).** Whether the witness remote is truly off-box, and who holds the signing and audit keys, are Commission decisions (already routed as CANT-DO).
