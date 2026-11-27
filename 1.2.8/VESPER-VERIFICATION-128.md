# VESPER-VERIFICATION-128 — chair cold verification of NOCTUA 1.2.8

Verifier: Vesper (chair). Date: November 26, 2026.
Build record: janus128/TRACK-128-REPORT.md. Commission: council10/SYNTHESIS.md §6.

## Method

One uninterrupted cold run of the tree's own `./run-next.sh`, launched by the
chair against the builder's final code, log
`janus128/scratch/battery-20261126-154647.log`, plus chair code spot-checks of
the commissioned changes. janus127 confirmed untouched before the run
(janus.py md5 3161d9d968e696c4ae001e0eea61f47e; sentinel.py md5
1fc7875056a38e6e04f410cf18b0dbef — both match the 1.2.7 verification record).

## Result: VERIFIED — BATTERY RESULT: SUCCESS

Every leg PASS: builders · round4 · round5 · round6 · Q + invariants ·
R battery · load envelope (COMPLETE) · S battery · T battery · U battery ·
V battery 19/19 · **W battery 6/6**.

## The five commissioned items, as executed in the chair's run

- **W1 (V5 reason promotion)** — baseline 1.2.7: torn-line fence records
  `checkpoints_malformed`, never promotes, clears after accept with the
  disagreement unrecorded. 1.2.8: the record promotes to
  `checkpoint_disagreement` with bad_ids recorded and the promotion chained;
  the fence still stands after repair; it clears only after acceptance.
- **W1b (promotion atomicity)** — a failed promotion append leaves the prior
  record standing (fails closed).
- **W2 (ceremony warning)** — 1.2.8 ceremony suppression placement returns
  `{"result"}` only (no `warning_near_matches`); placement and chaining
  unchanged; non-ceremony behavior is the V battery's standing coverage.
- **W3 (ceremony hold uniformity)** — ceremony /holds answers are
  byte-identical 201 bodies for existing and missing hits; the hold is
  placed and chained only for the real hit.
- **W4 (ceremony releases fenced)** — both release endpoints answer 503 in
  ceremony state with CEREMONY_REFUSED chained; suppression and hold remain
  active. (1.2.7 baseline: 200/200, hold released.)
- **W5 (G1 reactivation)** — a re-submitted expired listing enters the
  pending queue on 1.2.8 (row active=1, pending=1; chain effect
  `reactivated`); on 1.2.7 it was silently dropped with a null effect.

## Chair code spot-checks

- Promotion branch (janus.py ~2305–2331): promotes ONLY a file-state record;
  `ANCHOR_REASON_PROMOTED` is chain-appended before the meta mutation; an
  append failure returns without landing the transition.
- `CEREMONY_FENCED_POST` (janus.py:3429) now includes `/holds/release` and
  `/suppressions/release`.
- G1 clause (janus.py:5339): `OR hotlist_members.active=0` in the upsert's
  conflict WHERE, with `active=1, pending=1` in the DO UPDATE.

## Builder judgment calls — chair adjudication

All five RATIFIED: (1) the `ANCHOR_REASON_PROMOTED` chain kind with
`promoted_from` on the record — the promotion is itself an auditable event
and belongs in the chain; (2) the ceremony hold uniform body folding the
case-mismatch response into the same uniform answer — same disclosure
class, verified by W3; (3) G1's `effect` field on the existing
HOTLIST_ADD_PENDING kind rather than new kinds; (4) version-literal re-aims
in four test files with `.orig-127` preservation, per the R-F precedent
(the R leg passes cold in this run); (5) the W battery as a new file with
its own run-next.sh leg, the V leg keeping its janus126 baseline.

## Variances (measurements, not gates)

The builder's run recorded load-envelope health availability of
{20 answered, 0 dropped, 20 wrong_values} under saturation; the chair's run
passed the load leg with append completeness intact (500/500). Health
availability under saturation remains a measurement per the ratified Round
10 judgment call, and the wrong-values reading stays on the register for
pilot-phase triage.

## Verdict

1.2.8 implements the complete Round 10 §6 commission; the discriminating
cases fail on 1.2.7 and pass on 1.2.8; the full battery is green in a single
cold chair run. The chair issues the convergence addendum to
council10/SYNTHESIS.md: **the NOCTUA code loop is CONVERGED under criteria
1–4.** Deployment remains gated (independent pilot pen test; Ben Hooper's
answers) — convergence certifies the code gate, not deployment readiness.
