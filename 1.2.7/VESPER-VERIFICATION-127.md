# VESPER VERIFICATION — NOCTUA 1.2.7

Verifier: Vesper (cold-verification seat). Date: Nov 26, 2026
(03:48–04:40 UTC). Subject: `janus127/` as built per
`TRACK-127-REPORT.md`. Method: independent cold one-shot battery
run, an independent discrimination run, firsthand code reads of
the load-bearing dispositions, and a direct diff of the R15
re-aim. Nothing in the builder's report was taken on trust;
every number below was reproduced or read firsthand.

## Verdict: VERIFIED

Every gated claim in TRACK-127-REPORT.md reproduced exactly on
an independent cold run — in fact on a single uninterrupted
one-shot, which the builder's own three attempts never
achieved. The V battery discriminates (0/19 on janus126). All
five load-bearing code dispositions read as claimed. janus126
is untouched. Two run-dependent MEASUREMENTS differ from the
builder's digits (health availability under saturation; the
S10 retry count) — both are named in the reconciliation table
with the reason they cannot match digit-for-digit; neither is
a gate, and the gated properties behind both reproduced
exactly.

## Baselines and tree identity

| file | md5 | status |
|---|---|---|
| janus126/janus.py | `9e39e0414cf4b782eb93aaf05573e8bc` | expected value; identical before AND after all verification runs — janus126 untouched |
| janus126/sentinel.py | `dca5d958da4c8e4e7be775eaae092c7f` | expected value; identical before AND after |
| janus127/janus.py | `3161d9d968e696c4ae001e0eea61f47e` | recorded at verification start; identical at end — no code changed during verification |
| janus127/sentinel.py | `1fc7875056a38e6e04f410cf18b0dbef` | recorded at start; identical at end |
| janus127/scripts/compact.py | `8258f124cefddf4856073c2328936eca` | recorded (V18 surface) |

## Run disclosures (this verification)

- **Discrimination run** (Nov 26, 03:48 UTC):
  `python3 janus127/tests/run_v127_cases.py janus126 janus125`
  — janus126 as TEST tree. Exit 1. Result: **0/19 cases pass;
  all 19 FAIL** (v1, v2, v3, v4, v5, v5b, v6, v7, v8, v9, v10,
  v11, v12, v13, v14, v15, v16, v17, v18). Log:
  `janus127/verify-vesper/scratch/disc-20261126-034849.log`.
- **Acceptance battery** (Nov 26, 03:51–04:35 UTC, ~44 min):
  the tree's own `./run-next.sh` one-shot, cold, invoked via
  `janus127/verify-vesper/run-next.sh battery`. **One single
  uninterrupted run, exit 0, `BATTERY RESULT: SUCCESS`** — no
  session interruption occurred, so no leg-by-leg recovery was
  needed and none is claimed. The tree runner pins TMPDIR to
  `janus127/scratch/tmp` itself (workspace, not the 512 MB
  /tmp) and exports NOCTUA_BATTERY_CONTEXT=full. Log:
  `janus127/scratch/battery-20261126-035114.log` (copy in
  `janus127/verify-vesper/scratch/`).
- The builder's disclosures check out as stated: three
  one-shot attempts (run 1 died mid-R in a session
  interruption; run 2 stopped by the builder when Addendum 1
  landed; run 3 restart-killed inside the builders leg), the
  acceptance battery completed leg-by-leg with the runner's
  exact commands, and the R15 re-aim followed by a full R
  re-run (verified by diff — see below). My uninterrupted
  one-shot supersedes the composite as evidence and agrees
  with it on every gated number.

## Reconciliation table

| leg / claim | TRACK-127-REPORT | this verification | |
|---|---|---|---|
| builders | 335/335, exit 0 | log line: "335 checks, 335 passed, 0 failed"; leg PASS | MATCH |
| round 4 | 41 verdicts, only A9b contrast control confirmed | "verdicts: 41  confirmed: ['A9b']"; leg PASS | MATCH |
| round 5 | 21 verdicts, none reproduced | "verdicts: 21  reproduced: []"; leg PASS | MATCH |
| round 6 | PASS, every verdict PROPERTY HOLDS / not reproduced | "ROUND6 PASS: every verdict PROPERTY HOLDS / not reproduced"; leg PASS | MATCH |
| Q + invariants | all PASS (Q01–Q27, S2 pair, INV1–INV6) | 35 CASE PASS lines, 0 FAIL (27+2+6=35); leg PASS | MATCH |
| R battery | 20/20 | "R battery: 20/20 cases pass"; leg PASS | MATCH |
| load envelope | COMPLETE: 500/500 landed at 0/3/6 burners, both directions, verify=True | janus122: 500/500 at 0/3/6, verify=True, COMPLETE ×3; janus127: 500/500 at 0/3/6, verify=True, COMPLETE ×3; "completeness holds up to 6 burners" both | MATCH |
| load health availability | `{samples: 20, answered: 18, dropped: 2, wrong_values: 4}` | `{'samples': 20, 'answered': 20, 'dropped': 0, 'wrong_values': 0}` | **VARIANCE — see note 1** |
| S battery | 25/25; S10 passed with dropped_sample_retries 1 | "S battery: 25/25 cases pass"; S10-verify-freshness-bound detail shows dropped_sample_retries: 0, samples_after_tamper [false ×5] | MATCH on count — **retry count differs, see note 2** |
| T battery | 20/20 | "T battery: 20/20 cases pass" | MATCH |
| U battery | 21/21 | "U battery: 21/21 cases pass" | MATCH |
| V battery | 19/19 (V1–V15 + V16–V18) | "V battery: 19/19 cases pass", all 19 case ids PASS individually | MATCH |
| V discrimination | every case fails on janus126 | independent run: 0/19 pass on janus126, exit 1 | MATCH |
| R15 re-aim | literals "1.2.6"→"1.2.7", .orig-126 preserved, R re-run in full | direct diff of run_r123_cases.py.orig-126 vs current: ONLY the 3 literals (orig ll.1361–1363 → current ll.1356–1358), an added 3-line comment, and the header differ | MATCH |
| .orig-126 preservations | run_tests / run_u126_cases / run_r123_cases .orig-126 with reason headers | all three files present; headers read and accurate | MATCH |
| judgment calls | 11, flagged | 11 numbered calls present in the report (§ "Judgment calls") | MATCH (adjudication is Round 10's, not this seat's) |
| overall | every leg green on final code | BATTERY RESULT: SUCCESS, one-shot exit 0 | MATCH |

**Note 1 — health availability (named, not smoothed).** The
builder reported {20 samples, 18 answered, 2 dropped, 4 wrong
values}; my run measured {20, 20, 0, 0} — full availability.
This quantity is a saturation-timing measurement on a shared
VM; it is nondeterministic by construction, which is exactly
why the commission made it a reported measurement and not a
gate (judgment call 4). The digits cannot be expected to
reproduce; the leg's gated property (append completeness,
500/500 at every burner level in both directions, verify=True)
reproduced exactly. My run's cleaner numbers do not contradict
the builder's — they are two samples of the same noisy
quantity, and the worse sample is the one already on record
for Round 10, as commissioned.

**Note 2 — S10 retry count (named, not smoothed).** The
builder's acceptance run dropped one /health sample under load
and the commissioned single retry recovered it
(dropped_sample_retries: 1, logged in their case output). In
my run no sample dropped: the case (log id
`S10-verify-freshness-bound`; the report's prose names it
`s10_verify_overdue`) shows dropped_sample_retries: 0 with
freshness held in every returned sample
(samples_after_tamper all false). The retry mechanism was
armed (NOCTUA_BATTERY_CONTEXT=full, exported by the runner);
it simply was not needed. The §5 reporting convention stands:
full-battery S results are reported as run — the builder's
24/25-until-proven framing is superseded by two independent
25/25 full-battery passes, one of which exercised the retry
and one of which did not need it.

## Code-read spot-checks (firsthand, with file:line)

- **V1 — pickup lockout scope. CONFIRMED.** `janus.py:3196`:
  `def _auth_lock_note_failure(user, key_verified=False)`; the
  predicate is the function's first act (`if not key_verified:
  return`). need_auth (`janus.py:4405`) passes
  `key_verified=getattr(self, "_auth_key_ok", False)`. In
  `_totp_pickup` (`janus.py:5821`): the locked-account reply is
  the uniform 401 `{"error": "authentication failed"}`; the
  wrong-key branch calls only `_note_auth_fail` (no lockout
  count); the token-failure branch (`janus.py:5908`) passes
  `key_verified=True`.
- **V4 — ceremony state + LAB refusal. CONFIRMED.**
  `_totp_provisioned()` (`janus.py:2773`) — meta marker OR
  non-empty store — is the only provisioning test.
  `_ceremony_fenced` (`janus.py:3398`) is consulted in all
  three dispatchers — `_post` (janus.py:4553), `_delete`
  (~janus.py:8557), `_get` (janus.py:8705) — gated on
  `_ceremony_state()` plus TOTP_HUMAN_ROLES, chaining
  CEREMONY_REFUSED and answering 503. LAB refusal
  (`janus.py:9527`): `LAB_MODE and _totp_provisioned()` chains
  LAB_MODE_REFUSED (KEY_LOCKED-guarded, per the Q02 doctrine)
  and `sys.exit(3)`. The retired mechanisms
  (`_unprovisioned_locked`, `install_born_empty`,
  `_DB_LEGACY_CHAIN_AT_IMPORT`) survive only in explanatory
  comments (janus.py:1141, 2949, 3352) — no code references.
- **V16 — sink_divergence unreadable. CONFIRMED.**
  `sentinel.py:2015` `sink_divergence()`; at `sentinel.py:2041`
  the `if _state == "unreadable":` branch replaces `stranded`
  with every committed audit seq, so the divergence dict is
  returned (the accept ceremony is reachable) instead of the
  1.2.6 None.
- **V17 — _auth_locked performs no write. CONFIRMED.**
  `janus.py:3175`: the shell-unlock branch pops `_auth_locks`
  in memory and returns False; `_auth_lock_persist` is NOT
  called anywhere in the function (the word appears only in
  the explanatory comment). `_auth_lock_persist` itself
  remains at `janus.py:3138` for its in-lock owners.
- **V18 — compact.py per-side secrets. CONFIRMED.**
  `scripts/compact.py`: PARTNER_TOTP_SECRET (l.95) and
  AUDITOR_TOTP_SECRET (l.97), each from its per-side env var
  with the legacy NOCTUA_TOTP_SECRET fallback (the disclosed
  judgment call 11); CLI flags at ll.216/221. `http()` (l.101)
  takes `totp_secret=None` and attaches X-Noctua-TOTP only
  when one is passed (ll.113–115); `recompute()` (l.145)
  likewise. Partner-side calls pass the partner secret
  (ll.278, 331, 337, 351, 361); the home audit-result post
  passes the auditor secret (l.414); the checkpoint-receipt
  post (ll.393–395) passes none.
- **DeepSeek F5 answer (owed answer 1). CONSISTENT.**
  `anchor_fenced()` (`janus.py:2296`) calls `_anchor_apply` at
  janus.py:2306; its call sites are janus.py:4571 (_post),
  8570 (_delete), 8716 (_get), 9323 (_health). The only other
  path to `_anchor_apply` is `_startup_anchor_check()`
  (janus.py:2484, invoked at 2657 — boot, before serving).
  The call-site enumeration in the builder's answer is exact.
- **Claude B R-F/122 answer (owed answer 2). CONSISTENT.**
  During my round-6 leg the seatwork server process ran from
  `scratch/round6-seatwork/janus122/janus.py` — the historical
  slot name bound to the tree under test, as the answer
  states. The DET→SUP single-setup-line adaptation and its
  coverage companions (U battery U6 cases; V battery's
  v2_submission_vs_live, which passed in my run) are as
  described.

## What this verification does not do

It does not adjudicate the 11 judgment calls (Round 10's
work), does not re-derive dispositions beyond the five
spot-checked items plus the two owed answers (the remaining
V items are covered behaviorally by the V battery's 19
discriminating cases, which I ran on both trees), and makes
no claim about anything outside the battery's and the cases'
reach. No code or test file in janus127 was edited by this
seat; no git operations were performed.

*VESPER · the evening watch — verification seat, for Corey
Spangler, Cabot, Arkansas.*
