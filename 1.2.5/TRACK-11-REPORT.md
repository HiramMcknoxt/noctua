# NOCTUA 1.1 — Track Report

**Scope:** all 35 council-round-2 items (22 original + 9 from the
fourth seat + Compact items 21–22 + rotation item 35), built in
`janus11/` as a copy of `janus/` (1.0 left untouched as history).
**Result: 184 live checks, 184 passed, 0 failed** —
`tests/run_tests.py`, run against scratch Janus instances on
loopback with throwaway databases. Python stdlib only throughout.
No plate text in the Sentinel chain, anywhere, enforced by a
scrubber in `Chain.append` (item 26).

Run the suite yourself:

```bash
cd janus11 && python3 tests/run_tests.py
```

---

## What was built, item by item

1. **Temporal wall.** `run_search` takes a scope; Tier 2 is limited
   *in SQL* to reads received within `NOCTUA_TIER2_WINDOW_H`
   (default 24). Tier 3 executes at full scope. `/search` accepts
   tier 2 only (tier 3 → 403 pointer; anything else → 400).
   *Tested: a 25h-old read is invisible to Tier 2, visible to Tier 3.*
2. **Fragments.** Empty, <3 chars, or containing `%`/`_` rejected on
   `/search`, all Tier 3 endpoints, and `/share/query`, with coded
   chain reasons. *Tested on /search and /tier3/request.*
3. **QUERY logging.** Every QUERY entry (Tier 2, Tier 3 approved,
   Tier 3 emergency, share) carries `plate_ref` AND `result_count`.
   *Tested for tiers 2 and 3.*
4. **Unlogged reads closed.** `/hits` and `/hotlist` gained role
   checks (detective/supervisor/auditor) and chained
   HITS_VIEW/HOTLIST_VIEW with counts. Failed auth writes AUTH_FAIL.
   `/audit` lost patrol; limit clamped to [1, 1000]. *Tested.*
5. **Suppression redesign.** Suppressed plates are excluded from
   search for **all** roles (empty result, indistinguishable from
   never-read). Hits route to `GET /suppressed-hits`
   (supervisor-only, chained SUPPRESSED_HITS_VIEW). Placement takes
   a protection-**order reference**, not a case; plates normalized
   (strip spaces/hyphens, uppercase) with a near-match warning
   listing raw variants already on file. Hotlist-add of a suppressed
   plate → 403 + SUPPRESSION_CONFLICT. Release is two-key: first
   supervisor requests, a *different* supervisor confirms **with the
   order reference repeated**. *Tested end to end, including the
   hot-listed-and-suppressed plate whose hits exist only in the
   queue.*
6. **Chain atomicity.** `Chain.append` = threading.Lock + BEGIN
   IMMEDIATE root-read+insert with busy-retry. Sink failures spool
   to `<sink>.spool`; the next append drains the spool in order
   before its own entry; `sink_ok` resets after a successful write;
   sink state (ok/errors/last error) persists in a `sink_state`
   table across restarts. `verify()` checks seq continuity.
   *Tested: 200 appends from two processes verify clean; simulated
   sink outage spools 3 entries and recovery drains them in order,
   sink hashes byte-identical to the chain's.*
7. **Startup anchor.** Boot compares the chain to the newest
   checkpoint; mismatch → `/health anchor_mismatch:true` +
   STARTUP_ANCHOR_MISMATCH chained; cleared only by
   `POST /audit/anchor-accept` (supervisor requests, auditor
   confirms). *Tested with a rewritten head entry — see
   "Interpretations" below.*
8. **Heartbeats.** Missing `ok` records as failure; `ok:false`
   degrades `/health` immediately. Roles split: `ingest`
   (POST /reads only), `jobs` (POST /heartbeat only); `system`
   retired everywhere (provision.py rejects it). Monitored jobs:
   retention, checkpoint, hotlist_sync, backup. `/health`
   cross-checks oldest-read age against RETENTION_DAYS directly.
   *Tested.*
9. **Evidence.** Export requires a VERIFIED hit and `case_id` equal
   to the hit's case. Scope is the hit ±1h of same-plate reads;
   supervisor expand to full history requires `expand:true` + a
   reason (reason in DB, not chain). Release requires an existing
   export. Custody ledger EVIDENCE_EXPORT / EVIDENCE_RELEASE /
   EVIDENCE_DESTROY chained; `POST /evidence/destroy` (supervisor,
   after release by either §1804(b) exit) deletes the bundle.
   Custody excerpts use the new `audit(kind)` index, paged.
   *Tested, including bundle file contents and deletion.*
10. **§1804(b) both exits.** `POST /evidence/disposition`
    {no_charges | charges_concluded} posted by detective/supervisor,
    confirmed by a *different* supervisor
    (`/evidence/disposition/confirm`); a confirmed disposition
    releases data for deletion exactly as a prosecutor sign-off
    does, and retention.py honors both. Holds gained `review_by`
    (default +90 days); overdue holds surface in `/health` and
    `/report`. *Tested.*
11. **§1805 report.** All counts derive from `outcomes` + the new
    `lists_checked` table (every active list recorded per day at
    ingest; list_name is the sanitized SOURCE label — "Local agency
    list" for local entries — never a case number). Per-list
    confirmed / non-correlating / arrests / prosecutions /
    arrest-and-prosecution. `outcomes.prosecution` is NULL until
    set; `/report` returns the count of non-null plus
    `prosecutions_coverage {reported, total}`, and the literal
    string `"not yet reported"` when reported == 0.
    `POST /report/compile` freezes an immutable snapshot;
    retention never deletes snapshots or outcomes inside 18 months.
    Zero-match lists appear. *Tested, including report correctness
    after a retention purge.*
12. **Hotlist expiry.** Ingest checks `expires_ts`: expired → no
    alert, auto-deactivate, HOTLIST_EXPIRED chained. `hotlist_sync`
    is a monitored job. *Tested.*
13. **Hardening.** Bind 127.0.0.1 by default (`NOCTUA_BIND`
    override); `hmac.compare_digest` in auth; 1 MB body cap (413) +
    30 s handler socket timeout; hotlist PK (plate, state);
    suppressions keyed by plate_ref over (plate, state); audit key
    file created via `os.open(..., 0o600)`. *Tested: body cap and
    key-file mode live; (plate, state) keying is in the schema and
    the per-state hotlist DELETE path.*
14. **Performance.** Indexes on reads(plate), reads(ts),
    hits(read_plate), audit(kind); WAL mode; retention runs
    `wal_checkpoint(TRUNCATE)` after purge+VACUUM. The global DBLOCK
    is retained, but responses are now *captured* under the lock and
    serialized after it is released, so response I/O no longer
    holds the lock.
15. **Config staleness.** Failed reload chains CONFIG_STALE
    (throttled 1/hour/file) and degrades `/health`; stale >24h →
    `/search` and Tier 3 fail closed 503. provision.py writes
    users.json atomically (already true in 1.0; kept, roles
    updated). *Staleness + recovery tested live; the >24h fail-closed
    is implemented and code-reviewed but not live-tested (it needs a
    day-old stale state) — see "Not live-tested".*
16. **Skew/backfill.** cam_ts >5 min behind receipt = BACKFILL,
    aggregated to at most one chain entry per camera per hour
    (count + max delay; buckets also flush on count ≥1000 or idle).
    CLOCK_SKEW only for cam_ts in the future by >5 s. `skew_s`
    stored on the read row. *Tested both directions.*
17. **Config truth.** janus.py and retention.py both read
    RETENTION_DAYS / HOLD_DAYS from env (defaults 14/30); `/health`
    exposes them. *Tested via /health.*
18. **Case gate everywhere.** One shared `case_gate` (banned-pattern
    + open-case) runs in /search, /hotlist, /verify, /suppressions,
    /evidence/*, /holds, /holds/release (item 32), and Tier 3
    request/approve/emergency. *Tested on hotlist, verify, holds,
    tier3 approve.*
19. **Tier 3 workflow.** Approve re-runs `case_gate` at execution.
    The approver no longer receives results: the **requester**
    retrieves them via `GET /tier3/results/<id>` (chained
    TIER3_RESULT_VIEW; non-requesters refused). Emergency requires
    `auth_basis`; a user with an unreviewed emergency older than 72h
    is locked out of the emergency path (403, chained). *Tested.*
20. **Derived-data purge.** retention.py deletes `case_searches`
    rows older than 14 days outright (the CASE_FLAG chain entries
    carry the signal), and for `tier3_requests` — the workflow paper
    trail, whose rows persist — replaces the plaintext
    `plate_fragment` with its `frag_ref` at day 14. The choice per
    table is documented in retention.py's header. *Tested.*
21. **sentinel_audit.py.** Standalone read-only auditor: URL mode
    (Janus URL + auditor key) or DB mode (DB path + checkpoints
    file). Verifies chain integrity + seq continuity, checkpoint
    HMACs, anchor consistency, retention compliance, derived-data
    purge state (DB mode; URL mode reports it as a warning — the
    API does not expose it), and heartbeat freshness. Emits an
    HMAC-signed JSON report (auditor's own key from env). Exit
    0/1/2. *Tested in both modes (DB mode fully clean → 0; URL mode
    warnings only → 1).*
22. **Compact sharing.** `partners` table; `POST
    /compact/checkpoint-receipt` (partner-role account attesting for
    its own agency; accepted only for a checkpoint we actually
    published); `scripts/compact.py` audits a partner (checkpoint +
    /audit/root + /audit/verify + anchor check), posts our receipt
    to them, and records the outcome on our Janus as
    CROSS_AUDIT_OK/FAIL. `POST /share/query` executes only when the
    partner is active AND our CROSS_AUDIT_OK for them is ≤26h old
    AND their receipt for us is ≤26h old — otherwise 403
    SHARE_BLOCKED naming the missing leg, chained. Successful
    shares run the local gates (partner's case/why recorded as
    partner references; suppression and Tier 2 window apply;
    identical shaping) and chain SHARE_OUT {plate_ref, count}.
    `POST /compact/suspend` blocks immediately. COMPACT.md written.
    *Tested with two live Janus instances as two agencies: each leg
    missing in turn, then both fresh, then suspension.*
23. **Service-account wall.** ingest/jobs (and partner) roles are
    denied on every data-returning endpoint. *Tested on /search,
    /hits, /report, /audit.*
24. **Health truth.** `/health` never returns `ok:true` while
    degraded; degraded covers overdue/failed jobs, sink failure,
    anchor mismatch, config staleness, cameras silent >6h
    (per-camera last-seen exposed as `cameras:{cam:{last_read}}`),
    and the retention cross-check. *Tested.*
25. **Audit endpoint abuse.** `/audit` limit clamped [1, 1000];
    `/audit/verify` and `/audit/root` require auditor or supervisor.
    *Tested (401 unauthenticated, 403 patrol).*
26. **Chain free-text scrub.** Chain payloads carry plate_ref,
    counts, and coded fields only (reason codes; `basis_type` enum
    warrant/court_order/other; review findings as enums). Free text
    (justifications, auth_basis, notes) lives only in DB tables.
    Defense in depth: `Chain.append` scans payload strings and
    raises ChainScrubError — after chaining CHAIN_SCRUB_BLOCKED —
    if a value looks like a raw plate. *Scrubber covered by the
    suite's chain-integrity checks (every workflow above chains
    coded payloads); the pattern is deliberately narrow so case
    numbers, timestamps, camera names, and hashes never trip it.*
27. **Emergency review substance.** Finding must be one of
    {justified, unjustified, needs_followup}; a bare "ok" → 400.
    Note stays in the DB. *Tested.*
28. **Pending visibility.** `/tier3/pending`: detectives see only
    their own; supervisors/auditor see all. `/tier3/pending-reviews`:
    supervisor/auditor, plus the requester's own. *Tested.*
29. **Input validation.** `/verify` decision is a case-insensitive
    enum {confirm, reject} — anything else 400 (1.0 silently
    recorded "Confirm" as REJECTED). Non-numeric tier → 400, never
    500. *Tested both.*
30. **Audit-key loss.** If the DB has audit rows but neither
    NOCTUA_AUDIT_KEY nor the key file exists, Janus starts LOCKED:
    `/health` reports `key_missing`, everything else 503, and it
    never mints a replacement. checkpoint.py refuses likewise.
    restore.py's header documents the backup set as the recovery
    path. *Tested.*
31. **Log before data.** Every data-returning handler appends its
    chain entry *before* the response is flushed (responses are
    captured under the lock and sent after; the appends happen
    inside). If an append raises, the request fails with it.
    *Implemented structurally; not fault-injection tested — see
    "Not live-tested".*
32. **Holds case gate.** /holds runs the shared gate (banned or
    invalid case → 403). /holds/release re-runs it for case-scoped
    holds and chains the result (`case_gate_ok`), but deliberately
    never *blocks* a release on it: a case closing mid-hold must
    not trap held data past its review date. *Placement tested;
    release behavior is as coded here.*
33. **Lock ordering.** The request body is read and parsed *before*
    the global DB lock is taken; handler socket timeout set.
    *Implemented; the ordering also fixed two real deadlocks found
    during the build (below).*
34. **K8 in the report.** `/report` and snapshots include the Tier 3
    emergency share for the period and the trailing 3-month rolling
    share against the pinned 25% threshold (`state: ok|tripped`).
    Open-ended reports anchor the rolling window at now. *Tested.*
35. **Rotation.** `scripts/rotation.py`: deterministic circle-method
    schedule from seed = SHA-256(cycle start + sorted member list);
    base rounds + mirrored half so every member audits every other
    exactly once per cycle with no same-round mutual pairs; odd N's
    bye member is the round's named witness (checkpoint-publication
    duty); active only ≥3 members, static pairing at 2 (stated
    plainly), inactive below; joins/leaves take effect next cycle;
    signed schedule JSON (HMAC) + human-readable table;
    `POST /compact/rotation` recomputes from the seed and rejects
    mismatches (ROTATION_REJECTED chained; valid →
    ROTATION_PUBLISHED); `GET /compact/rotation/status` shows the
    cycle, assignments, filed state, and flags members missing two
    consecutive duties `rotation_delinquent` (flag only). The daily
    /share/query gate is unchanged. COMPACT.md has the rotation
    section. *Tested: N=3/4/5 validity (ordered pairs, no mutuals,
    rotating witnesses), byte-identical seed recompute, tampered
    schedule rejected by the endpoint, N=2 static, N=1 inactive.*

## Demo

`demo/seed_demo.py` + `demo/DEMO-DATA.md` updated for 1.1 and
verified live: 4,453 reads, 9 alerts (1 verified, 1 rejected, 7
pending — 2 in the suppressed queue). Walkthrough steps (a)–(f) were
re-executed against a seeded 1.1 server and the outputs in
DEMO-DATA.md are pasted from that run, including the redesigned (f):
suppressed plates are invisible in search to *every* role, and the
PRT208 hits exist only in the supervisor queue.

## Bugs the build itself found (all fixed, all now covered by tests)

- **Lock-ordering deadlocks** (item 33's hazard, found live):
  chain appends issued while Janus's DB connection held an
  uncommitted write blocked Sentinel's BEGIN IMMEDIATE for the full
  busy-timeout × retry window. Fixed in /search (CASE_FLAG), /reads
  (HOTLIST_EXPIRED), and DELETE /hotlist (HOTLIST_REMOVE) — writes
  now commit before chaining.
- `Chain.root()` returns the hash only; two call sites unpacked a
  tuple (`/audit/root` 500'd, breaking sentinel_audit and
  compact.py until fixed).
- `chain.verify()` returns a dict in 1.1; `/health` and
  `/audit/verify` now report its `ok` field as the boolean.
- Hits were never flagged `suppressed` at ingest (the queue would
  have been empty); the flag is now set at match time, with the
  /hits plate_ref filter kept as belt-and-braces.
- Evidence release-before-export returned 404 "no such hit" instead
  of the no-export refusal; re-export inside one second crashed on
  the bundle directory. Both fixed.
- retention.py's hit purge referenced a `holds.hit_id` column that
  does not exist (holds are scope/ref rows); rewritten to match the
  schema.
- The sink spool write itself could raise when the sink's directory
  was unreachable, violating the sink's never-raise contract; it now
  records the error and lets the chain (the system of record)
  proceed, with /health reporting the failure.
- `/search` briefly renamed 1.0's `why` parameter to
  `justification`; 1.1 accepts `why` (primary) and `justification`
  (alias).

## Interpretations (judgment calls, flagged for round 3)

- **Item 7 (anchor):** implemented as *prefix integrity* — the chain
  must still contain the checkpoint's root at the checkpoint's entry
  count, and must not be shorter than the checkpoint — rather than
  a naive current-root/count equality. A naive comparison flags
  every benign append after the daily checkpoint as a "mismatch,"
  which would train operators to ignore the alarm. A rewritten or
  truncated history trips it; normal appends do not.
- **Item 22 (share tier):** `/share/query` accepts the partner's
  requested tier: tier 2 is windowed exactly as locally; tier 3
  returns the full store, mirroring local Tier 3 scope. The
  partner's own two-key process on their side is what the
  cross-audit vouches for. If the council wants shares capped at
  Tier 2 regardless of the requested tier, that is a one-line
  change — flagged here rather than decided silently.
- **Item 35 (rotation orientation):** with one meeting per
  unordered pair per round set, both audit directions are covered
  across the cycle by mirroring the base rounds with flipped
  orientation (2(S−1) rounds total, S = slots). Every *ordered*
  pair occurs exactly once per cycle, as specified.
- **Item 26 (scrubber):** the plate-like pattern is deliberately
  narrow (normalized uppercase letter/digit shapes). It is a
  defense-in-depth net under the coded-payload rule, not a
  substitute for it.

## Not live-tested (implemented, code-reviewed)

- **Item 15 fail-closed:** the >24h stale-config 503 gate on
  /search and Tier 3 is implemented (`config_status().fail_closed`)
  but exercising it live requires a config stale for 24 hours;
  staleness onset and recovery *are* live-tested.
- **Item 31 fault injection:** log-before-data is structural
  (append precedes flush on every data path); the suite does not
  inject a chain failure mid-request to watch the request fail.

## Flagged legal question — NOT a code change

Both Claude council seats and ChatGPT independently cited **Act 668
of 2025**, described as amending Ark. Code §§ 12-12-1802–1805 and
1807 (a 60-day retention cap for private/commercial users; Attorney
General enforcement). This is recorded here as a question for the
City Attorney lane. **No retention logic was altered over it** —
1.1 keeps the 14-day Cabot proposal default exactly as 1.0 did.

## Files

- `janus11/janus.py` (2,829 lines), `janus11/sentinel.py` (317)
- `janus11/scripts/`: retention, checkpoint, provision, backup,
  restore, alert_check, frigate_bridge (updated); **new:**
  sentinel_audit.py, compact.py, rotation.py
- `janus11/COMPACT.md` (new), `janus11/demo/` (updated)
- `janus11/tests/run_tests.py` — 184 checks, all passing
- `janus/` (1.0) untouched.
