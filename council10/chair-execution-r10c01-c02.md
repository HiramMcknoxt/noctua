# Chair Execution — Round 10 acceptance checks R10-C01 / R10-C02
# VESPER · the evening watch

**Executor:** chair execution seat (cold local run, 2026-11-26).
**Tree under test:** `~/workspace/noctua-1.0/janus127/` (NOCTUA 1.2.7), unmodified.
**Fixtures:** synthetic only, via the tree's own harness patterns
(`tests/run_t125_cases.py` Boot/req; `tests/run_v127_cases.py` V5 anchor pattern).
**Scripts + raw captures:** `chair-execution/scratch/check_c01.py`,
`check_c02.py`, `c01-results.json`, `c02-results.json`.

Both checks were left by the ChatGPT static seat expressly "subject to
executing-seat reproduction." Both are now executed.

---

## CHECK 1 — R10-C01 (V4 ceremony disclosure): **CONFIRMED**

### Claim
During CEREMONY state, the permitted safety writes disclose historical plate
data in their responses: (a) `POST /suppressions` returns
`warning_near_matches` containing historical plate variants
(janus.py:5615–5627); (b) `POST /holds` distinguishes existing from
nonexistent hits (janus.py:5453–5462).

### Procedure
1. Booted janus127 fresh with `NOCTUA_LAB=0` and **no TOTP enrollments ever**
   (ceremony state by the V4 definition: `_ceremony_state()` =
   not provisioned, not lab, not demo).
2. Seeded synthetic historical reads with `plate_raw` values
   `["CAB 123", "CAB-123", "cab123", "CAB123", "ZZZ999"]` (canonical plate
   `CAB123`; `ZZZ999` is an unrelated control) and one synthetic hit
   (id 1, case `2027-1001`).
3. As key-only supervisor `sgt.reyes` (API key only, no second factor):
   control `GET /search`; `POST /suppressions` for plate `CAB123`;
   `POST /holds` on the existing hit id and on nonexistent id 999999.
4. Repeated both writes as key-only non-supervisor `det.okafor` (detective).

### Observed
Ceremony state is genuine, not a fixture artifact — `/health` reports
`"totp": {"ceremony": true, "state": "ceremony", "provisioned": false,
"lab_mode": false, "enrolled_active": 0}`, and the control call was refused
by the ceremony fence:

```
CONTROL key-only SUP GET /search -> HTTP 503
{"error": "this installation has not completed second-factor provisioning
 — the data surface is closed to key-only accounts until provisioning
 completes (state: ceremony)"}
```

(a) The suppression placement succeeded **and disclosed the historical raw
variants in its response body**:

```
C01a key-only SUP POST /suppressions plate=CAB123 -> HTTP 201
{
  "result": "suppression placed",
  "warning_near_matches": [
    "CAB 123",
    "CAB-123",
    "cab123"
  ]
}
```

These three strings are the historical `reads.plate_raw` values on file.
(The exact-match raw `CAB123` and the unrelated control `ZZZ999` were
correctly absent — the disclosure is precisely the near-match variant set
the claim named.)

(b) The hold placement **distinguished an existing hit from a nonexistent
one**, disclosing existing-hit status:

```
C01b key-only SUP POST /holds EXISTING hit id=1 -> HTTP 201
{"hold_id": 1, "result": "hold placed", "review_by": "2026-12-26"}

C01b key-only SUP POST /holds NONEXISTENT hit id=999999 -> HTTP 404
{"error": "no hit with that id"}
```

Key-only **non-supervisor** on the same calls — role refusals, no data:

```
DET POST /suppressions -> HTTP 403 {"error": "suppressions are supervisor-only"}
DET POST /holds        -> HTTP 403 {"error": "holds are placed by a supervisor"}
```

### Ruling — CONFIRMED
In ceremony state, a key-only supervisor's permitted safety writes return
historical plate-record information (the suppression response) and
existing-hit status (the hold response split), while the fenced data
surfaces refuse the same credential. The disclosure ChatGPT claimed exists
in live responses, in both named shapes. The seat's required invariant —
ceremony safety writes may change protective state and return an
acknowledgment, but must not disclose historical read-derived information
or existing-hit identity — is violated by 1.2.7 as shipped. Per
council9/SYNTHESIS §4, an executed confirmation reopens the U9/V4
adjudication.

---

## CHECK 2 — R10-C02 (V5 reason promotion): **CONFIRMED**

### Claim
The anchor fence records a mismatch reason only when no mismatch is
already recorded (janus.py:2283–2293), so a file-state reason recorded
first is never promoted when a genuine checkpoint disagreement is later
observed — and a subsequent clean file evaluation auto-clears the fence
despite the unaccepted disagreement (auto-clear governed by the recorded
reason at 2244–2263).

### Procedure
Two harness boots (A = install under test, B = foreign install), each
ingesting one read and publishing a signed checkpoint via the tree's own
`checkpoint.py`, exactly as the V5 battery case does. On A, driving the
live evaluation path (data-surface requests past the 5 s
`anchor_fenced()` cadence), with the recorded state read directly from
`meta.anchor_mismatch` after each step:

1. **Step 1** — append a torn line (`{"seq": 99, "root": "abc`) to A's
   checkpoints file; wait for the fence.
2. **Step 2** — replace the file with A's good checkpoints **plus B's
   foreign checkpoint line** (a genuine disagreement: foreign root/signature
   against A's chain); drive live evaluations for 10 s; read the record.
3. **Step 3** — restore the file to A's good checkpoints only; observe
   whether the fence clears.
4. **Control** — append B's foreign line again, with no prior record
   standing; read the record.

### Observed
Baseline: no recorded mismatch.

**Step 1** — fence set with the file-state reason; `/hits` refused 503:

```json
{"reason": "checkpoints_malformed", "malformed_lines": 1,
 "chain_entries": 15, "detected": "2026-11-26T15:59:49Z"}
```

**Step 2** — after 10 s of live evaluations against the good+foreign file,
the recorded state is **byte-identical to step 1** — same reason, same
`detected` timestamp, still claiming `malformed_lines: 1` of a file that
no longer contains a malformed line:

```json
{"reason": "checkpoints_malformed", "malformed_lines": 1,
 "chain_entries": 15, "detected": "2026-11-26T15:59:49Z"}
```

The fence stood throughout (`/hits` 503), but it stood **for the stale
file-state reason**; the genuine disagreement was never recorded.

**Step 3** — on the clean file the fence **auto-cleared**: the
`anchor_mismatch` record was deleted, `/hits` returned 200, and the chain
carries the clear, gated on the stale reason:

```
ANCHOR_CLEARED payload: {"prior_reason": "checkpoints_malformed",
 "checkpoint_entries": 5, "matches_chain": true, "chain_entries": 16, ...}
```

**Control** — the identical good+foreign content, evaluated with no prior
record standing, records the disagreement properly:

```json
{"reason": "checkpoint_disagreement",
 "bad_ids": [[5, "c53b7ce2519826f93dfe7ead53a5c0da4d56d6788991f56c2d0785e759445a4a"]],
 "bad_entries": ["5"], "checkpoint_entries": 5, "chain_entries": 28,
 "detected": "2026-11-26T16:00:10Z"}
```

So the step-2 file genuinely was a checkpoint disagreement in this
install — the only reason it never governed the fence is that the
file-state record pre-existed it.

### Ruling — CONFIRMED
The sequence the claim describes reproduces exactly: file-state fence
first → disagreement observed but never promoted (recorded reason and
detail remain the stale file-state entry) → clean file evaluation
auto-clears the fence, with the disagreement neither recorded nor
accepted. The seat's required invariant — once an unaccepted historical
checkpoint disagreement has been observed, a later clean file evaluation
must not clear the fence — is violated by 1.2.7 as shipped. The direct
Round 9 repair (a disagreement recorded *first* is sticky) holds; the
adjacent reason-transition defect is real. V5 reopens on executed
evidence.

---

## Summary for the chair

| Check | Finding | Ruling |
|---|---|---|
| R10-C01 | Ceremony safety writes disclose historical plate variants (suppression response) and hit existence (hold response split) to a key-only supervisor | **CONFIRMED** |
| R10-C02 | A pre-existing file-state fence reason is never promoted to `checkpoint_disagreement`; a later clean evaluation auto-clears despite an observed, unaccepted disagreement | **CONFIRMED** |

Both of the ChatGPT seat's deployment-blocking claims survive execution.
Its NOT CONVERGED vote stands on reproduced evidence.
