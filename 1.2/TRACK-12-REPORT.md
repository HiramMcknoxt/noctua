# NOCTUA 1.2 — Track Report

**Result: 246 checks, 246 passed, 0 failed** (`tests/run_tests.py`,
exit 0, run 2026-11-24 against the final code). 26 of the checks are
the S18 named round-3 attacks. `janus/` (1.0) and `janus11/` (1.1)
were not edited; all work is in `janus12/`.

Council round 3 returned NO-GO from all four seats on 1.1. This
build implements S1–S18 from the round-3 synthesis. What follows is
what was built, the decisions made where the brief left room, the
bugs the new tests caught in the new code, and the honest limits.

## The spine (S1)

`PLATE_DATA_STORES` + `REGISTRY_VERSION = "1.2"` declare every
table.column and folder that can hold plate text or plate-derived
time+place, each with a retention class and a purge action.
`retention.py` purges by iterating the registry (no hand-kept table
list), `sentinel_audit.py` checks the oldest item in every
registered store in both modes, and Janus's `/health` computes
`retention_breach` from the same registry. A schema test in the
suite introspects `sqlite_master` + the data root's folders and
fails if any plate-ish column or folder is unregistered — the one
named exemption is `tier3_requests.results_count`, a bare
cardinality (the permanent record that a search happened), not plate
data.

**Decision:** the registry lives in `sentinel.py`, not `janus.py`.
S15's one-place principle (frag_ref/plate_ref live in sentinel.py
and every script imports them) extends naturally: retention.py and
sentinel_audit.py import sentinel, not janus. `janus.py` re-exports
it as `janus.PLATE_DATA_STORES`, so the brief's access path also
works.

## Item by item

- **S2 Tier 3 lifecycle.** `tier3_requests` stores only matched read
  ids + hit ids (legacy `results` bodies are never returned and are
  NULLed by retention past class age). `GET /tier3/results/<id>`
  resolves the ids live through the current shaping layer —
  suppression filter and case revalidation at read time — and
  returns the plate-free summary (`results_count` + `plate_ref`,
  `expired: true`) when the detail is gone: reads aged out, plate
  suppressed since execution, or retention already nulled the ids.
  A true zero-match execution still answers an empty ok
  (`results_count == 0` is what distinguishes the two).
- **S3 Suppression identity.** `plate_ref()` normalizes internally;
  ingest stores canonical `plate` + `plate_raw`; suppression
  matching is canonical-only (state recorded, never part of
  identity — a TX order suppresses an AR read; tested). Search
  shaping filters suppressed rows in SQL (`NOT EXISTS` on canonical
  refs) before the LIMIT. Suppressed hits verify/export only via
  the supervisor queue.
- **S4 Ingest honesty.** Camera registry in config (`cameras.json`);
  unregistered camera → 403 + `INGEST_REJECTED`. Missing state
  stored `""`, missing confidence NULL — the AR/0.95 fabrication is
  gone from Janus and the bridge. Bridge forwards Frigate's event
  id; Janus dedupes persistently on `(cam, event_id)` and returns
  the original read id on redelivery. Bridge `/event` requires the
  `FRIGATE_BRIDGE_SECRET` header (fail-closed 503 when unset), 1 MB
  cap, socket timeout, locked stats.
- **S5 Health truth.** `/health` requires auth; unauthenticated
  liveness is `GET /ping` → `{"alive": true}` only. `degraded`
  includes `chain_ok`, `retention_breach` (store names), anchor and
  config state; `alert_check.py` names chain and retention reasons
  explicitly. Chain verify is cached ≤ 60 s and never computed under
  the write lock. Camera health is computed against the config
  registry (`never_reported`). `scripts/hotlist_sync.py` ships
  (expiry sweep + `HOTLIST_EXPIRED` + heartbeat), so the monitored
  job exists.
- **S6 Witness + anchor.** `checkpoint.py` reads `(seq, hash)` in
  one query in one transaction, prints exactly one JSON line
  (heartbeat chatter to stderr). `publish_witness.sh` parses only
  the JSON line, publishes, pushes when a git repo exists (push
  failure = failed heartbeat + exit 1), and posts the witness
  heartbeat only after a successful publish; Janus monitors the
  witness job. `restore.py`: tarfile `filter="data"`, signed
  manifest required when a key is configured, db + `-wal` + `-shm`
  moved aside together, the live `checkpoints.jsonl` is **never**
  overwritten (the backup's copy lands as
  `.checkpoints.jsonl.from-backup-<stamp>` — evidence, not state),
  pre-restore copies pruned per registry class, restored files
  0600, and a restore marker Janus consumes at boot to chain
  `RESTORE`. Startup anchor: missing/malformed checkpoints fail
  closed as `anchor_mismatch`; the **max-entries** checkpoint is
  checked; signatures verified (S7); acceptance is two-key
  (supervisor requests, auditor confirms) and records the accepted
  (root, entries) so a restart on the same state doesn't re-trigger.
- **S7 Key separation.** `NOCTUA_AUDIT_KEY` remains the plate-HMAC
  secret and never leaves the box. A new Ed25519 keypair (system
  openssl; private 0600 beside the DB) signs checkpoints, audit
  reports, rotation schedules, and receipts. Partners register a
  public key; `partners.audit_key_fingerprint` stores its SHA-256
  fingerprint. **Decision:** any boot that cannot prove key
  continuity — fingerprint mismatch, probe error with existing audit
  rows, *or a missing key over an existing chain* — is KEY_LOCKED
  and Janus **refuses to start** (exit 3, reason on stderr). This
  deliberately replaces 1.1's serve-503 locked mode: a locked server
  that still answers `/ping` can mask the lock from a naive liveness
  check; a refused start cannot be missed, and the log line names
  the reason.
- **S8 Compact gate.** The gate reads the **latest** `compact_audits`
  row per partner: must be ok and ≤ 26 h; a newer failure closes the
  gate immediately (tested: fail-after-ok, no manual suspension).
  `/compact/audit-result` accepts only a **signed** report and
  records its hash. Receipts must name the newest checkpoint
  (root + entries) and carry the partner's Ed25519 signature over
  `(root, entries, checkpoint_ts, agency)`, freshness from the
  checkpoint's own ts; replayed old receipts are refused (tested).
  `compact.py` independently recomputes the partner chain via
  `GET /audit/range` from its own stored `(seq, hash)`, verifies the
  checkpoint signature against the registered key, and posts its
  signed report even on failure — that is what closes the gate.
  **Decision:** `compact_audits` records audits **by us** (per S12's
  duty-tracking text), signed with *our* key and verified against
  our own public key; audits *of* us are the signed receipts in
  `compact_receipts`.
- **S9 chain_auditor.** Allowed only `/audit`, `/audit/root`,
  `/audit/verify`, `/audit/range`, `/compact/checkpoint` (GET);
  fenced in the dispatcher and covered by a dedicated test sweep.
  `provision.py` issues it. Tier 3 results readership is requester +
  supervisors; the auditor lost body access (tested).
- **S10 Shares.** Tier capped at 2; `case_ref` non-empty, partner
  `basis_type`, and `why` all required; `why` lives in the DB only
  (chain carries `why_hash`); stale-config fail-closed applies;
  60 queries/hour/partner → 429 + `SHARE_RATE_LIMIT`. The partner's
  `case_ref` gets the banned-pattern check only, never membership in
  our case list (a partner's cases are theirs).
- **S11 Chain discipline.** Handler write paths append their chain
  entry on the same connection inside the same transaction.
  `AUTH_FAIL` chains a hashed username + aggregate count, throttled
  per source. Category fields are enums with `"other"` as the
  fallback. The scrubber no longer raises on data paths: it hashes
  the plate-shaped value, chains a throttled `CHAIN_SCRUB_FLAG`, and
  the write proceeds; `cam`/`agency` coded fields are exempt, so
  CAM-101 and CPD-1001 work end to end (fault-injection tested).
- **S12 Rotation.** `build_schedule` **uses the seed**: SHA-256 of
  the seed drives a documented Fisher-Yates permutation; identical
  inputs reproduce byte-identically, a different seed or cycle start
  deals a different order (tested both ways). Members deduplicated
  and validated ⊆ active partners; real calendar dates only; period
  7–120; publishing over an active cycle → 409; voiding is
  supervisor-then-auditor two-key + `ROTATION_VOID`. Duty tracking
  reads receipts (of us) and audit rows (by us) inside each round
  window; delinquency = owed in 2 consecutive rounds, filed in
  neither; witness attestations are posted per round and shown in
  the status. **Note:** `scripts/rotation.py` and
  `janus.build_schedule` share the identical Fisher-Yates core but
  differ in inputs by design — rotation.py sorts members and derives
  the seed from `(cycle_start, members)`; Janus takes the given
  member order and an explicit seed. Cross-checks must pass sorted
  members + the derived seed to both.
- **S13 Config ceilings.** `RETENTION_DAYS > 150` refuses to start;
  Tier 2 window > 72 h refuses to start (the value is in the error).
  The effective config (retention days, tier2 window, bind, registry
  version, signing fingerprint) is in the boot `SYSTEM` chain entry.
  Stale-config fail-closed (`config_closed()`) is consulted by every
  data endpoint; users/cases content changes chain `CONFIG_CHANGED`
  with a diff hash. *Honest limit:* the fail-closed itself engages
  at 24 h of staleness (the 1.1 rule, kept); that exact transition
  is not directly testable without faking the clock, so the suite
  tests the observable parts — staleness degrades `/health`,
  `CONFIG_STALE`/`CONFIG_CHANGED` are chained, clean reload clears.
- **S14 Report residuals.** `REPORT_COMPILE` chains the snapshot
  body hash. List names come from the supervisor-managed list
  registry (`/lists`); hotlist adds with an unregistered list name
  are refused. K8's denominator counts **executed** Tier 3 searches
  only. Per-list prosecutions get the same "not yet reported"
  treatment as the totals. Outcome rows are created at ALERT time
  (`status=unresolved`); an unreviewed hit that ages out stays
  counted unresolved forever. Hotlist membership is a table — a
  plate may sit on multiple lists.
- **S15 Retention correctness.** `plate_ref`/`frag_ref` exist only
  in `sentinel.py`; every script imports them. Key resolution is
  Janus's (env → key file beside the DB; never mints). Retention's
  own connection sets `secure_delete=ON`; the WAL checkpoint result
  is checked and reported; any scrub/purge/chain failure heartbeats
  False and exits nonzero. Defaults aligned (`/data/noctua.db`,
  `NOCTUA_JANUS_URL`). VACUUM runs with busy_timeout + retries; on a
  persistent lock it skips, chains `RETENTION_VACUUM_SKIPPED`, and
  heartbeats ok with the note.
- **S16 Audit tool truth.** `sentinel_audit.py` DB mode opens the
  database `mode=ro` and verifies via `verify_detached` only — no
  `Chain` instantiation, no writes. URL mode treats checkpoint
  entries > chain entries as a **failure** (truncation), surfaces
  `/health` degraded flags as findings, and verifies checkpoint
  signatures with the **assessed system's** public key. Exit
  contract: 0 clean, 1 warnings only, 2 failures — in DB mode the
  two filesystem stores warn by design (their ages are `/health`'s
  job), so a healthy DB exits 1 with zero failures; the suite
  asserts on the report's fail count.
- **S17 Evidence residuals.** Re-export deletes the prior bundle in
  the same operation (timestamped names: a same-second re-export
  reuses the name and overwrites in place — that is the same
  bundle, not an orphan). Release (prosecutor sign-off or confirmed
  disposition) sets `destroy_by = release + 30 d`; overdue
  destructions surface in `/health`. Custody excerpts and `HOLD`
  entries carry hit ids as ints. **Evidence bundles are included in
  backups** (0600), and the inclusion is documented in
  `janus12/COMPACT.md`. (`docs/CANT-DO.md` lives outside `janus12/`
  and was not edited; the note belongs with the 1.2 docs, so it went
  into COMPACT.md.)
- **S18 Tests.** 246 checks, all named round-3 attacks included:
  populated Tier 3 across a retention run; fragment `VIC` vs stored
  `VIC 309`; non-AR suppression; fail-after-ok gate closure;
  replayed receipt refusal; rotation seed sensitivity + byte-identical
  reproduction; publish_witness against a local directory; restore
  keeps the anchor + chains `RESTORE`; chain_ok false ⇒ health not
  ok; `AUTH_FAIL` carries no raw username; CAM-101 end to end; wrong
  key at boot ⇒ refusal; unsigned manifest refused; tar-slip refused
  (even validly re-signed); **1,000 concurrent appends across two
  processes verify clean**; bridge, provision, alert_check,
  hotlist_sync, backup, restore, checkpoint, sentinel_audit (both
  modes), and compact.py end-to-end all covered.

## Bugs the new tests caught in the new code (fixed)

The suite earned its keep — each of these was found by a failing
check during this build, not by inspection:

1. A `DATA_ROLES` pre-gate I added in front of `/search` barred
   patrol from Tier 2 searches 1.1 allowed. Removed; role refusal
   lives in `janus_gate`, as in 1.1.
2. Rotation publish 500'd: `date` was never imported in `janus.py`.
3. `retention.py` crashed on the suppression/evidence registry
   entries — a shared `_cutoff(days)` ran before dispatch with
   `days=None` for the non-age classes. Cutoffs are now per-branch.
4. `Chain.__init__` raced on a fresh database under two processes
   (`journal_mode=WAL` lock during creation) — the S18 stress shape.
   Init pragma/DDL now retry on lock.
5. `/health`'s `ok` ignored mere config staleness (only the 24 h
   fail-closed counted); 1.1 degraded on any stale. Restored.
6. The `retention_breach` check counted a *scrubbed* fragment
   (`pref:…`, still NOT NULL) as a breach forever. The check now
   mirrors retention's completion rule per action.
7. `compact.py`'s `root_matches` compared the partner's **live**
   root against a checkpoint-height recompute — false for every
   healthy, still-chaining partner. It now extends the recompute to
   the live height; a live height *behind* the checkpoint fails as a
   rewind.
8. Tier 3 results answered "ok, 0 results" after retention nulled
   the stored ids; with a positive execution count on the row the
   honest answer is the expired summary. Fixed in the handler.

## Docs and demo

- `janus12/COMPACT.md` rewritten for 1.2: Ed25519 key separation,
  latest-row gate semantics, signed audit reports, newest-checkpoint
  receipts, Tier 2 share cap + rate limit, `chain_auditor`,
  seed-dealt rotation + two-key void, reinstatement's fresh-audit
  requirement, evidence bundles in backups.
- Demo re-run against 1.2 (fresh seed): 4,453 reads (4,442
  background + 11 API), 9 hits — 1 verified (arrest; prosecution
  reported false), 1 rejected, 5 pending, 2 suppressed_pending.
  `demo/DEMO-DATA.md` updated to match: 1.2 setup (camera registry),
  the new QUERY chain shape (`case_hash`/`why_hash`, no raw text),
  `TIER3_RESULTS_VIEW` + the live-resolution results shape, and the
  report's coverage denominator (1 of 9 — outcomes are born at
  alert time now).

## Standing notes

- Act 668 of 2025 (Ark.) remains a flagged legal question for the
  City Attorney lane; per instructions, **no retention logic was
  changed over it** — the 14-day Cabot default stands.
- Nothing was sent to ACIC or the City Attorney.
- Style held: stdlib only; the one external call is `openssl` for
  Ed25519, as sanctioned.
