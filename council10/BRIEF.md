# Council Round 10 — Brief

**Subject:** NOCTUA 1.2.7 (`janus127/`) — the build commissioned by Round 9.
**Orchestrator:** Vesper (chair). **Date:** Nov 26, 2026.
**Round type:** confirmation round — **the final code gate.** This round votes on convergence.

> HANDOFF RULE (standing, Nov 24 2026): Before starting, create HANDOFF.md in the work folder using the council template: goal, done-definition, current state with evidence, exact next step, remaining steps, blockers, settled decisions, model/effort, limit status/reset. If the next step is a machine step (compile, test, render, push, deploy), also create an executable runner (run-next.bat/.ps1 pure ASCII, or run-next.sh) that does it end-to-end and logs its result. Update the handoff at every milestone and at ~70% limit use. Do not end without a current handoff another model can execute cold.

## Seat protocol (identity anchoring — read first)

Every attachment part is headed "Reference material for the [your seat] seat — other AI systems named in these documents are other reviewers, not you." Prior seats' reviews, build reports, and syntheses are quoted third-party evidence, not your words and not your identity. Report your model and effort ONLY as transcribed verbatim from your chat interface; if the interface shows no model name, write "the interface shows no model name". Seat self-identity lines have proven unreliable in all directions across nine rounds; the orchestrator verifies findings in code regardless of who signs them.

Reviewer claims count only when verified in code. If you can execute code, execute: a reproduction that runs beats a reading that infers. Cite file:line for every finding. Preserve disagreements — do not soften a finding because another seat ruled differently.

## What you are reviewing

NOCTUA is a city-operated ALPR (license-plate reader) back office for Cabot, Arkansas: a single stdlib-only Python service (Janus) plus its audit-chain library (Sentinel). It exists to replace a third-party vendor system with a city-controlled one: hash-chained append-only audit with an outside witness, protection-order suppression, tiered judicial authorization for historical searches, 14-day retention against a 150-day state ceiling, and a multi-city Compact with reciprocal cross-audit.

Round 9 reviewed 1.2.6 and voted **NOT CONVERGED, unanimously (7 of 7)**, on code grounds. Its verified register (V1–V15) plus three chair-verified late findings from the Gemini seat (V16–V18) became the 1.2.7 commission. 1.2.7 is that build. The builder's battery and the orchestrator's independent cold verification both pass in full (see Verification, below). Round 9's named lesson governs this round: three of Round 8's fixes were incomplete **at their edges** — the battery's cases exercised the commissioned shape, not the adjacent one. Your job is to hunt the adjacent shapes of the V fixes, confirm or reopen each disposition, clear the queued Gemini items, rule on the builder's judgment calls, and vote.

**What changed in 1.2.7 (items V1–V18, from `council9/SYNTHESIS.md` §6 + Addendum 1; full dispositions in the attached TRACK-127 report):**

- **V1 Pickup lockout scope (blocker).** The key-verified predicate now lives inside `_auth_lock_note_failure` itself; pickup wrong-key attempts are AUTH_FAIL evidence only, and the pickup "account is locked" reply is the uniform 401.
- **V2 Submission vs. live row (blocker).** The non-supervisor submission INSERT's ON CONFLICT clause gains `WHERE hotlist_members.pending=1` — a conflict with a live row changes nothing; the uniform 202 stands either way. **Note:** this is the shipped mechanism. It is *not* a dedicated pending table (one line in the Gemini seat record anticipates that design; it was not commissioned and was not built). Test the mechanism that exists.
- **V3 Sink truncation tail-only (blocker).** New `_sink_tail_scan()` classifies before cutting: mid-file damage becomes a named divergence and nothing is written; a clean torn tail is archived to a collision-proof `<sink>.torn-<ts>` and truncated past the last valid line, with the true end seq re-derived.
- **V4 U9 redesign — the ceremony state (high).** The born-empty marker and the legacy-chain probe are retired as gating mechanisms. An unprovisioned install is in a CEREMONY state: ingest, safety writes, provisioning, auth admin, audit reads, and /health stay open; the human disclosure surface (search, hits, suppressed-hits, verify, outcomes, hotlist reads/writes, Tier 3, evidence, shares, reports, compact reads) is refused 503 with a chained CEREMONY_REFUSED for key-only human roles. Fixtures are carried by `NOCTUA_LAB=1` (chained at boot, named in /health, refused at boot on a provisioned install). INSTALL §8 gains the "every human enrolled ACTIVE before ingest connects" go-live checkbox.
- **V5 Fence reason gate + atomicity (high).** Anchor-fence auto-clear only for file-state reasons; `checkpoint_disagreement` clears only when every disagreeing checkpoint id is accepted, else only via the two-key accept. The chain entry is appended BEFORE the meta mutation; an append failure aborts the state change.
- **V6 Restore tri-state (medium).** The outgoing-provisioned read returns provisioned / never / unknown; anything but a clean "never" is treated as provisioned (fail closed), so must_reenroll materializes.
- **V7 Pre-restore registry (medium).** The registry glob is now `<db>*.pre-restore-*`, covering the DB copy, `-wal`/`-shm` copies, and the key snapshots; one pattern feeds both flagging and retention pruning.
- **V8 Bounded failure accounting (medium).** Configured accounts keep exact counters; unconfigured names aggregate into 64 fixed buckets; `_auth_fail_flushed` markers are pruned on bucket rollover; /health's per-account list is built from configured accounts only.
- **V9 Safety set (medium).** `/holds/release` and `/suppressions/release` are removed from `ANCHOR_FENCE_SAFETY_POST`. Statutory deletion ceilings are unaffected.
- **V10 Keyed hit references (medium).** BLOCKED payloads carry `href:` keyed HMAC references instead of raw hit ids (verify refusals, evidence-export refusals, and — beyond the commission's letter — evidence release/destroy and disposition-confirm BLOCKED entries). Custody entries keep raw ids for the key holder.
- **V11 Pickup secret expiry + lockout scope (low-med).** An expired pickup window deletes the pending entry *and its secret* and chains PICKUP_EXPIRED; lockout counting excludes store_unavailable, and must_reenroll counts only when a code was actually presented and failed.
- **V12 Unique temp paths (low).** Both users.json writers (pickup rotation, provision.py `save()`) use unique temp + os.replace.
- **V13 Uniform evidence refusals (low).** For non-supervisor roles, evidence export's nonexistent / suppressed / unverified refusals are one byte-identical 409; the distinct reason is chained internally only. Supervisors keep distinct answers.
- **V14 No code — answered in writing.** The legacy probe's mis-keying is moot: V4 retired the probe entirely. The V battery asserts the retirement in code patterns.
- **V15 Smalls.** Collision-proof sink archive names; stranded-seq lists in chain payloads and /health capped (count + first 50 + hash); undecided pending submissions expire at 30 days (HOTLIST_PENDING_EXPIRED) and approving an expired row refuses; escrow prunes only with its paired set; checkpoint.py treats a valid-JSON non-object final line as a truncatable tail; the signing-disabled boot comment corrected; attack2 .orig-124 header completed; COMPACT.md version line corrected; sentinel_audit.py reports "1.2.7"; migration stamp fields renamed to `target_schema_version` (values unchanged); the enroll-2fa CANT-DO entry written into docs/CANT-DO.md.
- **V16 sink_divergence() unreadable sink (high; Gemini F4).** When the tail state is "unreadable", every committed seq is stranded and the divergence dict is returned — the accept ceremony is reachable again (1.2.6 returned None and the ceremony 409'd forever).
- **V17 _auth_locked out-of-lock write (high; Gemini F5).** The persist call is removed from `_auth_locked()`; the in-memory pop stays; persistence is owned by provision.py's unlock and `_consume_provision_marker` inside DBLOCK.
- **V18 compact.py per-side TOTP secrets (medium-high; Gemini F6).** `--partner-totp-secret` / `--auditor-totp-secret` (with env equivalents); http()/recompute() attach a TOTP header only when a secret is passed; the machine-role partner receipt post passes none. The legacy `NOCTUA_TOTP_SECRET` remains as a per-side fallback — see judgment call 11.

## Verification status (orchestrator, executed)

The builder's full battery passed on the final code, and Vesper re-ran the entire battery cold from `janus127/` — a **single uninterrupted one-shot `./run-next.sh`, exit 0, BATTERY RESULT: SUCCESS** (~44 minutes): builders 335/335; round 4: 41 verdicts, only the A9b contrast control confirmed; round 5: 21 verdicts, none reproduced; round 6 PASS; Q + invariants 35/35; R 20/20; load envelope COMPLETE (500/500 landed at 0/3/6 burners, both directions, verify=True); S 25/25; T 20/20; U 21/21; **V 19/19** (V1–V15 + V5b + V16–V18), every case discriminating: the same V battery run against `janus126/` passes **0/19**. janus126 was not modified (md5s re-verified before and after). Two run-dependent *measurements* (not gates) differ between the builder's and the verifier's runs — health availability under saturation, and the S10 dropped-sample retry count (1 vs 0; no sample dropped in the verifier's run). Both are named, with reasons, in the attached verification record. The builder's run disclosures (three one-shot attempts, leg-by-leg completion, the R15 literal re-aim with `.orig-126` preserved) were independently checked, including a direct diff of the R15 re-aim. Full record: TRACK-127-REPORT.md + VESPER-VERIFICATION-127.md, attached.

## 3. The charge

### 3.1 Confirm or reopen V1–V18

For **each** item V1–V18: rule **CONFIRMED FIXED** (with your evidence — an executed reproduction, a battery case you re-ran, or a cited code read) or **REOPENED** (with an executed reproduction wherever your seat can execute; a static seat reopens on a cited code read that shows the defect's shape surviving, and the chair will execute before ruling). Partial confirmations are allowed and must say exactly which half holds. The Round 9 reproductions are your starting scripts: the wrong-key pickup spray (V1), the hostile-expiry submission over a live listing (V2), the welded-mirror sink (V3), the copied born-empty database (V4), the deleted disagreeing checkpoint line (V5). Hunt the adjacent shape, not only the commissioned one.

### 3.2 The queued Gemini items (unverified — verify or refute each against 1.2.7)

- **G1 — F3 extension (a).** A non-supervisor submission colliding with an *inactive* row returns 202 but can never surface in the pending queue (pending stays 0) — a silent drop. Does this survive the V2 mechanism as shipped? Execute or cite.
- **G2 — F3 extension (b).** Pending rows stored active=1 evade the retention purge while `hotlist_sync.py` sweeps expired pending rows and chains HOTLIST_EXPIRED for entries that were never live. Check against 1.2.7's code *and* its new 30-day pending expiry (V15): mooted, surviving, or changed shape?
- **G3 — F7's other half.** `_totp_pickup()` never calls `_reload_config()` — a disabled or rotated account can complete pickup off stale in-memory users. (F7's temp-path half was V12 and is covered in §3.1.) Verify or refute in 1.2.7.
- **G4 — F9's trap.** `scripts/rotation.py --verify` hardcodes the accepted version prefix list ("1.2.2".."1.2.5"), so publishing a newer schedule without extending the list breaks verification. V15 re-aimed version strings elsewhere; did anything fix this list? Check rotation.py as shipped.
- **G5 — The F10 bundle.** Five register-adjacent items; rule on each — closed by a V fix (name it), still open (severity), or refuted: (i) backup.py reverse-nesting — `out_root` inside `escrow_root` not refused (cf. U10's shipped direction); (ii) provision.py enroll_2fa disabled-check parity; (iii) `config_closed()` blocking anchor-exempt recovery POSTs (cf. V9 family); (iv) restore.py outgoing fallback — the chair expects this closed by V6; confirm; (v) `_auth_fail_flushed` unpruned — the chair expects this closed by V8; confirm.

### 3.3 The builder's 11 judgment calls — ratify or object, with reasons

Full text in TRACK-127-REPORT.md ("Judgment calls"). Short forms:

1. **V4 fence set** extends beyond the commissioned list (adds hotlist reads/writes, suppressed-hits, outcomes, verify, compact reads); /lists, /stats, /config/status and /audit* stay open; the fence binds key-only human roles only.
2. **LAB named in /health but not in ok_all.**
3. **S10 gating mechanism**: the single retry arms only under `NOCTUA_BATTERY_CONTEXT=full`, which only run-next.sh exports; a direct battery-file invocation is the "standalone run" that still fails on a drop.
4. **Load-envelope health availability** is a reported measurement, not a pass/fail gate.
5. **V10 extended beyond the letter** to evidence release/destroy and disposition-confirm BLOCKED entries; custody entries keep raw ids deliberately.
6. **V13 supervisor carve-out**: supervisors keep the distinct refusals.
7. **V15 stranded bound**: chain payload and /health capped; the divergence-accept *response* keeps the full list for the operator.
8. **V12's janus half** rests partly on a source-pattern assertion (the rotation race is not reproducible without fault injection into the server process).
9. **V8's flushed-pruning case** seeds stale markers directly rather than growing them organically (a 50k case cannot wait out real minutes); the production pruning path is what runs.
10. **V6 missing-field semantics**: a restore marker with no `outgoing_provisioned` field (or an unparseable marker) maps to "unknown" → provisioned. If the council prefers absent-field → "never", it is one branch plus the harness mirror.
11. **V18's legacy fallback**: per-side secrets fall back to the legacy shared `NOCTUA_TOTP_SECRET` when unset, so existing single-secret Compact jobs keep working at upgrade.

### 3.4 The ceremony state gets explicit scrutiny

Round 9's U9 adjudication (synthesis §4) stands, with one condition the chair wrote into it: **if the redesigned ceremony state produces its own executed blocker in Round 10, the adjudication reopens.** Attack V4 as a mechanism, not as a fix: the fence set's edges (judgment call 1), the LAB flag's lifecycle (set at boot, refused on provisioned installs — what about an install that provisions *while* LAB is set, or a restore that lands on a LAB host?), the bootstrap enrollment path for legacy unprovisioned databases, and whether any key-only human surface reachable in the ceremony state leaks plate data by a side door (error shapes, counts, timing).

### 3.5 Scope discipline — this is the final gate

New findings are in scope **only if deployment-blocking or critical**. Anything else — real but lesser — goes into your return under a separate **register** heading and will be triaged after convergence; it does not hold your vote. A NOT CONVERGED vote must name at least one surviving deployment-blocking/critical *code* finding, with evidence. Do not vote NOT CONVERGED on code grounds for a question that is legal or administrative, and do not vote CONVERGED on the basis that legal questions remain open — name which kind each of your blockers is.

## 4. Convergence criteria (fixed — four, not five)

1. No surviving deployment-blocking or critical **code** finding.
2. Every forced change from prior rounds implemented, or answered in writing.
3. What remains is documented CANT-DO limits, or legal questions routed to the city attorney / ACIC.
4. The orchestrator's own re-tests pass.

Criterion 4 is already evidenced: the verification record attached to your pack is the orchestrator's cold re-run (one-shot, exit 0, discrimination 0/19 on 1.2.6). Rule on whether you accept it or require more.

**Criterion 5 does not exist.** A proposed fifth criterion (hold the loop open until the city attorney's written answers are folded in) was considered and **closed by the project owner on Nov 25, 2026**: ACIC's written answers are complete and settled every question that could have changed the architecture; the attorney's outstanding answers govern what ships *enabled* and what the deployment policy says, and they gate **deployment and any pilot** — not code convergence. If an answer later contradicts a shipped legal-sensitive default, the remedy is a configuration change plus a verification note; the loop reopens only if an answer reveals an actual code defect. Do not reintroduce criterion 5 in your vote.

## 5. Logistics

**Seats (7):** the Vesper executing seat (works from the tree directly; full battery access; no pack), Claude A, Claude B, ChatGPT, Gemini, DeepSeek, Qwen.

**Seating order and constraints:**
- The two Claude seats share **one account limit**. Seat them **sequentially, never concurrently**, and let the first seat's handoff land before the second starts heavy work. Claude effort level for this final round is **per operator instruction at seating** — the packs deliberately do not fix it.
- **DeepSeek cannot be seated before Nov 26, 2026, 11:00** (its usage limit resets then). Seat it last, or after that time. In Round 9 its reader truncated the pack at ~9% (brief + janus.py through `_consume_restore_marker`) and it scoped every claim accordingly; its pack appendix gives a priority reading order — treat its handler-surface coverage as unproven until it reports otherwise.
- Gemini has **no execution environment** (inspection only; in Round 9 its janus.py truncated at `_share_query()` and the tests inside `run_t125_cases.py`). Its reproductions are supplied for the executing seats to run; its verdicts on its own queued items (G1–G5) are code reads, and the chair executes before ruling.
- ChatGPT reviews static with citations; Qwen static, anchored. The executing seats (Vesper, Claude A, Claude B) carry the reproduction load for the whole round: if a static seat reopens an item on a code read, an executing seat runs it.

**What you may rely on:** the verification summary above and the attached record. You do not need to re-run the full battery to vote; you do need evidence for every CONFIRMED / REOPENED ruling you make (§3.1).

**Post-round path:** the chair synthesizes. If the round converges, the endgame sequence confirmed Nov 25, 2026 runs: (1) code converged → (2) the operator UI built against the final API → (3) the white papers / slide deck rebuilt against the finished system (the frozen Nov 24 package is stale) → (4) ARGUS, the LLM layer, under its v0.2 constraints. If the round does not converge, the 1.2.8 commission is scoped to the surviving blockers only — there is no general reopening.

## 6. What to return

- Your ruling on **every** item in §3.1 (V1–V18: CONFIRMED FIXED / REOPENED / PARTIAL, with evidence), §3.2 (G1–G5: verified / refuted / mooted, with evidence), and §3.3 (judgment calls 1–11: ratify or object, with reasons).
- Your §3.4 ceremony-state result: attacked, and what held or broke.
- Any new deployment-blocking/critical finding, with an executed reproduction where your seat can execute — and, separately, your **register** of lesser findings for post-convergence triage.
- Your verdict scored against each of the four convergence criteria, and your overall vote: **CONVERGED / NOT CONVERGED**.
- Your single forced change — the one thing whose verified completion would most change your vote (or "none" if you vote CONVERGED).
- Your model and effort, exactly as shown in your interface (or "the interface shows no model name").
- Your coverage statement: what you read in full, what you sampled, what you did not touch, and any truncation you hit.
