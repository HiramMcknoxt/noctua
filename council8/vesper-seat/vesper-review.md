# Round 8 — Cold Vesper Seat Review of NOCTUA 1.2.5

Seat: Vesper (cold seat, independent reviewer, no stake in the build)
Model + effort: the interface shows no model name (subagent session; no model/effort shown in UI)
Date: 2026-11-25
Subject: `~/workspace/noctua-1.0/janus125/` vs baseline `janus124/`
Method: targeted execution. Eleven probes live in `probes/` beside this
review and re-execute cold via `./run-next.sh` (log:
`logs/run-20261125-175340.log`, runner exit 0; every probe produced a
verdict line and every verdict reproduced its individual run). The full
battery was NOT re-run wholesale — criterion 4 is the orchestrator's,
already satisfied; my job was to try to break the new invariants.

**Verdict: NOT CONVERGED.** One High availability finding (F-1) and one
unfinished commissioned fix (F-2) stand between this build and
convergence. Everything else I attacked held — including every
fail-closed shape that Security Round 1 forced into existence. This is
the closest round yet, and the gap is two named, mechanical items.

---

## 1. Findings register

### F-1 [HIGH — availability of alerts] The T2 account lockout locks machine identities; five unauthenticated requests silence ingest for 900 s, renewable indefinitely

- **Attacker model:** outsider on the LAN (Security Round 1 model 1) or
  any unauthenticated network peer. No credential of any kind is needed —
  only a username, and usernames are not secrets (the demo set is
  published in the repo).
- **Path:** T2's lockout (`_auth_lock_note_failure`, janus.py ~2795;
  threshold 5 consecutive failures, 900 s) is applied in `need_auth` to
  every account in the users config, including the `ingest` and `jobs`
  machine identities. Machine keys are high-entropy and never typed by a
  human, so a wrong-key attempt against them is never a typo — it is
  either a misconfiguration (already loud via AUTH_FAIL) or an attack.
- **Evidence (executed, `probes/p_h3_lockout.py`):** baseline ingest
  with the correct key → 201; five wrong-key POST /reads as
  `ingest.local` → 401 ×5; the bridge's CORRECT key then → **401
  (locked)**; ACCOUNT_LOCKED chained (true); supervisor unlock → 200;
  ingest after unlock → 201. The spray is repeatable every 900 s, so
  the lock can be held down forever with five requests per quarter
  hour. The same spray against every account leaves only the 900 s
  expiry (supervisors can unlock each other only while at least one
  supervisor remains unlocked).
- **Severity reasoning:** reads stop landing, so alerts stop — a direct
  hit on one of the three stated guarantees. The system fails LOUD
  (ACCOUNT_LOCKED chained, /health names locked accounts, unlock works,
  the lock does not extend), which is why this is High and not
  Critical: nothing is corrupted, leaked, or silently lost, and
  recovery is one supervisor action or 900 s. But a control introduced
  to protect human logins must not hand an unauthenticated peer a
  renewable off-switch for the alert path.
- **Compensating controls present:** chaining, health naming,
  supervisor unlock, no lock extension. None of them prevent the
  outage; they only make it visible.

### F-2 [MEDIUM — confidentiality] POST /hotlist still leaks protection-order existence; 404 is a unique signal, and the T7 acceptance case claims an equivalence it never probes

- **Attacker model:** low-privilege insider (model 2) — any account
  holding hotlist-add permission (detective tier), no supervisor role.
- **Path:** T7 shaped the protected-plate response to 404 "plate not
  found", intending it to be indistinguishable from an unknown plate.
  Execution shows unknown plates are not 404 at all — they add
  successfully.
- **Evidence (executed, `probes/p_pb_hotlist.py`, five shapes, all as
  a detective):** protected plate WITH reads → 404 "plate not found";
  protected plate with NO reads → 404; unprotected plate with reads →
  201; plate with no reads and no order → **201**; re-adding an
  already-listed plate → 201. Within these shapes, **404 means exactly
  one thing: this plate is under a protection-order suppression.** That
  is the same existence oracle T7 closed on /verify in this same build
  (byte-identical 409s), left open on the endpoint T7 also named.
- **Case defect (cited):** `tests/run_t125_cases.py:890–911`
  (`t7_hotlist_oracle`) asserts only that the detective gets 404 for
  the protected plate and the supervisor gets 403. Its docstring
  claims the response is "indistinguishable from an unknown plate" —
  the case never submits an unknown plate. It is weak-shaped in the
  exact pattern this council flagged in Round 6 (Q16): the case passes
  while the invariant its name claims does not hold.
- **Compensating control present:** every protected-plate probe chains
  SUPPRESSION_CONFLICT, so probing is auditable after the fact. The
  information still leaks in real time to the prober.

### F-3 [LOW — confidentiality] Scrubber coverage boundary: multi-token fragmentation and non-NFKC digit scripts evade `_contains_plate`

- **Attacker model:** authenticated insider deliberately encoding a
  plate into a free-text chain field (the scrubber is a safety net over
  insider-authored text; plate-bearing fields proper are refs, not
  text).
- **Evidence (executed unit matrix, `probes/p_h6_scrubber.py`):** every
  class T9 claims is detected — Cyrillic (upper and lower), Greek,
  full-width, mathematical digits (NFKC folds them), spaced/hyphen/dot
  separators, in-prose placement. NOT detected: a plate fragmented into
  ≥4 single-character tokens inside prose ("plate A B C 1 2 3 at the
  gate" — the token-window joins cap at 3 and whole-string
  normalization only fires when the whole field is the plate), and
  plates written with Arabic-Indic (U+0660–0669), Extended Arabic-Indic
  (U+06F0–06F9), or Devanagari digits (NFKC does not fold them to
  ASCII, `_PLATE_RE` is ASCII, and the confusables map carries no digit
  entries).
- **Disposition:** hardening item. A cheap fix exists (a whole-field
  strip-and-join check across all tokens; digit-script folds in the
  confusables map). Not a convergence blocker.

### F-4 [LOW — integrity of security state] The TOTP store has two uncoordinated read-modify-write writers and no inter-process lock

- **Path (cited):** janus.py's `_totp_accept` loads, mutates, and saves
  the store (`_totp_save`, janus.py:2410, atomic replace, no lock);
  scripts/provision.py runs the same cycle in a separate process. A
  grep for flock/LOCK across both files finds no coordination around
  the store. If the cycles interleave, one writer's save clobbers the
  other's update.
- **Impact shapes if hit:** (a) a just-completed enrollment silently
  vanishes — the operator holds a secret the store forgot; the user is
  then locked out fail-closed at first login (loud, recoverable);
  (b) a consumed TOTP counter rolls back — one used code becomes
  replayable inside its ±1-step window, if an attacker captured that
  exact code in that exact window.
- **Evidence:** structural (citation above) plus a bounded negative
  execution (`probes/p_h8_store_race.py`): 5 cross-process enrollment
  writes interleaved with janus-side activation/auth saves produced no
  lost enrollment and no counter regression. The window is real but
  narrow (one load→save span). Fix when convenient: flock the store in
  both writers, or route provision.py's writes through the running
  server. Not a convergence blocker.

### Observations (no severity; recorded for the next build's list)

- **O-1 — health's witness block is not signature-filtered.**
  `witness_state()` (janus.py:2065, consumed at :8340) selects the
  checkpoint with the largest `entries` without the Ed25519-validity
  filter `_anchor_evaluate` applies. Executed (`probes/p_h4_fence.py`):
  a forged unsigned line with entries=999999 became health's displayed
  "last witnessed" root. `matches_chain: false` keeps the display
  honest about agreement and the fence uses the strict path — but the
  displayed root is attacker-chosen text if the checkpoints file is
  writable. Display-only.
- **O-2 — AUTH_FAIL per-user totals are memory-only.** `_auth_fail_totals`
  (janus.py:2631) is an in-process dict; a restart zeroes the /health
  totals, and a cap-suppressed aggregate chains only inside a later
  `_note_auth_fail` call when a minute bucket rolls — a spray followed
  by silence and a restart can lose the suppressed aggregate entirely.
  The per-attempt chain evidence for counted failures is unaffected.
  Cited, not executed (the shape needs a timed spray + restart).
- **O-3 — auth bursts drop connections.** In the H2 trials
  (`probes/p_h2_concurrent.py`), 0–4 of 32 simultaneous authenticated
  requests per trial closed with no response (RemoteDisconnected).
  Replay protection held in every trial; this is a robustness wart on
  the auth path under burst, not on ingest (the load envelope covers
  ingest and passed).

### Held under attack (verified this round, for the record)

- **DeepSeek F5 (keep-alive memo) stays NEUTRALIZED** — now with
  socket-level evidence (`probes/p_h1*.py`): this server never persists
  a connection; even two unauthenticated /ping requests on one socket
  get one response and a close, with or without an explicit
  `Connection: keep-alive` header. The per-handler `_totp_memo` cannot
  outlive a single request in practice. (The original disposition's
  stated reason — HTTP/1.0 default — was imprecise; the operative fact
  is that connections never persist at all.)
- **SR1-03 (concurrent TOTP replay) stays NOT REPRODUCED** on 1.2.5:
  32 simultaneous same-code presentations, three accounts — at most one
  200 per code in every trial.
- **The anchor fence is complete** (`probes/p_h4_fence.py`): a forged
  checkpoint appended to a LIVE server is detected within the 5 s
  re-evaluation window; GET /search, GET /report, POST
  /evidence/export, POST /hotlist all → 503; safety writes (POST
  /reads, POST /suppressions) → 201; /health and /heartbeat stay up;
  health names `checkpoint_disagreement` and reports ok:false. The
  checkpoints-path-is-a-directory shape boots fenced with reason
  `checkpoints_unreadable` (the 1.2.4 boot-crash shape, T6, is gone).
- **Restore flip (T1)**: post-provisioning restore with the store
  deleted flips all six humans to must_reenroll, key-only → 401,
  TOTP_REENROLL_REQUIRED chained (`probes/p_pa_restore.py`, V3).
- **Two-key provisioning custody (T8)**: the confirmer's response
  carries no secret (regex-checked), enrollment of later users requires
  the confirmer's own factor (`probes/p_pd_pickup.py` setup path).

---

## 2. Rulings on the named residuals

- **R-A (restore indistinguishability) — RATIFIED LIMITATION.**
  Reproduced exactly as documented (`p_pa_restore.py` V1: provisioned
  install → store deleted → DB rolled back to a pre-provisioning
  snapshot with a restore marker → key-only auth 200, health state
  "provisioning"). Both controls fail closed: store deleted alone →
  401 (V2); post-provisioning restore → must_reenroll flip (V3). The
  shape requires an actor who already holds the full backup set AND
  can delete the store — at that point the ceremony state is the least
  of the losses, and it is health-red and named, never silent-green.
  No in-band fact separates this state from a genuine never-provisioned
  install (a never-provisioned install can carry a long chain too);
  the separator is operator knowledge, which is where the builder left
  it. Ratified.
- **R-B (/hotlist residue) — NOT RATIFIED; the documentation misdescribes
  the mechanism.** The builder's §5 calls 404 "protected-or-unknown"
  and "inherent to any add endpoint". Execution (F-2) shows unknown
  adds succeed at 201, so on this code 404 is not a conflation — it is
  a unique protection-order signal. The residue is therefore neither
  inherent nor correctly documented. See F-2 and criterion 2.
- **R-C (unbound legacy identities) — RATIFIED LIMITATION, with a
  deployment condition.** Executed (`probes/p_pc_binding.py`): an
  unbound ingest identity posts reads for CAM-01/05/09 (201 each) and
  /health names `ingest_unbound` / `jobs_unbound` as degradations; a
  hot config reload adding `cameras`/`jobs` bindings takes effect
  WITHOUT a restart, after which cross-camera ingest → 403 +
  INGEST_REJECTED chained and cross-job heartbeat → 403 +
  HEARTBEAT_REJECTED chained. The tightening path the builder
  described is real and operator-usable. Condition for the pilot: the
  deployed config ships bound identities (health already refuses to
  call an unbound install ok).
- **R-D (pickup is key-only) — RATIFIED LIMITATION.** Reproduced
  end-to-end (`probes/p_pd_pickup.py`): with only the target's current
  API key, the pickup returns 200 with the new TOTP secret, 10 recovery
  codes, and a rotated API key — and the new key + new secret then
  authenticate (200), i.e. the key thief ends with the complete
  credential set. Every documented mitigation verified in the same run:
  the confirmer never sees the secret; a second pickup with the new
  key → 409, with the old key → 401; the old key is dead on normal
  endpoints (401); TOTP_PICKUP and KEY_ROTATED both chain. The window
  exists only while an admin-initiated, chained re-enrollment is
  pending, and a pickup the holder did not perform is detectable the
  moment the holder tries (their key is dead) plus in the chain.
  The alternatives reintroduce worse shapes (confirmer-held secrets —
  Security Round 1 F11). Ratified.
- **R-E (throughput cost) — RATIFIED.** Arithmetic against CPD's own
  reported volume: 44,420 reads/day ≈ 0.51 appends/s average demand
  (matches add ~3.8/day, negligible). 1.2.5's measured append rate is
  ~17–19/s (S12 record) — ≈33× headroom on the average. A full day's
  reads compressed into a single hour (a 24× burst) is ≈12.3/s, still
  under the idle append rate; the load-envelope leg landed 500/500 at
  every burner level through 6 burners, which is the completeness
  guarantee that matters for alerts. The cost is real (sink
  verification per append) and worth paying at this volume. Revisit
  only if camera count or per-camera volume grows by an order of
  magnitude.
- **R-F (seat-file adaptations) — RATIFIED practice, diffs verified.**
  I diffed both adapted files against janus124 myself:
  `tests/attacks/round4/attack2.py` changes ONLY the signing key's
  location (escrow directory instead of inside the backup set) plus a
  disclosure comment — the scenario and its assertion (a validly
  re-signed tar-slip set is refused before the live DB moves) are
  untouched. `tests/attacks/round6/f11_restore_trust.py` changes ONLY
  the two `os.remove` calls into existence-guarded removes plus a
  disclosure comment — assertions untouched. One honest nuance: under
  T8 the f11 strip is now a no-op (backup sets never contain key
  material), so that leg's premise is vacuous; the coverage moved
  rather than vanished — restore trust-root pinning is exercised by
  T8's escrow case and the builders' backup/restore suite. Standing
  condition for the practice: when an adaptation vacates a scenario's
  premise, the replacement coverage must be named in the same commit
  — here it is. Ratified.

## 3. Judgment calls

- **(a) Ceremony state vs refuse-to-serve — ACCEPT the ceremony
  state.** P-A's evidence: the state is health-red, named
  ("provisioning", store_state "missing", every unenrolled human
  listed), and it is the only key-only window in the design. Refusing
  to serve a fresh install at all would brick the provisioning flow's
  own first boot and every demo/eval install for a marginal gain: the
  ceremony state already cannot be mistaken for a healthy install by
  anyone reading /health or alert_check.
- **(b) Fence line — ACCEPT.** Unanimous in Round 7 and now executed
  end-to-end (H4): data reads and data writes fence at 503, safety
  writes proceed chained, recovery surfaces stay open. The line is
  where I would have drawn it.
- **(c) T7 vs R9 out-rank reconciliation — ACCEPT.** Equal-rank plate
  changes refuse and chain READ_PLATE_CHANGE_REFUSED; strict
  (phase, confidence) out-rank still corrects and READ_SUPERSEDED names
  the withdrawn hits. The alternative (any different-plate redelivery
  withdraws) reopens the retroactive-withdrawal shape Security Round 1
  found in 1.2.4. The refused delivery is correctly NOT stored as a
  reads version (a stored row would win currency by the arrival
  tie-break).
- **(d) Escrow split vs script-side encryption — ACCEPT the split for
  the pilot, with the custody caveat stated.** The split's value is
  separation of custody; restore.py's fingerprint pinning enforces the
  escrow's integrity. The honest residue: a backup set and its escrow
  stored in the same place defeat the split — that is a procedure
  requirement (escrow stored separately), not a code defect, and
  TRACK-125 §3.6 documents it. Script-side encryption would add a
  passphrase-custody problem of the same shape. Accept.
- **(e) Absence-proof for the sink-status-exception branch — REJECT as
  sufficient.** sentinel.py is importable and the branch is a named
  health input; a fault-injection case (monkeypatch `sink_status` to
  raise in a test boot, assert the named degradation) is cheap to
  write and is the same standard this council applied to claimed-
  impossible branches in Round 7. "Covered by inspection" is how the
  T7 hotlist case happened. Require the case in the next build; it is
  a small item and not, by itself, my forced change.
- **(f) Demo mode as degradation — NOT sufficient alone for
  deployment.** The env-only gate plus health naming is right for the
  code loop, but a single environment variable on a production host is
  one config accident away from waived 2FA + multi-role god accounts
  on a network socket, detected only after the fact. Before any pilot:
  demo mode should also refuse a non-localhost bind (or require a
  second, explicit env opt-in to bind externally). I do not block
  convergence on this — demo mode is operator-enabled, not
  attacker-reachable — but it belongs on the pilot gate list next to
  the pen-test clause.

## 4. Verdict against the convergence criteria

- **Criterion 1 (no surviving deployment-blocking/critical code
  finding): FAIL.** F-1 stands executed and unrebutted: an
  unauthenticated peer can hold the ingest identity locked with five
  requests per 900 s, indefinitely. Nothing else I found is above
  Medium, and the entire Security Round 1 fail-closed spine (T1, T3,
  T5, T6) survived direct attack — but F-1 alone is a renewable
  off-switch for the alert path, which is deployment-blocking for a
  system whose purpose is alerting.
- **Criterion 2 (every forced change implemented or answered in
  writing): FAIL.** T7's /hotlist item was a forced change out of
  Security Round 1. It is implemented in a form that does not achieve
  its stated invariant, and its acceptance case asserts an equivalence
  it never tests (F-2). The remaining T items I re-tested (T1, T3, T8,
  T9) are implemented as commissioned.
- **Criterion 3 (what remains is documented limitation or routed legal
  questions): FAIL, narrowly.** R-A, R-C, R-D, R-E, R-F are documented
  and, on my execution, accurately so — those are legitimate
  limitations. R-B remains, and its documentation misdescribes the
  mechanism; an inaccurately documented limitation is not a documented
  limitation. The Ben/ACIC legal lanes are untouched by anything I
  found.
- **Criterion 4 (orchestrator's re-tests pass): PASS** (pre-satisfied
  per the brief; my targeted probes are consistent with the cold
  battery's results everywhere except F-2, where the battery's own
  case is the weak-shaped one).

**Overall: NOT CONVERGED.**

## 5. The single forced change

**Unauthenticated wrong-key attempts must not be able to lock a
machine identity.** Exempt the `ingest` and `jobs` identities from the
T2 account lockout (their failures keep chaining and keep counting in
/health, so the spray stays visible), or adopt any equivalent design
in which a key-only machine identity cannot be locked by someone who
does not hold its key. Human accounts keep the lockout exactly as
built — OPERATIONS.md §10's promise is finally true for them in
1.2.5, and this change does not touch that. Acceptance: a
discriminating case in the T battery's shape — five wrong-key attempts
against the ingest identity, then the correct key must still ingest
(201) — failing on 1.2.5, passing on the next build.

For the record, completing convergence also requires finishing the
existing T7 item honestly (F-2): make the non-supervisor /hotlist
response for a protected plate genuinely indistinguishable from the
response for an addable plate — the cleanest shape is to let the add
succeed identically for every plate and let protection keep being
enforced at match time, where it already lives — and replace
`t7_hotlist_oracle` with a case that probes protected, unknown, and
unprotected plates and asserts the responses match. That is criterion
2 bookkeeping on a change already commissioned, not a second forced
change.

If both land and re-verify, my vote flips: nothing else in this build
is holding it.

---

## Appendix — where execution contradicted the builder's report

One place, and it matters: **R-B's mechanism.** TRACK-125-REPORT §5
describes the /hotlist residue as a 201-vs-404 distinction against
"protected-or-unknown". Execution shows an unknown plate returns 201
(adds fine), so 404 does not conflate protected with unknown — it
identifies protected, uniquely, among the five shapes probed. The
builder's other residuals (R-A, R-C, R-D) reproduced *exactly* as
documented, including their mitigations; the escrow/ seat-file
disclosures (R-F) verified by diff; the restore-flip refinement and
the T7/R9 reconciliation behave as reported. The builder's honest-flag
practice remains the most reliable in this loop — which is precisely
why the one place the report's wording outran the code deserves
naming: the T7 case's docstring repeated the intention as if it were
the result, and the battery's green count inherited the claim.
