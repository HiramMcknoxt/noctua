# NOCTUA Council — Round 7 Synthesis: 1.2.3 Reviewed
Orchestrator: Vesper. Nov 24, 2026 (reviews retrieved 11:14 PM –
11:39 PM CST). Build under review: NOCTUA 1.2.3 (janus123/),
judged against the Round 6 acceptance standard — verified
invariant satisfaction, not passing counts. The orchestrator's
cold battery passed all seven legs (builders' 332/332; round-4,
round-5, round-6 attack legs PASS; Q battery + invariants 35/35;
R battery 20/20; load envelope complete to 6 burners) — and the
round still did not converge, because the seats found failure
shapes the battery does not observe. That is the standard working
as designed.

## Verdict: NOT CONVERGED — unanimous
| Seat | Model (as shown) | Mode | Verdict |
|---|---|---|---|
| ChatGPT | GPT-6.2, Thinking High | executed 1 probe + code-read | NOT CONVERGED (1/4 criteria) |
| Qwen | Qwen4-Max, Thinking ON (model line exposes no version) | code-read only | NOT CONVERGED (crit. 2, 3 FAIL) |
| Gemini | Deeper analysis 4 Neon, Thinking High | code-read only | NOT CONVERGED (crit. 1–3 FAIL) |
| Cold Vesper | Muse (subagent) | executed, full probes | NOT CONVERGED (banked in its HANDOFF) |
| Claude | Opus 5.5, Medium (UI footer) | executed, probes + logs | NOT CONVERGED — see adjudication |
| DeepSeek chat | self-identified as a Claude model | code-read | NOT CONVERGED — CORROBORATION, not the DeepSeek seat's vote (identity disclosed by the seat itself) |

Adjudications:
- Claude seat: its chat prose invents routes/functions that do
  not exist in the build (grep-verified) and its novel prose
  findings are excluded; its preserved work products (HANDOFF,
  probes, logs in council7/claude-seat/) are executed, grounded,
  and converge with the round. The vote counts; the evidence of
  record is the artifacts. Detail: council7/claude-review.md.
- The Qwen third-phantom shape is CLOSED as a dispute: real in
  the Chain class contract, unreachable in Janus's DBLOCK wiring
  (four seats concur; cold seat executed both layers). It becomes
  a hardening item (S10), not a defect verdict.
- The R14 paired throughput comparison (1.9 vs 5.6 appends/s) is
  DISPUTED on methodology (Gemini: the 1.2.2 side's appends may
  have rolled back at connection close, inflating its rate). The
  standalone envelope stands (completeness holds; 16.2/s idle →
  2.2/s at 6 burners). Re-measurement is commissioned (S12).
- Judgment calls: (a) witness rule — ACCEPT with amendments
  (deterministic designation among eligible others at n≥4;
  adverse vs positive attestations distinguishable; n=2
  self-attestation labeled as such). (b) R12 fence — ACCEPT as
  built, unanimous. (c) restore atomicity — NARROW the claim in
  writing + the fresh-init guard (S8); ChatGPT's demand for a
  full fail-injection gate is recorded as dissent.

## What held (verified across seats — do not reopen)
R1 native + plate-text-migrated orders as records; R3 pin
ceremony core (verify-don't-proxy incl. fragment-only quiet
installs, executed by two seats); R4 out-of-lock discipline;
R7 Compact anchoring; R8 one verifier; R9 supersede; R10
restore trust root; R12 fence; R13 attribution; R16 reads
inheritance (confirmed by its own author seat); the
per-contribution rotation path (freeze, no-overwrite, signed
transport, two-key cancel — executed by the cold seat); the
sink's in-process shapes (burst, twin, spool drain).

## Findings register (all verified by the orchestrator in code
or by execution, except where marked)
THEME — the round's lesson, in ChatGPT's words the council
adopts: the remaining weaknesses are lifecycle guarantees —
what happens when operations fail, restart, reload, cancel,
restore, or cannot complete normally.

A. Sink delivery is not durable (ChatGPT's price; R7-01/R7-03,
Gemini F1/F2, Claude p1/p1b executed, cold-seat F2/S3):
   A1 flush_deferred drains its queue up front; a failed
      verification connection silently discards committed
      entries; health stays green (executed by ChatGPT).
   A2 the persisted watermark is one global scalar shared by
      every process; a later entry delivered by another process
      makes an earlier committed entry permanently undeliverable
      (executed end-to-end by the Claude seat: 7/55
      RETENTION_PURGE entries missing, sink "healthy").
   A3 spooled twins duplicate on replay when the sink was down
      (Gemini, code-read); crash between commit and flush loses
      delivery with no restart reconciliation (cold seat,
      executed at Chain level).
B. Boot repair is not semantics-preserving (DeepSeek-chat's
   price; two one-line defects in _migrate_123):
   B1 _hotlist_canon rewrites the unknown-state wildcard ''
      to NULL; the match predicate never matches NULL — a
      state-less hot-list entry stops alerting after the first
      restart. A 1.2.3 REGRESSION (verified: janus.py:1132,
      predicate :2844).
   B2 _supp_repair's recovery branch restores plate text but
      not plate_ref (verified: janus.py ~1212) — the recovered
      order is half-active for the whole first boot: its hits
      vanish from /hits AND /suppressed-hits while /verify and
      /evidence/export treat them as unprotected (four seats).
   B3 plate-less orders kept active with plate NULL leak
      through the SQL suppression legs of run_search() and
      /tier3/results (NULL never equals a plate), while /hits'
      Python leg handles them (Gemini F4 + Qwen F-F).
   B4 direct 1.0 → 1.2.3 upgrade never completes: the deferred
      migration SELECTs list_name from a 1.0 hotlist table that
      has source (cold seat F1, executed); no janus10 fixture
      exists; MIGRATION_DEFECT records carry the exception TYPE
      only, not the message. _supp_rebuild lacks per-row
      isolation (Qwen F-E, fixture-or-absence-proof owed).
C. The demo boundary is a boot-time, name-bound, self-declared
   check (Gemini's price; five seats, executed by cold seat
   and Claude seat): the guard runs once at boot and never on
   the live reload path; it binds the literal name "imperator"
   while any account can carry a multi-role roles list; the
   demo flag is bool() of the users file's own value (the
   string "false" licenses it); nothing records demo mode in
   SYSTEM or /health.
D. Rotation ceremony, second door (Qwen's price; F-A, Gemini
   F5/F6/F7/F8, Claude p6 executed): the bulk /commit path
   takes nonce_hashes with NO authorship check — a supervisor
   can author every partner's commitment; executed consequence
   beyond Qwen's DoS: if partners reveal supervisor-supplied
   nonces, the schedule seed is predetermined by the
   supervisor. Post-reveal, a repeat /commit with empty hashes
   and mutated members/period re-opens grinding (the freeze
   guard requires non-empty hashes, janus.py:5112). Cancel/void
   deletes contributions whose signatures bind no ceremony
   instance, so signed contributions replay into a restarted
   ceremony. Witness designation falls back to the auditor for
   every n≥4 compact (janus.py ~4954).
E. Evidence lifecycle (ChatGPT R7-07, Qwen F-D): a bundle whose
   row says destroyed but which remains (or is restored) on
   disk is flagged forever and remediated by nothing; destroy
   paths rmtree before commit, so a rollback can leave evidence
   deleted but unchained.
F. Boundary hygiene (Qwen F-C, Gemini F9/F11, ChatGPT
   R7-09/R7-10, cold-seat F4): _strict_id has no int64 clamp
   (OverflowError → 500; also raw int() at /tier3/results and
   /audit/range); the boot-refusal message prints two remedies
   that both fail as printed (dead key-file remedy; missing
   --confirm) and never mentions the env var that defeats
   remedy #1; provision.py leaves a wrong pre-existing key
   file in place; _anchor_accept clears unreadable/missing-
   checkpoint mismatches (DeepSeek-chat residual);
   frigate_bridge's "new" event contradicts its docstring;
   chain_ok can report a tampered chain ok indefinitely under
   saturating ingest (Claude p4, verify-freshness shape).

## Convergence criteria
1. FAIL — deployment-blocking/code-critical findings survive
   (A1, A2, B1, B2, C, D).
2. FAIL — R5 and R6 are not satisfied in full; the Qwen
   residuals (overflow, destroyed-on-paper) were carried into
   this round undispositioned; the imperator commission's
   "impossible outside demo" is not achieved at runtime.
3. FAIL — what remains is concrete code defects, not CANT-DO
   items or routed legal questions.
4. PASS — the orchestrator's re-tests pass; the round's lesson
   is that the battery's coverage, not its honesty, is the gap.

## The 1.2.4 commission (S-items)
Acceptance standard: as for 1.2.3 — every item carries a
discriminating case that FAILS on 1.2.3 and PASSES on 1.2.4,
exercised on real multi-step lifecycles, re-run cold by the
orchestrator from the public repo layout. New battery shapes
this round adds: multi-process sink writers, first-boot-only
migration assertions (no second boot), a janus10 fixture,
reload-path config attacks, and post-reveal ceremony attacks.

- S1 Durable sink delivery. The delivery obligation derives
  from the committed chain itself, not a volatile queue:
  outstanding deliveries are computed from the audit table;
  verification failure preserves the obligation, retries, and
  degrades health until reconciliation; per-entry delivery
  state replaces (or gap-checks) the scalar watermark; restart
  reconciles and backfills; spool replay deduplicates.
  Fault-injection battery: verification-connection failure,
  sink-down twin, crash between commit and flush, interleaved
  janus + retention + hotlist_sync writers, restart mid-backlog.
  Invariant: zero uncommitted delivered, zero committed
  missing after recovery, no unexplained duplicates, no green
  health over an unresolved gap. (Answers A1–A3.)
- S2 Semantics-preserving boot repair. _hotlist_canon
  preserves ''; _supp_repair's recovery branch sets plate_ref
  in the same statement as plate; a recovered order counts
  complete only when its ref verifies; the two discriminating
  cases from the DeepSeek-chat seat (state-less entry →
  restart → AR-state read alerts; recovered plate-less order →
  FIRST boot → hit in /suppressed-hits, /verify 403) enter the
  battery. (Answers B1, B2.)
- S3 One suppression predicate. Every disclosure path — /hits,
  run_search (search, share/query, tier3 approve/emergency),
  /tier3/results, /verify, /evidence/export — applies the same
  ref-based suppression decision; the SQL legs become
  ref-aware or post-filtered like /hits; an active order with
  no plate text suppresses on all paths or is quarantined
  visibly, never silently inert. (Answers B3; adopts the
  Claude seat's forced change: matching by key_ref_candidates
  everywhere + re-key on recovery.)
- S4 Demo/install boundary. Installation mode is a server-side
  opt-in (environment, e.g. NOCTUA_DEMO_MODE=1), recorded in
  SYSTEM and surfaced in /health. The guard runs inside
  _apply_config on boot AND every reload — a violating reload
  is refused and the last-good config kept. Multi-role entries
  under ANY name (and "imperator" case-insensitively) are
  refused unless server-side demo mode is on; the demo flag is
  parsed strictly (JSON true only). Cases: boot, hot-reload,
  rename, string-flag, demo-file-on-production-env.
  (Answers C.)
- S5 Rotation ceremony completeness. Authorship on EVERY
  contribution path: the bulk commit is signature-gated per
  entry exactly as _authorized, or the bulk field is deleted.
  Contributions bind a unique ceremony-instance id; after the
  first reveal, /commit is closed for that ceremony in all
  shapes (empty hashes, mutated members/period → 409);
  retired (cancelled/voided) contributions are rejected on
  replay; witness designation at n≥4 selects deterministically
  among eligible others; witness status distinguishes positive
  from adverse attestations; n=2 self-attestation is labeled
  in status output and COMPACT.md. Discriminating cases:
  unsigned bulk commit refused + partner's own commit then
  succeeds; post-reveal mutation refused; cancelled-ceremony
  contribution replay refused. (Answers D + judgment (a).)
- S6 Migration completeness. A janus10 fixture (real 1.0 tree)
  enters the tree and the battery; direct 1.0 → current
  upgrade completes with a populated hot list; _supp_rebuild
  gains per-row isolation or a written absence-proof across
  1.0/1.1/1.2.x schemas; MIGRATION_DEFECT and /health carry the
  exception MESSAGE. (Answers B4, Qwen F-E.)
- S7 Evidence lifecycle completion. Retention remediates
  destroyed-on-paper bundles (deletes the on-disk copy whose
  row says destroyed), with a restore-resurrection case;
  destroy ordering can no longer leave evidence deleted but
  unchained. (Answers E.)
- S8 Restore honesty + fresh-init guard. Docs and docstrings
  say "pre-validated; the swap is not I/O-failure-atomic;
  .pre-restore-* copies are preserved for manual recovery."
  Janus refuses to mint a fresh key/chain over a directory
  holding .pre-restore-* copies without a restore marker;
  the swap moves to copy-to-temp + os.replace (+ fsync);
  restore never prints REFUSING after the live set has been
  replaced. A fail-injection case covers the guard (the full
  mid-swap atomicity gate remains ChatGPT's recorded dissent,
  not the commission). (Answers judgment (c).)
- S9 Boundary hygiene. _strict_id clamps to the SQLite int64
  range and rejects negatives per the Q12 contract (400, never
  500); /tier3/results/<id> and /audit/range route through it.
  The boot-refusal message prints only remedies that work,
  including --confirm and the env-precedence sentence.
  provision.py's pin ceremony overwrites or loudly refuses a
  wrong pre-existing key file. _anchor_accept refuses reasons
  other than checkpoint_disagreement. frigate_bridge doc and
  code agree on "new". (Answers F.)
- S10 Chain contract hardening. _append_txn returns the
  participation decision captured at insert; append() uses it
  instead of re-reading in_transaction; the external-
  serialization precondition is documented on Chain; the
  scrub-flag insert cannot leak a transaction on a shared
  connection; chain verification freshness under load is
  bounded and stated (the p4 shape gets a case or a written
  bound). (Answers the closed phantom dispute + F2/F-STALE.)
- S11 2FA, as scoped in 2FA-SCOPE.md (TOTP, stdlib, recovery
  codes, machine identities key-only). Its demo waiver rides
  on S4's server-side install mode, and the round must attack
  the waiver. On the CJIS Path B this is a compliance item.
- S12 Measurement honesty. The load comparison is re-measured
  with per-process verification (entries == landed on both
  trees, separate OS processes); boot-time migration scan cost
  is measured on a large database; hits(read_id) gains its
  index. TRACK reporting states what each number measures.

Sequencing note: S1–S10 are one build (1.2.4) under the
handoff protocol; S11 rides the same build but is attacked as
its own surface. Documents remain FROZEN. Round 8 runs on the
same standard, with Claude seats at Medium (Max reserved for
the final version's round, per Corey's standing instruction).
