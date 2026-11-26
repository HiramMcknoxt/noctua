# Round 6 — Qwen seat review of NOCTUA 1.2.2 (archive, substance-preserving)

Seat: chat.qwen.ai, UI showed Qwen4-Max + Thinking (chat
https://chat.qwen.ai/c/634e2a1e-2855-42f9-9afd-0cd3d59a25f0), run
Nov 24 ~18:34-18:55 CST via the user's Gmail sign-in.
MODEL-LINE ANOMALY: the review's own disclosure line names "Kimi K2
Thinking Performance," contradicting the UI — same anomaly class as
DeepSeek's "I am Claude" line. Identity lines from these web seats
are unreliable; the findings below stand on their reproductions.
Method: attachments arrived whitespace-stripped, so the seat pulled
sentinel.py / compact.py / provision.py verbatim from the public
repo (commit a707a10, confirmed) and EXECUTED them; janus.py
functions were transcribed and run. No Ed25519 CLI in its sandbox.

## Verdict: NOT CONVERGED (criteria 1-3 FAIL, 4 PASS as reported)

Six CODE-CRITICAL findings, all converging with the round's R-items:
- R6-01 rotation grindable by the publisher alone (supervisor commits
  and reveals for every member; the builders' rotation_ceremony
  helper performs the attack as the happy path; INV5 cannot detect
  it). = 1.2.3 R6. Its forced change (partner-identity/signature
  authorship, pending binds cycle params, void clears a stuck
  ceremony, adversarial grind test) matches R6 as built.
- R6-02 pin-audit-key crashes on every real DB (fragment vs frag) +
  its legacy formula differs from janus.py's verifier. = R3.
- R6-03 Q18's pre-auth warm calls auth() -> _reload_config() ->
  chain.append OUTSIDE DBLOCK: lost CONFIG_CHANGED entries (A13
  reopened) AND a phantom construction the other seats did not use:
  append() re-reads db.in_transaction unlocked after _append_txn,
  racing do_POST's rollback — a sink line streams for a transaction
  that rolls back. (The spool presence check itself held.) = R4/R5;
  the specific append-race shape was flagged to the 1.2.3 builder
  for structural confirmation.
- R6-04 compact.py's high-water advance fails every SECOND audit
  against the same checkpoint. = R7 (Gemini F1).
- R6-05 evidence folders: registry_breaches flags ORPHANED bundles
  and destroyed-on-paper-but-on-disk bundles, but retention's only
  evidence selection can never pick either — a permanent on-disk
  plate archive past the 150-day cap, /health degraded forever.
  1.2.3's R11 covers orphaned dirs; the destroyed-on-paper half was
  flagged to the builder for a confirming case.
- R6-06 _migrate_122's merge deletes the ACTIVE order and keeps the
  released order's court ref (survivor = first to re-key; copies
  only `active`). = R1/R2 (seat 2 F2b family).
Minors: R6-07 rotation deadlock (R6 cancel path), R6-08 re-commit
rewrites cycle params (R6 signed portion), R6-09 _strict_id accepts
unbounded decimals -> OverflowError 500 not 400 (flagged to builder),
R6-10 mixed UTC/local clocks in rotation status, R6-11 witness
round_no unchecked against the cycle (flagged), R6-12 deferred
migrations commit before MIGRATION is chained (1.2.3 runs them
inside the boot transaction — covered by design).
Non-reproductions recorded honestly (its /hits-cost suspicion was
wrong; Q17 cross-check and Q6 parity held where traced).
Judgments: (a) both-tree-pass = property evidence, not fix evidence;
Q16/Q18 cases must be rebuilt (convergence with the round); (b) Q25
trust root reads correctly but restore's atomicity claim is
over-broad (aside() inside the extraction loop) — narrow the claim
or add fail-injection; (c) strip-not-raise ACCEPT, DDL ACCEPT,
courier REJECT, disp-note clock ACCEPT, /health scope ACCEPT.
