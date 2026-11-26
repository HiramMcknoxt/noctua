# NOCTUA Council Round 9 — Qwen seat review

Seat: Qwen. Model/effort per the browser operator's interface observation: Qwen4-Max, Thinking (highest) — the response text itself claims no model name is shown; per seat protocol the interface observation governs. Chat: https://chat.qwen.ai/c/48f9449f-67c3-4618-ba92-91e4bb0b2be2. Static code review, no execution. Files delivered in two messages (Qwen's 5-document-per-turn limit); all 8 in conversation before it answered. Returned Nov 25, 2026.

---

NOCTUA Council Round 9 — Qwen seat review of 1.2.6 (janus126/)
    
    Method note (citation format). The review pack arrived as flattened, unnumbered text. I cannot execute code in this session (no execution environment or file-write capability was provided), so this is a code-reading review per the assignment. Every citation below is file :: function :: exact source anchor — the anchor is the grep target; line numbers are approximate (≈) where given. I also could not create HANDOFF.md/run-next.sh (no filesystem access); that standing rule is unfulfillable in this seat's environment and is disclosed rather than silently skipped.
    
    1. Findings register (most severe first)
    
    F1 — BLOCKING (U6 defeated): a non-supervisor "submission" silently mutates an ACTIVE hot-list entry on primary-key collision
    
    janus.py :: H._post_hotlist() — the non-supervisor branch:
    
    1 "INSERT INTO hotlist_members(plate,state,list_source,"
    2 "case_no,category,added_by,added_ts,expires_ts,active,"
    3 "pending) VALUES(?,?,?,?,?,?,?,?,1,1) "
    4 "ON CONFLICT(plate,state,list_source,case_no) "
    5 "DO UPDATE SET category=excluded.category, "
    6 "added_by=excluded.added_by,added_ts=excluded.added_ts, "
    7 "expires_ts=excluded.expires_ts",
    
    The table's PK is PRIMARY KEY(plate, state, list_source, case_no) (janus.py :: db.executescript DDL). The conflict branch updates category/added_by/added_ts/expires_ts but never touches pending or active. The supervisor branch's identical upsert does set active=1, pending=0; the submission branch does not.
    
    Executed-shape reproduction (static trace, trivially runnable):
    Supervisor places STL777/AR/Local agency list/2027-1014, active, no expiry → 201.
    Detective POSTs /hotlist with the same four key fields, category:"x", expires:<yesterday> → 202 {"result":"submitted"}, HOTLIST_ADD_PENDING chained.
    The row is now active=1, pending=0, expires_ts=<yesterday>, added_by=<detective> — live, immediately. It appears in GET /hotlist with the detective's category/expiry.
    Next ingest of STL777: _hits_for_read's if m_exp and m_exp <= ts: deactivates it and chains HOTLIST_EXPIRED. The stolen-vehicle listing is dead. No supervisor ever approved anything; the response claimed "submitted for supervisor approval."
    
    This is the exact property U6 was commissioned to establish — "a pending entry matches nothing until a supervisor approves it" — inverted for the collision case: a non-supervisor can kill, re-expire, re-category, or re-attribute any live listing (including shortening expiry to disable alerts, or extending it past supervisor intent), and can overwrite another detective's pending submission the same way. The U6 battery case (u6_hotlist_uniform) only submits fresh plates, so it never exercises the collision. The schema's PK makes active+pending coexistence impossible for one key, which is why the builder chose overwrite; the correct shape is a no-op-plus-queue-record or a separate pending ledger, never mutation of the live row.
    
    Fix: the submission path must not update an existing active=1, pending=0 row at all (uniform 202, chain the submission, leave the live row byte-identical); regression case: submit against a live entry with a hostile expiry and assert the row unchanged and the alert still fires.
    
    F2 — BLOCKING (U1 regression): wrong-key attempts on /auth/2fa/pickup count toward the §10 lockout — unauthenticated, renewable account lockout is back
    
    janus.py :: H._totp_pickup():
    
    if not hmac_mod.compare_digest(
            sha(key), str(trec.get("key_sha256", ""))):
        _note_auth_fail(target)
        _auth_lock_note_failure(target)
    
    _totp_pickup is dispatched before need_auth (_post: if path == "/auth/2fa/pickup": return self._totp_pickup()), so it never passes through _lockout_counts — the U1 guard that requires a VERIFIED key. And _auth_lock_note_failure itself guards only existence and machine-role:
    
    if user not in USERS:
        return
    if roles_of(USERS[user]) <= set(SERVICE_ROLES):
        return
    
    Its docstring claims "The guard lives HERE as well as in need_auth's counting rule, so no future caller can reintroduce the shape" — but the key-verdict guard lives only in _lockout_counts, and this caller bypasses it. (The token-failure branch later in the same function also calls _auth_lock_note_failure, but there the key has verified, so that one is correct per U7.)
    
    Reproduction (static trace): 5× POST /auth/2fa/pickup {"user":"sgt.reyes"} with X-Noctua-Key: wrong → five 401s, _auth_locks["sgt.reyes"].fails==5, locked_until=now+900, ACCOUNT_LOCKED chained. The supervisor's correct key+TOTP now refuses everywhere (auth() → _auth_locked). Repeat every 15 minutes against every supervisor/auditor → permanent, unauthenticated lockout of the human surface; break-glass requires shell (provision.py unlock). This is Round 8's C8-01 attack resurfacing on the one endpoint U1's battery never sprays (u1_lockout_scope sprays /reads, which goes through need_auth).
    
    Fix: remove _auth_lock_note_failure(target) from the wrong-key branch (keep _note_auth_fail for evidence); add the key-verdict guard inside _auth_lock_note_failure itself so the docstring becomes true; regression case: wrong-key pickup spray locks nobody.
    
    F3 — BLOCKING (retention/registry hole, U13-adjacent): pre-restore WAL/SHM/key copies escape the registered glob and the schema allowlist
    
    scripts/restore.py :: main():
    
    def aside(path):
        if os.path.exists(path):
            os.replace(path, path + ".pre-restore-" + stamp)
    ...
    for suffix in ("", "-wal", "-shm"):
        aside(db_path + suffix)
    ...
    for suffix in (".audit_key", ".signing_key.pem", ".signing_pub.pem"):
        ...
        shutil.copy2(src, src + ".pre-restore-" + stamp)
    
    The registered store is sentinel.py :: PLATE_DATA_STORES:
    
    {"store": "pre-restore copies", "kind": "glob",
     "pattern": "<db>.pre-restore-*", "class": "reads",
     "action": "prune_copies"},
    
    <db>.pre-restore-* matches janus.db.pre-restore-X but not janus.db-wal.pre-restore-X, janus.db-shm.pre-restore-X, or U13's new key snapshots janus.db.audit_key.pre-restore-X / .signing_key.pem.pre-restore-X. Consequences:
    
    retention.py :: prune_glob() and sentinel.registry_breaches()'s glob branch never see these copies. A pre-restore -WAL copy contains plate data and sits past the 14-day reads class, unpruned and unflagged, until the next restore runs (restore's own end-of-run prune uses the broader ".pre-restore-" in name test — quarterly per OPERATIONS §9, so copies can outlive the cap by months). Key-material copies likewise accumulate outside escrow custody, unregistered.
    
    The build's own schema contract is violated by its own restore output: tests/run_tests.py :: suite_schema() allows a loose file only if name[len(base):] in sidecar_suffixes or name[len(base):].startswith(".pre-restore-"). For janus.db-wal.pre-restore-X the remainder is -wal.pre-restore-X; for the key copies it is .audit_key.pre-restore-X — neither passes, so the full-column/full-file allowlist fails on any directory that has been restored. No battery leg runs suite_schema against a restored dir, which is why this is green.
    
    Fix: widen the registry glob to <db>*.pre-restore-* (or register each suffix explicitly), mirror it in the schema test's sidecar allowance, and add a battery leg that restores, ages the copies, and asserts retention prunes + schema passes on the restored directory.
    
    F4 — MEDIUM: U2's auto-clear is reason-blind — a genuine checkpoint_disagreement fence clears when one actor edits the local checkpoints file
    
    janus.py :: _anchor_apply() clears any recorded mismatch on a clean evaluation, and _anchor_evaluate() returns clean when the disagreeing lines are simply gone:
    
    bad = [cp for cp in _bad_checkpoints(cps)
           if tuple(_checkpoint_id(cp)) not in accepted]
    if not bad:
        return False, {}
    
    After a rollback to an earlier snapshot, the pre-snapshot checkpoints still match the restored prefix. An actor with write access to the checkpoints file (no signing key, no second account) truncates the post-snapshot lines; the next 5-second evaluation is clean; _anchor_apply deletes anchor_mismatch and chains ANCHOR_CLEARED. The two-key _anchor_accept — whose whole point is that the auditor, outside the chain of command, confirms a disagreement — becomes optional. The builder's docstring discloses "or removed," but removal-without-acceptance is precisely the single-actor path T3's fence existed to stop; external witness copies still catch it later, yet the runtime fence lifts now. Fix: auto-clear only file-state reasons (checkpoints_malformed/unreadable/missing repaired); a checkpoint_disagreement clears only when every bad checkpoint id is in the accepted set.
    
    F5 — MEDIUM: users.json writes still use a fixed temp path (the U11(iv) fix was applied to the TOTP store only)
    
    janus.py :: H._totp_pickup(): tmp = USERS_PATH + ".tmp"; scripts/provision.py :: save(): tmp = path + ".tmp". Two concurrent pickups (or a pickup racing provision.py rotate-key) interleave os.write on the same path and os.replace a torn file. A corrupt users.json at next boot leaves USERS={} (boot reload fails stale with no last-good in memory) → nobody authenticates; a lost rotation with a consumed pickup strands the account. U11(iv) fixed exactly this shape for <db>.totp.json with unique temps; the users-file writers were missed. Fix: unique temp + os.replace in both writers (same pattern as _totp_save).
    
    F6 — MEDIUM (queued small ii, confirmed): _auth_fail_totals is an unbounded unauthenticated memory-growth vector
    
    janus.py :: _note_auth_fail():
    
    _auth_fail_totals[_user_hash(user)] = \
        _auth_fail_totals.get(_user_hash(user), 0) + 1
    
    One dict key per distinct sprayed username, before any cap, never pruned (_auth_fail_global is pruned; totals are not). _auth_fail_flushed also grows without bound (one (user,bucket) per flushed marker, plus ("suppressed",bucket) per minute, forever). /health reads only the top-10, so the structure can be bounded cheaply. Ruling below: FIX-NOW.
    
    F7 — MEDIUM (queued small iii, confirmed): raw hit ids in BLOCKED entries are partner-joinable to protected hits' time+place
    
    janus.py :: H._post_verify() chains BLOCKED {"hit": hit_id, "reason": "suppressed_queue"} with the raw integer. ALERT entries carry hit (same int), cam, category, ts. A Compact partner's chain_auditor — read-only on /audit by design — joins BLOCKED(hit=N, suppressed_queue) to ALERT(hit=N) and learns which camera saw a protection-order vehicle and when: plate-derived time+place, the exact class the registry exists to control, disclosed without the plate ever appearing. Keying the hit reference in BLOCKED (or omitting it for the suppressed_queue reason) breaks the join. Ruling below: FIX-NOW.
    
    F8 — MEDIUM (queued small i, confirmed and extended): destructive releases ride the anchor-fence safety set
    
    janus.py :: ANCHOR_FENCE_SAFETY_POST = {"/reads", "/suppressions", "/suppressions/release", "/holds", "/holds/release"}. During a suspected rollback, /holds/release makes evidence purgeable and /suppressions/release lifts a protection order — both are destructive/exposing acts, not safety writes. Placement and ingest belong in the set; releases do not (suppression release's two-key rule mitigates but does not justify fencing exemption). Ruling below: FIX-NOW for both.
    
    F9 — LOW: the U11 version sweep is incomplete, and the chain records a migration to the wrong version
    
    janus.py :: _migrate_124() chains MIGRATION {"to": "1.2.5"} and MIGRATION_DEFECT {"to": "1.2.5"}, and writes migration_status {"version": "1.2.5"} on a 1.2.6 boot — the permanent record names the wrong target version. scripts/sentinel_audit.py :: main() reports "version": "1.2.5"; janus.py :: _rotation_publish() and scripts/rotation.py :: build_schedule() stamp schedule documents "version": "1.2.5" (functionally harmless — the signed-portion gate only special-cases "1.2.2" — but the sweep's claim "every user-facing version surface names 1.2.6" is false, and u11_version_sweep checks only five surfaces). COMPACT.md's header says 1.2.6 while its second line says "1.2.4 is what the code does."
    
    F10 — LOW: U9's legacy-chain probe exempts the wrong boundary
    
    janus.py import-time probe: _DB_LEGACY_CHAIN_AT_IMPORT = not (isinstance(_first, dict) and _first.get("v") == 2). Hash-v2 arrived in 1.2.1, TOTP in 1.2.4. A populated, never-provisioned 1.2.1–1.2.3 database (v2 payloads, no second factor ever offered) is classified as a populated arrival and locked, while the comment justifies the exemption as "the 1.1 line had no second factor." Recoverable via shell bootstrap enrollment and named in health, but the rationale and the boundary disagree; key the exemption on the TOTP era (e.g., first SYSTEM version < 1.2.4), not on payload v2.
    
    F11 — LOW group (noted, not individually blocking)
    
    Escrow prune vs archival sets (scripts/backup.py :: run()): a --no-prune archival set survives, but the next pruning run deletes its escrow by age — the archival set becomes unrestorable. Prune escrows only when their paired set is pruned.
    
    ANCHOR_CLEARED atomicity (janus.py :: _anchor_apply()): the meta delete is committed before the chain append, whose failure is swallowed (except Exception: pass) — a clear can land unchained.
    
    TOTP store read-modify-write race (janus.py :: _totp_accept() on the lock-free pre-warm path): two concurrent same-code requests can both pass the counter <= last check before either saves; cross-process shell confirmation races likewise. Disclosed in TRACK-126 U11(iv) as "the T-battery documented posture" — I confirm it remains open; an flock around store RMW closes it.
    
    Pending-queue growth (_post_hotlist): HOTLIST_ADD_PENDING is unthrottled and pending rows (active=1) are never purged by purge_inactive; an authenticated detective can grow chain+queue without bound. Consider a per-submitter throttle.
    
    Superseded-hit report semantics: a PENDING_SUPERSEDED hit rejected by a supervisor becomes reviewed, confirmed=0 → counted as non_corresponding in the §1805 report, where 1.2.2's machine-withdrawn outcomes were excluded. Policy question for the Commission, not a code break.
    
    Sink mid-file damage below the tail is invisible to /health (only _sink_file_tail's final-line state and below-tail candidates are checked; sink_divergence() catches it but runs only on ceremony). Also sink_divergence() reads the file without the spool flock (transient torn reads possible), and .diverged-<second-resolution> archive names can collide.
    
    DEMO_MODE=1 on an unprovisioned populated arrival disarms _unprovisioned_locked() (it returns False under DEMO_MODE) — the explicit, loudly-named operator waiver, but worth one doc line tying U5 and U9 together.
    
    scripts/checkpoint.py :: _refuse_if_rewritten(): a final line that is valid JSON but not an object (null, [1,2,3]) raises inside c.get(...) → persistent checkpoint failure rather than truncation. Conservative/fail-closed; only truly torn (invalid-JSON) tails are healed.
    
    2. Rulings on §3
    
    §3.1 — U9 interpretation: RATIFY the populated-arrival line. The literal reading is incompatible with the ceremony and with every fixture; install_born_empty + never-served is a defensible, code-visible line, and the legacy exemption is the right kind of carve-out (its boundary is off — F10). Two residuals to carry: (a) a born-empty install that accumulates data and never provisions stays in ceremony state forever — the control is health-red + alert_check naming it, which holds, but INSTALL §8's go-live checklist has no "every human enrolled ACTIVE" checkbox; add one (this is also my answer to (iv)); (b) F10's boundary fix.
    
    §3.2 — queued smalls:
    (i) /holds/release out of the safety set: FIX-NOW. Confirmed (F8). Extend the same move to /suppressions/release — lifting a protection order during a suspected rollback is the same class of act; its two-key rule is a mitigation, not a fence exemption.
    (ii) Bound _auth_fail_totals: FIX-NOW. Confirmed unbounded (F6). Cap the dict (top-N + overflow aggregate), prune _auth_fail_flushed on bucket rollover. Cheap, and the chain-cap philosophy already demands it.
    (iii) Keyed hit refs in BLOCKED: FIX-NOW. Confirmed joinable (F7). Key the hit reference (or drop it for suppressed_queue); keep raw ints in the custody-relevant kinds so custody_excerpt still joins.
    (iv) Fence the data surface during the T1 ceremony state: PILOT-GATE. A full fence contradicts the ratified U9 ceremony line and the living battery; the enforceable form is the go-live enrollment checkbox plus the existing health-red/alarm. Revisit as FIX-NOW only if the Commission wants the ceremony window itself narrowed.
    (v) 24-hour expiry on pending pickups: ALREADY IMPLEMENTED — verify, no new work. _totp_pickup checks age <= 24 * 3600 against enrolled_ts inside token_ok. Add a regression case (expired token → 401, unconsumed); note the negative-age edge is clock-skew-only.
    (vi) enroll-2fa shell-operator honesty: CANT-DO. Correct classification. Whoever can read <db>.totp.json can compute any confirmer's code; shell two-key is a ceremony against a file-privileged operator, not a cryptographic bound. Document it beside the openssl-Path residual.
    
    §3.3 — S10 null-tolerance: ACCEPT as a test-only fix, bounded: retry a dropped (null) sample once, log the retry, and still fail if the retry is null or any returned sample is wrong. A dropped response under six saturating ingest threads on a 1.5-CPU VM is a client/harness artifact; the freshness property held in every returned sample across four full runs and both standalone passes. Holding the product accountable for a sample it never answered would make the battery measure the VM, not the bound.
    
    §3.4 — R-F diff review: RATIFY as standing process. I read every attached diff. All changes are (a) DET→SUP setup re-pointing that follows directly from U6 (and restores measurability — the orig r5_hotlist_expiry comment notes its measurements are vacuous against pending entries), (b) the T8 escrow key-path adaptation in attack2.py, (c) existence-guarded key removals in f11_restore_trust.py. No assertion is weakened, deleted, or re-aimed; the deliberately-unadapted 1.0/1.1 fixture scenarios are correctly left alone. One cosmetic nit: attack2.py.orig-124's header says "1.2.5 adaptation" while its siblings say 1.2.6. The practice — assertion byte-unchanged, change traceable to a commissioned custody change, original preserved, diff attached — is ratified.
    
    §3.5 — U6 validation order: RATIFY. Leak analysis: case_gate and plate-presence run first but are plate-class-independent; the registry check precedes any suppression evaluation (the amended requirement); the informative suppression refusal is supervisor-only, and supervisors are the role permitted to know an order exists; for non-supervisors every validation precedes the byte-identical 202, and is_suppressed affects only chain content, which is the disclosed audit-surface residual (keyed refs; partners cannot compute them, and cross-role correlation requires collusion that the chain itself records). The order is sound. F1 is independent of the order — it is the upsert, not the sequence.
    
    3. Convergence verdict
    
    | Criterion | Score | Basis |
    |---|---|---|
    | 1. No surviving deployment-blocking/critical code finding | NOT MET | F1 (U6 collision bypass), F2 (U1 lockout regression), F3 (retention/registry glob hole) — all code, all verified by reading, all with trivial reproductions |
    | 2. Every forced change implemented or answered in writing | PARTIAL | U2–U5, U7–U8, U10–U12, U14 verified implemented as commissioned; U1 fails on the pickup path (F2), U6 fails on collision (F1), U13's snapshot copies create F3 |
    | 3. Remainder is documented CANT-DO or routed legal questions | NOT MET | My blockers are code, not legal. (vi) is correctly routed to CANT-DO; the ACIC/attorney tracks are separate and do not bear on this vote |
    | 4. Orchestrator's own re-tests pass | MET | Builder + Vesper cold runs reconcile and pass; S10 flake characterized and accepted (§3.3). Coverage gaps noted: no pickup wrong-key spray, no pending-vs-active collision, no schema/retention leg on a restored directory |
    
    Overall vote: NOT CONVERGED — on code grounds only.
    
    4. Single forced change
    
    Fix F1: the non-supervisor submission upsert must never mutate an existing active membership. On PK collision with an active=1, pending=0 row, leave the row byte-identical, answer the uniform 202, and record the submission in the chain (a separate pending ledger or a no-op queue record — not an overwrite). Verified completion = a regression case where a detective submits a hostile expiry against a live supervisor listing and the listing's row is unchanged, the alert still fires, and the 202 is byte-identical to the fresh-plate case. This is the commissioned U6 property itself failing on the system's safety core; its repair most changes my vote. F2 and F3 remain blocking and must also be fixed before I would vote CONVERGED.
    
    5. Model and effort
    
    Model: the interface shows no model name. Effort: xhigh (as configured in this session).
    
    6. Coverage statement
    
    Read in full: 01-brief; 02-janus.py; 03-sentinel.py; 04-scripts-combined (all ten scripts); 05-docs-combined (CANT-DO, INSTALL, OPERATIONS, NETWORK, COMPACT); 07-track126-report + VESPER-VERIFICATION-126; 08-rf-diffs (every diff).
    Read in full within 06-tests: run_u126_cases.py, run_t125_cases.py, run_tests.py (structure + U-relevant suites). Sampled: Q/R/S batteries and run_load_envelope.py (case shapes and assertions, not every line).
    Not touched / not available: demo/seed_demo.py, tests/fixtures/janus10|janus11, council8/SYNTHESIS.md, the scratch logs and run-next.sh (referenced only). No code was executed — no execution environment was provided; all findings are static traces with grep-verifiable anchors. No HANDOFF.md/runner was created (no filesystem access in this seat).
