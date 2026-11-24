- receipts:
  - None
- report:
  - status: completed
  - summary: MODEL/EFFORT USED: Gemini (standard included tier — the exact model/effort label displayed in the UI is not visible from inside model context; verify the UI is set to the best non-Ultra, non-credit-gated tier at highest included effort).
    
    All 20 attached files (janus.py, sentinel.py, all 12 files in scripts/, run_tests.py, TRACK-12-REPORT.md, COMPACT.md, SYNTHESIS.md, BRIEF.md, and gemini-review.md) were read in full from start to EOF. Because this environment has no shell (nl / wc -l) or Python execution runtime, code references cite exact file names, functions/routes, and verbatim code expressions, and behaviors requiring live execution are marked (needs runtime test).
    
    NOCTUA 1.2 is a major engineering step forward from 1.1: the PLATE_DATA_STORES spine, live Tier 3 ID resolution, canonical state-blind plate normalization, Ed25519 key separation, same-transaction primary chain appends, chain_auditor role, and 1,000-append two-process stress test are all real implementations. However, hostile code review uncovered seven deployment-blocking / code-critical defects — including a one-parameter bypass of the Tier 2 Compact sharing cap that hands partners full 14-day Tier 3 history, a nightly hotlist_sync.py SQL bug that wipes out every non-expiring hotlist entry, a retroactive protection-order suppression leak on existing hits, a self-signed manifest verification bypass in restore.py, and three false-failure bugs in sentinel_audit.py --db that will permanently fail every real deployment after 15–31 days.
    
    ## A. Verification of Round-3 Gemini-Seat Findings Against 1.2
    
    Each finding from gemini-review.md is verified against the 1.2 codebase, with the applicable standard (NOCTUA's claims vs. Ark. Code §§ 12-12-1801–1808).
    
    ### Prior Round-2 Carryovers (from Section A of Round-3 Review)
    
    Chain integrity weaker than claimed (streaming sink lock/spool crash; restore anchor overwrite; health chain_ok) — FIXED-BUT-WRONG (Standard: NOCTUA's claims). restore.py no longer overwrites live checkpoints.jsonl (saves backup copy as .from-backup-<stamp>), and janus.py _health now includes chain_ok in degraded and ok_all.
    
    Unfixed: sentinel.py Chain._stream() still has zero cross-process file locking (fcntl.flock) on sink_path / spool_path and no try/except ValueError around json.loads(line) when reading self.spool_path — a single truncated line in .spool permanently crashes Chain.append(), and janus.py / retention.py / hotlist_sync.py can still race on .spool. Worse, when Chain.append() participates in Janus's open transaction, _stream() fsyncs entries to the external sink before db.commit() (see Section B.4).
    
    Health lies by omission (chain_ok, unauth /health, missing hotlist_sync) — FIXED-BUT-WRONG (Standard: NOCTUA's claims). /ping is now the unauthenticated probe, /health requires supervisor / auditor / jobs, chain_ok and retention_breach degrade ok, alert_check.py names both explicitly, and scripts/hotlist_sync.py ships.
    
    Broken in new code: janus.py do_GET still acquires DBLOCK before calling _health() -> chain_ok_cached(), contradicting S5's claim that verification never runs under the write lock; retention_breach() omits scope='case' holds and ignores NOCTUA_BACKUP_DIR; and hotlist_sync.py wipes out every active hotlist entry with expires_ts="" (see Section B.8).
    
    § 1804(b) no-charges exit / evidence bundle orphans / tier3_requests.results — FIXED (with minor residuals) (Standard: Ark. Code § 12-12-1804(b) & NOCTUA's claims). Re-export in janus.py _evidence_post deletes the prior bundle directory in the same operation; release and confirmed disposition both set destroy_by = +30d, surfaced in /health and auto-destroyed by retention.py destroy_overdue_bundles(); tier3_requests stores IDs only and retention nulls legacy results bodies.
    
    Minor residual: case_gate is still not called on /evidence/release, /evidence/destroy, or /evidence/disposition (acceptable so a closed case cannot trap evidence from being released/destroyed), and automatic destruction by retention.py does not chain an individual EVIDENCE_DESTROY entry for custody_excerpt().
    
    Hot-list hygiene (expires validation, GET /hotlist, hotlist_sync) — FIXED-BUT-WRONG (Standard: Ark. Code § 12-12-1804(c) & NOCTUA's claims). hotlist_sync.py ships and chains HOTLIST_EXPIRED, and hotlist_members supports multi-list membership.
    
    Broken: hotlist_sync.py deactivates all non-expiring hotlist entries (expires_ts="" < now_iso()). Also unfixed from Round 3: POST /hotlist still does not validate expires ISO-8601 format, GET /hotlist still returns active rows whose expires_ts has already passed, and POST /verify does not re-check hotlist currency.
    
    WAL mode & secondary indexes (LIKE '%FRAG%' full scan under DBLOCK) — NOT FIXED (scope-accepted) (Standard: Performance / availability). run_search still executes leading-wildcard WHERE plate LIKE '%FRAG%' under global DBLOCK (Tier 2 is bounded by idx_reads_ts; Tier 3 scans full 14-day reads). janus.py docstring explicitly scopes this to small-city volume (needs runtime test at ~622k rows).
    
    Shared jobs role & TOCTOU permission races — FIXED-BUT-WRONG (Standard: Security). Shared jobs role remains an accepted small-city design trade-off. TOCTOU 0644 -> 0600 creation before os.chmod remains in provision.py save(), sentinel.py ensure_signing_key(), and backup.py (mitigated in backup.py by mode=0o700 on the backup directory).
    
    Key-domain collision & 1,000-write stress test (Round-2 Forced Change) — FIXED (Standard: NOCTUA's claims). Signing is now separated into an Ed25519 keypair via system openssl (sentinel.py), keeping NOCTUA_AUDIT_KEY strictly on-box for HMAC refs. run_tests.py suite_scripts now executes 1,000 concurrent appends across two processes (2 x 500), passing orchestrator re-tests (note: concurrent retention.py VACUUM vs. live Janus ingest is still untested (needs runtime test)).
    
    ### Section B & C Round-3 Findings
    
    B.1 Protection-order suppression bypass on formatted/out-of-state reads — FIXED-BUT-WRONG (Standard: Ark. Code § 12-12-1808(b) & NOCTUA's claims). Fixed: sentinel.plate_ref() normalizes internally and is state-blind; POST /reads stores canonical plate plus plate_raw; run_search() excludes suppressed plates in SQL before LIMIT.
    
    Still broken (code-critical): GET /hits, GET /tier3/results/<id> (live_hits), POST /verify, and POST /evidence/export check only the static hits.suppressed integer stamped at ingest time instead of joining suppressions live, and POST /suppressions does not retroactively flag existing hits. Any hit created before a protection order is entered continues to leak in plaintext to detectives/partners. janus.py backfills plate_raw but never normalizes pre-1.2 reads.plate or hits.read_plate.
    
    B.2 Compact sharing gate & compact.py — FIXED-BUT-WRONG (Standard: NOCTUA's claims [COMPACT.md] & Ark. Code § 12-12-1804(d)). Fixed: _share_query and share_gate_open now read the latest compact_audits row (ORDER BY id DESC LIMIT 1); /compact/checkpoint-receipt verifies Ed25519 signature and exact match to the newest checkpoint; /compact/audit-result verifies a signed report; compact.py independently recomputes the partner chain over /audit/range; shares require case_ref, why, basis_type, apply config_closed(), and rate-limit at 60/hr.
    
    Still broken (code-critical): (1) _share_query allows tier = 1 (and True), then calls run_search(frag, "tier2" if tier == 2 else "full") — giving any partner full Tier 3 historical access; (2) neither _share_query nor share_gate_open checks receipt/checkpoint age <= 26h, checks verified = 1, or fails closed when read_newest_checkpoint() is None; (3) /compact/audit-result does not check report["agency"] == agency or report["ts"] freshness; (4) compact.py still defaults our_agency to a.agency (the partner's own name!) and allows unpinned embedded cp["pubkey"] (see Section B.5).
    
    B.3 Rotation scheduler (rotation.py & /compact/rotation/*) — FIXED-BUT-WRONG (Standard: NOCTUA's claims [COMPACT.md]). Fixed: build_schedule now uses a documented SHA-256 Fisher-Yates permutation driven by seed; members are deduplicated and validated against active partners; cycle_start and period_days (7–120) are validated; active cycles cannot be overwritten without supervisor+auditor two-key ROTATION_VOID.
    
    Still broken (code-critical): POST /compact/rotation without a seed crashes with HTTP 500 (NameError: name 'uuid' is not defined); _rotation_status delinquency compares adjacent different agencies (rounds[i-1] and rounds[i]) and never excludes future rounds; POST /compact/witness has no role check, no signature check, and no chain entry (see Section B.6).
    
    B.4 Standalone audit tool (sentinel_audit.py) — FIXED-BUT-WRONG (Standard: NOCTUA's claims). Fixed: DB mode opens mode=ro and calls sentinel.verify_detached() without instantiating Chain; URL mode flags checkpoint truncation (cp["entries"] > root["entries"]) as a failure and surfaces /health degraded flags.
    
    Broken in new code (code-critical): registry_checks_db() has three false-failure bugs (scrubbed pref: fragments, destroyed evidence bundles with non-null bundle, and legally held hits > 31d) that cause sentinel_audit.py --db to fail permanently on every real deployment after 15–31 days; URL mode still trusts an unpinned embedded cp["pubkey"] when --pubkey / --pubkey-fingerprint are omitted.
    
    B.5 Chain scrubber (sentinel.py _sanitize) — FIXED (with residual bypasses) (Standard: NOCTUA's claims). Scrubber now hashes plate-shaped strings and chains a throttled CHAIN_SCRUB_FLAG instead of raising ChainScrubError; cam, camera, and agency are exempt so CAM-101 and CPD-1001 work end-to-end.
    
    Residual: _looks_like_plate() explicitly skips strings containing spaces/hyphens or lowercase ("ABC 123", "abc123"), so any unhashed free-text field reaching the chain (such as POST /lists list_name, or cam on INGEST_REJECTED) can still carry plaintext plates.
    
    B.6 Log-before-data / same-transaction ordering — FIXED-BUT-WRONG (Standard: NOCTUA's claims). Primary write handlers now share db with Chain(DB_PATH, conn=db) and commit data + audit entry in one transaction.
    
    Still commit-before-log: _anchor_accept (both branches), /compact/suspend, /compact/reinstate, /compact/rotation/void (both branches), and hotlist_sync.py; plus POST /compact/witness does not log at all; plus GET /tier3/pending, /tier3/reviews, /compact/partners, /compact/checkpoint, /compact/rotation/status remain unlogged; plus Chain.append() streams to the external sink before db.commit() (see Section B.4).
    
    B.7 Startup anchor (_startup_anchor_check) — FIXED-BUT-WRONG (Standard: NOCTUA's claims). Checks every checkpoint (including max-entries), fails closed on unreadable JSON, and remembers anchor_accepted across restarts.
    
    Broken: _anchor_evaluate() skips Ed25519 signature verification if cp.get("sig_alg") != "ed25519" (silent unsigned downgrade), and anchor_seen_checkpoint is only set at boot — so a long-running instance that never restarted after its first checkpoint fails checkpoints.jsonl is deleted before restart.
    
    B.8 Key-loss lockout (_audit_key / _key_fingerprint_check) — FIXED (Standard: NOCTUA's claims & Ark. Code § 12-12-1808(b)). Boot stores audit_key_fingerprint in meta, locks on both missing and mismatched keys, and refuses to start with exit code 3 (see Section B.7).
    
    C.1 retention.py — FIXED (Standard: Ark. Code § 12-12-1804(a)(2) & NOCTUA's claims). Purges by sentinel.PLATE_DATA_STORES, imports sentinel.frag_ref and sentinel.resolve_audit_key (with .audit_key fallback), sets PRAGMA secure_delete = ON, aligns defaults (/data/noctua.db, NOCTUA_JANUS_URL), checks WAL checkpoint busy status, retries VACUUM with RETENTION_VACUUM_SKIPPED, and fails closed (heartbeat(False), exit 1) on any purge/scrub/chain error.
    
    C.2 backup.py & restore.py — FIXED-BUT-WRONG (Standard: Ark. Code § 12-12-1804(a)(2) & Security). backup.py: pruning is now default-on (--no-prune to disable), evidence.tar.gz is included at 0600, manifest is Ed25519-signed, and failure sends heartbeat(False).
    
    restore.py: moves db + -wal + -shm + keys aside together, uses filter="data", prunes pre-restore copies, leaves .restore_marker, and never overwrites live checkpoints.jsonl — but has a critical self-signed trust-loop bypass in manifest verification, overwrites the DB before validating .restore_marker if boot hits KEY_LOCKED (see Section B.2 & B.7).
    
    C.3 checkpoint.py & publish_witness.sh — FIXED (with one shell edge case) (Standard: NOCTUA's claims). checkpoint.py reads (seq, hash) in one query inside one read-only transaction, signs with Ed25519, prints one JSON line to stdout, sends heartbeat(False) on error. publish_witness.sh parses only the JSON line and posts the witness heartbeat after git push.
    
    Edge case: git -C "$WITNESS_REPO" commit ... || true in publish_witness.sh silently swallows a real git commit failure (e.g., missing git user.name / user.email in cron), letting git push succeed with nothing pushed and posting witness heartbeat true.
    
    C.4 frigate_bridge.py — FIXED (with two edge cases) (Standard: NOCTUA's claims & Security). Adds fail-closed FRIGATE_BRIDGE_SECRET auth, 1 MB cap, 30s socket timeout, thread lock around stats / _seen, event-id forwarding, and stops fabricating "AR" / 0.95; Janus enforces cameras.json registry.
    
    Edge cases: (1) negative Content-Length bypasses BODY_CAP in both frigate_bridge.py and janus.py; (2) Janus persistent dedupe on (cam, event_id) drops Frigate's refined "end" OCR if an earlier "update" event arrived with a misread plate.
    
    C.5 provision.py & alert_check.py — FIXED (with minor residual) (Standard: NOCTUA's claims). provision.py adds chain_auditor; Janus chains CONFIG_CHANGED on content change; alert_check.py probes /ping, authenticates to /health, and names chain_ok and retention_breach explicitly. Minor residual: provision.py save() still writes .tmp before chmod(0o600).
    
    ## B. Attacking What's New in 1.2
    
    ### 1. PLATE_DATA_STORES Registry Completeness & the Schema Test (S1)
    
    Standard: NOCTUA's own claims (janus.py, sentinel.py, TRACK-12-REPORT.md) & Ark. Code § 12-12-1804(a)(2). Undeclared free-text stores in SQLite: PLATE_DATA_STORES rightly registers tier3_requests.why, tier3_requests.auth_basis, tier3_requests.review_note, share_queries.why, evidence.expand_reason, and evidence.disp_note because free text entered by operators can name a plate. By that exact same standard, two free-text tables were missed:
    
    holds.reason (janus.py schema & _post_holds): detective/supervisor free text explaining a hold (frequently naming the target vehicle/plate), retained indefinitely.
    
    witness_attestations.detail (janus.py /compact/witness): 500-character free text writable by any authenticated account (no role check), never purged.
    
    The schema test (suite_schema in run_tests.py) does NOT catch arbitrary new stores: suite_schema scans sqlite_master using pat = re.compile(r"plate|frag|results", re.I). Any newly added column named ocr_text, tag, vehicle, memo, reason, note, or detail passes the test completely unnoticed (which is why holds.reason and witness_attestations.detail passed, and why 6 of the registry's own columns would never have been caught if removed from the registry).
    
    The folder check (on_disk <= folders) inspects only directories directly under A.dir — it ignores loose files (e.g., an undeclared CSV/JSON export or spool file) and ignores directories outside <db_dir> (such as NOCTUA_BACKUP_DIR).
    
    To enforce completeness by construction, the schema test must use a full-column allowlist (every column is in PLATE_DATA_STORES or in an explicit NON_PLATE_COLUMNS manifest) so any unreviewed schema addition breaks the build.
    
    Three registry-enforcement contradictions between retention.py, janus.py, and sentinel_audit.py (Code-Critical):
    
    sentinel_audit.py registry_checks_db() permanently fails after 15 days on scrubbed Tier 3 fragments: TRACK-12-REPORT.md (Bug #6) notes that janus.py retention_breach() was fixed to check NOT LIKE 'pref:%' on scrub_fragment stores, but sentinel_audit.py was not fixed — it still queries WHERE plate_fragment IS NOT NULL. Once a scrubbed Tier 3 row is > RETENTION_DAYS + 1 days old, sentinel_audit.py --db exits 2 forever.
    
    sentinel_audit.py registry_checks_db() permanently fails after the first destroyed evidence bundle: it queries SELECT COUNT(*) FROM evidence WHERE bundle IS NOT NULL AND (destroyed_ts IS NOT NULL OR (destroy_by ...). Neither POST /evidence/destroy (janus.py) nor destroy_overdue_bundles() (retention.py) clears evidence.bundle — the column stays populated as the custody record. Thus any properly destroyed bundle causes a permanent fail (exit 2) without checking whether the directory exists on disk.
    
    sentinel_audit.py registry_checks_db() ignores active holds and unreleased evidence on hits: it runs SELECT MIN(ts) FROM hits WHERE 1=1, so any felony hit legitimately held past HOLD_DAYS + 1 (31 days) under § 12-12-1804(b) fails audit.
    
    janus.py retention_breach() omits scope='case' holds and ignores NOCTUA_BACKUP_DIR: retention.py protects hits covered by scope='case' holds, but janus.py retention_breach() checks only scope='hit' holds — triggering false /health retention breaches whenever a case-held hit passes 30 days. And janus.py hardcodes <db_dir>/backups rather than honoring NOCTUA_BACKUP_DIR, blinding /health when backups live on another mount.
    
    ### 2. Ed25519 Signing via System openssl (S7)
    
    Standard: NOCTUA's own claims (sentinel.py, restore.py, compact.py, sentinel_audit.py, COMPACT.md) & Security.
    
    Code-Critical — restore.py self-signed manifest verification bypass: In restore.py, manifest_sig is verified against set_pub = os.path.join(bdir, "signing_pub.pem") — a file inside the untrusted backup archive being restored — never against the live host's db_path + ".signing_pub.pem" or an out-of-band --pubkey / --pubkey-fingerprint. Furthermore, if manifest_sig verifies against the backup's own signing_pub.pem and the attacker sets "manifest_hmac": null, the if manifest.get("manifest_hmac"): block is skipped completely even when NOCTUA_AUDIT_KEY is configured in the host's environment. Even on default key-file installs, _find_audit_key() checks bdir/audit_key before db_path + ".audit_key".
    
    Exploit: An attacker generates a fresh Ed25519 keypair, builds a tampered backup directory containing noctua.db, config.tar.gz, and their own signing_key.pem / signing_pub.pem, signs manifest.json with their own key, sets manifest_hmac: null, and hands it to restore.py. restore.py verifies the attacker's signature against the attacker's public key, passes, and installs the attacker's DB (needs runtime test).
    
    Code-Critical — Unpinned trust-on-embedded-key in compact.py, sentinel_audit.py, and rotation.py: In compact.py, both --partner-pubkey and --partner-fingerprint are optional; if neither is passed, cp_pub = partner_pub or cp.get("pubkey") trusts whatever public key the remote partner embeds in /compact/checkpoint and records a passing signed audit.
    
    In sentinel_audit.py audit_url(), --pubkey and --pubkey-fingerprint are also optional (and run_tests.py invokes URL mode with neither!), silently verifying the partner's checkpoint against its own self-supplied cp["pubkey"].
    
    rotation.py --verify similarly verifies sched["sig"] only against the embedded sched["pubkey"] with no pinning option.
    
    Unsigned checkpoint downgrade in janus.py _anchor_evaluate(): _anchor_evaluate() wraps signature checking in if cp.get("sig_alg") == "ed25519": with no else: bad.append(n). Stripping sig_alg from a checkpoint line bypasses Ed25519 verification entirely (unlike sentinel_audit.py, which fails non-Ed25519 checkpoints).
    
    Key generation, temp-file, and PEM-validation hygiene in sentinel.py: ensure_signing_key() runs openssl genpkey -out priv before os.chmod(priv, 0o600) (world-readable TOCTOU window under default umask). sign_bytes() and verify_bytes() create sig = msg + ".sig" as a predictable filename in shared /tmp rather than inside a 0700 TemporaryDirectory. pubkey_fingerprint() calls base64.b64decode(body) without validate=True or PEM header validation, so POST /compact/partners accepts arbitrary non-PEM garbage strings as a partner's pubkey_pem.
    
    Custody: checkpoint.py honestly documents that keeping signing_key.pem on the same box as the DB does not stop a root/same-box insider; Clerk/off-box custody remains an institutional CANT-DO.
    
    ### 3. The chain_auditor Fence (S9)
    
    Standard: NOCTUA's own claims (janus.py, COMPACT.md) & Security / Availability.
    
    Access boundary holds: chain_auditor is hard-blocked on all POST routes at the top of _post(), blocked on DELETE /hotlist by the supervisor check, and restricted in _get() to CHAIN_AUDITOR_GETS = ("/audit", "/audit/root", "/audit/verify", "/audit/range", "/compact/checkpoint", ...) before any data query. Tier 3 result body access for auditor is also properly removed.
    
    Two availability / DoS defects inside the fence: GET /audit?limit=-1 bypasses the 1,000-row cap: janus.py computes chain.entries(min(int(q.get("limit", [200])[0]), 1000)). min(-1, 1000) is -1, and in SQLite LIMIT -1 returns every row in the audit table without bound under DBLOCK (and a non-integer limit=abc returns HTTP 500) (needs runtime test).
    
    GET /audit/verify runs uncached full-chain verification under DBLOCK: unlike /health (which caches for 60s), any partner holding a chain_auditor credential can repeatedly hit GET /audit/verify to force full-table chain.verify() scans while holding DBLOCK.
    
    ### 4. Same-Transaction Chain Appends (S11)
    
    Standard: NOCTUA's own claims (janus.py, sentinel.py, TRACK-12-REPORT.md).
    
    Still commit-before-log on 4 Janus write paths and 1 operational script: janus.py _anchor_accept: both the supervisor request branch (_meta_set commits internally before ANCHOR_ACCEPT_REQUEST) and the auditor confirm branch (db.commit() before ANCHOR_ACCEPT) commit before logging. janus.py POST /compact/suspend (db.commit() before PARTNER_SUSPEND) and POST /compact/reinstate (db.commit() before PARTNER_REINSTATE). janus.py POST /compact/rotation/void: both supervisor request (_meta_set commits before ROTATION_VOID_REQUEST) and auditor confirm (db.commit() before ROTATION_VOID). janus.py _post_reads: commits the read/hit/counter write before appending CLOCK_SKEW or flushing BACKFILL. scripts/hotlist_sync.py: updates hotlist_members, commits, closes the DB, and only then instantiates Chain(DB) to append HOTLIST_EXPIRED (unlike retention.py, it runs no VACUUM, so there is no reason not to share one transaction). POST /compact/witness: commits to witness_attestations with zero chain append.
    
    Stream-before-commit desynchronization in sentinel.py: When Chain.append() participates in Janus's open transaction (self.db.in_transaction is True), _append_txn() inserts into audit without committing, and Chain.append() immediately calls self._stream(entry) to write and fsync the entry to NOCTUA_SENTINEL_SINK. If the handler rolls back before db.commit(), the external sink permanently contains an uncommitted phantom entry whose seq and hash break chain continuity against the SQLite DB (needs runtime test).
    
    ### 5. Compact Gate Semantics, Share Cap, & Signed-Receipt Flow (S8, S10)
    
    Standard: NOCTUA's own claims (COMPACT.md, janus.py) & Ark. Code § 12-12-1804(d).
    
    Code-Critical — "tier": 1 bypasses the Tier 2 temporal wall on POST /share/query: _share_query checks if not isinstance(tier, int) or tier > 2 or tier < 1: — which accepts tier = 1 (and boolean True, since isinstance(True, int) is True). It then executes results = run_search(frag, "tier2" if tier == 2 else "full").
    
    Exploit: Any active Compact partner sends "tier": 1 in POST /share/query, bypassing the 24-hour Tier 2 wall and running a full 14-day Tier 3 historical search with no two-key approval, no case justification, and no Tier 3 review — contradicting COMPACT.md, and sharpening the § 12-12-1804(d) statutory exposure (needs runtime test).
    
    Code-Critical — Receipt freshness is never checked at query time, and missing checkpoints fail open: Both _share_query and share_gate_open verify only that the latest compact_receipts row matches newest when newest is truthy (if newest and (newest.get("root") != receipt[0] or newest.get("entries") != receipt[1]):).
    
    Defect 1: Neither checks checkpoint_ts age <= 26h (or received_ts age <= 26h) at query time. If the answering agency stops publishing daily checkpoints, newest never advances and the stale receipt keeps the share gate open indefinitely — directly contradicting COMPACT.md.
    
    Defect 2: If checkpoints.jsonl is deleted or unreadable (read_newest_checkpoint() returns None), if newest and ... evaluates to False and fails open, accepting any historical receipt row.
    
    Defect 3: Neither queries AND verified = 1, allowing unverified legacy 1.1 receipts (migrated with DEFAULT 0) to satisfy the gate.
    
    Signed audit-report replay across agencies and time: POST /compact/audit-result verifies report_sig over report and checks isinstance(report.get("ok"), bool), but never verifies report.get("agency") == agency and never checks report.get("ts") freshness (stamping now_iso() on arrival). A signed passing report for Agency A can be posted under Agency B, or an old passing report can be replayed indefinitely. POST /compact/reinstate selects the latest audit row with ORDER BY ts DESC LIMIT 1 instead of ORDER BY id DESC LIMIT 1 — non-deterministic if a pass and fail occur within the same second.
    
    compact.py defects: As noted in B.2, --partner-pubkey and --partner-fingerprint are optional (allowing silent trust of an embedded key). If --our-agency is omitted, payload = {"agency": a.our_agency or a.agency, ...} still sends the partner's agency name on the receipt (unfixed from Round 3), and --receipt-key defaults to --partner-key (wrong role credential).
    
    ### 6. Rotation Seed Permutation, Duty Tracking, & Witness Endpoint (S12)
    
    Standard: NOCTUA's own claims (janus.py, rotation.py, COMPACT.md).
    
    Seed-driven permutation works — with two edge-case defects: The SHA-256 Fisher-Yates shuffle in janus.py build_schedule() and rotation.py permute() genuinely permutes slots deterministically and produces a single Hamiltonian cycle where each member audits exactly one other agency and is audited by exactly one.
    
    Code-Critical crash: In janus.py _rotation_publish, if a caller omits seed (or passes ""), seed = uuid.uuid4().hex raises NameError: name 'uuid' is not defined (HTTP 500) because uuid is never imported in janus.py.
    
    Single-member self-audit & AGENCY exclusion: _rotation_publish accepts a 1-element members list (build_schedule produces auditor == audited), whereas rotation.py marks N < 2 inactive. Also, _rotation_publish requires set(members) <= partner_names (active rows in partners), which prevents including THIS-AGENCY itself in the rotation unless the agency registers itself as its own partner.
    
    Code-Critical — Duty tracking & delinquency in _rotation_status remain broken: Delinquency loops for i in range(1, len(rounds)): if rounds[i-1]["delinquent"] and rounds[i]["delinquent"]: delinquent... Because every agency is auditor in only one round per cycle, rounds[i-1] and rounds[i] are different agencies — the code blames Agency Y because Agency X was delinquent in the prior round! _rotation_status never filters for completed rounds (we < date.today()), so on Day 1 of a newly published cycle, future rounds have 0 filings and every agency from round 1 onward appears in delinquent_agencies. filed_by queries compact_audits without AND ok=1 (so a failing audit counts as duty fulfilled), witness queries witness_attestations without AND ok=1, and both check auditor even for rounds where neither auditor nor audited is this agency.
    
    Code-Critical — POST /compact/witness is unguarded, unsigned, and unlogged: In janus.py _compact_post, POST /compact/witness performs zero role check (any authenticated user — patrol, detective, ingest, jobs, or any partner — can file a "witness" attestation for any agency), no signature verification, and no chain.append().
    
    ### 7. Restore Boot-Marker Chaining, Never-Overwrite Checkpoints, & Key-Continuity Lockout (S6, S7)
    
    Standard: NOCTUA's own claims (janus.py, restore.py, TRACK-12-REPORT.md).
    
    Never-overwrite rule for live checkpoints: restore.py correctly writes the backup's checkpoints file to <db>.checkpoints.jsonl.from-backup-<stamp>, leaving the live checkpoints.jsonl untouched.
    
    Boot-marker RESTORE chaining has two flaws: In janus.py _consume_restore_marker(), if Janus boots with KEY_LOCKED == True (e.g., key mismatch after a restore), if not KEY_LOCKED: skips chaining RESTORE, and os.remove(marker) still deletes the marker — permanently losing the RESTORE audit entry once the operator fixes the key and restarts.
    
    In restore.py, live DB and keys are moved aside and overwritten before config.tar.gz and evidence.tar.gz are extracted with filter="data". If a tar-slip or corrupted tarball triggers refuse(), the live DB has already been replaced, contradicting restore.py's docstring ("exits 2 having restored NOTHING").
    
    Key-continuity lockout (refuse-to-start, exit 3): Works cleanly on 1.2-native installs: both a missing key over an existing chain and a mismatched NOCTUA_AUDIT_KEY against meta.audit_key_fingerprint cause Janus to refuse startup with exit 3 and a clear stderr message.
    
    Minor caveat: _key_fingerprint_check() pins sha(AUDIT_KEY) on first boot when meta.audit_key_fingerprint is None, so on a 1.1→1.2 upgraded DB (which has no stored fingerprint), passing the wrong key on the very first 1.2 boot silently pins it as the "correct" key.
    
    ### 8. Additional Findings Uncovered in 1.2
    
    Code-Critical — scripts/hotlist_sync.py wipes out every non-expiring hotlist entry on every run (Standard: NOCTUA's own claims [S5,S14]). janus.py _post_hotlist inserts d.get("expires", "") — storing the empty string "" (not NULL) when no expiry is set. hotlist_sync.py executes SELECT ... FROM hotlist_members WHERE active=1 AND expires_ts IS NOT NULL AND expires_ts < ?. In SQLite, "" IS NOT NULL is True and "" < "2026-..." is True. Every run of hotlist_sync.py deactivates every active stolen-vehicle and felony-warrant entry that has no explicit expiration date. run_tests.py suite_retention actually triggered this bug (wiping out RET100 alongside EXP200), but its assertion checked only all(e["plate"] != "EXP200" ...) and missed that b["entries"] was completely empty.
    
    Code-Critical — Retroactive protection-order suppression leak on existing hits (Standard: Ark. Code § 12-12-1808(b) & NOCTUA's own claims [S2,S3]). As noted in Section A (B.1): GET /hits, GET /tier3/results/<id> (live_hits), POST /verify, and POST /evidence/export rely solely on the ingest-time hits.suppressed column rather than querying suppressions live, and POST /suppressions does not update existing hits. A protection order placed after a hit was generated fails to hide that hit from non-supervisors or partners.
    
    High — Stale-config fail-closed (config_closed()) omitted from GET /tier3/results/<id> and other data routes (Standard: NOCTUA's own claims [S13]). GET /tier3/results/<id> returns plaintext plate reads without calling self.config_closed() (nor do GET /tier3/pending, GET /tier3/reviews, GET /report, POST /verify, POST /hotlist, DELETE /hotlist, POST /holds, POST /suppressions), contradicting S13's claim that fail-closed applies to all data endpoints.
    
    Medium — Missing 150-day startup ceiling on HOLD_DAYS (Standard: Ark. Code § 12-12-1804(a)(2)). janus.py refuses RETENTION_DAYS > 150 and TIER2_WINDOW_H > 72, but accepts arbitrary HOLD_DAYS (e.g., HOLD_DAYS=365), which would retain unverified/rejected hits past the 150-day statutory ceiling.
    
    Medium — Negative Content-Length bypasses 1 MB BODY_CAP (Standard: Security / Availability). Both janus.py _read_body() and frigate_bridge.py do_POST() check if n > BODY_CAP: without checking n < 0, allowing Content-Length: -1 to call self.rfile.read(-1) (unbounded read) (needs runtime test).
    
    Medium — chain_ok_cached() still runs under DBLOCK (Standard: NOCTUA's own claims [S5]). janus.py do_GET holds with DBLOCK: across _get() -> _health() -> chain_ok_cached(), contradicting the docstring and TRACK-12-REPORT.md claim that verification never runs under the write lock.
    
    Medium — Frigate "update" then "end" OCR refinement dropped by (cam, event_id) dedupe (Standard: Operational correctness [S4]). frigate_bridge.py forwards both "update" and "end" events and dedupes on (event_id, plate) so a corrected plate on "end" is forwarded, but janus.py dedupes on (cam, event_id) alone and drops the corrected final OCR as a duplicate.
    
    ## C. Convergence Ruling & One Forced Change
    
    ### Evaluation Against the Four Convergence Criteria
    
    No deployment-blocking or code-critical findings: FAILS. Seven deployment-blocking / code-critical defects remain (POST /share/query tier=1 full historical bypass; hotlist_sync.py wiping all non-expiring hotlist entries; retroactive suppression leak on hits; restore.py self-signed manifest bypass; Compact gate missing receipt freshness check + missing-checkpoint fail-open; compact.py unpinned embedded key; sentinel_audit.py --db permanently failing after 15–31 days; and rotation NameError + broken delinquency + unauthenticated/unsigned/unlogged /compact/witness).
    
    Prior forced changes implemented or answered in writing: SUBSTANTIALLY MET (with broken enforcement where it matters most). PLATE_DATA_STORES registry spine (Round 3) and the 1,000-append two-process stress test (Round 2) are built and executed, but the registry misses holds.reason and witness_attestations.detail, sentinel_audit.py and janus.py retention_breach() contradict retention.py on held hits, scrubbed fragments, and destroyed bundles, and suite_schema checks only a 3-word column regex.
    
    Only CANT-DO limitations or legal/institutional questions remain: FAILS. Concrete code defects remain, not just legal questions. City Attorney lane (still open, not code defects): Ark. Code § 12-12-1804(d) reciprocal sharing over pref: tokens; § 12-12-1808(b) supervisor-queue match exception; ACIC/NCIC authority for future upstream hotlist sync. Act 668 of 2025 is still unverified against the enrolled bill — flag, don't settle.
    
    Institutional/CANT-DO (properly documented): Clerk/off-box custody of signing_key.pem, witness-repo ownership, encrypted backup storage, Frigate media retention, single-node SQLite small-city scope.
    
    Do the orchestrator's 246/246 re-tests prove enough? NO. The suite is much stronger than 1.1's (adding suite_scripts, suite_a2, suite_a4, suite_backup_restore, suite_compact, suite_retention, and suite_schema) but it is still author-written and asserts the wrong invariants in the places that matter most: suite_retention ran hotlist_sync.py and verified only that EXP200 disappeared — missing that RET100 was destroyed in the same call. suite_compact tested tier=2 and tier=3, never tier=1; tested sentinel_audit.py --db only on a fresh instance with zero aged scrubbed fragments, zero destroyed bundles, and zero held hits; tested sentinel_audit.py --url without key pinning. suite_a2 / suite_a4 never tested placing a suppression after an existing hit was generated. suite_a5 always passed an explicit seed to POST /compact/rotation and never asserted delinquent_agencies == [] on Day 1. suite_backup_restore tested an unsigned manifest (null), never a tampered backup re-signed with an attacker's own signing_pub.pem. suite_schema tested only plate|frag|results column names, missing unregistered free-text columns.
    
    ### Explicit Ruling: NOT CONVERGED (NO-GO)
    
    The architecture of 1.2 is now genuinely sound — this does not need a redesign. It needs a surgical 1.2.1 patch release fixing the seven fail-open boundaries and registry contradictions above, with adversarial tests that fail before the fix and pass after it.
    
    ### One Forced Change
    
    Close every fail-open boundary and registry-verification contradiction across Janus and its companion scripts, and prove each closure with an adversarial test that fails before the fix:
    
    Access & suppression invariants (janus.py, hotlist_sync.py): Lock POST /share/query strictly to tier == 2 (type(tier) is int and tier == 2); apply live NOT EXISTS (SELECT 1 FROM suppressions WHERE active=1 AND plate=...) filtering on hits in GET /hits, GET /tier3/results/<id>, POST /verify, and POST /evidence/export; add self.config_closed() to GET /tier3/results/<id> (and remaining data endpoints); clamp GET /audit?limit= to 1..1000; add AND expires_ts != '' to hotlist_sync.py (and share one DB transaction for its update + HOTLIST_EXPIRED append).
    
    Cryptographic pinning & freshness (restore.py, compact.py, sentinel_audit.py, janus.py): Make restore.py verify manifests only against live host keys or an explicit --pubkey / --pubkey-fingerprint (never solely against keys inside the untrusted backup dir) and validate all tarballs before touching the live DB; require --partner-pubkey or --partner-fingerprint in compact.py; make _anchor_evaluate() reject non-ed25519 checkpoints; enforce checkpoint_ts <= 26h, verified=1, and fail-closed on missing newest in _share_query / share_gate_open; enforce report["agency"] == agency and fresh report["ts"] in /compact/audit-result; move remaining commit-before-log endpoints inside their transactions and move Chain._stream() post-commit (with fcntl.flock + JSON error handling).
    
    Registry & rotation parity (sentinel_audit.py, janus.py, run_tests.py): Align sentinel_audit.py registry_checks_db() and janus.py retention_breach() with retention.py (scrubbed pref: fragments, on-disk check for destroyed evidence bundles, scope='case' / scope='hit' holds, unreleased evidence, NOCTUA_BACKUP_DIR); register holds.reason and witness_attestations.detail and convert suite_schema to a full-column allowlist; import uuid in janus.py, fix _rotation_status per-agency completed-round delinquency, and gate + verify + chain POST /compact/witness.
    
    Adversarial proof in tests/run_tests.py: Add explicit failing-before-fix tests for share/query tier=1, hotlist_sync preserving non-expiring entries, post-hoc suppression hiding pre-existing hits, attacker-key-signed backup restore, sentinel_audit.py --db passing on an aged post-retention DB containing scrubbed fragments + destroyed bundles + held hits, POST /compact/rotation with omitted seed + Day-1 delinquent_agencies == [], and GET /audit?limit=-1.
    
    ---
    Delivery notes (browser agent, not part of Gemini's response): The model/effort actually shown in the Gemini UI was Neon High (Thinking: High) — the model picker showed Neon selected with High checked, and Carbon with a lock icon, i.e. still credit/Ultra-gated as in round 3, so it was correctly declined and Neon High was used. Gemini's own MODEL/EFFORT USED line above says the UI label was not visible from inside model context; the UI label was Neon High. Signed in as Corey Spangler (Pro). Chat: "NOCTUA 1.2 Security Council Review", https://gemini.google.com/app/d7b1a48bb20bf99d — retained as tab t1. Gemini caps a message at 10 attachments, so the 20 files were delivered in two messages: message 1 was the brief pasted exactly as written with janus.py, sentinel.py, alert_check.py, backup.py, checkpoint.py, compact.py, restore.py, sentinel_audit.py, run_tests.py and TRACK-12-REPORT.md; its generation was stopped before any response text appeared, then message 2 attached the remaining 10 files (frigate_bridge.py, hotlist_sync.py, provision.py, publish_witness.sh, retention.py, rotation.py, COMPACT.md, SYNTHESIS.md, BRIEF.md, gemini-review.md) with a note to review all 20 together. Gemini confirmed it read all 20 files in full. The complete response above is the final, finished response (response controls present, no Stop button); no file export/download was offered or used.