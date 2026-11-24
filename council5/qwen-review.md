# Round 5 — Qwen seat review of NOCTUA 1.2.1

MODEL/EFFORT: **Qwen4-Max, Thinking mode** (per UI; account "Free," no upgrade prompt). Qwen's own opening line does not name the tier (claims no picker is exposed to it). Chat: https://chat.qwen.ai/c/9b584bc7-d07d-40a3-a491-3fda50264fa9 — ran 10:04–10:18 AM CST, Nov 24, 2026 (harness-measured). Five files attached after the merge fix (tests+attacks combined). The attached sentinel.py rendering was text-mangled in Qwen's UI, so it fetched the repo copies of janus.py/sentinel.py and ran its reproductions against those. It did NOT re-run the builders' 312 suite or the attack suite (no janus11 fixture) and says so.

**Verdict: NOT CONVERGED** — all four criteria NO.

P-items: FIXED = P1, P2, P5, P7, P8, P10, P12, P14; FIXED (residual noted) = P6 (F8), P9 (F4), P11 (F7), P13 (F1c/F6); FIXED-BUT-WRONG = P3, P4.

## Headline finding — F1 [CODE-CRITICAL] (converges with Claude seat 2's R5-03, extends it)

The 1.2.1 migration repairs exactly two columns (reads.plate, hits.read_plate) and leaves three protection stores broken on upgraded databases; each consequence reproduced with the shipped SQL:
- **F1a** Legacy hot-list memberships stop alerting: the hotlist→hotlist_members migration copies plate verbatim ('VIC 309'), but _hits_for_read matches the canonical ingest plate ('VIC309') → no match, no alert, migration reports nothing.
- **F1b** Suppression runs under TWO identities: SQL shaping compares s.plate = reads.plate textually; Python shaping compares keyed refs. Migrated orders have suppressions.plate = NULL (column added, no backfill) → an order can hide a hit on one path and disclose it on search/share/Tier-3 paths, or be void everywhere. Neither branch is detected, chained, or surfaced in /health. Also raises a test-coverage contradiction: the builders' P4 pass implies their janus11 fixture already had the plate column — the 1.0-shaped upgrade path may be untested. (Instrument the P4 test to print the migrated suppression row.)
- **F1c** Legacy holds protect nothing: migrated holds get review_by = NULL; HIT_PROTECTED_SQL requires review_by IS NOT NULL → hit_protected False, registry flags the hit, and the next retention run DELETES a hit under an active litigation hold. overdue_holds() doesn't surface the NULL hold either. Silent data loss.

## Other findings

- F2 [minor] /hits filters suppressed rows AFTER the LIMIT (ORDER BY id DESC LIMIT 400 → filter → [:200]) — existence oracle + completeness bug on a disclosure path; run_search filters in SQL for exactly this reason.
- F3 [minor] Stale-config fail-closed is GET-only in practice: POST /verify, /hotlist, /holds(+release), /outcomes, /suppressions(+release), /report/compile, /reads don't check config_closed() — converges with Gemini N6 / Vesper F4 cluster.
- F4 [minor] Rotation implementations diverge at n=2 (Janus Fisher-Yates vs rotation.py static pair) and Janus's published sched_doc lacks the fields rotation.py --verify reads → verifier rejects genuine schedules. (Converges with Claude R5-13.)
- F5 [minor] Scrubber leaf-name exemption hashes plate-shaped agency IDs in ROTATION_PUBLISH.members → chained rotation record no longer matches the published schedule. Needs path-aware exemption.
- F6 [minor] READ_SUPERSEDED: any different plate supersedes regardless of confidence (STL777 @0.93 withdrawn by STL77 @0.61 replay) → correct alert + outcome row erased; counters.alerts never decremented on withdrawal. (Converges with Claude R5-15.) Raises a § 1805 reporting question (delete vs mark-withdrawn outcome rows) → Ben.
- F7 [minor] flush_deferred outside DBLOCK/Chain._lock on the shared connection — converges with Gemini N3 / Vesper F1.
- F8 [minor] restore.py verifies the chain AFTER the swap — converges with ChatGPT F1.
- F9 [minor] Unauthenticated full-chain verify via /health + /audit/verify before auth; cache check-and-set unlocked → concurrent anonymous scans. (Converges with Claude R5-02.)
- F10 [minor cluster] custody_excerpt omits OUTCOME_UPDATE; backup.py skips audit_key when NOCTUA_AUDIT_KEY is set (env-key backups can't unlock a restored chain; undocumented); a KEY_LOCKED boot still runs schema migrations/backfills (incl. DROP TABLE hotlist) before exit(3), unchained (converges with DeepSeek-native N1's lock-path concern); the A28 lock message misleads (tells operators to do the thing being refused); /report?snapshot=abc → 500; unbounded chain growth via SHARE_BLOCKED/receipt re-posts (no cap like AUTH_FAIL's).

## Rulings

P1 default ACCEPTABLE (document it as the only tier). A28 refusal RIGHT, ceremony incomplete (one-command pin-audit-key, fix the lock message, runbook check). Silent verdicts NOT self-legitimating — per-id re-aimed tests owed; A27's manual verification must be scripted.

**Forced change: make the in-place upgrade a registry-driven, tested repair, and collapse suppression to one identity** — iterate PLATE_DATA_STORES at first boot: canonicalize hotlist_members, backfill or explicitly invalidate-and-chain un-re-keyable suppressions, backfill/re-issue holds.review_by, chain MIGRATION with per-store counts, /health marker for unrepaired rows; one suppression helper for SQL + Python paths. Acceptance: real 1.1 AND 1.0-shaped DBs, F1a/b/c fail-before/pass-after, instrumented migrated-row print. (Converges with Claude seat 2's "one invariant, one decision" forced change.)

[Full verbatim text was delivered in the browser-task handoff, Nov 24 10:18 CST.]
