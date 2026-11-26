# HANDOFF — NOCTUA 1.2.6 builder seat

## Goal
Implement commission items U1–U14 (council8/SYNTHESIS.md §6 + Addendum 2:
U12 sink tail reconciliation, U13 restore key custody + R-A closure,
U14 anchor evaluation cost, U6 amended bogus-list ordering, U11 additions
(a)–(e)) in the new tree `janus126/` (copied from janus125/), with a
discriminating U battery, the full prior battery green via one cold
`./run-next.sh`, and TRACK-126-REPORT.md. No git operations, no pushes.
Prior trees untouched (janus125 janus.py md5
`ab455975b9eb987fa95d3a268190a3bf`, sentinel.py md5
`85c7f9e06cecc5565211ccb1d43c62d4` — verified at copy time and to be
re-verified at the end).

## Done definition
- [x] U1–U14 implemented in janus126/
- [x] tests/run_u126_cases.py discriminates (fails on janus125, passes on janus126)
- [x] Full battery green on final code — the one-shot ./run-next.sh
  was interrupted by a VM runtime restart after its builders leg
  (335/335 PASS); remaining legs ran with the runner's exact
  commands on unchanged code, all PASS (see TRACK-126-REPORT §1
  for the sequence, incl. the restore.py snapshot fix and the
  builders/round-4 re-runs on final code)
- [x] TRACK-126-REPORT.md: dispositions, judgment calls flagged, counts + log paths, honest flags
- [x] janus125/ baseline md5s re-verified unchanged

## Current state (evidence)
- 2026-11-25 ~12:32 CST: tree copied from janus125 (diff -rq clean, md5s
  identical). HANDOFF + runner rewritten for 1.2.6.
- 2026-11-25 ~13:50 CST: U1–U14 IMPLEMENTED (janus.py, sentinel.py,
  scripts/{provision,backup,restore,checkpoint,alert_check}.py, shared
  docs INSTALL/OPERATIONS, COMPACT.md, R-F .orig-124 files). Smoke boot
  PASS: U1 spray leaves ingest working, U4 NaN conf 400, U6 detective
  add 202 + supervisor queue lists it. U9 born-empty marker fixed after
  first smoke caught it never setting (config chain entries precede
  the boot block — signal is now DB-existed-at-import + never-served).
- 2026-11-25 ~14:30 CST: U battery WRITTEN (tests/run_u126_cases.py,
  21 cases) and green case-by-case vs janus125 (each case run
  individually during debugging; the one-shot cold run is still
  owed). Debugging found and fixed three REAL janus126 defects:
  (1) _consume_provision_marker chained ACCOUNT_UNLOCKED but never
  popped the in-memory lock (marker deletion then stranded the
  account); (2) restore.py used sqlite3 without importing it —
  the outgoing-provisioned read died silently in its except;
  (3) restore.py's outgoing read needed a normal connection (hot
  WAL). Builders' suite: P10 registry now lists the two new
  columns; A18 detached-verify failure from run 2 still to
  re-check. Living-suite adaptations so far (disclosed for TRACK
  §4): run_tests.py hotlist actors + VIC309 check + version
  strings; run_r123_cases.py version strings + R9 status;
  run_t125_cases.py t7_hotlist_oracle rewritten for U6,
  t7_redelivery status, setup adds via SUP.
- 2026-11-25 evening CST: leg-by-leg verification on near-final
  code (logs in scratch/logs/): builders run 5 = 333/335 (only
  the demo-seed DET adds failed; seed_demo.py since adapted to
  place via sgt.reyes — re-run owed in the cold battery); Q 29/29
  + Q-with-invariants 35/35 (q-2.log, q-inv-1.log); R 15/20 ->
  all 5 failures were un-converted DET setup adds, converted to
  SUP with a disclosure comment, the 5 re-run PASS (full R re-run
  owed in the cold battery); S 23/25 -> S11 pickup adapted to
  present the U7 token, S10's null samples were load flakiness,
  both re-run PASS; T 16/20 -> T1 group re-run 5/5 PASS (full-run
  store_state "ok" was a flake), T3/T7/T9 fixed via the T
  battery's hotlist() helper defaulting to SUP (t7's detective
  legs pass user=DET explicitly) PLUS one product reorder in
  _post_hotlist: list-registry -> supervisor suppression refusal
  -> category/expiry -> role split (the U6 amendment names the
  registry check; category presence is plate-independent).
  Round 4: attack1/2/3/4 setup adds -> SUP (originals kept as
  .orig-124 with reason headers); 40 verdicts, only attack4's
  A18 verify times out. Round 5: r5_evidence_deadend/parity/
  supersede/gates/hotlist_expiry setup adds -> SUP (originals
  kept); 20 verdicts, only r5_a18_anon_scan fails (same A18
  timeout). Round 6: f2d/f10/f4 setup adds -> SUP (originals
  kept; f2_migration and f9 adds hit 1.0/1.1 FIXTURE boots and
  were deliberately left DET); F2d/F4/F10 re-run PASS.
  A18 FINDING (both trees, not a 126 regression): pure
  verify_chain_rows over the fabricated 600k-entry chain takes
  18.3 s in-process on this VM (scratch/verifydbg2.py), against
  the seat files' 20 s client timeout; janus125's own attack4
  times out identically standalone today. The cold battery gets
  one more attempt on an idle, sequential machine; if it still
  times out, TRACK-126-REPORT reports the two A18 seat files as
  environment-bound with this evidence — never as passes.
  NEXT: load envelope result, then the FULL COLD ./run-next.sh,
  then TRACK-126-REPORT.md, then final md5 re-verification.

## Next step (exact)
1. Read the load-envelope result (scratch/logs/load-1.log).
2. Full cold ./run-next.sh (TMPDIR already wired inside it);
   if reaped, finish remaining legs with the runner's exact
   commands on unchanged code and say so.
3. Write TRACK-126-REPORT.md (U1-U14 dispositions, U9 judgment
   call FIRST, the three battery-found defects, the A18
   environment finding, section 4 living-suite updates incl.
   all seat-file adaptations + .orig-124 files, U8 supersession
   citation for TRACK-125's T4 absence-proof).
4. Re-verify janus125 md5s; final handoff update.

## Settled decisions (do not re-ask)
- Fix shapes per SYNTHESIS §6 + §4 rulings; judgment calls implemented
  best-reading and FLAGGED in TRACK-126-REPORT, never silent divergence.
- TMPDIR=janus126/scratch/tmp for all test runs (512 MB /tmp fills).
- `pkill -f 'janus[.]py'` standalone only, never compounded.
- Test execution authorized (Corey, Nov 24). No git pushes.
- Environment note: background process trees may be reaped at ~26–30 min;
  the 1.2.5 battery took ~50–57 min. If the full run is reaped, run legs
  with the runner's exact commands on unchanged code and say so plainly.

## Blockers
None yet.

## Model / effort
Muse (builder subagent of Vesper). Handoff updated at milestones.
