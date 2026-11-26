# HANDOFF — NOCTUA 1.2.3 build (Round 6 commission, items R1–R15)
Seat: builder subagent (Vesper-delegated)
Model + effort: Muse (this subagent session)
Updated: 2026-11-24 ~23:05 UTC
Limit status: ok — unknown %; update this file at every R-item boundary
Handoff runner: run-next.sh (re-runs the full acceptance battery cold, logs to scratch/battery-<ts>.log)

## Goal (one sentence)
Build NOCTUA 1.2.3 in ~/workspace/noctua-1.0/janus123/ implementing Round 6 items R1–R15 from council6/SYNTHESIS.md, with a discriminating test battery that fails on 1.2.2 and passes on 1.2.3.

## Done looks like (acceptance test)
- janus123/ tree complete; TRACK-123-REPORT.md with per-item R1–R15 dispositions, judgment calls flagged, test counts + log paths, measured load envelope (R14).
- ./run-next.sh exits 0: builders' suite + round-4 wrapper + round-5 wrapper + Q battery/invariants + round-6 seat-2 harness leg (all PROPERTY HOLDS / NOT-REPRODUCED) + R1–R15 discriminating battery (each case FAILS on janus122, PASSES on janus123, or has a written absence-proof in the report).
- No prior tree (janus/, janus11/, janus12/, janus121/, janus122/) modified. Nothing published.

## Current state
- Done: read council6/SYNTHESIS.md in full; tree copied (rsync, scratch/__pycache__ excluded, 1.7 MB of code); evidence read (harness README F1–F12, seat2-harness-vesper.log, vesper/gemini reviews).
- Done: FULL code survey — janus.py (5,817 lines), sentinel.py (1,567), all scripts, tests/run_tests.py, tests/run_q122_cases.py, fixtures' 1.1 plate_ref formula confirmed.
- Done: sentinel.py implementation (verify_chain_rows, key_ref_candidates + legacy_plate_ref, disp_note_days, rotation nonces binding, book-connection sink bookkeeping, streamed ledger + persisted sink_state.last_streamed_seq watermark, stamps 1.2.3, suppressions "id" registered). Import-verified.
- Done: janus.py implementation — R1 (suppressions records: surrogate id + UNIQUE(plate_ref, order_ref), per-order placement/release, ambiguity refusal), R2 (_migrate_123: per-unit SAVEPOINTs, MIGRATION_DEFECT chaining, meta migration_status, table rebuild with LEGACY-<rowid> refs, hotlist merge, suppression recovery-not-invalidation), R3 (key_ref_candidates at boot), R4 (config chaining deferred to locked sections; chain_ok_cached never computes under DBLOCK + role-gated pre-warm; import-time DML removed — dedupe into migration, seed + Chain after fingerprint check), R6 (phase freeze, no-overwrite, signature authorship, nonce floor 16, cancel path, void clears contributions, publish 1.2.3 + pubkey, witness designated-attester after standing, status counts designated + UTC active), R7 (future-dated checkpoint refused at receipt; two-sided freshness window at the gate), R9 (PENDING hits re-pointed on same-plate supersede), R12 (cause-aware fence; safety writes /reads + /suppressions(+release) proceed on feed-only staleness with chained warning), R13 (throttles keyed on authenticated user), R15 (/health migration_status + chain_scrub_flags; ok requires migration state != incomplete).
- Smoke-verified (scratch/smoke/smoke.py): fresh boot, /health migration_status complete, two orders coexist, ambiguous release 400, per-order release lifts only the named order. /health ok=False on fresh install matches janus122 (jobs overdue) — not a regression.
- Done: ALL scripts (provision R3, compact R7/R8, sentinel_audit R8/R15/M11, restore R10, retention R11/M12, backup stamp, hotlist_sync key=, rotation R6/R15, COMPACT.md + alert_check wording).
- Bugs found by the suites and FIXED in janus123: (1) _supp_rebuild used executescript (implicit COMMIT destroyed the migration SAVEPOINT -> boot crash on real 1.1 DBs) — now individual statements + _mig_unit tolerates a lost savepoint as a defect, not a crash; (2) verify_chain_rows rejected dict rows — it now normalizes /audit/range entry dicts itself (broke compact.py + sentinel_audit URL mode).
- Done: test updates — run_tests.py (stamps 1.2.3, rotation_ceremony sign_db/sign_dbs + signed partner reveals, P9 witness files for the round where agency-w is the DESIGNATED attester), run_q122_cases.py (header corrected, Q16 REBUILT on NOCTUA_SENTINEL_SINK with janus_fi fault injection, INV5 deterministic, ceremony sign_db at Q23/Q24/INV5), round4 attack1.py + round5 r5_rotation_grind.py ceremony adaptations.
- Done: tests/run_r123_cases.py (18 cases R1–R15, driver runs baseline+test), tests/attacks/run_round6.py + adapted harness in tests/attacks/round6/ (F1c rewritten — the patch-anchor premise is gone in 1.2.3; F6c exercises the new cancel path), tests/run_load_envelope.py.
- VERIFIED SO FAR: builders' 322/322 exit 0 (scratch/builders-2.log); round-4 PASS 41 verdicts A9b only (scratch/round4-3.log); round-5 PASS 21 verdicts 0 reproduced (scratch/round5-1.log); Q battery + invariants 35/35 on 123 (scratch/q-123-1.log); round-6 leg: full run had F5i text-match DEFECT + f6 crash — both were scenario/contract mismatches, fixed (F5i now probes the substantive property; F6a/F6c adapted to the two-phase ceremony the freeze mandates); F5+F6 re-run all PROPERTY HOLDS / not reproduced (scratch/round6-f5f6.log). Full round-6 re-run happens inside the final ./run-next.sh.
- In progress: R battery vs janus122 (scratch/r-1.log).

## NEXT STEP — do this first, exactly
1. R battery result (scratch/r-1.log); fix any case that fails to discriminate or fails on 123. Then load envelope (both trees). Then Q battery vs janus121 for the fail-before record. Then ./run-next.sh FULL cold run as the final acceptance evidence.
2. TRACK-123-REPORT.md (complete the per-item dispositions + judgment calls + R14 numbers); final handoff update; report to the orchestrator. NO git pushes.

## Design decisions taken during survey (binding; details in TRACK-123-REPORT)
- R1: suppressions gets surrogate id + UNIQUE(plate_ref, order_ref); one row per order; release is per-order two-key; release with {plate} only works when exactly one live order exists (keeps Q01 green).
- R2: migration becomes per-item SAVEPOINTs; failures chain MIGRATION_DEFECT + set meta migration_status; hotlist duplicate spellings merge deterministically; plate-less suppressions recovered by matching stored refs against known plates, else KEPT active and counted unverifiable (never silently invalidated — F2c).
- R3: sentinel.key_ref_candidates(key, plate, state) shared by janus verifier + provision.py. 1.1 formula (fixture janus11/janus.py:214-219): HMAC("{PLATE.upper()}|{STATE.upper()}") over the AS-SUBMITTED plate. provision.py bugs: literal "PLATE|" formula (:199), `fragment` vs real column `frag` (:220).
- R4: _reload_config never chains; pending CONFIG_CHANGED/STALE flush at the start of the next DBLOCK section (and at boot when unlocked). chain_ok_cached never computes while DBLOCK is held; pre-warm only for verify-consuming roles (supervisor/auditor/chain_auditor/jobs). Pre-lock DML moved: receipts dedupe -> migration (chained count), list_registry insert -> after fingerprint check, sink_state row -> lazy via dedicated bookkeeping connection (also fixes Gemini F5's leaked write txn).
- R5: flush_deferred watermark — sink_state.last_streamed_seq; entries with seq <= watermark never re-streamed. Q16 case rebuilt on NOCTUA_SENTINEL_SINK (a FILE path; the shipped case set NOCTUA_AUDIT_SINK_DIR, which nothing reads — the vacuity).
- R6: commit phase freezes at first reveal; commitments never overwritten (same hash = idempotent); partner filings need the partner's own identity or its Ed25519 signature (supervisor = transport only; home agency exempt — its officer IS the supervisor); cancel path (supervisor alone pre-reveal, two-key after); ROTATION_VOID also clears the cycle's contributions + pending; nonce floor 16 chars; sched_doc gains version 1.2.3 + pubkey; signed portion gains nonces_sha256 (version-gated so 1.2.2 docs still verify). Witness: attestation only from the round's designated attester — the bye member (n>=3) or the round's auditor (n=2) — and _rotation_status counts only those. JUDGMENT CALL, flagged in report.
- R7: compact.py keeps a checkpoint mark separate from the live mark; recompute anchors AT the checkpoint root (fixes Gemini F1/F7 second-run failure); future-dated checkpoints (>1h skew) fail freshness in compact.py AND at janus's receipt/gate (Gemini M1).
- R8: compact.py recompute + sentinel_audit.py audit_url verify through sentinel.verify_chain_rows (v1 kind/ts cross-check included).
- R9: same-plate supersede re-points PENDING hits to the new read version.
- R10: restore.py — the backup set's own audit key can no longer vouch (HMAC verified only under a HOST key); bare-host recovery = --pubkey / --pubkey-fingerprint pin or refusal.
- R11: retention.py purges orphaned evidence bundle dirs (no evidence row, mtime past reads class) in the same run.
- R12: feed-only staleness closes DATA READS; safety writes (POST /reads, /suppressions, /suppressions/release) proceed with a chained CONFIG_FEED_STALE_WRITE warning; file staleness closes everything as today; 503 text names the stale input + age. (Keeps Q09 green: hotlist/holds POSTs still 503 on a stale feed.)
- R13: SHARE_BLOCKED + INGEST_REJECTED throttles keyed on the authenticated user; entries carry "user".
- R14: measure first (tests/run_load_envelope.py, S18 shape under load); strengthen _append_txn backoff only if the numbers demand it.
- R15: version stamps 1.2.3 (janus VERSION + header, sentinel header + REGISTRY_VERSION, COMPACT.md, backup manifest "noctua", sentinel_audit report version, rotation.py doc version); /health gains migration_status + chain_scrub_flags; disp-note cap min(HOLD_DAYS+30, 150) via sentinel.disp_note_days in BOTH registry_breaches and retention.py; INV5 rewritten deterministic (positive recomputation; no probabilistic prediction set); INV4 heartbeat exclusion kept WITH written justification (synthesis allows justify-in-writing).

## Test-harness facts the implementation must respect
- Builders' rotation_ceremony helper commits/reveals as SUP for all members; in the 123 copy it gains sign_db= and signs partner transports with the instance key (all test partners are registered with the instance's own pubkey). Call sites to update: suite_a5, suite_p121, Q23, Q24, INV5.
- P13 route-enumeration check greps janus.py _get segments for the literal "config_closed" on every data route — keep per-route calls in _get handlers.
- suite_keyloss expects stderr "REFUSES TO START" + exit 3.
- Q18/boot polls: /health with SUP must pre-warm the verify (250k chain).
- suite_schema: every new column must be in NON_PLATE_COLUMNS; every folder under the data root must be a registered folder store.

## Remaining steps
1. sentinel.py + janus.py implementation (R1–R15 as above).
2. Scripts implementation.
3. Test updates in-tree (run_tests.py stamps + ceremony sign_db + P9 witness; run_q122_cases.py Q16 env var + INV5 + ceremony sign_db calls).
4. tests/run_r123_cases.py (discriminating battery, driver runs both trees), tests/attacks/run_round6.py + adapted harness, tests/run_load_envelope.py.
5. ./run-next.sh full battery on 123; R battery fail-before side on 122; iterate to green.
6. TRACK-123-REPORT.md; final HANDOFF.md update.

## Blockers / open questions
- None. Authorization to run all NOCTUA test suites was given by Corey (Nov 24). Builder publishes nothing.

## Decisions already made — do NOT re-ask
- Verdict of Round 6: NOT CONVERGED on 1.2.2; R1–R15 are the commission (council6/SYNTHESIS.md is source of truth).
- Sink phantoms: seat 2's fault-injection construction governs (zero phantoms); the live sink defect is lost writes (F4) — R5 tests both directions anyway.
- Strip-not-raise: KEEP strip, but surface the CHAIN_SCRUB_FLAG count in /health (R15).
- Structural DDL on locked boots OK for DDL proper; pre-lock DML is a defect (R4).
- Rotation: supervisor may TRANSPORT commitments/reveals, never author them — partner Ed25519 signature is authorship (R6).
- Disposition-note clock: HOLD_DAYS+30 capped at 150.
- /health: never-reported cameras excluded from operational health; migration_status reported separately as installation readiness (R15).
- Seat 1's C7 (per-camera caller ACLs) NOT adopted — 1.2.2 has roles, not camera ACLs.
- Documents FROZEN; Lanes 1–2 held; nothing published by the builder.

## Files that matter
- ~/workspace/noctua-1.0/council6/SYNTHESIS.md — the commission (R1–R15 + acceptance standard)
- ~/workspace/noctua-1.0/council6/harness-seat2/ — seat 2's attack harness + README finding map
- ~/workspace/noctua-1.0/council6/seat2-harness-vesper.log — orchestrator's reproduction run
- ~/workspace/noctua-1.0/janus122/ — base tree (DO NOT MODIFY)
- ~/workspace/noctua-1.0/janus123/tests/fixtures/{janus11,janus12}/ — real predecessor trees for migration/pin tests

## If you are picking this up cold
- Environment: TMPDIR must point at workspace scratch (/tmp tmpfs is 512 MB and fills). Kill stray servers with `pkill -f 'janus[.]py'` as a STANDALONE command only. Python stdlib only; Ed25519 via system openssl CLI.
- Tests in this tree: tests/run_tests.py (builders'), tests/run_q122_cases.py (Q battery + invariants), tests/attacks/run_round4.py, tests/attacks/run_round5.py.
- run-next.sh legs: builders, round4, round5, round6 (to be created), q-plus-invariants, r-battery (to be created), load-envelope (to be created). NOTE: verify run_round4.py's tree-arg style (its docstring says --tree) and fix run-next.sh if it passes the tree positionally.


---

## ORCHESTRATOR NOTES — Nov 24, 2026 (Corey, via Vesper)

1. **Sequencing (Corey, Nov 24):** this build does NOT stop or pause for
   the 5:30 p.m. splat priority — that applies to Corey's own Claude
   seats, not this build. Build 1.2.3 out to the full acceptance battery.
   A Claude audit follows when a seat is available (Merlin retry is
   scheduled Wed Nov 25 ~9:45 a.m. CT; Corey's real Claude limit resets
   Wed). ALPR is explicitly not a rush.
2. **Vesper's signature (Corey, Nov 24):** every code file in this tree
   carries Vesper's maker's mark in its header comments, exactly:

       #  ___
       # (o o)   VESPER · the evening watch
       # (   )   Vesper, for Corey Spangler — Cabot, Arkansas
       #  ^^^

   One-line form for small files/scripts: `# VESPER · the evening watch`.
   The mark lives in source comments ONLY — never in chain entries, data,
   hashes, or behavior. Add it to files you create or substantially edit;
   do not churn files just to add it mid-build.
3. **Interface commissioned:** ~/workspace/noctua-1.0/UI-SPEC.md — a
   browser UI (login, dashboard, plate lookup, protection orders, audit
   viewer, reports) served by janus.py itself, stdlib only. It builds
   AFTER 1.2.3 converges and the audit lands. Do not start it in this
   build; do keep the API/UI boundary clean so it can.

## BUILDER NOTE — maker's mark applied (Nov 24, per note 2 above)
- Full owl header: janus.py, sentinel.py (after the shebang, before
  the module docstring).
- One-line mark: scripts/{provision, compact, sentinel_audit,
  restore, retention, rotation, hotlist_sync, backup, alert_check}.py,
  tests/{run_tests, run_q122_cases, run_r123_cases,
  run_load_envelope}.py, tests/attacks/run_round6.py, run-next.sh.
- Verified comment-only: every occurrence of the mark sits on a `#`
  comment line (grep-checked); nothing in data, hashes, chain
  entries, payloads, or behavior. All marked files pass py_compile.
  The full cold battery (./run-next.sh) ran on the marked bytes for
  every leg it completed.
- Deliberately NOT marked (not Vesper-authored in this build):
  tests/attacks/round6/* (Claude seat 2's harness, copied in-tree —
  marking it would misattribute authorship), tests/attacks/round4/*
  and round5/* (prior rounds' attack suites carried forward; two
  received only small ceremony adaptations), tests/attacks/
  run_round4.py + run_round5.py (wrappers carried unchanged),
  demo/seed_demo.py, scripts/checkpoint.py, scripts/frigate_bridge.py
  (untouched in this build).

4. **Round 7 venue (Corey, Nov 24, ~8:25 p.m. CT):** Corey has opened
   his browser with ALL his AI seats signed in (Claude, ChatGPT, Gemini,
   DeepSeek, Qwen — the shared default profile carries live cookies for
   claude.ai, chatgpt.com, deepseek.com, qwen.ai). Round 7 runs THERE,
   with the real seats, once this build's acceptance battery passes —
   not through Merlin (whose Claude was down all afternoon Nov 24; the
   Merlin design-audit retry remains scheduled Wed ~9:45 a.m. CT as a
   bonus seat, not the Round 7 path). Corey's Claude weekly limit
   resets Wed Nov 25. Every Round 7 seat gets the handoff-protocol
   clause; Vesper re-runs all legs from the public repo layout before
   calling convergence, same standard as Rounds 5–6.
