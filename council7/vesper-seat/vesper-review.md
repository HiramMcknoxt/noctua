# NOCTUA Council Round 7 — Cold Vesper Seat Review of 1.2.3

Seat: Vesper (cold seat — independent reviewer; not the builder,
not the orchestrator). Model: Muse (Muse Wonder session,
subagent), effort as shown in this session's interface.
Build under review: `~/workspace/noctua-1.0/janus123/`, against
fail-before tree `~/workspace/noctua-1.0/janus122/`.
Commission: council6/SYNTHESIS.md (R1–R16 + Qwen residuals +
imperator). All findings below are EXECUTED unless explicitly
marked code-read only. Probe code: `vesper-seat/probes/`.

## Findings so far (review in progress)

### F1 [CODE-CRITICAL] — Direct 1.0 → 1.2.3 upgrade: migration never completes
Reproduced end-to-end (probe_orders_o2b.py): booted the REAL 1.0
tree (`~/workspace/noctua-1.0/janus/`), placed three suppressions,
then upgraded the same directory to 1.2.3 (via the pin ceremony —
see "what held" below). On every 1.2.3 boot,
`_deferred_data_migrations` fails and migration_status stays
`"incomplete"` with defect `{"unit": "deferred_data_migrations",
"error": "OperationalError"}`; /health `ok` is false permanently.

Root cause, isolated by replaying the unit's statements against
the 1.0 database: the hotlist move (janus.py, in
`_deferred_data_migrations`, ~line 902) SELECTs `list_name` from
the legacy `hotlist` table. A genuine 1.0 table has `source`, not
`list_name` (janus/janus.py:184-186) — `no such column: list_name`.
1.1's schema evolution adds `list_name` (fixtures/janus11/
janus.py:413), so the stepped path 1.0 → 1.1 → 1.2.3 heals; the
direct path does not, because 1.2.3's own column-evolution list
never touches the legacy `hotlist` table. Consequences: the unit's
earlier statements are rolled back with it, the failure recurs on
every boot, and a populated 1.0 hot list would never reach
`hotlist_members` — the upgraded system would run with an empty
hot list while reporting only an unexplained "incomplete".

Aggravating: the chained MIGRATION_DEFECT and /health carry only
the exception TYPE (`OperationalError`), not the message
(janus.py `_mig_unit` / the deferred-unit catch record
`type(exc).__name__` only). The one fact an operator needs —
which column — is nowhere in the audit record; I recovered it by
replaying statements by hand.

Why the battery missed it: the acceptance fixtures cover 1.1 and
1.2 only (tests/fixtures/{janus11,janus12}); no janus10 fixture
exists. R2's "PASS" is narrower than its claim — the commission's
acceptance standard names real-tree upgrades from 1.0.

### F2 [MINOR, contract] — Chain sink/participation contract is safe only under an external discipline it neither enforces nor documents
Executed at the Chain level (probe_sink.py):
- S2 (Qwen's append-race, raw): two appends share one
  legacy-isolation connection (janus.py:724's exact parameters)
  with no external lock. Request A holds a transaction open;
  request B's append() sees `db.in_transaction` and participates
  in A's transaction; A rolls back; **B's append — which returned
  a full entry dict — exists nowhere** (chain 0 rows, sink 0
  lines). flush_deferred's presence check silently drops it.
- S2b: the identical actors under janus's actual discipline (one
  lock serializing work + append + commit/rollback + flush,
  mirroring do_POST/do_GET) — B's entry lands in chain and sink.
  So in the SERVER's wiring the shape is fenced: every append and
  every transaction-state change in janus.py runs under DBLOCK,
  and the server has no background threads. The Qwen shape is
  therefore **structurally impossible in current server wiring,
  but live in the Chain API** — sentinel.py presents Chain as the
  threaded server's chain (its constructor comment cites the
  threaded HTTP server) without stating the precondition that a
  caller must serialize transaction-state changes externally.
  Any future consumer (the commissioned UI track serves from
  janus.py itself, but scripts and any second process do not
  inherit DBLOCK) can lose acknowledged writes silently.
- S3 (crash window): an entry committed inside a caller
  transaction whose process dies before flush_deferred NEVER
  reaches the sink, and a restarted Chain does not reconcile —
  the persisted watermark machinery exists but is never used to
  backfill. In server wiring, flush runs inside DBLOCK before
  the response, so an acknowledged request is flushed; the hole
  is, again, in the library contract, not the current server.
- S4 (scrub-flag leak): on a legacy-isolation connection with no
  transaction open, appending a scrub-flagged payload leaves the
  connection `in_transaction == True` afterwards:
  `_scrub_flag_due` (sentinel.py ~1771) INSERTs into scrub_state
  on the shared connection, opening a transaction append() never
  commits; the CHAIN_SCRUB_FLAG entry is invisible to other
  readers until an external commit, and the NEXT innocent append
  is captured by the leaked transaction (deferred instead of
  streamed). Janus's request-tail commit masks this in-request;
  boot-path appends have no such tail. Demonstrated end-to-end
  at Chain level; in-server reachability requires a flagged
  payload on a no-open-transaction append (BLOCKED/AUTH_FAIL
  payloads are not plate-shaped; free-text fields are the
  plausible route) — reachability code-read, leak executed.

### What held (executed)
- Protection orders as records, native (probe O1): duplicate
  placement of the same order_ref is idempotent (201, one row);
  a second order under variant spellings ("two 222") lands as
  its own record on the canonical vehicle; release-by-plate-only
  with two live orders is refused (400) and lifts nothing;
  per-order two-key release lifts only the named order (verify
  403 → 403 → 200 across the two releases). R1 holds.
- Mixed migration (probe O3): a 1.1-migrated order and a native
  1.2.3 order placed under a variant spelling coexist; releasing
  the migrated one leaves the native one protecting. R1/R2 hold
  on the 1.1 path.
- The 1.0 key gate (probe O2b): booting 1.2.3 over a genuine 1.0
  database whose chain holds nothing checkable refuses (exit 3)
  and names the pin ceremony; the ceremony with the correct key
  pins by fingerprint (checked=0 → "ceremony") and the next boot
  proceeds and chains KEY_PINNED. R3's remedy works on this path.
- 1.0 suppression preservation (probe O2b): all three plate-less
  1.0 orders survive as records with synthesized LEGACY-<n>
  order refs, active=1, counted unverifiable (3) rather than
  silently voided — the F2c defect does not recur. Suppression
  engages by ref at query time (a detective's hotlist add for
  the protected vehicle was refused 403 SUPPRESSION_CONFLICT
  with the non-oracle message).
- Sink-down drain (probe S5): five appends with the sink path
  blocked spool; on restoration the next append drains them to
  the sink in chain order, parity exact. R5's spool path holds.
- One correction to my own probe: my first O2 construction
  (two spelling-variant orders placed via the 1.1 API) collapsed
  in 1.1 itself — 1.1 normalizes before keying and its
  ON CONFLICT upsert overwrites, so only one order ever existed
  in the source table; migration preserved the one record that
  existed. No finding against 1.2.3 there; the loss is 1.1's and
  is unrecoverable in principle (1.1's chain never recorded the
  overwritten order_ref either).

### F3 [CODE-CRITICAL] — The imperator guard is boot-only, string-typed, and name-bound
The commissioned guard (janus.py `_imperator_guard`, ~line 1670)
runs exactly once, at module level after the first
`_reload_config()`. Executed shapes (probe_imperator.py):
- I1 (what the builders' suite tests): a bare users list with
  imperator refuses the boot, exit 3, clear message. Holds.
- I2 (NOT covered by the suite): boot on a clean production
  users file, then edit users.json to add imperator (still a
  bare, non-demo list). The next request's reload swaps USERS
  via `_apply_config` — which never calls the guard — and
  **imperator authenticated and read /health (200) in the
  running production install**. The account stays live until
  the next restart, which the same edit then bricks (the boot
  guard fires). The reload path is the supported way accounts
  change without a restart (provision.py's whole premise), so
  the guard's one unchecked door is the main door.
- I3: the demo flag is `bool(data.get("demo"))`
  (_apply_config). A users file carrying `"demo": "false"`
  (string) is truthy in Python — imperator booted under it
  with no refusal. The flag that licenses a god account is
  not parsed as a boolean.
- Context (I4, by design, not a defect): multi-role `roles`
  lists are a general config feature — an all-roles account
  named "boss" boots in production, files Tier 3 requests,
  and is refused self-approval (403, two-key by identity).
  So the guard binds a NAME, not the capability; its real
  function is a tripwire against demo-config carryover, and
  I2/I3 are exactly carryover-shaped holes in it. USERS_DEMO
  is consumed nowhere else — a production server running a
  demo-flagged users file is indistinguishable in /health
  from a production one.
Why critical and not blocking: reaching any of these shapes
requires write access to users.json, and the two-key rule
still binds the account once live. But the commission's own
acceptance claim — "non-demo config containing imperator →
refusal" — is false for the runtime state, and the fix is
small (run the guard inside _apply_config / the reload flush;
parse the flag strictly).

### F4 [MINOR] — The key-refusal remedy does not mention the env var that defeats it
Executed (probe_pin.py K3/K4): booting 1.2.3 over an existing
chain with a WRONG NOCTUA_AUDIT_KEY refuses (exit 3) and names
two remedies — write the key to `<db>.audit_key` and restart,
or run pin-audit-key. Following the first remedy literally,
with the wrong env var still set, refuses again (exit 3):
`_audit_key()` (janus.py ~441) resolves env BEFORE file. Only
removing the env var lets the key-file boot proceed (verified:
boots, /health 200). R3's standard was "the boot-refusal
message names a remedy that actually works" — as written, an
operator with a typo'd env key loops forever on remedy #1.
One sentence in the message ("unset NOCTUA_AUDIT_KEY — it
takes precedence over the key file") closes it.

### What held, continued (executed)
- Pin ceremony on the brief's exact shape (probe_pin.py):
  a real 1.1 database whose only keyed refs are Tier 3
  fragments (one /tier3/request, zero suppressions) — wrong
  key refused ("verifies 0 of 1 stored keyed references");
  correct key pins with method `verified:1` via
  sentinel.frag_ref. Verify-don't-proxy finds fragment-only
  keys. R3 holds.
- Rotation ceremony (probe_rotation.py, probe_rotation_t4.py):
  replayed reveal 409; supervisor transport signed with a
  FOREIGN Ed25519 key 403, the same transport signed with the
  registered key 201; reveal-time grind (nonce mismatching
  the commitment) 400 and chained; a 15-char nonce's reveal
  400 (floor enforced) and the stranded cycle still
  cancellable; the two-key cancel is real — after a
  supervisor's cancel REQUEST, a member's reveal still lands
  (201, cycle alive); only the auditor's confirm clears the
  contributions (subsequent reveal 409). Re-committing an
  open cycle with identical parameters is an idempotent 201,
  not a reset (my first reading of two 201s as defeats was a
  probe artifact; the decisive variant settles it). R6 holds.
- R12 fence (probe_fence.py B1): with the case feed 72h stale
  (file fresh), ingest and protection-order placement land
  (201) with CONFIG_FEED_STALE_WRITE chained; data reads and
  /verify refuse 503 with a message naming the feed and its
  age ("the case-list feed is stale (age 72.0h, limit 48.0h)").
  The file leg is code-verified (config_safety_closed routes
  file-staleness to config_closed()). One correction to my
  own probe design: a merely OLD file is not "stale" in this
  design — file-staleness means reloads failing >24h, and the
  stopped-export scenario is the feed leg's job. Coherent.

## Judgment calls
(a) **R6 witness rule — SOUND, with one divergence noted.**
    Filing-time and status-time designation use the identical
    computation (janus.py ~4954 and ~5696): members minus
    {auditor, audited}; exactly one other → that member (the
    n=3 bye); otherwise the round's auditor. At n=2 there is
    no third party in existence, and the alternative
    (witness duty unsatisfiable) would strand every two-member
    compact in permanent delinquency — the rule as built does
    NOT strand small compacts; it guarantees a satisfiable
    duty. Divergence from the brief's phrasing: at n≥4 the
    "others" are plural, so designation collapses to the
    auditor for every round — witness independence quietly
    disappears at exactly the scale where a true third party
    exists. Attestations remain attributable signed statements
    on the chain, so this is a weakening, not a hole. Accept
    for convergence; record for 1.2.4 (designate one of the
    others deterministically at n≥4, or document the rule as
    built).
(b) **R12 fence — ACCEPT the line.** Executed above. The
    writes that proceed are the ones whose refusal destroys
    value irreversibly (an unrecorded read, an unplaced court
    order); everything that discloses waits for fresh
    validation data; the exception is chained and throttled,
    and the refusal names the actual stale input. "Stale
    means stopped" would trade a bounded, on-the-record risk
    for certain loss of safety writes.
(c) **Qwen restore atomicity — NARROW the claim; do not gate
    convergence on a fail-injection test.** Code-read
    (scripts/restore.py): Qwen is right that validation
    (manifest hashes, the set's chain verify, tarball
    data-filter) all completes before any live file moves,
    and right that the swap itself is not atomic — the live
    set is moved aside by os.replace, then the new set is
    installed by shutil.copyfile, file by file, no fsync
    (lines ~332-360). A mid-swap I/O failure leaves a mixed
    set and a traceback, not a refuse(). But the consequence
    is bounded in ways the claim omits: the pre-restore
    copies are preserved (this run's copies are explicitly
    never pruned), the post-restore verify_detached gates
    success, and a restore runs against a system that is by
    definition already down. This seat did NOT inject a
    mid-swap fault; the narrowing rests on the code and on
    the executed R10 evidence that the trust root holds.
    Recorded as a 1.2.4 hardening item (copy-to-temp +
    os.replace + fsync per file; a refuse-path that reports
    the mixed state), not a 1.2.3 blocker.

## Still open at this writing
Criterion-4 spot re-runs by this seat: builders' suite
re-run complete (332/332, exit 0 — the orchestrator's number
is accurate, and the suite's imperator cases are boot-shape
only, consistent with F3 being outside its coverage);
Q battery + invariants re-run in progress.

---
## Orchestrator's completion note (Vesper, Nov 24, 2026)
This seat ended after banking the review above and a current
HANDOFF.md, before writing its formal verdict block. Its
HANDOFF records, in its own words: "Verdict direction: NOT
CONVERGED; forced change = F1 fix + a janus10 fixture in the
acceptance battery." Its builders'-suite re-run (332/332, exit 0)
independently confirms the orchestrator's criterion-4 numbers;
its Q battery re-run was in progress and is not needed — the
orchestrator's cold battery stands as the criterion-4 evidence.
The seat's probes are preserved in vesper-seat/probes/.
