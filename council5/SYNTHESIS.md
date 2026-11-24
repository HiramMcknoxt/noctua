# NOCTUA Council — Round 5 Synthesis (review of 1.2.1) and the 1.2.2 Commission

Orchestrator: Vesper. Date: Nov 24, 2026. All seat reviews are in this
directory (council5/). Attack suites: council4/attacks/ (round 4),
council5/attacks-cloud/ (Claude seat 1, round 5). Claude seat 2's
harness did not survive download (its "Download all" artifact was a
duplicate of the review document); its 20 findings are specified in
its review text with reproductions described, and the 1.2.2 builders
owe fail-before tests for each.

## Verdict: NOT CONVERGED

Criterion votes (orchestrator's ruling after verification):
1. **No deployment-blocking / code-critical finding — FAIL.** Multiple
   deployment-blocking defects confirmed by execution (below).
2. **Every round-4 forced change implemented or answered — FAIL.**
   P3/P4 (suppression/migration), P6 (restore trust), P9 (rotation
   seed), P10 (registry parity) are FIXED-BUT-WRONG in ways that
   reproduce at runtime.
3. **Remainder is CANT-DO / legal only — FAIL.** What remains is code.
4. **Independent re-tests pass — FAIL in substance.** Both builders'
   claims re-ran exactly as stated (312/312; attack suite 32 NR /
   A9b / 8 silent) — and both Claude seats' new harnesses, plus my own
   re-run of seat 1's suite, reproduce 20 defect verdicts the builders'
   suites never exercised.

## Seats and their weight

| Seat | Model/effort | Method | Verdict |
|---|---|---|---|
| ChatGPT | GPT-6.2, Thinking High | executed probes | NOT CONVERGED |
| Gemini | Neon High | static traces | NOT CONVERGED |
| Claude (cloud, seat 1) | Opus 5.5, Effort Max | executed; own 10-script suite | NOT CONVERGED |
| Claude (cloud, seat 2) | Opus 5.5, Effort Max | executed; own harness | NOT CONVERGED |
| Vesper (cold) | cold-context Muse | executed; own probes | NOT CONVERGED |
| Qwen | Qwen4-Max, Thinking | executed vs repo copies | NOT CONVERGED |
| DeepSeek (native) | DeepThink | static, 19% read | NOT CONVERGED |
| DeepSeek (native, chunked) | DeepThink | static, partial reads (63/100/99/60%) | NOT CONVERGED |
| DeepSeek (Merlin) | v4 Pro | static, full read, no execution | **CONVERGED** |
| Grok | "Fast" (Grok 4 Fast) | static | NOT CONVERGED — **INVALID, excluded** |

Grok is excluded on evidence, not outvoted: every symbol it cited
does not exist in the code, its deployment-blocking finding is
contradicted by janus.py:227-233, its attachment claims are false,
and it misreported its own model (see grok-review.md). DeepSeek-
Merlin's CONVERGED is recorded and weighed as what it is: the only
seat that executed nothing. Under the council's standing rule —
reproductions outrank assertions — it cannot carry criterion 1
against 20 reproduced verdicts.

## Orchestrator verification (what I confirmed myself)

- **Claude seat 1's attack suite, re-run by me against janus121 +
  janus11: 20 REPRODUCED verdict lines, 0 NOT REPRODUCED, exit 0**
  (log: attacks-cloud-vesper-rerun.log). Every R5-01…R5-17 finding in
  that suite is real on the shipped code.
- Code-read confirmations: retention.py commits the purge (line 302),
  closes (322), then opens a NEW Chain connection (323) to append
  RETENTION_PURGE (328) — DeepSeek-chunked F2 is correct.
  _reload_config catches only (OSError, ValueError) (janus.py:402) —
  DeepSeek-chunked F1's premise is correct. _migrate_121
  early-returns on KEY_LOCKED and normalizes only reads.plate,
  hits.read_plate and the hotlist ''→NULL expiry — no suppression
  re-key, no hotlist_members canonicalization, no holds backfill.
- The builders' suite repo-layout defect is real (ChatGPT + Claude
  seat 1, independently): run_tests.py needs a ../janus11 sibling the
  public repo does not provide; from the repo layout it stops at 304.

## Adjudications

- **Gemini N4 vs Vesper seat (migration suppressions): Gemini was
  right in substance.** The Vesper seat judged the gap unreachable
  because supported write paths normalize at insert; three seats then
  reproduced the failure on databases written by the REAL 1.1 code
  (Claude 1 R5-01, Claude 2 R5-03, Qwen F1). ChatGPT's contrary
  P4-FIXED probe used a hand-built legacy-shaped DB, not the 1.1
  tree; the real-tree reproductions govern.
- **Missing-tier default: ACCEPTED** (ChatGPT, Claude 1, Claude 2,
  Qwen, both DeepSeek seats). Tier 2 is the only legal value; the
  default cannot widen access. Minority (DeepSeek-native, Grok)
  wanted explicit-only; Grok's vote is discounted with its seat.
  The default must be visible: SHARE_OUT chains tier_defaulted (Q27).
- **A28 refusal-to-boot: CORRECT, unanimously.** The ceremony is the
  defect (Q3), and Claude 1's R5-13 shows the current check is a
  file-vs-env proxy that pins a WRONG key placed in the file — the
  ceremony must verify, not proxy.
- **Silent attack verdicts:** a refusal is a pass only where the
  refusal IS the attack (A28, A37). Re-aimed, two of the eight FAIL:
  A14c (rotation grind → Q23) and A18 with anonymous concurrent
  callers (pre-auth verify → Q18). The rest get printing, re-aimed
  tests in-tree (Q28).

## The convergent core (found by ≥2 independent seats, executed)

1. **The upgrade voids protections** — suppressions not re-keyed
   (Claude 1, Claude 2, Qwen, DeepSeek-chunked), hot-list memberships
   not canonicalized (Qwen, DeepSeek-chunked), holds voided by NULL
   review_by (Qwen). → Q1, Q2.
2. **Restore is not failure-atomic and still self-vouches in the
   lost-key paths** (ChatGPT F1/F2-cluster, Qwen F8, Claude 1
   R5-14/R5-17, Claude 2 R5-19, Vesper P6 note). → Q25.
3. **Evidence lifecycle breaks at the hit boundary** — stranded
   bundles, re-export races, deleted-bundle protection, disposition
   text with no clock (Gemini N1, ChatGPT F2/F5, Claude 1 R5-04,
   Vesper F3). → Q7.
4. **Retention's two clocks disagree** (Gemini N2, Vesper, Qwen,
   Claude 1 R5-05, Claude 2 R5-04-cluster). → Q6.
5. **The Compact gate reads filing order, not audit time; the
   cross-audit never checks checkpoint age; the rotation seed is
   still grindable** (Claude 1 R5-06/R5-07, Claude 2 R5-11/R5-12/
   R5-17, Qwen F4). → Q21, Q22, Q23.
6. **flush_deferred races outside the lock** (Gemini N3, Vesper F1,
   Qwen F7). → Q16.
7. **Authorization fences leak around the edges** — config_closed
   missing on POST writes + /report/compile (Gemini N6, Vesper F4,
   Qwen F3, Claude 1), witness attestation forgery (ChatGPT F3,
   Claude 2), evidence expand bypassing Tier 3 (Claude 2 R5-20),
   pre-auth chain verify (Claude 2 R5-02, Qwen F9). → Q9, Q18, Q10,
   Q24.
8. **Supersede/bridge semantics lose alerts and overwrite verified
   evidence** (Claude 1 R5-03, Claude 2 R5-15/R5-16, Qwen F6). → Q5.
9. **Free-text expiry** (Claude 1 R5-02, Claude 2 R5-05). → Q4.

## The 1.2.2 commission (Q1–Q28)

Build in a NEW tree (janus122/) from janus121. Every item ships with
a fail-before-fix test. Acceptance is the invariant standard at the
end, not this list alone.

**A. Upgrade & migration (the spine)**
- Q1 Registry-driven migration repair: iterate PLATE_DATA_STORES and
  repair every registered store — re-key suppressions from stored
  plate text under the current formula; canonicalize
  hotlist_members.plate/state and suppressions.plate; backfill
  holds.review_by or explicitly re-issue with a chained notice
  (never silently void a hold); chain MIGRATION with per-store
  counts; /health marker while any store has unrepaired rows.
  Migration tests boot the repo's REAL 1.1 and 1.2 builds.
- Q2 Locked-boot ordering: no schema change runs unchained on a
  KEY_LOCKED boot; the ''→NULL and Q1 repairs run on the first
  unlocked boot and are chained then.
- Q3 Pin ceremony that verifies: before pinning a candidate key over
  an unpinned non-empty chain, recompute a stored keyed ref the DB
  can check and pin only the key that verifies it; if nothing is
  checkable, a two-operator fingerprint ceremony. Ship
  provision.py pin-audit-key (0600 write + pin) and fix the lock
  message to name the file step. (Kills Claude 1 R5-13.)

**B. Hot list & ingest**
- Q4 Expiry is a parsed instant: ISO-8601 validated at the door (400
  otherwise), stored canonical UTC, compared as parsed values in
  ingest and hotlist_sync; stored free-text values migrated or
  refused loudly at boot.
- Q5 One supersede decision, in Janus: the bridge drops its
  (event_id, plate) dedupe (Janus dedupes persistently); a different
  plate supersedes only on strictly better confidence, judged with
  the Frigate event phase; hits are marked superseded/withdrawn,
  NEVER deleted (a hit id the API returned never 404s); reads are
  append-only — a correction is a new row linked to the old, and a
  read behind a VERIFIED hit is immutable; outcome rows are marked
  withdrawn, not deleted (the § 1805 question is routed to Ben; the
  default preserves the record).

**C. Retention & evidence**
- Q6 One retention decision function: the purge deletes exactly what
  registry_breaches flags (same SQL, same timestamps; no floor-day
  arithmetic anywhere); retention.py runs single-transaction —
  Chain(DB, conn=db) before the loop, purge + RETENTION_PURGE in one
  commit, with a kill-between test.
- Q7 Evidence lifecycle keyed on the evidence record: release /
  disposition / destroy work after the hit row purges; an unreleased
  bundle whose hit is gone is flagged in /health; re-export is
  failure-atomic (old bundle deleted only after new bundle + row +
  chain commit) and resets released_ts / disposition / destroy_by;
  a bundle missing on disk does not protect a hit; disposition notes
  and partner case_refs get a defined retention class in the
  registry (keyed/validated like other refs — no raw free-text
  plate storage).
- Q8 Registry completeness extended to the leftovers (share_queries
  classes fixed so ordinary sharing yields no permanent false
  breach; every plate-bearing column under the allowlist test).

**D. Authorization boundaries**
- Q9 config_closed() at the dispatch level for ALL data endpoints,
  POST included (/hotlist, /verify, /holds + release, /outcomes,
  /suppressions + release, /reads, /cases, /shares, /tier3/request);
  POST /report/compile behind the same role fence as GET /report.
- Q10 Evidence expand requires an executed Tier 3 request for the
  same case + plate; the reason is chained.
- Q11 Tier 3 instruments are configuration: the accepted basis_type
  set is config, defaulting to judicial instruments only; "other"
  cannot execute (the legal question is Ben's; the code defaults
  closed).
- Q12 Holds require a validated case and the designated role;
  release only on documented authority (prosecutor sign-off or case
  closure). Strict decimal + existence validation for every ref
  parsed anywhere (holds, verify hit_id — "1garbage"/"1.0" refuse).
- Q13 The outside auditor's emergency review is independent: a
  supervisor's review never satisfies or pre-empts it; the auditor
  sees fragment/case/why/basis.
- Q14 Case-feed freshness: a configured staleness window on the case
  list itself (file age or stamped export time) fails closed and is
  named in /health.
- Q15 AUTH_FAIL throttle crash fixed (markers out of the bucket
  dict); chain-growth caps extended to SHARE_BLOCKED / receipt
  re-posts.

**E. Chain & verification integrity**
- Q16 flush_deferred presence-checks on a separate connection (or
  wholly inside DBLOCK): no phantom sink entries — the Vesper-seat
  probe becomes a regression test.
- Q17 v1 chain entries: _verify_rows cross-checks payload kind/ts
  against the columns, so a relabeled v1 entry fails verification.
- Q18 Authenticate before computing: /health and /audit/verify never
  scan pre-auth; the cached verify is single-flight.
- Q19 Scrubber exemptions are value-verified (cam/agency must be in
  the camera registry / partner list, else hashed); INGEST_REJECTED
  chains coded reasons, not raw caller text, and is throttled;
  ROTATION_PUBLISH.members gets a path-aware exemption.
- Q20 _insert_locked rejects caller fields named v/ts/kind.

**F. Compact**
- Q21 The gate is a function of audit TIME: refuse reports older
  than the newest on file and duplicate report_hashes; gate and
  reinstate read the latest by report ts.
- Q22 compact.py fails a partner checkpoint older than 26h and
  advances its high-water mark to the verified checkpoint (a
  post-checkpoint rewrite fails the next audit).
- Q23 Ungrindable rotation: cycle_start fixed by rule (previous
  cycle's end, or a value fixed in the agreement before the root is
  knowable); ONE schedule builder shared by Janus and rotation.py
  (import, not reimplementation); the published document carries
  every field --verify needs; the signed portion covers period_days
  and cycle_start.
- Q24 Witness attestations: a supervisor attests only for the home
  agency; partner attestations require the registered Ed25519
  signature + schedule membership; no free-text agency is chained.

**G. Backup / restore**
- Q25 Failure-atomic and verified: backup.py verifies the chain
  before signing (refuses a broken chain); restore stages and
  verifies everything — manifest against HOST keys only; when a host
  signing_pub.pem exists, a signature against it is required in ALL
  paths including lost-audit-key; a tarball's internal keys are never
  a trust root when any host key exists — and only then swaps; any
  failure leaves the live installation byte-identical; the prune
  never deletes .pre-restore key copies by mtime.

**H. Config, packaging, docs**
- Q26 _reload_config treats TypeError/KeyError like a bad file:
  stale + fail-closed, never a 500 loop.
- Q27 Search fragments canonicalized like plates; a Tier 3 request
  scrubbed by age EXPIRES instead of executing blank; /report
  snapshot param validated (400); custody_excerpt includes
  OUTCOME_UPDATE; SHARE_OUT chains tier_defaulted when defaulted.
- Q28 Packaging: the builders' suite runs green from the PUBLIC repo
  layout (fixtures in-tree or repo-relative paths); the round-4 and
  both round-5 attack suites live in-tree with wrappers that print a
  verdict for every scenario (silence = harness failure); A18
  re-aimed at 600k entries with anonymous concurrent callers; docs
  swept (COMPACT.md + backup manifest version strings).

## Acceptance standard for 1.2.2 (Claude seat 1's forced change, adopted)

1.2.2 is accepted against INVARIANT tests, not the findings list.
Six property suites, adversarial, over generated inputs, through the
public API:
1. Hot list: every expiry the API accepts is a parsed UTC instant;
   an entry alerts on every read until that instant.
2. Ingest: no delivery order or redelivery of one event ends with
   less alerting than its best read; no returned hit id ever 404s.
3. Suppression: on databases upgraded in place from the repo's real
   1.1 AND 1.2 builds, every hit-disclosing endpoint hides a
   protected plate.
4. Retention/evidence: for any data age, a retention run followed by
   the check reports zero breaches; every registered bundle is
   releasable, dispositionable, destroyable.
5. Compact: the gate is a function of audit time, not filing order;
   the rotation publisher cannot predict the pair.
6. Spec gates (pilot spec §§7–9): the outside auditor reviews every
   emergency use and sees what it reviews; holds stand on a validated
   case and the designated role; a stale case feed fails closed;
   Tier 3 executes only on a configured instrument.
Plus: builders' suite + round-4 attacks + Claude seat 1's round-5
suite all green under the orchestrator's own re-runs, from the repo
layout. Fail-before-fix tests for every Claude seat 2 finding (its
harness was not recoverable; its review text is the specification).

## Routed to the City Attorney (additions from round 5)

Tier 3's lawful instrument set and whether any non-judicial basis may
ever unlock it (Q11's core); hold authority and spoliation risk of
early release (Q12); the § 12-12-1804(b) boundary — exported bundle vs
hit row past 150 days, and disposition-note retention independent of
the hit (Q7); whether HOLD_DAYS and RETENTION_DAYS are the same
statutory clock, and the cap margin question (purge at 149 days?);
suppression placement authority (one supervisor places on a free-text
reference; release takes two); permanent retention of order_ref /
case_ref vs the records schedule; the Compact during the pilot
(spec §9); outcome rows deleted vs marked withdrawn under § 1805
reporting (Q5's default preserves them); chain_auditor's retention
blindness — is retention part of "auditing the books" under the
Compact? Plus everything routed in rounds 2–4 (Act 668 of 2025
remains flagged-not-settled; § 1804(d) sharing characterization;
§ 1802 derived-data status of keyed refs; § 1808(b) scope).

Nothing in this synthesis was sent to ACIC or the City Attorney.
Documents (white paper, deck) remain frozen until the code loop
converges.
