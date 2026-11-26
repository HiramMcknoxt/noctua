# Round 10 — Claude Seat B review (as returned)

- Chat: https://claude.ai/chat/f3fe3c06-b9dd-47e3-bb12-d89b81722986
- Model/effort, operator-observed in the UI: Opus 5.5, Medium ("Model: Opus 5.5 Medium"; picker shows Opus 5.5 checked, "Effort: Medium (Recommended)" checked). Fable not selected. The seat's own text says it cannot see the UI — the operator's observation governs.
- Method: EXECUTING seat — rebuilt janus127 from the pack (md5s match Vesper's verification record exactly), re-ran the V battery test side (19/19 PASS), ran 10 reproductions of its own (r01–r10). Discrimination (0/19) not re-run — no janus126 in the pack; relies on Vesper's record.
- Vote: CONVERGED. V5 reason gate REOPENED at its edge (HIGH, insider-only, externally detectable) — the seat states a strict chair reading of criterion 2 on this item would flip its vote. V7 PARTIAL (test mirror missing, LOW). New finding: releases open in ceremony state (MEDIUM, register).

---

I'm voting CONVERGED. No deployment-blocking or critical code finding survived my runs. One forced change, V5, is incomplete at its edge: it's a HIGH, insider-only bypass of the anchor fence, which I'm carrying as the first post-convergence fix.

Method. I rebuilt janus127/ from the pack; the md5s of janus.py, sentinel.py and compact.py match Vesper's verification record exactly. I re-ran the V battery's test side here (19/19 pass). The pack has no janus126, so I could not re-run discrimination; that relies on Vesper's record. I wrote and ran 10 reproductions of my own. Scripts, logs and run-next.sh are in claudeB-r10-evidence.tgz, and HANDOFF.md is current.

## §3.1 — V1–V18

- V1 — CONFIRMED FIXED — V battery re-run. Pickup refusals are a uniform 401 in my G3 run, and the locked main path also answers with the uniform 401 body (r04).
- V2 — CONFIRMED FIXED — V battery re-run. The adjacent shape (a collision with an inactive row) is G1 below.
- V3 — CONFIRMED FIXED — V battery re-run.
- V4 — CONFIRMED FIXED — V battery re-run, plus r05, r07 and r08 (see §3.4).
- V5 — PARTIAL — the atomicity half holds; the reason gate is REOPENED at its edge — r01, executed. The gate checks only the reason already recorded (janus.py:2252–2263). A fence that is already up never gets its reason upgraded, because a new record is written only when none exists (2283–2293). So: tear a checkpoint line, which raises a file-state fence. Then add a genuinely disagreeing checkpoint; the fence stays 503, but the record still says checkpoints_malformed. Then delete both lines: the fence clears with ANCHOR_CLEARED {prior_reason: checkpoints_malformed} and no two-key accept. The control (a disagreement alone) stays fenced, as commissioned. Severity HIGH: it needs host-level insider access, and the outside witnesses (sink, Clerk's copy) still detect the change. Fix: when a record exists and a new evaluation finds checkpoint_disagreement, chain an upgrade and rewrite the record with the disagreement's bad_ids, appending first.
- V5b — CONFIRMED FIXED — r02. With the chain append forced to fail, the file-state clear, the accepted-disagreement clear and the set all abort, with 0 entries written. The two-key accept path is transactional (it rolls back on exception, janus.py:4513–4519).
- V6 — CONFIRMED FIXED — The V battery's v6 case is exactly the appendix shape (main file garbage, WAL sidecars removed), and it passes here. Code read: any exception reads as "unknown" (restore.py:435–452), which counts as provisioned (janus.py:2534–2541).
- V7 — PARTIAL — product fixed, test half not done — The product glob <db>*.pre-restore-* (sentinel.py:493) prunes and flags every artifact (v7 passes). But the commissioned mirror in the builders' schema check was not made: run verbatim on r08's really-restored directory, run_tests.py:1402–1416 reports 2 loose files (the signing-key and public-key pre-restore copies). Severity LOW (test coverage only).
- V8–V15 — CONFIRMED FIXED — V battery re-run. Pending submissions do expire, but only when the queue paths run (see G2).
- V16 — CONFIRMED FIXED — r03, end to end. With a garbage sink and nothing ever delivered, /health names seqs 1–5. The accept call returns 200, archives sink.log.diverged-*, and backfills 6 clean lines; the sink then reports ok: true.
- V17 — CONFIRMED FIXED — r04, live. Five bad codes with a correct key lock the account (row present). Shell unlock clears the row, the next login succeeds, and the read path writes nothing back. After a restart the user is still unlocked, and ACCOUNT_UNLOCKED is chained once.
- V18 — CONFIRMED FIXED — r05, live between two provisioned agencies with different secrets. Per-side secrets give ok: true, the audit result is recorded on A, and the receipt is recorded on B with no second-factor header. Swapped secrets fail with 401.

## §3.2 — Gemini items

- G1 — VERIFIED (survives), MEDIUM. r09: a supervisor's listing expires (made inactive by sync). A detective then re-submits the same plate, gets the uniform 202, and it never appears in the queue. The cause is the WHERE pending=1 guard (janus.py:5265–5275). A wanted vehicle can silently fail to be relisted.
- G2 — VERIFIED, changed shape, LOW. hotlist_sync sweeps active=1 rows (hotlist_sync.py:86–108), which includes pending submissions. It chains HOTLIST_EXPIRED for a row that was never live, and a supervisor can still approve that row into an active row with a past expiry (janus.py:5328). That row alerts no one. The 30-day pending expiry covers age, but it only runs when the submission or queue paths run, not on a timer.
- G3 — VERIFIED (survives), LOW-MED. r06: _totp_pickup reads the in-memory user list without reloading (janus.py:5835; only auth() reloads, at :3459). Right after disable-user, or after rotate-key with the old key, pickup still accepts the key (409 instead of 401) until any other authenticated request reloads. With a pending pickup and its token, a disabled or revoked key would collect the secret, the recovery codes and a fresh API key. Ingest traffic shrinks the window to milliseconds in production. Fix: call _reload_config() at the top of pickup.
- G4 — mooted for now; the latent trap remains, LOW. rotation.py:228/277 still hardcodes the versions "1.2.2" to "1.2.5". It works only because Janus still publishes schedule version "1.2.5" (janus.py:8206).
- G5:
  - (i) VERIFIED, LOW-MED. r10: a backup root inside the escrow directory succeeds (rc 0), putting the backup sets and keys under one directory. The forward direction is refused (backup.py:169–180).
  - (ii) VERIFIED by code read, LOW. enroll_2fa has no disabled-account check (provision.py:376–400).
  - (iii) VERIFIED, LOW-MED. r10: a stale case feed returns 503 for /auth/unlock, /audit/sink-divergence-accept and hold placement. The error calls them "data reads" (janus.py:4595–4605). Only /heartbeat and /audit/anchor-accept are exempt.
  - (iv) CLOSED by V6.
  - (v) CLOSED by V8; the v8 case passes here.

## §3.3 — Judgment calls

- Call 1 (fence set): ratify the extension, OBJECT IN PART. In r07 a key-only supervisor in the ceremony state can release a hold alone (200), and two can lift a protection order. V9's own logic says a release is not a safety write, so the releases belong inside the ceremony fence. The near-match oracle (§3.4) also argues for fencing that response field. Leaving /lists, /stats, /config/status and /audit* open is fine: no plate text found in /audit.
- Call 2: Ratify. r05: provisioning mid-run under LAB immediately refuses key-only humans (401), /health says lab_mode: true and provisioned, and the next boot refuses with exit 3.
- Call 3: Ratify (S10 retry gating).
- Call 4: Ratify (health availability as a measurement, not a gate).
- Call 5: Ratify (V10 beyond the letter).
- Call 6: Ratify (V13 supervisor carve-out).
- Call 7: Ratify (only the chain payload and /health are capped).
- Call 8: Ratify. G3 is a separate freshness gap on the same pickup path.
- Call 9: Ratify (V8 seeded markers).
- Call 10: Ratify as shipped. A missing field reading as "unknown", and so provisioned, is the fail-closed direction.
- Call 11: Ratify. r05 shows the legacy shared secret with two provisioned agencies fails loudly (401) rather than silently. Two small fixes for the register: compact.py should warn when it falls back, and handle a 401 on the audit-result post instead of crashing.

## §3.4 — Ceremony state

What held (all executed):
- On a populated install with no LAB flag, /hits and /search return 503 to key-only humans and CEREMONY_REFUSED is chained.
- The bootstrap enrollment path works: the enrolled user is served with a code, an unenrolled supervisor gets 401, and the second enrollment requires --confirm-by.
- LAB lifecycle: provisioning while LAB is set ends key-only service immediately, and the next boot refuses.
- Restore onto a LAB host: restoring a provisioned backup makes the next LAB boot exit 3 with LAB_MODE_REFUSED chained. A boot without LAB comes up provisioned with must_reenroll set for 6 accounts.

Side door, executed (r07), MEDIUM: A key-only supervisor's POST /suppressions returns warning_near_matches: ["KXR 4471","kxr-4471"] for a plate that was read, and [] for one never read (janus.py:5561–5627). That is a "was this plate read?" check through an open surface. It fires whenever the camera's OCR text isn't already canonical, and the Frigate bridge forwards raw OCR text. It is limited: supervisor-only, and every probe chains a real protection-order record that needs two keys to release. The seat does not consider it a blocker, so the U9 adjudication does not reopen. It and the open releases go to the register.

New deployment-blocking findings: None.

## Register (post-convergence triage)

- V5 edge (HIGH; first fix, before any pilot)
- Ceremony suppression near-match oracle (MEDIUM)
- Releases open in the ceremony state (MEDIUM)
- G1 (MEDIUM)
- G3 (LOW-MED)
- G5(i) and G5(iii) (LOW-MED)
- G2, G4, G5(ii) (LOW)
- V7 test mirror (LOW)
- On the V5 set path, an append failure leaves the service unfenced, since the fence reads only the stored record (janus.py:2154) (LOW)
- compact.py: state is saved through a fixed .tmp path, and a 401 on the audit-result post crashes with a traceback (LOW)

## Convergence criteria

1. Met. No surviving deployment-blocking or critical code finding.
2. Met, with one named exception: V5's reason gate. The seat reads the edge as HIGH, insider-only and still detected externally, which is below §3.5's bar for a NOT CONVERGED vote. If the chair reads criterion 2 strictly, this is the item that would flip the seat's vote.
3. Met. What remains is register items plus the legal track.
4. Accepted. The seat's test-side V re-run agrees with Vesper's record. Discrimination not re-run here.

Vote: CONVERGED.
Single forced change: none required for convergence. The recommended first 1.2.7.x item is the V5 edge fix, with r01 as its discriminating case.

## Coverage

Read in full: the brief, the docs, TRACK-127, Vesper's verification, and the synthesis with its diffs. janus.py: targeted ranges (anchor fence, ceremony, auth/lockout, dispatch, holds/suppressions, hot-list submissions, pickup, anchor accept, provision/restore markers, config, stats, LAB). Scripts: restore, compact, backup, provision, hotlist_sync and rotation, in the touched regions; sentinel.py for Chain.append and the registry. Not touched: Tier 3, evidence, shares, report compile, retention.py, checkpoint.py, alert_check.py, and the Q/R/S/T/U/load test bodies. The full battery was not run. No truncation (files rebuilt from the pack, md5s checked).

Seat's HANDOFF.md (attached in chat): DONE; reproductions r01 V5 stale-reason bypass REPRODUCED (V5 reopened at its edge, HIGH); r02 V5b holds (register note: append failure on the set path leaves the service unfenced); r03 V16 holds; r04 V17 holds; r05 V18 + LAB lifecycle holds; r06 G3 reproduced; r07 ceremony side doors (oracle + key-only releases); r08 restore onto LAB host + bootstrap holds; r09 G1/G2 reproduced; r10 G5(i)/(iii) reproduced; V7 suite_schema mirror missing (shown on r08's restored directory). Evidence bundle claudeB-r10-evidence.tgz attached in the chat (not downloaded).
