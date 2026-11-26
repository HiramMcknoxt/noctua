# Security Round 1 - DeepSeek seat review (verbatim)

Chat: https://chat.deepseek.com/a/chat/s/e41eca7e-46d8-4f4b-8bed-544d346d1df4
Model/effort as shown in the UI: no model name displayed anywhere in the interface; DeepThink toggle ON. The seat's own line agrees ("the interface shows no model name").
Ran 2:56-3:11 AM CST, Nov 25, 2026 (harness-measured).

MATERIAL LIMITATION (orchestrator's note): all 11 parts were attached, but DeepSeek displayed "Length limit reached. DeepSeek can only read the first 10%." The seat effectively reviewed janus.py only; it recorded hunts 2 and 6 as blocked and its ARGUS ruling as conditional. Its statement "only two parts were attached" is its own mistaken reading of that limit. A follow-up with sentinel.py + the ARGUS spec as separate small attachments was dispatched to the same chat to complete hunts 2 and 6 and close F12.

ORCHESTRATOR VERIFICATIONS (Vesper, Nov 25):
- F5 (memo persistence across keep-alive): NEUTRALIZED - janus.py sets no protocol_version; the BaseHTTPRequestHandler default HTTP/1.0 holds, so each request gets a fresh handler and the memo cannot persist across requests. The seat's own stated compensating control holds.
- F7 (sig_alg skip): CONFIRMED - janus.py:1880 verifies a signature only when cp.get("sig_alg") == "ed25519"; other checkpoints fall through to entries/root comparison. Converges with ChatGPT SR1-13.
- F6 (null checkpoint line): mechanism CONFIRMED - _load_checkpoints (1831) appends json.loads(line) unguarded (a "null" line yields None); _bad_checkpoints (1867) calls cp.get("entries") with no None/dict guard.
- F3 (SQL suppression leg): PARTIALLY CONFIRMED - the asymmetry is real (SQL leg compares the current formula only; the Python leg checks key_ref_candidates). The compensating call site _recover_order_for_plate runs on the ingest path only (janus.py:3494, inside _hits_for_read), closing the common path; stored reads never re-ingested remain the open question for the next commission's discriminating case.

---

Seat identity (transcribed from this chat's interface): the interface shows no model name. The interface shows no effort value. I will not infer either from the documents.

Material delivered to this seat. Only two parts were attached: part-01.txt (the round brief, then janus.py from its header through _note_auth_fail) and part-02.txt (the continuation of janus.py through the middle of run_search). The parts the assignment says follow — sentinel.py, the operational scripts, the design/build documents including 2FA-SCOPE.md and the 1.2.4 build report, the test suites, and argus/SPEC.md — were not attached. That is a material blocker and I record it as such:
• Hunt 2 (openssl command construction) cannot be audited: every openssl invocation lives in sentinel.py (ensure_signing_key, verify_bytes, checkpoint_signed_bytes), none of which is in the delivered parts. I will not speculate.
• Hunt 6 (ARGUS) cannot be ruled on "as written": the spec file is absent. My ruling below is conditional and explicitly flagged.
• All findings below are confined to janus.py as delivered, and are cited by function + quoted code rather than line number, because the excerpt is not paginated with line numbers in the delivered parts.

1. Attack surface map (as I derived it from janus.py)
Assets that matter (by stated guarantee):
• Confidentiality of reads: reads, hits, suppressions, hotlist_members, holds, tier3_requests, evidence, case_searches, share_queries.
• Integrity/completeness of the audit chain: audit (via Chain), meta (audit_key_fingerprint, anchor_mismatch, anchor_accepted_ids, migration_status), the checkpoints file, the Ed25519 signing keypair, the external City Clerk witness.
• Availability of alerts: the ingest path, hotlist_members, the camera registry, /health job heartbeats, the chain sink ledger.
• 2FA secrets: DB_PATH + ".totp.json" (plaintext JSON, 0600), last_counter state.
Entry points:
1. HTTP handler surface (all handlers not in the excerpt past run_search, but the auth/gate skeleton is visible): auth(), janus_gate(), case_gate(), validate_fragment(), _strict_id().
2. Config loads at boot and on every auth() via _reload_config() → _apply_config() for users.json, cases.json, cameras.json.
3. Boot-time parsers: _load_checkpoints(), _consume_restore_marker(), _migrate_124(), _key_fingerprint_check(), _anchor_evaluate().
4. TOTP state: _totp_load(), _totp_save(), _totp_accept().
5. Edge/partner inputs: frigate_bridge, hotlist_sync, partner checkpoint files, /share/query — the parsers are largely past the excerpt, but the suppression and id-validation primitives they must pass through are visible.
6. Operator/supply-chain surface: NOCTUA_DEMO_MODE, NOCTUA_AUDIT_KEY, DB_PATH, TOTP_PATH, CHECKPOINTS_PATH.
Trust boundaries:
• Unauthenticated network → auth() (key hash + optional TOTP). This is the boundary I attacked hardest.
• Authenticated user → role/case gates (role_is, only_role, case_gate).
• Partner → share/compact gates (mostly past the excerpt; _chain_throttled and _strict_id are the visible primitives).
• Filesystem → DB/checkpoints/TOTP/keys (attacker model 5). Second-hardest boundary; the TOTP file sits on it.
• Edge feeds → parsers (model 6).
• Operator env → boot decisions (model 7), notably DEMO_MODE and the restore marker.

2. Findings register
Severity is judged against the stated guarantees, not CVSS. Every finding names an attacker model, an attack path, and evidence.

F1 — High — 2FA is opt-in per account, not mandatory for human roles
Attacker: 2 (low-privilege insider with a valid patrol/detective key and no phone).
Path: A human-role entry in users.json with no matching entry in .totp.json authenticates with the key alone.
Evidence: def _totp_required(rec): … entry = _totp_load().get(rec["user"]); return entry is not None. When no entry exists the function returns False, and auth() skips _totp_accept entirely. S11 claims "TOTP (RFC 6238) for every HUMAN role"; the code enforces it only for accounts already enrolled, and nothing in the code enforces enrollment — no check in _users_guard_error() or in provision.py. Nothing in _users_guard_error() or the boot sequence requires enrollment; _totp_status() reports a count but does not fail closed on a human account with no entry.
Compensating control: none in code.

F2 — High — Deleting the TOTP secret file silently disables 2FA for every human account (fail-open)
Attacker: 5 (file attacker) / 7 (operator or supply-chain).
Path: rm /data/noctua.db.totp.json → _totp_load() returns {} (except OSError: return {}) → every _totp_required returns False → 2FA is waived for all human accounts, with no marker and no /health alarm. This is the asymmetric twin of the restore path: _consume_restore_marker() flips entries to must_reenroll (fail-closed), but a deletion is indistinguishable from a fresh install, and _totp_status() merely shows enrolled_active: 0.
Evidence: _totp_load (except OSError: return {}), _totp_required (keys on entry presence), _consume_restore_marker (the only fail-closed path, gated on a restore marker).
Compensating control: none.

F3 — High (conditional on call site) — SQL suppression leg does not honor historical-formula refs for plate-less orders; a protected plate leaks in search
Attacker: 2/3 (insider search).
Path: An active, plate-less legacy order whose stored plate_ref matches a plate under sentinel.key_ref_candidates is suppressed by the Python predicate _order_covers() but not by the SQL predicate _SUPPRESSED_SQL, which compares only s.plate_ref = noctua_plate_ref(col) (current formula, NULL for a plate-less order's target unless it was recovered). run_search uses the SQL leg, so a protected plate appears in Tier 2/3 results while is_suppressed() says it is covered.
Evidence: _SUPPRESSED_SQL = " NOT EXISTS (… s.plate_ref = noctua_plate_ref({col}))" versus _order_covers() (return ref in sentinel.key_ref_candidates(...)). The S3 comment claims "a plate-less order whose ref matches a plate under any historical formula is suppressed on every disclosure leg" — the SQL leg does not implement that.
Compensating control: _recover_order_for_plate() exists and would close the gap if it runs on every read path before search. Its call sites are not in the excerpt; the orchestrator must verify that before relying on it.

F4 — Medium — TOTP acceptance is check-then-update with no lock; concurrent requests can replay one code
Attacker: 2/3 who observes a code and races the legitimate holder.
Path: Two concurrent auth() calls (both run outside DBLOCK by design — the pre-warm and the in-lock call) each _totp_load() the shared dict, each read last_counter < counter, each pass _totp_accept, each _totp_save. The sequence if counter <= last: continue … entry["last_counter"] = counter … _totp_save(data) is not atomic. The same six-digit code is accepted twice.
Evidence: _totp_accept as quoted; _totp_save is not under DBLOCK.
Compensating control: the 30-second window makes the race hard, but S11 states "replay-proof within its window," and this breaks that claim for concurrent requests.

F5 — Medium (conditional on protocol_version) — Per-handler TOTP memo can persist across HTTP/1.1 keep-alive requests
Attacker: 2/3 holding a captured code plus the key.
Path: auth() stores handler._totp_memo = (user, code) and, on a later call, if memo == (user, code): return rec — skipping _totp_accept and therefore last_counter. If the handler sets protocol_version = "HTTP/1.1", one BaseHTTPRequestHandler instance serves multiple requests on a connection, and the memo survives across them, defeating replay protection.
Evidence: the memo block in auth(). protocol_version is not in the excerpt (default is HTTP/1.0, which would neutralize this); the orchestrator must check it.
Compensating control: HTTP/1.0 default, if it holds.

F6 — Medium — A checkpoints file line of null crashes boot via AttributeError
Attacker: 5/7.
Path: _load_checkpoints() returns [None] for a null line (it only rejects OSError / ValueError). _bad_checkpoints() then executes n = cp.get("entries") on None → uncaught AttributeError inside _anchor_evaluate() → _startup_anchor_check() → boot dies. The comment promises the anchor "fails CLOSED"; a crash is a denial of the availability of alerts.
Evidence: _bad_checkpoints (for cp in cps: n = cp.get("entries"), no None guard); _load_checkpoints (cps.append(json.loads(line))).
Compensating control: none; a process supervisor restart-loops on the same file.

F7 — Medium — Checkpoint signature verification is skipped for any checkpoint whose sig_alg is not exactly "ed25519"
Attacker: 5.
Path: _bad_checkpoints verifies a signature only under if cp.get("sig_alg") == "ed25519":. A checkpoint that omits sig_alg (or sets it to "none") is classified solely by entries / root, so a file attacker can inject an unsigned checkpoint that influences the disagreement/acceptance calculus. Acceptance still requires two-key _anchor_accept, but the S7 contract ("verifies checkpoint SIGNATURES") is not met for non-ed25519 entries.
Evidence: _bad_checkpoints as quoted.
Compensating control: two-key acceptance, partial.

F8 — Low/Medium — AUTH_FAIL chains a truncated bare SHA-256 of the username, reversible by brute force; contradicts the keyed-HMAC rule for case numbers
Attacker: 4 (partner chain_auditor reading /audit/range), or any chain reader.
Path: uh = sha(user)[:16] is a bare hash over a small username space. P11/A36 moved case numbers to keyed HMAC precisely because bare hashes are reversible (the case_hash docstring). Usernames are a comparable space; a partner with chain read access can dictionary the user_hash.
Evidence: _note_auth_fail (uh = sha(user)[:16]) vs case_hash.
Compensating control: none; inconsistent with the stated chaining rule.

F9 — Low — A hot-reload guard refusal (ConfigGuardError) is not surfaced in /health config_status
Attacker: 7 — reduces detectability.
Path: _reload_config sets st["guard_error"], but config_status() emits only stale / stale_since; a refused attempt to hot-add imperator or a multi-role account is visible only through a throttled CONFIG_STALE chain entry that carries the exception type, not the guard message.
Evidence: config_status() body; _reload_config guard branch.

F10 — Low — TOTP secrets are stored in plaintext JSON beside the DB (0600), readable by model 5
Attacker: 5.
Path: TOTP_PATH = DB_PATH + ".totp.json"; _totp_save writes json.dumps(data, …) unencrypted. A file attacker already has the DB, so 2FA is not the control for that model — but the brief's 2FA hunt asks for the state of the new surface, and this is its storage posture.
Evidence: TOTP_PATH; _totp_save.
Compensating control: OS file permissions only.

F11 — Low — Malformed TOTP entries can 500 auth()
Attacker: 7.
Path: entry["secret"] raises KeyError if absent; digest in (entry.get("recovery") or []) raises TypeError if recovery is an int. _totp_load validates only that the file is a dict, not the entry shape.
Evidence: _totp_accept; _totp_load.

F12 — Observation (hunt 5, cannot be closed from janus.py alone) — A rollback of the DB and the local checkpoints file to a consistent earlier state is not detected by _anchor_evaluate
Attacker: 5.
Path: _anchor_evaluate() consults only CHECKPOINTS_PATH and compares it to the live chain; a shorter but self-consistent pair passes. The real anchor is the external City Clerk witness (the publish_witness.sh path). I record this as an open item the sentinel/scripts part must close, not as a confirmed finding.

Hunt 2 note
The openssl invocations that matter (sentinel.ensure_signing_key, verify_bytes, checkpoint_signed_bytes) are in sentinel.py, not delivered. I make no assertion about command construction. This is a blocker, not a clearance.

3. Ruling on the LLM monitor (hunt 6)
I cannot rule on ARGUS "as written" because argus/SPEC.md was not among the parts delivered to this seat. I will not invent a spec to attack. I record that as a blocker and give the conditional ruling the brief's design description supports.
Conditional ruling — ARGUS may not exist in a mutating tier; it may exist only as a read-only advisory overlay, and only under these conditions:
1. No mutation authority derived from model output. The monitor must hold no DB write credential, no chain-append capability, and no token that reaches any mutating endpoint. Any "self-healing" action that touches state must be proposed in text and executed by a human through the existing authenticated path.
2. Injection containment must be mechanical, not prose. Plate text, case refs, and user-supplied fields must be provenance-tagged data, never concatenated into a prompt that can call tools. The monitor must not be able to execute a tool call whose arguments are derived from untrusted text.
3. Egress and hardware as specified, enforced at the network layer, not by the model's cooperation. The monitor must have no general network egress and no direct network path to a camera; the air-gap claim must be a network fact (no route, no interface) rather than a promise by the application.
4. The "two tiers" must be two authority tiers, not two confidence tiers. Tier 1 (advisory) is permitted under 1–3. Tier 2 (guarded self-healing) may not be enabled until the spec demonstrates a mechanical authority boundary — separate credentials, an allowlist of reversible actions, a human approval step for any mutation — and until that boundary has been penetration-tested.
5. Failure mode is alarm, not silence. Any monitor fault must degrade /health and page a human; a monitor that can fail quietly has inverted the system's safety function.
Until the spec is delivered and survives that battery, my vote is withheld, which under this round's criterion is a non-approval.

4. Verdict against the round's criterion
Criterion: no surviving Critical or High finding exploitable by its stated attacker model without a compensating control.
Verdict: NOT CONVERGED. F1 and F2 are High, exploit by models 2/3 and 5/7 respectively, and have no compensating control in code. F3 remains High unless _recover_order_for_plate is shown to run on every read path; the orchestrator must verify that call site, and if it is absent the finding stands. In short, 2FA fails-open in two independent ways (unenrolled account, and deleted secret file), which is the opposite of the posture S11 claims.

5. The single forced change that is the price of my vote
Make 2FA mandatory and fail-closed for every human-role account. Concretely: _totp_required(rec) must return True for any account carrying a human role regardless of whether an entry exists, and auth() must refuse (401, feeding the existing AUTH_FAIL throttle) an unenrolled human account rather than waiving the check. A missing .totp.json while any human-role account exists must lock the service (the same KEY_LOCKED posture) or force must_reenroll for every human account, and /health must alarm — deletion must not be indistinguishable from a fresh install. This one change closes F1 and F2 and removes the systemic fail-open in the 2FA surface.

6. Pilot pen-test gate clause (drafted for the pilot spec)
PILOT PEN-TEST GATE (non-waivable). Before any camera is energized on the pilot deployment, an independent penetration test of the deployed pilot system — not a review of design documents or a test of a staging build — must be completed, with findings remediated and re-tested. The test must cover, at minimum: (a) the authentication and authorization surface, including key-only authentication, role and case gates, and the full TOTP lifecycle (enrollment, activation, replay, recovery, and restore); (b) the confidentiality of reads, including suppression behaviour under historical plate-reference formulas and plate-less orders, the Tier 2/3 search path, and evidence and share endpoints; (c) the integrity and completeness of the audit chain, including checkpoint acceptance, rollback detection, and the external witness path; and (d) the deployment boundary — camera VLAN isolation, the WireGuard backhaul, localhost binding, and the absence of an internet route from the pilot network. No camera may be energized, and no live plate data may be ingested, until the test is complete and its findings are closed or formally accepted in writing by the accountable city official. This gate is non-waivable: it survives schedule pressure, and it is not satisfied by any other review, audit, or attestation.

Blockers restated for the orchestrator: (1) sentinel.py, the scripts, the design/build documents, the test suites, and argus/SPEC.md were not delivered to this seat — hunts 2 and 6 cannot be completed, and F12 cannot be closed, until they are. (2) F3 is conditional on where _recover_order_for_plate is invoked on the search/Tier-3 read path. (3) F5 requires the handler's protocol_version to be checked.

---

# FOLLOW-UP RESPONSE (same chat, Nov 25, 3:12-3:20 AM CST, harness-measured)

Orchestrator's note: sentinel.py + argus/SPEC.md were delivered as separate small attachments and read in full (no length-limit warning). F13 VERIFIED by Vesper: sentinel.py pubkey_fingerprint does base64.b64decode(body) with no try/except, and .splitlines() on a non-string raises AttributeError - a crafted checkpoints line crashes the anchor path, same fix family as F6.

Seat identity (transcribed from this chat's interface): the interface shows no model name. The interface shows no effort value. I do not infer either from the documents.

Material now in front of this seat: sentinel.py (full, as delivered) and argus/SPEC.md (full). The operational scripts, the design/build documents, the test suites, and publish_witness.sh remain undelivered. That still bounds F12; it does not bound Hunt 2 (all openssl invocations are in sentinel.py) or Hunt 6 (the spec is complete).

1. Hunt 2 - openssl command construction: ruling
Clean on command injection. All four subprocess.run calls in sentinel.py (ensure_signing_key x2, sign_bytes, verify_bytes) use list form, no shell=True, no string-built arguments; attacker-influenced bytes go to temp files, never into argv. Key handling sound in the main (private key written by openssl to its final path; mkstemp temp files 0600; finally blocks clean up). Three findings survive:
- F13 - Medium - pubkey_fingerprint() crashes on malformed PEM; a crafted checkpoint kills boot. _bad_checkpoints calls it for sig_alg == "ed25519" checkpoints; base64.b64decode has no try/except (binascii.Error), and a non-string pubkey raises AttributeError at .splitlines(); either propagates uncaught through _anchor_evaluate -> _startup_anchor_check -> boot. Same failure shape as F6; same fix (guard and treat malformed pubkey as a bad checkpoint).
- F14 - Low - -out/-inkey path-argument injection via NOCTUA_DB beginning with "-" (operator-controlled).
- F15 - Low - ensure_signing_key chmod window (key created under umask, chmod 0600 after subprocess returns).

2. Hunt 6 - ARGUS, ruled as written
- Q1 Sanitizer bypass: FAIL. _PLATE_RE is ASCII-only after normalize_plate; Cyrillic/full-width homoglyphs are not normalized into ASCII and pass with the plate intact. Fragmentation across queries defeats per-query checks; the spec never enumerates its templates, so "no field can carry them" is unverified.
- Q2 Sink injection: PARTIAL FAIL. The deterministic layer never reads ARGUS (boundary correctly drawn), but sink free-text fields (holds.reason, witness_attestations.detail, share_queries.why) reach ARGUS's context; if the digest is the auditor's primary reading layer, injected text can crowd out or mis-prioritize real flags. The spec's fencing language covers research results, not sink content.
- Q3 Research-result injection: FAIL as written. "Clearly fenced" / "can never become an instruction" are prompt-level; no mechanical separation between the research-reading context and the tool-calling context, no non-LLM-validated structured output.
- Q4 Machine key blast radius: FAIL. SERVICE_ROLES keys are role keys, not action keys; a jobs key reaches every jobs endpoint. The allowlist is enforced by the model's cooperation, not the credential.
- Q5 Rollback abuse: CONFIRMED DESIGN FINDING. A rollback to an older approved snapshot destroys every protection order, suppression, hot-list entry, evidence bundle and chain entry since it; an attacker who can induce an invariant failure chooses the timing. The spec's rollback does not route through Janus's restore ceremony, so it is not even a chained restore event.
- Q6 Same-host proxy: FAIL; separate hardware is a hard requirement. Host compromise defeats dual-NIC/no-forwarding/default-deny (root adds routes); "rules are files a human can audit" is configuration integrity, not runtime enforcement.
Additional: (A) "Not the alarm" is unenforceable in the UI if the digest is the auditor's reading layer - deterministic alerts need their own unfilterable channel; (B) ARGUS's review log is an unregistered plate-bearing store (outside PLATE_DATA_STORES) - a hunt-7 leakage path; (C) the 30-35B model class compounds Q2/Q3; (D) the spec's six open questions are honest and well-chosen - the design's answers are prose, not mechanisms.
FINAL RULING (replaces the conditional one): ARGUS may not exist as specified. Only under mechanical constraints: no Janus credential (Tier A proposed by ARGUS, executed by a deterministic non-LLM policy daemon with a human-edited allowlist, chaining as itself); Tier B advisory only (no automatic deploy, no automatic rollback; a human verifies "battery green"); research side on separate hardware; the sanitizer is defense-in-depth, not the boundary (no route to the enclave; separate model invocations for research vs tool calls; tool-call planner accepts only structured JSON validated by a non-LLM component); close the scrubber's Unicode/homoglyph gap before ARGUS is built (the gap is in the chain scrubber itself); register ARGUS's review log in PLATE_DATA_STORES or prove it plate-free by construction; rollback is a two-key chained restore ceremony, never automatic; deterministic alerts get their own unfilterable UI channel. Under those constraints ARGUS may exist as a read-only advisor. As written, it may not.

3. F12 - CONFIRMED, Medium. verify_detached/_verify_rows catch head-missing and hash breaks, but a rollback to a consistent earlier (DB, checkpoints) pair passes both. The only detector is the Clerk's externally held checkpoint copy, and no delivered code path compares the witnessed root against the live chain at boot or in /health (the witness job's heartbeat is monitored; its content is not). Fix belongs in /health: surface the last external witness root + timestamp and fail closed on mismatch.

4. Verdict and forced change: NOT CONVERGED - stands. F1/F2 remain High with no compensating control; F3 remains High pending the search-path call-site check; F13 new Medium; F12 confirmed Medium; the ARGUS spec fails its own six open questions.

5. Pen-test gate clause: unchanged from the first response (non-waivable independent test of the deployed pilot - application, network, key custody incl. a restore-from-backup exercise - before any camera goes live; CISA Cyber Hygiene / MS-ISAC as floor, paid independent test as standard; Critical/High remediated or accepted in writing by Corey Spangler with a named compensating control, the acceptance chained as a SYSTEM entry).

Blockers restated: scripts (incl. publish_witness.sh), design/build documents, and test suites remain undelivered to this seat.
