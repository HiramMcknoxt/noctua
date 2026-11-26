# Security Round 1 - Claude seat review (verbatim)

Chat: https://claude.ai/chat/aa4f2116-0fa1-40ba-9550-a2df8d69be64
Model/effort as shown in the UI (browser operator): Opus 5.5, Medium (footer + model picker; pay-gated Fable not selected). The seat's own in-response line says "the interface shows no model name" - the UI transcription governs.
Ran 2:56-3:11 AM CST, Nov 25, 2026 (harness-measured).
Coverage as stated by the seat: sentinel.py, provision.py, publish_witness.sh, the brief, the ARGUS spec and the docs bundle read in full; janus.py read in sections (1-920, 1833-2420, 3167-3840, 4184-4424, 6835-6880, 7420-7650), the rest by search and execution; tests file: only the S11 two-factor cases; frigate_bridge, hotlist_sync, compact.py and the share-query handler not hunted in depth. The seat executed reproductions against the unmodified uploaded code in a scratch tree; its HANDOFF.md, run-next.sh, repro.py and repro2.py artifacts remain in the chat (download attempt failed, not repeated).

---

NOCTUA Security Round 1: Claude seat review of 1.2.4

Model and effort:
the interface shows no model name, and I can't see any effort setting.

Coverage, stated up front:
• Read in full: sentinel.py, provision.py, publish_witness.sh, the brief, the ARGUS spec and the docs bundle.
• janus.py, read in sections: lines 1–920, 1833–2420, 3167–3840, 4184–4424, 6835–6880 and 7420–7650. The rest I covered by search, and by execution.
• Tests file: I read only the S11 two-factor cases.
• Not hunted in depth: frigate_bridge, hotlist_sync, compact.py and the share-query handler.
• Line numbers: janus.py citations use the numbering of the attachment as uploaded.
• Reproductions: I extracted the uploaded code unmodified into a scratch tree and ran it. The handoff, the runner and the two scripts are attached; run-next.sh re-runs everything and writes a log.

1. Attack surface map (derived from the code)

Assets
• Reads and hits. Plate text sits in reads.plate / reads.plate_raw and hits.*_plate.
• Protection-order existence and the protected plates.
• The audit chain plus its sink, spool and checkpoints file.
• Secrets: the audit HMAC key (<db>.audit_key or env), the Ed25519 signing key (<db>.signing_key.pem), the TOTP store (<db>.totp.json) and users.json key hashes.
• The safety function itself: ALERT generation and the PENDING hit queue.

Entry points
• One HTTP door, behind a TLS proxy on the office LAN:
  ◦ Human roles: detective, patrol, supervisor, auditor, chain_auditor.
  ◦ Machine roles: ingest (/reads), jobs (/heartbeat, /health), partner (/share/query, /compact/*).
• Files Janus re-reads at runtime, on mtime change: users, cases, cameras and the TOTP store.
• Boot-time inputs: environment variables (NOCTUA_DEMO_MODE, NOCTUA_AUDIT_KEY, NOCTUA_SENTINEL_SINK, NOCTUA_TIER3_BASIS_TYPES), the checkpoints file and the restore marker.
• External processes: openssl resolved through PATH; cron scripts that read the database directly.

Trust boundaries
1. Proxy → Janus. Identity is two headers plus an optional TOTP header. There is no rate limit and no lockout anywhere in janus.py.
2. Ingest → Janus. The bridge is fully trusted. A camera registry exists, but there is no per-read attestation, and the database is the only store of "has this read been seen?"
3. Filesystem → Janus. Every security-relevant state file beside the database is re-read live, and the TOTP store fails open when it is missing or unreadable.
4. Environment → Janus. One variable flips the install mode.
5. Janus → outside witnesses. The sink is optional, checkpoints are compared only against a local copy, and acceptance state lives in the database being protected.

2. Findings register

F1 | High | 5 file, 7 operator (also plain disaster recovery) | Two-factor fails open. _totp_required (janus.py:2171–2181) demands a code only when the account has an entry in the TOTP store. _totp_load (2073–2088) returns {} when the file is missing or doesn't parse. Deleting or corrupting the file silently turns two-factor off for every enrolled account. /health shows enrolled_active: 0, but the install still reports itself as healthy, because nothing in ok_all (7497–7503) treats that as a degradation. | Executed. Corrupt store → key-only 200; deleted store → key-only 200.

F2 | High | 2 insider, or anyone holding a stolen/phished key | No lockout or rate limit on the second factor. OPERATIONS.md §10 promises "five failed logins lock the account"; no such code exists (locked_out at 3248 is only the audit-key lock). Each guess has roughly a 3-in-1,000,000 chance (±1 step window) against a code that is valid for 90 seconds and can be re-tried for as long as the run stays up, at full speed. | Executed. 300/300 wrong codes got 401, then the valid code was still accepted.

F3 | High (makes F2 silent) | 1 outsider on the LAN + 2 | The AUTH_FAIL global cap blinds the chain. After 25 failures per minute across all usernames (2214, 2233), nothing more is chained. Spraying 26 junk attempts then exhausts the budget: a targeted brute force against one enrolled account is then not audited at all, and no alert fires. This is not just an audit gap: the lockout that OPERATIONS.md promises does not exist, so the cap is the only evidence of the attack, and it is also capped. | Executed. After the spray, 300 failures against the target added 0 AUTH_FAIL entries.

F4 | High | 7 operator / supply chain | A production install can be made to believe it is a demo. One environment variable, NOCTUA_DEMO_MODE=1 (493), does three things: it waives two-factor for every account (2176), it admits multi-role god accounts — a user with two or more roles — that a production boot would refuse (1881–1907, 1987–2009), and it is invisible to /health and alert_check green, because ok_all (7497–7503) does not include demo mode. The only trace is demo_mode: true inside the SYSTEM chain entry. INSTALL.md §3 puts every secret in the same .env file, so that is where this one line would go. | Executed. Enrolled detective key-only 200; god account 200; health's degraded list has no demo entry.

F5 | Medium | 7 | Running without a sink reports healthy. sink_up = (not enabled) or … (7440–7441). Removing NOCTUA_SENTINEL_SINK turns off outside streaming and health stays green. Partial compensating control: daily checkpoints are still written, so a careful operator can spot it, but there is no named degradation. | Executed. sink_up: true, enabled: false.

F6 | Medium | 5 (rollback) | Rollback leaves a silent sink gap. After the database is rolled back k entries, _deliver_locked adopts the sink file's tail (sentinel.py:1709–1714). New appends with seq < tail are then marked "delivered" and skipped (1749–1763), so no outside witness ever sees them, and the chain still verifies — because the verifier's sig_alg checks the delivered entries' signatures before it checks the sequence, and entries with sig_alg set to "none" skip signature checking (1882). A rollback that removes entries before checkpointing also removes them from any checkpoint. | Code citation

F7 | Medium | 2 | Existence oracle for protection orders. For a detective, POST /hotlist on a protected plate returns 403 "not eligible for listing"; any other plate returns 404 "plate not found", and a read the caller does not know about returns 404. So a detective with no case can test whether a plate has a protection order by guessing it. No audit entry covers it: POST /hotlist checks eligibility before appending (janus.py:4320–4424). | Code citation

F8 | Medium | 6 (Frigate or bridge) | Retroactive alert withdrawal. The bridge receives the ALERT response (3751). A redelivery with the same (cam, event_id), event_type:"end" and a different plate makes that version current. The PENDING hit becomes WITHDRAWN and its outcome switches from ALERT to WITHDRAWN. The attacker needs the bridge (or the camera); the audit chain keeps the original alert, so the audit trail is intact — but the officer never sees it. The ALERT has been withdrawn, and the hit never surfaces in the UI. | Code citation

F9 | Medium | 1/2 (concurrency) | Out-of-lock chain write (R4 regression). A recovery code presented on /health or /audit/verify runs _totp_accept from the pre-lock warm (6856–6857). That path calls chain.append("RECOVERY_USED") (2164) on the shared connection outside DBLOCK. The entry can ride, and be rolled back with, another request's transaction — the chain sequence ends up with a gap, and the recovery-use evidence vanishes. (The same commit that fixes R4 re-opens it.) | Code citation

F10 | Medium | 7 | Shell enrollment bypasses two-key. provision.py enroll-2fa overwrites pending or must_reenroll entries without --force, and --force overwrites active ones (scripts 1753–1780). None of this is chained. After any restore, every account is must_reenroll, so the shell silently re-keys everyone. Combined with rotate-key (chained only as a CONFIG_CHANGED diff hash), an operator fully impersonates any user. | Code citation

F11 | Low–Med | 2/3 | Re-enrollment hands the secret to the confirmer. The confirming auditor receives the new TOTP secret in the HTTP response (4241–4267), and the target's API key is not rotated when the TOTP secret changes. Any auditor confirming their own re-enrollment now holds both factors. The two-person control that enrolment is supposed to give is broken by design. | Code citation

F12 | Low–Med | 4 (availability) | The chain_auditor role can't actually use two-factor. It is in TOTP_HUMAN_ROLES (2068), but compact.py and sentinel_audit.py send no TOTP header (scripts ~735, ~3330). Enrolling it locks the operator's own audit out, so no operator will enroll it, and the role stays single-factor. | Code citation

F13 | Low | 7 | Every signature check trusts a bare openssl on PATH. verify_bytes trusts the exit code of whatever openssl PATH resolves to (sentinel.py:1172–1176). A shim makes every partner, receipt, audit-report and checkpoint verification pass or fail on command. This is a local-compromise (attacker 7) chain, not a network one, and the fix is a pinned path or a pure-Python verifier. | Code citation

Hunt 2, command construction: clean.
• Every openssl call is an argv list with temp-file paths: sentinel.py:1110, 1115, 1144, 1173; rotation.py:122, 126, 150, 176.
• The only shell-shaped item is $CHECKPOINT_CMD, unquoted in publish_witness.sh, and it comes from the operator's environment.

Hunt 1, other parts verified to hold:
• Replay within one process is refused.
• Drift beyond ±1 step is refused.
• Recovery codes are single-use and flag health.
• The users-file "demo" flag is inert.

3. Ruling on ARGUS (spec v0.1)

ARGUS may not be built as specced.

It may exist in the pilot only in this reduced form:
A read-only anomaly reviewer that:
• runs on separate hardware;
• reads a copy of the sink;
• holds no Janus credential of any kind and no internet path;
• writes only to a human-held review log.
Tier A, Tier B and sanitized research are cut from the pilot.

Why, against the six open questions:
1. "Cannot suppress alerts" holds only as prose. The spec gives ARGUS a jobs-class key. The jobs role can POST /heartbeat for any job name with ok:true (janus.py:3379–3400). That is exactly how retention, checkpoint and witness dead-man alarms are silenced: each alert_check job is a /heartbeat that the jobs role can spoof. A jobs key is a kill-switch for alerting. It also holds the two-factor bypass.
2. Injection through the sink is real and has a concrete channel. Chain payloads carry free text that insiders control. For example, a supervisor's list_name is chained raw in LIST_REGISTER (3408–3418), bounded only by the 1 MB body cap. Usernames and agency flags are tolerable. Anything with hands is not.
3. The quarantine on research results is prompt-level only (Q3). Nothing mechanical stops web text from steering a Tier A call: one model holds both the web text and the local facts, and the only line between them is an instruction. If a chain entry or a supervisor's note contains an instruction, ARGUS can be told to do the opposite of what it was asked, with no human in the loop.
4. Rollback abuse (Q5) is worse than the spec assumes. "Automatic rollback to last-known-good" with a database snapshot is literally the F6 attack: it erases entries the sink has not yet seen, and the database's own copy is the only thing being compared.
5. The sanitizer (Q1) can't close the channel. Templates with version, error-class and query-choice fields, plus query timing and fragmentation across entries, still leak. The spec itself says the sanitize step is untested. I agree: it is not testable to the standard the brief sets, because the channel is the sink itself.
6. Same-host proxy (Q6): not acceptable. This follows from (3) and (5). If research ever returns, it must run on a separate appliance, driven by a separate, air-gapped operator, with its own key set, and never hold a Janus credential.

Also missing: the GPU "shedding" has no specified mechanism. It is invited to be tested, but nothing exists to test. I have not counted it as a finding.

4. Verdict against the criterion

NOT MET.
F1, F2, F3 and F4 are High. Each is exploitable by its stated attacker model with no compensating control in the code. The new two-factor surface is what the pilot is for, and it is the weakest part of the system: it fails open on file loss, has no lockout or rate limit, and can be switched off for the whole install with one environment line.

5. The single forced change (price of my vote)

Make two-factor fail closed, in _totp_required and _totp_load:
• Every account with a human role owes a valid second factor.
• A missing, unreadable or empty TOTP store, or a human account with no entry, is an authentication failure, not a waiver, and it degrades /health by name.
• Demo mode stays the only waiver, but demo mode itself becomes a named degradation in /health that alert_check reports.
F2/F3 (a real lockout plus an uncapped per-target count) are also required before convergence. This is not optional, but it is a separate fix, not the single change. If I can have only one, it is fail-closed two-factor.

6. Proposed pilot pen-test gate clause

Pilot Penetration-Test Gate (non-waivable). No camera may capture a real plate until an independent penetration test of the deployed pilot has been completed and its findings dispositioned in writing. The test covers three things:
• The application: Janus, the scripts, two-factor, the Compact endpoints and the ingest path.
• The network: the camera VLAN, WireGuard spokes, the TLS proxy and management access.
• The key-custody and restore procedures, run as live ceremonies: audit key, signing key, TOTP store, backups and restore.
The floor is the free federal services available to the City: CISA Cyber Hygiene vulnerability scanning and the MS-ISAC services for SLTT members. The standard is a paid tester independent of the authors, the council and the Department, retained under a written scope and rules of engagement approved by the City Attorney. Any Critical or High finding open at report date blocks go-live until it is fixed and a retest confirms the fix. The report, the retest and the disposition of every finding go to the Council and the outside auditor before the capture gate opens. The gate can't be waived by configuration, by schedule pressure, or by any single official. It is repeated before any expansion and after any change to the authentication, key-custody or restore code.

Legal note for the Ben Hooper / ACIC lanes, not decided here: if the system lands on Path B, CJIS advanced-authentication requirements would make F1–F4 compliance failures, not only security findings.
