# NOCTUA Council — Round 6: Vesper Seat Review of NOCTUA 1.2.2

**Seat:** Vesper (cold-context instance). I am a fresh Muse Spark
instance with NO prior involvement in this codebase; everything
below comes from the files in `janus122/` and the round-5 record,
plus code I executed myself during this review. My harness does
not expose an effort-level setting to state; the review is
execution-based throughout — every load-bearing claim below is
either a run I made or a file:line citation.

**Tree reviewed:** `~/workspace/noctua-1.0/janus122/` (janus.py
5,817 lines, sentinel.py 1,567 lines, scripts/, tests/).
Comparison trees janus/, janus11/, janus12/, janus121/ were read
but not modified. No janus tree was modified by this review; my
probes live in `council6/probes/`.

## Test legs — run by me, on this machine

| Leg | My result |
|---|---|
| Builders' suite (`tests/run_tests.py`) | **322/322 passed, 0 failed** (log: `council6/probes/builders-run.log`) |
| Round-4 attacks (`tests/attacks/run_round4.py`) | **PASS** — 41 verdicts, only the A9b contrast control CONFIRMED, no unexpected CONFIRMED |
| Round-5 seat-1 attacks (`tests/attacks/run_round5.py`, incl. re-aimed A18) | **PASS** — 21 verdicts, 0 REPRODUCED |
| Q battery + 6 invariants (`tests/run_q122_cases.py janus122 --invariants`) | First run: 34/35 (INV5 failed — see F5; that run overlapped my own probe servers on nearby ports, disclosed for completeness). **Clean re-run, nothing else executing: 35/35 PASS** (log: `council6/probes/qbattery-run2.log`) |

The orchestrator's entering numbers are accurate. They are also
not the whole story: three of my four findings below live in code
paths the suites exercise only in unrepresentative shapes, and
the fourth in a shape the brief itself flagged as vacuous.

## Q1–Q28 verdicts

Evidence key: [run] = my execution of the case/suite; [read] = my
own reading of the 1.2.2 code; [probe] = my own adversarial probe.

| Item | Verdict | Basis |
|---|---|---|
| Q1 migration repair | **FIXED** | [probe] M-A: real janus11 DB (suppression + covered hit) upgraded live — suppression re-keyed, hit queued not leaked, MIGRATION entry chained with per-store counts, no unrepaired marker. INV3 + Q01 [run]. One latent fragility: F6. |
| Q2 locked-boot ordering | **FIXED-BUT-WRONG** | [probe] F3: the module-level receipts dedupe deletes data on every boot — locked boots included — with no chain entry. Q02's case covers the _migrate_122 path only. |
| Q3 pin ceremony | **FIXED-BUT-WRONG** | [probe] F2: `provision.py pin-audit-key` crashes on every real database, and its legacy-formula candidate can never match a real 1.1 ref. The boot-time auto-verify (janus.py `_verify_key_against_stored_refs`) uses the correct formula and is genuinely fixed; the shipped ceremony tool is not. |
| Q4 expiry is a parsed instant | **FIXED** | [read] `sentinel.parse_expiry` (bare date = end-of-day UTC), door validation at janus.py:2691, migration canonicalize-or-deactivate at janus.py:918. Q04 + INV1 [run]. |
| Q5 one supersede decision | **FIXED** | INV2 [run]: best-read alert survives 8/8 orderings, returned ids resolve 8/8. Append-only read versions sighted (janus.py:2502ff). Q05 [run]. |
| Q6 one retention function | **FIXED** | [read] retention.py:334-368 — Chain rides the purge connection from the start; purge + RETENTION_PURGE + one `db.commit()`; registry-driven store iteration. Q06 + INV4 [run]. |
| Q7 evidence lifecycle | **FIXED** | Q07 [run] FAIL→PASS (post-purge release/disposition/destroy all work); re-export resets release/disposition state in the export UPSERT (janus.py:3695ff, sighted); INV4 [run]. |
| Q8 registry completeness | **FIXED** | Q08 [run] FAIL→PASS — ordinary sharing no longer leaves a permanent false breach. |
| Q9 config_closed at dispatch | **FIXED** | [read] dispatch-level checks in do_POST/do_GET/do_DELETE and per-route (janus.py:2269, 2368, 4777, 5030, 5207ff); /report/compile fenced. Q09 [run]. |
| Q10 expand requires Tier 3 | **FIXED** | [read] `_tier3_covers` (janus.py:1894) — expand borrows an EXECUTED/EMERGENCY/REVIEWED Tier 3 for the same case+plate; reason hashed into the chain entry. Q10 [run]. |
| Q11 Tier 3 instruments are config | **FIXED** | Q11 + INV6 [run]; accepted set is in the SYSTEM chain entry (janus.py:5804). |
| Q12 holds validated | **FIXED** | Q12 [run]; `_strict_id` (janus.py:1456) sighted. |
| Q13 auditor review independent | **FIXED** | Q13 [run]: auditor sees basis fields; auditor review after a supervisor's returns 200, not 409. |
| Q14 case-feed freshness | **FIXED** | Q14 [run]: stale feed → search 503, staleness named in /health; `cases_feed_stale` (janus.py:542) sighted. |
| Q15 AUTH_FAIL throttle | **FIXED** | [read] janus.py:1379-1425 — flushed markers moved to their own set (`_auth_fail_flushed`); the prune compares only (user, bucket) keys. Q15 [run] reproduces the 121 500 and its absence on 122. |
| Q16 flush_deferred | **FIXED-BUT-WRONG** | [probe] F4: the separate-connection presence check cannot distinguish a rolled-back entry from an identical committed twin (same reused seq, same hash). Shape B (sink-down burst) and the distinct-payload control are clean. |
| Q17 v1 cross-check | **FIXED** | [read] sentinel.py:1101-1146 — `_verify_rows` cross-checks v1 payload kind/ts against the columns and now also refuses a chain that does not start at seq 1. Q17 [run]. |
| Q18 authenticate before computing | **FIXED** | [read] do_GET (janus.py:5091-5112) — side-effect-free `auth()` first, cache warmed outside DBLOCK, single-flight `chain_ok_cached` (janus.py:1927). Re-aimed A18 in the round-5 wrapper: not reproduced [run]. The Q18 *case* is weak-shaped, as the report admits; the property itself verifies. |
| Q19 scrubber exemptions | **FIXED** | [read] `_scrub_exempt_check` (janus.py:821) value-verifies cam/agency/members against the camera registry, the partners table, and the home agency. Q19 [run]. |
| Q20 envelope collision | **FIXED** | [read] sentinel.py:1443-1446 — `_insert_locked` strips caller `v`/`ts`/`kind`. Q20 [run]. (Ruling on strip-vs-raise under (c).) |
| Q21 gate follows audit time | **FIXED** | [read] janus.py:4030-4108 — duplicate report_hash refused (409), report older than the newest on file refused (409), freshness read from the report's own ts. Q21 [run]; INV5 gate half [run]. |
| Q22 compact checkpoint age | **FIXED** | Q22 [run]: a 4,800-hour-old checkpoint fails every check (`checkpoint_fresh: false`, gate closed). Caveat under (a): the case also passes on 121 in its current shape. |
| Q23 ungrindable rotation | **FIXED-BUT-WRONG** | [probe] F1: the commit-reveal ceremony has no phase barrier — a commitment can be replaced, or first filed, AFTER other members have revealed, and the publisher accepts the ground schedule. Reproduced end-to-end through the public API, twice. |
| Q24 witness standing | **FIXED** | [read] janus.py:4336-4427 — supervisor attests for the home agency only; partner filings need the registered Ed25519 signature over the attestation; cycle must exist and the agency must be a member. Q24 [run]. One residual: F8. |
| Q25 backup/restore verified + atomic | **FIXED** | [read] backup.py:150-159 verifies the chain before signing and refuses a broken one. Q25 [run] (atomicity half); round-4 A7 (trust-root half) NOT REPRODUCED under my own re-run. Ruling under (b). |
| Q26 config reload robustness | **FIXED** | [read] janus.py:514 — the reload catch now includes TypeError/KeyError. Q26 [run]: bad-shaped config → ingest 201s, /health 200, no 500 loop. |
| Q27 fragments / aged Tier 3 / misc | **FIXED** | Q27 [run]: aged request expires (approve → 409, executed: false), garbage snapshot param → 400. Retention-side EXPIRED transition sighted (retention.py:355). |
| Q28 packaging | **FIXED** | Everything runs green from the tree layout — I ran all four legs from `janus122/` with in-tree fixtures; wrappers print a verdict per scenario (silence = failure). Two test-quality defects ride along: F2's fixture gap and F5. |

**Tally: 24 FIXED, 4 FIXED-BUT-WRONG (Q2, Q3, Q16, Q23), 0 NOT
FIXED, 0 UNVERIFIED.**

## New findings

### F1 — [CODE-CRITICAL] Rotation commit-reveal has no phase barrier: the last mover chooses the pairing (Q23)

`_rotation_contribution` (janus.py:4582) accepts a commitment
filing at any time while a cycle is open, and its UPSERT
(janus.py:4624-4631) **overwrites** an existing `nonce_hash`
unconditionally — the `WHERE nonce IS NULL` guard exists only in
the commit endpoint's upsert (janus.py:4558-4565), not here.
Nothing at publish checks that commitments preceded reveals.

Reproduction (`council6/probes/probe_rotation.py`, live server,
members THIS-AGENCY / agency-a / agency-b):

- **R1 (replacement):** all three commit hashes; home and agency-a
  reveal; agency-b's commitment is then REPLACED via
  `/compact/rotation/contribute` → **HTTP 201 "commitment
  recorded"**. The replacement nonce was ground offline against
  the two revealed nonces. Reveal → 201; publish → 201;
  **published schedule == the attacker's ground target, ≠ the
  honest schedule.**
- **R2 (late first commit):** agency-b never commits up front;
  after the other two reveal, agency-b files its FIRST commitment
  (ground) → 201, reveals, publishes → **published schedule ==
  ground target.**

The battery's ceremony helper commits every hash up front and
reveals in order, so no shipped test ever interleaves the phases.
Invariant 5 of the acceptance standard — "the rotation publisher
cannot predict the pair" — fails in substance: any member (or a
supervisor transporting for one, see (c)(3)) can *bias* the pair
after seeing the other nonces. This is the second consecutive
round in which the rotation seed fell to a grinding variant
(1.2.1: cycle_start/root grind; 1.2.2: last-mover grind).

### F2 — [CODE-CRITICAL] `provision.py pin-audit-key` — the Q3 ceremony — crashes on every real database, and its legacy check is arithmetically wrong

Two independent defects in `scripts/provision.py`:

1. **Crash (reproduced).** Line 219 queries
   `SELECT DISTINCT fragment FROM case_searches` — the column is
   named `frag` in every tree's schema (janus122/janus.py:619).
   Against a real Janus database (built by booting janus122,
   running a search and placing a suppression, then stripping the
   pin to simulate the unpinned upgrade state), with the CORRECT
   key and fingerprint:
   `sqlite3.OperationalError: no such column: fragment`,
   traceback, exit 1. The command the KEY_LOCKED refusal message
   names as the remediation cannot complete against any database
   Janus itself wrote. The builders' suite missed it because its
   only pin-audit-key scenario (run_tests.py:2562) uses a
   hand-built database containing ONLY an `audit` table — no
   `tier3_requests`, so the block containing the bad query is
   skipped and the ceremony "passes" with checked=0.
2. **Wrong legacy formula (proven arithmetically).** Line
   198-199 computes the 1.1 candidate as
   `HMAC(key, "PLATE|" + (state or ""))` — the literal string
   "PLATE|", state not uppercased. The real 1.1 formula
   (janus11/janus.py:214-219) is `HMAC(key, "{PLATE}|{STATE}")`
   over the plate value, both uppercased. For key
   `test-audit-key-…` and plate VIC309/AR: real ref
   `pref:cc6c7f2e920ab2b0ff7eaeda` vs provision.py candidate
   `pref:090d1e263a05574f3126b91e` — never equal. So even with the
   crash fixed, the ceremony refuses the CORRECT key
   ("verifies 0 of N") for exactly the databases Q3 was built
   for — 1.1 upgrades whose checkable evidence is suppression
   refs. Janus's own boot-time verifier (janus.py:1094-1099)
   implements the formula correctly; the tool does not.

### F3 — [CODE-CRITICAL] A data DELETE runs at import on every boot — locked boots included — with no chain entry (Q2)

janus.py:797-806 (module level): duplicate `compact_receipts`
rows are deleted and a unique index created **at import time** —
before `_key_fingerprint_check()` (~janus.py:1195) and before
`_migrate_122()` (janus.py:1356). Q2's contract is that data
repairs wait for the first unlocked boot and are chained there;
this one is neither.

Reproduction (`council6/probes/probe_migration.py`, M-B; a real
janus121 database seeded with 3 duplicate receipts):

- **Unlocked 1.2.2 boot:** receipts 3 → 1; audit grew 4 → 8
  (boot entries) but **zero MIGRATION entries** — the deletion is
  recorded nowhere.
- **Locked boot (wrong env key):** the process correctly refuses
  to start (exit 3) — and the receipts STILL went 3 → 1, audit
  count unchanged (4 → 4). A boot that refuses to serve has
  already rewritten records, unchained.

Duplicates are admittedly near-inert semantically (the dedupe
keeps the first filing; DeepSeek N5 motivated it). The defect is
the contract breach: on a system whose entire claim is "nothing
is deleted unchained," a boot-time path deletes rows silently —
the same class Qwen F10 flagged in round 5 and Q2 was
commissioned to close.

### F4 — [CODE-CRITICAL] flush_deferred's presence check cannot tell a rolled-back entry from its committed twin (Q16)

`Chain.flush_deferred` (sentinel.py:1363-1406) presence-checks
each deferred entry on a read-only connection by `(seq, hash)`.
But `audit.seq` is AUTOINCREMENT — a rollback restores
`sqlite_sequence`, so the seq is REUSED — and `now_iso()`
(sentinel.py:141-143) has one-second resolution, so an identical
re-append in the same second produces the identical payload and
therefore the identical hash.

Reproduction (`council6/probes/probe_q16.py`, shape A,
deterministic): append `PROBE {marker: twin}` inside a
transaction → rollback → append the identical entry (commits,
seq 2, hash 925c7e27…) → `flush_deferred()`. The chain holds ONE
such entry; **the sink holds TWO identical PROBE lines** — the
second exists only because a transaction that never committed
queued it. Controls: shape C (distinct payload after rollback)
is correctly dropped; shape B (the brief's requested shape —
sink down, 6 threads with separate connections, mixed
commit/rollback, spool drain) is completely clean: no phantoms,
no duplicates, no rolled-back leaks.

Reachability, stated precisely: in Janus's current wiring the
window is narrowed to near-zero — every handler flushes inside
the same DBLOCK hold that commits or rolls back its transaction
(janus.py:2252, 5019, 5120), so a twin cannot commit between a
rollback and its flush, and no handler retries an append after an
internal rollback (the one in-handler rollback, janus.py:3714,
returns a 500 without retrying). Scripts are single-threaded and
flush after their own commits. The finding is therefore against
the **Chain-class contract Q16 specifies** ("presence-checks on a
separate connection: no phantom sink entries"), not a live HTTP
exploit today. It matters because the class is the reusable unit,
the invariant as written is false, and the 1.2.1→1.2.2 history
shows flush placement is exactly the kind of thing that moves
under performance pressure. A per-entry streamed-marker or a
monotonic streamed-seq check closes it cheaply.

### F5 — [MINOR] INV5 is probabilistically flaky: it false-fails on correct code (~1 run in 8)

INV5 asserts the published schedule is not among 3 schedules
predicted from the old seed formula. But for 4 members there are
only **24 distinct directed schedules** reachable from
`rotation_schedule` (measured: 3,000 random seeds → 24 distinct
outputs), so a 3-candidate prediction set contains the true
schedule with probability on the order of 3/24 ≈ 12% per run —
the test asserts a negative over a tiny space. My first battery
run failed INV5 with every other field nominal
(`stale_refile_status: 409, latest_audit_ok: false,
schedule_is_nonce_derived: true, publisher_prediction_matched:
true`); the clean re-run passed 35/35. Any single battery run —
including the ones criterion 4 rests on — carries this noise.

### F6 — [MINOR] _migrate_122 is all-or-nothing behind a swallowed exception: a failed repair is invisible by construction

`_migrate_122` wraps every repair in one try whose
`except sqlite3.Error` rolls back and says nothing (end of
janus.py:842-1063): no chain entry, no `migration_unrepaired`
marker (that code sits after the commit, inside the try), no log
line. One bad row would void ALL repairs — suppression re-key
included — on every boot, silently. **Honesty note:** I tried to
construct the triggering shape (two-spelling hotlist memberships
colliding on the `hotlist_members` PRIMARY KEY during
canonicalization) and could not — 1.1's door canonicalized plate
and uppercased state at write (janus11/janus.py:1102-1103), 1.2's
did likewise, and hotlist_sync never inserts. This is a
latent-fragility note on the failure *design*, not a reproduced
defect. (Probe M-A otherwise passed in full: the real-1.1
upgrade repairs work.)

### F7 — [MINOR] Rotation nonces may be 8 characters: the commitment's secrecy rests on a brute-forceable secret

`_rotation_contribution` accepts nonces of 8–256 characters
(janus.py:4636). A member who chooses an 8-character nonce has
its commitment hash brute-forced by anyone who can read
`rotation_contributions` (the home operator can), after which
that member's contribution to the seed is known before reveal —
compounding F1-style prediction for insiders. An entropy floor
(≥32 hex/base64 chars from a real RNG) costs nothing. Code-read
observation; not separately reproduced.

### F8 — [MINOR] Witness attestations are not bound to the round's designated witness

The witness endpoint (janus.py:4336-4427) checks that the cycle
exists, the agency is a member, and the filer has standing — but
never that `round_no` is a round of that schedule or that the
attesting agency is the member the schedule assigns witness duty
for that round. A member with a valid registered key can attest
"ok" for rounds it was never assigned to witness, and
`_rotation_status` counts attestations by (agency, round). The
signature proves the agency said it; nothing proves it was their
round to say it about. Q24's letter is satisfied; the Compact's
duty accounting is weaker than the letter.

## Judgment calls

**(a) The seven both-tree-pass cases (Q02, Q03, Q06, Q16, Q17,
Q18, Q22).** They must NOT count as verified on the case alone.
I re-verified all seven properties independently: Q06, Q17, Q18,
Q22 hold. **Q02, Q03, and Q16 do not** — F3, F2, and F4 are live
defects sitting inside three of the seven "passing" properties.
A case that passes on the defective tree is evidence about the
case, not the property. Convergence should require property-level
evidence per case; where a case cannot fail on the old tree, it
should be re-aimed or struck from the acceptance count.

**(b) Q25 — atomicity-tested, trust-root resting on round-4 A7.**
Sufficient for this round. A7 is an independent executed attack,
not a case in the same suite, and it printed NOT REPRODUCED under
my own re-run of the round-4 wrapper; backup.py's
verify-before-signing I read directly (backup.py:150-159). The
combination carries the claim. Standing note, same lesson as F2:
restore's lost-key path deserves a real-database test in the next
battery, because the suite's track record on script tooling is
now demonstrably weak.

**(c) The builders' five judgment calls.**
1. **Q20 strip-not-raise: ACCEPT.** The stripped keys are the
   caller's own reserved envelope names; stripping cannot
   fabricate chain data, and raising would hand any buggy caller
   a chain-wide denial of service.
2. **Structural DDL on KEY_LOCKED boots: ACCEPT for DDL proper**
   (idempotent, carries no plate data, and /health needs the
   tables) — **but the acceptance does not extend to the receipts
   dedupe DELETE sitting in the same module-level block** (F3).
   That is a data change wearing DDL's clothes.
3. **Supervisor-transported rotation reveals: REJECT as
   implemented.** Transport is safe only under a phase barrier;
   without one, transport means a single supervisor can run the
   F1 attack alone (my R1 used transport throughout). It becomes
   acceptable the moment commitments freeze at first reveal.
4. **Unconfirmed disposition notes dying at disp_ts + HOLD_DAYS
   + 30: ACCEPT** as a documented default — the class is defined,
   registered, and chained, and the underlying legal question is
   already routed to the City Attorney.
5. **/health camera scope (silent-after-reporting in,
   never-reported out): ACCEPT.** The included half is the
   operationally meaningful alarm; a never-reported camera is a
   provisioning state, visible in the camera registry.

## Convergence criteria — my verdicts

1. **No deployment-blocking / code-critical finding survives
   verification — FAIL.** F1, F2, F3, F4 are code-critical, each
   with a reproduction or an arithmetic proof in this review.
2. **Every prior forced change implemented or answered — FAIL.**
   Four of round 5's 28 items (Q2, Q3, Q16, Q23) are
   FIXED-BUT-WRONG in ways that reproduce at runtime.
3. **Remainder is CANT-DO / legal only — FAIL.** What remains
   after this round includes four code defects, three of them in
   the exact mechanisms rounds 4–5 were commissioned to close
   (rotation seed, key pinning, unchained writes, phantom sink
   entries).
4. **Orchestrator's re-tests pass — PASS, with caveats.** My own
   re-runs match the orchestrator's exactly (322/322; round-4
   PASS; round-5 PASS; Q battery 35/35 clean). The caveats are
   F5 (the battery false-fails ~1 run in 8 by construction) and
   F2's fixture gap (the builders' suite's green pin-audit-key
   check exercises a database shape that cannot occur).

## Overall verdict: **NOT CONVERGED**

1.2.2 is a substantial, honestly-tested build — the migration
spine, the retention unification, the authorization fences, and
the Compact gate all verify under independent execution, and the
builders' reported numbers are exact. But the round-5 commission
named four mechanisms as its core, and all four still fail under
adversarial probing: the rotation seed is biasable by the last
mover, the pin ceremony tool is broken against real databases, a
boot-time path still deletes records unchained, and the sink
presence check still cannot tell a rollback from its twin.

**The single forced change that is the price of my vote:**
*freeze the rotation ceremony's commit phase at the first
reveal* — `/compact/rotation/contribute` must refuse (409) any
commitment filing, new or replacement, once any contribution for
the open cycle carries a revealed nonce, and must never
overwrite an existing commitment (make the commit endpoint's
`WHERE nonce IS NULL` guard universal). F2, F3, and F4 are named
defects with obvious patches that I expect fixed in the same
pass; the phase barrier is the price because the rotation's
unpredictability is the Compact's reason to exist, and it has
now fallen to a grinding variant in two consecutive rounds.
