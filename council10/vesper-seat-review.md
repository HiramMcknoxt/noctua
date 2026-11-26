# Council Round 10 — Vesper executing seat review

**Seat:** Vesper executing seat, cold local run (Muse Spark,
orchestrator's own session — no pack, works from the tree).
**Subject:** NOCTUA 1.2.7 (`janus127/`). **Date:** Nov 26, 2026.
**Charge:** brief §3.1 (confirm/reopen V1–V18), §3.2 (G1–G5),
§3.3 (11 judgment calls), §3.4 (ceremony-state attack), vote on
criteria 1–4 only.

**Tree identity, verified at seat start and again at seat end:**
janus127 janus.py `3161d9d968e696c4ae001e0eea61f47e`,
sentinel.py `1fc7875056a38e6e04f410cf18b0dbef`; janus126
janus.py `9e39e0414cf4b782eb93aaf05573e8bc`, sentinel.py
`dca5d958da4c8e4e7be775eaae092c7f` — all four identical before
and after every run below. No code or test file was edited by
this seat; no git operations.

**Runs (all from clean scratch under
`council10/seatwork-vesper/scratch/`, TMPDIR pointed there):**

- `./run-next.sh` step 1: V battery against janus127 —
  **19/19 cases PASS**, exit 0 (log `v127-20261126-154516.log`).
- Step 2: the same battery with janus126 as test tree —
  **0/19 pass**, exit 1 (log `disc-20261126-154516.log`).
  Discrimination independently re-confirmed in this seat.
- Seat probes (`probes.py`, seven probes aimed at the
  ADJACENT shapes of the fixes, per the brief's Round 9
  lesson): P1–P3 executed three times each with identical
  results (the runner's step-3 pass, my standalone passes, and
  one clean full pass, log `probes-clean-20261126-155129.log`);
  P4/P5/P7 twice each. **Disclosure:** the runner's step-3
  pass died inside P4 when it raced my own concurrent manual
  P4 run on the same fixture directory (the LAB refusal fired
  on the first boot, correctly, against the other run's
  provisioned install). The clean full pass that followed —
  nothing else running — is the probe record of reference, and
  every probe detail below appears in it.

## §3.1 — V1–V18: all CONFIRMED FIXED

Each item below was confirmed by the V-battery case of the
same name in my fresh 19/19 run (every case also fails on
janus126 in my discrimination run), plus the item-specific
evidence named.

- **V1 (blocker) — CONFIRMED.** Case: 6-shot wrong-key pickup
  spray → target still authenticates (200); a genuinely locked
  account's pickup refusal is the uniform "authentication
  failed". Adjacent shape (probe P3): a 6-shot wrong-key spray
  against a NONEXISTENT username creates no lock state — the
  name never appears in /health's locked_accounts. The
  predicate's placement inside `_auth_lock_note_failure`
  (janus.py:3196) was read firsthand by the verification seat.
- **V2 (blocker) — CONFIRMED.** Case: a detective's submission
  against a supervisor's live row leaves the row byte-identical
  (category/added_by unchanged), the answer stays the uniform
  202, and the live plate still matches on ingest.
- **V3 (blocker) — CONFIRMED.** Case: with entries 4–5 welded
  and entry 10 torn, entries 6–9 survive in the sink file,
  sink_status is not-ok, and seqs 4, 5, 10 are named diverged
  (1.2.6 truncated at the weld and deleted the valid tail).
- **V4 (high) — CONFIRMED.** Case + my §3.4 attack below.
- **V5 (high) — CONFIRMED.** Cases v5 (deleting the disagreeing
  line no longer lifts the fence; two-key accept clears it;
  file-state fences still auto-clear on repair) and v5b
  (chain.append forced to raise → neither clear nor set lands).
  Adjacent shape by code read: `_anchor_apply` auto-clears a
  disagreement only when `bad_ids ⊆ _accepted_checkpoint_ids()`
  — a PARTIAL acceptance leaves the subset test false and the
  fence stands; a disagreement with no recorded bad_ids also
  stands. The partial-acceptance shape is closed by
  construction.
- **V6 (medium) — CONFIRMED.** Case (corrupt outgoing DB →
  marker records "unknown", key-only auth refuses,
  must_reenroll ≥ 1) + code read of restore.py:435–452 (the
  tri-state: "never" default, "provisioned" on a positive read,
  exception → "unknown").
- **V7 (medium) — CONFIRMED.** Case: all five pre-restore
  artifacts (DB, -wal, -shm, both key snapshots) prune under
  the one glob.
- **V8 (medium) — CONFIRMED.** Case: 50,000 sprayed usernames
  leave ≤ 65 totals entries with the configured account's count
  exact; 5,000 seeded stale flushed markers swept by the next
  failure. Pruning read firsthand at janus.py:3023.
- **V9 (medium) — CONFIRMED.** Case: both releases are out of
  ANCHOR_FENCE_SAFETY_POST, and under a fence a supervisor's
  hold release is refused 503 at dispatch.
- **V10 (medium) — CONFIRMED.** Case: refused verify and
  refused (suppressed) export chain BLOCKED payloads carrying
  `href:` keyed refs and no raw `hit` key.
- **V11 (low-med) — CONFIRMED.** Case: an aged pickup deletes
  the store entry (secret included) and chains PICKUP_EXPIRED;
  six no-code attempts against a must_reenroll entry and a
  corrupt-store sequence lock nobody.
- **V12 (low) — CONFIRMED.** Case: an os.replace spy sees three
  distinct temp paths from provision.py save(); the fixed
  `USERS_PATH + ".tmp"` rotation string is gone from janus.py.
  The janus half's source-pattern basis is the builder's
  disclosed judgment call 8, ratified below.
- **V13 (low) — CONFIRMED.** Case: the three detective refusals
  (nonexistent / suppressed / unverified) are byte-identical;
  the supervisor's suppressed answer stays distinct.
- **V14 (no code) — CONFIRMED as answered.** The probe, the
  marker, and `_unprovisioned_locked` survive only in comments
  naming their retirement (asserted by the v14 case); a legacy
  unprovisioned database lands in the ceremony state and
  enrolls through the same bootstrap path (see §3.4).
- **V15 (smalls) — CONFIRMED.** The bundled case passes all
  sub-shapes (collision-proof archive names, capped stranded
  lists at 50 + count + hash, 30-day pending expiry with
  approve-refuses-404, escrow pairing, checkpoint.py non-object
  tail, sentinel_audit "1.2.7"). The docs item I verified
  directly: the enroll-2fa CANT-DO entry exists at
  `docs/CANT-DO.md:25`, in the terms §5(vi) required.
- **V16 (high) — CONFIRMED.** Case (never-delivered unreadable
  sink strands seqs 1–5, ceremony reachable) + adjacent shape
  executed (probe P7): with 3 entries DELIVERED and the sink
  then corrupted, 2 further appends commit and
  `sink_divergence()` strands all 5 committed seqs
  (tail_seq 3, file_seq 0). The fix is not confined to the
  commissioned shape. (One probe-harness note: my first clean-
  pass P7 reused a dirty unit DB and stranded 10/10 committed
  seqs — the invariant held there too; the probe now uses a
  fresh directory per run.)
- **V17 (high) — CONFIRMED.** Case is behavioral: with a
  persisted lock row and a pending unlock marker, `_auth_locked`
  returns False, pops memory, and the row is STILL THERE.
- **V18 (medium-high) — CONFIRMED.** Case: distinct per-side
  env secrets produce different, correct codes per side and the
  machine-role receipt post carries no TOTP header. The legacy
  fallback is judgment call 11, ratified below with a note.

## §3.2 — The queued Gemini items

- **G1 (F3 ext. a) — VERIFIED. The defect is present in
  1.2.7, executed (probe P1, three identical runs).** A
  supervisor lists a plate (201); the listing is deactivated
  (the sync sweep's exact end state, active=0); a detective
  resubmits the same plate/case: the answer is the uniform
  **202**, the pending queue is **empty**, the row is unchanged
  (pending=0, active=0, added_by still the supervisor) — and
  HOTLIST_ADD_PENDING is chained anyway. The V2 guard
  (`WHERE pending=1`) makes the conflict a no-op against ANY
  pending=0 row, live or inactive; against an inactive row the
  submission therefore vanishes silently while the chain
  asserts a pending add that never materialized. Severity:
  HIGH operational / audit-accuracy — a resubmitted warrant or
  stolen-vehicle plate can be lost with no human ever seeing
  it, and the chain overstates the queue. It is NOT, in my
  ruling, deployment-blocking or critical under §3.5 and the
  register's own ladder: no security boundary is crossed, no
  live data is altered (the V2 blocker shape stays dead), the
  failure is confined to the previously-listed-then-deactivated
  shape, and a supervisor direct-add is a working path around
  it. **Register item #1: fix before any pilot** (on conflict
  with an inactive row, insert/reactivate as a fresh pending
  row; do not chain ADD_PENDING for a no-op). The chair should
  weigh this ruling explicitly — it is the closest call in my
  review.
- **G2 (F3 ext. b) — VERIFIED IN REDUCED SHAPE (probe P2).**
  Pending rows are stored active=1, so hotlist_sync's sweep
  (active=1, expiry past, NO pending predicate) deactivates a
  pending row and chains **HOTLIST_EXPIRED for an entry that
  was never live** — an audit mislabel, executed. The queue
  (pending=1 only) still lists the swept row, and a supervisor
  can approve it (200) into active=1 with a long-past expiry —
  but the read path refuses expired entries: **0 hits on
  ingest, executed**, so the resurrection is inert and the next
  sweep re-deactivates it. The "evades the retention purge"
  half is **mooted**: retention never governed hot-list rows,
  and V15's 30-day HOTLIST_PENDING_EXPIRED expiry now bounds
  pending rows on the submission/queue/decide paths.
  Register, LOW-MED (chain mislabel + queue hygiene; the sync
  sweep should skip pending rows, and the decide path should
  refuse an entry whose expiry has passed).
- **G3 (F7's other half) — VERIFIED, bounded (probe P3).**
  `_totp_pickup` never calls `_reload_config()` — every auth()
  request reloads (janus.py:3459), pickup is the one USERS
  consumer that doesn't. Executed: with a pending pickup
  minted, the account was disabled ON DISK (provision.py
  disable's exact write) while the server ran; the pickup then
  completed against stale memory — **200, the pending TOTP
  secret and recovery codes revealed, a new API key issued**.
  The bound, also executed: the new key then authenticates
  NOWHERE (401 — auth() reloads and sees the disable), and the
  rotation preserved the disabled flag in the file. What leaks
  is the secret disclosure itself, inside a 24h pickup window,
  to whoever holds the old key + the out-of-band token. One-line
  fix (reload at pickup entry, auth() parity). Register,
  LOW-MED.
- **G4 (F9's trap) — VERIFIED as a latent trap (code read).**
  rotation.py:228 and :277 still gate on the prefix list
  ("1.2.2".."1.2.5"), and build_schedule still stamps new
  schedules "1.2.5" — so today's schedules verify, and nothing
  in V15 extended the list. The trap springs only when the
  stamp is next bumped: a "1.2.6"+ document falls into the
  legacy branch and verification fails CLOSED (MISMATCH, exit
  2). No false-accept path exists — a 1.2.3+ signature covers
  portions the legacy branch never recomputes. Register, LOW
  (fix with the next schedule-format change: derive the gate
  from the document's own declared portion rules, or extend
  the list in the same commit that bumps the stamp).
- **G5 (F10 bundle) — ruled per item.**
  (i) backup.py reverse nesting — **VERIFIED still open.**
  U10 refuses escrow-inside-backup (backup.py:171–181 tests
  only `_esc_real` within `_root_real`); backup-inside-escrow
  is not refused, so an operator can still reunite the custody
  split under the escrow tree in the mirror direction.
  Register, LOW.
  (ii) enroll_2fa disabled parity — **VERIFIED still open.**
  provision.py's enroll_2fa contains no disabled check
  ("disabled" appears in provision.py only in the
  disable/enable/list commands), while the Janus side checks
  it (U11(a)). Enrolling a disabled account is inert — auth
  refuses disabled accounts before any factor — but the parity
  break is real. Register, LOW.
  (iii) config_closed vs anchor-accept — **REFUTED.**
  /audit/anchor-accept is exempt from config_closed at
  dispatch (janus.py:4595) and its handler (janus.py:4733)
  routes directly to `_anchor_accept` with no config_closed
  call; the recovery action stays reachable on a stale config.
  The config_closed at janus.py:8263 is `_share_query`, a
  disclosure surface, correctly closed.
  (iv) restore.py outgoing fallback — **CLOSED by V6**,
  confirmed (tri-state at restore.py:435–452 + the v6 case).
  (v) `_auth_fail_flushed` unpruned — **CLOSED by V8**,
  confirmed (pruning at janus.py:3023 + the v8 case).

## §3.3 — The builder's 11 judgment calls

1. **V4 fence set extension — RATIFY.** The added surfaces are
   plate-data surfaces of the same kind as the commissioned
   list; fencing search while leaving hotlist reads open would
   be incoherent. The surfaces left open check out under
   attack (§3.4): /lists returns registry names only, /stats
   aggregate counts only, /audit* is the ceremony's own
   evidence. Binding key-only human roles only matches the
   Round 9 threat; machine roles are not the exfiltration
   path and ingest must run.
2. **LAB named in /health, not in ok_all — RATIFY.** The
   totp state already holds health down when unprovisioned;
   adding a boot-time flag to ok_all would flap health on a
   lab that provisions mid-run (probe P4 shows that lifecycle
   is real). Disclosure without double-gating is the honest
   middle the builder claims.
3. **S10 gating via NOCTUA_BATTERY_CONTEXT=full — RATIFY.**
   It implements §5's exact distinction (full battery vs
   standalone) with the mechanism in the open. Two independent
   25/25 full-battery passes now exist — one exercising the
   retry, one not needing it (verification record, note 2).
4. **Load health availability as measurement, not gate —
   RATIFY.** The quantity is nondeterministic on a shared VM:
   the builder measured {20 samples, 18 answered, 4 wrong
   values}, the verifier {20, 20, 0}. Gating on it would
   manufacture the very flake §5 removed from S10. The gated
   property behind it (append completeness, 500/500 at every
   burner level, both directions) is deterministic and held
   in both runs.
5. **V10 extended beyond the letter — RATIFY.** One principle
   (a BLOCKED payload must not hand the blocked actor a raw id
   joinable to the alert) applied consistently; custody
   entries keep raw ids for the key holder, which is the
   correct line — the leak was payloads reaching the actor,
   not the chain's internal joins.
6. **V13 supervisor carve-out — RATIFY.** Implemented exactly
   as the commission's text specified; supervisors are the
   deciding role and need the reason, and the uniformity binds
   the roles that could probe with it.
7. **V15 stranded bound (accept response keeps the full list)
   — RATIFY.** The commission named the chain payload and
   /health; both are capped (v15 case). The accept response
   goes to the operator working the divergence, who needs the
   full list to work it.
8. **V12 janus half as source-pattern assertion — RATIFY,**
   with the disclosure noted as the right way to flag it. The
   rotation's functional behavior is covered by the v1/v11/u7
   pickup cases; the torn-write race itself needs fault
   injection into the server process, and the shipped pattern
   (unique temp + os.replace) is the same one the TOTP store
   proves behaviorally.
9. **V8 flushed-pruning seeded markers — RATIFY.** The code
   path exercised is the production one (janus.py:3023);
   organic growth would need failures spread across real
   minute-buckets inside a test run. Seeding state to reach a
   production path is standard practice, and the path is
   unmodified.
10. **V6 missing-field → "unknown" → provisioned — RATIFY.**
    Fail-closed is the only defensible reading of a restore
    marker that cannot prove the outgoing install was never
    provisioned. The alternative (absent → "never") would let
    a hand-written or pre-1.2.6 marker waive re-enrollment —
    the fail-open shape 1.2.5's T1 exists to kill. The LAB-
    refusal interaction the builder flags is correct operator
    behavior, and probe P4's lifecycle is consistent with it.
11. **V18 legacy TOTP fallback — RATIFY, with a register
    note.** Dropping the fallback would break every existing
    single-secret Compact job at upgrade; an operator who sets
    only the legacy variable has configured the shared shape
    deliberately, and the per-side path is there. Register
    note for the post-convergence docs pass: INSTALL/COMPACT
    should steer NEW deployments to per-side secrets and name
    the legacy variable as legacy.

## §3.4 — Ceremony state: attacked, held

The §4 reopening condition was the target: an executed blocker
in the redesign reopens the U9 adjudication. I attacked on
five fronts; none produced one.

- **Copied-database arrival (v4 case, my run):** a born-empty
  install's copied DB serves 503 on the new host; ingest stays
  open (201); the same install under LAB serves; LAB on a
  provisioned install refuses the boot (rc 3).
- **LAB lifecycle, provision-while-LAB (probe P4, executed):**
  booted LAB on an unprovisioned install (health: state "lab",
  lab_mode true) → enrolled and ACTIVATED a human under LAB →
  the install became provisioned mid-run → reboot of the same
  directory with LAB still set **refused, rc 3** → reboot
  without the LAB posture served, and /hits answered 401 to a
  replayed (consumed) activation code — normal TOTP semantics,
  NOT the 503 fence: the fence lifts on provisioning, exactly
  as designed.
- **Restore landing on a LAB host:** not run as a literal
  restore.py cycle; it reduces to the single provisioning test
  both paths feed (`_totp_provisioned()`), and P4 executes
  that test's consequence (a provisioned install + LAB = boot
  refusal). A restored UNPROVISIONED database lands in
  ceremony by the same test. Stated as construction, not
  execution.
- **Side doors (probe P5, executed, true ceremony state, no
  LAB):** GET /hits 503; GET /search 503 (POST /search is not
  a route — 404, a non-event); DELETE /hotlist 503; ingest
  201 (open by design); /stats 200 with aggregate counts only
  (reads, hits, pending, chain entries — no plate data);
  /lists 200 with registry names only; /health names the
  ceremony state and the unenrolled human usernames — account
  identifiers on the operator's own status surface, the
  ceremony's enrollment watch-list by design, not plate data.
- **Error-shape / ordering:** an UNAUTHENTICATED request to a
  fenced surface gets 401, not 503 — authentication precedes
  the fence check in all three dispatchers, so the ceremony
  state is not an oracle for callers without keys. Fenced
  refusals are a uniform 503 with a throttled CEREMONY_REFUSED
  chain entry.

**The ceremony redesign produces no executed blocker in this
seat. The U9 adjudication stands unreopened.**

## Register (lesser findings — post-convergence triage)

1. **G1** (HIGH, fix before pilot): submission against an
   inactive row silently drops while HOTLIST_ADD_PENDING is
   chained. §3.2.
2. **G2 residue** (LOW-MED): hotlist_sync sweeps pending rows
   and chains HOTLIST_EXPIRED for never-live entries; the
   decide path accepts an entry whose expiry has passed
   (inert — the read path refuses expired entries).
3. **G3** (LOW-MED): `_totp_pickup` never reloads config; a
   disk-disabled account's pending pickup completes and
   reveals its secret (the issued key cannot authenticate).
4. **G4** (LOW): rotation.py --verify's version-prefix list
   ends at "1.2.5"; fails closed when the stamp is bumped.
5. **G5(i)** (LOW): backup.py does not refuse out_root inside
   escrow_root (the mirror of U10's shipped direction).
6. **G5(ii)** (LOW): provision.py enroll_2fa has no disabled
   check (Janus-side parity break; inert while disabled).
7. **Docs note** (from call 11): steer new Compact deployments
   to per-side TOTP secrets in INSTALL/COMPACT at the
   post-convergence docs pass.

No new deployment-blocking or critical finding was found by
this seat.

## Convergence criteria — scored

1. **No surviving deployment-blocking/critical code finding —
   PASS.** All three Round 9 blockers and both addendum highs
   (V16, V17) are executed dead in this seat, with
   discrimination. My one HIGH finding (G1) is ruled
   non-blocking with the reasoning stated in §3.2 for the
   chair to weigh.
2. **Every forced change implemented or answered in writing —
   PASS.** V1–V18 implemented (V14 answered in writing, by
   design); the §5 conditions (S10 shape, R-F as amended)
   implemented and re-verified.
3. **Remainder is CANT-DO or routed legal questions — PASS.**
   What remains from this seat is the register above — code
   items triageable after convergence, none of them legal or
   administrative questions wearing a code costume.
4. **Orchestrator's re-tests pass — ACCEPT, and independently
   corroborated.** The verification record's one-shot full
   battery stands; this seat re-ran the V battery (19/19) and
   its discrimination (0/19) cold, and executed seven
   additional adjacent-shape probes.

## Vote: **CONVERGED**

**Single forced change:** none.

*VESPER · the evening watch — executing seat, for Corey
Spangler, Cabot, Arkansas.*
