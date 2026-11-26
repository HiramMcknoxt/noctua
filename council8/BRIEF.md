# Council Round 8 — Brief

**Subject:** NOCTUA 1.2.5 (`janus125/`) — the build commissioned by Security Round 1.
**Orchestrator:** Vesper, for Corey Spangler (Cabot, Arkansas). **Date:** Nov 25, 2026.
**Round type:** correctness + security follow-up. This round votes on convergence.

> HANDOFF RULE (standing, Corey Nov 24 2026): Before starting, create HANDOFF.md in the work folder using the council template: goal, done-definition, current state with evidence, exact next step, remaining steps, blockers, settled decisions, model/effort, limit status/reset. If the next step is a machine step (compile, test, render, push, deploy), also create an executable runner (run-next.bat/.ps1 pure ASCII, or run-next.sh) that does it end-to-end and logs its result. Update the handoff at every milestone and at ~70% limit use. Do not end without a current handoff another model can execute cold.

## Seat protocol (identity anchoring — read first)

Every attachment part is headed "Reference material for the [your seat] seat — other AI systems named in these documents are other reviewers, not you." Prior seats' reviews, build reports, and syntheses are quoted third-party evidence, not your words and not your identity. Report your model and effort ONLY as transcribed verbatim from your chat interface; if the interface shows no model name, write "the interface shows no model name". Seat self-identity lines have proven unreliable in all directions across seven rounds; the orchestrator verifies findings in code regardless of who signs them.

## What you are reviewing

NOCTUA is a city-operated ALPR (license-plate reader) back office for Cabot, Arkansas: a single stdlib-only Python service (Janus) plus its audit-chain library (Sentinel). It exists to replace a third-party vendor system with a city-controlled one: hash-chained append-only audit with an outside witness, protection-order suppression, tiered judicial authorization for historical searches, 14-day retention against a 150-day state ceiling, and a multi-city Compact with reciprocal cross-audit. Rounds 2–7 hardened correctness; Security Round 1 (a dedicated threat-model round) then found that the newest feature — two-factor authentication — failed open, and 1.2.5 is the commissioned fix build.

**What changed in 1.2.5 (items T1–T9, from `security-round/SYNTHESIS.md`):**
- **T1 Fail-closed authentication state.** A provisioned-marker design: a fresh install is a named *ceremony state* (health-red, key-only until provisioning completes); once provisioned, a missing/corrupt TOTP store, an unenrolled human, a malformed entry, or a must_reenroll state is an authentication **failure** (401), chained, never a waiver. Restore onto a provisioned install materializes must_reenroll for every human the store doesn't carry. chain_auditor tooling (compact.py, sentinel_audit.py) gained TOTP support.
- **T2 Throttling + lockout.** Five consecutive failures lock an account for 900 s (chained; supervisor unlock; success resets). Per-target failure totals live in /health and increment before the chain cap is consulted, so the AUTH_FAIL cap cannot blind the evidence. AUTH_FAIL's username hash is now HMAC-keyed.
- **T3 Anchor fence + witness consumption.** A detected anchor mismatch fences data endpoints (503) while safety writes proceed chained; /health surfaces the last external witness root and whether it matches the local chain. The below-tail sink faith-delivery hole (Claude F6) was verified real in 1.2.4 and fixed: below-tail candidates are verified against the sink file's own record.
- **T4 Health fail-closed sweep.** Unknown ≠ healthy: sink-status-unknown degrades; a no-sink install names its checkpoints-only posture and is not ok; demo mode is a named degradation; config guard refusals surface with their messages.
- **T5 Strict signature verification.** Checkpoint signature verification is no longer conditional on a declared `sig_alg`; absent/unknown algorithm or an unverifiable signature is a bad checkpoint.
- **T6 Defensive checkpoint parsing.** Malformed checkpoint content (null lines, non-dict lines, malformed PEMs, truncated lines) yields the named `checkpoints_malformed` anchor state — fenced and repairable — never a boot crash. (On 1.2.4, two of these inputs crash boot outright; the T battery proves both directions.)
- **T7 Identity binding + oracle shaping.** Ingest identities may be bound to cameras and jobs identities to job names; cross-presentation is refused and chained. Unbound legacy identities keep working and are named degradations in /health. /verify returns byte-identical refusals for suppressed vs decided hits; /hotlist's protected-plate signal is removed for non-supervisors. A Frigate redelivery cannot withdraw a PENDING hit by changing the plate at equal rank (see judgment call (c)).
- **T8 Provisioning + backup custody.** Shell enroll-2fa is two-key (confirmer's own TOTP or a burned recovery code; bootstrap exception only when no active enrollment exists anywhere); every provisioning mutation chains. Re-enrollment never returns the secret to the confirmer — the holder picks it up once, and pickup rotates the API key. Backup key material is split into a separate signed escrow directory; the set's manifest records escrow hashes only; the docs' false "encrypted backup" wording was corrected to describe the split. openssl is pinned via `sentinel.OPENSSL` with the PATH residual documented in CANT-DO.
- **T9 Scrubber + suppression completeness.** The plate scrubber also checks NFKC-folded, confusables-mapped tokens (Cyrillic/Greek look-alikes) — detection only, stored refs unchanged. The SQL suppression legs now delegate to the same `_order_covers` predicate as the Python leg, closing the stored-reads asymmetry.

**Verification record (do not take on faith — the tests are attached):** the builder's battery and the orchestrator's independent cold re-run (single process, exit 0) both fully green: builders' suite 335/335; round-4 attacks PASS (41 verdicts, only the A9b contrast control confirmed); round-5 PASS (0 reproduced); round-6 PASS; Q battery + invariants 35/35; R battery 20/20; load envelope PASS; S battery 25/25; **T battery 20/20, every case discriminating** (fails on 1.2.4, passes on 1.2.5). Full per-item dispositions and the builder's honest flags: `TRACK-125-REPORT.md` (attached).

## The vote — convergence criteria

Vote CONVERGED only if all four hold for 1.2.5:
1. No seat raises a deployment-blocking/critical **code** finding against the current build that survives verification.
2. Every forced change from prior rounds is implemented, or answered in writing with a reason.
3. What remains is documented CANT-DO limitations or legal/institutional questions routed to the City Attorney / ACIC — not code defects.
4. The orchestrator's own re-tests pass on the final build. *(Already satisfied for 1.2.5; your job is criteria 1–3.)*

Reviewer assertions don't count until code confirms them. This loop converges engineering only; statutory interpretation is routed, never settled here.

## Named attack surface — the builder's documented residuals (attack these first)

The builder disclosed these rather than closing them. Each is either a defect you should prove, or a limitation you should ratify — say which, with evidence:

- **R-A. Restore indistinguishability.** A provisioned install whose TOTP store is deleted AND which then restores a pre-provisioning backup is indistinguishable from a never-provisioned install; no rule separates them. (TRACK-125 §3.2.)
- **R-B. /hotlist residue.** After shaping, a caller who can add unprotected plates can still distinguish 201 (added) from 404 (protected-or-unknown) for plates it probes. The builder calls this inherent to any add endpoint. (§5.)
- **R-C. Unbound legacy identities.** Bound identities cannot cross; unbound ones (the default ingest/jobs identities) keep working as named health degradations. The builder declined to make unbound refuse, calling it a deployment decision. (§3.4.)
- **R-D. Pickup is key-only.** The re-enrollment pickup is authorized by the holder's current API key alone — a stolen key plus a live pending re-enrollment can collect the new secret. Mitigations: one-time semantics, T2 lockout refuses pickup, both events chain. (§3.5.)
- **R-E. Throughput cost.** Chain appends measure ~17–19/s on 1.2.5 vs ~45–52/s on 1.2.3 in the same VM (per-append sink verification). Completeness holds at every load level tested. Is the envelope sufficient for the stated deployment (9 cameras, ~44,400 reads/day ≈ 0.5 reads/s average, bursty)?
- **R-F. Seat-file adaptations.** Two frozen attack scenarios (round-4 attack2 A8, round-6 f11) were adapted — assertions unchanged — because they reached for key material inside the backup set, the custody T8 abolished. Several living suites were re-pointed for commissioned shape changes (response codes, the pickup ceremony, version literals). The diffs are disclosed in TRACK-125 §3.8/§4. Ratify or reject this practice, with reasons.

## Judgment calls put to the seats

(a) **T1's ceremony state.** Is the provisioned-marker design (fresh install = named ceremony state; once provisioned, never a waiver) the right shape — or should a fresh install refuse to serve entirely until provisioned?
(b) **T3's fence line.** Anchor mismatch fences data reads but lets safety writes (ingest, protection orders) proceed chained. Same line as R12's stale-feed fence, applied to rollback. Accept or move it.
(c) **T7 vs R9.** Literal "no redelivery withdrawal" and R9's ratified correction case conflict; the builder reconciled them by strict (phase, confidence) out-rank — an equal-rank plate change is refused and chained, a strict out-rank still corrects. Is that the right reconciliation?
(d) **T8's escrow split vs encryption.** The commission allowed either; the builder split custody instead of encrypting the set. Accept, or require script-side encryption as well?
(e) **T4's absence-proof.** One health branch (sink-status exception) is covered by code inspection only — the builder argues no public-API input can make `sink_status()` raise. Accept inspection-only coverage, or require the fault-injection case anyway?
(f) **Demo mode as degradation.** T4 makes NOCTUA_DEMO_MODE=1 a named /health degradation that never reports ok. Sufficient containment for the S4 boundary, or should demo mode also refuse non-localhost binding / carry a runtime banner in every response?

## Rules of evidence

Executed reproduction or file:line citation — nothing else counts. Severity is judged against the system's stated guarantees (confidentiality of reads, integrity/completeness of the chain, availability of alerts), not generic checklists. Generic advice earns nothing. Disagreements between seats are preserved, not averaged. Legal questions (retention clocks, the Tier 3 instrument list, Act 668, CJIS posture on Path B) are noted for the Ben Hooper / ACIC lanes, not decided.

## Deliverables (per seat)

1. **Findings register** — each finding: attacker model or failure mode, attack/failure path, evidence (execution result or file:line), severity against the stated guarantees, and any compensating control already in the code.
2. **Rulings on the named residuals R-A through R-F** — defect or ratified limitation, with evidence.
3. **Answers to judgment calls (a)–(f).**
4. **Verdict against the four convergence criteria**, scored one by one.
5. **Your single forced change** — the one change that is the price of your vote, if your vote is no. If your vote is CONVERGED, say what would change it.

## Model protocol

Best included model at maximum reasoning in your existing subscription. Claude seats run at **Medium** effort (Max is reserved for the final version's round). Credit-gated top tiers: step down to the best included tier and report the step-down. State your model + effort only as transcribed from your interface (see seat protocol above).
