# HANDOFF — NOCTUA 1.2.7 builder seat

## Goal
Implement commission items V1–V15 (council9/SYNTHESIS.md §6) in the new
tree `janus127/` (copied from janus126/), with a discriminating V
battery (tests/run_v127_cases.py: every case FAILS on janus126, PASSES
on janus127), the full prior battery green via one cold
`./run-next.sh`, and TRACK-127-REPORT.md. No git operations, no
pushes. Prior trees untouched (janus126 janus.py md5
`9e39e0414cf4b782eb93aaf05573e8bc`, sentinel.py md5
`dca5d958da4c8e4e7be775eaae092c7f` — verified at copy time, to be
re-verified at the end). Shared docs/ edits only where the commission
names them (CANT-DO entry, INSTALL §8 checkbox, COMPACT.md line).

## Done definition
- [x] V1–V15 implemented in janus127/ (V14 = no code, answered in writing)
- [x] tests/run_v127_cases.py discriminates (fails on janus126, passes on janus127)
- [x] S10 test-only fix per synthesis §5 conditions
- [x] Full battery green on final code via one cold ./run-next.sh (or disclosed restart recovery, runner's exact commands)
- [x] TRACK-127-REPORT.md: dispositions, judgment calls flagged, counts + log paths, honest flags, DeepSeek F5 answer, Claude B R-F/122 answer
- [x] janus126/ baseline md5s re-verified unchanged

## Current state (evidence)
- 2026-11-25 ~17:31 CST: tree copied from janus126 (rsync, scratch
  contents + __pycache__ excluded); md5s identical (see Goal).
  HANDOFF + runner rewritten for 1.2.7.
- ~17:45–18:20 CST: EXPLORATION COMPLETE. All V1–V15 code sites read
  in janus127 (janus.py auth/lockout/anchor/hotlist/verify/pickup/
  evidence/restore-marker regions; sentinel.py sink + registry;
  scripts restore/provision/backup/checkpoint/sentinel_audit;
  harness Boot sites in run_tests/run_q122/run_r123/run_s124/
  run_t125 + attacks round6 common; u7/u9/u11 case shapes).
  Design decisions for every item are formed (see the builder's
  working notes in TRACK-127-REPORT.md when written; key ones:
  V1 = key_verified predicate INSIDE _auth_lock_note_failure with a
  safe-default False; V4 = LAB_MODE beside DEMO_MODE, ceremony fence
  in the three dispatchers, harness Boots default NOCTUA_LAB=1 with
  an auto-drop once the fixture is provisioned; V5 = chain-append
  BEFORE meta mutation in _anchor_apply + reason-gated auto-clear;
  S10 retry gated on NOCTUA_BATTERY_CONTEXT=full set only by
  run-next.sh so a standalone drop still fails).
- R-F/122 ANSWER ESTABLISHED (for the report): round6/common.py's
  TREES maps slot names to SEAT_WORK dirs; run_round6.py symlinks
  the TREE UNDER TEST into the "janus122" slot (historical name), so
  f2d/f4 booting "122" run the test tree's janus.py. The adaptation
  in both files vs their .orig-124 originals is exactly one SETUP
  line: the hotlist add's actor DET→SUP (U6 made a detective's add a
  pending submission); every assertion unchanged. Actor-changing,
  so inside R-F only with the coverage companion — the U battery's
  U6 cases cover the detective-submission path, and synthesis §5
  names the V2 case as the retroactive companion for this sweep.
- DeepSeek F5 ANSWER ESTABLISHED: anchor_fenced() call sites are
  _post/_get/_delete/_health — all under DBLOCK; the only other
  path is boot via _startup_anchor_check (single-threaded). No
  out-of-lock call site exists.

## Current state update (post-implementation)
- Implementation COMPLETE: all V1–V15 code in janus.py / sentinel.py
  / scripts (restore, provision, backup, checkpoint, sentinel_audit),
  COMPACT.md, shared docs (CANT-DO entry, INSTALL §8 checkbox),
  harness LAB adaptations (run_tests Instance, run_q122/run_r123/
  run_s124/run_t125 Boots, round6 common Boot, round5 lib5
  boot_script), U-battery adaptations (u9 re-aim, u11 sweep;
  run_u126_cases.py.orig-126 preserved), S10 fix (retry gated on
  NOCTUA_BATTERY_CONTEXT=full, exported by run-next.sh), load
  envelope health-availability measurement. All edited files
  ast-parse. Smoke test passed (scratch/smoke.py): ceremony boot
  fences /hits 503, ingest 201, state "ceremony"; LAB boot serves.
- V battery written (tests/run_v127_cases.py, 16 cases). First
  dual-tree run in flight: scratch/v-battery-dev1.log.

## Exact next step
Cold run #1 (log scratch/battery-20261126-000513.log) DIED
mid-R-leg (session interruption, ~18:21 CST — the 1.2.6
failure mode). Legs completed: builders FAIL (diagnosed),
round4 PASS, round5 PASS, round6 FAIL (F9 Q02 only),
q-plus-invariants FAIL (Q02 only). ALL fallout fixed and
verified standalone: janus.py KEY_LOCKED guards on the LAB
boot appends (Q02 root cause); alert_check.py CEREMONY/LAB
branches; run_tests.py adaptations (.orig-126 preserved:
7 expectation updates + _fixture_provisioned V6-mirror +
P4 menv LAB declaration). Standalone verification:
builders 335/335 exit 0 (scratch/builders-fixcheck3.log);
Q battery exit 0 incl. Q02 growth 0 (scratch/q-fixcheck.log).
Run #2 (log scratch/battery-20261126-024001.log) was STOPPED
by the builder when Addendum 1 (V16-V18) landed: builders /
round4 / round5 PASS on pre-addendum code; it is a diagnostic
run, not the acceptance run. V16-V18 implemented + cases
v16/v17/v18 discriminate (scratch/v-battery-dev5.log).
Run #3 (one-shot, log scratch/battery-20261126-024941.log)
was RESTART-KILLED inside the builders leg (third VM
interruption of this build). Code unchanged since. Per the
commission's disclosed-recovery protocol (the 1.2.6 pattern),
the acceptance battery was completed LEG BY LEG with
run-next.sh's exact commands and environment (TMPDIR +
NOCTUA_BATTERY_CONTEXT=full exported per leg).
BUILD COMPLETE — all legs green on final code (logs
scratch/legs3/): builders 335/335, round4 PASS, round5 PASS,
round6 PASS, Q+invariants PASS, R 20/20 (after the R15
literal re-aim + full re-run), load COMPLETE (health
availability 18/20 answered, 2 dropped, 4 non-payload —
reported, not gated), S 25/25 (S10 passed with 1 logged
dropped-sample retry), T 20/20, U 21/21, V 19/19. janus126
md5s re-verified unchanged. TRACK-127-REPORT.md is final.
Remaining: the chair's cold verification, then Round 10.
FIX LIST (do not apply mid-run):
- PRODUCT: scripts/alert_check.py names two retired totp
  states ("unprovisioned_locked", "provisioning"); 1.2.7's
  states are ceremony/lab/provisioned. Add CEREMONY and LAB
  branches (parallel to DEMO MODE) — V4 scope.
- run_tests.py adaptations (preserve run_tests.py.orig-126
  first): registry_version literal -> "1.2.7" (line ~409);
  degraded totp state "provisioning" -> "lab" (~427);
  alert_check check "PROVISIONING" -> "LAB" (~483); S3
  detective export of suppressed hit 403 -> V13 uniform 409
  (~854); S3 export after verification 403 -> 409 uniform
  (~863); P10 REGISTRY_VERSION "1.2.6" -> "1.2.7" + stale
  check name (~1400); P3 detective export of now-suppressed
  hit 403 -> 409 uniform (~2374).
V battery is 16/16 discriminating (dev logs scratch/
v-battery-dev1..4.log). TRACK-127-REPORT.md drafted except
the battery-results section.

## Remaining steps
1. V battery discrimination verified per case.
2. Cold ./run-next.sh full battery; fix fallout (R-F rules for any
   living-suite adaptation: assertion-preserving, .orig preserved,
   coverage removed named + companion case added).
3. TRACK-127-REPORT.md; re-verify janus126 md5s.

## Blockers
- None at start.

## Settled decisions
- Synthesis §4 rules the U9 mechanism: populated-arrival marker and
  legacy probe RETIRED as gating mechanisms; unprovisioned =
  ceremony state everywhere; NOCTUA_LAB=1 carries fixtures.
- Version literals (DeepSeek F2/Qwen F9) adjudicated NOT a U11
  violation; only the two named residues are in V15.
- S10: exactly one logged retry of a dropped sample; wrong value
  still fails; standalone drop still fails.

## Model / effort / limits
- Builder subagent (Muse Spark). Limit status: unknown; update
  this file at ~70%.
