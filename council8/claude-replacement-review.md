# NOCTUA Council Round 8: Claude seat (replacing Merlin)

**Subject:** NOCTUA 1.2.5 (`janus125/`), rebuilt from the attachments: `janus.py`, `sentinel.py`, `scripts/*`, `tests/*` split back into a tree.
**Model / effort:** I can't see the chat interface from inside this session, so under the seat protocol: *the interface shows no model name to me.* My environment reports the model as Claude Opus 5.5 (`claude-opus-5-5`). I can't see the effort setting. The brief calls for Medium.
**Method:** I read the code and cited file:line. I also **ran five reproductions** against the rebuilt tree, using the T battery's own `Boot`/`req` harness without changes. Each one ran twice and gave the same result. The scripts are in `repro/` and `run-next.sh` reruns all of them.
**Line numbers** are lines of the real source files. For `janus.py` and `sentinel.py` that is the attachment line minus 3. For scripts it is the line within each split file.
**Coverage:** I did not read all 8,580 lines of `janus.py`. I read the T1–T9 surfaces in full: auth, TOTP, lockout, anchor/fence, checkpoints, restore flip, `/reads`, `/hotlist`, `/verify`, re-enroll/pickup and `/health`. I also read `provision.py enroll-2fa`, `restore.py` file handling, `backup.py` escrow, `alert_check.py` and the scrubber. I searched the rest by keyword. Areas outside T1–T9 that earlier rounds hardened (Tier 3, Compact, retention) got no fresh review.

---

## 1. Findings register (most severe first)

### R8-C1: Anyone can lock any account, including the ingest identity, with no credential at all. HIGH; blocks deployment.
- **Attacker:** any unauthenticated network peer that can reach Janus (the office LAN via the TLS proxy, INSTALL §5). Usernames are not secret.
- **Path:** `need_auth` charges *every* failed authentication to the named account. That includes a wrong **API key** (`janus.py:3832-3840` → `_auth_lock_note_failure`). The only check is `user in USERS`, so machine identities count too (`janus.py:2802`). The lock is checked only *after* the key matches (`janus.py:2923-2931`), so the real holder is refused while locked. Once a lock expires, `fails` stays ≥5, so **one** further bad request relocks the account (`janus.py:2804-2809`). Locks are persisted to `meta` and survive a restart (`janus.py:2761-2790, 2840`).
- **Executed** (`repro/r8_seat_repro.py` F1): five requests to `/reads` as `ingest.local` with key `not-the-key` all returned 401. After that, **the correct ingest key got 401** and no further reads landed. I did the same to `jobs.local`, and its correct heartbeat got 401. I did the same to **both** supervisors, and then neither could call `POST /auth/unlock` (401, 401). The chain recorded 4 `ACCOUNT_LOCKED` entries. Re-arming the attack costs about one request per account every 15 minutes.
- **Why this is a guarantee breach:** "availability of alerts" is a stated guarantee. While ingest is locked, Frigate→bridge→Janus forwards fail. The bridge does not queue (`frigate_bridge.py` docstring: "it does NOT queue to disk"), so plates that cross the cameras raise no hot-list alert. **Health can stay green**, because `locked_accounts` is not an input to `ok_all` (`janus.py:8402-8415`). `alert_check.py:93` returns OK whenever `ok` is true, so the locked-accounts reason it knows how to print (`alert_check.py:194-198`) only appears once something else has already degraded health. The first signal is `cameras_silent_after_report` after 6 h (`janus.py:543`). There is no recovery path while the attack continues: unlock needs an unlocked supervisor (`janus.py:5093`), and `provision.py` has no unlock command.
- **Existing compensating controls:** `ACCOUNT_LOCKED` and `AUTH_FAIL` are chained. Janus is reachable only from the office LAN. These make the attack *visible after the fact*. They do not keep alerts flowing.
- **Note:** this is a **regression introduced by T2** and was not present in 1.2.4. It also makes R-C worse: one unbound ingest identity is a single lockable point for every camera.

### R8-C2: The anti-withdrawal rule in T7 depends on a rank the caller asserts, and NaN gets around it. MEDIUM.
- **Attacker:** whoever holds the ingest key or the bridge secret, or a misbehaving bridge or Frigate.
- **Path:** `conf` is `float(conf)` with no range or finiteness check (`janus.py:4267-4272`). The equal-rank refusal compares `(phase, conf)` tuples (`janus.py:4333-4346`). With `conf = NaN` both `<` and `==` are false, so the delivery falls through to "takes currency" and withdraws the PENDING hit. With `conf = 1e9` (or `Infinity`, which Python's json accepts) it is a legitimate "strict out-rank" every time.
- **Executed** (F2): a hit raised at conf 0.95 / `end`, then a redelivery of `NEW222` with `conf=NaN` returned **200 superseded, and the hit went to WITHDRAWN**. SQLite stored NaN as NULL. The same happened with `conf=1e9`.
- **Existing compensating control:** `READ_SUPERSEDED` names the withdrawn hit ids (`janus.py:4413-4419`), and the hit is withdrawn rather than deleted.
- **Fix:** reject any `conf` that is not finite or not in [0,1] with a 400. Treat F8's attacker model honestly: the strict-out-rank path still lets a key holder withdraw a hit by asserting a higher confidence. See judgment call (c).

### R8-C3: The /hotlist oracle is fully intact. Only the status code changed. MEDIUM. (Ruling on R-B: this is a defect.)
- **Path:** in `_post_hotlist`, **the only** 404 is the protected-plate branch (`janus.py:4490-4512`). Every other plate with a valid case, list and category gets 201 (`janus.py:4538-4553`). There is no "unknown plate" outcome for an add endpoint, so 404 means "protected" with certainty.
- **Executed** (F3): the protected `ORC222` returned 404 "plate not found". `QQQ999`, `ZZZ000` and even `NOSUCH1` all returned **201 added**.
- **Test gap:** `T7-hotlist-oracle-shaped` checks the message text but never compares it with an unprotected plate (`tests/run_t125_cases.py`, `t7_hotlist_oracle`), so it can't detect this.
- **Existing compensating controls:** `SUPPRESSION_CONFLICT` is chained with `by` (`janus.py:4498-4500`). Each non-protected probe also leaves a real chained `HOTLIST_ADD` against a real case, so probing is costly and auditable. That keeps this at Medium.
- **Fix direction:** make non-supervisor adds uniform. One option: every non-supervisor add of a plate that hits a suppression returns the same 201 shape as a normal add but routes to a sealed supervisor queue. The other: all detective adds return 202 "accepted for supervisor listing". TRACK-125 §5's "protected-or-unknown" description should be corrected either way.

### R8-C4: The live anchor check re-verifies every checkpoint through openssl every 5 s while holding DBLOCK. Cost grows without limit. MEDIUM. (Bears on R-E.)
- **Path:** `anchor_fenced()` re-runs `_anchor_evaluate()` at most every 5 s on every non-exempt request, `/reads` included (`janus.py:2037-2050, 3986`). That calls `_bad_checkpoints`, which runs `sentinel.verify_bytes` once per checkpoint (`janus.py:2130-2137`). Each call is a **subprocess plus three temp files** (`sentinel.py:1196-1222`). It all happens inside `do_POST`/`do_GET`'s `DBLOCK`. Checkpoints accumulate daily and are never pruned, and the audit log has a 3-year floor.
- **Executed** (`repro/r8_checkpoint_growth.py`, valid signed checkpoint lines, no sink, 2-CPU VM; two runs):

  | checkpoints | reads/s | worst latency |
  |---|---|---|
  | 1 | 682 / 652 | 0.01–0.03 s |
  | 365 (1 yr) | 422 / 373 | 1.6–1.7 s |
  | 1095 (3 yr) | 62 / 32 | **4.5–4.75 s** |

  At three years, every 5 s window holds the whole service for about 4.5 s. On the builder's 1.5-CPU VM, with the sink's per-append verification also in play, that becomes a near-permanent stall.
- **Fix:** verify each checkpoint's signature once and cache the result by (entries, root, sig). Live re-evaluation then only needs `hash_at_seq` lookups, which are cheap.

### R8-C5: The backup key "split" is just a sibling folder on the same storage by default. MEDIUM. (Bears on judgment call (d).)
- The escrow root defaults to `dirname(backup_root)/key-escrow` (`backup.py:227-230`). Anyone who can read the backup target can read the escrow, in plaintext. The custody split exists only if an operator sets `NOCTUA_KEY_ESCROW_DIR` to storage held by someone else, and nothing enforces, warns about or health-reports that.
- **Fix:** refuse to write the escrow unless `NOCTUA_KEY_ESCROW_DIR` is set explicitly and is not under the backup root's parent, or at least print the custody warning and add a go-live checkbox.

### R8-C6: The shell's "two-key" enrollment can't stop the person running it. LOW (an honesty gap in the documentation).
- `provision.py enroll-2fa` loads the whole TOTP store, including every confirmer's `secret` (`provision.py:346-357, 368-426`). Whoever can run it can compute any confirmer's current code. The `PROVISION_2FA` evidence is a marker file the same user writes (`provision.py:459-465`) and can delete before Janus consumes it. T8's "every provisioning mutation chains" is therefore true only for an operator who cooperates. Neither problem is fixable in code without encrypting the store. Both belong in CANT-DO next to the openssl PATH residual.

### R8-C7: The scrubber misses letter-for-digit homoglyphs. LOW.
- **Executed** (direct calls to `sentinel._contains_plate`): `ABC12З` (Cyrillic Ze standing in for 3) and `ABC1О3` (Cyrillic O standing in for zero) are **not detected**. The fold maps О→Latin O, not →0 (`sentinel.py:1280-1296`). Full-width, ZWSP-split, math-bold and Latin-letter confusables are caught.
- **Fix:** in the folded copy, also try digit substitutions (O/О/Ο→0, З→3, I/І/Ι→1, Ѕ→5, В→8) when checking shape. This is detection only, as now.

### R8-C8: Hold release counts as a "safety write" under the anchor fence. LOW.
- `/holds/release` is in `ANCHOR_FENCE_SAFETY_POST` (`janus.py:2028-2030`). Releasing a hold makes evidence purgeable. During a suspected rollback that is a destructive act of custody, not a protective one. Placing holds should stay open. Releasing them should be fenced.

### R8-C9: The per-target failure tables grow without limit. LOW.
- `_auth_fail_totals[_user_hash(user)]` gets a new key for every distinct username sprayed and is never pruned (`janus.py:2664-2665`). That is an unauthenticated memory-growth vector. Bound it the way `_chain_throttle` is bounded (`janus.py:2733-2736`).

### R8-C10: Partner-readable chain entries name protected hits. LOW / informational.
- A detective's refused verify chains `BLOCKED {hit, reason:"suppressed_queue"}` (`janus.py:4598-4601`). A partner's `chain_auditor` can join that hit id to `ALERT {hit, cam, category}` and learn that "the felony-warrant hit at CAM-03 at 14:02 is under a protection order". Consider a keyed hit reference in BLOCKED entries.

### R8-C11: The version header is stale. NIT.
- `sentinel.py:5` still says "NOCTUA 1.2.4", and the module docstring has no 1.2.5 section, while `REGISTRY_VERSION="1.2.5"`. This is a candidate for R15's honesty sweep.

**Verified clean in this pass (no finding):** T1 states are kept apart end to end (`_totp_read` `janus.py:2381-2403`; auth refusals at 2932-2952). The restore flip runs after the TOTP helpers are defined (`janus.py:2612`). RECOVERY_USED is deferred to the locked flush (`janus.py:2495-2511, 3943-3945`). T5 checks are strict and each is guarded (`janus.py:2127-2152`). T6 parsing goes line by line (`janus.py:1980-2010`) and `pubkey_fingerprint` cannot raise (`sentinel.py:1158-1176`). Below-tail sink candidates are verified against the sink file (`sentinel.py:1852-1874`). The equal-rank refusal is not stored as a version (`janus.py:4346-4366`). The re-enroll confirm returns no secret (`janus.py:4970-4998`). Pickup rotates the key before it is consumed (`janus.py:5048-5079`).

---

## 2. Rulings on the named residuals

- **R-A, restore indistinguishability: ratified limitation, but the builder's claim is too strong.** Code already separates most real cases. `restore.py` does **not** overwrite the live checkpoints file (`restore.py:438-445`). So restoring a pre-provisioning backup onto a provisioned install that has published even one later checkpoint truncates beneath that checkpoint (`janus.py:2146-2148`), and the T3 fence engages. Health is also red by name in the provisioning state (`janus.py:8331-8336`), and RESTORE is chained (`janus.py:2245`). The remaining case needs host-file access, which CANT-DO already concedes. There is also a cheap ratchet: `restore.py` has the live DB in hand just before `aside()` (`restore.py:417-426`). It could copy the live `totp_provisioned` marker into `restore_marker`, and `_consume_restore_marker` could honor it. Recommended, not required.
- **R-B, /hotlist residue: defect.** See R8-C3. The 404 has a single meaning.
- **R-C, unbound legacy identities: ratified as a deployment decision, with conditions.** The code names them (`janus.py:8396-8401`), but health stays green with them unbound. Add "every ingest/jobs identity bound" to the INSTALL §8 go-live checklist. Note that R8-C1 makes an unbound shared ingest key a single lockable point for every camera.
- **R-D, pickup is key-only: ratified limitation, with two cheap mitigations.** Once the second factor is lost, the key is the only thing the holder has left, so this is inherent. But a pending pickup **never expires**: `pickup_pending` has no clock (`janus.py:4973-4982`), while the request side does (`janus.py:4957-4969`). Give the pickup a 24 h expiry. Better still, have the confirm return a one-time pickup token (not the secret) that the confirmer hands over in person. Then neither a stolen key nor the confirmer alone can collect the secret. Separately, the wrong-key branch at `janus.py:5032` inherits R8-C1.
- **R-E, throughput: sufficient for the pilot, not for the life of the system.** At about 0.5 reads/s average and about 5/s peak (NETWORK §7's 10× busy hour), 17–19 appends/s holds. The envelope as measured misses R8-C4: on fresh trees the measurement had about one checkpoint. A 90-day pilot (about 90 checkpoints) is fine. Year 1 to year 3 is not.
- **R-F, seat-file adaptations: ratify the practice, with conditions.** Adapting a frozen scenario is acceptable when (1) the assertion is byte-unchanged, (2) the only change follows from a commissioned custody change, and (3) the diff is attached for the council, not just described. I could not check (3): the pre-adaptation originals were not in my attachments, so I ratify on the builder's disclosure only. Future rounds should attach `diff -u` for every adapted seat file and the living-suite re-points listed in TRACK-125 §4.

## 3. Judgment calls

- **(a) T1 ceremony state: accept the provisioned-marker shape, and tighten it.** Refusing to serve at all before provisioning would also block the enrollment ceremony and ingest bring-up. But today the ceremony state leaves the **whole data surface** open, key-only, with no time limit (`janus.py:2933-2935`). Fence it the same way T3 does: in ceremony state allow provisioning, auth admin, health and safety writes, and refuse searches, Tier 3, shares and reports.
- **(b) T3 fence line: accept,** apart from R8-C8 (move `/holds/release` out of the safety set).
- **(c) T7 vs R9: the strict (phase, confidence) out-rank is the right reconciliation for honest redelivery.** It is no defence against an adversarial deliverer, because the rank is asserted by the caller. Validate `conf` (R8-C2). Record the residual honestly: a holder of the ingest key can still withdraw a PENDING hit by asserting a higher confidence. It is visible through `READ_SUPERSEDED.withdrawn_hit_ids`. If the council wants more than visibility, withdrawals of hits on alert-class lists should go to supervisor confirmation.
- **(d) Escrow split vs encryption: accept the split,** on the condition that it becomes a real split (R8-C5). Encryption in the script would only move the problem to wherever the decryption key is kept.
- **(e) T4 absence proof: reject inspection-only coverage.** No code change is needed to reach the branch. A **directory at `<sink>.spool`** makes `_sink_state()`'s `open()` raise. **Executed** (`repro/r8_t4_fault.py`): `/health` returned `ok:false`, `sink_status_unknown:true`, `sink.error:"status_unknown"`. The code behaves correctly. Add this case to the T battery. The premise that "no public-API input" can reach the branch was the wrong test: health exists for faults in the filesystem and the database, not just for API inputs.
- **(f) Demo mode: naming it a degradation is necessary but not enough.** Refusing non-localhost binding **would not contain it** in the reference deployment: Janus binds 127.0.0.1 behind a same-host proxy (INSTALL §5), so LAN traffic already arrives on localhost. Better containment uses T1's own marker. `NOCTUA_DEMO_MODE=1` should refuse to start against a database carrying `totp_provisioned`, or holding reads from registered production cameras. A banner on every response is optional.

## 4. Verdict against the convergence criteria

1. **No surviving deployment-blocking or critical code finding: FAILS.** R8-C1 is executed. An unauthenticated peer can halt ingest indefinitely, health stays green for up to 6 h, and no in-system recovery exists while the attack continues. It breaks the stated availability-of-alerts guarantee, and T2 introduced it.
2. **Every forced change implemented or answered in writing: substantially MET.** T1–T9 are all implemented. T7's /hotlist item is not met in substance (R8-C3), and its acceptance case does not test the property.
3. **What remains is CANT-DO or legal: NOT MET while C1–C3 stand.** C4 and C5 are code or defaults, not limitations. C6 belongs in CANT-DO.
4. **Orchestrator re-tests: satisfied** (per the brief; I did not re-run the full battery). My five reproductions are additive.

**Vote: NOT CONVERGED.**

## 5. Forced change (the price of my vote)

**Move the T2 lockout behind key verification, and exempt machine identities from it.** Count a failure toward the lockout only when the API key **matched** and the second factor failed (or the account is in a T1 fail-closed state). Wrong-key failures keep feeding the throttled `AUTH_FAIL` evidence and per-target totals, but never lock. API keys are 256-bit random (`secrets.token_urlsafe(32)`, `janus.py:5053`), so locking on key guesses adds no security and gives every stranger an off-switch. Accounts that owe no factor (ingest, jobs, partner) are never locked. Apply the same rule at `janus.py:5032` (pickup). Two companions: make `locked_accounts` non-empty an `ok_all` input, and add a chained break-glass `provision.py unlock` so a fully locked supervisor tier can recover. **Discriminating case:** five wrong-key requests as `ingest.local` and as a supervisor, after which correct credentials still return 200. It fails on 1.2.5 and passes on the fix. `repro/r8_seat_repro.py` F1 is that case today.

**What would change my vote to CONVERGED:** that change, verified, with R8-C2's `conf` validation riding along (one line). C3–C11 can go to the next build or the pilot gate.
