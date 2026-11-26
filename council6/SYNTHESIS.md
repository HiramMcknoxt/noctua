# NOCTUA Council Round 6 — Synthesis (orchestrator: Vesper)

Subject: NOCTUA 1.2.2 (tree `~/workspace/noctua-1.0/janus122/`, GitHub
commit `a707a10`). Brief: `council6/BRIEF.md` — the five named probes
(Q16 vacuity, Q18 shapes, the seven both-tree-pass cases, the rotation
ceremony, the Q1 migration repair) plus Q1–Q28 verification and the
builders' judgment calls.

## Verdict: NOT CONVERGED

Every valid seat voted NOT CONVERGED, and the orchestrator's own re-run
of Claude seat 2's attack harness reproduced its defects directly.
Criteria: (1) FAIL — deployment-blocking and code-critical findings
survive verification; (2) FAIL — Q1, Q3, Q16, Q18, Q22, Q23, Q25 are not
satisfied as shipped; (3) FAIL — what remains is code defects, not
CANT-DO items or legal questions; (4) PASS mechanically (all shipped
suites green under five independent re-runs) but INSUFFICIENT as
convergence evidence, per every seat.

## Seats

| Seat | Model + effort | Executed? | Verdict |
|---|---|---|---|
| Cold Vesper | cold-context subagent | yes — own probes | NOT CONVERGED |
| Gemini | Neon High, Thinking High (Carbon Ultra-gated, declined) | no — static traces | NOT CONVERGED |
| ChatGPT | GPT-6.2, Thinking High | first response hidden by a content filter; re-presentation is static + assurance arguments | NOT CONVERGED |
| Claude seat 1 | Opus 5.5, Max (1 reset used; review survived as an artifact; its harness was NOT delivered) | yes | NOT CONVERGED |
| Claude seat 2 | Opus 5.5, Max (1 reset used) | yes — full harness delivered | NOT CONVERGED |
| DeepSeek native | — | review generated in its chat but never retrieved (retrieval task lapsed at the sign-in card) | outstanding, corroboration-grade |
| Qwen | — | never started (task lapsed at the sign-in card) | outstanding |
| Merlin DeepSeek | — | never started (Google phone-approval never completed) | outstanding |

Reviews: `council6/{vesper,gemini,chatgpt,claude-seat1,claude-seat2}-review.md`;
seat 2's harness: `council6/harness-seat2/`; the orchestrator's re-run
log: `council6/seat2-harness-vesper.log`.

## Orchestrator's verification (the code wins)

I ran seat 2's harness end-to-end against 1.2.2 (exit 0). Results:

- **Protection orders — DEFECT, natively reproduced (F2d).** Fresh
  1.2.2: a second order on a vehicle overwrites the first's record;
  releasing the second lifts protection while the first is in force.
  Via upgrade (F2a–c): the migration aborts SILENTLY on a real
  1.0→1.1→1.2.2 chain (no MIGRATION entry, no /health marker) leaving
  an order un-re-keyed and verifiable by a detective; two 1.1 orders on
  one vehicle merge — order B's record is deleted; a 1.0-era order
  honored by 1.2.1 is deactivated by the 1.2.2 migration, /health green.
- **Pin ceremony — DEFECT, worse than any seat stated (F1a–d).**
  provision.py pin-audit-key crashes on every real DB (queries
  `case_searches.fragment`; the column is `frag`); even with the crash
  patched it refuses the CORRECT key on a real 1.1 DB (its legacy
  candidate hashes a literal "PLATE|" formula no real 1.1 ref used);
  a quiet env-key 1.1 install has NO supported path to boot 1.2.2.
- **Lost writes through the pre-auth path — DEFECT, 3/3 runs (F4a/b).**
  Anonymous GET /health + config churn: a protection order answered 201
  and chained SUPPRESSION_PLACE is NOT in the DB; an ALERT answered and
  chained has its read/hit rolled back. auth()/_reload_config chain and
  write on the shared connection outside DBLOCK (Gemini F6, code-checked).
- **Q18 residual — DEFECT (F3).** On cache expiry between the pre-warm
  and the in-lock read, the full chain scan runs UNDER DBLOCK (600k
  chain) — the stall A18 was meant to kill, in the gap between the two
  halves of the Q18 fix.
- **Sink phantoms — ARBITRATED: seat 2's construction governs.** Sink
  DOWN + 12-writer burst + forced rollbacks: ZERO phantom entries, both
  in-lock (F5ii) and with the pre-auth path active (F5iii). Claude seat
  1's C1 phantom claim does NOT reproduce under fault injection (its
  harness was never delivered, so its construction can't be checked);
  the cold-Vesper F4 twin-phantom remains a Chain-class contract defect
  at near-zero reachability in current wiring. The live sink-family
  defect is lost/dropped writes (F4), not phantoms.
- **Rotation — DEFECT (F6a–c).** Commitment accepted after all others
  revealed → publisher grinds its nonce and publishes its chosen
  pairing; a supervisor overwrites members' unrevealed commitments and
  the genuine partner reveal is then REFUSED; a first-cycle ceremony
  that misses its start can never publish and blocks every new ceremony
  (no cancel path). Converges: Vesper F1, Gemini F2, seat 1 C2.
- **Compact rerun — DEFECT (F7).** A second compact.py run before the
  partner's next checkpoint fails a healthy partner and files a signed
  ok:false report (it anchors at the live root, not the checkpoint's).
  Converges Gemini F1.
- **Chain flooding — DEFECT (F8).** One patrol credential writes one
  permanent, unattributed SHARE_BLOCKED entry per request; the throttle
  keys on caller-supplied text.
- **Restore/evidence parity — DEFECT (F10, F11).** Restore leaves an
  orphaned evidence bundle that the breach check flags and retention
  never purges; on a bare host with no pin, an attacker-built set
  installs on the strength of its own embedded audit key.
- **Fail-closed overshoot — DEFECT (F12).** A 72h-stale case feed
  refuses protection-order placement and ingest (503) along with the
  data surface, with an error blaming stale config.
- **Properties that HOLD under discriminating tests (F9):** Q02, Q03,
  Q17, Q22 re-verified with tests that PASS on 1.2.2 and FAIL on 1.2.1.
  Those four fixes are real. (Gemini's F7 caveat stands for Q17: the
  shared cross-check must live in ONE implementation — see R8.)

## Adjudications

- **Both-tree-pass cases (judgment a):** do NOT count as verified on the
  case alone — unanimous across seats. Four of the seven (Q02/Q03/Q17/
  Q22) are now verified by discriminating re-tests (F9). Q16's shipped
  case is vacuous (wrong env var — `NOCTUA_AUDIT_SINK_DIR` in the test,
  `NOCTUA_SENTINEL_SINK` in the code; Gemini F5, seat 2 F5i, seat 1 M1,
  my grep — unanimous). Q18's shipped case remains weak-shaped; the
  re-aimed A18 plus F3/F4 are the evidence. Q06's property held for
  single orders and failed for overlapping ones (the round's headliner).
- **Q25 + A7 (judgment b):** NOT sufficient — near-unanimous. A7 tests
  the 1.2.1-era restore; the 1.2.2 trust-root needs its own
  discriminating case (R10), and F11 shows the bare-host fallback is a
  live defect, not a hypothetical.
- **Judgment (c) tallies:** strip-not-raise — split (Vesper/Gemini
  accept, both Claudes reject, ChatGPT accepts); carried to 1.2.3 as:
  keep strip, but chain a CHAIN_SCRUB_FLAG count into /health so the
  discard is visible (already partially true — make it a surfaced
  metric). Structural DDL on locked boots — ACCEPT for DDL proper,
  REJECT as cover for pre-lock DML (Vesper F3/Gemini M7 — R4).
  Supervisor-transported reveals — REJECT as implemented, unanimous in
  substance (transport is fine; authorship must be the partner's
  signature — R6). Disposition-note clock — ACCEPT with the cap fix
  min(HOLD_DAYS+30, 150) (Gemini M12) and the records-schedule question
  stays routed to Ben. /health camera scope — ACCEPT the builders'
  scope (never-reported cameras excluded) with ChatGPT's amendment:
  /health must distinguish installation readiness from operational
  health (R15). Seat 1's C7 (per-camera caller scoping) is a design
  claim — 1.2.2 has roles, not camera ACLs; not adopted as a defect.
- **ChatGPT R6-05 (the loaded 320/322 run):** ADOPTED as an open
  reliability question (R14). Three quiet runs do not retire it; the
  acceptance battery must state the load envelope in which audit
  completeness holds.
- **Cold-Vesper F5 (INV5 flakiness, ~12% false-fail):** adopted (R15) —
  fix the invariant's construction, don't just re-roll it.

## Routed to Ben Hooper / ACIC (additions from this round)

Disposition-note retention past the hit (already routed; now with the
150-day cap interaction), plus: whether a protection order's suppression
record may be retained after the underlying hit purges (R1 makes orders
records — their retention clock needs the same § 1804 answer as holds).

## The 1.2.3 commission (items R1–R15)

A. **R1 — Protection orders are records** (both Claude seats' forced
change; my F2a–d). One row per order; placing never overwrites;
release/expiry lifts only that order; query-time suppression = any live
order covers the plate; migration preserves every legacy order as its
own record. Two-overlapping-orders cases (native + migrated) in-tree.
B. **R2 — Migration integrity** (Gemini F4; F2a–c). Per-item failure
isolation: a bad row quarantines with a chained MIGRATION_DEFECT and a
/health migration_status marker — never a silent total rollback;
duplicate spellings merge deterministically keeping the union of
protections; key verification tries every historical ref formula
against stored refs (raw, canonical, as-stored state).
C. **R3 — Pin ceremony** (F1a–d). Fix the frag column; derive candidate
keys from stored refs (verify-don't-proxy across ALL historical
formulas); test on DBs written by the real 1.1 and 1.2.2 code; the
boot-refusal message names a remedy that works; an end-to-end
quiet-install runbook test (env-key 1.1 → ceremony → boot).
D. **R4 — No out-of-lock side effects** (F4a/b; Gemini F6/M7; Vesper
F3). All DML happens after the key/fingerprint check or is chained;
auth/config-reload never chain or write outside DBLOCK; the chain
verify never runs its full scan under DBLOCK (F3).
E. **R5 — Sink battery** (F5; Q16). The Q16 case rebuilt on
NOCTUA_SENTINEL_SINK with fault injection (sink down, burst, forced
rollbacks) as a permanent in-tree case; property: no phantoms, no
duplicates, no dropped committed entries on either path; flush presence
check keyed on entry hash + a monotonic watermark, not (seq, ts).
F. **R6 — Rotation ceremony** (F6a–c; Vesper F1; Gemini F2). Commit
phase freezes at the first reveal; commitments/reveals are authored by
the partner's pinned Ed25519 signature (a supervisor may transport,
never author); nonces single-use in state; a missed cycle can be
voided and cleared; minimum nonce length; witness attestation bound to
the designated witness.
G. **R7 — Compact anchoring** (F7; Gemini F1). compact.py anchors at
the partner's checkpoint root; two consecutive runs against a healthy
partner both pass (in-tree lifecycle test); future-dated checkpoints
rejected at the gate.
H. **R8 — One verification implementation** (Gemini F7). compact.py and
sentinel_audit.py call sentinel.py's verifier (incl. the v1 kind/ts
cross-check); no reimplementations.
I. **R9 — Supersede completeness** (Gemini F8). Same-plate supersede
re-points or explicitly withdraws PENDING hits.
J. **R10 — Restore trust root** (F11; Gemini M2). No fallback to the
backup set's own key material: host key, explicit --pubkey/--fingerprint,
or refusal; Q25 gains a discriminating lost-key case against the
current restore path.
K. **R11 — Evidence parity** (F10). Restore-orphaned bundles enter the
normal bundle lifecycle; breach check and retention agree.
L. **R12 — Fence scope** (F12). The stale-feed fence blocks data reads;
safety writes (protection-order placement, ingest) proceed with chained
warnings; error text names the actual stale input.
M. **R13 — Chain-growth attribution** (F8). SHARE_BLOCKED and sibling
high-frequency chained events are rate-limited per authenticated caller
identity, never keyed on caller-supplied text; entries attributed.
N. **R14 — Load envelope** (ChatGPT R6-05). The concurrent-append stress
runs under defined load in the acceptance battery; the envelope
(appends/sec at which completeness holds) is measured and reported; if
contention loses appends, retry/backoff is implemented and tested.
O. **R15 — Honesty sweep.** sentinel.py version string; COMPACT.md and
backup stamps say 1.2.3; Q-battery header corrected; /health gains
migration_status (installation readiness) distinct from operational
health; INV4's heartbeat exclusion closed or justified in writing;
INV5's construction made deterministic; scrub-flag count surfaced in
/health; HOLD_DAYS+30 capped at 150.

## Acceptance standard for 1.2.3 (the round's merged forced change)

Verified invariant satisfaction, not passing counts: builders' suite +
round-4 attacks + round-5 seat-1 suite + **round-6 seat-2 harness
(in-tree)** + a new discriminating battery in which every R item has a
case that FAILS on 1.2.2 and PASSES on 1.2.3 (or a written
absence-proof), exercised against real multi-step lifecycles (real-tree
upgrades, two compact runs, a full rotation ceremony incl. abort, a
lost-key restore, the pin ceremony on real DBs). A case that observes
zero of the thing it tests fails the battery. All legs re-run by the
orchestrator from the public repo layout before Round 7 is called.

Documents remain FROZEN. Lanes 1–2 remain held for Corey's go.
