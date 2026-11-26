# TRACK-124-REPORT — NOCTUA 1.2.4

<!-- VESPER · the evening watch -->

**Tree:** `~/workspace/noctua-1.0/janus124/` — built from a
byte-verified copy of `janus123/` (md5 janus.py
`bcdaf653a4fb7ed837e43020df5011a4`, sentinel.py
`deb8a774fbe1df70fa6e7e28bfd8b0fb` at copy time). No earlier tree
was modified. Nothing was published; publication is the
orchestrator's step.

**Commission:** Round 7 council synthesis
(`~/workspace/noctua-1.0/council7/SYNTHESIS.md`), items S1–S12,
findings register A–F; S11 per `~/workspace/noctua-1.0/2FA-SCOPE.md`.

**Acceptance evidence (final, cold, one run):**
`./run-next.sh` — **SUCCESS, exit 0**, 2026-11-25 07:11 CST start,
log `scratch/battery-20261125-071116.log` (also
`scratch/battery-latest.log`):

| Leg | Result |
|---|---|
| builders' suite (`tests/run_tests.py`) | **332/332 checks** |
| round-4 attacks | PASS — 41 verdicts, only A9b CONFIRMED (the labeled contrast control) |
| round-5 attacks | PASS — 21 verdicts, 0 reproduced |
| round-6 attacks | PASS |
| Q battery + invariants | PASS — 27 cases + INV1–INV6 |
| R battery (vs janus122) | **20/20 cases** |
| load envelope (vs janus122) | PASS — completeness holds to 6 burners on both trees |
| **S battery (vs janus123)** | **25/25 cases** |

Every S case below names its discriminating case in
`tests/run_s124_cases.py`: the case FAILS on janus123 and PASSES
on janus124, except the three marked *measurement/regression*,
which must pass on janus124 and report janus123 for the record.

---

## Per-item dispositions

### S1 — Durable sink delivery (register A1/A2/A3) — DONE
`sentinel.py`: the delivery obligation is now derived from the
committed audit table. `_insert_locked` writes a
`sink_pending(seq, hash, queued_ts)` row **in the same transaction**
as the audit row (a rollback takes the obligation with it);
`_deliver_pending()` is the ONE delivery path — under the spool
flock it adopts the sink file's actual tail, delivers
ledger ∪ post-tail audit rows ∪ legacy spool entries in ascending
order, drops phantom obligations (rolled-back twins), and leaves
the obligation standing — with the backlog visible in
`sink_status()` (`pending`, `oldest_pending_ts`) and in `/health`
(`sink_up` is false over a backlog) — whenever delivery cannot be
verified. `flush_deferred()` no longer presence-checks-and-drops.
Cases:
- **S1a** (unit fault injection): two entries commit; the
  verification connection is made to fail. 1.2.3: both entries
  silently discarded (0 in sink after a healthy retry). 1.2.4:
  both delivered.
- **S1b** (*measurement*): the full server interleave — janus +
  retention.py ×4 + hotlist_sync.py under burner load. 1.2.4:
  0 missing / 0 duplicates / 0 phantoms, health pending 0.
  (Baseline reproduced the defect in both full-battery runs —
  seq 72 committed but never delivered — but the shape is
  timing-sensitive, so the case is classed measurement and S1's
  discrimination is carried deterministically by S1a + S1c.)
- **S1c** (deterministic multi-process): process R commits five
  entries in its own transaction and holds its flush; process J
  appends, delivers, and persists the shared watermark past R's
  seqs; R flushes. 1.2.3: **0 of R's 5 entries ever land**.
  1.2.4: all 11 entries land exactly once.

### S2 — Semantics-preserving boot repair (B1/B2) — DONE
`_hotlist_canon` preserves a legacy `''` state instead of
rewriting it to NULL (a state-less entry still alerts on an
AR-state read); `_supp_repair`'s recovery branch restores plate +
state + current-formula `plate_ref` in one statement and counts a
recovery only when the restored ref verifies. Case **S2** is
Claude p2's executed shape with FIRST-BOOT assertions only:
variant (a) plate already read, variant (b) plate first read
after the upgrade boot. 1.2.3 first boot: /verify 200 (allowed)
on both variants, hit leaked/invisible. 1.2.4 first boot:
403 + queued in /suppressed-hits + not leaked.

### S3 — One suppression predicate (B3) — DONE
All legs decide by `plate_ref`. SQL legs call a registered
SQLite function `noctua_plate_ref()` — sentinel's own primitive,
so SQL and Python cannot drift; the Python predicate
(`_order_covers`) additionally matches plate-less orders through
`key_ref_candidates`, and `_hits_for_read` performs on-sight
recovery (a plate-less order matched by a live read is rewritten
complete and chained SUPPRESSION_RECOVERED). Case **S3**: a
plate-less active order (current-formula ref) is exercised
against /hits, /suppressed-hits, tier-2 search, /verify,
/evidence/export, and Tier 3 results. 1.2.3: search leaked the
plate's reads (2). 1.2.4: every leg suppresses.

### S4 — Demo/install boundary (C) — DONE
Install mode is server-side only: `NOCTUA_DEMO_MODE=1`. The
guard lives **inside `_apply_config`** and runs on the boot load
and every reload: an entry named `imperator` (any case) or any
multi-role entry is refused unless demo mode is on; a violating
reload is refused and the last-good config kept (the refusal is
recorded in the config status); the file's `demo` flag is parsed
strictly (JSON `true` only — the string `"false"` is inert).
Demo mode is chained in SYSTEM and surfaced in /health
(`demo_mode`, `demo_file_flag`). Cases: **S4-reload-path-config
-attacks** (all three attacks authenticate on 1.2.3, all refused
401 on 1.2.4 with legitimate users unaffected),
**S4-boot-refusal-on-demo-file** (1.2.4 exits 3 with REFUSING TO
START), **S4-demo-mode-is-the-supported-demo** (*regression*: with
the env opt-in, the demo file works and /health says so).

### S5 — Rotation ceremony completeness (D) — DONE
Bulk commitments are **signature-gated per entry** exactly as
single contributions are (the home agency's own entry excepted,
as there); one unsigned entry refuses the whole bulk commit with
a chained BLOCKED. Contributions carry a `ceremony_id` minted at
the cycle's open. After the first reveal, /commit is closed in
**all shapes** (1.2.3's guard required a non-empty hash map, so
an empty-hashes commit with mutated members/period rewrote the
pending ceremony). Cancel and void **tombstone** the cycle's
contributions (bounded meta record); a retired commitment or
revealed nonce replayed into a restarted ceremony is refused
409 on the commit, bulk, and reveal paths. Witness designation
(`_designated_witness`): at n≥3 the designated witness is a
member who is neither auditor nor audited — the sole eligible
other at n=3, rotating deterministically by round at n≥4;
rotation status counts that member's filings split into
**positive vs adverse** attestations; at n=2 the round is labeled
`witness_self_attestation: true` (also stated in COMPACT.md).
Cases: **S5-unsigned-bulk** (201→403, partner's own filing then
201), **S5-post-reveal-freeze** (both mutation shapes 201→409),
**S5-cancelled-replay** (201→409), **S5-witness** (designation +
split fields + n=2 label; all absent/wrong on 1.2.3).
Judgment (a) stands as commissioned: the witness rule is
accepted WITH these amendments.

### S6 — Migration completeness (B4) — DONE
- `tests/fixtures/janus10/` is built from the real 1.0 tree
  (`~/workspace/noctua-1.0/janus/`), in-tree and in the battery.
- `_deferred_data_migrations` reads the legacy hot list through
  whichever source column the table actually has (`list_name`,
  else `source`, else the literal) — a genuine 1.0 table no
  longer kills the unit every boot.
- Every MIGRATION_DEFECT record carries the exception **message**
  (truncated 200 chars), in the defect records, the defect chain
  entries, and /health's migration status.
- `_supp_rebuild` is per-row isolated (see the absence-proof
  below for why the commissioned either/or resolves to both).
- The upgrade path's other half: **provision.py's pin ceremony
  crashed on a genuine 1.0 database** (`SELECT plate, state,
  plate_ref` against a suppressions table that has no plate/state
  columns until the migration adds them). It now enumerates by
  the table's actual columns. This was found by the S6 case, not
  by any seat — recorded here as a build-phase find.
Case **S6-janus10-direct-upgrade**: boot the real 1.0 tree,
populate its hot list (incl. a state-less entry), run the Q3 pin
ceremony (the documented path for a legacy chain holding no
checkable refs — this chain's only entry is SYSTEM), boot
1.2.4: migration **complete**, both entries migrated, both alert
on FIRST boot. On 1.2.3 the ceremony itself crashes; with a
ceremony on file its migration still never completes.
Case **S6-suppression-rebuild-isolation**: both orders survive
as separate records (distinct order_refs), id-keyed schema,
migration complete; 1.2.3 leaves the colliding pair in the
unrebuilt table with migration incomplete.

**F-E absence-proof (written, per the commission's either/or):**
a literal duplicate (plate_ref, order_ref) pair cannot arise
from any shipped legacy schema: `plate_ref` is the PRIMARY KEY
of the suppressions table in 1.0 (`janus/janus.py`), 1.1
(`tests/fixtures/janus11/janus.py`), and 1.2
(`tests/fixtures/janus12/janus.py`), so two source rows can
never share a plate_ref, and the rebuild's synthesized
`LEGACY-<rowid>` order_refs are unique by construction. The
duplicate is reachable only from a hand-repaired database —
which is exactly what the case constructs. Per-row isolation is
implemented anyway, so the hand-repaired shape is handled, not
merely argued away.

### S7 — Evidence lifecycle completion (E) — DONE
retention.py gains `remediate_destroyed_bundles`: a bundle whose
evidence row says destroyed but that is still on disk (the
restore-resurrection shape) is removed, chained
EVIDENCE_REMEDIATE. Both destroy paths are record-first:
janus's POST /evidence/destroy writes the row + chain entry and
commits **before** touching files (the response carries
`files_removed`; a failed removal is reported and left for
retention's remediation), and retention's own overdue-destroy
defers its file deletions until after the run's commit. Cases:
**S7-remediation** (destroy → resurrect → retention removes +
chains; 1.2.3 leaves the bundle forever),
**S7-destroy-records-before-files** (bundle made undeletable:
1.2.3 answers 500 with nothing recorded; 1.2.4 answers 200,
`files_removed: false`, row + EVIDENCE_DESTROY landed).

### S8 — Restore honesty + fresh-init guard (F) — DONE
restore.py's docstring claim is narrowed to the mechanism:
*pre-validated; the swap is not I/O-failure-atomic;
.pre-restore-* copies are preserved for manual recovery.*
Tarballs are validated **and fully extracted to staging
directories** before any live file moves; installs are
copy-to-temp + `os.replace` + fsync; no REFUSING is printed
after the live set is replaced (post-swap failure reports FAILED
with the recovery path named). Janus's **fresh-init guard**: a
boot whose database has no audit rows, in a directory holding
`.pre-restore-*` copies, with no restore marker, refuses to
start — checked **before any key source is honored** (the
mid-swap shape carries the deployment's env key, so guarding
only key-minting guarded nothing; the guard's first build had
exactly that hole and the case caught it). Case
**S8-fresh-init-guard**: 1.2.3 boots and founds a fresh chain
over the copies; 1.2.4 refuses (guard named in the log).
ChatGPT's full fail-injection gate remains a recorded dissent,
not commissioned — per settled decision (c).

### S9 — Boundary hygiene (F) — DONE
`_strict_id` clamps to SQLite int64 and rejects negatives and
over-long digit strings (400, never 500), and GET
/tier3/results/<id> + /audit/range route through it. The
KEY_LOCKED boot refusal prints only working remedies (env-key
precedence stated; the pin ceremony named **with** `--confirm`;
the dead write-the-file remedy removed). provision.py's pin
ceremony **overwrites a wrong pre-existing key file and prints
that it was replaced**. `_anchor_accept` refuses any mismatch
whose reason is not `checkpoint_disagreement` — outright, at the
first step (409, nothing recorded). frigate_bridge's docstring
and code agree on "new" events (see judgment calls — the code's
behavior was kept, the text fixed). alert_check names the actual
closure (feed-stale ≠ data-surface FAIL-CLOSED). compact.py's
recompute() fails explicitly on an inverted range. Cases:
**S9-strict-id** (500/404/200-class answers on 1.2.3 → 400/400/
400), **S9-anchor-accept** (checkpoints_missing cleared by
1.2.3's two-key accept; refused on 1.2.4, mismatch stands),
**S9-pin-overwrite** (wrong key file survives 1.2.3's ceremony;
replaced + announced on 1.2.4).

### S10 — Chain contract hardening (F) — DONE
`_append_txn` returns the participation decision **captured at
insert**; `append()` acts on the captured value, never re-reads
`db.in_transaction`. The scrub-flag insert runs on the
bookkeeping connection — no transaction leaks onto a shared
caller connection. The Chain docstring states the
external-serialization contract (in-process RLock + SQLite
locking; no cross-process append mutex; Janus serializes via
DBLOCK). Verify freshness is bounded and stated:
`NOCTUA_VERIFY_MAX_STALE_S` (default 300) — past the bound the
cached verdict is reported **not ok** ("verify overdue",
`last_verified_ok` preserved) instead of ok. Cases:
**S10-participation** (scrub-flagging append on a shared
connection: 1.2.3 leaves `in_transaction` true; 1.2.4 does not),
**S10-verify-freshness-bound** (Claude p4's shape: saturating
ingest + tampered chain — 1.2.3's /health serves chain_ok:true
in all 5 samples; 1.2.4's serves false in all 5).

### S11 — Two-factor authentication (2FA-SCOPE) — DONE
TOTP (RFC 6238, HMAC-SHA1, 30 s step, ±1 step drift) for every
HUMAN role; machine identities (ingest, jobs, partner) stay
key-only. Secrets live in `<db>.totp.json` (0600, atomic
replace) — never in the chain, never in users.json, and
**excluded from backup sets** (backup.py's set is an explicit
allowlist; the exclusion is now stated in its docstring), so a
restore flips every enrollment to `must_reenroll` when Janus
chains the RESTORE (TOTP_REENROLL_REQUIRED). Enrollment via
`provision.py enroll-2fa` prints the secret + 10 recovery codes
once and stays **pending until the first valid code**; an
accepted code is never replayable (strictly increasing
counter); recovery codes are stored SHA-256-hashed, are
single-use, chain RECOVERY_USED, and hold /health degraded until
a supervisor acknowledges (POST /auth/2fa/acknowledge, chained
TOTP_RECOVERY_ACK). Re-enrollment is two-key (supervisor
requests, a different auditor confirms and issues; chained
TOTP_REENROLL_REQUEST / TOTP_REENROLL). Failed factors return
the ordinary 401 and feed the AUTH_FAIL throttle. The **only**
waiver is S4's server-side demo mode.
Cases: **S11-totp-lifecycle** (the full 2FA-SCOPE acceptance
list) and **S11-restore-reenroll-two-key**. On 1.2.3 the
enrollment command does not exist.
Two build-phase finds inside this item, both fixed and covered
by the cases: (i) `_consume_restore_marker()` was *called*
before the TOTP helpers were *defined* — the flip died on a
NameError its own guard swallowed; the call now sits after the
definitions. (ii) do_GET's verify pre-warm authenticates twice
per request (Q18/P13), which read a TOTP acceptance as a replay;
auth() now memoizes its decision **on the handler** (one
instance per request) — cross-request replay protection is
untouched.

### S12 — Measurement honesty — DONE
`hits(read_id)` gained its index (`idx_hits_read_id`). The load
comparison was re-measured per-process with landed-count
verification on both trees; what each number measures is stated
with it:
- **Load envelope** (separate OS processes, HTTP ingest against
  a running server, sink landed-count verified 500/500 at every
  level, chain verifies): janus122 — 17.4 appends/s idle,
  2.6 @ 3 burners, 1.3 @ 6 burners. janus124 — **16.9 idle,
  3.9 @ 3, 2.6 @ 6**. Completeness holds on both; under load
  1.2.4 is at or above the baseline in this run (the S10 bound
  also ends the indefinite stale-verify stall that throttled
  1.2.2's loaded runs).
- **S12 unit load** (3 OS processes × 100 direct Chain appends
  against one DB + sink, landed == appended verified): janus123
  38.8 appends/s; janus124 **19.2 appends/s** — the durable
  ledger roughly halves raw sink-attached Chain throughput.
  That is the honest price of S1: every append now writes its
  delivery obligation in the same transaction. Server-level
  ingest (above) shows no such regression because request
  handling, not the ledger write, dominates there.
- **Boot-time migration scan** on a 3,000-entry database:
  janus123 504 ms; janus124 **506 ms** — no measurable change.

---

## Judgment calls (flagged for the orchestrator)

1. **Builders' suite `suite_demo`** now boots its demo instance
   with `NOCTUA_DEMO_MODE=1` in env — the demo's supported
   configuration under S4. Assertions unchanged. (Flagged in
   HANDOFF.md from the start.)
2. **Ceremony replay vs prior suites.** S5's tombstone refuses
   re-use of a voided ceremony's revealed nonces. Three prior
   artifacts encoded the 1.2.3 semantics and were updated
   minimally, assertions' intent preserved: run_tests.py's
   `rotation_ceremony` helper now signs bulk commitments (as it
   already signed reveals) and its S18/Q23 republish-after-void
   check re-runs with **fresh nonces** (the pure-function seed
   property is re-asserted arithmetically against the new
   nonces); run_q122_cases.py's Q23 cycle 2 likewise uses fresh
   nonces; round-5's `r5_rotation_grind.py` setup commit now
   carries partner signatures (its reshop attack stays unsigned
   and is still refused, by the open-cycle fence).
3. **S1b's classification** (measurement, above): the
   server-interleave shape reproduced on the baseline in both
   full runs but is timing-sensitive by nature; S1's
   discrimination rests on the deterministic S1a/S1c.
4. **frigate_bridge "new" events:** the register asked that doc
   and code agree, not which side wins. The code's behavior was
   kept (a "new" event forwards as an early read; Janus dedupes
   persistently and owns supersede — the Q5 doctrine) and the
   docstring corrected. The alternative (dropping "new") would
   have changed ingest behavior no seat voted on.
5. **Anchor-accept refusal point:** S9's text says the accept
   path "refuses reasons other than checkpoint_disagreement";
   1.2.4 refuses at the supervisor's first step (nothing is
   recorded) rather than recording and refusing the confirm —
   strictly safer, and the case asserts that shape.
6. **S8 guard scope:** the guard fires before any key source is
   honored, including a valid env key (see S8 above). A
   deliberate fresh start in a directory containing pre-restore
   copies now requires removing the copies or completing the
   restore — that friction is the commissioned behavior.
7. **A regression this build introduced and caught:**
   the first per-row `_supp_rebuild` shipped a VALUES clause
   with the wrong placeholder count; the rebuild unit failed on
   every legacy database ("12 values for 11 columns") until the
   builders' P4 migration check caught it. Fixed; P4 and the
   full battery are green. Recorded because the battery, not
   the author, earned that catch.

## What was NOT touched
Earlier trees (janus/ … janus123/) — read-only throughout. The
documents package (white paper, deck, one-pager, FAQ, video) —
frozen per the commission. The interface (UI-SPEC.md) — builds
after convergence. Nothing was published or pushed.
