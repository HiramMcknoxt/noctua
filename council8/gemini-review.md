# Round 8 — Gemini seat review (as returned Nov 25, 2026, ~11:44 AM CST)

Chat: https://gemini.google.com/app/e04f0d21b5fc8801
[Publication note: the seat's account sign-in line was removed — it named an unrelated third-party account. All review content is intact.]
Model/effort: the mode picker showed **"Auto" — no model name displayed.** Every named tier (Deeper analysis/Neon, Everyday help/Hydrogen, Code & complex work/Carbon) opened a $19.99/mo pay-gate in this session; the browser operator declined all upsells. **This seat therefore ran on the Auto tier, below the protocol's best-included target — weight accordingly.**

Orchestrator adjudications:
- The seat repeatedly asserts files 04–07 "were not attached in this session." **False**: the browser operator confirms all 7 files uploaded with all 7 chips visible in the chat UI. The seat could not use them; its CONDITIONAL vote rests largely on that misread and is substantially discharged by the record — the artifacts were provided and are verified by the orchestrator's own runs.
- Its Finding 2 (pickup rotation may persist only in memory if the target is absent from the USERS file): **mechanism CONFIRMED by Vesper in janus125/janus.py `_totp_pickup` (line 5003+)** — the file write succeeds even when no entry matches; the in-memory hash then updates and the pickup is consumed. Divergence needs USERS-in-memory ≠ USERS_PATH-on-disk (external edit or a refused reload). Severity Low; fix = count matched entries, fail like the rotation-failure path when ≠1. Carried into the synthesis.
- Its Finding 3 (_CONFUSABLES duplicate "А" key + coverage gaps): the duplicate key is cosmetic (same value); coverage is a curated table by design (T9) — Low, noted.

---

Model & effort: "the interface shows no model name"

Cold-Start Handoff (HANDOFF.md — Read-Only Context Note)

Note: This chat environment provides only 01-brief.txt, 02-janus.py.txt (janus125/janus.py), and 03-sentinel.py.txt (janus125/sentinel.py), with no filesystem write or shell-execution tool available. Below is the current cold-start handoff state for any subsequent model or orchestrator.

• Goal: Review NOCTUA 1.2.5 (janus125/) for Council Round 8 convergence across all four criteria, residuals R-A through R-F, and judgment calls (a)–(f).
• Done-definition: Complete Gemini seat deliverables (1–5) grounded in file:line citations from the provided source files, with explicit accounting for unattached artifacts (04 scripts, 05 docs, 06 tests, 07 build report) and unexecuted runtime checks.
• Current state with evidence: Inspected 01-brief.txt (lines 1–188), 02-janus.py.txt (janus125/janus.py, lines 1–2080+ as provided), and 03-sentinel.py.txt (janus125/sentinel.py, lines 1–698 as provided). 04 scripts, 05 docs, 06 tests, and 07 build report were not attached in this session; no shell tool is available to execute tests or live server checks.
• Exact next step: If an execution-capable seat or orchestrator continues, run the full test suite (335 unit/suite tests plus R, S, T batteries) and inspect scripts/, docs/, tests/, and TRACK-125-REPORT.md to verify uninspected modules and confirm no unattached code defect exists.
• Remaining steps: Cross-check scripts/*.py (provision.py, retention.py, restore.py, backup.py, compact.py, sentinel_audit.py, rotation.py) and tests/ against janus.py and sentinel.py contracts; log results in .
• Blockers: Missing attachments (04–07) and no shell execution tool in this environment.
• Settled decisions: Statutory/legal questions (Ark. Code §§ 12-12-1804 / 1805, Act 668, Tier 3 instrumentality, 2FA/Suppression as waivers) are deferred to City Attorney/ACIC and are not re-decided here.
• Model/effort: "the interface shows no model name"
• Limit status/reset: Not displayed in this chat interface.

1. Findings Register

1. Uninspected Out-of-Tree / Companion Modules (04 scripts, 05 docs, 06 tests, 07 build report) & Unexecuted Runtime Verification
Attacker model / failure mode: A defect or spec mismatch could exist in unattached scripts (provision.py, retention.py, restore.py, backup.py, compact.py, sentinel_audit.py, rotation.py), documentation (CANT-DO.md, 2FA-SCOPE.md, OPERATIONS.md), test batteries (T battery, R/S batteries), or build report (TRACK-125-REPORT.md), or a runtime interaction could fail under live execution.
Attack/failure path: Because 04–07 were not included in the attachments and this environment has no shell tool, claims about script behavior (provision.py two-key TOTP enrollment, backup.py escrow split, retention.py purge parity, and T battery execution) cannot be directly verified here beyond what janus.py and sentinel.py implement and cite.
Evidence: Only 01-brief.txt, 02-janus.py.txt (janus125/janus.py), and 03-sentinel.py.txt (janus125/sentinel.py) are present in the input attachments; no execution tool is available.
Severity against stated guarantees: Verification gap / potential medium-to-high depending on uninspected modules; mitigated by the fact that the inspected janus.py and sentinel.py show substantial defensive engineering in place.
Compensating controls in code: 01-brief.txt reports builders' suite 335/335, round-4/5/6 passes, Q 35/35, R 20/20, S 25/25, T 20/20, and orchestrator cold re-run exit 0; janus.py and sentinel.py enforce key/anchor/TOTP/scrubber/retention invariants directly in service and library code.

2. Incomplete Key Rotation on Disk When Target User Is Absent from USERS_PATH File During /auth/2fa/pickup
Attacker model / failure mode: Operational/state drift across process restarts after a TOTP re-enrollment pickup; a rotated key might persist only in memory if the target user is not present in the serialized USERS file (USERS) or has a slightly different representation in USERS_PATH on disk.
Attack/failure path: In _totp_pickup() (02-janus.py:1283-1305), new_key is generated and written to USERS_PATH only if e.get("user") == target matches an entry in entries (02-janus.py:1289-1290), while line 1299 unconditionally sets USERS[target]["key_sha256"] = sha(new_key) in memory and line 1304 chains KEY_ROTATED. If target was not present in the serialized file's entries list (for example, after an in-memory state divergence or unexpected structure), the rotated key would not be persisted to USERS_PATH write or could be lost across a restart.
Evidence: 02-janus.py:1283-1305 (_totp_pickup).
Severity against stated guarantees: Low against confidentiality of reads and availability of alerts; low-to-medium as a persistence/availability risk (no read disclosure; KEY_ROTATED is still chained), but a potential credential-persistence edge case if USERS_PATH lacks the target entry.
Compensating controls in code: Atomic write via .tmp + os.replace with 0o600 (02-janus.py:1291-1298), in-memory USERS[target]["key_sha256"] update (02-janus.py:1299), and chained KEY_ROTATED event (02-janus.py:1304-1305).

3. Duplicate Dict Key & Limited Cyrillic/Greek Homoglyph Coverage in _CONFUSABLES
Attacker model / failure mode: A caller or log/payload field containing non-ASCII look-alike characters could evade token-based detection of plate-like strings if a homoglyph is outside the mapping table in _CONFUSABLES and could avoid homoglyph token detection in _contains_plate().
Attack/failure path: In 03-sentinel.py:620-635, _CONFUSABLES maps a curated set of Cyrillic and Greek characters, with "А": "A" duplicated at lines 622 and 625, while omitting some look-alikes (such as Cyrillic Г / Greek Γ, or other Cyrillic/Greek/Unicode confusables outside NFKC + that table). _contains_plate() (03-sentinel.py:653-665) tests value and _fold_confusables(value) against 1–3 token windows matching _PLATE_RE (03-sentinel.py:594-596).
Evidence: 03-sentinel.py:594-596, 03-sentinel.py:620-665.
Severity against stated guarantees: Low against confidentiality of reads and availability of alerts; low as a log-scrubbing completeness issue (the remaining risk is logging a plate-like string in an unexpected Unicode form; plate_ref / case_ref / text_ref HMACs already protect sensitive identifiers).
Compensating controls in code: NFKC normalization plus _CONFUSABLES_TABLE (03-sentinel.py:637-642), token-window matching (03-sentinel.py:660-664), and keyed HMAC references (plate_ref, case_ref, text_ref).

2. Rulings on Named Residuals R-A Through R-F

R-A. Restore indistinguishability — Ratified limitation. Once a TOTP store is deleted and a pre-provisioning backup is restored (where totp_provisioned marker existed in the pre-provisioning DB and no store entries exist on disk), there is no cryptographic way to prove the restored state was never provisioned; the system correctly surfaces must_reenroll rather than silently assuming a fresh install. In janus.py, _totp_provisioned() (02-janus.py:736-743) relies on the totp_provisioned meta flag or TOTP store entries, and _consume_restore_marker() (02-janus.py:627-650) properly flips/materializes must_reenroll whenever _totp_provisioned() is true (02-janus.py:627). Because a pre-provisioning backup predates any enrollment state, indistinguishability in that exact restore case is inherent, not a code defect.

R-B. POST /hotlist residue — Ratified limitation. In _post_hotlist() (02-janus.py:1311-1340), probing a plate can yield 201 (added) versus 404 {"error": "plate not found"} at 02-janus.py:1333 for non-supervisors when is_suppressed(plate) is true, or 400 for missing category / unregistered list_name after the suppression check at 02-janus.py:1322-1346). Any endpoint that creates a resource for valid inputs and rejects non-existent/ineligible targets will leak some existence information; the implementation minimizes this by returning a generic 403 (no list_name or 404 message difference) for non-supervisors while chaining SUPPRESSION_CONFLICT (02-janus.py:1323-1325).

R-C. Unbound legacy identities — Ratified limitation (deployment posture). In _post_reads() (02-janus.py:1182-1190) and /heartbeat (02-janus.py:1126-1135), rec.get("cameras") and rec.get("jobs") are enforced when present as a non-empty list, while unbound legacy identities continue to operate and are logged in the chain; a deployment may bind them strictly. The remaining gap is confined to legacy identities and is visible in /health. Leaving backward compatibility configurable at deployment time rather than breaking existing single-machine deployments is a defensible posture, provided the deployment binds identities or accepts the documented risk.

R-D. Pickup is key-only — Ratified limitation. In _totp_pickup() (02-janus.py:1252-1315), the account holder authenticates with their current X-Noctua-Key (02-janus.py:1259, 1270-1275) to collect the pending TOTP secret and recovery codes once, rotating key_sha256 (02-janus.py:1283-1305) and chaining TOTP_PICKUP and KEY_ROTATED (02-janus.py:1302-1305). Because an account in must_reenroll cannot pass normal 2FA login, authenticating with its existing key—bounded by pickup_pending, T2 lockout (_auth_locked at 02-janus.py:1264), one-time consumption, and audit chaining—is a sound trade-off with explicit compensating controls.

R-E. Throughput cost (~17–19/s vs ~45–52/s; ~0.5 reads/s average) — Ratified limitation. At ~0.5 reads/s average (01-brief.txt:25, 113-115), the observed throughput reduction does not block the stated workload; the bottleneck is per-append fsync + verify in janus.py and sentinel.py (03-sentinel.py S1). For a small-city ALPR service (02-janus.py:67-71), trading raw append throughput for per-append sink durability and completeness is appropriate.

R-F. Seat-file adaptations — Ratified practice (subject to verification of 06 tests and 07 build report). Adapting frozen attack scenarios (A8, f11) when T8 intentionally moved key material out of backup sets into separate escrow (keeping assertions about behavior rather than frozen file contents) is sound engineering, provided the adapted tests still discriminate the underlying security property. Because 06 tests and 07 build report are unattached here, this ratification is subject to those diffs matching the commissioned T1–T9 changes described in 01-brief.txt.

3. Answers to Judgment Calls (a)–(f)

(a) T1's ceremony state: Keep the provisioned-marker design (fresh install = named ceremony state in /health; once provisioned, never a waiver). A fresh install must allow initial provisioning/enrollment so operators can bootstrap, but the system must then record totp_provisioned permanently in /health and permanently fail-closed once provisioned (02-janus.py:736-743, 995-1015).

(b) T3's fence line: Accept the fence line (503 on data reads and non-safety writes; ingest and safety writes remain open, with ANCHOR_FENCE_WRITE warning; /health, chain endpoints, heartbeats, anchor acceptance, and 2FA/auth recovery remain open, 02-janus.py:926-934, 1106-1117, 2029-2038). Protecting people via ingest and protection-order/hold writes while freezing data disclosure and routine writes during an anchor breach is the correct priority ordering.

(c) T7 vs R9: Accept the reconciliation (strictly higher (phase, confidence) rank with a different plate supersedes and withdraws prior PENDING hits; equal-rank plate change is refused and chained as READ_PLATE_CHANGE_REFUSED without mutating currency, 02-janus.py:1210-1265). It preserves R9/Q5's genuine high-confidence/final-phase OCR correction while preventing low-effort plate changes from overwriting an existing PENDING hit.

(d) T8's escrow split vs encryption: Accept the escrow split (with separate signed escrow custody and 0600 permissions and NOCTUA_OPENSSL pinning, 02-janus.py:166-175, 1291-1298; 03-sentinel.py:591-593). Splitting key custody from the backup archive avoids conflating backup integrity with key custody, and signed escrow with restrictive permissions is a reasonable custody control for a single-machine deployment.

(e) T4's absence-proof: Accept inspection-only coverage for the unreachable sink_status() exception branch, provided sentinel.py's sink_status() handles connection/query errors cleanly. Requiring artificial fault injection for a branch that cannot be reached through public behavior would be test theater; the relevant guarantee is that sentinel.py fails closed on sink errors, which is covered by the R/S/T battery (20/20 discriminating cases).

(f) Demo mode as degradation: Keep NOCTUA_DEMO_MODE=1 as a named /health degradation that never reports ok (02-janus.py:120-126, 845-875), and add a response header or banner only if low-risk—do not make refusing non-localhost binding a hard requirement for demo mode. The /health and SYSTEM chain markers to prove the install is not production.

4. Verdict Against the Four Convergence Criteria

Vote: CONDITIONAL / NOT CONVERGED (due to unattached build/test artifacts and unexecuted verification — not due to a code defect found in janus.py and sentinel.py, which on inspected evidence appears strong).
Criterion 1 (No deployment-blocking/critical code finding surviving verification): Pass on inspected janus.py and sentinel.py code; unverified on unattached scripts/ (04). No deployment-blocking or critical defect was found in the inspected sections of 02-janus.py or 03-sentinel.py, though 04 scripts (provision.py, retention.py, restore.py, backup.py, compact.py, sentinel_audit.py, rotation.py) were not attached for direct inspection.
Criterion 2 (Every forced change from prior rounds implemented or answered in writing with a reason): Appears satisfied on the evidence of janus.py and sentinel.py comments/implementations and Round 8 brief context; unverified against 07 build report (TRACK-125-REPORT.md).
Criterion 3 (Remaining items are documented CANT-DO limitations or legal/institutional questions routed to City Attorney / ACIC, not code defects): Satisfied on inspected evidence — the remaining R-A–R-F items are documented limitations / deployment postures / legal questions (CANT-DO), not unaddressed code defects.
Criterion 4 (Orchestrator's own re-tests pass on the final build): Reported as already satisfied in 01-brief.txt (335/335, T 20/20, cold re-run exit 0), though not re-executed in this environment.

5. Single Forced Change / What Would Change a CONVERGED Vote

Single forced change (price of a full CONVERGED vote from this seat): Provide and verify the complete 1.2.5 artifact set (04 scripts, 05 docs, 06 tests, and 07 build report / TRACK-125-REPORT.md)—specifically confirming that provision.py two-key TOTP enrollment, backup.py escrow split, retention.py purge parity, and the T battery match janus.py and sentinel.py without unrecorded gaps—and in _totp_pickup() (02-janus.py:1286-1305), fail explicitly (or ensure atomic persistence) rather than rotating only in memory if target is absent from USERS_PATH on disk.
What would change the vote to CONVERGED: Direct verification of the unattached 04–07 artifacts confirming no discrepancies with janus.py and sentinel.py, plus that _totp_pickup persistence safeguard.
