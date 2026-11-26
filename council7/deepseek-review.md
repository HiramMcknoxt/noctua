# NOCTUA Round 7 — DeepSeek-chat seat review
Retrieved Nov 24, 2026, 11:25 PM CST via browser seat (chat.deepseek.com, DeepThink ON, code in 10 .txt parts).
IDENTITY CAVEAT: the model in that chat self-identified as "Claude (Anthropic)", not DeepSeek, and asked to be treated as corroboration rather than the DeepSeek seat's vote. Recorded as a corroborating review; its code citations were verified by the orchestrator where they converge (F2) or are new (F1).
Verdict: NOT CONVERGED (criteria 1 FAIL, 2 PASS-with-caveat, 3 FAIL, 4 PASS-mechanically).

Interface identity
    
    Model/interface: Claude (Anthropic). This chat interface exposes no model/mode selector, so there is no "DeepSeek native — Thinking High" badge for me to report; I am not DeepSeek. I'll do the review as the seat, but the council should treat it as a Claude-model review — if the seat's rule requires the literal DeepSeek model, use this as corroboration, not as the seat's vote.
    
    What I did
    
    I read all ten parts: janus.py, sentinel.py, the eleven scripts, the four test drivers, and the docs (Round 6 synthesis, handoff, TRACK report, 2FA scope). I re-derived the orchestrator's claims rather than trusting the summary, and I attacked the five areas named in the brief. The build is genuinely strong: the battery is extensive, the R1–R16 items are present in code and in the written record, and most of the Round 6 headlines are closed. But two code-critical defects survive in the 1.2.3 repair pass itself — the pass R1/R2 were commissioned to fix — and the battery is blind to both because its R2/hotlist cases only exercise the shapes that work.
    
    I am not failing the build for 2FA; it is out of scope.
    
    Surviving findings
    
    F1 (code-critical, new): _hotlist_canon nulls unknown-state hot-list memberships, silently disabling alerts after any restart
    
    janus.py, _migrate_123 → _hotlist_canon:
    
    cstate = (row[2] or "").upper()
    ...
    db.execute("UPDATE hotlist_members SET plate=?, state=?, active=?, "
               "expires_ts=? WHERE rowid=?",
               (canon, cstate or None, active, expires, keep[0]))
    
    A membership created through the API with no state is stored as '' (_post_hotlist: state = (d.get("state") or "").upper()). _hotlist_canon runs on every unlocked boot and rewrites state to cstate or None — i.e. '' → NULL.
    
    The match predicate in _hits_for_read is:
    
    WHERE plate=? AND active=1 AND (state=? OR state='' OR ?='')
    
    In SQLite, NULL = '' is NULL, not true. So after the first boot following a no-state listing, that membership matches only reads whose state is also unknown. A read with state='AR' no longer alerts. The docs and the query both treat '' as the wildcard; the migration converts it to a value the query does not recognize.
    
    This is a 1.2.3 regression: 1.2.2 has no _hotlist_canon, so the entry survives restarts. Repro:
    
    Fresh 1.2.3; POST /hotlist {"plate":"HOT111","category":"stolen vehicle","case":"2027-1014"} (no state) → 201.
    
    POST /reads {"plate":"HOT111","state":"AR","cam":"CAM-01"} → ALERT (works; '' is wildcard).
    
    Restart Janus.
    
    Same read → "stored", no alert. hotlist_members.state is now NULL.
    
    No test in the corpus adds a no-state hot-list entry: suite_a, suite_a2, suite_retention, q01, q04, inv1, r2_migration all pass state="AR". The battery's green is not evidence for this property.
    
    Fix (one line): set state=cstate (preserve ''), or change the match to COALESCE(state,'')=''. Add the discriminating case above (fails on 1.2.3, passes on 1.2.2).
    
    F2 (code-critical, new): the R2 recovery branch re-keys the plate text but not plate_ref; recovered plate-less orders are half-active and their hits vanish from both queues on the first boot
    
    janus.py, _migrate_123 → _supp_repair:
    
    if plate and normalize_plate(plate):
        ...
        db.execute("UPDATE suppressions SET plate=?, state=?, plate_ref=? WHERE id=?",
                   (canon, ..., new_ref, sid))
    elif active:
        match = ...
        if match:
            db.execute("UPDATE suppressions SET plate=? WHERE id=?", (match, sid))
            recovered += 1
    
    The plate-text branch re-keys plate_ref to the current formula. The recovery branch sets plate only. The order is counted active, plate is populated, and migration_status reports complete — but its plate_ref is still the old (e.g. 1.1 legacy) value.
    
    Now the two suppression mechanisms disagree:
    
    Search//hits SQL uses plate text: _SUPPRESSED_HIT_SQL (s.plate = hits.read_plate OR s.plate = hits.entry_plate). The recovered order matches, so /hits excludes the hit.
    
    hit_suppressed_now() uses plate_ref against active_suppression_refs() (the stored, stale ref). It returns false, so /suppressed-hits excludes the hit; _post_verify and /evidence/export treat it as unsuppressed.
    
    Result on the first boot after upgrade: a hit on a recovered protected plate is invisible in /hits and in the supervisor queue, and a detective can verify and export it (/verify 200, export 201) — the exact class of protection failure R1/R2 exist to kill. On the second boot, _supp_repair sees the now-populated plate and re-keys the ref; the order becomes consistent. But the first-boot window is however long the service runs between restarts, and nothing in /health names it (unrepaired counts only active rows with null/empty plate, and the plate is set). It is silent.
    
    Repro (needs a 1.0/1.1 DB with a plate-less active order whose plate_ref is legacy_plate_ref(key,"VIC309","AR")):
    
    Boot 1.2.3 on that DB. _supp_repair recovers plate="VIC309", leaves plate_ref legacy.
    
    Ingest {"plate":"VIC309","state":"AR"} → ALERT (hit created; is_suppressed false, so suppressed=0).
    
    GET /hits (detective) → hit absent. GET /suppressed-hits (supervisor) → hit absent.
    
    POST /verify (detective, hit id) → 200 VERIFIED.
    
    Restart → the ref re-keys and the hit appears in the queue / verify is 403.
    
    The R battery's r2_migration uses a suppression with plate text (PRT555), so it exercises only the branch that works. q01 likewise. The recovery branch is untested.
    
    Fix (one line in the branch): also set plate_ref=? to plate_ref(match). Add the first-boot case above (no second boot).
    
    F3 (medium, defense-in-depth): _imperator_guard is boot-only; a live reload can serve imperator from a non-demo users file until restart
    
    The guard is called once, after the first _reload_config():
    
    _reload_config()
    _imperator_guard()
    
    _apply_config("users", …) on a later reload sets USERS_DEMO and USERS from the new file with no guard. Path: boot with the demo-flagged file (imperator allowed), edit users.json to a bare list that keeps imperator (removing demo:true), trigger a reload (any request). USERS_DEMO=False, imperator is active and served; the next boot refuses (exit 3). The config file is the trust root, so this is not an external attack — but the guard's stated purpose is that the account is impossible outside demo, and the reload path is normal operation. I classify this as a hardening gap, not the price of the vote. Recommend: re-check in _apply_config and reject the reload (keep last good) when imperator appears in a non-demo file.
    
    Residuals / limits (not blocking, worth recording)
    
    _anchor_accept will clear a mismatch whose reason is checkpoints_unreadable/checkpoints_missing (it records no bad checkpoint ids and deletes the meta), giving a green /health until the next boot re-locks. The two-key flow should refuse reasons other than checkpoint_disagreement.
    
    Legacy free-text expiries (12/31/2027) are deactivated at migration (counted in MIGRATION, not per row). Defensible, but an operator can miss it; document it.
    
    frigate_bridge allows type:"new" through (etype not in ("end","update","new")), contradicting its docstring ("only end and update"). A new with a preliminary plate is stored at rank 1 and superseded later; low impact, but the doc/code disagree.
    
    retention.py deletes bundle directories before the transaction commits; a commit failure loses the file while the row says otherwise. Filesystem/DB atomicity was not promised, but note it.
    
    Cross-process sink twin: R5b's duplicate prevention relies on the in-memory _streamed set; a crash between an immediate _stream and flush_deferred can re-stream the twin in a new process. Low reachability in Janus (handlers defer), documented as a limit.
    
    _migrate_123 runs full scans of reads, hits, hotlist_members, suppressions, holds on every boot. Correct, but a boot-time cost on large DBs; the load envelope measures appends, not boot.
    
    _receipts dedupe keeps MIN(id); a legacy unverified duplicate could displace a verified one. The receipt endpoint only writes verified rows, so this is a legacy-only edge.
    
    What holds (checked, not merely counted)
    
    R16 (my Round 6 finding): works. sentinel.read_deletable keeps a read while any hit referencing it (hits.read_id) is not deletable, and the 150-day cap applies to both. The r16_reads case (hold fresh, hit+read aged 20d, retention, re-export non-empty) is the right shape. Caveat: a legacy hit whose read_id backfill failed protects nothing — _hits_backfill runs every boot, so this is a narrow residual, not the R16 defect.
    
    R1 native and migrated-with-plate-text: two orders coexist; release lifts one; verify remains 403 while the other is live. The R1 tests are sound.
    
    R5b twin (in-process) and R5a burst: the sink ledger + read-only presence check + _book_conn separate connection hold; zero phantoms/duplicates/missing in the tested shape.
    
    R6 ceremony: commit freezes at first reveal, commitments are never overwritten, partner authorship by identity or Ed25519, unsigned supervisor transport 403, cancel two-key, void clears contributions. The tests exercise the real paths.
    
    R7 compact anchoring: checkpoint mark separate from live mark; two runs pass; future-dated checkpoint fails freshness.
    
    R8 one verifier: compact.recompute and sentinel_audit --url both fail a relabeled v1 chain through sentinel.verify_chain_rows.
    
    R10 restore trust root: attacker self-vouching set refused on a bare host; pinned legitimate set installs.
    
    R13 attribution: 60 varying-agency share requests add ≤3 entries, attributed to the caller.
    
    R3 pin ceremony: works on the tree's own DB and on a real 1.1 DB; the column is frag; candidates go through key_ref_candidates; the upgraded DB boots after the ceremony.
    
    Criterion verdicts
    
    No surviving deployment-blocking or code-critical finding — FAIL. F1 and F2 are code-critical: F1 silently disables a no-state hot-list listing on the next restart (a safety miss, and a 1.2.3 regression); F2 leaves a recovered protection order half-active, hiding its hits from both queues and allowing a detective to verify/export them on the first boot. Both are in the repair pass the round was commissioned to fix.
    
    Every R1–R16 implemented or answered in writing — PASS, with a caveat. All items are present in code and in TRACK-123-REPORT. R16 is checked and works. The caveat: R2's recovery sub-case is implemented but defective (F2), which is a criterion-1 failure, not a missing item.
    
    What remains is documented limits or legal questions, not code defects — FAIL. The two findings above are code defects, not limits; the residual list is limits, but it is not what decides this criterion.
    
    The orchestrator's re-tests pass — PASS mechanically, insufficient as convergence evidence. The battery is green (332/332, round-4/5/6, Q 35/35, R 20/20, envelope). But the acceptance standard is verified invariant satisfaction, not passing counts. The R2 case uses plate text; every hot-list case passes a state. A case that observes zero of the thing it tests fails the battery — and the two shapes above are observed by no case. The re-run passing is real; it does not cover F1/F2.
    
    Overall: NOT CONVERGED.
    
    The single forced change (the price of my vote)
    
    Make the 1.2.3 boot repair semantics-preserving. One change to _migrate_123, two edits:
    
    1. _hotlist_canon must preserve the API's unknown-state wildcard: store state=cstate ('' stays '') rather than cstate or None, or change _hits_for_read to match COALESCE(state,'')=''.
    
    2. _supp_repair's recovery branch must set plate_ref to the current formula (plate_ref(match)) when it sets plate=match.
    
    And two discriminating cases in the battery, both of which fail on 1.2.3 as shipped and pass on 1.2.2 (F1) or must be made to pass on the first boot (F2):
    
    - no-state hot-list entry → restart → ingest with state="AR" → expect ALERT (F1);
    - plate-less legacy order recovered → first boot → /verify by a detective is 403 and the hit is in /suppressed-hits (F2).
    
    The imperator reload guard (F3) and the anchor-accept reason check are recommended hardening; I do not make them the price, because the users/cases files are the trust root and the next boot refuses. The price is the repair pass.
    
    The build is close, and the battery is the best this project has had. But the round's own subject — protection orders and hot-list integrity across real migrations — still has two silent failure modes, and the acceptance suite is aimed just to the side of both.
