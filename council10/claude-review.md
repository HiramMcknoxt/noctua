# Round 10 — Claude Seat A review (as returned)

- Chat: https://claude.ai/chat/b82c1dd1-22de-4cfd-bcfa-3c7e7d7a4be8
- Model/effort, operator-observed in the UI: Opus 5.5, Medium ("Model: Opus 5.5 Medium"). The seat's own §7 identifies itself from system configuration as Claude Opus 5.5 (claude-opus-5-5) with no effort level exposed — the operator's UI observation governs.
- Method: EXECUTING seat — rebuilt the 1.2.7 tree from the pack, ran the V battery (19/19 on the 1.2.7 side) and its own reproduction scripts against the real janus.py.
- Caveats recorded by the seat: the pack has no janus126/ tree, so the 0/19 discrimination leg was NOT re-run (relies on Vesper's record); the full ./run-next.sh was not in the pack and was not run (criterion 4 rests on Vesper's record for the full battery).
- Vote: CONVERGED. V5 ruled PARTIAL (executed "reason laundering" edge, rated high not blocking). No single forced change.

---

# NOCTUA Council Round 10 — Claude Seat A return (executing seat)

**Subject:** NOCTUA 1.2.7 (`janus127/`), rebuilt byte-for-byte from the pack's combined files (janus.py, sentinel.py, scripts/, tests/, docs/; every .py compiles).
**Vote: CONVERGED.** V5 is ruled PARTIAL. Reasoning under §5 below.

## 0. What I executed

- **V battery, 1.2.7 side: 19/19 PASS** (`tests/run_v127_cases.py`, exit 0, log `v127.log`).
- **Discrimination against 1.2.6 (0/19): NOT re-run.** The pack has no `janus126/` tree. Each baseline leg raised "no such file", so my 19/19 is the 1.2.7 half only. I rely on Vesper's record for the 0/19.
- **Full `./run-next.sh`: not run.** It is not in the pack, and neither are the round-4/5 attack files. Criterion 4 rests on Vesper's record.
- **My own scripts:** `repro/r10_seatA.py` (V1, G3, V2/G1/G2, V4 + §3.4, V5), `repro/v3_adjacent.py` (sink shapes), `repro/v12_spy.py` (V12 fault injection), `repro/g5ii.py`. Every server-level repro boots the real `janus.py` through the battery's own `Boot` harness.

## 1. §3.1 — V1–V18

| Item | Ruling | Evidence |
|---|---|---|
| **V1** | **CONFIRMED FIXED** | Executed. 7 wrong-key pickups × 3 humans all got 401. Afterwards all three still authenticate with key + code (200), and the locked list is []. A 30-name unknown-user spray gets only 401. Locked edge: a locked account's pickup with the wrong key, with the right key, and an unlocked account with the wrong key all return the byte-identical `{"error":"authentication failed"}`. Code: predicate at janus.py:3216; pickup no-count at :5855; locked reply at :5843; only post-key token failure counts at :5908. |
| **V2** | **CONFIRMED FIXED** | Executed. A hostile past-expiry submission over a live row leaves the row unchanged (category, submitter, expiry) and returns 202; ingest still alerts. A no-expiry submission over a live row also leaves it unchanged. Pending-on-pending rewrites the pending row. Mechanism at janus.py:5266-5275. |
| **V3** | **CONFIRMED FIXED** | Executed six shapes (unit level, live `Chain`). (a) R9 weld mid-file + torn tail → named divergence [4,5,10], nothing deleted. (b) Weld at line 1 + torn tail → divergence [1,2,10], nothing deleted. (c) Torn tail only → tail archived to `.torn-<ts>` (115 B), file cut to the last valid line, missing seq named. (d) Last two lines welded → both archived (458 B), named. The rotation ceremony restores 1..11 in every case. Adjacent residue (e/f) in the register (R-5): mid-file damage with a *clean* tail is invisible to `sink_status`. |
| **V4** | **CONFIRMED FIXED** | Executed (see §3/§4 of the seat's return). Copied born-empty DB: battery passes. Copy taken after provisioning, with and without the TOTP store: every key-only human gets 401 and state is `provisioned` (fail-closed). Restore of a provisioned set onto a fresh host: marker `never`, but must_reenroll=6 materializes and key-only gets 401. LAB on the restored host refuses boot (rc 3). |
| **V5** | **PARTIAL — REOPENED at its edge** | The commissioned shape holds (executed control: the disagreeing line is deleted and the fence stays 503). Deleting the whole checkpoints file then restoring a good one also stays fenced. **Broken edge, executed — reason laundering:** (1) append one torn line → fenced, record `checkpoints_malformed`. (2) The genuine disagreeing checkpoint now stands in the file → still fenced, but the record is **never upgraded** (still `checkpoints_malformed`). (3) Delete the disagreeing line → **fence clears with no two-key accept** (`anchor_accepted_ids` is empty). The chain holds only `STARTUP_ANCHOR_MISMATCH{reason:checkpoints_malformed}` and `ANCHOR_CLEARED{prior_reason:checkpoints_malformed}`; **no disagreement is ever chained.** Cause: janus.py:2280 records a mismatch only when no record exists, and :2244-2258 gates the clear on the recorded reason. Atomicity (V5b) is confirmed by the battery. Fix: one branch — when a live evaluation returns `checkpoint_disagreement` while a file-state record stands, chain it and replace the record. |
| **V6** | **CONFIRMED FIXED** | Battery v6 passes. Code: restore.py:2827-2844 writes the tri-state. Janus maps unknown/absent → provisioned (janus.py `_consume_restore_marker`, `outgoing_state != "never"`). The fresh-host run above also passes. |
| **V7** | **CONFIRMED FIXED** | Battery v7 passes. Glob `<db>*.pre-restore-*` (sentinel.py:493) feeds both flagging and prune. Residue in register (R-8). |
| **V8** | **CONFIRMED FIXED (bounding)** | Battery v8 passes. Code at janus.py:2982-2997 and 3023-3024. **Report inaccuracy:** TRACK-127 says /health's list is "built from configured accounts only". The code at janus.py:3252 sorts all totals, unknown buckets included, and takes the top 10. That is bounded (≤65), but a spray can push a real account's total out of the /health top 10 (register R-7). |
| **V9** | **CONFIRMED FIXED** | Battery v9 passes. janus.py:2173-2182 drops the releases from the safety set. |
| **V10** | **CONFIRMED FIXED** | Battery v10 passes. A scan of every `chain.append("BLOCKED", …)` that touches a hit (janus.py:5362, 5372, 5389, 6567, 6590, 6825, 6873, 6985) finds `hit_ref(hit_id)` in each. No raw hit id survives in a BLOCKED payload. |
| **V11** | **CONFIRMED FIXED** | Battery v11 passes. Expiry deletes the entry and its secret and chains PICKUP_EXPIRED (janus.py:5887-5901). Lockout counting excludes store_unavailable; must_reenroll counts only when a code is presented (janus.py:3338-3346). |
| **V12** | **CONFIRMED FIXED — janus half now executed** | Battery v12 passes. In addition, an `os.replace` spy ran **inside the live Janus process** across a real reenroll → pickup. The single users.json replace came from `users.json.tmp.<pid>.<hex>`; the fixed `.tmp` was never used. Residue in register (R-9). |
| **V13** | **CONFIRMED FIXED** | Battery v13 passes (byte-identical 409 for non-supervisors). |
| **V14** | **CONFIRMED (answered in writing)** | `install_born_empty`, the legacy probe and `_unprovisioned_locked` survive only in comments (janus.py:1141, 2949, 3352). Battery v14 passes. |
| **V15** | **CONFIRMED FIXED** | Battery v15 passes. Executed: a pending row aged 31 days is deleted with HOTLIST_PENDING_EXPIRED chained. checkpoint.py non-object tail: scripts/checkpoint.py:744-765. Paired escrow prune: backup.py:596-621. |
| **V16** | **CONFIRMED FIXED** | Battery v16 passes. sentinel.py:2041-2055 strands every committed seq when the sink is unreadable. |
| **V17** | **CONFIRMED FIXED** | Battery v17 passes. janus.py:3175-3193 does an in-memory pop only; persistence lives in `_consume_provision_marker` (janus.py:1043-1046) under DBLOCK. |
| **V18** | **CONFIRMED FIXED** | Battery v18 passes. scripts/compact.py:980-983 and 1101-1110 add per-side secrets. The receipt post (:1278-1280) passes no secret, so `http()` attaches no TOTP header (:998). |

## 2. §3.2 — Gemini queued items

- **G1 — VERIFIED (survives), low.** Executed. The supervisor lists a plate with a past expiry and `hotlist_sync.py` deactivates the row (pending=0, active=0). A detective then submits the same plate/case. The answer is 202, the row is unchanged, the submission is **not** in `/hotlist/pending`, and HOTLIST_ADD_PENDING is chained for it. The submission is silently dropped. Cause: the V2 guard `WHERE hotlist_members.pending=1` (janus.py:5274) also blocks the inactive-row case.
- **G2 — VERIFIED (survives; V15 does not touch it), low.** Executed. A pending submission is stored with active=1 (janus.py:5266). `hotlist_sync.py` (scripts:1666-1669, no pending filter) sets active=0 and chains **HOTLIST_EXPIRED for a never-live entry**. The row stays in the queue. A supervisor **can approve it**: it becomes pending=0, active=1 with a past expiry, and the next sync chains a second HOTLIST_EXPIRED. Matching does not alert on it (expiry check at janus.py:4823). V15's 30-day expiry works but runs on added_ts, so it is orthogonal. Fix: add `AND COALESCE(pending,0)=0` to the sync query, and refuse to approve rows that have already expired.
- **G3 — VERIFIED (survives), sharper than queued, medium.** Executed. `_totp_pickup` (janus.py:5821ff) never calls `_reload_config()`; only `auth()` does (:3459).
  - **Rotate variant:** with a pickup pending, the admin runs `provision.py rotate-key det.okafor` to revoke a compromised key. If no other request lands first, a pickup with the **old** key + token returns 200 with the TOTP secret and a new API key, and overwrites the admin's rotation on disk. The attacker then authenticates (200) and the admin-issued key gets 401.
  - **Disable variant:** pickup succeeds (200, secret revealed). The disk entry stays disabled, so later authentication fails.
  - Preconditions: old key + pickup token + a race window. Ordinary traffic narrows the window, because any authenticated request triggers a config reload.
  - Fix: one line, `_reload_config()` at the top of `_totp_pickup`.
- **G4 — REFUTED as a live defect; latent trap remains.** rotation.py:3789/3838 hardcode "1.2.2"…"1.2.5". But Janus stamps published schedules `"version": "1.2.5"` (janus.py:8206), a pinned format version, and rotation.py's own builder does the same (:3688). Current documents verify. A future version bump without extending the list would break verification (register R-10).
- **G5:**
  - (i) **Still open, low.** backup.py:405-406 refuses only an escrow inside the backup tree. A backup root inside the escrow tree is not refused.
  - (ii) **Still open, low-medium (executed).** provision.py `enroll_2fa` has no `disabled` check on the target (scripts:2094-2109) **or on the confirmer** (:2152-2156). A disabled account's active enrollment was accepted as the T8 second key (its recovery code confirmed SUP's enrollment), and a disabled account was itself enrolled.
  - (iii) **Still open, low.** janus.py:4595 exempts only `/heartbeat` and `/audit/anchor-accept` from `config_closed()`. `/auth/unlock`, `/auth/2fa/reenroll`, `/auth/2fa/acknowledge` and `/audit/sink-divergence-accept`, all anchor-exempt recovery surfaces, are refused on a stale config file. The shell unlock still works.
  - (iv) **Closed by V6** (confirmed above).
  - (v) **Closed by V8** (janus.py:3023-3024).

## 3. §3.3 — Judgment calls

1. **Ratify.** Executed: every fenced read returns 503 in the ceremony state. GET routes are exact-match (janus.py:8786ff), so the fence set covers every data GET. /stats returns counts only (janus.py:4263-4282).
2. **Ratify.** LAB is named and degraded in /health, and refused on provisioned installs.
3. **Ratify.** The gating is explicit, and a standalone run stays strict.
4. **Ratify.** It is a measurement under saturation and is disclosed as one.
5. **Ratify.** Extending hrefs to release/destroy/disposition is correct (scan above). Custody entries keep raw ids for the key holder, as designed.
6. **Ratify.** Supervisors may know the reason.
7. **Ratify.** The full list goes only to the authenticated ceremony operator.
8. **Accept, and now superseded:** the seat built the fault injection (an in-process `os.replace` spy in a wrapper that runs the real janus.py) and executed V12's janus half live. The residual lost-update race between Janus and provision.py is a separate matter (R-9).
9. **Ratify.** The production prune path is what runs.
10. **Ratify absent-field → "unknown" → provisioned.** Fail-closed is right. An old marker costs one re-enrollment, not an open door.
11. **Ratify.** The fallback reproduces 1.2.6 behavior exactly and fails loudly (401), never open.

## 4. §3.4 — Ceremony state, attacked

**Held:**
- Copied born-empty DB (battery).
- Copy taken after provisioning, with and without the store: fail-closed 401.
- Restore onto a fresh host: must_reenroll materializes.
- LAB on a restored provisioned host: refuses boot.
- Provisioning while LAB is set, mid-run: once the first enrollment lands, key-only humans get 401 (both the pending enrollee and unenrolled others); with a code, 200. A reboot under LAB then refuses (rc 3). LAB never waives a second factor on a provisioned install, because the waiver path requires `not _totp_provisioned()` (janus.py:3369-3371, 3494).
- CEREMONY_REFUSED is chained and throttled.
- Legacy bootstrap: the first shell enrollment provisions the install immediately (janus.py:2773-2782), so the fence lifts only once second factors bind everyone.

**Side door found (executed), low:** in the ceremony state, a key-only **supervisor** can still use `POST /suppressions`. Its `warning_near_matches` (janus.py:5617-5624) returns the raw camera forms that canonicalize to the probed plate. Probing `SEC777` returned `["SEC 777"]`; an unseen plate returned `[]`. That is a plate-read existence oracle for raw-variant reads, open while every data read is fenced.

Each probe places a real, chained protection order that needs a two-key release, and it is supervisor-only. The seat does not rate it a blocker, so the U9 adjudication does not reopen. Fix: omit the warning while `_ceremony_state()` is true.

Also low: `POST /holds` with scope=hit discloses a hit's case number (janus.py:5457-5460). That is not plate data.

## 5. Convergence

| Criterion | Score | Notes |
|---|---|---|
| 1. No surviving deployment-blocking/critical code finding | **Met, by judgment** | The strongest survivor is V5 laundering. Rated **high, not blocking**. Its actor needs write access to the checkpoints file beside the DB. That same custody can already clear the fence directly: the seat executed a forged `anchor_accepted_ids` row written into meta, and it cleared. So laundering adds no adversarial capability; it defeats the fence's mistake-proofing. The external witness (git remote, clerk email, partner recompute from the stored cp mark) is untouched and still catches a real rewrite. G3 is medium and needs two secrets plus a race. |
| 2. Forced changes implemented or answered | **Met, V5 partial** | V1–V18 are all implemented (V14 answered in writing). V5's commissioned shape is fixed; its record-upgrade edge is not. |
| 3. What remains is CANT-DO limits or legal routing | **Met** | No legal question holds the vote. Everything above is code-register. |
| 4. Orchestrator re-tests pass | **Accepted** | Independent 19/19 on the 1.2.7 side agrees with Vesper's record. Could not re-run 0/19 or the full battery (not in pack). |

**Vote: CONVERGED.**

**Single forced change: none.** The seat holds this against the possibility that the chair weighs V5's edge under criterion 2 as an incomplete forced change. If so, the change is the one-branch record upgrade described in V5 — also its top post-convergence item.

## 6. Register (lesser findings for post-convergence triage)

| ID | Finding | Severity |
|---|---|---|
| R-1 | V5 reason laundering (janus.py:2244-2258, 2280). One-branch fix. | **high** |
| R-2 | G3 stale-USERS pickup → rotation reversal (janus.py:5821). One-line fix. | medium |
| R-3 | Ceremony suppression near-match oracle (janus.py:5617). | low |
| R-4 | G2 sync sweeps pending rows, and an expired pending row is approvable (scripts/hotlist_sync.py:1666; janus.py:5330). | low |
| R-5 | Sink mid-file damage with a valid final line: `sink_status` reports ok and /health is green, while `sink_divergence()` names [4,5] (executed). Pre-existing. | low |
| R-6 | G1 silent drop over an inactive row (janus.py:5274). | low |
| R-7 | /health top-10 fail_totals includes unknown buckets; a spray can evict a configured account from the view (janus.py:3252). The report text is inaccurate. | low |
| R-8 | Evidence-merge `.pre-restore-*` files inside bundle directories sit outside the `<db>*` glob. Bounded by the bundle's own destroy. | low |
| R-9 | users.json read-modify-write lost update between Janus pickup and provision.py (atomic now, but not coordinated). | low |
| R-10 | rotation.py hardcoded version list (latent). | low |
| R-11 | G5 (i), (ii), (iii) as above. | low / low-medium / low |

## 7. Model and effort

The seat cannot see the chat interface. Its system configuration identifies the model as **Claude Opus 5.5** (`claude-opus-5-5`). **No effort level is exposed to it.** (Operator UI transcription: Opus 5.5, Medium.)

## 8. Coverage

- **Read in full:** brief (01); scripts (04).
- **Read or searched:** janus.py at auth/lockout/ceremony/TOTP (2694-3540), dispatchers (4393-4740, 8526-8790), hotlist (5147-5345), holds/suppressions (5420-5700), pickup (5821-5990), anchor (2160-2500), boot LAB/DEMO (9515-9600), config reload (921-1070); a function index of the rest. sentinel.py sink code (1775-2105), registry glob, rotation portion. The V battery harness and the cases reused; the T harness's Boot/req. Targeted greps of the TRACK report and the R9 synthesis.
- **Not read:** the docs file beyond greps; the Q/R/S/T/U battery files beyond the harness; janus Tier 3, evidence, Compact and rotation handlers beyond the BLOCKED scan; most of sentinel.py outside the sink and registry.
- **No truncation hit.** Tree rebuilt in full.
