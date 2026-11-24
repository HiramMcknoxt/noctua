# NOCTUA Council — Round 5 Brief (review of NOCTUA 1.2.1)

You are one seat on a four-seat hostile code-review council (ChatGPT,
Gemini, Claude ×2) reviewing NOCTUA, an open-source city-owned ALPR
system (Janus API + Sentinel hash-chained audit log + the Compact, a
reciprocal-audit data-sharing pact between agencies). This is round 5.
Rounds 2, 3, and 4 all returned NOT CONVERGED. Round 4's findings were
consolidated into patch items P1–P14; a patch build, **NOCTUA 1.2.1**,
claims to implement all of them. Your job: verify that claim against
the code, hunt for NEW defects (especially in the new code), and vote
on convergence. Reviewer assertions don't count — yours included.
Where you can, prove it: run the code, cite file:line, or show the
exact request/response.

## MODEL PROTOCOL (standing instruction from the project owner)

Use the best model and the highest reasoning/effort level INCLUDED in
the owner's existing subscription. Do NOT select any model that
requires extra usage credits (e.g. Fable) and do NOT select
Ultra-class credit-heavy tiers. If the top tier is credit-gated, step
down to the best included model. Your review MUST begin with a line
stating the actual model and effort used, as shown in the UI.

## What you are given (attachments)

- `1.2.1/janus.py`, `1.2.1/sentinel.py` (individual files)
- scripts-combined.txt — the 12 scripts under `1.2.1/scripts/`, each
  under a `FILE:` header
- docs-combined.txt — `1.2.1/TRACK-121-REPORT.md` (the builders'
  report), `1.2.1/COMPACT.md`, and `council4/SYNTHESIS.md` (the
  round-4 consolidation your patch was built from)
- `1.2.1/tests/run_tests.py` — the builders' suite (312 checks)
- attacks-combined.txt — the independent attack suite a round-4 seat
  wrote (`council4/attacks/` in the repo). You may reuse, extend, or
  ignore it.
The same files are in the public repo at
github.com/HiramMcknoxt/noctua under `1.2.1/` and `council4/`.

## Claims to verify (treat as UNVERIFIED until you check the code)

1. Attack suite vs 1.2.1: zero CONFIRMED defect lines — the only
   CONFIRMED is A9b, the suite's contrast control (it prints CONFIRMED
   when Janus's startup anchor correctly flags a rewritten history).
   32 verdicts NOT REPRODUCED. Eight attacks print nothing because the
   harness dies in setup when the setup itself exercises a now-refused
   behavior (client-supplied rotation seed; env-key-only boot over an
   unpinned chain; HOLD_DAYS=400).
2. Builders' suite: 312/312.
3. P1–P14 all implemented as specified in council4/SYNTHESIS.md.

## Judgment calls the builders flagged — rule on these

- P1: a share request with NO tier field still defaults to tier 2.
  Acceptable, or must tier be explicit?
- P4/A28: the blessed 1.1→1.2.1 upgrade shape is a key-FILE deployment.
  An env-key-only 1.1 deployment must place its key in the file beside
  the DB, because an unverifiable env key over an existing unpinned
  chain is REFUSED at boot. Is refusing-to-start the right product
  behavior here, or a deployment blocker that needs a ceremony?
- The eight silent attack verdicts: is "the harness dies because the
  setup is refused" a legitimate pass, or does the loop owe those
  scenarios a re-aimed test?

## Convergence criteria (vote on each)

(1) No seat raises a deployment-blocking or code-critical finding
against 1.2.1. (2) Every round-4 forced change is implemented or
answered in writing with a reason. (3) What remains is documented
CANT-DO limitations or legal/institutional questions routed to the
City Attorney / ACIC — not code defects. (4) Independent re-tests pass
on the final build (the orchestrator has re-run both suites; your own
verification counts toward this).

## Output format

1. First line: MODEL/EFFORT USED (model + effort as shown in the UI).
2. Verdict: CONVERGED or NOT CONVERGED, with the per-criterion votes.
3. Round-4 verification table: each P-item / forced change —
   FIXED / FIXED-BUT-WRONG / NOT FIXED, with evidence.
4. New findings, severity-tagged (deployment-blocking / code-critical /
   minor), each with file:line or a reproduction.
5. Rulings on the three judgment calls above.
6. If NOT CONVERGED: your ONE forced change for the next patch.
7. Anything you believe is a legal/institutional question (route it —
   do not settle statute from the chair; Act 668 of 2025 remains
   flagged-not-settled).

Context you can rely on: Arkansas law (Ark. Code §§ 12-12-1801–1808)
caps ALPR retention at 150 days; Cabot proposes 14. Retention, the
two-key Tier 3 judicial gate, query-time suppression for
protection-order plates, and "no cross-audit, no data" Compact sharing
are the system's reason to exist — defects in them are never minor.
