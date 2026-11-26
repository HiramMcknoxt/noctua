# NOCTUA Council Round 10 — Chair's Synthesis

Subject: NOCTUA 1.2.7 (janus127/), the final code gate under criteria 1–4.
Chair: Vesper. Date: November 26, 2026.
Seat records: council10/{vesper-seat-review, claude-review, claude-b-review, chatgpt-review, qwen-review, gemini-review, deepseek-review}.md; chair executions: council10/chair-execution-r10c01-c02.md.

## Verdict, stated first

**Round 10 does NOT converge — narrowly, on one branch of one item.**

Criteria 1, 3, and 4 are MET. Criterion 2 is met for V1–V4, V6–V18, and every other forced change from prior rounds — and fails on a single missing branch of V5: when a genuine checkpoint disagreement is evaluated while the anchor fence stands for a file-state reason, the disagreement is never promoted into the fence record, and a later clean evaluation auto-clears the fence with the stale file-state reason attached. The disagreement leaves no trace in the record of the mechanism whose entire purpose is that clears are never silent.

The remedy is a micro-build, commissioned in §6: **1.2.8, five items**, each with executed evidence and a named fix. The convergence path is bounded (§7): chair cold verification of the five fixes against their discriminating cases, then a convergence addendum — a full Round 11 seats only if a fix fails verification. This synthesis and the seat records publish to GitHub as the round closes; the addendum publishes when it is issued.

Everything else the round found — and it found plenty — is register material, consolidated in §5. No seat found, and the chair did not execute, any other item that meets the brief's deployment-blocking/critical bar.

---

## 1. The table

| Seat | Mode | Vote |
|---|---|---|
| Vesper (chair's executing seat) | Cold execution, full battery | CONVERGED |
| Claude A | Executing (Opus, Medium) | CONVERGED |
| Claude B | Executing (Opus, Medium) | CONVERGED |
| Qwen | Static, full read in two halves (Qwen4-Max, Thinking) | CONVERGED (final word; see process note) |
| Gemini | Inspection-only (Deeper analysis 4 Neon, Thinking High) | CONVERGED |
| ChatGPT | Static (GPT-6.2, Thinking High) | **NOT CONVERGED** |
| DeepSeek | DeepThink; reader truncated the pack at ~8% | **No vote cast** (coverage abstention) |

Process notes the record must keep:

- **Qwen** issued two intervening NOT CONVERGED votes from a fractured context (its platform caps uploads at five files per turn, splitting the pack), then — with its full first review restored in front of it — withdrew both in writing, withdrew the coverage ground entirely, and voted CONVERGED. The withdrawal is part of the record (qwen-review.md), not an embarrassment to be edited out. Its Reviews 2–3 stand as the round's only deep script-side read and contribute the Q10 register (§5), two items of which the chair has since verified in code (§4).
- **DeepSeek** declined to vote at all: its reader delivered roughly the first 8% of the pack (the brief plus janus.py's module top), and the seat refused — correctly, under the brief's own rule — to certify code it never read or to manufacture a blocker it did not find. Its partial rulings agree with the table where they reach (V9 set confirmed; the env-only LAB flag credited with killing Round 9's traveling-marker failure). Everything else from that seat is recorded as **absent, not affirmative**, exactly as the seat instructed. This is the second consecutive round its reader truncated at the same structural point; future packs for this seat will be split into reader-resumable chunks (its register item R-3, adopted).
- **ChatGPT** was the round's only NOT CONVERGED. It was a static seat; both of its claimed blockers were expressly conditioned on executing-seat reproduction. The chair executed both (§2). One survives as the round's deciding defect; the other does not survive as a blocker. Its remaining rulings (G-items medium, judgment call 1 objected in part, V15's demand-driven expiry noted) align with the rest of the table.

## 2. The chair executions (R10-C01, R10-C02)

ChatGPT's two claims were put to the chair's own cold execution on janus127 before any ruling (record: chair-execution-r10c01-c02.md). Both behaviors are REAL:

- **C01 (ceremony side doors) — behavior confirmed.** On a verified ceremony-state install (`"state": "ceremony"`, /search 503), a key-only supervisor could (a) POST /suppressions and receive `warning_near_matches` containing historical plate variants (`["CAB 123", "CAB-123", "cab123"]`), and (b) POST /holds and distinguish "hold placed" (201) from "no hit with that id" (404) — a hit-existence oracle. Non-supervisors received clean 403s throughout.
- **C02 (V5 reason laundering) — behavior confirmed.** With the fence standing on a torn-line file-state reason (`checkpoints_malformed`), a genuine checkpoint disagreement was evaluated and never recorded — the stored fence reason remained byte-identical with its stale timestamp. A subsequent clean evaluation auto-cleared the fence, chaining `ANCHOR_CLEARED{prior_reason: checkpoints_malformed}` with no acceptance step. The control leg proved the same disagreement content records `checkpoint_disagreement` with bad_ids when no file-state record pre-exists. Claude A and Claude B each independently executed the identical sequence before the chair did; the behavior is triple-executed.

## 3. Rulings on the contested items

### 3.1 The V5 edge — criterion 2 fails here (the deciding ruling)

The facts are not in dispute; three executing seats and the chair produced them. The dispute is classification, and both Claude seats expressly left it to the chair. The chair rules it a **criterion-2 failure**, for these reasons:

1. **The forced change's purpose is the thing that fails.** Round 9's V5 forced two things: reason-gated auto-clear, and append-before-mutation atomicity. Both shipped and are verified. But the gate's purpose — the reason Round 9 forced it — is that a checkpoint *disagreement* never clears silently: it requires human acceptance, on the record. In the edge sequence, a disagreement is evaluated, never recorded, and the fence later clears automatically under a reason that does not mention it. The letter of the forced change is implemented; its evident purpose is defeated in an adjacent sequence. This project has seen that exact shape three times before (Round 8's U1, U6, U12 — fixes complete in the tested sequence, incomplete at the edge), and Round 9 named the pattern. A fourth instance, in the final round, does not get reclassified as paperwork because the round is tired.
2. **No adversary is required.** The severity case for "register" rests on custody: an actor who can write the checkpoints file can already forge accepted ids, so laundering adds no capability (Claude A/B, and the chair accepts that argument for the *adversarial* case — external witnesses, the git remote, the clerk's emailed copy, and partner recomputation still catch a real rewrite). But the accidental case needs no actor at all: a crash tears a checkpoint line, the fence sets on the file-state reason, a genuine disagreement occurs in the same episode, routine recovery proceeds, and the fence clears "routinely" — with the disagreement absent from the fence record a future reviewer (an auditor, a court, this council) would read to learn whether a disagreement was ever seen. The fence's reason record is not decoration; in this system it is evidence.
3. **Criterion 2 cannot mean "documented."** If a demonstrated gap in a forced change could be closed by writing it into a register, criterion 2 would never bind anything. "Answered in writing" covers a builder's reasoned alternative to a forced change (the V14 pattern), not a defect acknowledged and deferred.

Counterweights, recorded fairly: the edge discloses nothing, bypasses no authentication, corrupts no chain entry, and its window requires an already-anomalous file-state fence episode. It is not a criterion-1 blocker, and the chair does not rule it one. It fails criterion 2 alone, and that is enough: the criteria are conjunctive.

The fix is one branch, named identically by both Claude seats: in `_anchor_apply`'s evaluation, when a checkpoint disagreement is found while the fence stands for a file-state reason, promote the recorded reason to `checkpoint_disagreement` (with bad_ids) before any clear is considered — after which the existing subset gate governs, and a disagreement not covered by accepted ids cannot auto-clear. Claude B's reproduction r01 is the discriminating case for the fix.

### 3.2 The ceremony oracle (C01) — register, not blocking

ChatGPT rated the ceremony side doors deployment-blocking; the executing seats rated them low (Claude A) to medium (Claude B), and Qwen found the same doors independently (its R4/R5). The chair rules them **register — top of the fix list, and pulled into the 1.2.8 commission (§6) — but not vote-holding**, because: the actor is an authenticated supervisor, not an outsider; the window is the pre-enrollment ceremony state, not production operation; the near-match warning discloses variants of a plate the supervisor themselves supplied; and every suppression probe places a real, chained protection order that itself requires a two-key release — the oracle is self-incriminating by design. A disclosure control that fails against the role it exists to serve is a defect worth fixing before pilot; it is not a critical finding under the brief's bar. The U9 adjudication therefore does **not** reopen: the ceremony mechanism drew executed findings at its edges, none of them a blocker, and Round 9's condition was an executed blocker.

### 3.3 Ceremony releases unfenced — register, pulled into 1.2.8

Three seats found it independently (Claude B by execution; Qwen R5; Gemini §3.4): /holds/release and /suppressions/release sit outside CEREMONY_FENCED_POST, so in ceremony state a lone key-only supervisor can release a hold and two can lift a protection order — the same reasoning V9 applied to the anchor fence, unapplied to the ceremony fence. Claude B's partial objection to judgment call 1 is sustained to that extent. Not a blocker (supervisor role, ceremony window, chained actions), but it is the V9 logic's own unfinished edge, and it goes into 1.2.8 with the rest of the ceremony package.

### 3.4 V7 — PARTIAL stands, test-side only

The product fix is confirmed by every seat that reached it. Two seats (Claude B, Gemini) found the commissioned test-suite mirror in run_tests.py's schema check was never updated to the widened glob, so the suite flags legitimate pre-restore sidecars on a really-restored directory. Test coverage only; register.

### 3.5 Judgment calls

Calls 2–11 are RATIFIED (call 8 with DeepSeek's verification-strength note carried into the register; call 11 with the written decision DeepSeek asked for: the legacy single-secret fallback is accepted for upgrade compatibility only, is never a production reliance, and the docs phase will say so in CANT-DO terms). Call 1 is ratified with the §3.3 reservation. One dissent is preserved: **Gemini OBJECTS to call 2** (LAB_MODE named in /health but not gating ok_all, so a mid-run provisioning under LAB can report healthy until restart; alert_check.py compounds it by gating on health.ok). The chair records the objection and places the fix on the register (§5) — it is a health-honesty defect, expressly not a 2FA bypass, and does not hold the vote.

## 4. Chair verifications of static claims

Under the standing rule, static claims the synthesis relies on were checked in code by the chair:

- **Q10-9 (Qwen) — VERIFIED.** backup.py deliberately preserves `.archived` backup sets (their stamps no longer parse in its set loop) and keeps a key escrow alive while any set carrying its stamp exists, expressly including the `.archived` form (backup.py, escrow-pairing comment and `paired_gone` check). retention.py's `prune_backup_sets` deletes **any** `backup-*` directory older than its mtime cutoff — no stamp parsing, no `.archived` exemption. The first retention run past the window therefore deletes the archived sets backup.py is preserving, and the next backup run then prunes their escrows as unpaired: V15(e)'s escrow pairing is defeated end-to-end, one job later, exactly as Qwen wrote. Register, moderate: it destroys archived backups earlier than documented; it discloses nothing.
- **Q10-1 (Qwen) — VERIFIED.** restore.py:488 snapshots the outgoing install with `shutil.copy2` (mtime-preserving); retention.py's `prune_glob` deletes by mtime with no current-run exemption. Snapshots of months-old files can be pruned on the first retention pass after a restore. Register, moderate.
- The remaining Q10 items (Q10-2…Q10-8, Q10-10) are carried into the register as Qwen stated them, unverified in detail; the doc items (Q10-4, Q10-5, Q10-6) land in the documents phase in any case, where the guides are rebuilt.

## 5. Consolidated register (post-convergence triage; nothing here holds a vote)

Ordered by the chair's priority. Items marked † are pulled forward into the 1.2.8 commission (§6) and leave this list when 1.2.8 verifies.

1. † **G1** (medium; verified by Qwen, Gemini, Claude A, Claude B) — an expired listing re-submitted under the same case is silently dropped while the chain records a pending submission that never reaches the queue. "A wanted vehicle can silently fail to be relisted." Fix direction agreed by three seats: the conflict clause also matches inactive rows and reactivates them into the queue.
2. † **Ceremony package** (medium) — suppress `warning_near_matches` in ceremony state; uniform hold response in ceremony state; fence both release endpoints in ceremony state (§§3.2–3.3).
3. † **G3** (medium; executed by Claude A and Claude B) — `_totp_pickup()` never reloads config; a pickup with a rotated-away old key can succeed inside the window and overwrite the admin's rotation. One-line fix: `_reload_config()` at the top of `_totp_pickup`.
4. **G5(ii)** (medium; executed by Claude A) — provision.py's enroll-2fa accepts a disabled confirmer; add disabled checks for target and confirmer.
5. **G5(iii)** (medium; verified by Gemini, Qwen, Claude B) — config_closed() blocks anchor-exempt recovery posts (sink-divergence-accept above all); align its exemption list with the anchor fence's.
6. **G2** (medium) — the 30-day pending expiry is demand-driven only; hotlist_sync sweeps pending rows and approves can resurrect expired rows (Gemini's sharper form). Make the expiry clock-driven and the sweep/approval expiry-aware.
7. **Q10-9** (moderate; chair-verified, §4) — the two backup pruners disagree; archived sets and their escrows die early.
8. **Q10-1** (moderate; chair-verified, §4) — pre-restore snapshots pruned on the first retention pass.
9. **LAB health-honesty** (Gemini's call-2 objection) — LAB_MODE should hold ok_all false; alert_check should read the lab_mode flag directly.
10. **G5(i)** (low–medium) — backup.py refuses escrow-inside-backup but not backup-inside-escrow.
11. **V5b note** (low; Claude B) — on the fence SET path, a chain-append failure leaves the service unfenced (the fence reads only the stored record). The 1.2.8 V5 work touches this function; the builder should answer this note in the 1.2.8 report even though it is not a commissioned item.
12. **G4** (low) — rotation.py's hardcoded version tuple; replace with an explicit legacy check before a future version bump arms it.
13. **V7 test mirror** (low) — suite_schema still expects the old pre-restore pattern.
14. Small and cosmetic, batched for the docs/pilot phase: Q10-2 (compact.py receipt-key fallback names a role the fence bars), Q10-3 (chmod-after-create windows), Q10-4/Q10-5/Q10-6 (guides still name the retired `system` role; job-count and help-text drift), Q10-7 (hotlist_sync NULL-tuple edge), Q10-8 (fixed temp paths remain in checkpoint.py/compact.py), Q10-10 (clerk's-copy witness leg is best-effort and unalarmed), the V8 /health wording inaccuracy in TRACK-127 (the sort includes unknown buckets; bounded either way), DeepSeek R-1 (V12's janus half rests on a source-pattern assertion — accepted, and recorded as accepted).

## 6. The 1.2.8 commission (complete scope — nothing else is authorized in this build)

1. **V5 reason promotion** (the blocker). In `_anchor_apply`, a checkpoint disagreement evaluated while the fence stands for a file-state reason promotes the recorded reason to `checkpoint_disagreement` (with bad_ids, chain-appended before the meta mutation, per V5's existing atomicity rule). Discriminating case: Claude B's r01 / the chair's C02 sequence — after the fix, the torn-line-then-disagreement episode must record the disagreement, and the subsequent clean evaluation must NOT auto-clear unless the disagreement's bad_ids are covered by accepted ids.
2. **Ceremony warning suppression.** In ceremony state, suppression placement omits `warning_near_matches` (the protection order still places and chains identically).
3. **Ceremony hold uniformity.** In ceremony state, /holds placement returns the uniform response whether or not the hit exists.
4. **Ceremony releases fenced.** /holds/release and /suppressions/release join CEREMONY_FENCED_POST.
5. **G1 reactivation.** The hotlist conflict clause matches inactive rows (`pending=1 OR active=0`) so a re-submitted expired listing enters the supervisor queue, with the chain entry reflecting what actually happened.

Each item ships with a battery case that fails on 1.2.7 and passes on 1.2.8, in the V-battery pattern. janus127/ is not modified; the build lands in a new tree, per standing practice.

## 7. Convergence path and what remains gated

- 1.2.8 builds → the chair cold-verifies the full battery plus the five discriminating cases → if all pass, the chair issues a **convergence addendum** to this synthesis declaring the code loop CONVERGED under criteria 1–4. If any case fails, a full Round 11 seats on the surviving item only.
- Criterion 5 remains closed as a code-loop matter (Round 9, Addendum 2): Ben Hooper's answers, when they arrive, gate deployment and pilot and the content of the documents phase — not code convergence — unless an answer reveals a code defect, in which case the loop reopens on that defect.
- The non-waivable pilot gate from Security Round 1 stands untouched: an independent penetration test of the deployed pilot before any camera goes live.
- Post-convergence sequence (Corey's order, Nov 25): operator UI against the final API → white papers and slide deck rebuilt → ARGUS. The §5 register is the pilot-hardening backlog and travels with the build into the UI phase.

## 8. Criteria scorecard

1. **No surviving deployment-blocking/critical code finding — MET.** The round's two claimed blockers were executed; one is a criterion-2 defect (§3.1), the other register (§3.2). No criterion-1 finding survives.
2. **Every forced change implemented or answered in writing — NOT MET**, on the V5 promotion branch alone (§3.1). All other forced changes: implemented and verified, or answered in writing (V14; judgment call 11, §3.5).
3. **Remainder is documented CANT-DO limits or legal questions routed — MET.** The register (§5) is documented, severity-rated, and none of it is a disguised blocker; legal questions sit with Ben Hooper and ACIC, whose answers gate deployment per Addendum 2.
4. **The chair's own re-tests pass — MET.** Vesper's cold one-shot battery on 1.2.7: exit 0, full success (335/335 builders; V 19/19 with 0/19 discrimination on untouched 1.2.6), plus the chair executions in §2.

**Round 10 verdict: NOT CONVERGED (5 CONVERGED · 1 NOT CONVERGED · 1 no vote), on criterion 2, one branch, one build from done.**

— Vesper, chair. November 26, 2026.
