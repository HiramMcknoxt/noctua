- receipts:
  - None
- report:
  - status: completed
  - summary: MODEL/EFFORT USED: Neon High (as previously set in this chat)
    
    The full Round 3 response from Gemini, verbatim:
    
    Proof of Read & Coverage Accounting
    
    All 16 files were attached directly and read 100% from line 1 to EOF (no truncation). Because this environment has no shell (wc -l) or Python runtime, line counts below are manual counts (with TRACK-11-REPORT.md cross-checked where reported); every code citation pairs the exact function/route name with its line region, and all runtime-dependent behaviors are marked (needs runtime test).
    
    | File | Coverage | Line Count (manual / reported) | Two Named Functions / Sections |
    |---|---|---|---|
    | council2/synthesis.md (SYNTHESIS.md) | Full | ~152 lines | Markdown — Convergent findings, Forced-change dispositions |
    | 1.1/janus.py | Full | ~2,710 manual / 2,829 reported | _startup_anchor_check, _share_query (also run_search, _rotation_status) |
    | 1.1/sentinel.py | Full | ~317 lines | _scrub_scan, Chain._append_txn (also Chain._stream, Chain.verify) |
    | 1.1/scripts/retention.py | Full | ~184 lines | frag_ref, heartbeat (also main) |
    | 1.1/scripts/compact.py | Full | ~142 lines | http, report_hash (also main) |
    | 1.1/scripts/rotation.py | Full | ~190 lines | seed_for, build_schedule (also _rounds_for, canonical) |
    | 1.1/scripts/sentinel_audit.py | Full | ~279 lines | verify_checkpoints, audit_url (also audit_db, main) |
    | 1.1/scripts/backup.py | Full | ~195 lines | sha256_file, config_paths (also _audit_key, main) |
    | 1.1/scripts/restore.py | Full | ~149 lines | sha256_file, refuse (also main) |
    | 1.1/scripts/checkpoint.py | Full | ~129 lines | _audit_key, heartbeat (also main) |
    | 1.1/scripts/frigate_bridge.py | Full | ~201 lines | extract, forward (also H.do_POST) |
    | 1.1/scripts/provision.py | Full | ~128 lines | save, issue_key (also load, find) |
    | 1.1/scripts/alert_check.py | Full | ~102 lines | notify, main |
    | 1.1/COMPACT.md | Full | ~145 lines | Markdown — How it works, Audit rotation — the anti-capture mechanism |
    | 1.1/TRACK-11-REPORT.md | Full | ~265 lines | Markdown — What was built, item by item, Interpretations |
    | 1.1/tests/run_tests.py | Full | ~1,160 lines | suite_compact, suite_retention (also Instance.start, suite_scripts) |
    
    A. Verification of Round 2 Gemini-Seat Findings
    
    Every finding attributed to the Gemini seat (convergent and seat-specific) in SYNTHESIS.md was verified directly against the 1.1 source.
    
    1. Tier 2 unbounded (Convergent #1) — FIXED (local /search only) — janus.py run_search (~L550–585) injects AND ts>=? for scope == "tier2"; _search_get (~L2510–2545) restricts /search to tier == 2; validate_fragment (~L520–535) blocks empty, less than 3 chars, %, and _. (Bypassed for partners via /share/query tier: 3 — see Section B.) — Standard: Janus claims
    
    2. Chain integrity weaker than claimed (Convergent #6) — FIXED-BUT-WRONG — sentinel.py Chain._append_txn (~L233–264) uses threading.Lock + BEGIN IMMEDIATE + busy-retry; verify() (~L298–317) checks seq != prev_seq + 1. Still broken: (a) _stream() (~L179–216) has no cross-process file lock (retention.py vs. janus.py race on sink.jsonl/.spool), and a truncated JSON line in .spool raises unhandled ValueError, crashing Chain.append() permanently; (b) restore.py (~L111–116) overwrites checkpoints.jsonl with the backup copy, neutralizing _startup_anchor_check; (c) janus.py /health omits chain_ok from degraded. — Standard: Janus claims
    
    3. Health lies by omission (Convergent #7) — FIXED-BUT-WRONG — janus.py /heartbeat (~L1020–1042) enforces ok is True; roles split into ingest/jobs; sink failure degrades /health. Critical omission: in janus.py _get /health (~L2225–2270), degraded does not include chain_ok! A corrupted Sentinel chain reports "chain_ok": false, "degraded": false, "ok": true, and alert_check.py (~L65) exits 0 ("OK: janus healthy"). — Standard: Janus claims
    
    4. § 1804(b) missing no-charges exit; holds never expire (Convergent #9) — FIXED-BUT-WRONG — janus.py /evidence/disposition + /evidence/disposition/confirm (~L1855–1940) implement clause (1) with two-key confirmation; holds gain review_by (+90d) surfaced in /health and /report. Gaps: (a) case_gate is not called on /evidence/disposition, /evidence/release, or /evidence/destroy despite docstring item 18; (b) confirmed disposition never destroys on-disk evidence bundles automatically, and re-exporting a hit in a later second orphans the prior bundle directory on disk forever (_evidence_post ~L1760–1800); (c) tier3_requests.results retains plaintext copies of reads/hits forever (see Section C). — Standard: Ark. Code § 12-12-1804(b) & Janus claims
    
    5. Hot-list hygiene (Convergent #10) — FIXED-BUT-WRONG — janus.py /reads (~L970–982) checks expires_ts <= ts, auto-deactivates, and chains HOTLIST_EXPIRED; hotlist_sync added to JOB_MAX_AGE_S; shared case_gate added across primary routes. Gaps: (a) POST /hotlist never validates expires ISO-8601 format (string compare breaks on non-ISO strings); (b) GET /hotlist (~L2345) returns expired entries that have not yet been hit; (c) POST /verify still does not re-check hot-list currency; (d) no hotlist_sync script ships in 1.1/scripts/. — Standard: Ark. Code § 12-12-1804(c) & Janus claims
    
    6. No WAL mode; no secondary indexes (Gemini-specific) — FIXED-BUT-WRONG — PRAGMA journal_mode = WAL added in janus.py (~L293), sentinel.py (~L118), retention.py (~L96). Indexes added on reads(plate), reads(ts), hits(read_plate), audit(kind). However: run_search uses leading-wildcard LIKE '%FRAG%', so SQLite cannot use idx_reads_plate or idx_hits_plate. idx_reads_ts helps Tier 2 (24h window), but Tier 3 (scope="full") still scans up to the entire 14-day table under global DBLOCK (needs runtime test at ~622k rows). — Standard: Performance / availability
    
    7. Auth uses != instead of hmac.compare_digest (Gemini-specific) — FIXED — janus.py auth (~L490–502) uses hmac_mod.compare_digest(sha(key), str(rec.get("key_sha256", ""))). — Standard: Security
    
    8. system role can spoof healthy heartbeats (Gemini-specific) — FIXED (with shared-jobs caveat) — system retired in provision.py (~L38) and janus.py; ingest is blocked (403) on /heartbeat. Caveat: all four cron jobs (retention, checkpoint, hotlist_sync, backup) plus compact.py share one jobs role credential, so compromising any single cron script can still spoof all other heartbeats and forge CROSS_AUDIT_OK. — Standard: Janus claims
    
    9. Audit-key file TOCTOU permission race (Gemini-specific) — FIXED (in janus.py / checkpoint.py; unfixed elsewhere) — janus.py _audit_key (~L206) and checkpoint.py _audit_key (~L73) now use os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600). Same TOCTOU pattern remains in provision.py save() (~L55), backup.py (~L105–134), and restore.py (~L109–116). — Standard: Security
    
    10. Small plate keyspace reverses plate_ref if HMAC key leaks (Gemini-specific) — NOT FIXED (worsened in 1.1) — janus.py plate_ref (~L218) now keys (plate, state), adding only ~5.6 bits; frag_ref (~L226) over 3-char fragments has only 46,656 combinations (reversible in milliseconds). Worsened: checkpoint.py (~L114) and sentinel_audit.py (~L132, ~L161) reuse NOCTUA_AUDIT_KEY to sign and verify checkpoints — forcing an agency to hand its plate-pseudonymization secret to external auditors if they want checkpoint HMACs verified! — Standard: Ark. Code § 12-12-1802 & Security
    
    11. Round 2 Forced Change (storage split + atomic appends + 1,000-write test) — PARTIAL / NOT FIXED — Storage split rejected in writing (SYNTHESIS.md), and the exact failure mode it warned about materialized in tier3_requests.results and backup.py (see Section C). Transactional appends: FIXED. 1,000-write stress test: NOT FIXED — run_tests.py suite_scripts (~L632–645) runs only 200 appends (2 × 100) and never tests retention.py VACUUM concurrently against live Janus traffic (needs runtime test). — Standard: Janus claims
    
    B. Attacking What's New in 1.1
    
    1. Protection-Order Suppression Redesign — Active Bypass on Formatted Reads (Code-Critical)
    
    Standard: Ark. Code § 12-12-1808(b) & Janus's own claims (item 5).
    
    The flaw: POST /suppressions (janus.py ~L1140) normalizes the plate via normalize_plate() ("VIC 309" becomes "VIC309") before hashing plate_ref(plate, state). Neither POST /reads (~L940) nor plate_ref() (~L218) calls normalize_plate()!
    
    The exploit: If Frigate or an ingest client sends "VIC 309" or "VIC-309", reads.plate stores "VIC 309" verbatim. In run_search() (~L575–584), plate_ref("VIC 309", "AR") != plate_ref("VIC309", "AR"). Any patrol officer, detective, supervisor, or Compact partner searching plate=309 or plate=VIC (both valid ≥3-char fragments) receives the protected victim's reads in plaintext.
    
    Why 184/184 missed it: run_tests.py suite_a2 (~L313–340) ingests "VIC 309", suppresses "VIC309", then searches only plate=VIC309 — which misses "VIC 309" in SQL LIKE because of the space, masking the filter failure!
    
    Secondary state-mismatch gap: frigate_bridge.py (~L46–50) admits Frigate does not reliably report state and defaults to "AR". A victim's out-of-state plate suppressed under "TX" will still leak whenever Frigate reads it as "AR".
    
    2. The Compact Sharing Gate (POST /share/query) & Cross-Audit (scripts/compact.py)
    
    Standard: Janus's own claims (COMPACT.md, item 22) & Ark. Code § 12-12-1804(d).
    
    Failed cross-audit does NOT close the sharing gate: _share_query (janus.py ~L2035–2042) runs: SELECT COUNT(*) FROM compact_audits WHERE agency=? AND ok=1 AND ts>=? (26h window). If Agency A passes at 08:00 and fails at 09:00 (CROSS_AUDIT_FAIL, ok=0), the 08:00 ok=1 row keeps our_audit == 1 and leaves sharing open for the next 25 hours. It must check the most recent audit row, not any passing row in the window.
    
    Checkpoint-receipt replay defeats the 26h freshness gate: POST /compact/checkpoint-receipt (janus.py ~L1905–1935) scans the entire checkpoints.jsonl file and accepts any (root, entries) pair ever published. A partner can replay a 6-month-old checkpoint every day; received_ts is stamped now_iso(), keeping the 26h receipt leg permanently green without ever auditing today's chain.
    
    Receipt signature is never verified: POST /compact/checkpoint-receipt stores d.get("sig") unverified, and compact.py (~L115) simply echoes the target's own checkpoint sig back rather than signing with the auditor's key.
    
    compact.py trusts the target's self-reported verification: compact.py (~L96–108) calls GET /audit/verify on the partner and trusts {"ok": true} without verifying hash linkage locally, never checks checkpoint sig, never checks checkpoint date freshness, and never queries /health (so a partner with broken retention or anchor_mismatch: true still gets CROSS_AUDIT_OK). Also, if --our-agency is omitted (~L113), a.our_agency or a.agency sends the partner's agency name instead of our own.
    
    Unbounded Tier 3 exposure to external partners: _share_query (janus.py ~L2062–2075) lets any partner request "tier": 3 (full 14-day store) with:
    
    Empty case_ref: "" (any(p in "".upper() ...) is False; non-empty check is missing);
    
    Zero auth_basis or basis_type;
    
    No config_status()["fail_closed"] check (stale users.json >24h closes local /search and /tier3/* with 503, but leaves /share/query open, honoring revoked partner keys);
    
    Direct tension with Ark. Code § 12-12-1804(d)(1)–(2), which bars governmental entities from exchanging captured plate data except data "that indicates evidence of an offense." Running arbitrary 3-char substring searches across 14 days of non-hit citizen reads for another agency is a major statutory question for the City Attorney.
    
    3. Rotation Scheduler (scripts/rotation.py & /compact/rotation/*)
    
    Standard: Janus's own claims (COMPACT.md, item 35).
    
    rotation_delinquent is mathematically dead code (can never fire for N ≥ 3): In janus.py _rotation_status (~L2670–2690), delinquency iterates over completed[-2:] (the last two rounds) and flags a member only when owed == 2 and filed_n == 0. By construction in rotation.py, every ordered pair (m, AGENCY) occurs at most once per full cycle — so across any 2 consecutive rounds, owed can never exceed 1. rotation_delinquent is permanently [].
    
    Wrong table and zero date filter in _rotation_status: When auditee == AGENCY (another agency owes us an audit), _rotation_status (~L2658–2666, ~L2680) queries compact_audits WHERE agency=auditor AND ok=1 — which records our audits of them, not their audits/receipts for us! Worse, neither query filters by round start/end timestamps, so a single passing audit from years ago marks every future round filed: true forever.
    
    The published seed is never used to generate the schedule: rotation.py build_schedule (~L78–112) hashes cycle_start + "|" + sorted(members) into seed, writes it into the JSON, and then feeds sorted(members) alphabetically into _rounds_for(slots) without ever using seed to permute slots. Every cycle with the same members produces the exact same fixed alphabetical schedule regardless of cycle_start.
    
    Input & lifecycle edge cases: build_schedule does not deduplicate members (["a","a","b"] produces self-audits ["a","a"]); POST /compact/rotation allows a supervisor to overwrite/reshuffle an active cycle mid-cycle (contradicting COMPACT.md), strips sig without checking it, and if cycle_start is in the future, round_idx is negative so Python's rounds[:round_idx] treats future rounds as completed.
    
    4. Standalone Audit Tool (scripts/sentinel_audit.py)
    
    Standard: Janus's own claims (item 21).
    
    Silent pass on chain truncation in URL mode: In audit_url (~L138–150), if cp["entries"] <= root["entries"]: has no else branch. If the target chain was truncated below the checkpoint count, audit_url skips anchor consistency without emitting a failure.
    
    URL mode trusts self-reported /audit/verify and ignores /health degradation flags: Does not verify chain hashes independently, does not check checkpoint date freshness, and ignores degraded, sentinel_sink_ok, config_stale, and cameras_silent.
    
    DB mode is NOT read-only: Despite claiming "standalone, READ-ONLY audit", audit_db (~L156) instantiates sentinel.Chain(a.db), which opens SQLite read-write and executes PRAGMA journal_mode = WAL, CREATE TABLE IF NOT EXISTS, and INSERT OR IGNORE INTO sink_state. It fails on read-only forensic copies (needs runtime test).
    
    Blind to tier3_requests.results: Checks only plate_fragment NOT LIKE 'pref:%' (~L202), missing the permanent plaintext plate dump in results.
    
    5. Chain Scrubber (sentinel.py _scrub_scan)
    
    Standard: Janus's own claims (item 26).
    
    False-positive Denial of Service on legitimate IDs: _PLATE_RE ((?:[A-Z]{2,3}[0-9]{3,4}|[0-9]{3}[A-Z]{3}|[A-Z][0-9]{3}[A-Z]{2})) matches valid camera names like CAM-101 (CAM101) and standard case numbers like CR-2027, AR-2027, or CPD-1001. Because Chain.append() raises ChainScrubError on any matching field, deploying a camera named CAM-101 or a case CPD-1001 causes HTTP 500 across /reads (on alert), /search, /hotlist, /verify, /holds, /tier3/*, and /share/query!
    
    Trivially bypassed by hostile insider: Lowercase ("abc123"), punctuation/prose ("plate ABC123"), or non-matching Arkansas plate formats ("ABC12D") pass right through _scrub_scan into the permanent chain.
    
    6. Log-Before-Data Ordering (Item 31)
    
    Standard: Janus's own claims (item 31).
    
    Unlogged GET endpoints: GET /tier3/pending (~L2395), GET /tier3/pending-reviews (~L2417), GET /compact/partners, GET /compact/checkpoint, and GET /compact/rotation/status return operational/investigative metadata (case_no, why, requester) with zero chain.append().
    
    Commit-before-log on write/export endpoints: Because db.commit() must run before chain.append() to avoid the two-connection WAL deadlock documented in TRACK-11-REPORT.md, POST /evidence/export writes the entire plaintext bundle to disk and commits evidence before chaining EVIDENCE_EXPORT; POST /tier3/approve and /tier3/emergency commit full results to tier3_requests before chaining TIER3_APPROVE/QUERY. If chain.append() raises (e.g., ChainScrubError on case="CR-2027" or disk/SQLite error), the side effect or plaintext evidence bundle is already committed with no matching audit entry (needs runtime test).
    
    7. Startup Anchor (_startup_anchor_check, Item 7)
    
    Standard: Janus's own claims (item 7).
    
    Silent fail-open on tampered/corrupted checkpoint file: In janus.py (~L452–462), if checkpoints.jsonl is deleted, truncated, or has one malformed line appended, except (OSError, ValueError): return exits cleanly with anchor_mismatch = False and zero audit entry.
    
    Does not verify checkpoint HMAC: Checks only hash_at_seq(entries) != root.
    
    Defeated by restore.py: restore.py overwrites live checkpoints.jsonl with the backup's older copy (see Section C), so restoring an older backup never trips the local startup anchor.
    
    Restart loop after clearing: POST /audit/anchor-accept deletes meta.anchor_mismatch (~L1401) without touching checkpoints.jsonl, so any Janus restart before the next daily checkpoint immediately re-triggers anchor_mismatch.
    
    8. Key-Loss Lockout (_audit_key, Item 30)
    
    Standard: Janus's own claims (item 30) & Ark. Code § 12-12-1808(b).
    
    Catches missing key, misses WRONG key: If NOCTUA_AUDIT_KEY is mistyped or swapped in .env (or replaced with a wrong .audit_key file), Janus stores no key fingerprint in meta, starts unlocked (KEY_LOCKED = False), and silently unmatches every active protection-order suppression and orphans all historical plate_ref entries.
    
    C. Audit of the Scripts (First-Time Council Review)
    
    1. scripts/retention.py — The 14-Day Promise Is Broken (Code-Critical)
    
    Standard: Janus's 14-day promise & Ark. Code § 12-12-1804(a)(2) (150-day hard cap).
    
    Permanent plaintext plate store in tier3_requests.results: janus.py stores full JSON search results (up to 200 raw reads + 50 hits, including plate, state, cam, ts) in tier3_requests.results (~L1505, ~L1612). retention.py (~L128–146) scrubs only plate_fragment and never deletes or nulls results. Every Tier 3 search creates a permanent, unexpired copy of captured plate data, retrievable forever via GET /tier3/results/<id> — violating both the 14-day policy and the 150-day statutory cap.
    
    frag_ref() mismatch breaks audit linkage: janus.py (frag_ref, ~L226) computes HMAC("FRAG|" + frag.upper())[:24]. retention.py (frag_ref, ~L66–74) computes full 64-char HMAC("FRAG|" + fragment) without .upper() and without [:24]. Scrubbed tier3_requests.plate_fragment values never match audit.payload.plate_ref.
    
    Silent scrub skip on default key-file installs: retention.py (~L63) reads only os.environ.get("NOCTUA_AUDIT_KEY", "") and never checks DB + ".audit_key". On a default install without NOCTUA_AUDIT_KEY in cron's environment, retention.py prints a skip message, leaves every tier3_requests.plate_fragment in plaintext, and still posts heartbeat(True)!
    
    Default path/port drift: Defaults to ../data/janus.db and http://127.0.0.1:8471 (NOCTUA_JANUS, ignoring NOCTUA_JANUS_URL), whereas janus.py, backup.py, checkpoint.py, frigate_bridge.py, and alert_check.py default to /data/noctua.db, port 8080, and NOCTUA_JANUS_URL.
    
    Silent chain-failure swallow: Lines ~171–179 catch chain.append("RETENTION_PURGE") exceptions, print to stdout, and still call heartbeat(True, detail).
    
    Live VACUUM + missing secure_delete: Connects without PRAGMA secure_delete = ON (~L96) and executes VACUUM (~L151) on the live DB while Janus holds open WAL connections (5s busy_timeout), risking lock timeouts or service stalls (needs runtime test).
    
    Unpurged residual tables/files: Released suppressions retain plaintext plate forever; unconfirmed evidence dispositions lock hits indefinitely; released on-disk evidence bundles are never cleaned up automatically.
    
    2. scripts/backup.py & scripts/restore.py
    
    Standard: Ark. Code § 12-12-1804(a)(2) & Security.
    
    backup.py --prune is opt-in, not default (~L94): Running backup.py from cron without --prune accumulates full DB backups (containing plaintext reads) forever, silently violating the 14-day rule and eventually the 150-day statutory cap.
    
    backup.py omits EVIDENCE_DIR: Active felony evidence bundles are excluded from backups.
    
    backup.py never sends heartbeat(False) on failure: Any exception crashes before step 4b (~L153), leaving /health green for up to 30 hours. Also creates manifest.json and checkpoints.jsonl without 0o600, and copies noctua.db/audit_key/config.tar.gz before chmod 0o600 (TOCTOU).
    
    restore.py Tar-Slip (arbitrary file overwrite): tar.extractall(config_dir) (~L124) lacks filter="data" or path traversal checks; a malicious config.tar.gz can write outside config_dir.
    
    restore.py accepts unsigned manifests silently (~L76): if manifest.get("manifest_hmac"): — stripping manifest_hmac to null and recalculating SHA-256 bypasses HMAC verification entirely, even when NOCTUA_AUDIT_KEY is set.
    
    restore.py leaves stale -wal / -shm files on disk (~L105–110): Moves aside db_path only, not db_path + "-wal" or db_path + "-shm". Restoring over an uncheckpointed WAL database risks immediate SQLite corruption or old WAL frame replay (needs runtime test).
    
    restore.py defeats local startup anchor & leaks retention: Overwrites live checkpoints.jsonl with the backup's old file (~L115), leaves *.pre-restore-<stamp> DB files (containing plaintext reads) on disk permanently with nothing pruning them, and fails to chmod 0o600 the restored DB.
    
    3. scripts/checkpoint.py
    
    Standard: Janus's own claims (items 7, 22).
    
    Non-transactional root / entries race (~L106–110): Runs SELECT hash ... ORDER BY seq DESC LIMIT 1 and SELECT COUNT(*) FROM audit as two separate queries with no transaction and no busy_timeout. A concurrent Janus append between the two reads publishes a mismatched {root: hash(N), entries: N+1} checkpoint — guaranteed to trip anchor_mismatch on restart and break Compact cross-audits (needs runtime test). Also uses COUNT(*) rather than seq even though hash_at_seq() indexes by seq.
    
    Key reuse & missing failure heartbeat: Signs checkpoints with NOCTUA_AUDIT_KEY (forcing key exposure to external auditors) and never sends heartbeat(False) on crash.
    
    4. scripts/frigate_bridge.py
    
    Standard: Janus's own claims (Round 2 Convergent #11) & Security.
    
    Zero authentication, zero body cap, zero socket timeout on POST /event (~L156–164): Any local caller (or network caller if rebound) can inject arbitrary plate reads, OOM the process via Content-Length, or stall worker threads indefinitely.
    
    No camera allowlist & unnormalized plates: Round 2 Convergent #11 ("any camera name accepted") remains unfixed in both frigate_bridge.py and janus.py. Still defaults state="AR", conf=0.95, and forwards unnormalized plate strings straight into Finding B.1's suppression bypass.
    
    Thread-safety & drift: Global stats and _seen (~L76–77) are mutated across ThreadingHTTPServer threads without a lock; startup warning (~L197) still names retired NOCTUA_SYSTEM_KEY; docstring (~L55) still describes 1.0 clock-skew behavior.
    
    5. scripts/provision.py & scripts/alert_check.py
    
    provision.py: save() (~L55–59) writes path + ".tmp" with default umask before calling os.chmod(tmp, 0o600) (TOCTOU race + fixed temp filename). Account creation, disablement, and key rotation leave zero Sentinel audit entries (Janus's _reload_config also does not chain USERS_CHANGED).
    
    alert_check.py: Relies exclusively on health.get("ok") (~L65), so it reports healthy (exit 0) when chain_ok is False; also lacks an explicit reason branch for retention_breach.
    
    6. tests/run_tests.py (Attacking the "184/184 Passed" Claim)
    
    The 184 checks are real HTTP/subprocess tests (assuming they pass at runtime — (needs runtime test)), but five entire scripts (backup.py, restore.py, frigate_bridge.py, provision.py, alert_check.py) have zero test coverage, and the suite's own fixtures accidentally hid the worst bugs:
    
    suite_retention inserted a tier3_requests row with results=NULL, checked only frag.startswith("pref:"), and explicitly set NOCTUA_AUDIT_KEY.
    
    suite_a2 tested suppression by searching "VIC309" instead of "309" or "VIC", missing the "VIC 309" leak.
    
    suite_compact never tested CROSS_AUDIT_FAIL after CROSS_AUDIT_OK, checkpoint replay, or rotation_delinquent.
    
    suite_scripts ran 200 concurrent appends instead of the promised 1,000-write test.
    
    D. Convergence Ruling
    
    Deployment-blocking / code-critical findings REMAIN. Verdict: NO-GO for operational deployment until fixed.
    
    Deployment-Blocking Code Defects (with Smallest Fixes)
    
    Unpurged plaintext plate reads in tier3_requests.results + broken retention.py (frag_ref, .audit_key, fail-open heartbeat):
    
    Smallest fix: In retention.py, set results = NULL on tier3_requests older than PURGE_DAYS (better: 72h after execution), import or match janus.py's frag_ref() (frag.upper(), [:24]), add DB + ".audit_key" fallback, set PRAGMA secure_delete = ON, align default DB/URL env vars, and call heartbeat(False) + exit non-zero if scrubbing or RETENTION_PURGE chaining fails.
    
    Protection-order suppression bypass on whitespace/hyphen plate variants ("VIC 309"):
    
    Smallest fix: Call normalize_plate(plate) inside plate_ref() and at POST /reads ingest (and frigate_bridge.py).
    
    /health ignores chain_ok: False (and alert_check.py misses it):
    
    Smallest fix: Add or not chain_ok to degraded in janus.py /health, and add explicit chain_ok and retention_breach checks in alert_check.py.
    
    Compact gate & checkpoint flaws (CROSS_AUDIT_FAIL ignored inside 26h; historical checkpoint replay; unprotected partner Tier 3; checkpoint.py non-transactional race):
    
    Smallest fix: Query the latest compact_audits row in _share_query; require checkpoint-receipt to match a checkpoint dated within 26h; cap /share/query at Tier 2 (or enforce non-empty case_ref, auth_basis, and config_status()["fail_closed"]); query SELECT seq, hash FROM audit ORDER BY seq DESC LIMIT 1 atomically in checkpoint.py; fix _rotation_status table/date/delinquency logic and actually permute slots with seed.
    
    Key-domain collision (NOCTUA_AUDIT_KEY reused for checkpoint HMACs) + ChainScrubError DoS on CAM-101 / CR-2027 + restore.py WAL/tar-slip/unsigned-manifest bugs:
    
    Smallest fix: Split NOCTUA_CHECKPOINT_KEY (or asymmetric Ed25519) from NOCTUA_AUDIT_KEY and store audit_key_fingerprint in meta to detect wrong keys at boot; exempt known non-plate fields (cam, case, agency) or restrict _scrub_scan appropriately and run scrub checks before db.commit(); in restore.py, move -wal/-shm aside, enforce tar.extractall(..., filter="data"), refuse unsigned manifests when a key is configured, and do not overwrite live checkpoints.jsonl.
    
    backup.py opt-in pruning & unauthenticated frigate_bridge.py:
    
    Smallest fix: Make backup.py prune by default (flag --no-prune to disable) and report heartbeat(False) on error; add shared-secret auth, body cap, socket timeout, and cameras.yaml allowlist validation to frigate_bridge.py / janus.py POST /reads.
    
    Non-Code Items Remaining (Not Code Defects)
    
    Legal questions for the City Attorney:
    
    Ark. Code § 12-12-1804(d)(1)–(2) vs. /share/query: Whether reciprocal partner queries over non-hit 14-day reads qualify as sharing data "that indicates evidence of an offense."
    
    Act 668 of 2025 (SB 446): Enrolled text adds private landowner/commercial ALPR authorization (60-day cap, subpoena requirement for government compulsion from private users) while retaining the 150-day law-enforcement cap under § 12-12-1804(a)(2) and evidentiary exclusion under § 12-12-1805(a)(3)(B) if public retention rules are not promulgated — City Attorney should verify full enrolled text against CANT-DO and municipal rules.
    
    Ark. Code § 12-12-1802 "derived data": Whether keyed plate_ref / frag_ref tokens in an append-only chain constitute regulated derived data given offline brute-forceability.
    
    Ark. Code § 12-12-1808(b): Whether supervisor-only /suppressed-hits satisfies the match exception and how out-of-state / default-"AR" reads affect protection-order compliance.
    
    ACIC/NCIC CJIS authority for hot-list ingestion (hotlist_sync is not yet built).
    
    Institutional & operational decisions: Off-box Clerk/auditor custody of the checkpoint signing key and streaming sink; encrypted backup storage; human enforcement of rotation_delinquent and overdue holds (>90d); independent pre-deployment certification of the exact production build.
    
    Accepted limitations (within Janus's honest-claims boundary): Direct host/OS/SQLite bypasses and provision.py filesystem edits sit outside Janus's HTTP mediation; single-node SQLite with global DBLOCK is explicitly scoped to small-city volume; prosecutor sign-off/disposition attribution relies on supervisor attestation rather than cryptographic prosecutor keys.
    
    E. One Forced Change
    
    Eliminate every unpurged plaintext plate copy outside reads/hits and make the entire retention pipeline fail-closed:
    
    Null tier3_requests.results on purge (or on a short post-execution TTL), unify retention.py's frag_ref() and .audit_key fallback with janus.py, fail closed (heartbeat(False), non-zero exit) on any scrub or RETENTION_PURGE failure, make backup.py pruning default-on, and clean up orphaned re-exported evidence bundles and restore.py .pre-restore-* snapshots.
    
    Prove it in tests/run_tests.py by asserting tier3_requests.results IS NULL post-retention, verifying frag_ref exact parity with the Sentinel chain, testing retention.py without NOCTUA_AUDIT_KEY in env, and adding live execution tests for backup.py, restore.py, alert_check.py, frigate_bridge.py, and the 1,000-write concurrency stress test.
    
    Want me to draft a clean patch list for the 1.2 fix build?
    
    ---
    Delivery notes (not part of Gemini's response): Model stayed Neon High throughout; the model was not changed and no new chat was started — same chat at https://gemini.google.com/app/b8aa69a4804e46f0. Gemini allows at most 10 attachments per message, so all 16 files could not go in one message: Batch 1 (10 files: SYNTHESIS.md, janus.py, sentinel.py, retention.py, compact.py, rotation.py, sentinel_audit.py, backup.py, restore.py, checkpoint.py) was sent with a hold note, and Gemini confirmed "Batch 1 received (all 10 files intact). Ready for Batch 2." The first Batch 2 attempt (frigate_bridge.py, provision.py, alert_check.py, COMPACT.md, TRACK-11-REPORT.md, run_tests.py) appeared to send and Gemini generated for about 5 minutes, but the turn then vanished from the chat; after a reload confirmed it was gone, I re-attached and re-sent Batch 2, and Gemini confirmed "Batch 2 received (all 6 files intact). All 16 files are loaded in full." Only then was the exact trigger message sent. The review response finished completely (no Stop button; Good/Bad/Copy/Redo controls shown). I did not click the "Yes" follow-up chip after its closing question. Headline outcome: NO-GO — deployment-blocking/code-critical findings remain, chiefly the unpurged plaintext tier3_requests.results store, the "VIC 309" protection-order suppression bypass, /health ignoring chain_ok, and the Compact gate/checkpoint flaws; the single forced change is to eliminate every unpurged plaintext plate copy outside reads/hits and make retention fail-closed.