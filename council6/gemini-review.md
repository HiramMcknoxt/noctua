# Round 6 — Gemini seat review of NOCTUA 1.2.2 (archive, substance-preserving)

Seat: Gemini, **Neon High** (Thinking High) — best included model; Carbon
shown locked behind the paid Ultra upgrade, declined per protocol.
Static code audit only — no local execution environment in that session.
Chat: https://gemini.google.com/app/5dd065665ecabde1
Full verbatim text: browser handoff of Nov 24, 2026, 12:54 PM CST (also in
~/workspace/agents/0847f038-cfbc-4eb1-b271-f33f7534ec1d/subagent-output/).

## Verdict: NOT CONVERGED — criteria 1 FAIL, 2 FAIL, 3 FAIL, 4 PASS mechanically / INSUFFICIENT substantively
4 DEPLOYMENT-BLOCKING, 4 CODE-CRITICAL, 12 MINOR.

## DEPLOYMENT-BLOCKING
- F1 (Q22): compact.py high-water mark breaks every SECOND cross-audit
  against a healthy partner: Run 1 saves the live root (seq > checkpoint
  entries N, since a heartbeat + receipt land after the checkpoint); Run 2
  recomputes from_seq > to_seq (loop runs zero times, returns live hash),
  then compares live hash != cp root -> anchor_root False -> posts
  ok:False, closing the share gate on a healthy partner, exit 2. Tests
  missed it: suite runs compact.py once; q22's second run expects failure.
  [Vesper: code path confirmed statically — compact.py:103 while loop +
  :247 comparison. Runtime repro owed in the 1.2.3 battery.]
- F2 (Q23): rotation ceremony broken four ways — no commit-before-reveal
  phase barrier (last revealer grinds; unrevealed commitments overwritable
  via ON CONFLICT ... WHERE nonce IS NULL); total supervisor courier
  substitution (supervisor can submit commitment hash AND reveal for every
  partner, no partner auth or Ed25519 signature); permanent
  rotation_pending deadlock (withheld reveal past midnight or typo'd
  cycle_start -> publish 409s forever, new commit 409s, void never clears
  rotation_pending; recovery = manual SQL); ROTATION_VOID leaves
  rotation_contributions intact, forcing voided nonces onto the
  replacement cycle. [Converges with the Vesper seat's F1.]
- F3 (Q3/Q1): pin-audit-key crashes on real DBs (fragment vs frag —
  converges with Vesper F2, independently found); literal "PLATE|" legacy
  formula; PLUS janus.py's own _verify_key_against_stored_refs checks only
  normalize_plate + uppercased state, so a 1.1 suppression stored as
  "VIC 309" (hashed "VIC 309|AR") fails verification -> KEY_LOCKED even
  with the original key file present; the lockout error text still
  prescribes 1.2.1's removed file-trust remedy.
- F4 (Q1): _migrate_122 silently rolls back EVERYTHING on a
  hotlist_members PK collision: two legacy spellings canonicalizing to the
  same (plate,state,list_source,case_no) — "VIC 309"+"VIC309", "ar"+"AR" —
  make the per-row UPDATE raise IntegrityError; the whole repair pass
  (suppression re-keys, holds backfill, expiry parsing) rolls back inside
  the swallowed except, no chain entry/marker/log, /health ok — while
  DROP TABLE hotlist already committed. Also: active-into-nulled
  suppression merge leaves plate=NULL on the surviving active row, so
  _SUPPRESSED_SQL never hides the plate; legacy share_queries.case_ref
  never keyed by the migration.

## CODE-CRITICAL
- F5 (Q16): WHY Q16 was vacuous — q16_flush_phantom sets
  NOCTUA_AUDIT_SINK_DIR, an env var nothing reads (real: 
  NOCTUA_SENTINEL_SINK, sentinel.py:1235). [Vesper: CONFIRMED by grep —
  run_q122_cases.py:918 vs sentinel.py:1235.] Plus: _sink_record_error /
  _sink_record_ok UPDATE sink_state on Janus's non-autocommit shared
  connection after the pre-flush commit -> a write transaction leaks
  across requests (WAL writer lock held; cron jobs starve on
  database-is-locked) and _note_quarantine's `not db.in_transaction`
  check evaluates False after a recovery drain -> SPOOL_QUARANTINE entry
  silently dropped on the live server. (On the narrow phantom question:
  the mode=ro presence check does stop rolled-back rows in normal flow.)
- F6 (Q18): do_GET calls auth() OUTSIDE DBLOCK on the theory "auth() has
  no DB side effects" — false: auth() -> _reload_config() can
  chain.append(CONFIG_CHANGED / CONFIG_STALE) on the shared connection,
  and even anonymous callers trigger it; also chain_ok_cached() warms for
  ANY authenticated account before role authorization (a patrol account
  can trigger the 600k scan, once per 60s).
- F7 (Q17): compact.py recompute() and sentinel_audit.py audit_url()
  reimplement verification WITHOUT the v1 kind/ts-vs-payload cross-check
  that sentinel.py _verify_rows has — a partner serving a relabeled v1
  chain passes both "independent" recomputes. [Vesper: CONFIRMED by grep —
  the cross-check exists only at sentinel.py:1137.] Also q17's case wrote
  v2 entries only, never v1.
- F8 (Q5): same-plate supersede orphans PENDING hits — the same-plate
  branch inserts the new read but never updates hits.read_id, so a later
  different-plate supersede looks up hits by the NEW read_id, finds none,
  and the original PENDING hit is never withdrawn.

## MINOR (M1-M12, condensed)
M1 future-dated checkpoints pass the 26h gate (no negative-age bound,
unlike audit-result's -3600). M2 bare-metal restore self-vouches on the
backup's internal audit_key when no host key/pin exists. M3
_rotation_status mixes UTC and host-local dates. M4 Janus sched_doc omits
"pubkey" so --verify --pubkey-fingerprint always fails on Janus schedules;
nonces excluded from rotation_signed_portion (strippable). M5
_rotation_commit sets rotation_pending non-atomically (meta commit before
contributions insert). M6 scrubber false-positives badge-number usernames
(ofc.417 -> OFC417) and the pref: prefix check is a loose startswith.
M7 pre-lock DML beyond the DELETE: list_registry insert, sink_state init,
ensure_signing_key all run before _key_fingerprint_check. M8 exact
duplicate deliveries insert duplicate reads rows. M9 retention.py rmtree
before commit; expand_reason clock divergence retention vs registry.
M10 hotlist_sync Chain() missing key=key (scrubber would fall back to
unkeyed SHA-256). M11 sentinel_audit --url mishandles 0-entry checkpoints
(400 -> warn instead of GENESIS check). M12 HOLD_DAYS+30 can exceed 150
when HOLD_DAYS > 120 (needs min(HOLD_DAYS+30, 150)).

## Judgment rulings
(a) REJECT both-tree-pass as verified — five of the seven concealed real
defects (Q03->F3, Q16->F5, Q17->F7, Q18->F6, Q22->F1; Q02 missed M7;
only Q06 held cleanly).
(b) Q25 + A7 INSUFFICIENT — A7 doesn't cover bare-metal self-vouching
(M2) or the --pubkey-fingerprint paths; Q25 needs explicit lost-key /
bare-metal pin tests.
(c) Strip-not-raise ACCEPT. DDL on locked boots ACCEPT for DDL, REJECT
for pre-lock DML (move it after the fingerprint check). Supervisor
courier REJECT as implemented (needs partner Ed25519 signatures on
commitments/reveals). Disposition-note clock ACCEPT with the M12 cap fix.
 /health camera scope ACCEPT with a caveat (silent > RETENTION_DAYS
reverts to never_reported). Emergency Tier 3 instrument set ACCEPT.

## Forced change (price of this seat's vote)
Repair F1-F8 and gate 1.2.3 acceptance on a zero-vacuous adversarial
suite: every Q item fails on 1.2.1 (or proves absence) and passes on
1.2.3 against real multi-step lifecycles — two consecutive compact.py
runs; shared v1 cross-check in both tools; partner-signed phase-barriered
rotation with abort/expiry and void cleanup; pin-audit-key on a full
Janus schema; migration handling duplicate spellings/unnormalized
suppressions/nulled merges without silent rollback; real
NOCTUA_SENTINEL_SINK outage/recovery with zero leaked transactions;
lock-safe config reload + role-gated verify cache; same-plate-then-
correction supersede withdrawal.
