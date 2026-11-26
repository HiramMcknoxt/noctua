# NOCTUA Round 7 — Gemini seat review (UI: Deeper analysis 4 Neon, Thinking High; model line declines to name a UI string)
Retrieved Nov 24, 2026, 11:20 PM CST via browser seat. CODE-READ ONLY.
Verdict: NOT CONVERGED (criteria 1-3 FAIL, 4 PASS mechanically/insufficient).

Seat: Gemini (NOCTUA Council, Round 7 — Review of Build 1.2.3)
    
    Model & Thinking Setting: Gemini — the exact UI model variant and thinking-effort dropdown label are not exposed inside this model runtime context, so I will not guess a UI string.
    
    Execution Mode & Handoff Status: Code-read only (no shell, Python interpreter, or local working filesystem is available in this chat session). Because no filesystem is writable here, HANDOFF.md cannot be created on disk; this header records seat, build (1.2.3), scope (Probes 1–5, Judgment Calls a–c, Qwen residuals, R1–R16), and complete delivery in this response. Every finding below is cited to exact file, function, and code path so the orchestrator can reproduce each one in minutes. 2FA is treated as out of scope per 2FA-SCOPE.md and does not enter the convergence vote.
    
    Named Probes (Code-Read Only)
    
    Probe 1 — The Rebuilt Q16 Sink Case & Qwen's Third Phantom Shape
    
    Qwen's third phantom shape (append() racing a handler's rollback()): Within janus.py as wired, this shape is structurally blocked by DBLOCK. Every serving call to chain.append(), db.commit() / db.rollback(), and chain.flush_deferred() runs inside with DBLOCK: (do_POST, do_DELETE, do_GET), and R4 removed all DB/chain writes from _reload_config(). At the standalone sentinel.Chain class boundary, however, self._lock does not guard an external caller's conn.rollback() on a shared connection, so safety remains a caller-locking contract rather than a class-level invariant. (Minor boot-time quirk: if CHAIN_SCRUB_FLAG fires inside _scrub_flag_due() on a default-isolation connection outside a request wrapper — e.g., _consume_restore_marker() with a plate-shaped backup name — INSERT INTO scrub_state implicitly opens a transaction on self.db that nothing commits until the first request.)
    
    DEFECT F1 (Code-Critical) — Multi-process last_streamed_seq watermark permanently drops committed entries from the sink: In sentinel.py Chain.flush_deferred(), watermark = self._watermark() loads sink_state.last_streamed_seq once (if self._watermark_cache is None:) and skips streaming any entry with entry["seq"] <= watermark. sink_state.last_streamed_seq is a global scalar max shared across every process touching the DB (janus.py, scripts/retention.py, scripts/hotlist_sync.py). Reproduction: retention.py (or hotlist_sync.py) opens db, appends RETENTION_PURGE at seq = N, and runs db.commit(). Before retention.py executes the next line (chain.flush_deferred()), live janus.py commits a normal POST at seq = N + 1, calls chain.flush_deferred(), streams N + 1, and persists sink_state.last_streamed_seq = N + 1. retention.py (whose _watermark_cache is None) now calls flush_deferred(), reads watermark = N + 1, hits if entry["seq"] <= watermark: continue (N <= N + 1), and permanently drops committed RETENTION_PURGE (seq = N) from the sink. The same drop hits janus.py itself on its first transactional flush after boot if a cron job commits and flushes N + 1 first. Neither Q16 nor R5a catches this because both run a single janus.py process with no concurrent retention.py / hotlist_sync.py writer.
    
    DEFECT F2 (High) — Spooled rollback-twin duplication when the sink is down: In sentinel.py Chain._stream(), self._note_streamed(e) is called only after a successful write to self.sink_path — never in the except OSError: branch that writes to self.spool_path. If flush_deferred() processes two queued entries sharing (seq, hash) (the R5b rollback-twin shape) while the sink is down, the first entry spools without populating self._streamed or advancing self._streamed_max, so the second entry passes both checks and is appended to the same spool file; when the sink recovers, the spool is replayed without re-checking, duplicating the entry. r5_twin missed this because it ran with the sink up.
    
    Probe 2 — Protection Orders as Records (R1) & Migration Recovery (R2)
    
    Native, migrated, and mixed overlapping orders (R1): The schema rebuild (id PRIMARY KEY AUTOINCREMENT, UNIQUE(plate_ref, order_ref)), _post_suppression() conflict target (plate_ref, order_ref), per-order _post_suppression_release() (refusing ambiguous plate-only release with 400 when len(rows) > 1 and updating WHERE id=?), and retention.py null_after_release (filtering active=0) are sound for orders with plate text.
    
    DEFECT F3 (Deployment-Blocking) — Recovered 1.1 plate-less protection orders leave plate_ref on the broken legacy hash, bypassing hit/verify/export/release protection on the entire first boot: In janus.py _migrate_123() -> _supp_repair():
    
    if match:
        db.execute("UPDATE suppressions SET plate=? WHERE id=?", (match, sid))
        recovered += 1
    
    It writes plate = match and forgets to update plate_ref to plate_ref(match). Impact: After recovering a 1.1 plate-less order (plate IS NULL, plate_ref = legacy_plate_ref(KEY, plate, state)), /health reports migration_status.state == "complete" and unverifiable == 0. Yet suppressions.plate_ref still holds the 1.1 legacy hash, so is_suppressed() and hit_suppressed_now() return False for that vehicle for the entire lifetime of that boot: new hits are stamped suppressed=0, detectives can POST /verify (200) and POST /evidence/export (201) and POST /hotlist (201), supervisors do not see the hit in /suppressed-hits, and POST /suppressions/release returns 404 ("no active suppression"). Only a second restart re-keys plate_ref. Companion gap in _supp_repair: known collects only canonicalized plate values, never reads.plate_raw, so a 1.1 plate-less order hashed over spaced text ("VIC 309|AR") cannot be recovered even when reads.plate_raw contains "VIC 309".
    
    DEFECT F4 (Deployment-Blocking) — Active plate-less orders kept alive by R2 leak reads and hits through run_search() and GET /tier3/results/<id>: R2 keeps unrecovered plate-less orders active=1 (plate IS NULL) so orders 1.2.1 honored stay in force. GET /hits explicitly handles keyed-only orders by paging SQL batches through Python hit_suppressed_now() (active_suppression_refs()). run_search() (used by GET /search, POST /share/query, POST /tier3/approve, POST /tier3/emergency) and GET /tier3/results/<id> filter only in SQL via NOT EXISTS (SELECT 1 FROM suppressions s WHERE s.active=1 AND s.plate = reads.plate) and _SUPPRESSED_HIT_SQL (s.plate = hits.read_plate OR s.plate = hits.entry_plate). Because NULL = <plate> evaluates to UNKNOWN, every active plate-less suppression leaks reads and hits to detectives, Tier 3 results, and Compact /share/query).
    
    Probe 3 — The Rotation Ceremony (R6)
    
    DEFECT F5 (Code-Critical) — POST /compact/rotation/commit accepts unsigned partner nonce_hashes from a supervisor: _rotation_contribution() (POST /compact/rotation/contribute) enforces _authorized(), refusing unsigned supervisor commits for partner agencies (403, "transport is not authorship"). _rotation_commit() (POST /compact/rotation/commit) bypasses _authorized() entirely and writes every entry in the supervisor's nonce_hashes dict straight into rotation_contributions with zero partner signature check. A supervisor can lock out every partner's genuine commitment/reveal (any later genuine partner contribute gets 409, and genuine reveal gets 400 mismatch) — reproducing Round 6 Seat 2 F6b through /commit.
    
    DEFECT F6 (Code-Critical) — Post-reveal mutation of members and period_days restores schedule grinding: In _rotation_commit(), the freeze check is if any_reveal and hashes: return 409, and the same-cycle_start guard (if pdoc.get("cycle_start") != cycle_start:) permits repeat calls for the open cycle. Attack: After all members have committed and revealed, the supervisor knows every nonce. The supervisor POSTs /compact/rotation/commit with the same cycle_start, empty nonce_hashes: {}, and either a mutated period_days (7..120) or a chosen subset of members (e.g., dropping one revealed partner to alter sha({"members": ..., "nonces": ...})). Because hashes is empty, if any_reveal and hashes: is False; meta.rotation_pending is overwritten post-reveal, and POST /compact/rotation immediately publishes the ground schedule.
    
    DEFECT F7 (High) — Partner commitments/reveals are replayable after cancel or void (violates R6 single-use nonces): Both POST /compact/rotation/void and _rotation_cancel() execute DELETE FROM rotation_contributions WHERE cycle_start=?, and partner signatures cover only {"agency", "cycle_start", "kind", "nonce_hash"|"nonce"} with no ceremony/attempt ID. After cancelling or voiding a cycle, the supervisor can open a fresh commit for the same cycle_start and replay a partner's already-revealed signed commit + reveal while substituting a new home nonce to change the resulting schedule.
    
    DEFECT F8 (Code-Critical) — Witness designation breaks for every Compact with n >= 4 cities: Both POST /compact/witness and _rotation_status() compute:
    
    _others = [m for m in members
                    if m not in (round_rec.get("auditor"),
                                 round_rec.get("audited"))]
    designated = _others[0] if len(_others) == 1 \
        else round_rec.get("auditor")
    
    len(_others) == 1 holds only when n == 3. For every 4+ member Compact (len(_others) >= 2), designated falls back to round_rec.get("auditor"): the auditor is forced to self-attest, while every genuinely independent non-participating member is rejected with 400.
    
    Probe 4 — The Pin Ceremony (R3) on a Quiet Install
    
    DEFECT F9 (High) — The boot-refusal message names two remedies, and BOTH fail as printed: In janus.py if __name__ == "__main__": under KEY_LOCK_REASON == "unpinned_key_over_existing_chain": "write the key to the file %s.audit_key (mode 0600) and restart" — dead remedy. Q3 deliberately removed file-based trust-on-first-use in _key_fingerprint_check(), so restarting with .audit_key hits the exact same refusal. "python3 scripts/provision.py pin-audit-key --db %s --fingerprint <sha256...>" — omits the mandatory --confirm flag, so scripts/provision.py exits immediately with "refusing: --confirm is required".
    
    Tier 3 fragment verification on a quiet 1.1 install: _verify_key_against_stored_refs() in janus.py and pin_audit_key() in scripts/provision.py check sentinel.frag_ref(key, frag) in chain_refs where chain_refs collects payload["plate_ref"] from audit and frag comes from tier3_requests.plate_fragment (NOT LIKE 'pref:%') and case_searches.frag. If the 1.1 DB's Tier 3 fragment is still un-scrubbed and 1.1 chained frag_ref under "plate_ref", verify-don't-proxy will match it. Two caveats the orchestrator should verify (since tests/fixtures/janus11/janus.py is not attached): (a) r3_pin in run_r123_cases.py only tested /suppressions + /search, never a Tier 3-only 1.1 DB; if 1.1 stored a pending/denied tier3_requests row without chaining plate_ref (or under another key), checked > matched will make both janus.py and provision.py --confirm refuse the correct key; (b) if retention already scrubbed plate_fragment to 'pref:...', checked == 0, triggering the broken boot-refusal message above. Minor parity nit: janus.py queries suppressions WHERE plate IS NOT NULL while provision.py adds AND plate != ''; neither excludes plate_fragment = ''.
    
    Probe 5 — The imperator Guard
    
    DEFECT F10 (Deployment-Blocking) — Three independent bypasses allow imperator, multi-role god accounts, or the demo flag itself to take effect in a non-demo production installation:
    
    Runtime hot-reload bypass (direct breach of the guard): _imperator_guard() is called only once at boot in janus.py, never in _apply_config() or _reload_config(). Boot Janus on a clean non-demo users.json (or with users.json transiently unreadable at boot so USERS == {}), then append {"user": "imperator", "roles": ["detective", "patrol", "supervisor", "auditor", "chain_auditor", "in... to the bare production list (USERS_DEMO stays False). The next request runs auth() -> _reload_config() -> _apply_config("users", ...), loading imperator live with all roles and zero refusal.
    
    Rename / arbitrary multi-role bypass: _imperator_guard() checks only the literal string "imperator" in USERS, while _apply_config("users", data) accepts "roles": [...] on any user in a non-demo config and roles_of() / only_role() honor it unconditionally. Naming the account "Imperator" (capital I) or adding "roles": [...] to any existing account in a bare production users.json boots cleanly with exit 0 and grants full god-mode (including lifting the chain_auditor identity fence).
    
    Self-asserting demo flag (no external gate, invisible in audit and /health): _apply_config("users", data) sets USERS_DEMO = bool(data.get("demo")) purely from the JSON file itself, with no server-side/environment opt-in (e.g., NOCTUA_DEMO_MODE=1), no refusal or degradation in /health, and no demo flag recorded in SYSTEM or CONFIG_CHANGED. Wrapping any production users.json in {"demo": true, "users": [...]} — at boot or via hot reload — silently licenses imperator (and would silently waive TOTP once 2FA-SCOPE.md lands).
    
    (Bonus note on imperator itself: because imperator holds "auditor" in roles, _run_tiered_search() rejects imperator on GET /search with 403 "auditors verify the system; they do not search it", and /tier3/review always enters the auditor branch first.)
    
    Unimplemented Commission Items & Secondary Findings (Code-Read Only)
    
    DEFECT F11 (High — Qwen Residual #3 unimplemented) — _strict_id() overflow causes unhandled HTTP 500: janus.py _strict_id() accepts negative integers (-1), integers > 2**63 - 1 (triggering unhandled OverflowError: Python int too large to convert to SQLite INTEGER -> 500 on /verify, /outcomes, /holds, /tier3/*, /evidence/*, /report?snapshot=), and > 4300-digit strings (triggering unhandled ValueError in Python 3.11+ int() -> 500). The same unbounded int() appears in GET /tier3/results/<id> and GET /audit/range.
    
    DEFECT F12 (High — Qwen Residual #2 unimplemented) — Destroyed-on-paper evidence bundles still on disk: sentinel.py registry_breaches() flags destroyed_ts IS NOT NULL + on_disk == True as a retention breach. Yet scripts/retention.py never deletes it (destroy_overdue_bundles filters destroyed_ts IS NULL; purge_orphan_bundles skips any bundle present in evidence), and POST /evidence/destroy returns 409 ("bundle already destroyed"). Furthermore, both POST /evidence/destroy and destroy_overdue_bundles() call shutil.rmtree() before db.commit(), so a DB rollback leaves evidence deleted unchained. (TRACK-123-REPORT.md names the Qwen residuals in its header but lists zero dispositions or tests for them.)
    
    Secondary findings (non-blocking): r14_load paired comparison bug (tests/run_r123_cases.py): Opens sqlite3.connect(dbp, timeout=60) without isolation_level=None and checks sum(landed) == 1000 and ver.get("ok") without checking ver["entries"] == 1000. As run_load_envelope.py itself documents, 1.2.2's Chain.__init__ DML leaves in_transaction=True, so 1.2.2 rolls back all 1000 appends at conn.close() while verify_detached returns {ok: True, entries: 0} — invalidating the reported 5.6 vs 1.9 appends/s comparison in TRACK-123-REPORT.md. run_load_envelope.py also uses Python threads (shared GIL) rather than separate OS processes.
    
    Unindexed hits.read_id under DBLOCK (R16): read_deletable() queries SELECT id, ts FROM hits WHERE read_id=? per read older than RETENTION_DAYS, and hits(read_id) has no index; /health calls registry_breaches() under DBLOCK. Add CREATE INDEX IF NOT EXISTS idx_hits_read_id ON hits(read_id).
    
    alert_check.py R12 wording & compact.py rewind check: alert_check.py still prints "configuration stale >24h — the data surface is FAIL-CLOSED" when only the 48h case feed is stale; compact.py recompute() should explicitly fail when to_seq < from_seq.
    
    Rulings on Judgment Calls
    
    (a) R6 witness rule (designated attester only): Sound in principle for n = 2 and n = 3, but broken in code for n >= 4 (see Defect F8). At n = 2, allowing the round's auditor to attest avoids stranding a two-city compact (which has no third member). At n >= 3, restricting attestation to a designated non-participating ("bye") member prevents collusion — provided the designation uses len(_others) >= 1 (e.g., deterministic _others[(round_no - 1) % len(_others)]) instead of len(_others) == 1, which currently forces self-attestation for every compact of 4+ cities.
    
    (b) R12 fence (stale case feed closes data reads, permits safety writes with chained warning): Right call. The CONFIG_FEED_STALE_WRITE warning plus /health degradation keeps the exception auditable.
    
    (c) Qwen's restore-atomicity claim: Narrow the claim; do not block convergence on a mid-swap fail-injection. restore.py genuinely pre-validates manifest signatures, file hashes, read-only chain integrity, and tar data_filter before touching any live file, and preserves moved-aside live files as *.pre-restore-<stamp>. Qwen is factually right that mid-swap shutil.copyfile / extractall I/O failures do not auto-rollback; docstrings and docs should say "pre-validated before swap (with .pre-restore-* backups preserved for manual recovery on mid-swap I/O failure)" rather than "failure-atomic".
    
    Convergence Verdict
    
    Criterion (1) — No surviving deployment-blocking or code-critical finding: FAIL. Deployment-blocking and code-critical defects survive in the imperator/demo boundary (F10), R2 protection-order recovery and plate-less search/Tier-3 filtering (F3, F4), R6 rotation ceremony and n >= 4 witness designation (F5, F6, F8), R5 multi-process sink watermark drop (F1), R3 boot-refusal remedies (F9), and the unimplemented Qwen residuals (F11, F12).
    
    Criterion (2) — Every prior forced change implemented or answered in writing: FAIL. R1 (standard orders), R4, R7, R8, R9, R10, R11, R12, R13, R15, and R16 largely hold, but R2, R3, R5, R6, the imperator guard, and the Qwen residuals are incomplete or unaddressed.
    
    Criterion (3) — What remains is documented CANT-DO limitations or legal questions routed to the City Attorney / ACIC: FAIL. All findings above are concrete code defects, not CANT-DO boundaries or legal determinations (2FA is excluded per brief).
    
    Criterion (4) — The orchestrator's re-tests pass: PASS (mechanically), INSUFFICIENT for convergence. All 7 legs pass in TRACK-123-REPORT.md, but the suites did not probe hot-reload/rename imperator bypasses, 1.1 plate-less order recovery, n >= 4 witnessing, post-reveal /commit mutation, multi-process sink flushes, or the Qwen residuals, and r14_load's baseline measurement is flawed.
    
    Overall Verdict: NOT CONVERGED.
    
    Single forced change (price of the Gemini seat's vote): Enforce the demo/multi-role boundary inside _apply_config("users", ...) on both boot and every hot reload, gated on an independent server-side opt-in (e.g., NOCTUA_DEMO_MODE=1, recorded in SYSTEM and surfaced in /health) rather than a self-declared JSON boolean in users.json — refusing both "imperator" (case-insensitive) and any "roles" multi-role array on any user unless server-side demo mode is explicitly enabled (and rejecting hot-reload transitions that introduce them). (For the orchestrator's next commission, F1–F9 and F11–F12 above should land in the same pass so Round 8 can converge cleanly.)
