# Chair verification — 1.2.8 seam-check claims (C2, P2, P1, P5 leg)

Chair's independent reproductions of the Claude seam-check seat's three
open claims, executed Nov 26, 2026 (log timestamps 2026-11-27T05:40–05:42Z)
against a scratch COPY of the janus128 tree (`seamcheck/chair-tree/`,
janus.py md5 `60081d1827eef9104826faaac0384264`, identical to
`janus128/janus.py`; the real tree was never modified).

Method note: the seat's review file tripped an automated execution-risk
check when read, so the seat's own probe bundle and commands were NOT
used. All probes are the chair's own scripts (`chair_anchor_probes.py`,
`chair_ceremony_probes.py`, re-runnable via `run-next.sh`; full output in
`chair-probes.log`), built on the tree's own T-battery harness pattern.
The seat's claims were treated as hypotheses and re-derived from scratch.

---

## C2 — ceremony case-scope hold_id oracle — **CONFIRMED**

Setup: seeded under LAB (hit 1 = plate CHC111, case 2027-1001, verified;
hit 2 = plate CHC222, case 2027-1014, left PENDING/unverified), then
rebooted with LAB off — `/health` totp state `ceremony`, `/search` 503.
All placements by the key-only supervisor (sgt.reyes).

Hit-scope responses were byte-identical across all four legs —
`201 {"result": "hold placed", "review_by": "2026-12-27"}` — so fix 3's
uniformity holds for the hit scope itself. The side channel is exactly
where the seat said it is:

| hit-scope attempt | gap to next case-scope hold_id | chain entries added by the hit attempt* |
|---|---|---|
| real hit, its own case | **2** | **+1** |
| nonexistent id (999999) | **1** | **0** |
| real hit, wrong case | **1** | **0** |
| real unverified hit, own case | **2** | **+1** |

\* The chair's raw chain delta measured across (hit attempt + the
following case-scope hold) was 2/1/1/2; the case-scope hold itself always
chains one HOLD_PLACE, so the hit-attempt-attributable delta is 2−1,
1−1, 1−1, 2−1 = **+1/0/0/+1 — the seat's /audit/root figures exactly**.
`/audit/root` is readable by the key-only supervisor in ceremony (200,
`{"root": …, "entries": 15}`), so both channels the seat named are live:
the hold_id gap needs no audit access at all, and the root-entry count
confirms it. Legs 1 vs 3 (same hit, own case vs candidate case) differ,
so iterating candidate cases reveals which case a hit stands on — the
case-number disclosure is real, not just hit existence.

Response-shape check (asked for explicitly): the case-scope ceremony
response is `{"result", "hold_id", "review_by"}`; the uniform hit-scope
shape is `{"result", "review_by"}`. **`hold_id` is the only differing
field.**

Why, in code (`_post_holds`): the ceremony-uniform return is scoped to
`if ceremony and d["scope"] == "hit"` (janus.py:5605); every other
placement falls to the general return carrying `"hold_id":
cur.lastrowid` (janus.py:5610–5612). A placed hit-scope hold still
executes the shared `INSERT INTO holds` (janus.py:5591) and consumes an
AUTOINCREMENT id it never returns; an unplaceable attempt returns early
(janus.py:5581–5589) inserting and chaining nothing. The counter is
therefore a perfect placed/not-placed bit, readable by placing any
case-scope hold (an open, legitimate ceremony action).

Severity note (chair's observation, agreeing with the seat's own limit):
the same supervisor can already read the audit chain in ceremony, whose
entries expose hit existence and hit↔case links — the oracle discloses no
fact the chain doesn't. What it breaks is fix 3's claim: the /holds
endpoint's answers are not uniform in ceremony, only its hit-scope
response bodies are.

## P2 — corrupt anchor record: permanent fence, /health down — **CONFIRMED** (all four sub-claims)

Setup: healthy install fenced as `checkpoints_malformed` (torn line);
the stored `anchor_mismatch` meta value was then replaced in the DB with
the unparseable string `{"reason": "checkpoint_disagreem` (unterminated).
The checkpoints file was healthy or repairable throughout the later legs.

- **(a) CONFIRMED.** A genuine foreign-signed disagreement was written to
  the checkpoints file and evaluated across ~13 s of cadence: the meta
  record stayed byte-identical to the planted corrupt string, the audit
  table gained **zero** rows (15 → 15), and no `ANCHOR_REASON_PROMOTED`
  was chained. The disagreement leaves no trace.
  Why: `_anchor_apply`'s promotion branch (janus.py:2305–2330) parses the
  prior record under a guard; on `ValueError` prior = {}, whose reason is
  not in `ANCHOR_FILE_STATE_REASONS`, so no promotion fires — and the
  record-setting branch (janus.py:2291) requires `recorded is None`, so
  nothing else is written either.
- **(b) CONFIRMED.** `GET /health` returned **500** with body error
  `internal: Unterminated string starting at: line 1 column 12
  (char 11)`. Why: the health builder embeds
  `json.loads(_meta_get("anchor_mismatch"))` **unguarded**
  (janus.py:9537–9538); the `ValueError` escapes the handler and
  `do_GET`'s catch-all (janus.py:8794) turns it into the 500. The
  diagnostic surface dies on exactly the state an operator would need it
  for.
- **(c) CONFIRMED.** Both keys got **409** with the verbatim error: "the
  current anchor mismatch is unknown — only a checkpoint_disagreement
  can be accepted by two keys; an unreadable or missing checkpoints file
  must be repaired, not accepted". Why: `_anchor_accept` parses the
  record under a guard → {} → the reason gate at janus.py:6207 fires
  before any role/pending logic.
- **(d) CONFIRMED.** After the checkpoints file was repaired to the good
  file and the cadence driven ~13 s: still 503, record unchanged. After a
  full restart on the same directory: still 503, /health still 500,
  record unchanged. Why: on a clean evaluation `_anchor_apply`
  (janus.py:2255–2270) reads prior reason as `""` — neither
  `checkpoint_disagreement` (subset gate) nor a member of
  `ANCHOR_FILE_STATE_REASONS` (auto-clear) — so it returns and the fence
  stands; the boot path (`_startup_anchor_check`, janus.py:2525–2530)
  applies the same function and lands in the same place. The only remedy
  the system names — repair the file — cannot help, because the defect is
  in the DB record, not the file. **No in-system recovery path exists
  short of DB surgery.** The state fails closed throughout (nothing
  unaccepted ever cleared), reachable only via DB corruption or
  tampering — agreeing with the seat's severity framing.

No divergence from the seat on any P2 sub-claim, including its exact
409 wording.

## P1 — record does not track the live disagreement; accept takes the live file — **CONFIRMED**

Sequence executed: torn line → fence `checkpoints_malformed`; foreign
checkpoint X (id `[5, a3a068c2…]`) appended → record promoted to
`checkpoint_disagreement`, `bad_ids = [X]`, `promoted_from =
checkpoints_malformed`, `ANCHOR_REASON_PROMOTED` chained. Then X was
removed and a different foreign checkpoint Y (id `[5, 2d4e0017…]`)
introduced, cadence driven ~13 s:

- The fence record stayed **byte-identical** — still naming X, same
  bad_ids, same detected stamp. Y's root appears in **no** audit payload
  and **not** in /health (`anchor_detail.bad_ids` = [X] only). The fence
  stood (503) throughout — nothing unaccepted auto-cleared.
- Two-key accept performed while only Y was present: supervisor 200,
  auditor 200 ("anchor mismatch cleared"); the recorded
  `anchor_accepted_ids` afterwards = **[Y] only** (`y_accepted: true`,
  `x_accepted: false`); the fence then cleared (/hits 200). The two keys
  permanently accepted a checkpoint that neither the record nor /health
  ever displayed to them.

Why, in code — the accept path and the record read different sources:
- The record is written by `_anchor_apply`'s promotion branch
  (janus.py:2316–2330) **only** when the prior reason is a file-state
  reason; a record already standing as `checkpoint_disagreement` is left
  exactly as-is, so later disagreements never update it.
- `_anchor_accept`'s gate reads only the **record's** reason
  (janus.py:6202–6215 — reason == checkpoint_disagreement, satisfied by
  X's stale record), but its confirm leg computes the accepted ids from
  the **live file**: `for cp in _bad_checkpoints(): accepted.add(...)`
  (janus.py:6258–6259), then deletes the record. Whatever disagrees at
  confirm time is what gets accepted.
- The auto-clear gate, by contrast, compares the **record's** bad_ids
  against the accepted set (janus.py:2261–2267) — so auto-clear tracks
  the recorded disagreement while acceptance tracks the live one. That
  asymmetry is the whole finding.
- /health's `anchor_detail` is the record verbatim (janus.py:9537–9538),
  so the display can only ever show X.

The fence's safety invariant holds (no silent clear — the seat said the
same); the open question the seat left to the chair is whether "the
record tracks the live disagreement, and acceptance binds to what the
record showed the two keys" is also an invariant. On the executed facts,
it currently is not.

## P5 spot-check (one leg) — **CONFIRMED**

The seat's key seam: after promotion to `checkpoint_disagreement` (X
recorded), the checkpoints file was replaced with the good file plus a
fresh torn line — a new file-state episode with X gone. Across ~13 s of
evaluations: /hits stayed 503, the record stayed
`checkpoint_disagreement` with bad_ids unchanged and the meta value
**byte-identical** to the promoted record. The record does not regress
to a file-state reason; the original V5 bug does not reappear one level
up on this leg.

---

## Summary for the ruling

| claim | seat | chair |
|---|---|---|
| C2 | SEAM DEFECT | **CONFIRMED** — gap pattern 2/1/1/2 and root-entry +1/0/0/+1 reproduced exactly; `hold_id` is the only extra field in the case-scope response |
| P2 | SEAM DEFECT (fails closed, low) | **CONFIRMED** — all four sub-claims (a)–(d) reproduced, incl. the verbatim 409 and the /health 500 text |
| P1 | AMBIGUOUS | **CONFIRMED as described** — record byte-identical under Y; accept bound to the live file and accepted Y unseen; the classification (defect vs acceptable) remains the chair's call |
| P5 (key seam) | HOLDS | spot-check leg **CONFIRMED** — no regression after promotion |

No observation differed from the seat's report in substance. The one
measurement nuance (C2 chain deltas) is a counting-offset artifact and
resolves to the seat's exact figures.
