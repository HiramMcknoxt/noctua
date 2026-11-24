- receipts:
  - None
- report:
  - status: completed
  - summary: MODEL/EFFORT USED: Opus 5.5, Effort Max
    
    Model setup: Opened a new chat at https://claude.ai/chat/8364dde1-efa8-471e-bade-bfe19f5be81a (signed in as Corey, Pro). In the model picker, Opus 5.5 was already selected; Fable 5.2 was shown as "Requires usage credits" and was not selected, per the assignment. Effort was already set to "Max" (checked in the Effort menu; the picker showed "Opus 5.5 Max 4× or more usage"). No credit-gated step-down was needed. The pasted message was submitted exactly as assigned, and Claude's complete response finished after about 30 minutes. The full response text verbatim follows.
    
    ---
    
    I'm pulling the NOCTUA 1.1 repo files into a sandbox now. I'll read them in full, then go through A–E with line cites. Where I can actually run the code, I'll test it instead of marking items "needs runtime test."
    
    NOCTUA 1.1: round 3 hostile review (Claude seat, user's browser)
    
    Three defects still block any live-data pilot, and the Compact needs fixes before any partner joins. Two of the three blockers are in scripts nobody had reviewed before this round. Most of what my seat found in round 2 is fixed, and most of the janus.py fixes are real.
    
    I couldn't run anything. This session refused to execute the downloaded code, the same block as round 2. Everything below comes from reading the code. Items marked (runtime) depend on timing or environment. Everything else follows directly from the cited lines.
    
    How findings are tagged:
    
    [claim]: judged against NOCTUA's own claims (docstrings, TRACK-11-REPORT, COMPACT.md, the round-2 dispositions).
    [statute]: judged against Ark. Code §§ 12-12-1801–1808.
    [both]: fails both.
    
    Proof of reading
    
    File | Lines | Read | Two functions
    council2/synthesis.md | 156 | full | (prose; my seat's findings at 102–109)
    janus.py | 2,829 | full | run_search() 585, _share_query() 2214
    sentinel.py | 317 | full | _append_txn() 228, _scrub_scan() 80
    scripts/retention.py | 187 | full | main() 93, frag_ref() 65
    scripts/compact.py | 133 | full | main() 61, report_hash() 56
    scripts/rotation.py | 194 | full | build_schedule() 78, _rounds_for() 58
    scripts/sentinel_audit.py | 290 | full | audit_url() 87, audit_db() 163
    scripts/backup.py | 200 | full | main() 91, config_paths() 79
    scripts/restore.py | 148 | full | main() 59, aside() 108
    scripts/checkpoint.py | 127 | full | _audit_key() 50, heartbeat() 78
    scripts/frigate_bridge.py | 204 | full | extract() 80, forward() 126
    scripts/provision.py | 130 | full | issue_key() 67, save() 52
    scripts/alert_check.py | 97 | full | notify() 35, main() 51
    scripts/publish_witness.sh | 62 | full | (not on your list, but it publishes the outside anchor)
    COMPACT.md / TRACK-11-REPORT.md | 137 / 342 | full | (prose)
    tests/run_tests.py | 1,214 | partial: lines 1–207, 336–395, 1100–1214, and every check() name | suite_retention() 1102, Instance.start() 113
    
    Not reviewed: demo/seed_demo.py and DEMO-DATA.md.
    
    The "184/184" claim
    
    I couldn't reproduce it. If it is true, it still proves less than claimed, because every defect below passes the suite:
    
    Key from the environment, never the file. Every Janus instance and the retention run get NOCTUA_AUDIT_KEY in the environment (run_tests 101–102, 1144). The shipped default is the key file, which retention.py never reads (C2).
    Weak scrub test. The fragment-scrub check is startswith("pref:") (1161–1162). It can't see that retention writes a different ref than Janus does.
    Results never tested. The retention test inserts a Tier 3 row with no results (1134–1138), so it never checks whether results are purged. They aren't.
    Narrow suppression test. Suppression is checked by searching the full normalized plate (361). The suite stores the raw variant "VIC 309" (339–342) but never searches a fragment that would find it, and never tests a non-AR state.
    Missing tests. Nothing covers rotation status or delinquency, restore against the anchor, publish_witness.sh, a partner's auditor account reading data, or what AUTH_FAIL writes into the chain.
    Not independent. The build that wrote the code also wrote the suite. My round-2 acceptance condition asked for a suite written by non-authors, and Vesper's re-run used this same suite, blind spots included.
    
    Credit where due: TRACK flags its own untested items (315–323) and the share-tier choice (298–304) instead of hiding them.
    
    A. My round-2 findings, checked against 1.1
    
    My seat's six findings
    
    # | Round-2 finding | Verdict | 1.1 lines
    1 | One stalled connection freezes the service | FIXED | body read before the global lock (953–957); 30-second socket timeout (864–867)
    2 | "Confirm" with a capital C recorded as REJECTED | FIXED | 1135–1138
    3 | Non-numeric tier crashes the request | FIXED | 2638–2642, 2270–2275
    4 | Lost key file makes Janus silently mint a new key | FIXED for a missing key, FIXED-BUT-WRONG for a wrong one | 175–208
    5 | /tier3/pending shows every detective everything | FIXED | 2550–2570
    6 | Emergency review closes on "ok" | FIXED in letter only | 1709–1713
    
    Remaining problems:
    
    #1, body-size cap bypass. A negative Content-Length passes the cap check (901), and rfile.read(-1) then reads until the client stops sending (906). This happens before login, so memory use is unbounded. A standards-following proxy should reject the header, but NOCTUA_BIND bypasses the proxy. [claim] (runtime)
    #4, wrong key.
    The environment key wins over the key file (184–186) and is never checked against the stored data. A typo in NOCTUA_AUDIT_KEY, which retention.py pushes operators to set (C2), or a key from another install starts Janus unlocked with every suppression silently voided. That is the round-2 failure, reached another way.
    The suppressions table stores the raw plate and state (1302–1312), so a boot-time self-check would be one query. None exists.
    If the probe that counts audit rows errors for any reason, Janus treats the database as a fresh install and mints a key (198–199). checkpoint.py does the same (63–64). [both]
    #6. The review note is still optional (1735). "justified" alone closes a review; an enum alone doesn't make the review substantive. [claim]
    
    Convergent findings my seat shared
    
    Tier 2 unbounded: FIXED-BUT-WRONG. The time window is now in the SQL (598–603), only tier 2 is accepted (2643–2655), and wildcards and empty searches are refused (555–566). Remaining:
    The window runs on receipt time ts (985, 602), so a backlog replayed after an outage is fully searchable at Tier 2 for 24 hours.
    Tier 2 still accepts 3-character substrings (565, 597). My condition asked for exact plates. A search for "100" returns up to 200 plates containing 100, on one key.
    The window is an environment variable with no ceiling (155) and isn't recorded in the chain at startup. [claim]
    Unlogged data paths: mostly FIXED. /hits and /hotlist are now role-checked and chained (2451–2470, 2494–2506). Remaining:
    Refusals still not chained: 975–977, 1067–1069, 1131–1133, 1181–1183, 2408–2411, 2420–2422, and the /compact role checks (2047, 2074, 2134, 2151, 2165).
    /tier3/pending and /tier3/pending-reviews return why text without a chain entry (2550–2588). [claim]
    QUERY entries lack plate_ref and count: FIXED (2715–2718, 1573–1577, 1690–1694, 2283–2285).
    Suppression is an oracle and a sieve: FIXED-BUT-WRONG. The placeholder rows are gone and /hits is filtered, but new leaks exist (B7). [both]
    Evidence export bypass: core FIXED. Export requires a VERIFIED hit under the same case (1776–1791), scope is ±1 hour (1811–1822), release requires an export (1903–1914), and a destroy endpoint exists (1925–1961). Remaining:
    A re-export writes a new bundle folder and repoints the row (1836–1841, 1864–1875). The old bundle stays on disk forever. NOT FIXED.
    The prosecutor sign-off is still typed text (1891–1899).
    Nothing destroys a released bundle or flags one as overdue.
    Custody excerpts match fields.get("hit") == hit_id (848), but VERIFY records hit_id exactly as the client sent it (1177). A string "5" never equals the number 5, so that entry silently drops out of the bundle. HOLD entries carry no hit key (1238–1242, 1259), so holds never appear even though the code lists them (836–838).
    Bundles aren't backed up (C3). [claim]
    Chain integrity: FIXED in sentinel.py, NOT FIXED in effect. Appends are now atomic (228–258), failed sink writes spool (176–212), and verify() catches sequence gaps (298–317). But:
    The outside anchor doesn't work as shipped (C1).
    The startup anchor fails open if the checkpoints file is missing or any line in it is malformed (477–488).
    It never checks the checkpoint's HMAC signature, and it runs only at boot. [claim]
    Health lies by omission: core FIXED. ok must be explicit (1077), degraded covers the right conditions (2374–2377), and retention is cross-checked directly (2372–2373). Remaining:
    /health still requires no login and runs chain.verify() under the global lock on every call (2342, 2379). The round-2 stall moved from /audit/verify to /health.
    Camera silence is computed from stored reads (670–671). A camera dead for more than 14 days drops off the list once retention deletes its last read, and health turns green.
    hotlist_sync is a monitored job (159–160), but no such script ships, so a real install can never show green.
    The retention heartbeat reports ok even when the fragment scrub was skipped (C2). The checkpoint heartbeat reports ok before the witness is published (C1). [claim]
    § 1805 report: core FIXED (counts from outcomes 775–828, lists_checked 1002–1006, snapshots 1396–1416, K8 742–772). Remaining:
    REPORT_COMPILE chains only the snapshot's id, not a hash of its contents (1412–1413), so the "immutable" snapshot can be edited undetected.
    list_name is free text typed by detectives (1116–1117). The sanitizer removes only case numbers shaped like \d{4}-\d+ (737), so other case formats and names reach the public report. [both]
    § 1804(b) has two exits, code had one: FIXED-BUT-WRONG. The disposition path exists (1962–2040). Remaining:
    review_by isn't validated (1229–1231). "9999-12-31", or any value that sorts after today such as a word, never goes overdue (686–687).
    Tier 3 results have no exit at all (C2). [statute]
    Hot-list hygiene: expiry FIXED (1013–1021). An expiry is still optional and has no maximum (1123).
    Ingest trusts too much: NOT FIXED.
    State still defaults to AR and confidence to 0.95 (980, 997; bridge 128–129). The made-up confidence lands in the evidence file reads.json (1823–1825).
    Any camera name is accepted, there's no dedupe, and plates aren't normalized (979; bridge 127). [claim]
    Doc vs. code drift: the bind address and the environment retention settings are FIXED (143, 153–155). New drift is listed in D.
    
    My round-2 binding condition:
    
    (a) Temporal wall: yes. Exact plate only: no.
    (b) Suppression on search for every role: yes. Raw formatting variants and non-AR states: no.
    (c) Log before returning data: yes for read paths. Writes still commit before logging (B6).
    Acceptance by a non-author adversarial suite: not met.
    
    B. Attacking what's new
    
    B1. The Compact gate checks paperwork, not audits. [claim]
    
    Our leg. /compact/audit-result records CROSS_AUDIT_OK from a bare {"ok": true} posted by the jobs account or any single supervisor (2113–2130). Nothing is verified.
    Their leg.
    A receipt is accepted if it names any checkpoint we have ever published (2084–2093).
    Freshness is measured by when the receipt arrives, not when the checkpoint was made (2244–2246).
    We serve partners our checkpoint ourselves (2603–2621).
    So a partner can re-post one receipt every day forever without auditing anything.
    The "independent" check is a self-report.
    compact.py's check is the auditee's own /audit/verify answer (compact 97–101).
    The checkpoint and the chain entry it's compared against are both served by the auditee (93–106).
    The signature is passed through and never checked (115).
    sentinel_audit's URL mode works the same way and labels the result "chain integrity (independent)" (128–132, 134–157).
    A partner that rewrote its chain and appended a matching local checkpoint passes.
    COMPACT.md 19–20, "enforced by the software, not by trust", is false.
    Fix:
    Their leg can be proven from our own records. Janus already chains AUDIT_VERIFY and AUDIT_ROOT_VIEW with the caller's name (2413, 2417). Require that the partner's auditor account verified our chain within 26 hours and that their receipt names our newest checkpoint.
    For our leg, compact.py should recompute the hashes itself and remember the last (seq, hash) it verified for each partner. That needs a seq-range endpoint; /audit today returns only the newest 1,000 entries or one entry at a time (2431–2448).
    
    B2. A partner's audit account can read data. [claim]
    
    compact.py and sentinel_audit.py use an auditor-role account on the partner's Janus (compact 8–10; sentinel_audit 9).
    auditor is a data role (167). That account can read:
    /hits with plates (2451–2470);
    the whole hot list with case numbers (2494–2506);
    /stats and /report;
    GET /tier3/results/&lt;any id&gt; (2736), which is every Tier 3 result ever run, never purged (C2).
    None of this passes through the reciprocity gate, the Tier 2 window, or a second key.
    Fix: add a chain_auditor role limited to /audit, /audit/root, /audit/verify and /compact/checkpoint, and offer it in provision.py.
    
    B3. Shares get Tier 3 on one key, and the reason is thrown away. [claim]
    
    A tier 3 /share/query searches the full store with a fragment (2270–2281) on a single partner credential. A local detective needs a second supervisor for the same thing (1516–1583).
    There is no rate limit, so iterating fragments can pull the whole store.
    why is required (2249–2256), then never stored or chained. COMPACT.md 49–51 says it is recorded.
    case_ref, which is partner free text, is chained as written (2283–2285).
    Fix: take the builder's own flagged one-line change and cap shares at Tier 2 (TRACK 298–304). Store why.
    
    B4. The checkpoint is signed with the plate key. [claim]
    
    checkpoint.py signs with the same key that produces every plate_ref (checkpoint 113; janus 214–228).
    To verify your checkpoint, a partner needs that key. With it they can reverse every plate_ref in your chain, including SUPPRESSION_PLACE entries (1314–1315), which is effectively your list of vehicles under protection orders. Because HMAC is symmetric, they can also forge your checkpoints.
    Without the key, "signed" means nothing to them. Audit reports (sentinel_audit 273–279) and rotation schedules (rotation 157–158) have the same problem.
    In URL mode, if the auditor has its own NOCTUA_AUDIT_KEY set, sentinel_audit checks the partner's checkpoint with the wrong key and reports a false FAIL (136, 141–143).
    Fix: use a separate signing key and asymmetric signatures. The system's openssl can do Ed25519 if the stdlib-only rule must hold, and partners.audit_key_fingerprint already exists (366).
    
    B5. The rotation seed does nothing, and duty tracking reads the wrong table. [claim]
    
    The seed is never used.
    The seed is computed (rotation 82) but slots come straight from the sorted member list (94–97).
    Changing cycle_start changes only the seed string, so every cycle repeats the same rounds.
    "A pure function of a published seed" (COMPACT.md 99–103; rotation 6–12) is false.
    Agency IDs are self-chosen strings (2050–2062), so an agency picks its slot by picking its name.
    The pairing math is correct. I worked through three members by hand: round 1 b→c, round 2 a→b, round 3 a→c, with a, c and b as the witnesses, then rounds 4–6 mirrored. Every ordered pair appears once, no round has a mutual pair, the member with the bye is the witness, and rotation starts at 3 or more members (83–93).
    Janus accepts whatever the publisher sends.
    The member list isn't checked against the partners table (2181–2185).
    The period has no limit; a 36,500-day round never ends.
    cycle_start isn't validated (2169–2173), and a non-date value makes /compact/rotation/status return 500 (2769–2770).
    Wrong table.
    compact_audits holds our audits of partners (2121–2127).
    The status view uses it to decide whether a partner audited us (2781–2784) and who is delinquent (2806–2810), with no time window.
    The daily share gate requires our audit of every sharing partner, so every sharing partner shows "filed" forever and can never be flagged delinquent.
    The witness's duty isn't tracked anywhere.
    
    B6. Scrubber gaps, free text in the chain, and logging after the commit. [claim]
    
    The scrubber misses lowercase plates ("abc123"), plates inside longer text, and every plate format outside its three patterns (sentinel 76–77, 89–95). TRACK line 9 claims "No plate text in the Sentinel chain, anywhere". That is false.
    Free text reaches the permanent chain:
    AUTH_FAIL records the raw X-Noctua-User header (924–926). It needs no login, has no throttle, and accepts up to 64 KB per header line. The entry is permanent, copied to the sink and partner audits, can't be redacted without breaking every later hash, and makes every /health verify() slower (2379).
    BLOCKED entries record whatever case was sent (1490–1492, 1646–1648) and whatever hit was sent (1143, 1152, 1760, 1910).
    SHARE_BLOCKED records agency from any logged-in user, any role (2226–2232).
    category is recorded on HOTLIST_ADD and every ALERT (1127, 1061).
    HOLD_PLACE records ref and review_by (1238–1242).
    cam is recorded on BACKFILL, CLOCK_SKEW and ALERT (704–706, 1050, 1060).
    False positives happen after the data is committed.
    A camera named "CAM-101" becomes "CAM101", which matches the plate pattern. So would a badge-style username like "PD1234" or a case number like "CR-1234", and provision.py doesn't restrict names (80).
    Every write path commits first and chains second, on purpose, to avoid a deadlock (TRACK 261–266). Examples: /reads commits at 1043 and chains at 1060; /verify commits at 1176 and chains at 1177.
    So a scrubber hit, or a database busy timeout after 12 retries (sentinel 235–258), leaves an action committed, unlogged, and answered with a 500.
    With a camera named CAM-101, every hit from it sits in the hits table with no ALERT entry. That is the fault-injection test TRACK says was never run (321–323).
    Tier 3 executions also store results (1562–1568, 1675–1684) before chaining the QUERY entry.
    Fix:
    Append the chain entry inside Janus's own transaction. The audit table is in the same SQLite file, so one transaction can cover both the data and its log entry.
    Chain hashes of free text, never the text, and make category an enum.
    
    B7. Suppression in 1.1: where a motivated abuser with a login still gets through. [both]
    
    State mismatch.
    Suppression is keyed by plate and state (1297–1301), and state defaults to AR (1298).
    The bridge stamps AR whenever Frigate gives no state (bridge 43–47, 128), which its own docstring says is the usual case.
    A supervisor who correctly enters an order's non-AR state creates a suppression no read will ever match. The plate shows up in search for every role (614) and in /hits (2462–2463).
    A detective can still hot-list it under the default AR with no SUPPRESSION_CONFLICT (1106). That is the 1.0 attack, back.
    This is a regression: 1.0 keyed plate refs without state (synthesis 71).
    Formatting variants.
    Ingest only uppercases plates (979; bridge 127), while suppression strips spaces and hyphens (1297), and search compares refs against the raw stored row (614).
    With the suite's own data ("VIC 309" stored, suppression on VIC309), /search?plate=VIC returns the "VIC 309" row to every role.
    The near-match warning (1316–1332) tells the supervisor but leaves the leak. A suppression entered as "VIC 309" normalizes back to VIC309, so the variant can never be suppressed.
    Wrong key: every suppression is voided at once (A #4).
    The chain leaks location and time.
    ALERT is chained for suppressed hits too, with the camera name (1059–1061), and detectives can read /audit (2420).
    Comparing ALERT hit ids against /hits exposes which hits are suppressed, with camera and time.
    Whether camera plus time is captured plate data belongs with the derived-data question already routed to the City Attorney.
    Other oracles:
    /stats shows detectives the suppressed_pending count (2519–2521).
    The hot-list refusal message tells any detective whether a plate has a protection order on file (1113–1115).
    Search drops suppressed rows only after taking the first 200 (604–617). A short page then signals that something was removed, but only when a fragment matches more than 200 rows in the window.
    A path around the queue. /verify accepts any pending hit id, suppressed or not (1146–1148), and export doesn't check either (1764–1767). A detective can get a suppressed hit's plate and its ±1 hour reads into an evidence bundle without going through the supervisor-only queue.
    
    B8. Settings a careless operator can turn. [statute]
    
    RETENTION_DAYS has no ceiling (153), and /health measures breaches against the same variable (2372–2373). Setting it to 200 keeps health green while breaking the 150-day cap.
    The 24-hour stale-config fail-closed covers only /search and Tier 3 (1495, 1555, 1651, 2680). /hits, /hotlist, /tier3/results and evidence export keep serving yesterday's users, including ones that were revoked.
    Fix: refuse to start above 150 days, and record the effective configuration in the SYSTEM entry at startup (2826).
    
    C. The scripts
    
    C1. There is no working outside anchor as shipped. [claim] The round-2 disposition depends on it: "the witness/checkpoint layer … is what makes a restore detectable" (synthesis 137–139).
    
    publish_witness.sh never publishes.
    It parses checkpoint.py's output as a single JSON object (42–45), with set -euo pipefail on (35).
    checkpoint.py prints the checkpoint (121) and then always prints a second line: "heartbeat skipped" (84), "heartbeat sent" (98), or "heartbeat FAILED" (100).
    json.load fails on the extra line, and the script exits at line 43. Nothing reaches the witness repo or the Clerk. Running the script once on any install will show it.
    By then checkpoint.py has already sent an ok heartbeat (122–123), so /health stays green.
    restore.py rolls back the anchor.
    It moves the live checkpoints file aside and installs the backup's copy (115, 122–124).
    After a restore, the restored chain matches the newest local checkpoint, so the startup anchor check (489–495) sees nothing. The old file sits unused as *.pre-restore-*.
    Result: the sink is optional (sentinel 142), so with no sink and a broken witness, nothing outside the box holds a copy. An insider can restore a two-day-old backup set, or re-hash the chain and append a new checkpoint with the server-side key, and /health still reports chain_ok.
    A rare false alarm. checkpoint.py reads the chain's root and its entry count in two separate statements (106–109). An append in between produces a checkpoint that doesn't match itself. The result is a false anchor mismatch at the next boot and a false CROSS_AUDIT_FAIL at every partner. (runtime; rare)
    Fix:
    checkpoint.py sends its heartbeat messages to stderr.
    publish_witness.sh posts a witness heartbeat only after the push and the email succeed, and Janus monitors that job.
    restore.py keeps the live checkpoints file and chains a RESTORE entry.
    The anchor check uses the checkpoint with the most entries, not the last line.
    checkpoint.py reads seq and hash in one query.
    
    C2. retention.py: Tier 3 results are kept forever. [both] My round-2 runner-up asked that the retention job be reviewed before any deployment. This is why.
    
    What's kept.
    tier3_requests.results stores the full output of every Tier 3 search: up to 200 reads and 50 hits, each with plate, camera and time (1562–1567, 1675–1683).
    retention.py scrubs only plate_fragment (135–154) and states that rows are never deleted (24). Nothing anywhere clears results.
    Who can read it. The requester, any supervisor, any auditor, and a partner's audit account can read these results forever (2736–2737; B2).
    Why it matters.
    Neither § 1804(b) exit ever deletes them, and they outlive the 150-day cap.
    The round-2 disposition promised "derived text 14d" (synthesis 136).
    sentinel_audit's DB mode would still report the derived-data purge as ok (213–224).
    Fix: set results to NULL at RETENTION_DAYS, extended only while a hold or unreleased evidence covers the case. Add the same check to sentinel_audit and a test row that has results.
    Also in retention.py:
    It reads the key only from the environment (62), while Janus defaults to the key file (187–189). On a default install the fragment scrub is skipped with a printed note (146–150), and the heartbeat still says ok (183).
    Its fragment ref is the full 64-character hex digest (73); Janus's is cut to 24 (228). A scrubbed row can't be matched to its chain entry, despite the comment calling it "the same keyed HMAC the chain uses" (22–23).
    It never turns on secure delete for its own connection (95), relies on VACUUM (157), and ignores the result of the WAL checkpoint (160). (runtime)
    VACUUM runs while Janus is live, and Janus waits only 5 seconds for the database while holding its global lock (301). (needs load test)
    It deletes reads by receipt time (104–105), so a backlog delivered after an outage lives 14 days past its arrival.
    Evidence bundles are never deleted, orphaned ones included.
    Its default database path and port differ from Janus's (51–53 vs. 140, 144).
    
    C3. backup.py and restore.py. [claim]
    
    The key travels with the data it unlocks.
    The audit key ships in the same backup set as the database (backup 124–131), and the manifest's HMAC is made with that key (142–147).
    restore.py verifies the manifest with the set's own key file when the environment has none (restore 79–80).
    Anyone who can write to the backup store can edit the database, re-hash it, re-sign the manifest, and get "manifest verified".
    backup.py's claim that the HMAC proves the set wasn't altered (26–28) is false whenever the key is in the set, which is the default.
    Unsafe archive extraction. tar.extractall(config_dir) runs with no filter (134). On Python 3.12 and 3.13, a crafted config archive can write outside /config as whoever runs the restore. Combined with the self-verifying manifest, a planted backup set means code execution at restore time.
    Plate data lives about 28 days in backups. Backups hold reads up to 14 days old and are kept 14 days (58, 183). Pruning is optional (92, 182); without it, backups pile up with no limit.
    Evidence isn't backed up. A disk failure loses every bundle while a restore brings back evidence rows pointing at nothing.
    Fix:
    Keep the key in separate custody from the database, and have restore take the key only from the environment or that custody, never from the set.
    Extract with filter="data".
    Check the key against the suppressions table at boot and lock on a mismatch.
    
    C4. Bridge, provisioning, alerting.
    
    frigate_bridge.py: the ingest defaults are unfixed (127–129), there's no body-size cap (163–164), and the dedupe set is wiped all at once at 10,000 entries (191–192).
    provision.py: no rule for usernames (80) and no chain-only role (37).
    alert_check.py: sound, but it trusts /health's ok (65), so it inherits every /health blind spot above.
    
    D. Convergence
    
    Yes, deployment-blocking defects remain. Each has a small fix.
    
    Blocking for any live-data deployment:
    
    No working outside anchor (C1). Fix: the five edits in C1. [claim]
    Tier 3 results kept forever and readable by supervisors and auditors (C2). Fix: about three lines in retention.py, plus the audit-tool check and a test. [both]
    Suppression fails on a non-AR state, a formatting variant, or a wrong key (B7, A #4). Fix: the forced change in E. [both]
    
    Blocking only for activating the Compact. A pilot with no partners can ship with partner accounts unissued.
    
    A partner's audit account reads data (B2), shares get Tier 3 on one key with no reason recorded (B3), both audit legs are self-attested (B1), the checkpoint is signed with the plate key (B4), and rotation status reads the wrong table (B5). The fixes are in each item.
    
    Code-critical, but not blocking on its own:
    5. Writes commit before they're logged (B6).
    6. Unauthenticated free text in the permanent chain (B6).
    7. /health verifies the whole chain on every call, under the global lock, with no login. Fix: verify incrementally from the last verified entry, or require a login.
    8. Ingest defaults and no camera allowlist (A).
    9. No ceiling on RETENTION_DAYS (B8).
    
    New doc drift in 1.1:
    
    COMPACT.md: "enforced by the software" and "justification recorded".
    The rotation "seed".
    TRACK line 9 ("no plate text in the chain, anywhere").
    TRACK item 18: the case gate runs only on /evidence/export, not all of /evidence/*.
    retention.py 22–23.
    backup.py 26–28.
    sentinel_audit's "(independent)" label.
    
    Not code defects:
    
    Act 668 of 2025 stays with the City Attorney. Nothing in 1.1 conflicts with a 150-day cap for public agencies except C2, which breaks the cap with or without the amendment. If the secondary source's description of Attorney General enforcement is right, C2 and B7 are where the exposure sits.
    Legal questions already routed:
    whether § 1808(b) has a supervisor exception;
    whether ALERT entries (camera plus time) for a suppressed hit can be disclosed;
    the derived-data question, which B4 sharpens because a partner would need your key to verify checkpoints;
    whether keeping Tier 3 results for an open case fits § 1804(b)'s ongoing-investigation exception.
    Institutional decisions: key custody on the Clerk's side, the stdlib-only rule vs. asymmetric signatures, and independent certification.
    Accepted limitations:
    one detective key is enough to add a hot-list entry (it's logged);
    two supervisors can collude;
    the prosecutor sign-off is typed text;
    the 25% emergency-share threshold (K8) is reported, not enforced;
    Compact membership and the consequences of delinquency belong in the agreement, not the code.
    
    E. Forced change
    
    A suppression binds the plate, not the record. No live-data deployment until:
    
    (a) every suppression check matches on normalize_plate(plate) alone, ignoring state, and is applied in SQL before any row limit. This covers ingest flagging, search, /hits, /share/query, Tier 3, and evidence export;
    
    (b) Janus and the bridge store the normalized plate (raw OCR text can go in a separate column);
    
    (c) at boot, Janus recomputes plate_ref for every suppressions row that has a stored plate, and starts LOCKED on any mismatch, exactly as it does for a missing key;
    
    (d) ALERT entries for suppressed hits carry no camera, and /stats shows suppressed counts to supervisors only.
    
    Acceptance tests. Each must fail against 1.1 as published and pass after the fix:
    
    Non-AR state. Suppression entered with state TX; a read arrives with no state. The plate is invisible to every role in a 3-character fragment search and absent from /hits, and a detective's hot-list add under AR gets 403 SUPPRESSION_CONFLICT.
    Formatting variant. Read stored as "VIC 309", suppression on VIC309. /search?plate=VIC returns nothing for any role.
    Wrong key. Janus started with a different NOCTUA_AUDIT_KEY starts LOCKED.
    
    Why this one: it's a regression introduced in 1.1, it fails without any visible sign, and the person it fails is exactly the one the threat model names, someone a motivated abuser with a login is trying to find. The other blockers in D stand either way. This is the one I wouldn't sign without.
    
    I can write the tests in E and the checks for C1 and C2 as one script Vesper can run on a scratch install. That would give the council the runtime confirmation I couldn't get here.
    
    Sources: janus.py, sentinel.py, retention.py, publish_witness.sh, restore.py, council2/synthesis.md
    
    ---
    Chat retained in tab t1: https://claude.ai/chat/8364dde1-efa8-471e-bade-bfe19f5be81a