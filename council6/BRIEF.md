# NOCTUA Council — Round 6 Brief: Review of NOCTUA 1.2.2

You are one seat on an independent review council for NOCTUA, a
city-owned, open-source ALPR (license-plate reader) system: Janus
(the single gated API in front of all plate data) and the Sentinel
(hash-chained, externally witnessed audit log). Arkansas law:
Ark. Code §§ 12-12-1801 to -1808 (150-day retention cap for
governmental ALPR data). The system is pre-deployment; nothing is
live. Five council rounds have each returned NOT CONVERGED, and
each produced a fix release. You are reviewing **1.2.2**, built to
answer Round 5's 28-item commission (Q1–Q28).

## Convergence criteria — rule on each, explicitly

1. No seat raises a deployment-blocking or code-critical finding
   against 1.2.2 that survives verification (a reproduction, or a
   code citation the orchestrator can confirm).
2. Every forced change from prior rounds is implemented, or
   answered in writing with a reason.
3. What remains is documented CANT-DO limitations or legal /
   institutional questions routed to the City Attorney or ACIC —
   not code defects.
4. The orchestrator's own re-tests pass on the final build.
   (Status entering this round: builders' suite 322/322, round-4
   attacks PASS with only the A9b contrast control CONFIRMED,
   round-5 attacks PASS with 0 reproduced, Q battery + 6 invariant
   suites 35/35 — all independently re-run by the orchestrator;
   the same battery scores 7/35 against 1.2.1. Details and honest
   caveats: TRACK-122-REPORT.md, attached in docs-combined.txt.)

## What you receive (attachments)

- `janus.py`, `sentinel.py` — the 1.2.2 core (also the whole tree:
  github.com/HiramMcknoxt/noctua, folder `1.2.2/`, commit a707a10;
  attachments are byte-identical to it).
- `scripts-combined.txt` — all operator scripts (retention,
  checkpoint, witness, backup, restore, compact, rotation,
  sentinel_audit, frigate_bridge, provision, hotlist_sync).
- `docs-combined.txt` — TRACK-122-REPORT.md (what was built, the
  verified numbers, the known test-quality flags), the Round 5
  synthesis (the Q1–Q28 commission you are verifying), COMPACT.md.
- `tests-combined.txt` — the builders' suite and the Q battery
  (29 cases + 6 invariant suites).

## Named probes — the orchestrator flags these as under-tested

1. **Q16 is vacuous as constructed.** Its burst spooled 0 entries
   on both trees, so the flush_deferred phantom-entry check ran
   over an empty spool. Attack it properly: sink DOWN during a
   concurrent burst with forced rollbacks — can a sink entry exist
   for a transaction that never committed?
2. **Q18's case is weak-shaped.** The discriminating evidence is
   the re-aimed A18 (600k-entry chain, anonymous concurrent
   callers). Find pre-auth or cache shapes A18 does not cover.
3. **Seven Q cases pass on 1.2.1 too** (Q02, Q03, Q06, Q16, Q17,
   Q18, Q22). Do not trust them; verify the properties yourself.
4. **The rotation commit-reveal ceremony is new code.** Attack
   grinding, nonce reuse, withheld reveals, and courier
   substitution. (Verification already caught one dead path here:
   `rotation.py --verify` crashed on every nonce-derived schedule
   until fixed during the battery — ask what else the builders'
   suite never exercises.)
5. **The migration repair (Q1)** now re-keys suppressions on real
   1.1- and 1.2-shaped databases. Try to build a legacy shape it
   mishandles.

## Judgment calls — rule on each

(a) Do the seven both-tree-pass cases count as "verified" for
    acceptance, or does convergence require a discriminating test
    for every case?
(b) Q25's restore test covers atomicity only; the lost-key
    trust-root substance rests on round-4 scenario A7. Sufficient?
(c) Builders' judgment calls (TRACK-122-REPORT.md lists them):
    strip-not-raise on envelope collisions; structural DDL on
    KEY_LOCKED boots; supervisor-transported rotation reveals;
    unconfirmed disposition notes dying at disp_ts + HOLD_DAYS +
    30; /health's camera scope. Accept or reject each.

## Rules of the seat

- State the exact model and effort level you are running, as shown
  in your UI, at the top of your review.
- Execute the code if your environment allows; a finding needs a
  reproduction or a precise file:line citation. Assertions the
  orchestrator cannot confirm do not count.
- Classify every finding: DEPLOYMENT-BLOCKING, CODE-CRITICAL, or
  MINOR. End with: a verdict on each convergence criterion, an
  overall CONVERGED / NOT CONVERGED, and — if NOT CONVERGED —
  the single forced change you would make the price of your vote.
