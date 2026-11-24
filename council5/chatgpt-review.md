# Round 5 — ChatGPT seat review of NOCTUA 1.2.1

MODEL/EFFORT (UI picker, observed by the browser agent): GPT-6.2 selected, Thinking effort High (3 of 3, maximum). Chat: https://chatgpt.com/c/6b05a897-875c-83ea-8c76-aa6d8e4b8cb5 — ran 9:07–9:49 AM CST, Nov 24, 2026 (harness-measured). This seat EXECUTED reproductions for its findings.

**Verdict: NOT CONVERGED** — all four criteria NO.

P-items: P1 FIXED · P2 FIXED · P3 FIXED · P4 FIXED (own migration probe: VIC 309→VIC309 canonicalized, raw preserved, ''→NULL expiry, MIGRATION chained, suppressed legacy read excluded — but built a legacy-shaped DB by hand, not from the actual 1.1 tree) · P5 FIXED · P6 FIXED-BUT-WRONG · P7 FIXED-BUT-WRONG · P8 FIXED · P9 NOT FIXED · P10 NOT FIXED · P11 FIXED-BUT-WRONG · P12 FIXED · P13 FIXED-BUT-WRONG · P14 FIXED-BUT-WRONG.

## New findings (all reproduced at runtime by this seat)

- **F1 [DEPLOYMENT-BLOCKING] Restore installs an invalid chain before checking it.** backup.py signs a manifest over a snapshot without verifying the chain; restore.py moves the live DB/WAL/SHM/keys aside, installs the backup, and only THEN verifies — on failure (exit 3) the corrupted DB is left live, the original sits in .pre-restore-*, marker written, no rollback. Reproduced by corrupting audit seq 1's kind column: backup exit 0 (signed), restore exit 3, broken DB live. Also: manifest doesn't independently require noctua.db. FORCED CHANGE: backup/restore must be a verified, failure-atomic operation (verify before signing; stage + verify before swap; failure leaves the live installation byte-identical).
- **F2 [CODE-CRITICAL] Evidence re-export destroys the previous bundle outside the transaction.** janus.py:2780–2832: creates new bundle, deletes old, then updates DB + chains + commits. Reproduced with an external writer lock: re-export returned 500 "database is locked" — old bundle already deleted, new bundle orphaned, DB row still points at the old bundle, chain still shows 1 export.
- **F3 [CODE-CRITICAL] Local supervisor can attest for another agency without its signature.** janus.py:3350–3407 (esp. 3376–3378): any supervisor bypasses the partner-key branch; POST /compact/witness {agency: "agency-a", ok: true} from a local supervisor → 201, false attestation recorded, and rotation_status counts it (janus.py:3683–3686). Fix: supervisors attest only for the home agency; partner attestations require the registered Ed25519 signature + schedule membership.
- **F4 [CODE-CRITICAL] Scrubber exemptions leak raw plate-shaped strings into the chain.** sentinel.py:742–773 exempts fields named cam/camera/agency globally. INGEST_REJECTED chained cam="ABC123" verbatim for an unregistered camera; /compact/witness chained agency="ABC123" raw. Exemption must be registry-verified per value, else hash/omit.
- **F5 [CODE-CRITICAL] P10 retention lifecycle cluster.** 5A: hit_protected checks the evidence row (bundle IS NOT NULL…) but never that the bundle EXISTS on disk — deleted bundle dir → retention purges nothing, /health clean, hit protected by evidence that no longer exists. 5B: unconfirmed disposition disp_note (free text, can contain plate text) has no destruction clock without an export (destroyed_ts/destroy_by/export_ts all NULL) — reproduced: hit purged at 31d, disp_note "VIC309" retained indefinitely, no breach flagged. 5C: partner share_queries.case_ref is raw, unvalidated, allowlisted non-plate — reproduced: case_ref "VIC309" survives retention at 40d while why is purged; permanent plate-text storage by design oversight. 5D: share_queries.plate_ref is class "derived" with action "none" — never purged, but the breach checker flags it after the derived lifetime → permanent false retention breach after ordinary partner activity (reproduced at 40d).
- **F6 [CODE-CRITICAL] Malformed hold ref protects a hit the chain can't identify.** janus.py:2136–2151 + sentinel HIT_PROTECTED_SQL: ref GLOB '[0-9]*' + CAST matches "1garbage"→1 in SQL, but _as_int("1garbage") is None so HOLD_PLACE chains no hit field. Reproduced: hold placed (201), hit protected past HOLD_DAYS, no breach, chain silent about which hit. Fix: strict decimal validation + existence check + normalized chained ID. (Same GLOB weakness Gemini flagged as N9-minor; this seat reproduced the protective effect and rates it code-critical.)
- **F7 [CODE-CRITICAL] Accepted rollback deadlocks Compact checkpoint renewal.** read_newest_checkpoint() picks max by entries; after an accepted restore to a shorter chain, the old higher-entries checkpoint keeps winning over new post-restore checkpoints → receipts can't match, gate closes permanently once the old checkpoint ages past 26h. Verified the selection behavior directly.
- **F8 [MINOR] Docs drift:** COMPACT.md still says "NOCTUA 1.2"; compact.py docstring still describes the pre-v2 hash; backup manifest still stamps 1.2.

## Test results (this seat's own runs)

Builders' suite: reached 304 PASS, 0 failures, then stopped — the P4 fixture needs the actual janus11 tree (not among attachments) and demo files weren't attached; does NOT certify 312/312. Attack suite: every attack that executed was NOT REPRODUCED (A9b CONFIRMED as the contrast control, correctly); suite did not complete all scenarios.

## Judgment-call rulings

- P1 missing-tier default: ACCEPTABLE.
- P4/A28 refusal-to-boot: CORRECT (fail-closed); requires a documented operator runbook/ceremony, not a weaker control.
- Silent attacks: refusal-shaped setups are legitimate passes FOR THE REFUSAL only. A18 (600k concurrency) is NOT independently verified — the harness's env-key boot refusal proves key pinning, not scale behavior; builders tested 250k with a key file. Re-aim A18 with a deployment-shaped setup.

## Routed out

Act 668 (Ben); evidence-bundle retention exceptions past 150 days (Ben/ACIC — converges with Gemini's N1 question); keyed refs + partner case_refs as ALPR information (Ben/ACIC); disposition-note retention independent of the hit (Ben); Tier 3 legal basis (Ben); Compact sharing authority + partner key registration (Ben/ACIC). CANT-DO acknowledged: single-connection SQLite + global lock (small-city scale), hot-list upstream feed integration is city-specific, witness repo + key custody are institutional.

[Full verbatim text was delivered in the browser-task handoff, Nov 24 09:49 CST; this file preserves the complete substance — verdict, P-table, all eight findings with reproductions, rulings, forced change, and routings.]
