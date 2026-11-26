# Round 8 — Claude seat review (as returned Nov 25, 2026, ~12:00 PM CST)

Chat: https://claude.ai/chat/83f51921-935c-4dac-b2e8-2d229ae384fa
Model/effort (UI, browser operator's transcription): **Opus 5.5, Medium**. The seat's own line says it cannot see the interface and names Opus 5.5 from session context — the UI governs.
Method: the seat rebuilt the 1.2.5 tree from the attachments and EXECUTED repros through the T battery's own Boot harness (repro scripts + logs in claude-seat-r8-repro.tar.gz, retained in the chat; the REVIEW.md download attempt's outcome was unknown and was not retried).
Vote: **NOT CONVERGED.**

Orchestrator verification notes:
- C8-01 converges with cold-seat F-1 (same mechanism, independently executed) and extends it: supervisors are lockable too, so the cold seat's "supervisor-unlockable" mitigation fails when both supervisors are locked; /health ok_all does not consume locked_accounts. Severity: the seat says Critical, the cold seat said High — the synthesis carries Critical-leaning-High with the extension verified in code shape (need_auth counts every 401; unlock is supervisor-only).
- C8-02's mechanism checks against janus.py:2037: anchor_fenced() returns the recorded flag FIRST (`if anchor_mismatch(): return True`) — live re-evaluation only runs when no mismatch is recorded, and _anchor_accept is the only deleter and refuses repair-class reasons. Executed by the seat end-to-end (repair + restart + fresh matching checkpoint → still fenced).
- C8-08's worst case ("corrupt store → key-only silently") is NOT SUSTAINED: _totp_required (janus.py:2561) makes every human owe a factor and auth() gates on provisioning state — on a provisioned install a corrupt store refuses (T1 design; the T battery's corrupt-store case executes 401). The residual hygiene item (fixed .tmp path, lock-free pre-warm writer) is real and matches cold-seat F-4; carried as a Low.

---

# NOCTUA Council Round 8 — Claude seat review of 1.2.5 (`janus125/`)

**Vote: NOT CONVERGED.** Two new availability defects survive execution. Both were introduced by 1.2.5's fail-closed work (T2 and T3/T6), and both break the stated guarantee **availability of alerts**. One can be triggered by an unauthenticated caller and permanently loses reads. The other can be triggered by a power cut and has no in-application exit.

## 1. Findings register (most severe first)

### C8-01 — Unauthenticated lockout of ingest, jobs, partner and supervisor identities. **Critical (availability of alerts; read completeness). New in 1.2.5 (T2).** EXECUTED — `repro/r1_lockout_dos.py`
- Attacker model: anyone who can reach Janus's HTTP surface. No credential needed. Usernames ship as defaults (ingest.local in frigate_bridge.py, jobs.local in alert_check.py/retention.py).
- Path: need_auth calls _auth_lock_note_failure(user) on EVERY 401 (janus.py:3840) — wrong key, missing TOTP, or no key ever presented. It counts any name in USERS (2802); machine identities not excluded. auth() refuses even correct credentials while the lock holds (2926-2931). The lock persists in meta (2780-2790); a restart doesn't clear it.
- Executed: five wrong-key requests each lock ingest.local, both supervisors, jobs.local for 15 minutes: a hot-listed plate passes, ingest gets 401, 0 hits; the second supervisor cannot unlock anyone (401); heartbeats 401; after restart, still 401.
- Reads are LOST, not delayed: the bridge is a pass-through (frigate_bridge.py:247-254), nothing retries or buffers; the § 12-12-1805 counters undercount.
- Detection lags: locked_accounts is in /health but NOT an input to ok_all (janus.py:7720-7750), so health stays green until the 6-hour camera-silence alarm, which blames the cameras.
- No audited break-glass: unlock is HTTP-only and supervisor-only (5093-5101); with every supervisor locked, the only exits are waiting or editing the live DB.
- Same mechanism, legitimate trigger (EXECUTED, r6): code reuse/stale-code presentations count as failures — a legitimate officer can lock herself out.
- Compensating control: ACCOUNT_LOCKED is chained (2811). That records the attack; it doesn't stop it.

### C8-02 — An anchor-fence reason of the "repair" class can never be cleared. **High (availability of alerts). New in 1.2.5 (T3/T6).** EXECUTED — `repro/r2_torn_checkpoint.py`
- checkpoint.py appends with plain open("a") + write + fsync (checkpoint.py:173-176); a crash mid-write leaves a torn final line.
- T6 classifies it checkpoints_malformed (janus.py:2172-2177); the fence refuses every data read/write incl. GET /hits, GET /reads, POST /verify (3986-4002, 7757-7766).
- _anchor_accept refuses every reason except checkpoint_disagreement (5192-5199) and says "repair the checkpoints file" — but the ONLY code that deletes the anchor_mismatch flag is _anchor_accept itself (5253-5255), and the recorded flag short-circuits live re-evaluation.
- Executed: after the torn line /hits 503, /verify 503, anchor-accept 409; after repairing the file exactly as instructed + restart: still 503/409; after a fresh good checkpoint with witness.matches_chain: true — still fenced.
- Same trap: checkpoints_unreadable, checkpoints_missing, anchor_check_error. In 1.2.4 these degraded health; in 1.2.5 they are a permanent outage of hit review. Only exit: hand-editing meta in SQLite — unchained, unaudited.

### C8-03 — After a sink divergence, every request rescans the entire sink file under DBLOCK; the divergence never heals. **High (availability, post-restore).** EXECUTED — `repro/r8_sink_rescan.py`
- _deliver_locked builds _sink_seq_hashes(), a full sink parse (sentinel.py:1719-1743); a diverged obligation is never deleted (1871-1876); flush_deferred runs inside DBLOCK after every request (janus.py:7782-7791).
- Executed cost per append: 0.0009 s empty sink; 0.17 s at 100k lines; 1.81 s at 300k lines. A plain read goes 2 ms → 526 ms at 300k lines; at ~1M lines ingest capacity falls to the deployment's average rate; the bridge's 10 s timeout (frigate_bridge.py:172) starts dropping reads.
- Trigger: any rollback under an existing sink, including an honest restore. No documented recovery; the code's only reset (move the sink aside, 1826-1832) is undocumented and loses the delivery record. sink_status names it (health red) but doesn't limit the cost.

### C8-04 — Redelivery: the ingest identity can still withdraw any PENDING hit by asserting a higher confidence. **High (alert integrity; F8).** EXECUTED — `repro/r9_redelivery.py`
- Rank is (event_type, conf), both caller-supplied (janus.py:4307-4321); float() accepts NaN, inf, and parseable strings, no range check.
- Executed: same event at 0.97 refused; at 0.99 hit WITHDRAWN; conf NaN against a 1.0 hit: WITHDRAWN.
- READ_SUPERSEDED chains withdrawn_hit_ids (4413-4419), but the PENDING alert leaves the review queue with no supervisor action.

### C8-05 — POST /hotlist: "404 plate not found" is still a unique protected-plate signal (R-B). **Medium.** EXECUTED — `repro/r5_hotlist_oracle.py`
- Every unsuppressed plate gets 201 (janus.py:4538-4553); 404 occurs only for a suppressed plate (4498-4500). Executed: protected → 404; five never-seen plates → 201 each. SUPPRESSION_CONFLICT chains with `by` — auditing a leak does not close it.

### C8-06 — NOCTUA_DEMO_MODE=1 on a provisioned install waives every human's second factor, silently. **Medium.** EXECUTED — `repro/r7_demo_2fa.py`
- _totp_required returns False whenever DEMO_MODE is set (janus.py:2569-2570). No boot check against the provisioned marker, no warning.
- Executed: provisioned install, supervisor key-only → 401; restart with DEMO_MODE=1 → 200. The waiver appears in the chain only as a missing TOTP entry. "T1 made 'delete one file' fail closed. 'Change one environment variable' now fails open, silently."

### C8-07 — Pickup is key-only: stolen key + live pending re-enrollment = full takeover. **Medium.** EXECUTED — `repro/r10_pickup.py`
- Pickup checks only the key (5029-5034) and returns the TOTP secret AND a new API key (5037-5041): the attacker ends with both factors; the holder's old key dies (also a lockout). One-time semantics + TOTP_PICKUP/KEY_ROTATED chaining record it; nothing prevents it.

### C8-08 — TOTP store written from the lock-free pre-warm through a fixed `.tmp` path. **Low.** EXECUTED — `repro/r11_totp_tmp.py`
- do_GET calls auth() outside DBLOCK for /health and /audit/verify (janus.py:7713-7716); auth() can write the store via totp.json.tmp (2540-2560). Interleaved writes could corrupt the store. (Orchestrator: the seat's "corrupt store → key-only" worst case is not sustained under T1 — see header note; the race hygiene point stands.)

### C8-09 — The chain_auditor's "second factor" lives in the job environment beside its key. **Low.**
- compact.py:74-108 and sentinel_audit.py:104-127 read NOCTUA_TOTP_SECRET from the job's environment, next to NOCTUA_API_KEY — both factors in one place for anyone who can read the job env/cron/process list. The one-code-per-step design also makes multi-request runs produce routine 401s/AUTH_FAILURE entries, noising the trail.

### C8-10 — Key escrow defaults to a sibling of the backup root; the custody isn't actually split. **Medium (pre-existing, surfaced by T4 work).** EXECUTED — `repro/r12_escrow.py`
- backup.py:227-230 places the default escrow beside the backup root. Anyone with the backup directory has the backup and its keys. Fix: default escrow outside the backup tree; refuse a path inside it.

### C8-11 — Documentation drift on key custody. **Medium (pre-existing), plus three Low items.**
- INSTALL.md §6 says checkpoints are "HMAC-signed with this key [NOCTUA_AUDIT_KEY]" — they are Ed25519-signed with NOCTUA_CHECKPOINT_KEY (checkpoint.py:1-40). OPERATIONS.md §10 says unlocks are "Administrator actions"; the code requires a supervisor (5093-5101). COMPACT.md is labeled "as implemented in 1.2.4". INSTALL.md §7 omits the escrow split.

### C8-12 — T4's absence-proof premise is false for environmental faults. **Low.** EXECUTED — `repro/r12_t4_fault.py`
- A directory at <sink>.spool makes sink_status() raise IsADirectoryError (sentinel.py:1697-1699); the absence proof never exercises it. It proves absence only for the faults it enumerates.

### C8-13 — Scrubber: digit look-alikes are not folded. **Low.** EXECUTED
- BYX12З (Cyrillic Ze for 3) passes _contains_plate. The scrubber exists to keep plates out of logs; a miss is a privacy leak, not a security hole.

## 2. Rulings on the named residuals
- **R-A — RATIFIED, with one cheap tightening.** Executed (r3): restore.py never overwrites the live checkpoints file (71-74, 441-447), so the rollback is caught if that file survives. If it doesn't, key-only auth returns on a populated DB (only /reads and /hits gated). Tightening: key-only ceremony only while no plate data exists (see (a)).
- **R-B — DEFECT, not inherent (C8-05).** Fix: (i) every non-supervisor add returns 202 "submitted for supervisor approval" uniformly, listing the plate in the supervisor's pending queue; (ii) accept and store the entry (S3 makes its hits born-suppressed). A fake 201 fails because GET /hotlist shows the whole list (7906-7920) — hence the 202 shape.
- **R-C — RATIFIED, for a reason the report doesn't give.** One central Frigate/bridge serves all nine cameras (NETWORK.md §1), so a single identity bound to nine cameras ≡ unbound; binding buys nothing until per-site bridges exist. Jobs binding IS meaningful (each script takes its own NOCTUA_JOBS_USER) — make "one jobs identity per job" an INSTALL §8 checkbox. No code change.
- **R-D — DEFECT, Medium (C8-07).** Fix: pickup also requires a one-time token from the configuration channel (the channel that delivered the original key), or a supervisor's co-signature.
- **R-E — RATIFIED for steady state** (executed: 50 plain reads added 0 chain entries; the envelope has ~10× headroom); **the post-divergence state is a separate defect (C8-03).**
- **R-F — RATIFIED with a standing condition** (keep each adapted file's original beside it with a one-line reason), **and one rejection**: the re-pointed T7 assertion certifying the non-supervisor 404 is the R-B leak written into the suite — change it to the 202 shape, don't ratify it.

## 3. Judgment calls
- **(a)** Accept the provisioned-marker shape, with: /reads refuses (503, chained) on a non-demo unprovisioned install, and key-only human auth only while reads and hits are empty. Capture is gated behind go-live anyway; this closes R-A's populated-DB ceremony hole.
- **(b)** Accept the fence line; reject the missing exit (C8-02). For checkpoints_malformed/unreadable/missing: re-evaluate and auto-clear when the file is well-formed and the chain matches; for anchor_check_error, persist only after N consecutive failures. checkpoint.py should write via temp + atomic replace, or truncate a torn final line on open.
- **(c)** Keep strict out-rank for currency; stop letting a supersede REMOVE an alert — the old PENDING hit becomes PENDING_SUPERSEDED and stays in the review queue until a supervisor disposes of it, linked to the new hit. Clamp conf to finite [0,1], reject otherwise with 400.
- **(d)** Accept the split; require it to be one (C8-10): default escrow outside the backup root, refuse inside. Escrow encryption is separate hardening, not a substitute.
- **(e)** Require the fault-injection case (C8-12): directory-in-place-of-file, permission denied, full disk in the T battery.
- **(f)** Named degradation is not sufficient (C8-06): refuse to boot with DEMO_MODE=1 when the DB carries totp_provisioned, and chain DEMO_MODE_REFUSED. (Localhost binding doesn't help — production also binds 127.0.0.1 behind the proxy; a banner is cosmetic.)

## 4. Verdict against the convergence criteria
1. FAILS — C8-01 (Critical) and C8-02 (High) survive execution; C8-03/C8-04 are live defects.
2. MET IN FORM — T1–T9 implemented or answered; but form is not substance where the implementation introduces C8-01/C8-02.
3. FAILS while C8-01–C8-04 stand — code defects with code fixes, not CANT-DO.
4. Accepted on the orchestrator's record.

**Vote: NOT CONVERGED.**

## 5. Single forced change
**Make the T2 lockout count guesses at the second factor, never mere 401s.**
- A failure counts toward the 5-strike lock ONLY when the presented key verified, the account is human, and the second-factor code was wrong or missing after a valid key. A wrong key, a missing key, or a pre-key request never counts.
- Machine identities (ingest, jobs, partner) are NEVER locked. Wrong-key attempts are throttled per-source-IP, not per-account; a lock on a machine identity is a configuration error.
- Add a shell-side, chained `provision.py unlock` as audited break-glass (requires the same physical access as provisioning).
- Locked human accounts become an input to /health ok.
- Discriminating cases: r1's shape (keyless spray must not stop ingest) and r6's shape (legitimate code reuse must not lock the officer out).
- C8-02 independently fails criterion 1; its (b) fix must land in the same build.

**What would change the vote:** C8-01 and C8-02 fixed with their repros added as discriminating T-battery cases; C8-03 and C8-04 fixed or answered with a code change (not a docs note).

## Legal / institutional notes (routed, not decided)
- Path B / CJIS advanced authentication assumes lockout semantics an unauthenticated caller can't switch off — C8-01 is also a CJIS-AA compliance risk. Route to Ben.
- C8-01's lost reads undercount the § 12-12-1805 "plates scanned" total with no record of the loss. Route to the statutory-reporting owner.
- C8-01 partner lockout and C8-07 pickup takeover affect Compact partners. Route to the Compact liaison.
