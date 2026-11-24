# Track A Report — Janus 1.0 (productionized front door)

Built to `/home/hatch/workspace/noctua-1.0/INTERFACE.md`, upgrading the
v0.9 code in `noctua-deploy/`. Python stdlib only throughout. Every
file header states what the file is and its limits.

## What was built

| File | What it is |
|---|---|
| `janus.py` | Janus 1.0. All v0.9 endpoints kept; adds two-key Tier 3, evidence export/release, cumulative counters, heartbeats + degraded `/health`, clock-skew flagging, config reload on mtime, disabled-account auth, request-serializing lock + `busy_timeout`. |
| `sentinel.py` | Sentinel chain, byte-compatible with v0.9 (a v0.9 chain verifies under 1.0); only change is `busy_timeout`. |
| `scripts/retention.py` | v0.9 behavior + evidence gate (exported-unreleased hits are skipped and counted) + `/heartbeat` reporting (ok and failure paths). |
| `scripts/checkpoint.py` | v0.9 signed checkpoint + `/heartbeat` reporting. |
| `scripts/publish_witness.sh` | Carried forward unchanged from v0.9 (daily signed-checkpoint publication). |
| `scripts/provision.py` | NEW. `add-user` (prints raw key once, stores SHA-256 only), `disable-user`, `enable-user`, `rotate-key`, `list-users`. Atomic 0600 writes; Janus picks changes up without a restart. |
| `scripts/backup.py` | NEW. SQLite online backup + config tarball + audit key/checkpoints + SHA-256 manifest with audit-key HMAC. `--prune` deletes sets older than the reads schedule (14 days default). |
| `scripts/restore.py` | NEW. Verifies manifest HMAC + every file hash **before** restoring anything; refuses (exit 2, nothing written) on any mismatch; moves live files aside as `*.pre-restore-*`; verifies the restored chain end-to-end. |
| `scripts/alert_check.py` | NEW. Hourly dead-man check: exit 1 + printed reason when Janus is unreachable or a required job is overdue; optional `NOCTUA_ALERT_WEBHOOK` POST; cron/MAILTO wiring documented (no vendor assumed). |
| `scripts/frigate_bridge.py` | NEW. Real HTTP service on localhost (default :8091): accepts Frigate event JSON or a plain test body, extracts the LPR plate, dedupes, and forwards to Janus `POST /reads` as the system identity. Janus-down → 502, no disk queue (Frigate's own buffer is the outage buffer). |
| `demo/seed_demo.py` | Demo seeder: demo users/cases (provision.py's format), hot list + hits + suppression through the live API, 4,442 background reads (1/10 of a Cabot day) backfilled with matching counters. Fresh-target only; refuses a non-empty DB or a users file containing non-demo users (exit 2; `--force` overrides). |
| `demo/DEMO-DATA.md` | Presenter sheet: demo users/keys, cases, hot list, and walkthrough (a)–(f) with exact curl commands, expected responses, and the Sentinel entry each step writes. |

## Test results — live, against a scratch server (port 18099, DB in /tmp)

**125/125 checks passed** across four suites (scripts in
`/tmp/noctua-test/run_tests*.py` and `/tmp/noctua-demo/walkthrough.py`
during the build; re-runnable against any scratch instance):

- **Phase 1 — API (65/65):** all v0.9 endpoints (ingest, hot list,
  verify→409 on re-verify, outcomes, Tier 2 search, suppression
  stub-vs-marker, report, stats); role blocks (patrol can't ingest or
  add hot-list entries, auditor can't search, unauthenticated 401);
  heartbeats (system-only; `/health` goes degraded→clean); two-key
  Tier 3 (request executes nothing; non-supervisor approve 403;
  **same-user approve 403**; second supervisor approves and gets
  results; re-approve 409; deny then approve 409); emergency path
  (non-supervisor 403; executes; lands in review queue; **own-use
  review 403**; auditor closes it; queue empties); evidence export
  (role/case blocks) and release (supervisor-only); CLOCK_SKEW chained
  for a 1-hour-skewed camera timestamp; chain verifies; every new
  chain kind present (TIER3_*, EVIDENCE_*, HEARTBEAT…).
- **Phase 2A — jobs & scripts (30/30):** evidence bundle file hashes
  and manifest hash recomputed from disk and matching; bundle dir
  0700. Provisioning against the *live* server: add-user key
  authenticates without restart, duplicate refused, disable → 401,
  rotate → old key 401 / new key 200. Retention's actual output line:
  `retention: 1 reads, 1 hits deleted, 1 held skipped, 1 evidence
  skipped` — the released-evidence hit was deleted, the
  exported-**unreleased** hit and the case-held hit survived, outcomes
  were preserved, and the deleted plate string was absent from the raw
  DB file bytes (secure_delete + VACUUM). Checkpoint HMAC verified
  independently; both jobs' heartbeats landed; `alert_check.py` exits
  0 healthy / 1 when Janus is down. Backup set created (4 files,
  manifest HMAC present); **restore of a byte-tampered set refused
  with exit 2 and wrote nothing**; restore of the clean set succeeded
  and printed `restored OK: chain verifies, 53 entries`.
- **Phase 2B — bridge (10/10):** plain body forwarded; Frigate-shaped
  event (`after.attributes.recognized_license_plate`) forwarded;
  duplicate event deduped; `type:"new"` ignored; plateless event
  counted not forwarded; Janus read count grew by exactly 2. Raw scan
  of all 53 audit payloads **and** the Sentinel sink file: **zero**
  occurrences of any of the 10 test plate strings.
- **Demo walkthrough (20/20):** seeded a fresh instance via
  `seed_demo.py` (4,451 reads; report `plates_scanned` = 4,451,
  agreeing with the store; seeder re-run correctly refuses, exit 2),
  then executed DEMO-DATA.md steps (a)–(f) verbatim — including three
  literal `curl` spot-checks — and confirmed each response and each
  Sentinel entry matches what the sheet says. Closing report on the
  demo data: 4,451 scanned, 1 confirmed match, 1 non-corresponding, 1
  arrest; chain verifies.

No check failed at any point; nothing needed fixing after the first
full run. (One cosmetic fix during the build: the seeder's refusal
initially exited 1 instead of the documented 2 — patched and
re-verified.)

## Judgment calls and deviations — stated plainly

1. **`/search?tier=3` no longer executes, even with `judicial=1`.**
   The v0.9 flag-based Tier 3 is replaced by the two-key workflow, as
   INTERFACE.md mandates ("TWO-KEY in 1.0"). The endpoint itself
   works unchanged for Tiers 1–2 and returns a 403 pointing at
   `/tier3/request` for Tier 3. This is the one place "keep every v1
   endpoint working" and the 1.0 spec conflict; the 1.0 spec won, and
   the change is documented in the `janus.py` header.
2. **Retention vs. "never a flat timer" for verified hits.** An
   exported hit is now undeletable until prosecutor release (the
   interface's hard rule). A verified hit that was *never exported*
   still follows the v0.9 30-day resolved-hit timer — exporting is the
   act that enters the evidence lifecycle. Rationale is written into
   `retention.py`'s header; policy can tighten it without code change.
3. **The auditor may close Tier 3 post-hoc reviews.** That is one
   write by an otherwise read-only role — it records a judgment about
   someone else's search and grants no data access. The reviewer also
   cannot be the person who used the emergency path. If the council
   prefers supervisor-only review, it is a one-line role change.
4. **`/tier3/deny` also accepts the requester** (acts as a cancel), in
   addition to supervisors. Approvals remain supervisor-only and
   never same-user.
5. **Read timestamps:** `reads.ts` remains server receipt time (the
   system of record); the camera timestamp is stored in `reads.cam_ts`
   and skew >5s is chained as `CLOCK_SKEW` and returned at ingest.
6. **`/report` plates_scanned is day-granular** (counters are per
   day/camera) and counters begin at 1.0 deployment — v0.9-era reads
   are not backfilled into them.
7. **Backup retention:** full backup sets are pruned on the 14-day
   *reads* schedule (the most restrictive class they contain); the
   18-month outcomes class lives in the live DB and report snapshots,
   not in long-kept full backups. INTERFACE.md's "same schedule as the
   data classes they contain" is implemented as most-restrictive-class
   for a set that contains all classes; a per-class split backup was
   not built.
8. **Heartbeats are wired, not automatic:** retention/checkpoint POST
   `/heartbeat` only when `NOCTUA_JANUS_URL` + `NOCTUA_SYSTEM_KEY` are
   set; otherwise they print that the dead-man switch is unwired for
   that job. A job with no heartbeat ever is reported **overdue**
   ("never reported") at `/health` — silence is an alarm, including on
   day one, until the bring-up checklist runs the jobs once.
9. **`GET /tier3/pending` was added** beyond the interface list —
   approvers need a way to see the queue; it is read-only and
   role-gated like `/tier3/pending-reviews`.
10. **Frigate payload shape is an assumption**, labeled in the bridge
    header: Frigate's LPR plate is read from
    `after.attributes.recognized_license_plate` (or `sub_label`). It
    must be confirmed against the pinned Frigate version during the
    integration day the v0.9 README already budgets; the plain-body
    shape exists so the whole path is testable before that day.
    State defaults to AR when Frigate doesn't report one (also
    labeled) — non-AR hot-list entries only match reads whose state
    was actually reported.
11. **Concurrency:** Janus serializes request handling behind one
    lock. At 9-camera city volume that is not a bottleneck; it is a
    stated design limit, not a hidden one.

## Not implemented / out of scope

- Nothing in the INTERFACE.md §Janus API list is unimplemented.
- CJIS Path B remains out of scope, exactly as the interface states;
  nothing here claims Path B compliance. Path A remains the labeled
  planning assumption.
- The checkpoint key-custody limit is unchanged from v0.9 and stated
  in `checkpoint.py`: with the key on the server, checkpoints detect
  outsider tampering, not a fully privileged insider holding both
  chain and key.
