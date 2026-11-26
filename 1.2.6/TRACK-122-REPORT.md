# NOCTUA 1.2.2 — Build & Verification Report

Built from janus121 per the Round 5 synthesis commission
(~/workspace/noctua-1.0/council5/SYNTHESIS.md, items Q1–Q28).
Implementation by a delegated builder (edits completed Nov 24,
~11:05 CST; that session's verification was stopped by a security
check before any test ran). Verification completed by a second
builder/finisher and independently re-run by the orchestrator
(Vesper) after the user's explicit authorization to execute the
codebase (Nov 24, 2026, 11:09 CST: "Yes — run the NOCTUA test
suites"). janus/, janus11/, janus12/, janus121/ were never modified.

## Acceptance legs — final numbers

| Leg | Finisher | Orchestrator re-run |
|---|---|---|
| Builders' suite (repo-shaped layout) | 322/322, exit 0 | **322/322, exit 0** |
| Round-4 attack suite (in-tree wrapper) | PASS — 41 verdicts, only A9b CONFIRMED (contrast control), no harness failures | **PASS — identical** |
| Round-5 seat-1 attack suite (in-tree wrapper, incl. re-aimed A18 at 600k entries / 12 anonymous concurrent callers) | PASS — 21 verdicts, 0 REPRODUCED, no harness failures | **PASS — identical** |
| Q battery (29 cases) vs janus122 | 29/29 PASS | (combined run below) |
| Q battery + 6 invariant suites vs janus122 | 35/35 PASS, exit 0 | **35/35 PASS, exit 0** |
| Same battery vs janus121 (fail-before) | 7/35 PASS, exit 1 | not re-run (see below) |

Demo seed checks are inside the builders' 322 and pass.
One builders' run under load (load average ~6.6 from back-to-back
legs) scored 320/322: both misses were the S18 two-writer stress
checks hitting `database is locked` at BEGIN IMMEDIATE (529/1,000
appends landed). Three quiet-machine runs (two finisher, one
orchestrator) are 322/322. The stress check is load-sensitive; the
report records both outcomes rather than selecting one.

## Q1–Q28 disposition

All 28 items are implemented. Each maps to a same-named case in
tests/run_q122_cases.py (Q01…Q27 cover Q1–Q27; Q28 is the packaging
item, evidenced by the in-tree fixtures, wrappers, and this battery
running from the repo-shaped layout). Case outcomes vs janus121 →
janus122:

- FAIL→PASS (behavioral delta proven): Q01, Q04, Q05, Q07, Q08,
  Q09, Q10, Q11, Q12, Q13, Q14, Q15, Q19, Q20, Q21, Q24, Q25, Q26,
  Q27 — 19 cases. Examples: Q15 reproduces the AUTH_FAIL bucket 500
  on 121 ([401,401,401,500,200]); Q26 reproduces the config-shape
  500 loop; Q25 shows 121's backup.py signing a broken-chain set
  (rc 0) where 122 refuses (rc 1); INV2 (ingest ordering) on 121:
  best-read alert survives 1/8 events, returned ids resolve 0/8 —
  on 122, 8/8 and 8/8.
- FAIL→PASS via harness absence: Q23, INV5 — 121 has no
  commit-reveal rotation at all; the cases fail there with
  AttributeError (no `rotation_ceremony` helper). Recorded as
  absence-of-mechanism evidence, not a behavior probe.
- PASS on both trees (property already held in 1.2.1; the case
  verifies it on 122 but evidences no delta): Q02, Q03, Q06, Q16,
  Q17, Q18, Q22 — 7 cases. Per-case reasons are in
  scratch/finisher-results.md.
- All six invariant suites FAIL or error on 121 and PASS on 122.

## Defects found BY verification and fixed in janus122 (6)

1. janus.py `_apply_config` required a `"key"` field no producer
   writes (all write `key_sha256`) → valid users.json rejected as
   stale, all auth failed. (First verification session.)
2. `sentinel.rotation_signed_portion` referenced by janus.py and
   rotation.py but never defined → rotation publish 500.
3. scripts/retention.py called `ts_cutoff`/`day_cutoff` without the
   required `now_dt` → every retention run crashed.
4. Duplicate checkpoint receipt → 500 (UNIQUE constraint); handler
   now idempotent.
5. Q18's reorder initially computed the cached verify INSIDE DBLOCK,
   re-creating the A18 stall (4.09s on a 250k chain); recomposed:
   side-effect-free auth check first, cache warmed outside the
   lock, real auth inside.
6. scripts/rotation.py `seed_from_nonces` called `.decode()` on
   bytes → `rotation.py --verify` crashed on EVERY nonce-derived
   1.2.2 schedule; the Q23 offline verification path was dead and
   the builders' suite never exercised it (legacy seed path only).
   Fixed; --verify now exits 0 with a byte-for-byte recompute.

## Known test-quality flags (not papered over)

- **Q16 is vacuous as constructed**: its 40-request burst spooled 0
  entries on BOTH trees (the sink stayed healthy), so the
  phantom-entry check ran over an empty spool. The flush_deferred
  invariant still lacks a discriminating test; a sink-down burst
  variant is owed. Round 6 seats are told this explicitly.
- **Q18's case is weak-shaped** (single anonymous request, small
  chain; passes on both trees). The discriminating evidence for
  Q18 is the re-aimed A18 (600k entries, anonymous concurrent),
  which is NOT REPRODUCED on 122; the 121-side harm was established
  in Round 5 by Claude seat 2's reproduction (R5-02).
- **INV4 excludes sentinel_audit's "heartbeat freshness" check by
  name** — it grades cron jobs that never run inside a test
  instance.
- The fail-before (janus121) battery was executed once, by the
  finisher; the orchestrator's re-runs covered the janus122 side
  of every leg.

## Judgment calls (flagged by the builders, standing unless Round 6 objects)

Q20 strips envelope-colliding caller fields rather than raising;
emergency Tier 3 is held to the configured instrument set;
structural DDL runs on KEY_LOCKED boots while data migrations
defer; rotation contributions/reveals may be supervisor-transported
(the commitment hash, not the courier, binds); unconfirmed
disposition notes die at disp_ts + HOLD_DAYS + 30; /health folds in
overdue holds and silent-after-reporting cameras but not
never-reported cameras; Q25's test covers the atomicity half only —
the lost-key trust-root substance is covered by round-4 scenario A7
(NOT REPRODUCED on 122 in both runs).

## Orchestrator's verdict

1.2.2 meets the Round 5 acceptance standard as written: the six
invariant suites pass on 122 and fail on 121, and the builders' +
both attack suites are green under independent re-runs from the
repo layout — subject to the Q16/Q18 test-quality flags above,
which are carried into the Round 6 brief as named probes.
Convergence is the council's decision in Round 6, not this
report's. Logs: janus122/scratch/ (builders-vesper.log,
round4-vesper.log, round5-vesper.log, qcases-vesper2.log,
finisher-results.md and the finisher's logs cited there).
