# TRACK-123-REPORT — NOCTUA 1.2.3

Builder: delegated subagent (Vesper-orchestrated), Nov 24, 2026.
Base: janus122/ copied to janus123/; no earlier tree modified.
Commission: council6/SYNTHESIS.md, items R1–R15, plus late items
R16 (DeepSeek F3), the Qwen residuals, and the demo-only
`imperator` account (Corey, Nov 24). Test execution authorized by
Corey ("Yes — run the NOCTUA test suites", Nov 24).
Nothing published by the builder — publication is the
orchestrator's step.

COMPLETED BY THE ORCHESTRATOR (Vesper), Nov 24, 2026, from her own
cold re-run of the full battery (./run-next.sh, exit 0; log:
scratch/battery-latest.log, driver output scratch/vesper-battery.out).
The builder's per-leg runs agree with the re-run on every leg they
share; where they differ (builders' count), the re-run is the
larger number because the imperator and R16 cases landed after the
builder's last full-suite pass.

## Acceptance legs — orchestrator's cold re-run, all PASS

| Leg | Result |
|---|---|
| Builders' suite (tests/run_tests.py) | 332/332, exit 0 |
| Round-4 attacks (run_round4.py) | PASS — 41 verdicts, only A9b CONFIRMED (the labeled contrast control) |
| Round-5 seat-1 suite (run_round5.py) | PASS — 21 verdicts, 0 reproduced |
| Round-6 seat-2 harness (run_round6.py) | PASS — every verdict PROPERTY HOLDS / not reproduced |
| Q battery + invariants (run_q122_cases.py --invariants) | 35/35 |
| R battery (run_r123_cases.py, 123 vs 122) | 20/20 cases PASS, each discriminating except R14 (see below) |
| Load envelope (run_load_envelope.py) | completeness holds to 6 burners; 500/500 landed at every level |

Note on the log: two "FAIL P10 schema" lines appear inside the
round-4 leg — they are the registry-breach detector correctly
reporting violations planted by an attack scenario, inside a leg
whose own verdict is PASS. The builders' leg itself is clean.

## Per-item dispositions (R battery: baseline 1.2.2 fails, 1.2.3 passes)

- R1 protection orders are records — PASS, native and migrated
  (two orders coexist; releasing one leaves the other protecting:
  verify 403 after release on 123, 200 on 122).
- R2 migration integrity — PASS (per-item isolation;
  migration_status complete with counts, defects [], unverifiable
  0; no DML on a locked boot — dedupe chained on unlock instead).
- R3 pin ceremony — PASS on real 1.1 and native DBs (122 crashes
  with the `fragment` column error; 123 rc 0, boot after ceremony).
- R4 no out-of-lock side effects — PASS (the F4 lost-write
  construction now lands the write, attributed, first attempt).
- R5 sink battery — PASS both shapes (burst regression; the
  twin/rollback shape that threw "cannot start a transaction
  within a transaction" on 122 yields exactly one sink copy on 123).
- R6 rotation ceremony — PASS (late commit after reveals 409;
  unsigned supervisor transport 403; cancel path 200/200; fresh
  commit after cancel 201).
- R7 compact anchoring — PASS (two consecutive runs pass on 123;
  the second fails on 122; future-dated checkpoints rejected).
- R8 one verification implementation — PASS (both tools now fail a
  relabeled chain identically through sentinel.verify_chain_rows).
- R9 supersede completeness — PASS (original hit WITHDRAWN on 123;
  stranded PENDING on 122).
- R10 restore trust root — PASS (attacker-built set refused, rc 2,
  nothing installed; pinned legitimate set restores).
- R11 evidence parity — PASS (orphaned bundle purged by retention;
  breach list empty after the run).
- R12 fence scope — PASS. R13 chain-growth attribution — PASS.
- R14 load envelope — PASS on its own terms and NON-discriminating
  by design: it measures, it does not separate the trees. Both
  trees land everything; 1.2.3 is slower per append under load
  (paired run: 1.9 appends/s vs 1.2.2's 5.6; standalone envelope:
  16.2/s idle, 2.5/s at 3 burners, 2.2/s at 6 burners, completeness
  holding throughout). The honest reading: 1.2.3 bought audit
  correctness with throughput, and the envelope where completeness
  holds is now measured and stated instead of assumed.
- R15 honesty sweep — PASS (version stamps, /health
  migration_status + chain_scrub_flags, deterministic INV5,
  disposition-note cap min(HOLD_DAYS+30, 150)).
- R16 reads inherit hit protection — PASS both cases (a held hit's
  reads survive retention and appear in export and re-export;
  protection-order fields preserved through the lifecycle).

## imperator (Corey, Nov 24) — verified in the builders' suite
Demo seed writes a DEMO-FLAGGED users file carrying imperator with
every role; it acts across the officer/supervisor/chain_auditor/
ingest fences; it CANNOT approve its own Tier 3 request (two-key
rule intact) and a second user can approve it; a non-demo users
file containing imperator refuses the boot (exit 3).

## Defects found in 1.2.3 during the build, fixed before acceptance
1. Migration savepoint destroyed by executescript (boot crash on
   real 1.1 DBs) — fixed with individual statements; a lost
   savepoint is now a recorded defect, never a crash.
2. verify_chain_rows rejected HTTP dict rows, breaking compact.py
   and sentinel_audit.py — fixed; one implementation, both shapes.

## Judgment calls (flagged per the commission)
- R6 witness: attestation counts only from the round's designated
  attester (bye member; round's auditor at n=2). Put to Round 7.
- R12 fence line: stale case feed closes data reads; safety writes
  proceed with a chained warning. Put to Round 7.
- Plate-less legacy suppressions: recovered by matching stored
  refs against known plates, else KEPT active and counted
  unverifiable — never silently invalidated. In the R2 case the
  unverifiable count is 0.
- Release-by-plate is accepted only when exactly one live order
  exists for the plate; otherwise the caller must name the order.
- INV4's heartbeat-freshness exclusion is kept, justified in
  writing in the tree (synthesis permits justify-in-writing).
