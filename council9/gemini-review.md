# Gemini seat — NOCTUA Council Round 9 review (on 1.2.6)

- Seated: Nov 25, 2026, ~20:32–20:46 CST (browser task, Goliath Chrome).
- Chat: https://gemini.google.com/app/607255d2abba86e6
- Model/effort (operator-observed in the UI; governs per seat protocol):
  model picker "Neon High" — "Deeper analysis 4 Neon", Thinking level:
  High. ("Carbon" was locked behind a $99.99/mo Pro Ultra upgrade; not
  available on Corey's plan.) The seat's own §5 self-report says "the
  interface shows no model name" — recorded as another instance of
  unreliable seat self-identity; the operator observation stands.
- Coverage (seat's own statement): read 01, 03, 04, 05, 07, 08 in full;
  02-janus.py.txt truncated at the start of _share_query(); 06-tests
  truncated inside run_t125_cases.py. NO execution environment —
  all findings are code-inspection, reproductions supplied for
  orchestrator execution. Claims are therefore UNVERIFIED until
  executed or chair-read, per council rule.
- Vote: NOT CONVERGED (code grounds). U9: REJECT as shipped.
  §3 rulings: (i) FIX-NOW, (ii) FIX-NOW, (iii) FIX-NOW,
  (iv) FIX-NOW (subsumed by literal U9), (v) FIX-NOW,
  (vi) CANT-DO — all matching the chair's synthesis tally.
  S10: ACCEPT with conditions (retry only on transport drop, never on
  an HTTP 200 with chain_ok null; record retry count).
  R-F: RATIFY (assertions preserved) + hygiene adjustment (adaptation
  comment at top of file / manifest, not mid-file).
  U6 validation order: RATIFY (F3 persistence defect carved out).

## Findings (seat numbering) and chair mapping

- F1 CRITICAL — pickup wrong-key counts toward lockout.
  = Register V1 (executed by three seats in the main round). Agrees.
- F2 HIGH — U9 born-empty marker sticky + travels with DB copies;
  legacy seq-1 probe permanently exempts upgraded installs; share
  query not gated. = the executed U9 attack behind register V4;
  seat REJECTS U9 as shipped, consistent with the chair's ruling and
  the commissioned ceremony redesign.
- F3 HIGH — hotlist upsert mutates live entries. = Register V2,
  PLUS two extensions the main round did not log: (a) a submission
  colliding with an INACTIVE row returns 202 but can never surface
  in the pending queue (pending stays 0) — silent drop; (b) pending
  rows stored active=1 evade retention purge while hotlist_sync.py
  sweeps expired pending rows and chains HOTLIST_EXPIRED for entries
  that were never live. Extensions UNVERIFIED — queued for Round 10
  execution against 1.2.7 (whose V2 fix moves submissions to a
  dedicated pending table, which should moot both if implemented as
  commissioned).
- F4 HIGH — NEW. sink_divergence() discards the "unreadable" tail
  state: when the sink file is non-empty garbage with tail_seq == 0,
  _deliver_locked marks divergence and halts delivery, but
  sink_divergence() returns None, so POST
  /audit/sink-divergence-accept 409s forever and the operator cannot
  recover via the documented ceremony. Not in V1–V15 (V3 covers
  _sink_truncate_torn, a different function). Chair verification:
  see SYNTHESIS.md Addendum 1.
- F5 HIGH — NEW. _auth_locked() calls _auth_lock_persist() (DELETE +
  db.commit() on the shared connection) outside DBLOCK when a shell
  unlock is pending. Not in V1–V15. Chair verification: Addendum 1.
- F6 MEDIUM-HIGH — NEW. scripts/compact.py uses one global
  NOCTUA_TOTP_SECRET for two different human accounts on two
  different agencies' servers; a two-provisioned-agency Compact sync
  cannot authenticate both sides. Not in V1–V15. Chair verification:
  Addendum 1.
- F7 MEDIUM — _totp_pickup() never calls _reload_config() (disabled /
  rotated accounts can complete pickup off stale in-memory users) +
  fixed users.json temp path. Overlaps V11/V12 in part; the
  _reload_config half is new. Queued for Round 10.
- F8 MEDIUM — _sink_truncate_torn first-unparseable truncation.
  = Register V3 (executed by both Claude seats). Agrees.
- F9 LOW-MED — version residues. Overlaps the chair's version-literal
  adjudication residues (sentinel_audit version, migration stamps)
  + one new trap: scripts/rotation.py --verify hardcodes the
  accepted version prefix list ("1.2.2".."1.2.5"), so publishing a
  "1.2.6" schedule without extending the list breaks verification.
  Queued for Round 10 / V15-class smalls.
- F10 LOW — bundle: backup.py reverse-nesting (out_root inside
  escrow_root not refused; cf. V6 family), provision enroll_2fa
  disabled-check parity, config_closed() blocking anchor-exempt
  recovery POSTs (cf. V9 family), restore.py outgoing fallback
  (= V6, chair-verified in the main round), _auth_fail_flushed
  unpruned (= V8 family). Mostly register-adjacent; logged for
  Round 10 sweep.

## Seat's single forced change
Close the U1 lockout-scope bypass + the out-of-lock persist in the
auth/pickup lifecycle (its F1 + F5 + F7-entry fix), with F2, F3, F4,
F6, F8 and §3.2(i)–(v) shipping in the same patch.

Full verbatim text of the review is preserved in this chat's browser
handoff of Nov 25, 2026, 20:46 CST, and in the Gemini chat itself
(URL above).
