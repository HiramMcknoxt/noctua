# Round 10 — Qwen seat review (as returned)

- Chat: https://chat.qwen.ai/c/b165b7bc-d704-4167-9795-a24064dd202e ("NOCTUA Council Round 10 Gate") — the chat is the authoritative full record.
- Model/mode, operator-observed in the UI: Qwen4-Max; Thinking. (The seat's own text declines to transcribe interface labels; the operator's observation governs.)
- Full verbatim return also preserved at: ~/workspace/agents/0847f038-cfbc-4eb1-b271-f33f7534ec1d/subagent-output/7c2312b1-258e-4103-84a3-6f6826ec1b7a-result-4db2c899c229.txt

## PROCESS NOTE (chair — read first)

Qwen's 5-documents-per-turn limit split the 8-file pack across turns and fractured the seat's context. The seat produced THREE reviews and a final compact verdict:

1. **Review 1** (files 01, 02, 03, 07, 08 — brief, janus.py, sentinel.py, reports, synthesis): full anchored review of V1–V18 and G1–G5. Vote: **CONVERGED**. Reproduced verbatim below.
2. **Review 2** (files 04, 05, 06 only; the seat's context did not retain Review 1 and it said so plainly): script/doc/test-side rulings, most server halves marked UNVERIFIED, new findings Q10-1…Q10-7. Vote: NOT CONVERGED on coverage + doc grounds.
3. **Review 3** (consolidation attempt carrying Review 2 forward; still without Review 1 in context): added Q10-8, Q10-9, Q10-10. Vote: NOT CONVERGED.
4. **Final compact verdict** (after the operator re-supplied files 01, 02, 03, 08 plus the full pasted text of Review 1; two full-restatement attempts failed on platform errors): the seat CORRECTED its two intervening replies, WITHDREW the "incomplete coverage" ground entirely, and voted **CONVERGED** (verbatim at the end of this file).

The seat's final word governs its vote: CONVERGED. Reviews 2–3 remain valuable as the only script-side deep read of the round; their Q10 register is carried into the synthesis as unverified-but-precise items (the seat itself classifies them register-class, including its strongest, Q10-9).

---

# REVIEW 1 (verbatim) — files 01, 02, 03, 07, 08

NOCTUA Council Round 10 — Qwen Seat Review (static, anchored)
Subject: NOCTUA 1.2.7 (janus127/). Method: anchored code read of the supplied janus.py and sentinel.py extracts, cross-checked against the orchestrator's cold verification record and the builder's report. I have no execution environment; every ruling below is a code read or is explicitly marked as resting on the orchestrator's executed evidence. Where I reopen or register a finding I give an exact reproduction step list for the executing seats.
Citation note: the pack extracts strip leading indentation, so my anchors are function-name + exact quoted code. Where the verification record (VESPER-VERIFICATION-127.md) supplies a firsthand line number I reuse it and mark it (verif.). Other line ranges are approximate.

## Part A — My primary load (seat appendix items)

**V8 — Bounded failure accounting → CONFIRMED FIXED.** The bound is structural: `_auth_fail_total_key` folds every unconfigured name into one of 64 fixed `unknown:` buckets; configured accounts keep exact keyed counts; the namespaces cannot collide. Key space is provably |USERS| + 64, independent of spray volume. Flushed-marker pruning in `_note_auth_fail` discards markers older than bucket − 1; the Q15 TypeError shape (3-tuple marker keys) is gone. /health sorts the bounded totals dict (top 10); the report's phrase "built from configured accounts only" is slightly imprecise but the bound holds either way. Evidence: code read; V-battery v8 case executed green by the orchestrator; 0/19 discrimination on 1.2.6.

**V11 — Pickup secret expiry + lockout scope → CONFIRMED FIXED.** (a) The expired branch of `_totp_pickup()` deletes the whole entry (secret included), saves the store, chains PICKUP_EXPIRED, returns the uniform 401, no lockout count; `expired` is fail-closed on unparseable timestamps; the deletion precedes the token check. (b) `_lockout_counts()`: store_unavailable never counts; must_reenroll counts only when a code was actually presented.

**V12 — Unique temp paths → CONFIRMED FIXED** (janus half read; provision half verification-evidenced). The pickup rotation uses `"%s.tmp.%d.%s" % (USERS_PATH, os.getpid(), secrets.token_hex(4))` with os.open 0o600 and os.replace; no fixed `USERS_PATH + ".tmp"` remains in janus.py. The seat ratifies judgment call 8.

**V14 — Probe retirement → CONFIRMED FIXED.** No `_DB_LEGACY_CHAIN_AT_IMPORT`, no `install_born_empty` read/write, no `def _unprovisioned_locked` — the names survive only in comments/docstrings. `_totp_provisioned()` is the sole provisioning test, consumed by `_ceremony_state()`, auth(), and the boot LAB/DEMO refusals.

**V15 residues → CONFIRMED FIXED** for the readable residues (migration stamp rename to `target_schema_version` with value unchanged; `sentinel.stranded_summary()` bound; 30-day pending expiry via `_expire_pending_submissions()`; collision-proof archive names; signing-disabled boot comment now states the service runs FENCED). Script/doc residues not in the seat's turn-1 files (sentinel_audit.py version, escrow pairing, checkpoint.py tail, COMPACT.md line, .orig-124 header, CANT-DO entry) marked CONFIRMED on the orchestrator's executed evidence.

**G2 — PARTIALLY MOOTED / changed shape; residual registered (low).** V15 bounds the indefinite evasion (30-day deletion), but (1) the expiry is request-triggered, not clock-triggered — no cron leg; a pending row can outlive 30 days in wall-clock terms on a quiet install; (2) the registry breach check's hotlist leg inspects only active=0 rows, so the lazy bound is not health-visible. The hotlist_sync.py half was unverified in Review 1's coverage (file arrived in turn 2; see Review 2's G2 facts). The row is inert (matches nothing, appears in no list view). Register R6. Not vote-holding.

**G5(ii) — UNVERIFIED from Review 1 coverage; janus-side parity holds** (provision.py arrived in turn 2; Review 2/3 ruled the script halves of other items but G5(ii)'s definition lived in the absent synthesis for that context — the executing seats verified it: Claude A executed, Claude B code-read; see their reviews).

## Part B — Remaining V items (§3.1)

- V1 — CONFIRMED FIXED. Guard inside `_auth_lock_note_failure` (verif. 3196); pickup wrong-key branch calls only `_note_auth_fail`; token branch passes key_verified=True (verif. 5908); locked reply uniform 401.
- V2 — CONFIRMED FIXED. Conflict clause carries `WHERE hotlist_members.pending=1`; live rows untouched; uniform 202 + HOTLIST_ADD_PENDING either way. (Inactive-row adjacent shape = G1.)
- V3 — CONFIRMED FIXED. `_sink_tail_scan()` classifies mid_damage; torn branch returns a named divergence on mid-damage (writes nothing), else truncates only past the last valid line with a collision-proof archive name. (Clean-tail mid-weld observation → register R9.)
- V4 — CONFIRMED FIXED. See Part D.
- V5 — CONFIRMED FIXED (in Review 1's read). `_anchor_apply`: checkpoint_disagreement auto-clears only if bad_ids ⊆ accepted ids; file-state reasons enumerated; chain.append precedes the meta mutation in both clear and set paths; append failure aborts. [Chair note: Review 1 did not test the reason-promotion sequence; the V5 edge was found and executed by Claude A, Claude B, ChatGPT (static), and the chair execution — see those records.]
- V6 — CONFIRMED FIXED. `_consume_restore_marker` mapping; unknown → provisioned (materializes).
- V7 — CONFIRMED FIXED. PLATE_DATA_STORES pre-restore pattern `<db>*.pre-restore-*`; registry glob branch uses it. (Review 2/3's Q10-1 qualifies the retention behavior of those snapshots — see below.)
- V9 — CONFIRMED FIXED. ANCHOR_FENCE_SAFETY_POST = {"/reads","/suppressions","/holds"}; both releases removed.
- V10 — CONFIRMED FIXED. `hit_ref()` keyed HMAC refs in all hit-naming BLOCKED payloads; custody entries keep raw ids by design.
- V13 — CONFIRMED FIXED (commissioned three). Byte-identical 409 for non-supervisors across nonexistent/suppressed/unverified. (Fourth case_mismatch shape not uniform → register R7.)
- V16 — CONFIRMED FIXED. `sink_divergence()` strands every committed seq when the sink is unreadable (verif. 2041).
- V17 — CONFIRMED FIXED. `_auth_locked` shell-unlock branch pops in memory only (verif. 3175); persistence owned by provision.py unlock + `_consume_provision_marker`.
- V18 — CONFIRMED FIXED (verification-evidenced in Review 1; the script half was read in full in Review 2 and CONFIRMED there).

No V item is REOPENED in Review 1's read.

## Part C — Queued Gemini items (§3.2)

- **G1 — VERIFIED, SURVIVES (medium; register R1).** Full trace: the conflict WHERE fails on an inactive row (pending=0), nothing is written, yet HOTLIST_ADD_PENDING is chained and the uniform 202 returned; the submission never appears in /hotlist/pending and approve 404s. "This is the natural 're-list an expired stolen vehicle under the same case' workflow." Less severe than V2 (fails to add protection rather than removing it; supervisor direct-add still reactivates). Rated medium, register, not vote-holding — "but it is the highest-value post-convergence fix." Fix direction: `WHERE hotlist_members.pending=1 OR hotlist_members.active=0`, or the dedicated pending table.
- **G3 — VERIFIED, SURVIVES (medium; register R2).** `_totp_pickup()` reads in-memory USERS; `_reload_config()` runs only inside auth() (and boot). A disabled/rotated account can complete pickup off the stale record in the window. Fix: `_reload_config()` at pickup start.
- **G4 — REFUTED as a current defect; latent fragility.** Janus publishes schedule version "1.2.5"; the reported accepted list covers it. Maintenance note, not a defect.
- **G5(iii) — VERIFIED (medium-low; register R3).** `/audit/sink-divergence-accept` is anchor-exempt but not config_closed-exempt; during a stale config file the sink-divergence resolution ceremony 503s — "the two fences disagree about its recovery status." Fix: exempt it like /audit/anchor-accept.
- G5(iv) — CONFIRMED closed by V6. G5(v) — CONFIRMED closed by V8. G5(i) — UNVERIFIED in Review 1 (backup.py arrived turn 2).

## Part D — §3.4 Ceremony-state attack

"Attacked as a mechanism. It held; the adjudication does not reopen." Fence coverage enumerated across GET/POST/DELETE dispatchers (uniform 503 + throttled CEREMONY_REFUSED for key-only humans; machine roles exempt by design). LAB lifecycle held both ways (LAB lifts only the ceremony fence, never waives TOTP; provisioning under LAB enforces TOTP immediately; next boot refuses; restore of a provisioned backup onto a LAB host refuses at boot). Legacy-bootstrap path held.

Side doors found (register, not blockers):
- **R4:** ceremony-state /suppressions response `warning_near_matches` — plate-variant/existence oracle for a key-only supervisor who already knows the plate. Recommend omitting the warning in ceremony state.
- **R5:** /suppressions/release and /holds/release are NOT in CEREMONY_FENCED_POST — a key-only supervisor can remove protection during the ceremony. "Parallel to V9's anchor-fence reasoning." Recommend fencing both releases in ceremony state.
- /stats aggregate counts and /audit* ALERT metadata noted as already-accepted diagnostic posture, not findings.

## Part E — Judgment calls

All 11 RATIFIED (call 1 with the R4/R5 side-door notes).

## Part F — Register (Review 1)

R1 (G1, medium) — top post-convergence fix. R2 (G3, medium). R3 (G5iii, medium-low). R4 (ceremony oracle, medium-low). R5 (ceremony releases open, medium-low). R6 (G2 residual, low). R7 (V13 case_mismatch non-uniformity, low). R8 (/config/status named but unrouted, nit). R9 (mid-file sink weld with clean tail not proactively scanned, low). R10 (_sink_truncate_torn archive-failure message nit). G4 maintenance note. New deployment-blocking/critical findings: NONE.

## Part G — Verdict (Review 1)

All four criteria MET. **Overall vote: CONVERGED.** Single forced change: none. Highest-value post-convergence recommendation: R1/G1. Coverage: janus.py and sentinel.py read in full; scripts/tests/docs not in turn-1 files (rulings on those halves rest on the orchestrator's executed evidence, marked as such). Static seat, no execution.

---

# REVIEWS 2–3 (summary; full text in the chat and the preserved return)

Review 2 (files 04/05/06 — scripts, docs, tests) ruled the script halves: V12-provision CONFIRMED; V15(a) CONFIRMED, V15(e) CONFIRMED, V15(f) SPLIT (sentinel_audit "1.2.7" confirmed; janus stamp unverified); V6-script CONFIRMED; V7-mechanism CONFIRMED / registry UNVERIFIED; V18-script CONFIRMED in full; G2 script facts CONFIRMED (predicate, atomicity, fail-closed); G4/G5(i)/G5(ii) PENDING-DEFINITION (definitions in the absent synthesis). New findings:
- **Q10-1 (moderate):** pre-restore key snapshots are pruned on the first retention pass — restore.py's copy2 preserves mtime, key files are months old, retention's prune_glob deletes by mtime with no current-run exemption; the "complete snapshot" promise holds for hours, not the reads window. (Review 3 extended: aside()'s os.replace also preserves mtime, so a restore after a long outage can lose DB/WAL/SHM copies immediately too.) Fix: utime snapshots to now, or prune by filename stamp.
- **Q10-2 (minor):** compact.py receipt-credential fallback defaults to the chain_auditor key, which the role fence bars from writing receipts — the no-flag path cannot work; require --receipt-key.
- **Q10-3 (minor):** provision.py save() chmod-after-create window, no fsync (Review 3 extended to backup.py's escrow key write).
- **Q10-4 (moderate, docs):** shipped guides still name the retired "system" role (INSTALL §3/§6, NETWORK §4/§5, OPERATIONS §7); INSTALL §6 also omits chain_auditor and partner.
- **Q10-5 (minor, docs):** OPERATIONS §7 "Three jobs heartbeat" vs the five-job monitored set; three --help surfaces still read "NOCTUA 1.2.4"; rotation.py's hard-coded verify tuple (the G4 trap, restated).
- **Q10-6 (cosmetic):** OPERATIONS §9a archive-name pattern under-specifies the collision-proof suffix.
- **Q10-7 (observation):** hotlist_sync UPDATE's NULL-tuple edge (schema-contingent).

Review 3 added:
- **Q10-8 (minor):** the unique-temp doctrine stopped at users.json — checkpoint.py (`tmp = out + ".tmp"`) and compact.py save_state (`path + ".tmp"`) still use fixed temps with race/lost-update shapes; restore.py's _install_file noted, not charged.
- **Q10-9 (moderate):** two backup pruners disagree — retention.py's prune_backup_sets deletes the .archived sets backup.py deliberately preserves, defeating V15(e)'s escrow pairing one job later; INSTALL §7(2)'s promised second schedule for audit-preservation sets has no implementation. "No case runs both pruners over one archive."
- **Q10-10 (minor):** the Clerk's-copy leg of publish_witness.sh is best-effort and unalarmed (mail failure or absence is silent; the heartbeat still says "witnessed").

Review 2 vote: NOT CONVERGED (coverage + criterion-3 doc grounds). Review 3 vote: NOT CONVERGED (same grounds + Q10-9). Both votes were WITHDRAWN by the seat in its final verdict once it had both halves in front of it.

---

# FINAL COMPACT VERDICT (verbatim)

"Correction first: my two intervening replies were wrong — the earlier CONVERGED review is in this thread and the server code was in my pack. I withdraw the "incomplete coverage" ground entirely.

Justification: With both halves read, nothing meets the brief's deployment-blocking/critical bar — V1–V18 hold on the server side, and the strongest script-side item, Q10-9 (retention.py → prune_backup_sets deletes the .archived sets backup.py preserves, defeating V15(e)'s escrow pairing one job later, with INSTALL §7(2)'s second schedule unimplemented), destroys data earlier rather than disclosing it: real, but register-class. Criteria 1–4 are therefore met, and Q10-1…Q10-10 go to post-convergence triage rather than holding the vote.

Model and mode: Qwen (Alibaba Group); the interface shows no model name, and no composer mode label is observable to me — I won't invent either.

Final vote: CONVERGED."

(Operator UI observation for the record: Model Qwen4-Max, Mode Thinking.)
