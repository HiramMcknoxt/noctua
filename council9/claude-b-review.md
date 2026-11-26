# NOCTUA Council Round 9 — Claude seat B review (Merlin slot)

Seat: Claude seat B (seated in the Merlin slot at Corey's direction). Model/effort per the browser operator's interface observation: Opus 5.5, Medium (the seat's own text claims it cannot see the display; per seat protocol the interface observation governs). Chat: https://claude.ai/chat/67be8544-57ae-42d6-a7f2-c0ccf74e12a4. Executed review: rebuilt the tree from the attachments; reproductions run (scripts in the seat's tarball, which could not be downloaded from the chat — buttons obscured; the review document describes each repro and result). Below: the seat's chat response verbatim, then its review document as read in the chat (the browser notes a few long sentences were elided by the accessibility view, marked with brackets). Returned Nov 25, 2026.

---

"I'll review 1.2.6 the way the brief asks: pull the real files out of the attachments, rebuild the tree, and reproduce the findings rather than assert them.
    
    Setting up the workspace and a handoff file
    
    Reading the auth/lockout/U9 block first (lines 2887–3340).
    
    Reproduced. Repro 2 — does the U9 install_born_empty marker travel inside a copied database?
    
    Linear and unbounded (~120 bytes per sprayed name, no eviction). Now the code-read items for the §3 rulings.
    
    Reproduced. Checking the U7 pickup flow, since §3 item 2(v) asks for a 24-hour expiry that TRACK-126 doesn't cover.
    
    _totp_pickup counts a wrong key toward the lockout (janus.py:5620-5623) on an unauthenticated endpoint, the exact shape U1 was meant to close.
    
    U4 holds: a missing conf ranks lowest (janus.py:4767-4768), so it can't out-rank anything. Checking whether the seat attack files survive the R-F adaptations.
    
    My vote is NOT CONVERGED, on code grounds only. Three of the changes Round 8 asked for (U1, U6, U12) introduced problems that are themselves deployment-blocking, and two more (U9, U2) ship with defects I reproduced.
    
    The three blockers:
    • F1, the lockout fix (U1) is undone by the new pickup step (U7). The 2FA pickup endpoint needs no login, and it counts a wrong key toward the account lockout. A stranger can lock both supervisors with ten requests, which also takes /health red.
    • F2, a detective can bypass the new supervisor approval queue (U6). If a detective 'submits' an entry that already exists on the live hot list, the submission rewrites the live entry directly — no queue entry, no approval, and the stolen-vehicle entry becomes an expired parking entry.
    • F3, the torn-tail repair (U12) deletes good evidence from the outside copy of the audit log. If that copy has one damaged line in the middle (the kind of damage U12 was ordered to handle), the repair deletes the six entries after it, reports the repair as successful, and health stays green.
    
    Other findings, also run:
    • F4: The marker that decides whether a database 'arrived populated' (U9) is stored inside the database it judges, so copying the database to a new machine carries the verdict with it.
    • F5: Deleting the disagreeing checkpoint lines from the local file lifts a real rollback lockdown without a second key's acceptance.
    • F6: Partner agencies can read the audit log and line up a protected vehicle's hit with the camera and time of the hit.
    • F7: Each new username in a failed-login spray adds about 120 bytes of memory that is never freed.
    • F9: Most of the files restore sets aside, including the old write-ahead log that holds plate data, are never cleaned up.
    
    One suspicion didn't reproduce: queue IDs stayed stable through the nightly database cleanup, so I dropped that one.
    
    Rulings on §3:
    • Item 1 (U9): Reject the 'populated arrival' line. My alternative is that any unprovisioned install fences searches, hits, Tier 3 and shares, no matter how the database arrived — and a lab flag covers the tests.
    • Item 2: (i), (ii), (iii) and (iv) are FIX-NOW. (v) is already done by U7; the only leftover is clearing the pending secret on expiry. (vi) is a CANT-DO.
    • Item 3 (S10): Accept the retry, capped at one dropped sample per run and logged.
    • Item 4 (R-F): No assertion changed, so I ratify the practice, with one added condition: each adaptation must name the coverage it removes. Also worth checking what Boot('122') runs, because two of the adapted files use it.
    • Item 5 (U6 order): Ratify the order; the problem is the write behind it (F2).
    
    Forced change: fix F1, so that a wrong key at pickup never counts toward a lockout. Add a test where a stranger's spray at every account locks no one.
    
    Model: I can't see the chat interface. My system context says Claude Opus 5.5 (claude-opus-5-5), and no effort level is shown to me. This exact sentence is also in the review file.
    
    Coverage: I read sentinel.py, the docs, the build report and the diffs in full. I read about 2,100 of the 9,289 lines of janus.py, the parts around the U changes, and reached the rest only by search. I didn't get to Tier 3, the Compact, rotation or the evidence lifecycle.
    
    Citations use the real file line numbers (attachment line − 3). Files are in r9-claude-seat-b-repros.tar.gz: review-r9-claude-seat-b.md, HANDOFF.md, run-next.sh, the repro scripts and run log in work/"
    
    === FULL REVIEW DOCUMENT (review-r9-claude-seat-b.md), AS READ IN THE CHAT ===
    
    Title: "NOCTUA Council Round 9 — Claude seat B (Merlin slot) review of 1.2.6"
    Vote: NOT CONVERGED (code grounds; three blockers, each executed and each a small fix).
    Citations: All file:line references are to the real janus126/ files. The tree was rebuilt from the attachments by stripping the three-line reference header (attachment line − 3). Repros are in r9-claude-seat-b-repros.tar.gz (review-r9-claude-seat-b.md, HANDOFF.md, run-next.sh, the repro scripts and run log in work/). Each repro script is self-contained: it boots its own scratch Janus on loopback ports 23001–23071.
    
    1. Findings register (most severe first)
    
    F1 — BLOCKER (code). U1 regresses through U7's pickup endpoint: an unauthenticated stranger can lock both supervisors. EXECUTED.
    - Where: janus.py:5620-5625. _totp_pickup calls _auth_lock_note_failure(target) on a wrong key, before it checks whether any pickup is pending (5626-5632). The route is reached before need_auth (janus.py:4340-4344), so it needs no credentials at all. The U1 guard inside _auth_lock_note_failure (3090-3093) only exempts machine identities.
    - Repro: work/repro_u1_pickup_lockout.py. In the control, five wrong-key GETs at sgt.reyes lock nothing (U1 holds on need_auth). Then five POST /auth/2fa/pickup {"user": …} requests with a made-up key, sent at each supervisor, return 401 ×10. Afterwards both supervisors get 401 with their correct keys, two ACCOUNT_LOCKED entries are chained, and /health reports ok: false.
    - Impact: This is Round 8's deployment-blocking C8-01 again, now aimed at humans. Ten requests from any office [can lock the supervisors; /auth/unlock is supervisor-only], protection-order placement and release, the U6 hot-list queue, and Tier 3 approval [are affected].
    - Fix: On a wrong key, call _note_auth_fail only. Keep _auth_lock_note_failure solely on the post-key token failure (5655-5657), which is the case U1 intends to count. Discriminating case: a wrong-key pickup spray at every human account locks no one.
    
    F2 — BLOCKER (code). U6 queue bypass: a detective's "submission" rewrites a live, supervisor-approved entry, and the queue never sees it. EXECUTED.
    - Where: janus.py:5041-5050. The non-supervisor INSERT's ON CONFLICT(plate,state,list_source,case_no) DO UPDATE SET category, added_by, added_ts, expires_ts never sets or checks pending. When a live row (pending=0) exists on the same key, the "submission" edits that live row directly and returns the uniform 202.
    - Repro: work/repro_u6_conflict_bypass.py. The supervisor adds STL777 as stolen vehicle (201). The detective then posts the same key with category: parking, expires: 2020-01-01 and gets 202 submitted. The pending queue stays empty. The live row now reads ('parking', 'det.okafor', '2020-01-01T23:59:59Z'). The stolen car passes CAM-01: no ALERT, and HOTLIST_EXPIRED is chained "by ingest". The chain shows only HOTLIST_ADD_PENDING.
    - Impact: The supervisor gate U6 created is bypassable on any key that already has a live entry. A non-supervisor [can edit live entries; added_by is overwritten].
    - Fix: DO UPDATE … WHERE hotlist_members.pending=1 (the response stays a uniform 202). Discriminating case: a detective submission over a live key leaves [the live row unchanged].
    - Coverage note (bears on §3 item 4): The R-F adaptations moved every detective setup add to the supervisor, so no case anywhere still exercises a detective add over an existing key — which is exactly how F2 slipped through.
    
    F3 — BLOCKER (code). U12's torn-tail repair silently destroys valid witness-mirror entries, and health stays green. EXECUTED.
    - Where: sentinel.py:1828-1889 decides "torn" from the tail chunk. sentinel.py:1891-1922 (_sink_truncate_torn) then scans from the start of the file and truncates at the first unparseable line. After the cut, _deliver_locked (2049-2067) keeps using the pre-truncation file_seq and appends straight after the cut. _sink_record_ok (2246) then resets ok=1 in the same pass.
    - Repro: work/repro_u12_truncate_midfile.py. Start with a 10-entry mirror. Add one mid-file bad line (a 1.2.5-era welded partial write, the exact [kind U12 was ordered to handle]). The repair [deletes entries after the bad line; the live sink ends at seq 4, seqs 5-10 are lost, while] sink_status.ok == True, and diverged_seqs == []. The recorded message claims "truncated … back to seq 10". The gap only surfaces if someone runs the [divergence check]. The .diverged-* archive then holds [1, 2, 3, 11, 12]. Seqs 5–10 are in neither the live sink nor the archive.
    - Impact: Witness evidence is deleted, and the deletion is reported as a successful repair: "never silently skip [evidence]".
    - Fix: Have _sink_file_tail return the byte offset of the last valid line it found in the tail scan, and truncate only there. Re-derive file_seq after truncating. Treat any mid-file unparseable line as a named divergence, never as something to truncate away, and make ok contingent on the tail's seq continuity.
    
    F4 — HIGH (code; rides on §3 item 1). The U9 marker travels with the database it is supposed to judge. EXECUTED.
    - Where: install_born_empty is written into the DB's own meta table (janus.py:2854-2866) and read at 3234.
    - Repro: work/repro_u9_marker_travels.py. A born-empty 1.2.6 install ingests 5 reads unprovisioned; its DB file is then copied to a fresh host, where the copy behaves as a "populated arrival": ingests (201), serves a detective key-only (GET /hits 200), and serves /health to the supervisor key-only. Control: the same copy with the meta row deleted is locked (ingest 503, [searches refused]).
    - Also: A born-empty install keeps serving key-only humans and the full data surface with real plates indefinitely. Nothing ends the ceremony state except provisioning.
    
    F5 — MEDIUM (code). The U2 auto-clear lifts a genuine rollback fence when the disagreeing checkpoint lines are deleted from the local file; the two-key acceptance it replaces was the point of the fence. EXECUTED.
    - Where: janus.py:2183-2203 clears a recorded mismatch on any clean evaluation, whatever its prior_reason. The docstring at 2174-2178 says "or removed".
    - Repro: work/repro_u2_trim_clears_fence.py. Take checkpoints at 7 and 13 entries, roll the chain back to 7, and boot. Result: fenced (GET /hits 503, STARTUP_ANCHOR_MISMATCH). Delete the 13-entry line from <db>.checkpoints.jsonl and wait 5 s: GET /hits returns 200, ANCHOR_CLEARED is chained, and no acceptance entry exists.
    - Severity reasoning: The actor needs shell write access to the checkpoints file. The published checkpoints still exist offline, and ANCHOR_CLEARED records prior_reason, so detection survives. But in 1.2.5 a recorded disagreement was sticky until two keys accepted it; [now it can be cleared by deleting a line].
    - Fix: Auto-clear only checkpoints_malformed, checkpoints_unreadable, checkpoints_missing and anchor_check_error. A checkpoint_disagreement clears only through accepted IDs.
    
    F6 — MEDIUM (code; §3 item 2(iii)). The partner-readable chain joins a protected vehicle to a camera and time.
    - Where: ALERT {hit, cam, category} (janus.py:4626) and BLOCKED {hit, reason: "suppressed_queue"} (5159-5162) are both served to chain_auditor via /audit/range.
    - Repro: work/repro_blocked_hit_join.py. chain_auditor recovers (hit 1, CAM-02, 2026-11-25T23:12:24Z) for a plate under a protection order.
    
    F7 — MEDIUM (code; §3 item 2(ii)). _auth_fail_totals grows without bound from unauthenticated requests. EXECUTED.
    - Where: janus.py:2882, incremented at 2915-2916 before the global cap at 2922, and never pruned. _auth_lock_status (3124) sorts the entire dict on every /health.
    - Repro: work/repro_authfail_totals_growth.py. Spraying 8k, 16k and 24k distinct usernames raises RSS by +0.8, +1.7 and +3.2 MB: linear, about 120 bytes per name, no eviction.
    
    F8 — MEDIUM (code, read). Pending hot-list submissions without an expiry never age out.
    - Where: Pending rows are active=1 (janus.py:5044). Retention purges only active=0 (scripts/retention.py:225-229). hotlist_sync deactivates only rows that carry an expiry (scripts/hotlist_sync.py:86-90). registry_breaches checks only active=0 (sentinel.py:958-966).
    - Impact: An undecided submission, including a protected plate typed by a detective, is a plate-text store with [no expiry].
    - Nit: Approval reactivates an already-expired pending row (janus.py:5099-5102).
    
    F9 — MEDIUM (pre-existing; the U13 snapshot copies join it). Most pre-restore files are invisible to the retention sweep, so they are never pruned. EXECUTED.
    - Where: The registry pattern <db>.pre-restore-* (sentinel.py:486-488) is used by scripts/retention.py:326-339 and sentinel.py:1092-1104. It does not match <db>-wal.pre-restore-* or <db>-shm.pre-restore-* (scripts/restore.py:418-420; the outgoing WAL holds plate pages), nor U13's key copies <db>.audit_key.pre-restore-* (restore.py:477-479).
    - Repro: work/repro_preresrore_glob_gap.py. Four of five 60-day-old files are missed. Only restore.py's own substring prune (563-586) ever removes them, and only at the next restore.
    
    F10 — LOW-MEDIUM (code, read). U13's R-A closure fails open.
    - Where: scripts/restore.py:427-443. Any exception while reading the outgoing marker yields outgoing_provisioned = False. That is the same silent shape as TRACK-126's defect 2.
    - Fix: Fail closed: refuse, or record outgoing_provisioned: "unknown" and let Janus treat unknown as provisioned.
    
    F11 — LOW (code, read). The lockout counts fail-closed store states.
    - Where: _lockout_counts counts store_unavailable and must_reenroll (janus.py:3206-3208). A corrupt TOTP store, or the post-restore must_reenroll state, turns normal login attempts into locks for every human. That adds a 15-minute tail and red health [after restore].
    
    F12 — NITS
    - sentinel.py:1972-1977: the archive name has one-second resolution, so a second rotation within the same second would os.replace over the earlier evidence file.
    - sentinel.py:2060-2062: the torn-truncation message reports the pre-truncation seq (seen in F3).
    Not reproduced (disclosed): I suspected that U6 queue ids, which are rowid on a composite-PK table, are unstable across the nightly VACUUM. work/repro_u6_rowid_vacuum.py showed SQLite preserving them on this build, so I dropped it. U4 boundary probes (work/repro_u4_conf_probe.py) hold: NaN, Infinity, true, strings and values above 1 all get 400. Omitted or null conf is accepted but ranks lowest (janus.py:4767-4768), so it cannot out-rank anything.
    
    2. Rulings on §3
    1. U9 interpretation — REJECT populated-arrival as the line (F4).
    - Why: The marker lives inside the database it judges, so it travels with copies. It also never expires, so [a born-empty install serves data indefinitely].
    - The line I would draw: Unprovisioned means the ceremony state everywhere, regardless of birth. The ceremony state is the §3 [fenced state].
    - Open: ingest, safety writes, provisioning, auth administration, health.
    - Refused: searches, Tier 3, shares, reports, hit review.
    - Lab and fixtures: Bench and fixture installs run under an explicit NOCTUA_LAB=1. It is chained at every boot, named red at /health, and refused at boot on a provisioned install (the U5 pattern). DEMO_MODE already covers the demo.
    - What it breaks: Every fixture that reads data key-only while unprovisioned needs the lab flag. That is one environment variable in the shared Boot / Instance helpers, plus demo/seed_demo.py if it reads data outside DEMO_MODE. The install_born_empty marker and the legacy-chain probe (janus.py:1120-1135, which fails open on any non-v2 first payload) can then be retired.
    
    2. Queued smalls
    - (i) Move /holds/release out of the fence safety set — FIX-NOW. It is in ANCHOR_FENCE_SAFETY_POST (janus.py:2144-2146). Releasing a hold makes evidence purgeable, which is destructive during a suspected rollback, and [should not be a safety write].
    - (ii) Bound _auth_fail_totals — FIX-NOW (F7, executed). Use a bounded top-K or LRU with an evicted-count total.
    - (iii) Keyed hit references in BLOCKED entries — FIX-NOW (F6, executed). Use href: = HMAC(audit key, hit id) in BLOCKED payloads. Internal auditors can still join; partners cannot.
    - (iv) Fence the data surface during the ceremony state — FIX-NOW, as the mechanism for item 1 above.
    - (v) 24-hour expiry on pending secret pickups — implemented by U7. I verified the token age check (janus.py:5647-5654) and the reenroll request window (5529-5541). Residual hygiene, FIX-NOW: on expiry, clear the pending secret and chain an expiry entry. Today the [expired secret remains / is not cleared].
    - (vi) Enroll-2fa shell-operator honesty gap — CANT-DO. Accept it as a CANT-DO.md entry, worded with the same plainness as the openssl PATH entry. Whoever holds [shell / the operator] [can bypass it].
    
    3. S10 null-tolerance — ACCEPT as a test-only fix, with conditions.
    - Allow exactly one retry per dropped sample, and log every retry in the case output.
    - Fail the case if more than one sample drops, or if any drop occurs in a standalone run.
    - The property is freshness, which held in every returned sample. Availability of /health under saturation should become its own named load-envelope measurement rather than being absorbed here.
    
    4. R-F diff review — the adaptations preserve their assertions; the practice is ratified with one added condition.
    - What I checked: Every hunk in 08-rf-diffs is an actor swap (DET→SUP on setup adds), the 1.2.5 escrow re-pointing (attack2, f11), or removal of the header line. No assertion changed.
    - Added condition: Each adaptation must also name the coverage it removes, and the build must add a replacement case for the displaced actor's behavior. Moving every detective add to the supervisor removed all coverage of a detective add over an existing key, which is exactly where F2 lives.
    - For the orchestrator to verify: f2d_native_orders.py and f4_preauth_race.py boot "122". If that label runs janus122 code, the adaptation is not a commissioned custody change (1.2.2 has no pending state). It is harmless but outside the stated rule, and it is inconsistent with leaving f2/f9 unadapted.
    
    5. U6 validation order — RATIFY the order; OBJECT to the write it guards (F2).
    - Leak analysis: For non-supervisors, every pre-202 answer depends on the plate only through steps that do not branch on suppression: role, case gate, plate present, registry, category, expiry. Every class gets the same 202 body. The supervisor-only refusal before category/expiry leaks nothing to anyone not already entitled to the reason.
    - Residuals (stated, not blocking):
      - A suppressed submission writes one extra chain entry (SUPPRESSION_CONFLICT). That entry is partner-visible with a keyed plate_ref, and the extra insert is a timing difference I did not measure.
      - A submitter can infer protection later, when an approval never appears in GET /hotlist. That oracle depends on the supervisor acting and is inherent to a queue.
    
    3. Convergence scoring
    - Criterion 1. No surviving deployment-blocking or critical code finding — FAIL — F1 (unauthenticated supervisor off-switch, the C8-01 class), F2 (a non-supervisor disables live listings), F3 (silent witness-evidence loss with green health). All three are code, all executed.
    - Criterion 2. Every forced change implemented or answered — PARTIAL — U1, U6, U9, U12 and U2 shipped but each carries an executed defect (F1, F2, F4, F3, F5). U3/U4/U5/U7 [held / shipped cleanly — per the page view, this cell continues beyond the visible text].
    - Criterion 3. Remainder is CANT-DO or legal — NOT YET — The open items above are code. The ACIC follow-up and city-attorney answers are legal and are not part of my vote.
    - Criterion 4. Orchestrator re-tests pass — PASS — Per VESPER-VERIFICATION-126. The battery does not exercise F1–F7.
    Overall: NOT CONVERGED — on code grounds only. Each blocker is a fix of a few lines with a discriminating case that already exists in work/.
    
    4. Single forced change
    F1: In _totp_pickup (janus.py:5620-5625), a wrong key must not feed the lockout. Pair it with a discriminating case: a stranger's wrong-key [spray at every account locks no one]. This is the most severe finding (an unauthenticated off-switch for the supervisor role). F2 and F3 are [next in severity].
    
    5. Model and effort
    I cannot see the chat interface. My system context identifies the model as Claude Opus 5.5 (claude-opus-5-5). No effort level is shown to me.
    [Note from the browser agent: the interface itself, as I observed it, shows "Opus 5.5 Medium" — model Opus 5.5, effort Medium.]
    
    6. Coverage
    - Read in full: the brief, sentinel.py, the docs pack, TRACK-126 and VESPER-VERIFICATION-126, and the R-F diffs.
    - janus.py, sampled (about 2,100 of 9,289 lines): auth, lockout and U9 (2880-3340); boot marker (1100-1137, 2840-2878); anchor and U14 (2092-2415); dispatcher, need_auth and the sink ceremony (4194-4573); hot-list matching and U6 (4584-4632, 4933-5122); verify head (5118-5170); ingest supersede and U4 (4700-4830); reenroll and pickup (5473-5762); GET /hotlist* and /audit* (8425-8605). Everything else only via grep.
    - Scripts: restore.py U13 block (405-500, 560-592), retention.py purge and prune paths, hotlist_sync.py sweep. Not read: backup.py, compact.py, rotation.py, provision.py (beyond doc references), sentinel_audit.py, alert_check.py, frigate_bridge.py, checkpoint.py (executed, not read).
    - Tests: harness headers only. The seat attack files themselves were not in the pack (only their diffs).
    - Not touched: Tier 3, Compact, rotation, evidence lifecycle. Per §4 these come after the U surfaces, and I did not [reach them].
    
    Deliverables in the chat: the full review document "Review r9 claude seat b" (review-r9-claude-seat-b.md) and "R9 claude seat b repros.tar.gz" (containing review-r9-claude-seat-b.md, HANDOFF.md, run-next.sh, and the repro scripts and run log in work/). Attempts to download those files from the chat failed in this browser because the download buttons were reported as obscured by the side panel; the files remain available in the chat at the URL above.
    
    Fidelity note: the chat reply above is reproduced verbatim from the page's text view. The document section reproduces the document as read across the page's views; a few very long sentences were elided by the browser's accessibility view (shown in brackets above where a clause was cut off), so for grep-verification use the document file in the chat itself, not this report's transcription.