# TRACK-128 — NOCTUA 1.2.8 build report
# VESPER · the evening watch

**Builder:** council builder seat (Vesper's), 2026-11-26.
**Commission:** council10/SYNTHESIS.md §6 — five items, complete scope,
nothing else authorized. **Source tree:** janus127/ copied to janus128/
(rsync, scratch/ and __pycache__ excluded); janus127/ byte-untouched
(baseline md5s recorded at copy time in scratch/baseline-127-md5.txt
and re-verified at the end of this build — see §7).
**Chair verification is separate:** this report states what was built
and what the builder's own runs showed. It does not declare
convergence.

---

## 1. Item 1 — V5 reason promotion (the blocker)

**Where:** `janus.py:_anchor_apply` (mismatch branch), plus its
docstring.

**What changed:** 1.2.7 wrote a mismatch record only when none stood
(`if recorded is None`), so a checkpoint disagreement evaluated while
the fence stood for a file-state reason was never recorded; the later
file repair auto-cleared the fence under the stale reason
(R10-C02 — chair-executed; Claude B's r01 is the same sequence).
1.2.8 adds a promotion branch beside the set path: when a fresh
evaluation returns `checkpoint_disagreement` and the recorded reason
is in `ANCHOR_FILE_STATE_REASONS`, the record is promoted —

1. `chain.append("ANCHOR_REASON_PROMOTED", {prior_reason,
   prior_detected, reason, bad_ids, checkpoint_entries,
   chain_entries})` FIRST;
2. only on success, `_meta_set("anchor_mismatch", ...)` replaces the
   record with the disagreement detail (bad_ids included), stamped
   with a fresh `detected` and a `promoted_from` field naming the
   file-state reason it replaced.

An append failure aborts the promotion (the file-state record stands;
the next evaluation retries) — V5's append-before-mutation atomicity
rule, applied to the new transition. After promotion the existing
subset gate governs: the disagreement auto-clears only when its
bad_ids are covered by `_accepted_checkpoint_ids()`; otherwise the
fence stands for the two-key anchor-accept. A record already standing
for `checkpoint_disagreement` (or any non-file-state reason) is left
exactly as it is — only a file-state record can auto-clear out from
under a disagreement, so only it is promoted.

**Discriminating cases:**
- `w1_reason_promotion` (server, the C02/r01 sequence): torn line →
  fence records `checkpoints_malformed` → good+foreign file → record
  promotes to `checkpoint_disagreement` with bad_ids,
  ANCHOR_REASON_PROMOTED chained → good file restored → fence does
  NOT auto-clear → two-key accept clears. **janus127: FAIL** (record
  stays `checkpoints_malformed`, no promotion chained, fence
  auto-clears on repair). **janus128: PASS.**
- `w1b_promotion_atomicity` (unit): working append → promotion lands
  and chains; forced append failure → the file-state record stands
  unpromoted. **janus127: FAIL** (no promotion exists to land).
  **janus128: PASS.**

## 2. Item 2 — Ceremony warning suppression

**Where:** `janus.py:_post_suppression` (response construction).

**What changed:** when `_ceremony_state()` holds, the placement
returns the bare acknowledgment `201 {"result": "suppression
placed"}` — the near-match variant scan is not even run. The order
places and `SUPPRESSION_PLACE` chains identically, and the
non-ceremony response (with `warning_near_matches`) is byte-identical
to 1.2.7's. (R10-C01a: the warning disclosed historical raw plate
forms to a key-only supervisor while every data surface was fenced.)

**Discriminating case:** `w2_ceremony_warning` — reads seeded under
raw variant forms (`CAB 123`, `CAB-123`, `cab123`); ceremony boot
(verified: /health state `ceremony`, /search 503); key-only
supervisor placement → 201, no `warning_near_matches` key,
suppression active, SUPPRESSION_PLACE chained. **janus127: FAIL**
(response carries the variants). **janus128: PASS.**

## 3. Item 3 — Ceremony hold uniformity

**Where:** `janus.py:_post_holds` (hit-scope lookup + response).

**What changed:** in the ceremony state, hit-scope placement answers
ONE uniform response — `201 {"result": "hold placed", "review_by":
<date>}`, no `hold_id` — whether the hit exists, does not exist, or
exists under a different case. The hold is inserted and
`HOLD_PLACE` chained only when the hit exists and its case matches;
the unplaceable outcomes place nothing and chain nothing (a
HOLD_PLACE for a hit that is not there would corrupt the record the
uniformity protects). The case-mismatch outcome is folded into the
uniform answer because 1.2.7's 400 named the hit's own case number —
the same disclosure class as the 404 (R10-C01b; the case-number leak
was also noted by Claude A). Body-only validation (bad `ref` shape,
bad `review_by`) still answers 400 in ceremony: it depends only on
the request body, identically for existing and missing hits, so it
carries no existence signal. Case-scope holds take no hit lookup and
are unchanged. Outside the ceremony state every answer is 1.2.7's,
in 1.2.7's order (404 before case-mismatch 400 before review_by
validation), and the success body keeps its `hold_id`.

**Discriminating case:** `w3_ceremony_hold_uniform` — a real hit is
seeded (hotlist + ingest under LAB, rebooted into ceremony);
placements on the real id and on id 999999 return identical status
AND body; exactly one hold exists, for the real hit. **janus127:
FAIL** (201 with hold_id vs 404 "no hit with that id").
**janus128: PASS.**

## 4. Item 4 — Ceremony releases fenced

**Where:** `janus.py:CEREMONY_FENCED_POST` (the set gains
`"/holds/release"` and `"/suppressions/release"`), and the comment
above the set (corrected: placements stay open in ceremony; releases
no longer do).

**What changed:** nothing else — the existing dispatcher check
(`_ceremony_state()` + human role + `_ceremony_fenced("POST", path)`)
now refuses both release endpoints in ceremony state with the
established posture: 503 + throttled `CEREMONY_REFUSED` chain entry.
This is V9's reasoning (a release removes protection; it is not a
safety write) applied to the ceremony fence, per synthesis §3.3.
Machine roles are untouched (the fence binds human roles only), and
outside the ceremony state the releases behave exactly as in 1.2.7.

**Discriminating case:** `w4_ceremony_releases_fenced` — a
suppression and a case hold stand; in ceremony, both release
endpoints answer 503 to a key-only supervisor, CEREMONY_REFUSED is
chained, and both protections remain active. **janus127: FAIL**
(both releases served: 200/200, the hold actually released).
**janus128: PASS.**

## 5. Item 5 — G1 reactivation

**Where:** `janus.py:_post_hotlist` (the non-supervisor submission
upsert).

**What changed:** the conflict clause now reads
`WHERE hotlist_members.pending=1 OR hotlist_members.active=0`, and
the DO UPDATE also sets `active=1, pending=1`. A re-submission
against an INACTIVE row (an expired/swept listing, active=0,
pending=0) therefore reactivates the row into the supervisor pending
queue with the submission's fresh category/submitter/expiry, instead
of 1.2.7's silent drop. V2 is preserved exactly: a LIVE row
(active=1, pending=0) matches neither disjunct and is never touched;
a PENDING row (pending=1, either active value) updates as before —
for the swept-pending shape (active=0, pending=1) the update also
restores the canonical active=1 the fresh-insert shape carries.
The response remains the uniform 202 in every outcome (V2's no-leak
property is response-side and is unchanged).

**The chain entry reflects what actually happened:** a pre-read of
the conflicting row (same conflict key) classifies the outcome, and
`HOTLIST_ADD_PENDING` now carries an `effect` field —
`"new"` (fresh insert), `"pending_updated"` (a pending row
refreshed), `"reactivated"` (an inactive row reactivated), or
`"live_row_no_change"` (the V2 case: the submission changed
nothing). 1.2.7 chained the same entry with no effect field for all
four outcomes, including the G1 drop it misrecorded as a submission.
The entry kind is unchanged; the effect is chain-side information
for chain readers, per the U6 design precedent.

**Discriminating case:** `w5_g1_reactivation` — supervisor lists a
plate with a past expiry; `hotlist_sync.py` sweeps it to (0,0); a
detective re-submits the same plate/case → 202, the plate appears in
GET /hotlist/pending, the row reads (active=1, pending=1), and the
chained entry's effect is `"reactivated"`. **janus127: FAIL** (row
stays (0,0), queue empty, effect null). **janus128: PASS.**

## 6. The W battery

New file `tests/run_w128_cases.py` (6 cases: w1, w1b, w2, w3, w4,
w5), in the V-battery pattern — every case runs against both trees
and passes only when the invariant holds on janus128 and fails on
janus127. Builder's standalone run (scratch/w-battery-dev1.log):

**W battery: 6/6 cases pass** — every case discriminates. The
baseline legs independently reproduce the chair's C01/C02
observations (record never promotes and the fence auto-clears on
repair; the 201/404 hold split with hold_id disclosed; releases
served 200/200 in ceremony; the G1 resubmission dropped with a null
effect).

`run-next.sh` gains a `w-battery` leg (baseline janus127); the
v-battery leg keeps its janus126 baseline.

## 7. Full battery

**Result: SUCCESS — one uninterrupted cold run of the tree's own
`./run-next.sh` on final code, exit 0, every leg PASS.**
Log: `scratch/battery-20261126-205707.log` (also
`scratch/battery-latest.log`; console line in
`scratch/run2-console.log`).

| Leg | Result |
|---|---|
| builders (run_tests.py) | PASS — 335 checks, 335 passed, 0 failed |
| round4 | PASS — 41 verdicts, only the A9b contrast control confirmed |
| round5 | PASS — 21 verdicts, none reproduced |
| round6 | PASS |
| Q + invariants | PASS — Q battery 35/35 |
| R battery | PASS — 20/20 |
| load envelope | PASS — COMPLETE, 500/500 appends at 0/3/6 burners in both directions, chain verifies |
| S battery | PASS — 25/25 (S10: 0 dropped-sample retries) |
| T battery | PASS — 20/20 |
| U battery | PASS — 21/21 (u11 version sweep green on the re-aimed literals) |
| V battery | PASS — 19/19 against the janus126 baseline |
| W battery | PASS — 6/6 against the janus127 baseline |

**Run history, disclosed in full.** This was the second launch.
Run #1 (`scratch/battery-20261126-201702.log`) completed builders,
round4, round5, round6 and Q+invariants (all PASS), then failed the
R leg on R15 alone — its shipping-build version literals still said
1.2.7 (see judgment call 4; R15's substantive checks passed), and
was then terminated by a SIGTERM from the runtime during the
load-envelope leg (the same session-interruption failure mode the
1.2.7 build recorded). The R battery was re-run standalone after
the re-aim: 20/20 PASS (`scratch/r-battery-rea.log`, R15 green,
baseline still failing on its own 1.2.2 literals). Run #2 above was
launched detached and ran cold, start to finish, with no leg
restarted. Production code was identical in both runs; the only
change between them was the R15/u11 test-literal re-aim.

**Measurement variance (not a gate).** The load envelope's
health-availability measurement in run #2 read {samples: 20,
answered: 20, dropped: 0, wrong_values: 20} — every sample
answered, none dropped, but all 20 counted as non-full-payload
"wrong values" under saturation. 1.2.7's two recorded measurements
were {18 answered, 2 dropped, 4 wrong} (builder) and {20/20/0/0}
(verifier). Per Round 9 judgment call 4 (ratified in Round 10)
this figure is a disclosed measurement, not a gate; the gate —
append completeness under load — held at every burner level in
both directions. The chair may wish to note the wrong-values
figure for the pilot-hardening register; nothing in the five
items touches the /health path.

**Baseline integrity.** janus127/ is byte-untouched:
`md5sum -c` against the copy-time record
(`scratch/baseline-127-md5.txt`) passes for janus.py
(3161d9d9…), sentinel.py (1fc78750…) and scripts/compact.py, and
no non-`__pycache__` file in janus127/ carries a modification time
after the copy.

## 8. The V5b note (synthesis §5 item 11) — answered, not fixed

Claude B's note: on the fence SET path, a chain-append failure
leaves the service unfenced, because the fence reads only the stored
record.

**Item 1 does not touch this.** The promotion branch is a sibling of
the set path, not a modification of it; the set path's code is
byte-identical to 1.2.7's. The behavior in 1.2.8 is exactly 1.2.7's:
`_anchor_apply` appends `STARTUP_ANCHOR_MISMATCH` first and, if the
append raises, returns without writing the record — and
`anchor_fenced()` returns `anchor_mismatch()`, which reads only the
stored meta record (janus.py, `anchor_mismatch()`). So during a
chain-append outage an evaluated mismatch founds no fence; the
service runs unfenced until a later evaluation's append succeeds
(the live path re-evaluates on the ~5 s `anchor_fenced()` cadence,
so the window closes with the first successful append; the boot path
retries at the next boot). No record of the missed transition exists
beyond the append failure itself. That asymmetry is pre-existing
1.2.7 behavior, rated LOW by its finder, and it is reported here per
the commission — not fixed, as fixing it is outside the five items.

For contrast, the NEW promotion path fails the other way: an append
failure there leaves the file-state record standing — the fence
stays UP on the old reason (verified by w1b leg 2). The clear path
is likewise unchanged from 1.2.7 (append-first; a failure leaves the
record standing).

## 9. Version literals

Following the tree's convention ("the literal follows the shipping
build"): janus.py docstring + `VERSION`, sentinel.py docstring +
`REGISTRY_VERSION`, scripts/sentinel_audit.py `version`,
scripts/backup.py manifest `noctua`, COMPACT.md's two lines, and
run-next.sh's header now read 1.2.8. Historical annotations in code
comments (e.g. "1.2.7 (V5)") are history and were not rewritten.
Two test files assert version literals; their expectations were
adapted 1.2.7 → 1.2.8 and the pre-adaptation files preserved beside
them (`tests/run_tests.py.orig-127`, `tests/run_v127_cases.py.
orig-127`, each with an R-F header note) — the 1.2.7 builder's exact
precedent (run_tests.py.orig-126). No assertion was weakened; the
adapted literals are enumerated in judgment call 4.

## 10. Judgment calls (for chair adjudication)

1. **Promotion chain kind.** The promotion chains as a new kind,
   `ANCHOR_REASON_PROMOTED`, rather than reusing
   `STARTUP_ANCHOR_MISMATCH`. Rationale: the fence record is
   evidence; a distinct kind makes the transition self-describing
   to a future reader (auditor, court, council) without parsing
   payloads, and keeps "a mismatch was first recorded" distinct
   from "a standing record was promoted". The promoted record also
   carries `promoted_from`, and the chain payload preserves
   `prior_reason` + `prior_detected`, so the file-state episode is
   not erased by the promotion. If the chair prefers the existing
   kind, the change is one string.
2. **Ceremony hold uniformity — the response shape.** The uniform
   body is the placed leg's acknowledgment minus `hold_id`:
   `201 {"result": "hold placed", "review_by": ...}` on both legs.
   The unplaceable leg places nothing and chains nothing, so the
   acknowledgment is, for that leg, a uniformity fiction of the
   same kind the codebase already accepts (U6's uniform 202 for
   submissions that change nothing; V13's uniform 409). The
   case-mismatch outcome is folded in (see §3). The operator
   learns the true state from the holds list after provisioning.
   Flagged because the commission named only the 201-vs-404 split;
   the case-mismatch 400 and the hold_id were folded in as the
   same disclosure class.
3. **G1 chain `effect` field.** "The chain entry reflects what
   actually happened" is implemented as an `effect` field on the
   existing `HOTLIST_ADD_PENDING` kind (four values, §5), computed
   from a one-row pre-read on the conflict key — not as new chain
   kinds. The response side is untouched (uniform 202), so no new
   oracle opens; the effect is visible only to chain readers, by
   design.
4. **Test-literal adaptations.** Four test files assert the
   shipping build's version literal, and each declares the
   convention itself (R15: the literals "name the SHIPPING build"
   and are "re-aimed every build"; u11: "the expected literal
   follows the build"). All four were adapted 1.2.7 → 1.2.8 with
   .orig-127 preservation, per the tree's R-F precedent:
   tests/run_tests.py (registry_version at the health check, the
   P10 label, REGISTRY_VERSION), tests/run_v127_cases.py (the
   v15f sentinel_audit version check), tests/run_r123_cases.py
   (R15's version_ok/registry_ok), tests/run_u126_cases.py
   (u11's sweep). The diffs against the .orig-127 files are the
   literals and their own comments only — verified by direct
   diff. Without this the version bump itself fails the builders'
   suite, the R battery, the U battery, and the V battery on
   their own literals. No other test content was touched. (The
   first full-battery run caught R15 before its re-aim landed;
   see §7.)
5. **W battery as a new file.** The five items' cases live in
   tests/run_w128_cases.py rather than being appended to the V
   battery: the V battery remains 1.2.7's acceptance record
   untouched (apart from call 4's literal), and run-next.sh runs
   both, each against its own baseline (V vs janus126, W vs
   janus127).

## 11. Scope discipline

Nothing outside the five items was changed in production code.
G3 (register #3) is NOT in this build — the commission's five items
are V5 promotion, the three ceremony items, and G1. sentinel.py's
only changes are the two version literals; scripts/ changes are the
two version literals (sentinel_audit.py, backup.py). janus127/ was
not modified (re-verified in §7).
