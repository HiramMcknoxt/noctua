# Round 8 Synthesis — NOCTUA 1.2.5
<!-- VESPER · the evening watch — synthesis document, not code -->

Written by Vesper, Nov 25, 2026. Verdict: **NOT CONVERGED.**

Seats: cold Vesper (executed; `vesper-seat/vesper-review.md`), Claude (executed;
`claude-review.md`), Gemini (code-read, Auto tier; `gemini-review.md`),
DeepSeek (chunked code-read, deliveries in progress; `deepseek-review.md`),
ChatGPT (**excluded — fabricated review**, see §5). Merlin and Qwen had not
returned when this synthesis was written (both gated on Corey: a manual file
attach and a CAPTCHA slider respectively). DeepSeek's final verdict was still
withheld pending its last chunks; its returned portions are incorporated.

The pattern of the round: 1.2.5's fail-closed spine **held** under executed
attack (T1 restore flip, T3 fence detection, T5 strict signatures, T8 custody
— all verified by execution). What failed is, again, lifecycle behavior of the
new controls themselves: a lockout that locks the wrong people, a fence with
no exit, a delivery ledger whose failure mode taxes every request. The core
safeguards are no longer the story; the controls' own failure modes are.

## 1. Criteria

1. **No surviving deployment-blocking/critical code finding — FAIL.**
   The unauthenticated lockout (F-1/C8-01) and the fence with no exit (C8-02)
   both survive execution.
2. **Every forced change implemented or answered in writing — FAIL.**
   T7's /hotlist leg was answered in form, not substance: its acceptance case
   is weak-shaped (never submits an unknown plate) and the oracle it claims to
   close is intact. Judgment call (e) was answered with an absence-proof this
   round rejects.
3. **What remains is documented CANT-DO limitations or legal questions — FAIL,
   narrowly.** R-B's documentation misdescribes the mechanism it discloses
   (the 404 does not conflate protected with unknown; unknown plates return
   201), and C8-11's custody-documentation drift is the same class of fault.
   An inaccurately documented limitation is not a documented limitation.
4. **Orchestrator re-tests pass — PASS.** Vesper's cold battery on 1.2.5:
   single-process exit 0, every leg reconciled line-by-line with
   TRACK-125-REPORT.md (335/335; T battery 20/20, all discriminating).

## 2. Findings register (consolidated, with verification status)

- **F-1 / C8-01 [CRITICAL-HIGH, EXECUTED by two seats independently] — the T2
  lockout counts mere 401s, so anyone can lock any account, including the
  machine identities and both supervisors.** Five wrong-key (or keyless)
  requests naming `ingest.local` lock it for 900 s; the bridge's correct key
  then gets 401 ACCOUNT_LOCKED; reads are LOST (the bridge does not retry),
  undercounting the § 1805 totals. Renewable indefinitely. Locks persist
  across restart; unlock is supervisor-only over HTTP, so locking both
  supervisors removes the only exit short of waiting or hand-editing the DB;
  locked accounts do not feed /health's ok_all, so health stays green until
  the 6-hour camera-silence alarm misattributes the cause. A legitimate
  trigger exists too: stale/reused second-factor codes count as failures
  (Claude r6). Severity disagreement preserved: cold seat High (fails loud,
  chained, health-named), Claude Critical (the supervisor-lock extension and
  the lost-reads point). The extension is executed fact; criterion 1 fails on
  either rating. **Both seats' forced changes point the same direction and
  are merged in U1.**
- **C8-02 [HIGH, EXECUTED] — the anchor fence has no exit for repair-class
  reasons.** A torn final checkpoints line (power cut during checkpoint.py's
  append) records `checkpoints_malformed`; `_anchor_accept` refuses every
  reason except `checkpoint_disagreement`; and `anchor_fenced()` checks the
  recorded flag before any live re-evaluation (janus.py:2037), so repairing
  the file, restarting, and signing a fresh matching checkpoint leaves the
  service fenced forever. Verified in code by Vesper. The only exit is
  hand-editing `meta` — unchained state surgery, the thing the chain exists
  to prevent. Same trap for checkpoints_unreadable / checkpoints_missing /
  anchor_check_error.
- **C8-03 [HIGH, EXECUTED] — a diverged sink obligation makes every request
  rescan the whole sink file under DBLOCK, forever.** 0.17 s/pass at 100k
  lines, 1.81 s at 300k; a plain read goes 2 ms → 526 ms; the divergence
  never heals and no documented recovery exists. Trigger is any rollback
  under an existing sink — including an honest restore, i.e. the recovery
  path itself plants the tax.
- **F-2 / C8-05 [MEDIUM, EXECUTED by two seats] — the /hotlist 404 uniquely
  identifies protected plates** (unknown and unprotected plates return 201),
  and the T7 acceptance case that claims otherwise is weak-shaped. DeepSeek
  adds the chain channel: SUPPRESSION_CONFLICT entries are readable by
  chain_auditor/partners — by design (the chain is the audit), but R-B's text
  must say so instead of claiming the signal is "removed."
- **C8-04 [HIGH→MEDIUM as reconciled, EXECUTED] — redelivery withdrawal.**
  Two separable parts: (i) ingest confidence is unvalidated — NaN, inf, and
  out-of-range values are accepted, and NaN withdraws a 1.0 hit. Defect,
  uncontested. (ii) A strictly-higher-confidence different-plate redelivery
  by the ingest identity alone removes a PENDING hit from the review queue.
  This is the (c) disagreement: Gemini and the cold seat accepted the
  strict-outrank reconciliation as built; Claude rejects the *removal*.
  U4 adopts Claude's queue-preservation shape, which keeps R9's currency
  rule and ends unreviewed disappearance.
- **C8-06 [MEDIUM, EXECUTED] — DEMO_MODE=1 on a provisioned install waives
  every human's second factor, silently.** `_totp_required` returns False
  under DEMO_MODE (janus.py:2569); nothing checks the provisioned marker.
  Judgment call (f) is answered: named degradation is NOT sufficient. U5.
- **C8-07 / R-D [MEDIUM, EXECUTED] — key-only pickup is a full takeover**
  when a re-enrollment is pending (secret + fresh recovery codes + rotated
  key; the holder's old key dies). Three seats ratified the tradeoff as
  documented; Claude dissented with an executed demonstration. The
  orchestrator sides with the demonstration: U7 adds a confirmer-issued
  one-time pickup token.
- **C8-10 [MEDIUM, EXECUTED] — the backup escrow defaults to a sibling of
  the backup root** (backup.py:227-230), so the T8 custody split is nominal.
  U10.
- **C8-12 + cold-seat (e) [LOW] — T4's absence-proof is falsified by
  execution**: a directory at `<sink>.spool` makes sink_status() raise. The
  absence-proof is retired; U8 requires the fault-injection case.
- **Lows bundle**: sentinel.py docstring still says 1.2.4 (DeepSeek,
  verified); pubkey_fingerprint returns sha256(b"") for an empty-body PEM
  instead of None (DeepSeek F1); Gemini's _totp_pickup persistence edge
  (users-file write can succeed with zero matched entries while the chain
  asserts a rotation — mechanism verified by Vesper); DeepSeek F4 pickup
  failure-atomicity (seat's own conclusion: current order is the better of
  two; answered by U7's matched-count guard); tier3 approve runs
  run_search on a retention-scrubbed "pref:" fragment, executing an aged
  request empty instead of expiring it (DeepSeek F3, verified by Vesper
  across the registry/retention/handler code — narrow: requires a retention
  run to die between registry entries); scrubber misses digit look-alikes
  and ≥4-token fragmentation (cold F-3, Claude C8-13 — every class T9
  actually claims is detected; the misses are outside the claimed classes
  and become claimed in U11); TOTP store two-writer hygiene (cold F-4,
  Claude C8-08 — C8-08's "corrupt store → key-only" worst case is NOT
  sustained under T1, verified at janus.py:2561 + auth()'s provisioning
  gate; the fixed-.tmp race hygiene is real); C8-09 chain_auditor env
  custody (both factors in the job environment — documentation item);
  C8-11 documentation drift (INSTALL §6 names the wrong checkpoint key;
  OPERATIONS §10 says "Administrator" where the code requires supervisor;
  COMPACT.md labeled 1.2.4; INSTALL §7 omits the escrow split).
- **Held under attack (executed, cold seat)**: T1 restore flip, T3 fence
  detection, T5 strict signatures, T8 confirmer custody; SR1-03 concurrent
  replay still not reproduced (≤1 auth per code, 3 trials × 32); DeepSeek
  F5 (keep-alive memo persistence) neutralized with socket-level proof.

## 3. Residual rulings

- **R-A — RATIFIED, narrowed by U9.** Reproduces exactly as documented; both
  controls fail closed; the state is loud. Claude's tightening (ceremony
  key-only auth only while reads/hits are empty; /reads refuses on an
  unprovisioned non-demo install) is adopted — after U9 the residual is a
  pre-provisioning backup that already contains reads, which the go-live
  gate (INSTALL §0) forbids creating.
- **R-B — NOT ratified as documented; closed by U6.** The mechanism was
  misdescribed and the HTTP oracle is real. U6 adopts Claude's 202 +
  supervisor-queue shape (a fake 201 fails because GET /hotlist exposes the
  list). The chain channel is named as by-design: the audit trail carrying
  the probe record is the audit working, disclosed as such.
- **R-C — RATIFIED**, with Claude's addition: one bridge serves all nine
  cameras in the reference deployment, so camera binding buys nothing until
  per-site bridges exist; jobs binding is meaningful — "one jobs identity
  per job" becomes an INSTALL checkbox (documentation, no code change).
- **R-D — NOT ratified; closed by U7** (see C8-07).
- **R-E — RATIFIED** by three seats (Gemini, DeepSeek, cold seat by
  arithmetic: ~0.51 appends/s average demand vs ~17–19/s ≈ 33× headroom).
  DeepSeek's caveat is adopted: the pilot operations plan gets a
  burst-of-9-cameras test; the average is not the operationally relevant
  number. C8-03 is the divergent-state exception and is fixed by U3.
- **R-F — RATIFIED with Claude's condition**: adapted seat files keep their
  originals beside them with a one-line reason. The cold seat diffed both
  adaptations itself: assertions intact. The one re-point that certified
  the /hotlist 404 is rejected with R-B and replaced under U6.

## 4. Judgment-call rulings

(a) Ceremony state — ACCEPT, plus U9's tightening.
(b) Fence line — ACCEPT the line; U2 adds the missing exit.
(c) T7/R9 reconciliation — SUPERSEDED by U4 (currency by strict out-rank;
    alerts never leave the queue unreviewed; conf validated).
(d) Escrow split — ACCEPT the split; U10 makes it real.
(e) Absence-proof — REJECTED as sufficient (two executing seats); U8 case
    required. Gemini's acceptance is recorded as the dissent.
(f) Demo mode as named degradation — NOT sufficient (Claude C8-06 executed);
    U5 boot refusal on provisioned installs. The cold seat's non-localhost
    bind refusal is additionally noted for the pilot gate (production binds
    localhost behind a proxy, so it cannot be the code-level control).

## 5. Seat adjudications

- **ChatGPT — EXCLUDED.** Its review describes a different system
  (a `reset_janus_credentials.py`, `_fallback_secret()`, JANUS_KEY /
  SENTINEL_SHARED_SECRET env vars, "LLM API authentication" — grep-verified
  zero matches across the tree; cited lines contain unrelated code; its
  residual rulings answer questions never asked). Vote and forced change
  void. Second fabrication exclusion in the loop's history (cf. Round 5
  Grok). Standing rule reaffirmed: a seat return is not evidence until its
  citations spot-check.
- **Gemini — weighted.** Ran on the Auto tier (named tiers pay-gated,
  declined) and believed files 04–07 unattached when they were in the UI;
  its conditional vote rested largely on that misread and is discharged by
  the record. Its ratifications align with the executing seats on R-A/R-C/
  R-E/R-F; its two Lows are real (one mechanism-verified by Vesper).
- **DeepSeek — credited for honesty.** Refused to fabricate from an 8%
  truncation, then reviewed rigorously in chunks: confirmed the sink design
  and Chain serialization, caught the docstring version string and the
  fingerprint mismatch, ratified R-A/R-E/R-F from code. Final verdict
  pending its last chunks at synthesis time.
- **Claude — the round's heaviest return.** Rebuilt the tree, executed
  eleven repros, found the round's second blocking defect (C8-02) and the
  sharpest form of the first. Its fix shapes are adopted in U1, U2, U4,
  U6, U7, U10 more often than any other seat's.
- **Cold Vesper — the round's other executing seat.** Found F-1 first,
  falsified the builder's R-B mechanism by execution, diffed the R-F
  adaptations itself, and held the spine.

## 6. The 1.2.6 commission (items U1–U11)

Acceptance standard: as for 1.2.5, plus every U item carries a
discriminating case that FAILS on 1.2.5 and PASSES on 1.2.6 (or a written
absence-proof the next round accepts), and the two seats' repro shapes
(r1/r6 lockout, r2 torn checkpoint, r5 hotlist, r8 sink rescan) enter the
battery as cases. All legs re-run cold by Vesper before Round 9 is called.

- **U1 Lockout scope.** A failure counts toward the 5-strike lock ONLY when
  the presented key verified, the account is human, and the second factor
  was wrong/missing/replayed after that valid key. Wrong or missing keys
  never count (they still chain and count in /health's per-target totals).
  Machine identities never lock. Locked human accounts feed /health ok_all.
  Add `provision.py unlock`: shell-side, chained, the audited break-glass
  for the all-supervisors-locked case. Cases: keyless/wrong-key spray
  against ingest.local and both supervisors → correct keys still work,
  nothing locked; five wrong TOTP codes after a valid key → locked;
  legitimate stale-code presentation pattern (r6) does not strand the
  officer beyond the designed behavior — the case states what the designed
  behavior IS (a replayed code is a failure; the lock needs five).
- **U2 Fence exit.** anchor_fenced()'s live re-evaluation can CLEAR a
  recorded mismatch when the current evaluation is clean: the flag is
  deleted and ANCHOR_CLEARED is chained with the prior reason and the
  healing evidence (newest checkpoint entries/root). anchor_check_error
  persists only after 3 consecutive failed evaluations. checkpoint.py
  writes via temp file + atomic replace, and on open truncates a torn
  FINAL line (a partial last line only — mid-file malformation still
  fences). _anchor_accept keeps its checkpoint_disagreement-only rule.
  Cases: torn line → fenced → repair → fence clears with no anchor-accept;
  mid-file malformed line → fences, does not auto-heal while malformed,
  clears after repair; genuine disagreement still requires anchor-accept.
- **U3 Sink divergence cost.** Per-request delivery cost must not scale
  with total sink size after a process's first pass: memoize/persist the
  verified seq→hash index (in-process memo keyed on sink identity +
  length watermark is acceptable if the case proves the bound; a persisted
  index is better). Add a supervisor-chained divergence-resolution path
  (SINK_DIVERGENCE_ACCEPTED naming the stranded seqs) and document the
  ceremony in OPERATIONS; INSTALL §7's post-restore steps name it. Case:
  diverged sink at ≥100k lines — plain-read latency after warmup under a
  stated bound; divergence resolvable via the ceremony with chain evidence;
  no obligation silently dropped (resolution names the seqs).
- **U4 Supersede preserves the alert.** Ingest confidence must be a finite
  number in [0,1] — NaN/inf/out-of-range/non-numeric → 400, nothing stored.
  A superseded PENDING hit becomes PENDING_SUPERSEDED and remains in the
  review queue, linked to its successor, until a supervisor disposes of it
  (disposition chained). Strict out-rank still governs currency for
  matching; R9's correction case must still pass. Cases: NaN conf → 400;
  0.99 different-plate supersede → old hit PENDING_SUPERSEDED and listed,
  new hit current; equal-rank still refused.
- **U5 Demo mode vs provisioned installs.** Boot refuses (exit 3, the
  key-gate pattern) when NOCTUA_DEMO_MODE=1 is set on an install whose DB
  carries totp_provisioned; the refusal is chained where the chain is
  writable (DEMO_MODE_REFUSED). Demo installs (unprovisioned) are
  unaffected; suite_demo behavior unchanged. Case: provisioned + demo env
  → refusal; unprovisioned + demo env → boots and waives as designed.
- **U6 /hotlist completion.** Non-supervisor adds return a uniform 202
  ("submitted for supervisor approval") for protected, unprotected, and
  unknown plates alike; the entry is stored pending; a supervisor queue
  surface lists pending adds; supervisor approval activates the entry,
  rejection removes it — both chained. Supervisor adds keep the direct
  201 path. Hits on a pending or protected entry remain born-suppressed.
  Rewrite t7_hotlist_oracle: submit all three plate classes as a
  non-supervisor and assert byte-identical responses; assert the entry is
  not active until approved. TRACK documentation states the chain channel
  plainly (probe records are visible to chain readers by design).
- **U7 Pickup hardening.** Pickup requires the holder's key PLUS a one-time
  pickup token generated at re-enrollment confirm, shown only to the
  confirmer (who conveys it out-of-band), stored hashed, single-use,
  expiring with the pending window. The users-file rotation counts matched
  entries: ≠1 → pickup fails unconsumed (500, chained PICKUP_FAILED).
  Cases: key-only pickup → 401; key+token → success; token reuse →
  refused; users-file divergence (entry removed between reloads) → pickup
  fails unconsumed and the store still shows pending.
- **U8 Sink-status fault injection.** Case: a directory at <sink>.spool
  (and a second environmental fault the platform supports) → sink_status
  returns an unknown/not-ok state, /health names it, nothing crashes, and
  delivery obligation handling treats unknown as not-delivered. The T4
  absence-proof text is replaced by this case's citation.
- **U9 Ceremony-state tightening.** On a non-demo unprovisioned install:
  POST /reads refuses (503, chained) and key-only human authentication is
  permitted only while reads and hits are both empty; once plate data
  exists, an unprovisioned install serves nothing until provisioning
  completes (health names the state). Cases: fresh install ceremony works
  end-to-end (provision → enroll → data flows); populated-but-unprovisioned
  DB → /reads 503 and human auth refused with the state named.
- **U10 Escrow location.** backup.py's default escrow directory is outside
  the backup root; an escrow path inside the backup tree is refused loudly
  (nonzero exit, nothing written). INSTALL §7 documents the split and the
  refusal. Case: default run → escrow outside the set; explicit inside
  path → refusal.
- **U11 Smalls bundle.** (i) Version-string sweep: sentinel.py docstring
  and every doc that names a version (COMPACT.md) state the build's
  version; a case greps the tree for the prior version string in
  user-facing places. (ii) pubkey_fingerprint of an empty/body-less PEM
  returns None per its docstring; case included. (iii) Tier 3 approve: a
  plate_fragment that is "pref:"-prefixed or fails validate_fragment
  expires the request on the same path as the why/basis scrub. (iv) TOTP
  store writes use a unique temp path + os.replace. (v) Scrubber: fold
  digit look-alikes (confusable digits incl. Cyrillic З→3 and
  Arabic-Indic/Devanagari digits via Unicode digit normalization) — the
  claimed classes are restated to include them, with cases; ≥4-token
  fragmentation stays a named non-claim. (vi) C8-11 doc fixes (INSTALL §6
  checkpoint key name, OPERATIONS §10 supervisor, INSTALL §7 escrow,
  OPERATIONS note that a chain_auditor job environment holds both of that
  identity's factors). (vii) R-F condition applied: the two adapted seat
  files gain their originals beside them with a one-line reason each.

## 7. What convergence now requires

Round 9 runs on 1.2.6 with the same standard. The open legal/institutional
lanes are unchanged (Ben: 22 questions, incl. the CJIS-AA lockout note
Claude routed — C8-01 is also a compliance question on Path B; ACIC: 10
questions; no replies as of this synthesis). Criterion 5 remains Corey's
open decision, not adopted.

---

## Addendum (Nov 25, 2026, ~12:26 PM CST) — DeepSeek final

DeepSeek completed its chunked read (all of janus.py + sentinel.py; scripts
unread, its vote expressly contingent on TRACK-125's script dispositions)
and voted **CONVERGED** — the round's only convergence vote. It is recorded
and does not change the verdict, for two reasons:

1. Its one engagement with the lockout (its F36) traces the same code the
   executing seats ran, but classifies the unauthenticated lockout as a
   "standard consequence / runbook gap, not a code defect," and so does not
   count it against criterion 1. The round's severity standard judges
   findings against the system's stated guarantees; two seats EXECUTED the
   consequence against the availability-of-alerts guarantee (ingest dead,
   reads lost, both supervisors lockable with no in-app exit). Executed
   evidence governs classification disputes. Notably, the seat's own F36
   remedy — an out-of-band `provision.py` unlock — is Claude's forced
   change and is already U1; U1's counting change goes further and removes
   the unauthenticated lock entirely.
2. It never engaged C8-02 (the fence with no exit), the round's second
   blocking defect, and its vote is contingent on material it did not read.

Useful confirmations from its read: R-C enforcement is real (403 + chained
INGEST_REJECTED / HEARTBEAT_REJECTED in the handlers; /health naming
correctly not an ok_all input), with one nuance added to the R-C record —
binding is field-presence-conditional, so `"cameras": []` means unbound,
not bound-to-nothing. run_search's T9 leg verified at source. Its
anchor-transaction question was answered by its own later reading (not
reachable at the visible call sites).

---

## Addendum 2 (Nov 25, 2026, ~12:35 PM CST) — Qwen seat; commission extended to U14

Qwen returned (code-read; Corey solved its CAPTCHA by hand) with the round's
last substantive input: NOT CONVERGED, criteria 1/3 FAIL, and two NEW Highs
no other seat found — both **verified in code by Vesper** before adoption:

- **Q-F1 [HIGH, VERIFIED] — sink tail reconciliation.** `_sink_file_tail`'s
  `except Exception: return 0, None` makes a torn final sink line
  indistinguishable from an absent sink; `_deliver_locked` (sentinel.py:1823)
  then takes the "vanished" branch, resets the recorded tail, and re-delivers
  the WHOLE chain into the existing file — duplicates throughout the Clerk's
  witness mirror, ledger cleared, health green. A truncated-but-nonempty
  sink (0 < file_seq < tail_seq) matches no branch: the missing range is
  never re-delivered, health green. Trigger is a named failure mode (power
  cut / ENOSPC partial write), no attacker needed. **This is Qwen's forced
  change and becomes U12.**
- **Q-F2 [HIGH, VERIFIED] — restore strips the host's keys.** restore.py
  moves the live audit + signing keys to .pre-restore-* unconditionally,
  then reinstalls keys only if the set's manifest carries them
  (restore.py:430/434) — and T8's escrow split means 1.2.5 sets never do
  (hashes only, under "key_escrow"). Every 1.2.5 restore therefore leaves
  the host keyless (file-key: KEY_LOCKED exit 3) or re-mints the signing
  identity (env-key: fresh keypair → every historical checkpoint mismatches
  → anchor fence), while printing "restored OK." The battery cannot see it:
  its restore instances publish no checkpoints and the ceremony endpoints
  are fence-exempt. **Becomes U13.**
- Qwen's **R-A ruling is adopted over the round's ratifications**: the
  residual is closable — restore leaves the outgoing live DB on disk as
  .pre-restore-*; if the OUTGOING install was provisioned, the incoming
  install is treated as provisioned (must_reenroll materialized) regardless
  of the incoming DB's marker. Folded into U13; R-A is then closed, not
  narrowed.
- **Q-F3 [MEDIUM] — anchor evaluation cost.** _anchor_evaluate verifies
  every checkpoint's signature via an openssl subprocess under DBLOCK every
  5 s, over a file that grows daily forever (the R4/S10 shape, reintroduced).
  **Becomes U14** (memoize per-checkpoint verification by content; evaluate
  incrementally; the U2 auto-clear must not re-verify the whole file per
  window either).
- **U6 amended (Q-F5)**: _post_hotlist checks suppression BEFORE the
  list-registry, so a bogus list_name yields a side-effect-free 404-vs-400
  existence probe. U6's uniformity must cover evaluation order: registry
  validation first (uniform response for bogus lists across plate classes),
  then the 202 path. U6's case gains the bogus-list probe shape.
- **U11 additions**: Q-F4 (pickup + re-enroll target checks mirror auth()'s
  disabled test); Q-F6 (alert_check names migration_status incomplete);
  sentinel.totp_code gains the base32-padding tolerance janus's wrapper has
  (auditor tooling parity); _sql_order_covers fails CLOSED on exception
  (a suppression predicate never fails open — case via fault injection or
  a written absence-proof the next round accepts); INSTALL §8 go-live
  checklist gains the bound-identities checkbox (Qwen R-C + Claude R-C).
- Qwen dissents recorded: (c) strict out-rank accepted as built (against
  U4's queue-preservation — U4 stands: it preserves R9 currency AND the
  queue; Qwen's acceptance is noted); R-D ratified conditional on F4
  (against U7 — U7 stands on Claude's executed takeover); (f) bind guard
  recommended instead of U5's boot refusal (U5 stands as the stronger
  form). Its (e) position converges with the executing seats (U8 stands),
  with a cheaper case construction (write-contention) the builder may use.
- Qwen's R-F condition (orchestrator diff of the adapted files) is
  satisfied by the cold seat's own diff — assertions intact.

**Commission is now U1–U14.** The 1.2.6 builder was dispatched before
Qwen landed and has been sent this addendum; the new items are in scope
for the same build. Merlin remains the only seat out (awaiting Corey's
manual attach); anything it adds folds in as a further addendum.

---

## Addendum 3 — Claude seat seated in place of Merlin (Nov 25, 2026, ~14:36–14:48 CST)

Merlin's generation failed twice with empty responses (see the seat log), so at Corey's direction ("just use paid claude seats if you have to") a Claude seat was seated directly on claude.ai in the Merlin slot: Opus 5.5, Medium effort as shown in the interface at sending, same seven-file pack, same brief. Full review: `claude-replacement-review.md`. This seat is recorded as a Claude seat, NOT a Merlin return.

**Vote: NOT CONVERGED** — consistent with the round. The seat executed five reproductions against a rebuilt 1.2.5 tree (each run twice), so its headliners are executed evidence, not inference.

**Its findings map onto the existing 1.2.6 commission — no new blockers:**
- R8-C1 (lockout: anyone can lock any account incl. ingest, health stays green) = **U1**, verbatim its forced change. Independent executed confirmation of the round's headliner.
- R8-C2 (conf NaN/1e9 defeats the anti-withdrawal rule) = **U4**.
- R8-C3 (/hotlist 404 oracle intact; R-B ruled a defect) = **U6**.
- R8-C4 (anchor re-verification cost grows unbounded; ~4.5 s stalls at 3 years of checkpoints) = **U14**.
- R8-C5 (escrow default is a sibling folder, split not real) = **U10**.
- R8-C7 (digit look-alike folding) ⊂ **U11**; R8-C11 (stale version strings) ⊂ **U11**.
- Judgment (e) (directory-at-spool fault injection) = **U8**; (f) (demo refuses on provisioned DB) = **U5**; R-A ratchet = **U13**.

**New items queued for Round 9's brief (none block 1.2.6):**
- R8-C8: move `/holds/release` out of the anchor-fence safety set (releasing a hold is destructive, not protective).
- R8-C9: bound `_auth_fail_totals` growth (unauthenticated memory-growth vector).
- R8-C10: keyed hit references in BLOCKED chain entries (partner-readable entries currently joinable to protected hits).
- Judgment (a) tightening: fence the data surface during the T1 ceremony state (allow provisioning/auth admin/health/safety writes; refuse searches, Tier 3, shares, reports).
- R-D nuance: 24 h expiry on pending pickups (U7's token + matched-count guard already commissioned).
- R8-C6: enroll-2fa shell-operator honesty gap → CANT-DO documentation entry.
- R-F process rule: future packs attach `diff -u` for every adapted seat file.
