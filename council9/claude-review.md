# NOCTUA Council Round 9 — Claude seat review

Seat: Claude. Model/effort per the browser operator's interface observation: Opus 5.5, Medium (the seat's own text claims it cannot see the display and its HANDOFF says effort low — per seat protocol the interface observation governs). Chat: https://claude.ai/chat/1431d6a9-c6a7-4a0f-8d7a-8264200b9789. Executed review: rebuilt the tree from the attachments and ran reproductions. The text below is the seat's own CLAUDE-SEAT-R9.md artifact, verbatim. Its two repro scripts (claude-r9-repro.py, claude-r9-u12-sink.py) could not be downloaded from the chat (buttons obscured); the artifact describes each reproduction and its result. Returned Nov 25, 2026.

---

# NOCTUA Council Round 9 — Claude seat review of 1.2.6

**Vote: NOT CONVERGED.** Every blocker listed below is a **code** finding. None of them is a legal question.

**Model / effort.** I can't see the chat interface's display, so I can't copy it verbatim. The session's system information names the model as **Opus 5.5** (`claude-opus-5-5`). No effort level is shown to me.

**Method.** I rebuilt the tree from the attachments: janus.py, sentinel.py, scripts/, and tests/. Line numbers below are **real-file** numbers, meaning the attachment line minus 3. I ran every repro against that tree using the T-battery `Boot` harness (`tests/run_t125_cases.py`), plus one in-process `sentinel.Chain` unit. The repro scripts are attached as `claude-r9-repro.py` and `claude-r9-u12-sink.py`.

---

## 1. Findings register (most severe first)

### C9-01 — U1 is not closed: anyone can lock every human account through `/auth/2fa/pickup` — BLOCKER (code), EXECUTED
- **Where:** `janus.py:5620-5625`. In `_totp_pickup`, a **wrong-key** attempt calls `_auth_lock_note_failure(target)` directly, which bypasses `_lockout_counts` (`janus.py:3188`). The pickup endpoint also runs **before** `need_auth` (`janus.py:4340-4344`).
- **What `_auth_lock_note_failure` checks:** only the machine-account guard (`janus.py:3090-3093`). It does not check that the key verified.
- **Repro (`U1_pickup_lock`):** I sent 5 × `POST /auth/2fa/pickup` with key `wrong` for each of sgt.reyes, capt.voss and det.okafor. That is 15 unauthenticated requests.
  - All three accounts then got **401 with their correct keys**.
  - Three `ACCOUNT_LOCKED` entries were chained.
  - `POST /auth/unlock` by a supervisor returned 401, because every supervisor was locked.
  - /health went not-ok.
  - **Control:** the same spray against `GET /stats` (the path U1 fixed), followed by the correct key, returned **200**.
- **Impact:** This is the C8-01 shape on a second entry path. It works with no credentials, renews every 15 minutes, and leaves only the shell break-glass to recover.
- **Smaller issue on the same path:** the pre-auth answer `"account is locked"` (`janus.py:5614-5618`) tells an unauthenticated caller whether an account is locked.
- **Fix:**
  - Delete the call at `:5623`.
  - Move the key-verified predicate **inside** `_auth_lock_note_failure`, so the docstring's promise that no future caller can reintroduce the shape becomes true.
  - Make the locked answer a uniform 401.
  - Add a battery case that sprays **every** pre-auth route.

### C9-02 — U6 bypass: a detective's "submission" silently rewrites a live supervisor hot-list entry — BLOCKER (code), EXECUTED
- **Where:** `janus.py:5041-5050`. The non-supervisor INSERT shares the conflict key `(plate,state,list_source,case_no)` with live rows. Its `DO UPDATE` overwrites `category`, `added_by`, `added_ts` and `expires_ts`, and leaves `pending=0, active=1` untouched.
- **Repro (`U6_upsert`):**
  1. The supervisor adds STL900 with an expiry 30 days out. Response: 201.
  2. The detective posts the same key with `expires` two days ago. Response: **202 "submitted for supervisor approval"**.
  3. The row is now `det.okafor / 2026-11-23T23:59:59Z / active 1 / pending 0 / category "warrant"`.
  4. A read of STL900 produces **0 hits** and the entry deactivates (`HOTLIST_EXPIRED`).
  5. The chain records `HOTLIST_ADD_PENDING`, which is a false description of a live modification.
- **Second shape:** if the detective omits `expires`, the supervisor's 30-day entry becomes **permanent** (`expires_ts NULL`).
- **Impact:** A stolen-vehicle listing can be neutralized, or extended indefinitely, without supervisor approval, and the response and chain both claim the change is awaiting approval.
- **Fix:** On the non-supervisor path, a conflict with a `pending=0` row must be `DO NOTHING` (the answer stays the same uniform 202, so the existence of the live entry does not leak). Alternatively, keep pending submissions in their own table or key.
- **Test-coverage note:** the R-F adaptations moved every detective setup add to the supervisor. That removed exactly the coverage that would have caught this (see §3 item 4).

### C9-03 — U12 regression: torn-tail recovery deletes valid delivered entries from the witness mirror, with health green — BLOCKER (code), EXECUTED
- **Where:** `sentinel.py:1888-1919`. `_sink_truncate_torn` scans from the start of the file and truncates at the **first** unparseable line, not at the final partial line. `_deliver_locked` (`sentinel.py:2047-2060`) then carries on using the **pre-truncation** `file_seq`. It does not re-read the tail, so no divergence branch fires.
- **Repro (`claude-r9-u12-sink.py`):**
  - Starting mirror: seqs `[1,2,3,<weld>,6..10,<torn tail>]`. The mid-file weld is exactly the line 1.2.5's Q-F1 defect produced: an entry appended onto a torn fragment.
  - After the next append the mirror is `[1,2,3,11]`. Seqs 6-10 (valid, already delivered) are **gone**, and none of the removed bytes were archived.
  - `sink_status`: `ok=True`, `diverged_seqs=[]`, `last_error="…truncated the partial final line back to seq 10"`. That message is false.
  - Only `sink_divergence()`, which only the ceremony calls, sees `stranded_seqs [4..10]`.
- **Impact:** This contradicts both U12 ("never silently … skipped") and U3 ("archived, never deleted"). Every 1.2.5 install that ever had a torn tail carries a weld and will hit this.
- **Fix:**
  - Cut only the bytes after the last `\n`.
  - Archive the cut bytes to `<sink>.torn-<ts>`.
  - Re-read the tail after any truncation and route `file_seq < tail_seq` into the named-divergence branch.
  - Treat a mid-file unparseable line as a divergence.

### C9-04 — U9 marker is a property of the database, so it travels with every copy — IMPORTANT (code), EXECUTED
- **Where:** `janus.py:2854-2868` writes `install_born_empty` into the DB's own `meta`. `_unprovisioned_locked` (`janus.py:3227-3234`) trusts it.
- **Repro (`U9_marker`):**
  1. A 1.2.6 install born empty, never provisioned, ingests a read. The marker is in its DB.
  2. That populated DB is copied to a new directory (the "arrival" shape) and booted. Ingest returned **201**, detective key-only returned **200**, totp state was `provisioning`.
  3. **Control:** the same copy with only the marker row deleted gave ingest **503** and detective **401**.
- **Impact:** The guard therefore fires only for databases born under ≤1.2.5. The U9 case passes because its fixture is built by janus125 (`tests/run_u126_cases.py:731-760`). That is also why it discriminates.

### C9-05 — U2 lets a genuine rollback fence be cleared by deleting one line of a local file, with no second key — IMPORTANT (code), EXECUTED
- **Where:** `janus.py:2183-2203`. `_anchor_apply` clears **any** recorded mismatch on a clean evaluation, whatever the reason. The docstring at `:2169-2178` names "removed" checkpoints as a legitimate clear path.
- **Repro (`U2_clear`):**
  1. Two checkpoints are published, then the DB is rolled back to a snapshot taken between them.
  2. The data surface returns 503 with `checkpoint_disagreement`.
  3. The newest line is deleted from `<db>.checkpoints.jsonl`.
  4. Within 6 seconds `/hits` returns **200**, the meta flag is gone, `ANCHOR_CLEARED {prior_reason: checkpoint_disagreement}` is chained, and there are **0** acceptance entries.
- **Impact:** This reopens T3's rollback-and-continue path for anyone with host write access, which is the same access the rollback itself needs. It is mitigated only because the ANCHOR_CLEARED entry is chained and the Clerk holds the outside copy.
- **Fix:**
  - Auto-clear only the file-state reasons (`checkpoints_malformed`, `checkpoints_unreadable`, `anchor_check_error`).
  - Clear `checkpoint_disagreement` only through the two-key `_anchor_accept`.
  - Persist a high-water mark of published checkpoint entries, so a file that regresses below it fails closed.

### C9-06 — `_auth_fail_totals` grows without bound and is sorted in full on every /health — MEDIUM (code), EXECUTED (= queued item ii)
- **Where:** `janus.py:2882` and `:2915-2916`, sorted at `:3124`.
- **Repro (`U1_totals`):**
  - 20,000 distinct unauthenticated usernames took 14.9 s from one client.
  - RSS grew by **1,808 KB, about 93 bytes per name**, which is linear. That projects to roughly 0.9 GB at 10M names.
  - The chain stayed bounded (29 rows), so only the memory and the sort grow.

### C9-07 — The protected-hit join in partner-readable BLOCKED entries — MEDIUM (code), read (= queued item iii)
- **Where:** `janus.py:5160-5163` and `:6338` chain `{"hit": <raw id>, "reason": "suppressed_queue"}`. `ALERT` (`janus.py:4628`) chains the same raw `hit` together with `cam`.
- **Impact:** A `chain_auditor` can therefore learn "a protection-order vehicle passed camera X at time T".

### C9-08 — Pending pickup secret never expires; only the token does — LOW (code), read (= queued item v)
- **Where:** `janus.py:5649-5654` gates the token at 24h. The entry's `secret` and `pickup_pending=True` persist in the TOTP store indefinitely until a pickup succeeds (`:5716-5720`).

### C9-09 — Unbounded `stranded_seqs` in a chain payload and in /health — NIT (code), read
- **Where:** an "unreadable" sink strands every seq (`sentinel.py:2087-2089`). The ceremony chains the whole list in one entry (`janus.py:4549`), and `_sink_state` returns it in /health.
- **Impact:** At 600k entries that is a multi-MB chain entry.

### C9-10 — The sink ceremony is single-key and exempt from the fence; anchor acceptance is two-key — NIT/DESIGN, read
- **Where:** `janus.py:4520-4560` and `:2143`.
- **Impact:** During a rollback, one supervisor can turn the mirror's red light green. The diverged file is still archived, so this is recorded asymmetry rather than evidence loss. I name it so it can be ratified explicitly.

### C9-11 — Documentation — NIT
- `tests/attacks/round4/attack2.py.orig-124`'s header describes only the 1.2.5 escrow adaptation. Its diff also carries the 1.2.6 DET→SUP changes.
- The enroll-2fa shell-operator entry proposed in (vi) is **not** in `docs/CANT-DO.md` as attached.

---

## 2. Rulings on brief §3

**1. U9 interpretation — REJECT as shipped. RATIFY the principle.**
- The ceremony-versus-arrival distinction is legitimate, and the literal text is unworkable, as the builder argued.
- But the implemented line is not the line the builder describes. The marker is DB-resident, so every 1.2.6-born DB passes as "born empty" anywhere it is copied (C9-04, executed).
- **The line I would draw:**
  - While unprovisioned **and the DB holds any reads or hits**, fence the disclosure surface for key-only humans: searches, hits view, Tier 3, shares, reports and evidence export.
  - Ingest, safety writes, provisioning, auth administration and health continue.
  - Keep a host-bound marker (a sidecar file plus the first chain hash) only to exempt the empty first-run ceremony.
- **What it breaks:** fixtures that search on unprovisioned installs with data have to enroll first (the `_enroll` helper exists). Demo mode is unaffected. This is fixture churn, not lost product function.

**2. Queued smalls:**
- (i) Move `/holds/release` out of the fence safety set — **FIX-NOW**. Move `/suppressions/release` too (`janus.py:2144-2146`), because removing a protection is not a write that protects anyone. Both can wait for the fence to clear.
- (ii) Bound `_auth_fail_totals` — **FIX-NOW** (C9-06). Count per real account; aggregate unknown names into one counter.
- (iii) Keyed hit refs in BLOCKED entries — **FIX-NOW** (C9-07). Use an HMAC hit ref in BLOCKED entries, or at least in `suppressed_queue` ones.
- (iv) Fence the data surface during T1 — **FIX-NOW**, as the mechanism of my U9 line above. The fence keys on data being present, not on the DB marker.
- (v) 24-hour expiry on pending pickups — **FIX-NOW** (small). The token window exists; expire the pending entry and its secret too, and chain `PICKUP_EXPIRED` (C9-08).
- (vi) enroll-2fa shell-operator gap — **CANT-DO**, accepted. The entry must actually be written into `docs/CANT-DO.md`; it is absent from the attached copy.

**3. S10 null-tolerance — ACCEPT as a test-only fix**, on three conditions:
- Retry exactly once.
- The retried sample must satisfy the same freshness property.
- The retry is logged in the case's output, so that a run full of retries is visible.

The property under test is freshness, not health availability under six saturating threads on 1.5 CPUs. If the Council wants availability under load, it should be its own case.

**4. R-F diffs — the adaptations preserve their assertions, and I RATIFY the practice with one addition.**
- Every 1.2.6 hunk is DET→SUP on a setup add, and every `assert s == 201` remains correct for the supervisor's direct add. The 1.2.5 hunks (attack2 escrow, f11 existence-guard) are likewise assertion-preserving.
- **Addition:** when an adaptation changes the **actor**, a companion case must exercise the original actor's path under the new semantics. The DET→SUP sweep removed all detective-path coverage, and C9-02 lives exactly there.
- Also fix the attack2 `.orig-124` header (C9-11).

**5. U6 validation order — RATIFY** (registry → supervisor suppression refusal → category/expiry → role split).
- **Leak analysis:** On the non-supervisor path, every check before the 202 is plate-independent (`case_gate`, plate present, registry, category, expiry; `janus.py:4941-4996`), so the response is uniform.
- The supervisor's informative 403 is to a party allowed the reason.
- Residual signals: the chain's `SUPPRESSION_CONFLICT` record is by design. The delayed oracle (protected submissions never become listed) is indistinguishable from a rejection.
- The real defect in this handler is not the order but the upsert (C9-02).

---

## 3. Convergence criteria

| # | Criterion | Score |
|---|---|---|
| 1 | No surviving deployment-blocking or critical code finding | **FAIL.** C9-01 (unauthenticated lockout of every human), C9-02 (approval-gate bypass on the hot list), C9-03 (silent deletion from the witness mirror). All code. |
| 2 | Every forced change implemented or answered | **FAIL.** U1 is closed on one path only. U6 is bypassable. U12's "never skipped" claim is false. U9's mechanism does not reach its stated case. U2 over-clears. |
| 3 | What remains is CANT-DO or legal | **FAIL** for the items above. Item (vi) is properly CANT-DO once written. The ACIC/city-attorney tracks are legal and I do not count them. |
| 4 | Orchestrator's re-tests pass | **PASS** as reported. I did not re-run the full battery (no janus125 baseline in my pack). My repros show the battery does not cover the paths above. |

**Overall: NOT CONVERGED.** These are code grounds only.

## 4. Single forced change

**Make lockout accounting impossible to reach without a verified key, on every route.**
- Put the key-verified predicate inside `_auth_lock_note_failure` and delete the direct call at `janus.py:5623`.
- Make the pre-auth "locked" answer uniform.
- Add a battery case that sprays wrong keys at every pre-auth route (`/auth/2fa/pickup` included), then proves the correct key still works.

If this is verified alongside the one-line `DO NOTHING` for C9-02 and the tail-only truncation for C9-03, my vote moves to CONVERGED, conditional on the U9 line.

## 5. Coverage

- **Read in full:** brief, sentinel.py, docs, the TRACK-126 report and Vesper's verification report, R-F diffs.
- **Read closely in janus.py:** the anchor fence (2090-2390), born-empty/U9, auth/lockout (2840-3300), need_auth and POST dispatch (4165-4560), ingest conf (4698-4720), hotlist add/queue (4933-5115), verify (5118-5165), pickup/unlock (5600-5760).
- **Sampled in janus.py:** the hotlist match and list queries.
- **Tests:** the T and U harness heads, the U9 case.
- **Not touched:** Tier 3, Compact, retention, evidence, scripts/restore.py (U13), backup.py (U10), checkpoint.py beyond its path, the remaining test files, U14 beyond reading the memo (`janus.py:2291-2314`, which looked correct).
- **Executed:** 6 repros, listed in §1.
