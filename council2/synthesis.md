# NOCTUA Council — Round 2 Synthesis (NOCTUA 1.0)

**Seats:** ChatGPT (user's browser), Gemini (user's browser), Claude (cloud),
Claude (user's browser). All four read the actual 1.0 code from the public
repo (janus.py 1,134 lines, sentinel.py, INTEGRATION.md, CANT-DO.md,
NETWORK.md) and proved it (line counts, named handlers). Reviews archived
with the round-2 working files; this synthesis is the durable record.

**Unanimous verdict:** the architecture is right and the implementation is
not deployable. Every control in 1.0 had a cheaper path around it — "one
door with five unlocked windows" (Claude, user's browser). No seat approved
operational use; all four approved continuing the gated pilot path.

**Orchestrator verification:** every load-bearing claim below was checked
against the 1.0 code by Vesper before entering the fix list (grep/line
inspection). One reviewer claim was discounted (Gemini: "reads has no
cam_ts" — the column exists via migration; Gemini's fetch truncated at
~line 266 and it said so honestly).

## Convergent findings (≥2 seats, code-confirmed)

1. **Tier 2 is unbounded.** run_search() has no temporal predicate; Tier 2
   and Tier 3 run identical SQL over the whole 14-day store. tier values
   other than 3 execute; wildcards/empty fragments return the 200 newest
   reads. The tier wall is workflow-deep, not data-deep. (All 4 seats.)
2. **Unlogged data paths.** GET /hits and GET /hotlist have no role check
   and write no chain entry — any authenticated account reads every hit
   and the full hot list. Failed logins unlogged. The docstring claim
   "every allowed and blocked action is logged" is false. (Both Claudes,
   ChatGPT.)
3. **QUERY entries don't record what was searched** — no plate_ref, no
   result count (Tier 3 entries do; Tier 2 don't). The outside auditor
   cannot sample searches against case files. (Both Claudes, ChatGPT.)
4. **Suppression is an oracle and a sieve.** Stub rows leak existence,
   count, and rough timing to every role; supervisors see full records;
   suppression is enforced only in run_search — not at hot-list add,
   ingest, or /hits — so a protected plate can be hot-listed and every
   pass becomes a readable alert. (§ 12-12-1808(b); both Claudes,
   ChatGPT on the supervisor-exception reading.)
5. **Evidence export is a permanent bypass.** No hit-status check, case
   need not be the hit's, exports copy the plate's full 14-day history,
   bundles are never deleted, release doesn't require an export, custody
   excerpts truncate silently at the newest 100k chain entries.
   (Both Claudes.)
6. **Chain integrity is weaker than claimed.** Chain.append is not
   atomic across processes (root-read → insert, no BEGIN IMMEDIATE) —
   the retention process can fork it. The sink latch never recovers and
   drops entries silently. verify() has no sequence-gap check and no
   outside anchor, so a restore rolls the chain back invisibly.
   (Gemini, both Claudes, ChatGPT.)
7. **Health lies by omission.** Heartbeats check age only — a job
   reporting ok:false stays green; /health returned ok:true while
   degraded; sink failure never degrades; the bridge's account both
   ingests and posts heartbeats (and could search). (All 4 seats.)
8. **§ 1805 report defects.** False-match count read from the hits table
   (retention deletes it — the v0.9 bug recurring); per-list breakdown
   missing for most categories; zero-hit lists vanish; local list names
   embed case numbers that would print in a public report; prosecutions
   conflate "not reported" with zero; no frozen 18-month compilation;
   the K8 emergency share is never computed. (Both Claudes, ChatGPT.)
9. **§ 1804(b) has two exits; the code implements one.** Prosecutor
   sign-off covers clause (2); clause (1) — investigation ends without
   charges — has no path. Holds never expire. (Both Claudes, Gemini.)
10. **Hot-list hygiene.** expires_ts stored but never checked at match
    time (expired entries alert forever); no freshness tracking against
    § 1804(c)'s 24-hour update duty; banned-pattern checks only in
    case_gate's original callers. (Both Claudes, Gemini.)
11. **Ingest trusts too much.** Any camera name accepted ("no new
    cameras without a vote" unenforced); state defaults "AR", confidence
    defaults 0.95 (a fabricated confidence can enter evidence); no
    dedupe; plate_ref keyed without state. (ChatGPT, Claude cloud.)
12. **Doc-vs-code drift.** janus.py binds 0.0.0.0 while NETWORK.md says
    localhost; NETWORK's central-vs-edge Frigate descriptions carry
    incompatible bandwidth math (~630 GB/mo continuous vs 25 GB LTE);
    RETENTION_DAYS/HOLD_DAYS documented but never read; INTEGRATION
    decisions 3, 6, 7 not implemented as written. (ChatGPT, both
    Claudes.)

## Seat-specific findings (code-confirmed unless noted)

- **Gemini:** no WAL mode and no secondary indexes (LIKE '%frag%' full
  scans over ~622k rows under a global lock); auth compares hashes with
  `!=`, not hmac.compare_digest; the system role can spoof healthy
  heartbeats; audit-key file has a TOCTOU permission race; plate keyspace
  is small enough that a leaked HMAC key reverses every plate_ref;
  forced change: split storage by retention class + transactional chain
  appends + a 1,000-write concurrency stress test.
- **ChatGPT:** _reload_config silently keeps last-good config forever
  (closed cases stay open; no staleness bound); /verify doesn't re-check
  hot-list currency despite INTEGRATION #6; evidence release doesn't
  authenticate the prosecutor; forced change: fail-closed authorization
  at the data-access boundary + independent certification of the exact
  production release before any live plate data.
- **Claude (cloud):** Tier 3 results go to the approver; the requester
  has no retrieval endpoint, so the handoff happens off-system; approve
  doesn't re-validate the case; emergency requires no auth_basis and is
  unlimited; suppression format mismatch ("VIC 999" vs "VIC999") fails
  silently; suppression requires a criminal case, so a civil protection
  order can't be entered; CLOCK_SKEW fires on backfill latency
  (~14,800 false entries for one 3-day outage); free-text fields can
  carry plate text into the permanent chain.
- **Claude (user's browser):** one stalled connection freezes the whole
  service (global lock taken before body read, no timeout); "Confirm"
  with a capital C records a hit as REJECTED; non-numeric tier crashes
  the request; a lost audit-key file makes _audit_key() silently mint a
  new key — every suppression stops matching, nobody is warned;
  /tier3/pending shows every detective every request's fragment and
  warrant basis; emergency reviews close on any non-empty finding
  ("ok" works).

## Legal questions the loop will NOT decide (routed to the City Attorney)

- **Act 668 of 2025** — cited independently by three seats as amending
  §§ 12-12-1802–1805 and 1807 (60-day cap for private/commercial users;
  Attorney General enforcement under the DTPA). Verify against the
  enrolled bill; if correct, CANT-DO and the policy draft need the new
  exposure lines.
- **§ 12-12-1808(b)** — whether any supervisor exception exists to
  protection-order suppression. Interim code position (1.1): no
  supervisor view; disclosure through the match workflow only.
- **Derived data** — whether keyed plate_refs in the audit chain are
  "derived" captured plate data under § 1802 (Gemini's key-reversal
  point sharpens this).

## Forced-change dispositions

- **ChatGPT (fail-closed data-access boundary + independent
  certification):** ACCEPTED in substance — 1.1 puts the gates in the
  query path itself (temporal wall in SQL, suppression exclusion in the
  shaping layer for every role, log-before-data). Independent
  certification remains a pre-deployment condition in the spec; the
  council loop is not a substitute for it.
- **Gemini (storage split by retention class):** ANSWERED IN WRITING —
  the design's answer stands: reads/outcomes/derived tables share one
  database, but retention classes are enforced by the purge rules per
  table (reads 14d; derived text 14d; outcomes + snapshots plate-free
  and preserved; bundles under their own custody ledger), and the
  witness/checkpoint layer — not file separation — is what makes a
  restore detectable. The transactional-append and stress-test parts
  are ACCEPTED and implemented (200-append two-process test in the
  suite; the 1,000-write version runs in Round 3 verification).
- **Claude cloud (single gated path for every plate-data route):**
  ACCEPTED — implemented as items 1–5, 9, 23, 31 of the 1.1 brief.
- **Claude browser (same condition, plus adversarial suite that fails
  on 1.0 and passes on the fix):** ACCEPTED — the 1.1 suite is built
  exactly that way (184 checks; each round-2 attack is a named test).

## Outcome

35 fix items (22 + 9 fourth-seat + Compact 21/22 + rotation 35, with
additions through item 35) went into the NOCTUA 1.1 build, including the
new Compact work (audit tool, reciprocal cross-audit sharing gate,
deterministic audit rotation). Build result: **184/184 live checks
passed**, independently re-run by Vesper from scratch with the same
result. Round 3 reviews 1.1 — this time including the scripts
(retention, backup, restore, bridge) that round 2 never saw.
