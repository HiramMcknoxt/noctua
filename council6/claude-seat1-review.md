# Round 6 — Claude seat 1 review of NOCTUA 1.2.2 (archive, substance-preserving)

Seat: Claude **Opus 5.5, Effort Max** (UI-confirmed). Executed: cloned the
repo at a707a10, re-ran all baselines (322/322; 35/35; round-4 PASS A9b
only; round-5 PASS 0 reproduced — all matching the orchestrator).
Chat: https://claude.ai/chat/c2a98c23-4131-4ffe-9f71-eb4ec6fe9692
Review artifact: https://claude.ai/artifact/U7d1Y1sen9MQL3b9GFnKYM
(PDF saved by the browser task under .hatch-browser/outputs for task
94c779c5.) The seat used its ONE permitted usage reset (~12:52 PM), hit
the limit again ~1:52 PM (resets 5:40 PM); the chat message never
delivered the review — it survives in the artifact. **Its attack harness
tar.gz was NOT delivered** (chat shows no attachment); reproductions are
as described in the artifact text. Some env-var names in the artifact
transcription (Q16_SINK_URL / NOCTUA_SINK_URL) do not match the code
(NOCTUA_SENTINEL_SINK) or the test (NOCTUA_AUDIT_SINK_DIR) — treat those
two names as transcription artifacts; the behavioral claims are what
count and are arbitrated by seat 2's harness + the orchestrator's run.

## Verdict: NOT CONVERGED — criteria 1 FAIL, 2 FAIL, 3 FAIL, 4 PASS on its own terms

- **B1 [DEPLOYMENT-BLOCKING] = the forced change.** Releasing one
  protection order silently strips protection still owed by another
  order on the same plate (cites a single `protected` boolean,
  janus.py:4936, cleared by release_protection at :5008; two overlapping
  orders, release the first, a hit returns UNSUPPRESSED while the second
  order is in force). Remedy: per-order protection records; release
  deletes only that order's row; suppression = "any live order covers
  this plate." **Independently the same finding as Claude seat 2's
  C3/F2d, which that seat reproduced natively.**
- C1 [CODE-CRITICAL]: flush_deferred ships phantom sink entries for
  rolled-back transactions when the sink is correctly configured (sink
  DOWN, burst, forced rollbacks). **CONFLICTS with seat 2's F5**, which
  with fault injection found 0 phantoms and instead found the pre-auth
  path DROPPING committed sink entries. Orchestrator's harness run
  arbitrates.
- C2 [CODE-CRITICAL]: rotation — courier can substitute a reveal and a
  nonce can be reused (commit not bound to the schedule in the verify
  path; same nonce committed twice, both reveals verify). Converges
  with Vesper F1 / Gemini F2 / seat 2 F6 in substance.
- C4 [CODE-CRITICAL]: pre-auth cache keyed by (caller, scope) is not
  invalidated on role revocation — a revoked caller keeps a cached ALLOW
  until TTL. (Seat 2's F4 covers a sibling pre-auth defect: lost writes
  via out-of-lock config reload + chaining.)
- C5 [CODE-CRITICAL]: migration re-keys suppressions without normalizing
  the stored plate the way query-time does; NULL plate_hash rows re-keyed
  to a hash of empty/NULL — a 1.1-suppressed plate becomes searchable.
  Converges with Gemini F4 / seat 2 F2 in substance.
- C6 [CODE-CRITICAL]: Q25 covers atomicity only; A7 exercises the
  1.2.1-era restore, not 1.2.2's — the lost-key trust root on the current
  path is untested. Converges with the round's (b) rulings.
- C7 [CODE-CRITICAL]: /health returns per-camera status to callers not
  authorized for those cameras. [Orchestrator note: 1.2.2 has roles, not
  per-camera ACLs; classified as a design-scope claim in the synthesis
  unless the code shows a scope concept.]

Minors M1-M7: Q16 env-var vacuity (converges); Q18 weak shape; both-tree
cases are not discriminating evidence; a second unexercised rotation path;
test-quality flags in TRACK-122-REPORT are honest.
Judgment: (a) both-tree-pass does NOT count as verified — discriminating
test or independent reproduction required. (b) Q25+A7 NOT sufficient.
(c) strip-not-raise REJECT; DDL on locked boots ACCEPT (no plate data);
courier REJECT; disp-note clock ACCEPT as documented; /health scope
REJECT (C7).
