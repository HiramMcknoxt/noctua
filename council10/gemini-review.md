# Round 10 — Gemini seat review (as returned)

- Chat: https://gemini.google.com/app/8b0a411793b43381
- Model/thinking, operator-observed in the UI: "Deeper analysis 4 Neon" (checked), Thinking level "High" (sub-label "Extra thorough"); prompt-bar button reads "Neon High". No paid Ultra tier selected. The seat's own §6 states the interface shows it no model name — the operator's UI observation governs.
- Method: INSPECTION-ONLY (as commissioned) — anchored code read with exact reproduction step-lists for executing seats. Coverage disclosed by the seat: files 01, 03, 04, 05, 07, 08 read in full; 02-janus.py.txt TRUNCATED inside `_rotation_contribution` — post-truncation paths (incl. _delete/_get dispatchers and the LAB boot refusal at janus.py:8557/8705/9527) rest on Vesper's verification record and are labeled as such in the review.
- Full verbatim return preserved at: ~/workspace/agents/0847f038-cfbc-4eb1-b271-f33f7534ec1d/subagent-output/f8edf835-ad66-408c-9302-ca1b483235ae-result-f521d938c92d.txt
- Vote: **CONVERGED.** No new deployment-blocking/critical findings. Single forced change: none.

---

## §3.1 — V1–V18 rulings

- V1 CONFIRMED FIXED — guard inside `_auth_lock_note_failure` (returns before touching _auth_locks when key_verified is false); pickup's locked branch uniform 401, wrong-key branch counts nothing, only the post-key bad-token branch counts.
- V2 CONFIRMED FIXED — conflict clause `WHERE hotlist_members.pending=1`; live rows untouched; uniform 202 + HOTLIST_ADD_PENDING preserved. (Adjacent edges ruled under G1/G2.)
- V3 CONFIRMED FIXED — `_sink_tail_scan` classifies in one pass; mid_damage → named divergence, no truncation; clean torn tails cut to `<sink>.torn-<ts>` and re-derived. (Minor register note on OSError handling in `_sink_truncate_torn` → REG-9.)
- V4 CONFIRMED FIXED — marker/probe retired; `_ceremony_state` gates solely on `not _totp_provisioned()` (DEMO/LAB exempted); fence enforced in all dispatchers (post-truncation legs on Vesper's record); alert_check names CEREMONY STATE and LAB MODE; INSTALL §8 checkbox present.
- V5 CONFIRMED FIXED (in this seat's read) — `_anchor_apply` restricts auto-clears to ANCHOR_FILE_STATE_REASONS or a checkpoint_disagreement whose bad_ids are a non-empty subset of accepted ids; append precedes mutation with try/except abort. [Chair note: like Qwen's Review 1, this seat did not test the reason-promotion sequence; the V5 edge stands on the Claude A / Claude B / chair executions.]
- V6 CONFIRMED FIXED — restore.py emits the tri-state (exception → "unknown"); `_consume_restore_marker` maps legacy booleans, preserves strings, defaults to "unknown"; `outgoing_state != "never"` treated as provisioned.
- V7 PARTIAL — product code CONFIRMED FIXED (glob `<db>*.pre-restore-*` feeds registry_breaches and retention prune; all five artifacts covered); the suite_schema test mirror was NOT updated (still requires `.pre-restore-` immediately after the base name) — Low, test-only. [Corroborates Claude B's V7 PARTIAL.]
- V8 CONFIRMED FIXED — 64 fixed unknown buckets; flushed-marker pruning on every call; bounded sort in `_auth_lock_status`.
- V9 CONFIRMED FIXED — safety set is {"/reads", "/suppressions", "/holds"}; both releases refuse 503 during an anchor fence.
- V10 CONFIRMED FIXED — `hit_ref()` keyed HMAC refs in all BLOCKED payloads; custody entries keep raw ids for custody_excerpt() by design.
- V11 CONFIRMED FIXED — expired/unparseable pickup window deletes the entry incl. secret, chains PICKUP_EXPIRED, uniform 401, no lockout count; store_unavailable never counts; must_reenroll counts only with a presented code.
- V12 CONFIRMED FIXED — unique temp pattern in both janus pickup and provision.py save.
- V13 CONFIRMED FIXED — byte-identical 409 for non-supervisors across nonexistent/suppressed/unverified; supervisors keep distinct responses.
- V14 CONFIRMED FIXED (mooted and answered) — probe retired by V4; rationale documented in TRACK-127.
- V15 CONFIRMED FIXED — all sub-items verified in code/docs (archive naming, stranded bound, 30-day pending expiry, escrow pairing, checkpoint tail, signing comment, COMPACT.md 1.2.7, sentinel_audit version, target_schema_version rename, CANT-DO entry). (attack2.py.orig-124 not in this pack; accepted on TRACK-127 attestation.)
- V16 CONFIRMED FIXED — sink_divergence() strands every committed seq on an unreadable sink; the accept ceremony can rotate and backfill.
- V17 CONFIRMED FIXED — `_auth_locked` pops in memory only; `_auth_lock_persist` no longer called from it.
- V18 CONFIRMED FIXED — per-side secrets; header attached only when a secret is passed; receipt post passes none.

## §3.2 — Gemini's own queued items (G1–G5), ruled by their origin seat

- **G1 — VERIFIED, SURVIVES (Medium, register).** Full code trace + 6-step reproduction list (reproduced in the preserved return): the conflict WHERE fails on the inactive row, nothing is written, HOTLIST_ADD_PENDING chains anyway, 202 returned, the submission never enters the pending queue.
- **G2 — VERIFIED, SURVIVES in hotlist_sync; CHANGED SHAPE in retention/approval (Medium, register).** hotlist_sync sweeps pending rows (no pending filter) and chains HOTLIST_EXPIRED for never-live entries; the 30-day expiry is lazy (HTTP hotlist paths only), never run by retention.py or checked by registry_breaches — a no-expiry pending row on a quiet queue survives past 30 and even 150 days unflagged; and `_hotlist_pending_decide` approves without checking expires_ts/active, flipping a swept row back to active=1 with a past expiry. 5-step reproduction list in the preserved return.
- **G3 — VERIFIED, SURVIVES (Medium, register — "sharpest non-blocking finding").** Pickup dispatches before auth() and never reloads config; both subcases traced (disable-user: secret collected, though the on-disk disabled flag survives the rewrite and blocks later access — "which keeps this below critical/blocker"; rotate-key: the revoked key completes pickup and overwrites the admin's rotation — account takeover shape). 4-step reproduction list in the preserved return. [Executed and confirmed by Claude A and Claude B.]
- **G4 — VERIFIED, LATENT TRAP SURVIVES (Low, register).** rotation.py's hardcoded prefix tuple in two places; harmless only because the producer still stamps "1.2.5". 3-step reproduction list in the preserved return.
- **G5(i) — VERIFIED, STILL OPEN (Low–Medium).** backup.py refuses escrow-inside-backup but not backup-inside-escrow; repro supplied.
- **G5(ii) — VERIFIED, STILL OPEN (Medium).** enroll_2fa checks neither the target's disabled flag nor the confirmer's (the confirmer is never looked up in users.json at all) — a disabled operator's still-active TOTP entry can second-key confirmations, including --force overwrites. Repro supplied. [Executed by Claude A; code-read by Claude B.]
- **G5(iii) — VERIFIED, STILL OPEN (Medium).** config_closed() exempts only /heartbeat and /audit/anchor-accept; /auth/unlock, /auth/2fa/reenroll, /auth/2fa/acknowledge, /audit/sink-divergence-accept all 503 on a stale config — and a restored 3-day-old backup restores a stale cases.json, deadlocking the very recovery steps INSTALL §7 requires until a fresh case export arrives. Repro supplied.
- G5(iv) — CLOSED BY V6. G5(v) — CLOSED BY V8.

## §3.3 — Judgment calls

Calls 1, 3, 4, 5, 6, 7, 8, 9, 10, 11 RATIFIED (call 1 with the reservation that the ceremony releases should be fenced — see §3.4). **Call 2 — OBJECT:** LAB_MODE is named in /health but not in ok_all; an install that provisions mid-run under LAB can report ok:true and alert_check.py exits 0 ("OK: janus healthy") until restart, because alert_check gates on health.ok and totp.state. Fix: hold ok_all False unconditionally under LAB_MODE (matching DEMO_MODE) and have alert_check read the lab_mode flag directly. Logged to register (REG-6); expressly NOT a 2FA bypass (auth enforces 2FA as soon as the store is non-empty). [Qwen's Review 1 noted the same behavior and ratified with the note; the objection is preserved as a dissent.]

## §3.4 — Ceremony attack (origin seat for V16–V18/F-items)

"Attacking V4 as a mechanism does not surface a deployment-blocking defect that would reopen Round 9's V4 ruling." Held: no file-portable bypass (state derives solely from _totp_provisioned()); mid-run provisioning under LAB never waives 2FA and the next boot refuses; restore onto a LAB host fails closed (marker consumed before the LAB check; boot exits 3); legacy bootstrap path works without deadlock; the fence fires in dispatch before handler logic, so no error-shape/timing oracles on fenced routes; /stats exposes aggregate counts only, no plate text.

Edges (non-blocking, registered):
- **Releases unfenced in ceremony state** — /holds/release and /suppressions/release are absent from CEREMONY_FENCED_POST: a key-only supervisor can probe protection-order existence (404 vs 200 vs 400-with-count) and two key-only supervisors can lift a protection order without 2FA, while GET /hits correctly 503s. Repro supplied. [Third seat to find this: Qwen R5, Claude B r07, Gemini §3.4.]
- **LAB_MODE health-honesty gap** (the call-2 objection above), with repro.

[Chair note: this seat's §3.4 does not discuss the suppression-placement near-match oracle in the ceremony response; that item stands on the Claude A / Claude B / chair executions.]

## §5 — Register (seat's R10-REG-1…12, all non-blocking)

REG-1 (Med, G3) reload config at pickup · REG-2 (Med, G5iii) align config_closed exemptions with the anchor-exempt set · REG-3 (Med, G1) conflict clause reactivates inactive rows into the queue · REG-4 (Med, G2) pending filter in hotlist_sync + refuse expired approvals + run pending expiry in retention/registry · REG-5 (Med, §3.4) fence both releases in ceremony state · REG-6 (Med, call 2) LAB_MODE gates ok_all + alert_check reads lab_mode · REG-7 (Med, G5ii) disabled checks for target and confirmer in enroll_2fa · REG-8 (Low–Med, G5i) refuse backup-inside-escrow · REG-9 (Low, V3 edge) _sink_truncate_torn should surface OSError and abort delivery · REG-10 (Low, G4) replace the hardcoded version tuple with an explicit legacy check · REG-11 (Low, V7) suite_schema mirror · REG-12 (Low) provision.py save() os.open 0o600 hygiene + inspect the builder's 4 load-run wrong_values (absent in Vesper's cold run).

## §6 — Criteria and vote

Criterion 1 MET · Criterion 2 MET · Criterion 3 MET · Criterion 4 MET (accepted: Vesper's cold one-shot, exit 0, full battery success, V 19/19, 0/19 discrimination on untouched janus126). **Overall vote: CONVERGED.** Single forced change: none. Model/effort line in the seat's own text: "the interface shows no model name" (operator UI observation governs: Deeper analysis 4 Neon, Thinking High).

## §7 — Coverage

Read in full: 01 (incl. the Gemini appendix), 03, 04 (all 12 scripts), 05, 07, 08. File 02 truncated inside _rotation_contribution (see header note).
