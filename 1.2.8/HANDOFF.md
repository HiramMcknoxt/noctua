# HANDOFF — NOCTUA 1.2.8 builder seat

Seat: builder subagent (Vesper's council builder seat)
Model + effort: Muse (this session); effort n/a
Updated: 2026-11-26 ~16:20 CST — STATUS: DONE (builder side; chair
cold verification is separate and has not happened here)
Limit status: ok / unknown
Handoff runner: run-next.sh (this folder)

> HANDOFF RULE (standing, Corey Nov 24 2026): Before starting, create HANDOFF.md in the work folder using the council template: goal, done-definition, current state with evidence, exact next step, remaining steps, blockers, settled decisions, model/effort, limit status/reset. If the next step is a machine step (compile, test, render, push, deploy), also create an executable runner (run-next.bat/.ps1 pure ASCII, or run-next.sh) that does it end-to-end and logs its result. Update the handoff at every milestone and at ~70% limit use. Do not end without a current handoff another model can execute cold.

## Goal (one sentence)
Implement the five commissioned items of council10/SYNTHESIS.md §6 in the
new tree `janus128/` (copied from janus127/), each with a discriminating
W-battery case (fails on janus127, passes on janus128), the full prior
battery green via one cold `./run-next.sh`, and TRACK-128-REPORT.md.
janus127/ stays byte-untouched. No git operations, no pushes.

## Done looks like (acceptance test) — ALL MET
- [x] Items 1–5 implemented in janus128/janus.py only (plus version
      literals per tree convention)
- [x] tests/run_w128_cases.py discriminates: 6/6 cases FAIL on
      janus127, PASS on janus128 (scratch/w-battery-dev1.log)
- [x] Full battery green on janus128 via one cold ./run-next.sh —
      BATTERY RESULT: SUCCESS, all 12 legs PASS
      (scratch/battery-20261126-205707.log; run history incl. the
      reaped run #1 disclosed in TRACK-128-REPORT.md §7)
- [x] TRACK-128-REPORT.md written: per-item changes, discriminating
      results, full battery result, V5b answer (§8), five numbered
      judgment calls (§10)
- [x] janus127 baseline md5s re-verified unchanged (md5sum -c OK;
      zero non-__pycache__ files modified after the copy)

## Current state
- Done: tree copied from janus127 (rsync, scratch/ + __pycache__
  excluded) 2026-11-26; baseline md5s recorded. Source documents read:
  council10/SYNTHESIS.md (§6 commission, §3.1/§3.2/§3.3 rulings),
  chair-execution-r10c01-c02.md, claude-b-review.md (r01),
  claude-review.md, gemini-review.md §3.2. All five code sites read in
  janus.py: _anchor_apply (~2209), _post_suppression (~5562),
  _post_holds (~5420), CEREMONY_FENCED_POST (~3384), _post_hotlist
  non-supervisor upsert (~5265). Harness patterns read (T Boot,
  V battery v4/v5 cases).
- Done: all five items implemented in janus128/janus.py; version
  literals bumped (janus.py VERSION/docstring, sentinel.py
  REGISTRY_VERSION/docstring, sentinel_audit.py, backup.py
  manifest, COMPACT.md, run-next.sh header); test literals adapted
  with .orig-127 preserved (tests/run_tests.py.orig-127,
  tests/run_v127_cases.py.orig-127). All edited files ast-parse.
- Done: W battery written (tests/run_w128_cases.py, 6 cases) and
  DISCRIMINATES on first run: 6/6 pass (scratch/w-battery-dev1.log).
  Baseline legs reproduce C01/C02 exactly (record never promotes,
  auto-clear after repair; 201/404 hold split; releases served
  200/200; G1 resubmission dropped, chain effect null).
- Done: full battery run #2 (detached launch after run #1 was
  SIGTERM-reaped mid-load-envelope, the 1.2.7 build's failure
  mode): BATTERY RESULT: SUCCESS — builders 335/335, round4 41
  verdicts (A9b contrast only), round5 21 none reproduced, round6
  PASS, Q 35/35, R 20/20, load COMPLETE 500/500 both directions,
  S 25/25, T 20/20, U 21/21, V 19/19, W 6/6. One measurement
  variance disclosed in the report §7 (health availability
  wrong_values 20/20 under saturation; a measurement, not a gate).
- Done: TRACK-128-REPORT.md complete. NEXT: the chair's cold
  verification (not the builder's to run or declare).

## Design decisions (formed during exploration — do NOT re-derive)
1. Item 1 (V5 promotion): in _anchor_apply's mismatch branch, after
   the recorded-is-None set path, add a promotion branch: recorded
   reason in ANCHOR_FILE_STATE_REASONS + fresh detail reason ==
   checkpoint_disagreement => chain-append the promotion FIRST, then
   _meta_set the disagreement record (bad_ids ride the detail). New
   chain kind ANCHOR_REASON_PROMOTED {prior_reason, prior_detected,
   reason, bad_ids, checkpoint_entries, chain_entries}; the record
   also carries promoted_from. Append failure aborts (record stands).
2. Item 2: _post_suppression omits warning_near_matches from the
   response when _ceremony_state(); placement + SUPPRESSION_PLACE
   chain unchanged; non-ceremony response byte-identical.
3. Item 3: _post_holds scope=hit in ceremony state returns ONE
   uniform 201 {"result": "hold placed", "review_by": ...} (no
   hold_id) whether the hit exists, is missing, or its case
   mismatches; the hold is placed + chained only when it exists and
   its case matches. Non-ceremony path byte-identical (404/400 in
   the original order).
4. Item 4: "/holds/release" and "/suppressions/release" join
   CEREMONY_FENCED_POST; the comment above the set is corrected
   (placements stay open; releases are fenced).
5. Item 5: _post_hotlist non-supervisor upsert WHERE becomes
   (pending=1 OR active=0) and the DO UPDATE also sets active=1,
   pending=1; a pre-read of the conflicting row classifies the
   outcome and HOTLIST_ADD_PENDING gains an "effect" field
   (new / pending_updated / reactivated / live_row_no_change).
6. Version bump (tree convention, "the literal follows the shipping
   build"): janus.py VERSION + docstring, sentinel.py
   REGISTRY_VERSION + docstring, scripts/sentinel_audit.py version,
   scripts/backup.py manifest, COMPACT.md lines, run-next.sh header.
   Test literals that assert the version (tests/run_tests.py
   registry_version/REGISTRY_VERSION, tests/run_v127_cases.py v15f
   sentinel_audit line) are adapted 1.2.7 -> 1.2.8 with the
   pre-adaptation files preserved as .orig-127 under R-F (the
   1.2.7 builder's exact precedent: run_tests.py.orig-126).

## NEXT STEP — do this first, exactly
1. Apply the five janus.py edits + version literals (designs above).
2. Adapt the two test files' version literals; preserve .orig-127.
3. Write tests/run_w128_cases.py (cases w1, w1b, w2, w3, w4, w5 in
   the V-battery pattern: test tree + baseline tree, pass only when
   the invariant holds on 128 and fails on 127).
4. Run the W battery standalone; iterate until it discriminates.
5. Cold-run ./run-next.sh (full); fix fallout without weakening
   assertions; re-run cold until green or honestly report variance.
6. Write TRACK-128-REPORT.md (incl. the V5b answer: item 1 does NOT
   touch the SET path; report the set-path behavior as-is).
7. Re-verify janus127 md5s; update this handoff to DONE.

## Blockers / open questions
None at start. V5b (SYNTHESIS §5 item 11) is report-only by commission.

## Decisions already made — do NOT re-ask
- Scope is the five items ONLY (SYNTHESIS §6). G3 is NOT in this
  build despite sitting at register #3 — the commission's five items
  are V5 promotion, the three ceremony items, and G1.
- The chair rules, the builder reports; do NOT declare convergence.

## Files that matter
- ~/workspace/noctua-1.0/council10/SYNTHESIS.md — the commission (§6)
- ~/workspace/noctua-1.0/council10/chair-execution-r10c01-c02.md —
  C01/C02 executed evidence (discriminating sequences)
- janus128/janus.py — the only production file this build changes
- janus128/tests/run_w128_cases.py — the new W battery
- janus128/TRACK-128-REPORT.md — the build report (final deliverable)

## If you are picking this up cold
TMPDIR must point at the tree's scratch/tmp (run-next.sh does this;
the 512 MB /tmp fills). Kill a test server only with a standalone
`pkill -f 'janus[.]py'`. The W battery's default baseline is the
sibling janus127 tree; the V battery's baseline stays janus126.
