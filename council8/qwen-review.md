# Round 8 — Qwen seat review (as returned Nov 25, 2026, ~12:32 PM CST)

Chat: https://chat.qwen.ai/c/f535444c-fa7d-48f7-a398-4e6f884c362d
Model/effort (UI, browser operator's transcription): **Qwen4-Max, Thinking on**. The seat's own line says the interface shows no model name — the UI governs.
Method: CODE-READ ONLY (its pack omitted the test suites, disclosed up front); function-anchored citations with verbatim snippets; cold-executable repro recipes supplied for each material finding.
Vote: **NOT CONVERGED** (criterion 1 FAIL, 2 PASS, 3 FAIL, 4 PASS on the brief's record).
Seat history: blocked twice on the Access Verification slider (Security Round 1 and this round); Corey solved the slider by hand Nov 25 ~12:20 PM CST and the seat ran in the staged tab with its five pack files intact.

Orchestrator verification (Vesper, Nov 25):
- **F1 CONFIRMED in code**: sentinel.py `_sink_file_tail` ends `except Exception: return 0, None` — a torn last line is indistinguishable from an absent sink; `_deliver_locked` (line 1823) `elif file_seq == 0 and tail_seq:` takes the "vanished" branch and resets the recorded tail → full re-delivery into the existing file, duplicates, ledger cleared, health green. No branch handles 0 < file_seq < tail_seq (truncated sink) — the missing range is never re-delivered.
- **F2 CONFIRMED in code**: restore.py's aside() moves the live .audit_key/.signing_key.pem/.signing_pub.pem to .pre-restore-* (header line 67), then reinstalls keys only `if "audit_key" in manifest["files"]` (line 430) / `if priv_name in manifest["files"]` (434) — and backup.py's T8 escrow split records only hashes under "key_escrow", so those conditions are false for every 1.2.5 set. Host keys are moved aside and never replaced; restore reports success.
- F3–F6 and the minor notes are code-consistent reads, carried into the addendum commission (U14, U11 additions, U6 amendment).

---

## Findings register

### F1 — HIGH (integrity/completeness of the witness mirror)
A torn or unparseable sink tail is conflated with an absent sink, triggering full-chain re-delivery; a non-empty sink behind the recorded tail is silently ignored. Health reports green over both. No attacker needed: a power cut mid-append or an ENOSPC partial write (OPERATIONS §8's named failure mode) leaves a torn final line. Chain._sink_file_tail returns (0, None) on any parse failure of the last line; _deliver_locked treats that exactly like a vanished file (tail_seq reset to 0, whole chain re-appended to a sink that already holds it, ledger cleared, _sink_record_ok, sink_status ok=1 pending=0, /health sink_up=True). The mirror then contains every entry twice plus a torn fragment; nothing downstream detects duplicate seqs. Second facet: a sink truncated but non-empty (0 < file_seq < tail_seq) matches neither branch; entries (file_seq, tail_seq] are missing from the mirror and never re-delivered, health green. The T3 below-tail check covers hash divergence at a seq the file still holds, not tail loss. SPOOL_QUARANTINE covers torn spool lines, not sink lines.

### F2 — HIGH (availability / the restore ceremony)
restore.py moves the host's audit and signing keys aside unconditionally and reinstalls keys only when the set carries them — which a 1.2.5 escrow-split set never does. Every 1.2.5 restore leaves the host keyless and re-mints the signing identity. File-key deployment: _audit_key() finds nothing, has_rows=True → KEY_LOCKED "missing" → exit 3. Env-key deployment: ensure_signing_key mints a fresh keypair; _bad_checkpoints compares every historical checkpoint's fingerprint to the new key → all mismatch → anchor_mismatch → the data surface fences (503). The header's claim ("a restore uses the HOST's keys") is contradicted by the code. Why the battery misses it: the re-enroll/pickup/health endpoints are fence-exempt, so the S11 restore ceremony passes while fenced; and a test instance that never published a checkpoint has an empty checkpoints file, so no disagreement ever evaluates. The defect manifests only where daily checkpoints exist — production. Compensating: fail-closed, recoverable via pin ceremony + escrow, copies retained 14 days. But the ceremony's happy path is broken and the tool reports success.

### F3 — MEDIUM (availability, growing without bound)
The T3 live anchor evaluation verifies EVERY checkpoint's Ed25519 signature via an openssl subprocess under DBLOCK on a 5-second cadence. The checkpoints file appends daily and is never pruned: ~90 spawns per window at pilot scale; ~1100 (tens of seconds under the global lock) at 3 years — past the bridge's 10 s timeout. The shape S5/Q18/R4 moved chain verification off the lock to kill, reintroduced in the newest feature. Fix direction: memoize verification per checkpoint content, evaluate only newer checkpoints, or run the live eval on the detached read-only path like chain_ok_cached.

### F4 — LOW (auth boundary)
_totp_pickup and the re-enroll target check omit the disabled test auth() enforces. A disabled account's stolen key can burn a live pending pickup and collect the secret + recovery codes + rotated key. Impact deferred to re-enablement; one-line mirror fix.

### F5 — MEDIUM (confidentiality of protection-order existence)
The /hotlist oracle is sharper than R-B: _post_hotlist evaluates suppression (→ 404) BEFORE the list-registry check (→ 400), so a bogus list_name gives a side-effect-free 404-vs-400 existence probe — nothing added, no HOTLIST_ADD chained. Mitigation: validate the registry before the suppression check (uniform 400 for bogus lists); the valid-list path's one bit is the inherent R-B residue.

### F6 — LOW (alerting honesty)
alert_check.py has no named reason for migration_status.state == "incomplete" (it names only migration_unrepaired) — an incomplete-migration boot holds health down with only the generic "no named reason" line.

### Minor notes
"cameras": [] / "jobs": [] treated as unbound (converges with DeepSeek's nuance); sentinel.totp_code lacks the base32-padding tolerance janus._totp_code adds (auditor tooling can crash on a foreign unpadded secret); _sql_order_covers returns 0 (fail-open) on any exception — no reachable trigger found, but a suppression predicate should fail closed; read_newest_checkpoint accepts bool entries via isinstance(int).

## Residual rulings
- **R-A — DEFECT, Medium, closable in code** (dissents from the round's ratifications): _consume_restore_marker can read the outgoing live DB's .pre-restore-* copy — if the outgoing install was provisioned, force must_reenroll regardless of the incoming DB's marker. RESTORE chaining + health-red + alerting are compensating controls, so not vote-blocking alone, but it should be closed, not ratified. *(Orchestrator: ADOPTED — see addendum U13.)*
- **R-B — RATIFIED** with the F5 sharpening: one bit is inherent to any add endpoint; fix the free variant by reordering validation.
- **R-C — RATIFIED** as a deployment decision, with a docs gap: the INSTALL §8 go-live checklist does not require bound identities — add the checkbox.
- **R-D — RATIFIED, conditional on F4.** (Dissent from Claude's defect ruling and U7, recorded.) Optional hardening: rotate the API key at re-enroll request time for suspected-compromise cases.
- **R-E — RATIFIED** for the pilot, with the F3 caveat (the anchor scan erodes the headroom monotonically; also retention_breach() runs full scans under DBLOCK — same off-lock treatment eventually).
- **R-F — RATIFY in principle**, conditional on the orchestrator diffing the two adapted files (its pack omitted the suites). *(Orchestrator: the cold seat already diffed them — assertions intact; condition satisfied.)*

## Judgment calls
(a) ACCEPT the ceremony design; close R-A via the pre-restore marker check. (b) ACCEPT the fence line (safety writes proceeding is the R12 line; moving it is strictly worse). (c) ACCEPT strict out-rank as built (dissents from Claude's U4 queue-preservation shape — recorded; the not-stored-as-version detail is the crucial part). (d) ACCEPT the split, conditional on F2 (restore must leave host keys in place or install escrow keys). (e) REQUIRE the fault-injection case anyway — the absence-proof's premise is falsifiable (write contention can raise out of sink_status via _book_conn's DML; the branch fails closed correctly, but the reasoning is wrong and the case is cheap). (f) ACCEPT named degradation; RECOMMEND a loopback bind guard for demo mode (hardening, not blocking) — dissents from Claude's boot-refusal shape; U5 already adopts the stronger form.

## Verdict
Criterion 1 FAIL (F1, F2), 2 PASS, 3 FAIL, 4 PASS on the brief's record. **NOT CONVERGED.**
**Single forced change: fix the sink tail reconciliation (F1)** — _sink_file_tail must distinguish absent/empty from unparseable-tail (recover the last valid line, or fail closed preserving the obligation; never (0, None) for a non-empty file); _deliver_locked must treat 0 < file_seq < tail_seq as a named divergence (obligations preserved, sink_state.ok=0). Two discriminating fault-injection cases (torn tail; truncated non-empty) that fail on 1.2.5. F2 also meets the blocking bar and is expected fixed in the same pass. Vote flips when F1 is fixed with both cases green and F2 is fixed or formally dispositioned.
