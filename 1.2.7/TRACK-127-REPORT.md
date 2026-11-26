# TRACK-127 — NOCTUA 1.2.7 build report

Builder: Vesper (subagent builder seat). Commission:
`council9/SYNTHESIS.md` §6, items V1–V15, plus the §5 rulings
(S10 test-only fix; R-F as amended), plus Addendum 1's
V16–V18 (Gemini F4/F5/F6, chair-verified), which landed
mid-build and were folded in the same evening. Tree:
`janus127/`, copied from `janus126/` (janus.py md5
`9e39e0414cf4b782eb93aaf05573e8bc`, sentinel.py md5
`dca5d958da4c8e4e7be775eaae092c7f` at copy time — see the end
of this report for the closing re-verification).
No git operations, no pushes. The only files touched outside
`janus127/` are the two shared docs the commission names
(`docs/CANT-DO.md`, `docs/INSTALL.md` §8) and, inside the tree,
`COMPACT.md`.

## Battery results

**Final: every leg green on the final code.** Per-leg record
(logs in `janus127/scratch/legs3/`):

| leg | result | log |
|---|---|---|
| builders | 335/335 checks, exit 0 | legs3/01-builders.log |
| round 4 | 41 verdicts, only the A9b contrast control confirmed, exit 0 | legs3/02-round4.log |
| round 5 | 21 verdicts, none reproduced, exit 0 | legs3/03-round5.log |
| round 6 | PASS — every verdict PROPERTY HOLDS / not reproduced, exit 0 | legs3/04-round6.log |
| Q + invariants | every case PASS (Q01–Q27, S2 pair, INV1–INV6), exit 0 | legs3/05-q.log |
| R battery | 20/20, exit 0 | legs3/06-r2.log |
| load envelope | COMPLETE: 500/500 landed at 0/3/6 burners, both directions, verify=True; `health_availability_under_saturation: {samples: 20, answered: 18, dropped: 2, wrong_values: 4}` (reported measurement, not a gate — see judgment call 4; the 4 "wrong values" are responses under saturation that were not full health payloads, recorded for Round 10 as commissioned) | legs3/07-load.log |
| S battery | 25/25, exit 0 — S10 PASSED under load with `dropped_sample_retries: 1` on the test side (one dropped sample, recovered by the single commissioned retry, logged in the case output per §5; freshness held in every returned sample) | legs3/08-s.log |
| T battery | 20/20, exit 0 | legs3/09-t.log |
| U battery | 21/21, exit 0 | legs3/10-u.log |
| V battery | 19/19, exit 0 (V1–V15 + V16–V18) | legs3/11-v.log |

**How the battery was run — full disclosure.** The one-shot
`./run-next.sh` was attempted three times; the VM's session
instability (the same failure mode that interrupted both
1.2.6 verification runs) and one mid-build commission change
broke all three:

- **Run #1** (`scratch/battery-20261126-000513.log`) — a
  diagnostic run on the pre-fix code. It completed builders
  (FAIL: 7 check failures + a crash at suite_p121, all
  diagnosed — see "Defects the battery caught"), round 4 PASS,
  round 5 PASS, round 6 FAIL (F9 Q02 only), Q FAIL (Q02 only),
  then DIED mid-R-leg in a session interruption (~18:21 CST).
  R (partial), load, S, T, U, V never ran in run #1.
- **Run #2** (`scratch/battery-20261126-024001.log`) — on the
  post-fix code: builders / round 4 / round 5 PASS. The
  builder STOPPED it during round 6 when Addendum 1 landed
  (V16–V18 changed janus.py, sentinel.py, and compact.py, so
  no run on pre-addendum code could be the acceptance run).
- **Run #3** (`scratch/battery-20261126-024941.log`) — the
  one-shot on the final code (V1–V18 in). A runtime restart
  killed it inside the builders leg; no leg completed.

The acceptance battery was therefore completed **leg by leg
with run-next.sh's exact commands and environment** (TMPDIR
at janus127/scratch/tmp, NOCTUA_BATTERY_CONTEXT=full exported
for the S leg's S10 rule), one leg per background execution so
a further restart could cost at most one leg — the disclosed
recovery the commission prescribes and the 1.2.6 report used.
Code did not change during the leg-by-leg completion except
ONE test-file literal: the first R attempt in this sequence
came back 19/20 with R15 failing on its hardcoded "1.2.6"
version literals (the re-aim-every-build pattern of u11,
missed in exploration). R15 was re-aimed to "1.2.7"
(run_r123_cases.py.orig-126 preserved with the reason header)
and the R leg was re-run IN FULL: 20/20. No product code
changed after run #3 launched.

## Defects the battery caught during this build

Two real defects in the new code were caught by the living
suites during the first cold run and fixed before the
acceptance run (both are also recorded in the run disclosure
in the battery section):

1. **The LAB_MODE boot entry chained under a KEY_LOCKED boot**
   (caught by Q02 and round-6's F9 re-verification of it). The
   V4 boot appends (`LAB_MODE`, and the `LAB_MODE_REFUSED` /
   `DEMO_MODE_REFUSED` refusal entries) ran before the
   key-lock branch and wrote one entry under a wrong key —
   violating the codebase's own doctrine ("on a KEY_LOCKED boot
   nothing is chained, ever"). Fixed: both LAB appends are
   guarded on `not KEY_LOCKED`, and the two refusal appends
   raise out of their try blocks when locked (the refusals
   themselves — message + exit 3 — are unaffected). Q02 now
   measures audit growth under lock: 0.
2. **alert_check.py named two retired second-factor states**
   ("unprovisioned_locked", "provisioning") and neither of
   1.2.7's. A production install in the ceremony state — the
   exact condition the dead-man check exists to shout about —
   would have fallen through to the store-details branch.
   Fixed: alert_check names the CEREMONY state (fenced data
   surface, enrollment outstanding) and LAB MODE (fixture
   waiver, never production), parallel to its DEMO MODE line.

## Per-item dispositions

**V1 — pickup lockout scope (BLOCKER). DONE.**
`_auth_lock_note_failure(user, key_verified=False)` now returns
without counting unless the caller passes a verified key; the
guard lives INSIDE the function so no future call site can
repeat the round-9 bypass. need_auth passes
`key_verified=self._auth_key_ok`. The pickup handler's wrong-key
branch no longer calls it at all (the failure is AUTH_FAIL
evidence only, via `_note_auth_fail`); the token-failure branch
— reached only after the key verified — passes
`key_verified=True`. The pickup "account is locked" reply is
replaced by the uniform 401 `{"error": "authentication failed"}`.
Case `v1_pickup_lockout`: a 6-shot wrong-key spray leaves the
target able to authenticate (1.2.6: locked out), and a genuinely
locked account's pickup refusal is the uniform body (1.2.6 named
the lock and the unlock path).

**V2 — submission never mutates a live row (BLOCKER). DONE.**
The non-supervisor submission INSERT's ON CONFLICT clause gains
`WHERE hotlist_members.pending=1`: a conflict with a live
(pending=0) row changes nothing; a conflict with a pending row
still updates the submission. The answer stays the uniform 202
and HOTLIST_ADD_PENDING is still chained either way; the
validation order is untouched (§5 ratified it). Case
`v2_submission_vs_live`: a detective's submission against a
supervisor's live row leaves the row byte-identical, returns the
same 202 shape as a fresh submission, and the plate still
matches on ingest. This case is also the R-F coverage companion
for the DET→SUP adaptation sweep (§5).

**V3 — sink truncation is tail-only (BLOCKER). DONE.**
sentinel.py gains `_sink_tail_scan()` (one pass: last valid seq,
the cut offset just past it, and whether an unparseable line
sits BEFORE the last valid line). The torn branch of
`_deliver_locked` now classifies first: mid-file damage sets the
diverged seqs (audit vs sink map), records a named divergence,
and writes nothing; a clean torn tail is archived to
`<sink>.torn-<ts>` (collision-proof name), truncated at the cut,
and the recorded message names the TRUE seq the file ends at
after re-deriving the tail from the truncated file. Case
`v3_sink_mid_damage`: with entries 4–5 welded and entry 10's
line torn, entries 6–9 survive in the file, sink_status is
not-ok, and seq 4 is named diverged (1.2.6 truncated at the weld
and deleted 4–10's valid entries).

**V4 — U9 redesign: the ceremony state (HIGH). DONE.**
The born-empty marker and the legacy-chain probe are retired as
gating mechanisms (the import-time probes and the marker write
are deleted; `_totp_provisioned()` — store or meta marker — is
now the only provisioning test). An unprovisioned install is in
the CEREMONY state: `_ceremony_fenced(method, path)` fences the
human data surfaces (search, hits, suppressed-hits, verify,
outcomes, hotlist reads and writes, Tier 3, evidence, shares,
reports, compact reads) for key-only HUMAN roles, answered 503
with a chained CEREMONY_REFUSED; ingest, the safety writes,
provisioning, auth administration, the audit reads and /health
stay open. Fixtures are carried by `NOCTUA_LAB=1`: chained at
boot (LAB_MODE), named in /health (top-level and degraded
`lab_mode`, totp state "lab"), and refused at boot on a
provisioned install (LAB_MODE_REFUSED chained, exit 3 — the U5
pattern). Legacy unprovisioned databases land in the ceremony
state with the existing bootstrap enrollment path. INSTALL §8
gains the go-live checkbox ("every human enrolled ACTIVE before
ingest connects"). Case `v4_ceremony_state`: a born-empty
install's copied DB serves 503 on the new host (1.2.6 served the
data), ingest stays open, the same install under LAB serves,
and LAB on a provisioned install refuses the boot.

**V5 — fence reason gate + atomicity (HIGH). DONE.**
`_anchor_apply` now (a) clears automatically only for file-state
reasons (`checkpoints_malformed`, `checkpoints_unreadable`,
`checkpoints_missing`, `anchor_check_error`); a
`checkpoint_disagreement` auto-clears only when every recorded
disagreeing checkpoint id (new `bad_ids` in the evaluation
detail) is in the accepted-ids set — otherwise it clears only
via the two-key accept; and (b) appends the chain entry
(ANCHOR_CLEARED / STARTUP_ANCHOR_MISMATCH) BEFORE mutating meta,
aborting the state change when the append fails (1.2.6 committed
first and swallowed the failure). Case `v5_fence_reason_gate`:
deleting the disagreeing line no longer lifts the fence
(1.2.6: it did); the two-key accept clears it; a torn-line
(file-state) fence still auto-clears on repair with
ANCHOR_CLEARED chained. Case `v5b_fence_atomicity`: with
chain.append forced to raise, neither the clear nor the set
lands.

**V6 — restore tri-state (MEDIUM). DONE.**
restore.py's outgoing read returns "provisioned" / "never" /
"unknown" (any exception → "unknown"); the marker carries the
string. Janus maps it fail-closed: anything but a clean "never"
(legacy booleans map True→provisioned, False→never) counts as
provisioned, so the must_reenroll flip materializes. Case
`v6_restore_unknown`: with the outgoing DB corrupt at read time
(main file garbage, WAL sidecars removed — a hot WAL's frames
shadow page 1 and mask corruption), the marker records
"unknown", key-only auth refuses, must_reenroll ≥ 1 (1.2.6 read
False and skipped the flip).

**V7 — pre-restore registry (MEDIUM). DONE.**
The registry pattern is now `"<db>*.pre-restore-*"`, covering
the DB copy, the `-wal`/`-shm` copies, and the `.audit_key` /
`.signing_key.pem` / `.signing_pub.pem` snapshots restore
writes. One pattern feeds both `registry_breaches` (flagging)
and retention's `prune_glob` (pruning). Case
`v7_registry_prune`: all five aged artifacts prune (1.2.6 pruned
only the DB copy — exactly Claude B's 4-of-5).

**V8 — bounded failure accounting (MEDIUM). DONE.**
`_note_auth_fail` keys totals by `_auth_fail_total_key`: a
configured account's own hash (exact counts, unchanged
semantics) or one of 64 fixed `unknown:<n>` buckets for
unconfigured names; the suppressed aggregate still rides the
"(suppressed)" total and is flushed per bucket as before.
`_auth_fail_flushed` markers are pruned on every call once
their bucket rolls over. /health's per-account list is built
from configured accounts only, so its sort is bounded too. Case
`v8_fail_totals_bound`: 50,000 distinct sprayed usernames leave
≤ 65 totals entries (1 configured + 64 buckets; 1.2.6: 50,001)
with the configured account's count exact, and 5,000 seeded
stale flushed markers are swept by the next failure (1.2.6: all
persist).

**V9 — safety set (MEDIUM). DONE.**
`ANCHOR_FENCE_SAFETY_POST` is now `{"/reads", "/suppressions",
"/holds"}` — both releases removed, per the §5 ruling (extended
to suppressions/release). Statutory ceilings are unaffected.
Case `v9_safety_set`: the set membership, plus the dispatch
consequence — during a fence a supervisor's hold release is
refused 503 (1.2.6 let it through, reaching the handler).

**V10 — keyed hit references (MEDIUM). DONE.**
New `hit_ref()` beside `plate_ref()` ("href:" + keyed HMAC,
"href:unavailable" without a key). Every BLOCKED payload that
named a hit now carries `hit_ref` instead of the raw id: the
three verify refusals, the five evidence-export refusals, and —
beyond the commission's letter, same principle — the evidence
release/destroy and disposition-confirm BLOCKED entries.
Custody entries (VERIFY, ALERT, EVIDENCE_*) keep raw ids for the
key holder's internal joins. Case `v10_blocked_hit_ref`: a
refused verify and a refused (suppressed) export chain BLOCKED
payloads with `href:` refs and no `hit` key (1.2.6: raw ids).

**V11 — pickup secret expiry + lockout scope (LOW-MED). DONE.**
(a) `_totp_pickup` computes token expiry separately from the
hash check: an expired window (or an unparseable enrolled_ts)
deletes the pending entry — secret included — saves the store,
chains PICKUP_EXPIRED, and refuses uniformly, with no lockout
count. (b) `_lockout_counts` counts only
{bad_second_factor, not_enrolled, entry_malformed};
must_reenroll counts only when a code was actually presented
(the X-Noctua-TOTP header is non-empty); store_unavailable never
counts. Case `v11_pickup_expiry_scope`: an aged pickup leaves
no store entry and chains PICKUP_EXPIRED (1.2.6: the secret
persisted); six no-code attempts against a must_reenroll entry
lock nobody (1.2.6: the account appeared in locked_accounts).

**V12 — unique temp paths (LOW). DONE.**
The pickup rotation's users.json write and provision.py's
`save()` both use the TOTP store's unique-temp pattern
(`<path>.tmp.<pid>.<hex>` + os.replace). Case
`v12_users_tmp_unique`: an os.replace spy sees three distinct
temp paths from save() (1.2.6: the same fixed `.tmp` three
times), and janus.py no longer contains the fixed
`USERS_PATH + ".tmp"` rotation. Honest flag: the janus half is a
source-pattern assertion — the rotation's functional behavior is
covered by the pickup cases (v1/v11, u7); a torn-write race on
the rotation specifically is not reproducible in a test without
fault injection into the server process.

**V13 — uniform evidence refusals (LOW). DONE.**
For non-supervisor roles, evidence export's nonexistent,
suppressed, and unverified refusals are one byte-identical 409
`{"error": "hit not found or already decided"}` (the /verify
shape); the distinct reason is chained internally only.
Supervisors keep the distinct answers. Case
`v13_evidence_uniform`: the three detective refusals are
byte-identical (1.2.6: 404 / 403-naming-suppression /
409-naming-status), and the supervisor's suppressed answer
stays distinct.

**V14 — no code. ANSWERED HERE.**
Qwen F10 was right about the probe's keying: `_DB_LEGACY_CHAIN_
AT_IMPORT` keyed the U9 exemption on the first payload's `v`
field (payload v2 arrived in 1.2.1), while its rationale cited
the TOTP era (1.2.4). The discrepancy is moot in 1.2.7: V4
retired the probe (and the marker it fed) as a gating mechanism
entirely — there is no legacy exemption left to mis-key. A
legacy unprovisioned database now lands in the ceremony state
like any other unprovisioned install, and reaches service
through the same bootstrap enrollment path. Case
`v14_probe_retired` asserts the retirement in code patterns
(the probe assignment, the `_unprovisioned_locked` definition,
and the marker read/write are gone; 1.2.7's comments name the
retirement in words, so the case matches code, not mentions).

**V15 — smalls. DONE, item by item.**
- Sink archive names: `_unique_archive_path()` adds a monotonic
  `-2`, `-3`… suffix on collision; used by the divergence
  rotation and the torn-tail archive. Case v15(b): a pre-created
  same-second archive is never overwritten (1.2.6: os.replace
  destroyed it).
- Bounded stranded lists: `stranded_summary()` (count + first
  50 + SHA-256 of the full list) now shapes the chained
  SINK_DIVERGENCE_ACCEPTED payload and /health's sink section
  (`diverged_seqs` capped, `diverged_count`/`diverged_sha256`
  beside it). Case v15(d): 60 stranded seqs chain as 50 + count
  60 + hash (1.2.6: the full list). The accept RESPONSE still
  carries the full list to the operator working the divergence —
  see judgment calls.
- Pending submissions expire: `_expire_pending_submissions()`
  (30 days, chained HOTLIST_PENDING_EXPIRED per row) runs on the
  submission, queue-read, and decide paths; approving an expired
  id 404s. Case v15(c).
- Escrow pairing: backup.py's prune collects the stamps of sets
  pruned this run; an escrow prunes only with its set (same run)
  or when its set is gone AND it is past the cutoff — an
  archivist-retained set (e.g. renamed `backup-<stamp>.archived`,
  whose stamp no longer parses) keeps its escrow. Case v15(e):
  the retained set's escrow survives, a set-less escrow still
  prunes (1.2.6 pruned both by age).
- checkpoint.py: a valid-JSON non-object final line is treated
  exactly like a torn line (truncate + note); a non-object line
  elsewhere still refuses as unreadable. Case v15(a) (1.2.6:
  AttributeError).
- Signing comment: the boot comment now says the failure
  disables signing AND fences the service (every checkpoint
  disagrees when SIGNING_PUB_PEM is None), matching
  `_checkpoint_sig_ok`'s behavior.
- attack2.py.orig-124's header now describes both adaptations
  (the 1.2.5 escrow re-point and the 1.2.6 DET→SUP setup change).
- COMPACT.md's second line reads "1.2.7 is what the code does."
- sentinel_audit.py reports version "1.2.7". Case v15(f).
- Migration stamps: the MIGRATION / MIGRATION_DEFECT payload key
  `"to"` is renamed `"target_schema_version"` and
  migration_status's `"version"` likewise; the VALUES stay
  "1.2.5" — they name that migration's target schema, which is
  historical fact. TRACK-126's "every user-visible version
  string reads 1.2.6" claim was overstated and is not repeated
  here: the stamps name a schema version, the schedule documents
  carry a document-format version, and both are correct as-is.
- CANT-DO: the enroll-2fa shell-operator entry is written into
  `docs/CANT-DO.md` (Technical limits): enrollment is an
  in-person act at the machine; there is no remote enrollment
  and no emailed secret, and enrolling a department means
  scheduling people at the machine. (§5(vi) found the entry did
  not exist; now it does.)

**V16 — sink_divergence() names an unreadable sink (HIGH;
Addendum 1, Gemini F4). DONE.**
My V3 rework did NOT already cover this — it changed
`_deliver_locked`'s torn-tail path; `sink_divergence()` is a
different function and kept the defect: stranded was computed
only for seq ≤ max(tail_seq, file_seq), so a non-empty
unparseable sink with nothing ever delivered (tail 0, file 0)
returned None while delivery treated the same state as a
divergence and halted — the accept ceremony 409'd forever.
Fixed: when the tail state is "unreadable", every committed
seq is stranded (the same computation `_deliver_locked`'s
unreadable branch already made) and the divergence dict is
returned. Case `v16_sink_unreadable`: the divergence names
seqs 1–5 (1.2.6: None).

**V17 — _auth_locked performs no out-of-lock write (HIGH;
Addendum 1, Gemini F5). DONE.**
The shell-unlock branch of `_auth_locked()` popped the
in-memory lock AND called `_auth_lock_persist` — a DELETE +
commit on the shared connection from a function that runs on
auth paths outside DBLOCK. The persist call is removed; the
in-memory pop (the 1.2.6 fix) stays. Persistence is owned
where the chair's verification found it: provision.py's unlock
already deleted the persisted row when it wrote the marker,
and `_consume_provision_marker` reconciles inside DBLOCK.
Case `v17_auth_locked_no_write` is behavioral: with a
persisted lock row and a pending unlock marker, the call
returns False, the memory is popped, and the row is STILL
THERE (1.2.6: row deleted by the read path).

**V18 — compact.py per-side TOTP secrets (MEDIUM-HIGH;
Addendum 1, Gemini F6). DONE.**
compact.py authenticates as two different human accounts on
two agencies' servers (our chain_auditor AT the partner; our
auditor on OUR Janus) but attached the one global
NOCTUA_TOTP_SECRET to every http() call. Now: `--partner-
totp-secret` / NOCTUA_PARTNER_TOTP_SECRET and `--auditor-
totp-secret` / NOCTUA_AUDITOR_TOTP_SECRET; http() and
recompute() take an explicit `totp_secret` and attach a header
only when one is passed; every partner-side call passes the
partner secret, the audit-result post passes the auditor
secret, and the partner receipt post — a machine-role call —
passes none. Judgment call (flagged): the legacy
NOCTUA_TOTP_SECRET remains as the fallback for either side
when its per-side secret is unset, so existing single-secret
scheduled jobs keep working; setting the per-side variables is
what separates the sides. Case `v18_compact_per_side`: with
distinct per-side env secrets, the two sides' requests carry
different, correct codes and the receipt carries no TOTP
header (1.2.6: the per-side API does not exist — the unit
errors there, which is the defect's shape).

**S10 test-only fix (§5 conditions). DONE.**
`s10_verify_overdue` (S battery) retries a DROPPED sample
(chain_ok None — no response) exactly once, only when
`NOCTUA_BATTERY_CONTEXT=full` (exported by run-next.sh alone),
and reports the retry count in the case detail. A wrong returned
value is never retried; a standalone run (context unset) keeps
the strict behavior — a drop fails the case. Per the ruling,
full-battery S results keep being reported as 24/25 until the
revised case passes under load; the battery section below
reports exactly what the run showed. The load envelope gains
the named measurement `health_availability_under_saturation`
(20 /health samples under 6 ingest burners against the test
tree: answered / dropped / wrong_values) — reported, not gated.

## The two owed answers

**DeepSeek F5 — can `anchor_fenced()` invoke `_anchor_apply`
outside DBLOCK?** No. `anchor_fenced()`'s call sites are the
three dispatchers (`_post`, `_get`, `_delete`) and `_health`
(reached through `_get`) — all execute under DBLOCK, which the
do_* wrappers hold for the whole request. The only other path
that reaches `_anchor_apply` is boot, via
`_startup_anchor_check()`, which runs single-threaded before the
server starts serving. There is no out-of-lock call site; the
fence's evaluate-and-apply sequence cannot interleave with a
request.

**Claude B's R-F query — the round-6 files that boot "122".**
The "122" label is the round-6 seat harness's historical slot
name for the TREE UNDER TEST: `tests/attacks/run_round6.py`
symlinks the tree being tested into the `janus122` slot (its own
docstring says the slot name is historical). The real older
builds occupy their own slots (janus121 = the sibling baseline
tree; janus11/janus12 = fixtures; SEAT_J10 = the 1.0 build). So
`f2d_native_orders.py` and `f4_preauth_race.py` booting "122"
run the CURRENT test tree's janus.py — janus127 in this build.
Their adaptation against the preserved `.orig-124` originals is
exactly one SETUP line each: the hot-list add's actor changed
DET→SUP, because U6 made a detective's add a pending submission
and the cases exercise the direct-add path. Every assertion is
unchanged. Verdict: the adaptation is actor-changing, so it is
inside the R-F rule ONLY with its coverage companion — which
exists: the U battery's U6 cases cover the detective-submission
path, and the synthesis §5 names the V battery's V2 case as the
retroactive companion for the DET→SUP sweep.

## Living-suite adaptations in this build (R-F record)

- **Harness LAB default (all batteries).** Every Boot/Instance
  now defaults `NOCTUA_LAB=1` — assertion-preserving in effect:
  without it, the ceremony fence (V4) would refuse the data
  surfaces every pre-1.2.7 fixture exercises unprovisioned. The
  flag is dropped by start() once the fixture's DB is
  provisioned (a provisioned install refuses LAB at boot), and
  an env_extra that names NOCTUA_LAB explicitly is never
  dropped (the operator's posture wins — added after the V4
  case showed the drop defeating the refusal test). Coverage
  removed: NONE from the suites — the ceremony behavior itself
  is covered by the V battery's v4 case, including the
  no-flag posture. Files: tests/run_t125_cases.py,
  run_tests.py, run_q122_cases.py, run_r123_cases.py,
  run_s124_cases.py, attacks/round6/common.py (Boots);
  attacks/round5/lib5.py's boot_script injects the flag only for
  unprovisioned fixtures (older builds ignore the variable).
  Two refinements landed during the battery runs, both in the
  drop's provisioning prediction (`_fixture_provisioned`, same
  six files): (a) it mirrors Janus's V6 restore-marker mapping
  exactly — a marker counts as provisioned unless it explicitly
  says "never"/False (a missing field or an unparseable marker
  reads "unknown", and Janus treats unknown as provisioned);
  the first cold run's p121-marker fixture (a hand-written
  marker with no outgoing field) exposed the mismatch when the
  LAB refusal fired on the boot after marker consumption.
  (b) The P4 migration suite's hand-built boot env (run_tests.py)
  declares NOCTUA_LAB=1 directly — its migrated legacy DB is
  unprovisioned and the suite exercises searches the ceremony
  fence would otherwise refuse; the migration assertions are
  untouched. run_tests.py's pre-adaptation original is
  preserved as run_tests.py.orig-126 with the full reason
  header (the seven expectation updates from the first cold
  run — registry/version literals following the shipping build,
  the fixture's "lab" state name, alert_check's LAB line, and
  the three V13 uniform-refusal shapes — are itemized there
  and in the battery section).
- **U battery: u9_populated_arrival re-aimed.** The case's
  premise (the marker mechanism) was retired by V4; the case now
  asserts the V4 semantics on the same construction (a populated
  DB arriving from janus125): ingest open, /hits refused 503,
  health state "ceremony". The baseline (janus125) still fails
  it. Original preserved as run_u126_cases.py.orig-126 with the
  reason header.
- **U battery: u11_version_sweep re-aimed** to the shipping
  build's literal ("1.2.7") on the same five surfaces; the case
  docstring notes the literal follows the shipping build. Same
  .orig-126 preservation.
- **R battery: R15 version literals re-aimed** ("1.2.6" →
  "1.2.7", three spots in r15_honesty: /health version,
  /health registry_version, sentinel REGISTRY_VERSION — the
  invariant is that all three equal the shipping build's
  version consistently). Found by the acceptance battery's
  first R attempt (19/20); original preserved as
  run_r123_cases.py.orig-126 with the reason header; the leg
  was then re-run in full (20/20).

## Judgment calls (flagged, per the commission)

1. **V4 fence set.** §4 names searches, hits view, Tier 3,
   shares, reports. The fence also covers /hotlist reads and
   writes, /suppressed-hits, /outcomes, /verify, and the compact
   read surfaces — all plate-data surfaces of the same kind.
   /lists, /stats, /config/status stay open (registry and
   diagnostics, no plate data); /audit* stays open (the audit
   chain is the ceremony's own evidence, and the chain_auditor
   role's read is how an operator watches enrollment happen).
   The fence binds key-only HUMAN roles only; machine roles
   (ingest/jobs/partner) are not the round-9 threat and are
   untouched.
2. **LAB in /health.** LAB_MODE is named in /health (top-level,
   degraded, and the totp state "lab") but was NOT added to the
   ok_all computation: totp state already holds health down when
   unprovisioned, and a lab fixture can provision mid-run, after
   which the flag refuses only at boot. Naming without gating
   seemed the honest middle; flagged for the round.
3. **S10 gating mechanism.** The synthesis says "a drop in a
   standalone run still fails". Implemented as: the retry arms
   only under NOCTUA_BATTERY_CONTEXT=full, which only
   run-next.sh exports. A hand-run of the full runner IS the
   full battery; a direct battery-file invocation is the
   standalone run.
4. **Load-envelope health availability** is a reported
   measurement, not a pass/fail gate: the leg still passes on
   append completeness. Making availability a gate would
   re-create the S10 flake as a load-leg flake; the numbers are
   in the log for the round to judge.
5. **V10 beyond the letter.** The keyed-ref conversion was
   extended to the evidence release/destroy and
   disposition-confirm BLOCKED entries (same joinability
   principle). VERIFY/ALERT/EVIDENCE_* custody entries keep raw
   ids deliberately.
6. **V13 supervisor carve-out.** The uniform shape binds
   non-supervisors; supervisors keep the distinct refusals (the
   commission's text says "to non-supervisor roles" in §6's V13
   line — implemented as written).
7. **V15 stranded bound.** Only the CHAIN payload and /health
   are capped; the accept response keeps the full list for the
   operator working the divergence. The commission named chain
   entries and /health; the response is neither.
8. **V12 janus half** rests partly on a source-pattern
   assertion (see the V12 disposition's honest flag).
9. **V8 flushed-pruning test construction** seeds stale markers
   directly into `_auth_fail_flushed` rather than growing them
   organically (organic growth needs failures spread across
   minute buckets — a 50k-case cannot wait out real minutes).
   The pruning code path exercised is the production one.
10. **V6's missing-field semantics.** A restore marker with NO
    outgoing_provisioned field (pre-1.2.6 restores, or a
    hand-written marker) maps to "unknown" → provisioned in
    Janus's consumption, as does an unparseable marker. The
    commission's V6 text covers the read failing (exception);
    the absent-field case is the same fail-closed reading, and
    it is what Janus shipped in this build. It interacts with
    the LAB refusal: marker consumption at import marks the
    install provisioned, so a LAB-flagged boot over such a
    marker refuses — correct for an operator, and the harness
    now predicts it (see the R-F record). Flagged for the
    round: if the council prefers absent-field → "never", the
    change is one branch in `_consume_restore_marker` plus the
    harness mirror.
11. **V18's legacy fallback.** The per-side secrets fall back
    to the legacy NOCTUA_TOTP_SECRET when unset (either side
    independently). The addendum names the per-side variables
    but is silent on the legacy one; dropping the fallback
    would break every existing single-secret Compact job at
    upgrade, so it stays — an operator who sets only the legacy
    variable has explicitly configured the shared-secret shape
    the finding criticizes, and the per-side path is there when
    the second agency provisions. Flagged for the round.

## Closing verification

janus126/ untouched, re-verified at build end (Nov 25, 2026):
janus.py md5 `9e39e0414cf4b782eb93aaf05573e8bc`, sentinel.py
md5 `dca5d958da4c8e4e7be775eaae092c7f` — identical to the
copy-time values and to the council9 pack records. No git
operations were performed and nothing was pushed. Files
outside janus127/ touched: `docs/CANT-DO.md` and
`docs/INSTALL.md` (the two the commission names) — nothing
else.
