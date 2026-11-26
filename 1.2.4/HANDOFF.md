# HANDOFF — NOCTUA 1.2.4 build (builder seat)

<!-- VESPER · the evening watch -->

## Goal
Build NOCTUA 1.2.4 in this tree (`janus124/`), implementing council
Round 7 synthesis items S1–S12 (`~/workspace/noctua-1.0/council7/
SYNTHESIS.md`, findings register A–F; S11 per `2FA-SCOPE.md`).
Base: a byte-verified copy of `janus123/` (md5 janus.py
bcdaf653a4fb7ed837e43020df5011a4, sentinel.py
deb8a774fbe1df70fa6e7e28bfd8b0fb — checked at copy time).
Earlier trees are NEVER modified. Nothing is published (no git).

## Done-definition
- Every S item implemented, each with a discriminating case in the
  new S battery (`tests/run_s124_cases.py`) that FAILS on janus123
  and PASSES here (or a written absence-proof in the report).
- Full battery green via `./run-next.sh` (builders' suite, round-4/
  5/6 wrappers, Q battery + invariants, R battery, load envelope,
  S battery), logs under `scratch/`.
- `TRACK-124-REPORT.md`: per-item S1–S12 dispositions, judgment
  calls flagged, test counts + log paths, S12 measurements.
- This handoff updated at every S-item boundary.

## Current state (updated as work lands)
- [x] Tree copied from janus123, checksums verified.
- [x] Commission + all seat reviews + 2FA-SCOPE read in full.
- [x] Code survey: sentinel Chain/sink, janus config/migrations/
  key-check/suppression/rotation/compact/evidence/health/boot.
- [x] S1 durable sink delivery (sentinel.py) — sink_pending
  ledger in the insert transaction; `_deliver_pending()` the one
  delivery path; unit smoke PASS (commit/rollback/flush shapes).
- [x] S2 semantics-preserving boot repair (janus.py) — canon
  preserves `''`; recovery writes plate+state+plate_ref together.
- [x] S3 one suppression predicate — `noctua_plate_ref` SQL
  function, ref-based SQL legs, `_order_covers`, on-sight
  recovery in `_hits_for_read`.
- [x] S4 demo/install boundary — guard inside `_apply_config`
  (boot + every reload), strict demo-flag parse, DEMO_MODE in
  SYSTEM + /health.
- [x] S5 rotation ceremony — bulk commits signature-gated per
  entry; ceremony_id on contributions; freeze widened to all
  shapes; tombstone on cancel/void + replay refusals (commit,
  bulk, reveal); designated witness via `_designated_witness`
  (n≥4 rotation, n=2 labeled self-attestation); witness status
  splits positive/adverse; COMPACT.md witness section updated.
- [x] S6 migration completeness — legacy list-source from actual
  columns, defect records carry the message, per-row
  `_supp_rebuild` isolation; janus10 fixture built from the real
  1.0 tree; F-E absence-proof written in TRACK-124-REPORT.md.
  Build-phase find: provision.py's pin ceremony crashed on the
  1.0 suppressions schema — fixed (enumerate actual columns).
  Build-phase regression, caught by builders' P4 and fixed: the
  first per-row rebuild had a wrong VALUES placeholder count.
- [x] S7 evidence lifecycle — janus destroy reordered
  record-first; retention remediates destroyed-on-paper bundles
  (EVIDENCE_REMEDIATE) and defers this-run file deletions until
  after the run's commit.
- [x] S8 restore honesty + fresh-init guard — restore.py
  pre-validates + stages extraction, installs copy-to-temp +
  os.replace + fsync, narrowed docstring claim, FAILED (never
  REFUSING) post-swap; janus fresh-init guard refuses a fresh
  chain over .pre-restore-* copies without a restore marker,
  checked before ANY key source (env included — the first
  build's mint-only placement was a hole the S8 case caught).
- [x] S9 boundary hygiene — `_strict_id` int64 clamp on both raw
  routes; boot refusal prints only working remedies; provision
  pin overwrites a wrong key file loudly; `_anchor_accept`
  refuses non-checkpoint_disagreement reasons outright;
  frigate doc/code agree ("new" forwards — doc fixed);
  alert_check names the actual closure; compact.recompute fails
  inverted ranges.
- [x] S10 chain contract — participation captured at insert;
  scrub flag on the bookkeeping connection; verify staleness
  bound NOCTUA_VERIFY_MAX_STALE_S (default 300) enforced in
  `_verify_verdict`; serialization contract documented on Chain.
- [x] S11 2FA (TOTP) — janus: store beside DB (0600), RFC 6238
  ±1 step, counter-replay-proof, pending-until-first-code,
  recovery codes (hashed, single-use, RECOVERY_USED chained,
  /health flag until supervisor ack), two-key re-enroll endpoint,
  restore forces must_reenroll, DEMO_MODE-only waiver, machine
  roles key-only. provision.py enroll-2fa. backup.py exclusion
  documented (explicit allowlist — store not in sets).
  Build-phase finds, fixed: the restore-marker call ran before
  the TOTP helpers were defined (flip silently skipped); the
  do_GET verify pre-warm's double auth() read a TOTP acceptance
  as a replay — auth() now memoizes per request handler.
- [x] S12 measurement honesty — hits(read_id) index; per-process
  load comparison with landed-count verification (envelope:
  16.9/s idle, 3.9 @3, 2.6 @6 burners, 500/500 everywhere; unit
  Chain load 19.2/s vs 38.8 on 1.2.3 — the ledger's honest
  price); boot scan 506 ms vs 504 ms on 3,000 entries.
- [x] **FULL BATTERY GREEN** — `./run-next.sh` SUCCESS (exit 0),
  log `scratch/battery-20261125-071116.log`: builders 332/332,
  round-4 PASS (41 verdicts, only A9b confirmed = contrast
  control), round-5 PASS (21, 0 reproduced), round-6 PASS,
  Q + invariants PASS, R battery 20/20, load envelope PASS,
  S battery 25/25.
- [x] TRACK-124-REPORT.md written (per-item dispositions,
  judgment calls, F-E absence-proof, S12 measurements, log
  paths).

## Exact next step
NONE for the builder. The tree is complete and unpublished, per
the commission. The orchestrator's steps (from the parent
context): reconcile TRACK-124-REPORT.md against her own cold
re-runs, then Round 8 dispatch.

## Remaining steps
None in this build. Known follow-ups that belong to the
orchestrator, not this tree: Round 8 council; the Merlin audit
of 1.2.3 (scheduled Nov 25 ~9:45 AM CT) folds into that round;
publication remains the orchestrator's step.

## Blockers
None at start. Known tension (flagged in the report): builders'
suite `suite_demo` boots the demo seed on a production-mode server
and expects imperator to work — S4 deliberately changes that
semantic; the suite's demo instance gets `NOCTUA_DEMO_MODE=1` in
its env (the demo's supported configuration under S4), assertions
unchanged.

## Settled decisions (do not re-ask)
- (a) witness rule accepted WITH S5 amendments; (b) R12 fence as
  built — do not revert; (c) restore claim narrowed per S8;
  ChatGPT's full fail-injection gate is a recorded dissent, NOT
  commissioned (fresh-init guard + its case are).
- S11 in scope; demo waiver rides on S4's server-side install mode.
- Documents package FROZEN; interface builds after convergence.
- Environment: TMPDIR -> workspace scratch; kill stray servers
  ONLY with a standalone `pkill -f 'janus[.]py'`; kill pattern
  never compounded with anything mentioning janus.py.
- Python stdlib only; Ed25519 via system openssl.
- Vesper signature in header comments of created/substantially
  edited code files; never in data/hashes/chain entries.

## Model / effort / limits
Builder seat: Muse (this session), high effort. Limit status:
fresh at build start; update this file at ~70% use.
