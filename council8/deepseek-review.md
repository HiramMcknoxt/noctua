# Round 8 — DeepSeek seat review (as returned Nov 25, 2026, ~11:44 AM CST)

Chat: https://chat.deepseek.com/a/chat/s/c331767b-9e59-4beb-aca1-c845cde68860
Model/effort: the interface shows no model name (accurate for this seat); DeepThink ON.
Coverage: **the platform truncated the attachments — "Length limit reached. DeepSeek can only read the first 8%."** The seat could read part-01 (brief + start of janus.py) and part-02 (janus.py through _recovery_hash) only. The seat declined to fabricate the rest — recorded as an honest non-certification, NOT a vote on the build. A follow-up delivery (sentinel.py + TRACK-125-REPORT as two small files, then further chunks) was dispatched to the same chat.

Orchestrator note on its one flagged question: anchor_fenced() calls _meta_set/chain.append outside DBLOCK — **checked in code: sentinel.Chain holds its own threading.RLock (sentinel.py:1570) and append() runs under it (sentinel.py:2164), so a single Chain.append is internally serialized regardless of DBLOCK. Not a defect.** The seat itself labeled it "a question, not a finding."

---

I need to be direct with you about a limitation before I do anything else: the attachments you describe are not fully present in what I can read.

What I can actually read in this session:

• part-01.txt: the full Round 8 brief (01-brief), plus the beginning of janus.py (through roughly the ANCHOR_FENCE_EXEMPT_POST set in the T3 section).
• part-02.txt: a continuation of janus.py (anchor fence sets, anchor_fenced, witness_state, _bad_checkpoints, _anchor_evaluate, _startup_anchor_check, _consume_restore_marker, _imperator_guard, boot sequence calls, and the start of the two-factor section through _recovery_hash).

What I cannot read, because it was not provided in this chat:

• sentinel.py
• the operational scripts (retention.py, restore.py, backup.py, checkpoint.py, compact.py, sentinel_audit.py, provision.py, frigate_bridge.py, etc.)
• the design docs and the Security Round 1 synthesis (security-round/SYNTHESIS.md)
• the test suites (the T battery, round-4/5/6 batteries, Q/R/S batteries, load envelope)
• TRACK-125-REPORT.md — the builder's dispositions, which the brief repeatedly cites for the named residuals R-A through R-F
• the remainder of janus.py after _recovery_hash (auth dispatch, the 2FA verification path, the fence dispatch logic, handler code, need_auth, throttling/lockout, /health, /hotlist, /verify, ingest, suppression endpoints, /audit/range, etc.)

So I cannot honestly produce the deliverables the brief demands. The rules of evidence are explicit: "Executed reproduction or file:line citation — nothing else counts." I have not executed anything (no test harness is attached and I have no shell here), and the file coverage I have is limited to the first portion of janus.py and none of the other components the residuals and judgment calls turn on. I could produce a plausible-looking review, but it would be invented. I will not do that.

What I will not do: pretend to have reviewed code I cannot see, invent file:line citations, or score the four convergence criteria as if I had the evidence to do so.

What I can offer, within evidence limits:

1. On the parts I can read, I can give genuine observations — but note the brief's own rule that a finding must be a code defect against the current build, and the current build is 1.2.5 as a whole, not the fragments I have. Two things I can say from what I can actually see:
◦ T3 fence scope (janus.py, the ANCHOR_FENCE_EXEMPT_POST / _SAFETY_POST / _EXEMPT_GET sets): the fence exempts "/auth/2fa/reenroll", "/auth/2fa/pickup", "/auth/unlock", "/audit/anchor-accept", "/heartbeat" for POST, and "/reads", "/suppressions", "/holds" (+ releases) as safety writes. This is consistent with judgment call (b)'s description. I cannot verify the fence dispatch itself, because that code is not in my readable set.
◦ anchor_fenced() (part-02): it treats an exception from _anchor_evaluate() as mismatch=True (fail closed) and records/chains a mismatch. That is the correct direction per T3/T6. But it calls _meta_set and chain.append from inside a function that anchor_mismatch()-style callers may invoke outside DBLOCK — the brief's own R4 history is precisely about chain appends outside DBLOCK. I cannot confirm whether anchor_fenced() is only called under DBLOCK, so I flag it as a question, not a finding.
These are observations, not findings, and I will not dress them up as more.
2. The one thing I can rule on with the brief itself as evidence: the brief's verification record states the T battery is 20/20 discriminating and the orchestrator's cold re-run is green. Under the brief's own evidence rule, that is a claim in the brief, not executed reproduction by me, and I have not seen the T battery source — so I will not certify it as my own finding.

Verdict I can honestly give: NOT CONVERGED — on evidentiary grounds, not on a proven defect.
The brief requires me to score criteria 1–3 against the current build with executed reproduction or file:line evidence. I do not have that evidence, and I cannot manufacture it. I therefore cannot certify; the seat is unequipped as delivered.
That is not a finding against 1.2.5 — it is a statement about the reference set handed to this seat.

My single forced change (as the price of a CONVERGED vote from me): deliver the complete reference set — full janus.py, sentinel.py, all operational scripts, the Security Round 1 SYNTHESIS.md, TRACK-125-REPORT.md, and the T/Q/R/S battery sources — in a form this seat can actually read, and re-run the seat. I will not move to CONVERGED on a partial read.

Rulings on R-A…R-F and judgment calls (a)–(f): I am declining to rule, not because I have no opinion, but because each one turns on code or reports I do not have:
• R-A (restore indistinguishability) and R-B (/hotlist residue) depend on restore.py, backup.py, and the /hotlist handler — not in my readable set.
• R-C, R-D depend on provision.py, the auth/pickup handlers, and need_auth — not readable.
• R-E depends on the load-envelope test and sentinel.py sink code — not readable.
• R-F depends on TRACK-125-REPORT.md §3.8/§4 and the adapted fixtures — not provided.
• (a)–(f) each rest on handler/boot code beyond what I can see (e.g., (b) needs the dispatch fence; (d) needs the retention/restore implementation in backup.py; (e) needs the sink_status() implementation in sentinel.py; (f) needs the response path).
I could give you reasoning-from-the-brief positions on each, clearly labeled as not evidence-based, if that is useful — but the brief says such answers earn nothing, and I would rather tell you the limit than fill it with speculation.

Model/effort reporting (per the seat protocol): the interface in this chat shows no model name; I am therefore writing, verbatim as instructed: "the interface shows no model name."
I also cannot verify effort level from the interface, so I report no effort rather than guess.

If you can re-deliver the full attachment set (or the specific files above), I will do the full review, with findings register, rulings, judgment calls, and a scored verdict. Until then, I am not certifying anything.

---

## Follow-up delivery 1 (Nov 25, 2026, ~11:52 AM CST) — sentinel.py + TRACK-125-REPORT

The seat read both files in full. Full response is in the chat (URL above); operative results:

- **Chain.append question ANSWERED by the seat (converges with Vesper's own check)**: append is self-serializing in-process via Chain's RLock; cross-process serialization is DBLOCK's job by documented design. Residual question it poses: anchor_fenced() also calls _meta_set, whose unconditional db.commit() could commit a caller's open transaction early IF anchor_fenced() is ever invoked mid-transaction — needs the janus.py dispatch code (delivery 2). Vesper's note: the known call sites (POST dispatch janus.py:3986, GET dispatch :7757, health :8341, :7623) sit at dispatch top, before handlers open transactions; the cold seat's probes may settle it by execution.
- **New catch, VERIFIED by Vesper**: sentinel.py line 5's module docstring still reads "NOCTUA 1.2.4" — the 1.2.5 honesty sweep missed it (REGISTRY_VERSION was bumped). Cosmetic; on the fix list.
- **F1 (Low)**: pubkey_fingerprint's docstring claims malformed input → None; an empty-body PEM yields sha256(b"") instead. verify_bytes still rejects such keys, so checkpoints still fail verification — documentation/behavior mismatch, not a hole. (Status: seat's code-read; plausible from the code path it quotes; confirm at synthesis.)
- **T5/T6/T9 claims hold** on reading; sink design confirmed in detail ("the strongest part" — obligation-as-row, per-entry ledger, below-tail verification against the sink's own seq:hash map, _book_conn autocommit bookkeeping).
- **R-A RATIFIED** as limitation (confirmed from _consume_restore_marker/_totp_provisioned code; structurally unfixable in code; mitigation is ceremony discipline).
- **R-E RATIFIED** with a caveat worth keeping: the operationally relevant number is the **burst rate**, not the 0.5 reads/s average — recommends a 9-camera burst test in the pilot operations plan, not a code change.
- **R-F RATIFIED** as documented (assertion-preserving re-pointing is correct maintenance; diffs themselves unseen by the seat).
- **R-B, R-C (enforcement leg), R-D deferred** pending the janus.py remainder + scripts. Verdict withheld by design until deliveries complete.

---

## Follow-up delivery 3 (Nov 25, 2026, ~12:14 PM CST) — janus.py tail (rotation handlers, dispatch, /health, __main__)

- Chunk map: part-04 covered everything after the rotation-void tail (do_GET/do_DELETE dispatch, _health in full, _run_tiered_search, /tier3/results live resolution, __main__ boot refusal) — but the sequential chunking SKIPPED the span between _recovery_hash and _post_hotlist (need_auth, auth, lockout accounting, run_search, _strict_id, chain_ok_cached, _totp_status, the /reads handler). A targeted extract of janus.py lines 2505-4471 was built as delivery 4.
- **Its delivery-1 open question ANSWERED (by the seat)**: anchor_fenced() is never invoked with a caller-held open transaction at the visible call sites (dispatch-top, defer-if-in-transaction flush helpers); the _meta_set commit hazard is not reachable there. It downgraded its own flag as over-cautious.
- **F17 (positive)**: /health's ok_all includes every degradation the T4 sweep names (sink unknown, checkpoints-only posture, demo mode, config guard, totp_bad, recovery_alerts). NOTE (Vesper): ok_all does NOT include locked_accounts — consistent with Claude C8-01's detection-lag point.
- **F18/F19 (positive)**: /audit/range validation strict; /health degraded block comprehensive.
- **R-C: PARTIALLY CONFIRMED** — the /health naming of unbound identities is real and correctly NOT an ok_all input; enforcement awaits delivery 4.

---

## Follow-up delivery 4 (Nov 25, 2026, ~12:26 PM CST) — targeted extract (janus.py 2505-4471) + FINAL VERDICT

The seat read the missing span (auth, lockout accounting, run_search, need_auth, /reads) and ruled:

- **R-C FULLY CONFIRMED / RATIFIED**: binding is enforced in the handlers, not need_auth — _post_reads refuses an unbound camera with 403 + chained INGEST_REJECTED; /heartbeat likewise with HEARTBEAT_REJECTED. Nuance worth naming: the check is field-presence-conditional — `"cameras": []` counts as UNBOUND, not bound-to-nothing (the safer default; recorded in the synthesis).
- **Lockout accounting traced accurately** — every real-account 401 increments the counter, incl. wrong key. The seat registers this as **F36: classic lockout-DoS, rated Moderate, classified as an operational residual / runbook gap, NOT a code defect** — its remedy: an out-of-band provision.py unlock path. (Orchestrator: that remedy is Claude's forced-change break-glass, already in U1; and U1's counting change removes the unauthenticated lock entirely, which is stronger than the seat's runbook answer. The seat's classification is the round's preserved dissent on criterion 1 — see the synthesis addendum.)
- run_search / T9 SQL leg verified at source (noctua_order_covers registered SQL function delegating to the one predicate).
- **FINAL VERDICT: CONVERGED**, forced change "None", expressly contingent on TRACK-125's dispositions for the operational scripts (unread by this seat) being accurate.
