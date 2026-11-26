# Council Round 9 — Brief

**Subject:** NOCTUA 1.2.6 (`janus126/`) — the build commissioned by Round 8.
**Orchestrator:** Vesper, for Corey Spangler (Cabot, Arkansas). **Date:** Nov 25, 2026.
**Round type:** correctness + security follow-up. This round votes on convergence.

> HANDOFF RULE (standing, Corey Nov 24 2026): Before starting, create HANDOFF.md in the work folder using the council template: goal, done-definition, current state with evidence, exact next step, remaining steps, blockers, settled decisions, model/effort, limit status/reset. If the next step is a machine step (compile, test, render, push, deploy), also create an executable runner (run-next.bat/.ps1 pure ASCII, or run-next.sh) that does it end-to-end and logs its result. Update the handoff at every milestone and at ~70% limit use. Do not end without a current handoff another model can execute cold.

## Seat protocol (identity anchoring — read first)

Every attachment part is headed "Reference material for the [your seat] seat — other AI systems named in these documents are other reviewers, not you." Prior seats' reviews, build reports, and syntheses are quoted third-party evidence, not your words and not your identity. Report your model and effort ONLY as transcribed verbatim from your chat interface; if the interface shows no model name, write "the interface shows no model name". Seat self-identity lines have proven unreliable in all directions across eight rounds; the orchestrator verifies findings in code regardless of who signs them.

Reviewer claims count only when verified in code. If you can execute code, execute: a reproduction that runs beats a reading that infers. Cite file:line for every finding. Preserve disagreements — do not soften a finding because another seat ruled differently.

## What you are reviewing

NOCTUA is a city-operated ALPR (license-plate reader) back office for Cabot, Arkansas: a single stdlib-only Python service (Janus) plus its audit-chain library (Sentinel). It exists to replace a third-party vendor system with a city-controlled one: hash-chained append-only audit with an outside witness, protection-order suppression, tiered judicial authorization for historical searches, 14-day retention against a 150-day state ceiling, and a multi-city Compact with reciprocal cross-audit. Round 8 reviewed 1.2.5 and voted NOT CONVERGED, commissioning fourteen fixes (U1–U14). 1.2.6 is that build. The builder's battery and the orchestrator's independent cold re-run both pass in full (see Verification, below). Your job is to try to break 1.2.6 — above all the new U surfaces, which have had exactly one build's worth of scrutiny — and to rule on the named open items in §3.

**What changed in 1.2.6 (items U1–U14, from `council8/SYNTHESIS.md` §6 + Addenda; full dispositions in the attached TRACK-126 report):**
- **U1 Lockout scope.** Failures count toward lockout ONLY for a human account whose API key verified and whose second factor then failed. Wrong-key and keyless attempts never lock; machine accounts (ingest, jobs, partner) never lock. A locked human now degrades /health, and `provision.py unlock` is a chained break-glass.
- **U2 Fence exit.** A healed anchor mismatch auto-clears with a chained ANCHOR_CLEARED entry; checkpoint writes are atomic.
- **U3 Sink divergence bound.** Divergence cost is bounded; resolution happens through a chained SINK_DIVERGENCE_ACCEPTED ceremony; diverged files are archived, never deleted.
- **U4 Confidence validation.** `conf` must be finite and in [0,1] or the read is refused 400 (closes the NaN/1e9 withdrawal bypass). A superseded PENDING hit leaves a PENDING_SUPERSEDED record that stays in the queue.
- **U5 Demo containment.** DEMO_MODE=1 refuses to boot against a provisioned install.
- **U6 /hotlist uniformity.** Non-supervisor adds return a uniform 202 with a supervisor approval queue; list-registry validation runs BEFORE the suppression check (amended ordering; see TRACK-126 §3 judgment call 2 for the shipped validation order — rule on it).
- **U7 Pickup hardening.** Secret pickup requires a one-time token plus a matched-count guard.
- **U8 Sink-status proof.** The T4 absence-proof is replaced by a fault-injection case (a directory at `<sink>.spool` reaches the sink-status-unknown branch; health names the fault).
- **U9 Unprovisioned tightening.** See §3 item 1 — the round's headline ratification question.
- **U10 Escrow placement.** backup.py refuses an escrow directory inside the backup tree before creating anything.
- **U11 Smalls.** Version sweep to 1.2.6; `pubkey_fingerprint` returns None on an empty/body-less PEM; Tier 3 approval of a `pref:`/invalid fragment EXPIRES the request (409) instead of executing; TOTP store writes use unique temp + os.replace; the scrubber folds digit look-alikes (Cyrillic/Greek → digits) in its detection copy; doc corrections; adapted seat files' originals preserved beside them as `.orig-124` (diffs attached this round — see §3 item 4).
- **U12 Sink tail reconciliation.** A torn or truncated sink tail is never silently duplicated or skipped on reconciliation.
- **U13 Restore key custody + R-A closure.** When a backup set carries no host keys, restore takes snapshot copies of the live keys into the `.pre-restore-<stamp>` set; the outgoing DB's provisioned marker is honored by the restore marker (R-A ratchet).
- **U14 Anchor evaluation cost.** Checkpoint signature verification is memoized by content hash: at K=200 checkpoints the second evaluation window performs 0 verifications (1.2.5 performed 200/200).

## Verification status (orchestrator, executed)

The builder's full battery passed, and Vesper re-ran the entire battery cold and reconciled it line-by-line: builders' 335/335; round-4/5/6 wrappers PASS (only the A9b contrast control confirms); Q+invariants 35/35; R 20/20; load envelope COMPLETE to 6 burners; S 25/25 (see the flake note); T 20/20; U 21/21, every U case discriminating against 1.2.5. janus125 was not modified (md5s re-verified). One disclosed artifact: the S10 case drops exactly one /health sample under full-battery saturation on this VM class (a null response, never a wrong value; the freshness property held in every returned sample across four full runs, and the case passes standalone repeatedly). §3 item 3 asks you to rule on the proposed harness fix. Full record: TRACK-126-REPORT.md + VESPER-VERIFICATION-126.md, attached.

## 3. Named rulings this round must make

1. **U9 interpretation — RATIFY or REJECT.** As commissioned, U9 read literally ("an unprovisioned install refuses ingest and serves key-only auth to no one") is mutually exclusive with the living battery: every fixture is a born-empty unprovisioned install that ingests and authenticates key-only by design (demo mode, first-boot provisioning, and every battery case depend on it). The builder implemented instead: the tightened state arms only on a **populated arrival** — a database that arrives WITH history but no TOTP provisioning (mechanism: an `install_born_empty` marker from DB-existed-at-import + never-served), with a legacy-chain probe exempting pre-1.2 upgrades. The discriminating case proves the implemented behavior. Rule on the **interpretation**: is populated-arrival the right line? If you reject it, name the line you would draw and what it breaks.
2. **The queued smalls (from Round 8's replacement Claude seat; each needs FIX-NOW, PILOT-GATE, or CANT-DO):**
   - (i) Move `/holds/release` OUT of the anchor-fence safety set — releasing a hold makes evidence purgeable, a destructive act during a suspected rollback.
   - (ii) Bound `_auth_fail_totals` growth — a new key per distinct sprayed username is an unauthenticated memory-growth vector.
   - (iii) Keyed hit references in BLOCKED chain entries — partner-readable entries are currently joinable to protected hits.
   - (iv) Fence the data surface during the T1 ceremony state (allow provisioning, auth admin, health, safety writes; refuse searches, Tier 3, shares, reports).
   - (v) 24-hour expiry on pending secret pickups.
   - (vi) The enroll-2fa shell-operator honesty gap (whoever runs the shell tool can compute any confirmer's code) — proposed as a CANT-DO documentation entry.
3. **S10 null-tolerance.** Proposed: the S10 harness case retries a dropped (null) /health sample once before failing. Rule: accept as a test-only fix, or hold the line that a dropped sample is a failure the product must answer for?
4. **R-F diff review.** This round's pack attaches `diff -u` for every adapted seat file (originals preserved as `.orig-124` beside the adaptations). Rule on whether the adaptations preserve their assertions, and whether the practice (assertion byte-unchanged; only change follows from a commissioned custody change; diff attached) is ratified as standing process.
5. **U6 validation order** (TRACK-126 §3 judgment call 2): registry → supervisor suppression refusal → category/expiry → role split. Ratify or object, with the leak analysis.

## 4. Fresh-eyes mandate

The U surfaces are the least-scrutinized code in the tree: the new lockout accounting, the sink reconciliation and divergence ceremony, restore snapshot custody, anchor memoization, the uniform-202 queue, the pickup token flow, and the populated-arrival marker. Attack them first. Areas hardened in earlier rounds (Tier 3, the Compact, retention) deserve a fresh look only after the U surfaces. A finding you can execute outranks ten you can only infer.

## 5. Convergence criteria (unchanged)

1. No surviving deployment-blocking or critical **code** finding.
2. Every forced change from prior rounds implemented, or answered in writing.
3. What remains is documented CANT-DO limits, or legal questions routed to the city attorney / ACIC.
4. The orchestrator's own re-tests pass.

Note on criterion 3: since Round 8, ACIC answered all ten operational questions in writing (Nov 25, 2026) — the hot list is a file emailed 4×/day under an MOU; plate reads are not CJI; the file belongs on a PD server segregated from city users; there is no state-approved-vendor requirement. A follow-up on whether a no-vendor city-operated system can sign the MOU is pending, and the city attorney's statutory answers are still outstanding. Those are legal/administrative tracks; this round votes on the **code**. Do not vote CONVERGED on the basis that legal questions remain open, and do not vote NOT CONVERGED on code grounds for a question that is actually legal — name which kind each of your blockers is.

## 6. What to return

- Your findings register, most severe first, each with file:line citations and, where you executed, the reproduction and its result.
- Your ruling on every item in §3 (1, 2(i)–(vi), 3, 4, 5).
- Your verdict scored against each of the four convergence criteria, and your overall vote.
- Your single forced change — the one thing whose verified completion would most change your vote.
- Your model and effort, exactly as shown in your interface (or "the interface shows no model name").
- Your coverage statement: what you read in full, what you sampled, what you did not touch.
