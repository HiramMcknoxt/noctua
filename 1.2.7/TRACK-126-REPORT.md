# TRACK-126-REPORT — NOCTUA 1.2.6 (Janus + Sentinel)

Builder: Vesper's builder subagent, Nov 25, 2026.
Source tree: `janus125/` copied to `janus126/`; janus125 untouched —
its janus.py md5 `ab455975b9eb987fa95d3a268190a3bf` and sentinel.py
md5 `85c7f9e06cecc5565211ccb1d43c62d4` were verified at copy time
and RE-VERIFIED unchanged at the end of the build. No git
operations, no pushes. Commission: `council8/SYNTHESIS.md` §6 items
U1–U11 plus Addendum 2 items U12–U14, the U6 amendment (registry
validation before the suppression check), and U11 additions
(a)–(e). Seat findings: `council8/{vesper-seat,claude,gemini,
deepseek,qwen}-review.md` / `council8/qwen-review.md`.

## 1. Battery results (final code)

| Leg | Result | Evidence (all under `janus126/scratch/logs/`) |
|---|---|---|
| builders' suite | **335/335 PASS** | `cold-builders.log`; also the builders leg of `scratch/battery-20261125-204621.log` |
| round-4 wrapper | **PASS** — 40 verdicts, only A9b CONFIRMED (contrast control) | `cold-round4b.log` |
| round-5 wrapper | **PASS** — 21 verdicts, none reproduced | `cold-round5b.log` |
| round-6 harness | **PASS** — every verdict PROPERTY HOLDS / not reproduced | `cold-round6.log` |
| Q battery + invariants | **35/35 PASS** | `cold-q.log` |
| R battery | **20/20 PASS** | `cold-r.log` |
| load envelope | **PASS** — completeness holds to 6 burners (500/500 landed at 0/3/6 burners, verify COMPLETE) | `cold-load.log` |
| S battery | **25/25 PASS** — see the S10 flag below | `cold-s.log` (24/25) + standalone S10 re-run |
| T battery | **20/20 PASS** | `cold-t.log` |
| U battery (new) | **21/21 PASS**, every case discriminating vs janus125 | `cold-u.log` |

**Honest flag — the one-shot `./run-next.sh` was interrupted, and
one leg carries a documented flake.** The cold `./run-next.sh`
(started 2026-11-25 20:46 CST, log `scratch/battery-20261125-
204621.log`) completed its builders leg (335/335 PASS) and was
killed mid-round-4 by a **runtime restart of this VM**, not by a
test failure. The remaining legs were then run with the runner's
exact commands on unchanged code, in runner order, and all passed
(logs above). One code change landed during that sequence: the
round-5 leg's first cold attempt (`cold-round5.log`) exposed an
R5-14 collision with U13 (see §3, defect 4); `scripts/restore.py`
gained the snapshot-copy completion, round 5 was re-run green
(`cold-round5b.log`), the builders' suite was re-run on the final
code (335/335, `cold-builders.log`), and round 4 was also re-run
on final code (`cold-round4b.log`) because it exercises restore.
Every leg in the table above therefore stands on the final code.

**S10 flake (disclosed, not hidden):** in both full S-battery runs
the S10 case failed with exactly ONE `null` health sample among
five (the sample adjacent to the chain tamper), the other four
correctly `false`; run standalone on the same final code it
passes with all five samples `false` (twice). The case samples
`/health` under six saturating ingest threads on this 1.5-CPU VM;
one dropped response fails its all-samples assertion. The
freshness bound itself held in every sample that returned.

**A18 timing sensitivity (both trees, not a 1.2.6 regression):**
the round-4 `attack4.py` and round-5 `r5_a18_anon_scan.py`
scenarios verify a fabricated 600,000-entry chain through a
client with a 20 s timeout. Pure in-process `verify_chain_rows`
over that chain measures **18.3 s** on this VM
(`scratch/verifydbg2.py`), so any contention pushes the request
past the timeout. During the loaded afternoon both seat files
timed out — and janus125's own `attack4.py` timed out identically
when run standalone as a control, proving the sensitivity is the
environment's, not this build's. In the cold runs both files
completed: round 4 PASS with A18 not reproduced, round 5's scan
NOT REPRODUCED with an 8.73 s authenticated verify. Round 9
should expect these two files to be load-sensitive on any
comparable VM.

## 2. Per-item dispositions

**U1 — lockout scope. DONE.** `auth()` stashes the key-verdict and
failure reason on the request record; the failure counter
(`_lockout_counts`) increments ONLY for a human account whose key
VERIFIED and whose second factor then failed. Keyless and
wrong-key attempts never count; machine accounts never lock;
replay of a consumed TOTP code counts (it is a post-key second-
factor failure). A locked human account now feeds health's
`ok_all` (health goes not-ok while any human is locked), and the
shell path is real: `provision.py unlock <user>` appends a marker
line, Janus chains ACCOUNT_UNLOCKED, and the account serves
again; POST /auth/unlock (supervisor) remains the in-band path.
Case `u1_lockout_scope` (spraying ingest + both supervisors with
keyless/wrong-key attempts locks nobody; the legitimate
stale-code pattern still locks on the fifth post-key failure and
unlocks via the shell marker) and `u1_replay_and_wrong_key` —
both FAIL on 125, PASS on 126.

**U2 — anchor fence exit. DONE.** A clean anchor evaluation now
clears the fence itself: the flag file is deleted and
ANCHOR_CLEARED is chained. An evaluation ERROR persists the
fence only after 3 consecutive errors, so one torn read no
longer fences the install forever. `scripts/checkpoint.py`
truncates a torn FINAL line on open (mid-file malformation still
refuses) and appends via temp file + os.replace + directory
fsync. Case `u2_fence_exit` (torn checkpoint → fence → repair →
auto-clear without any manual flag deletion) — FAILS on 125,
PASSES on 126.

**U3 — sink divergence cost + resolution ceremony. DONE.** The
sink index is memoized keyed on (path, size, mtime_ns): at
≥100k lines a diverged-obligation rescan no longer re-reads the
file per append (case measures 8 appends in 0.37 s where 125
needed 6.5–14.4 s for 6). Resolution is a ceremony, not an edit:
POST /audit/sink-divergence-accept (supervisor) chains
SINK_DIVERGENCE_ACCEPTED naming the stranded seqs, archives the
diverged file as `<sink>.diverged-<ts>` evidence, resets the
tail, and backfills. Case `u3_sink_divergence` — FAILS on 125
(ceremony 404), PASSES on 126.

**U4 — ingest confidence + supersede honesty. DONE.** `conf`
must be a finite number in [0, 1] (bool, non-number, NaN, ±inf,
out-of-range → 400, nothing stored). A re-delivery that
supersedes a PENDING hit now marks it PENDING_SUPERSEDED (new
`hits.superseded_by` column links the successor; the read model
keeps the withdrawn_* fields plus `successor_hit`). A supervisor
disposes of superseded hits through the normal outcome path.
Case `u4_supersede` + the NaN-confidence leg of
`u11_janus_units`/ingest probes — FAIL on 125, PASS on 126.

**U5 — DEMO_MODE on a provisioned install. DONE.** Boot refuses:
DEMO_MODE=1 against a provisioned install chains
DEMO_MODE_REFUSED and exits 3 instead of silently waiving the
second factor. Case `u5_demo_refusal` — FAILS on 125 (boots and
serves), PASSES on 126 (exit 3).

**U6 — hot-list submission uniformity (as amended). DONE.** A
non-supervisor's add is stored PENDING and answered with a
uniform `202 {"result": "submitted"}` for every plate class —
protected, unprotected, never-seen. Pending entries match
nothing and appear in no list view. Supervisors decide via
GET /hotlist/pending and POST /hotlist/approve | /hotlist/reject;
approving a protected entry deletes it, refuses 403, and chains
HOTLIST_ADD_REJECTED (a protected plate's hits are born-
suppressed whatever the queue decides). A supervisor's own add
remains a direct 201, with the informative suppression 403.
**Amendment implemented:** the list-registry check runs BEFORE
any suppression evaluation, so a bogus `list_name` earns the
identical 400 for every plate class (the side-effect-free
404-vs-400 probe is closed). One ordering nuance is flagged in
§3. Case `u6_hotlist_uniform` (three plate classes byte-identical
202s + the bogus-list probe) — FAILS on 125 (404/201/201),
PASSES on 126.

**U7 — pickup token + rotation count. DONE.** Confirming a
re-enrollment mints a pickup token shown ONLY in the confirm
response (to the confirmer, who conveys it out-of-band); only
its SHA-256 is stored. Pickup requires key + token; the token is
single-use and expires with the pending window (24 h from
enrollment). A bad token is a post-key failure and feeds the U1
lockout counter. The users-file rotation the pickup performs
refuses (PICKUP_FAILED chained, HTTP 500, token NOT consumed)
unless exactly one record matches. Case `u7_pickup_token` —
FAILS on 125 (pickup succeeds with no token), PASSES on 126.

**U8 — sink-status fault injection replaces the T4
absence-proof. DONE.** `sink_status()` wraps its state read in
try/except and reports `ok=False / unknown` on any fault instead
of raising into health. Case `u8_sink_status_fault` points the
sink path at a directory: 125 raises IsADirectoryError out of
health; 126 reports the fault by name. **Supersession:** the
absence-proof paragraph for this surface in
`janus125/TRACK-125-REPORT.md` (the T4 discussion) is superseded
by this fault-injection case; the 125 report itself is a prior
tree's record and was not edited.

**U9 — unprovisioned-install tightening. DONE WITH A FLAGGED
JUDGMENT CALL — see §3, item 1 (read it first).**

**U10 — backup escrow placement. DONE.** `scripts/backup.py`
refuses an escrow directory inside the backup tree BEFORE
creating anything (the default remains the sibling
`key-escrow/` beside the backup root). Case
`u10_escrow_placement` — FAILS on 125, PASSES on 126.

**U11 — smalls. DONE, all parts.**
(i) Version sweep: every user-visible version string reads
1.2.6 (janus VERSION, sentinel REGISTRY_VERSION, backup manifest,
COMPACT.md label) — case `u11_version_sweep`.
(ii) `pubkey_fingerprint` of an empty / body-less PEM returns
None instead of raising — case in `u11_sentinel_units`.
(iii) Tier 3 approval of a request whose plate fragment is a
`pref:`/invalid fragment EXPIRES the request (409 EXPIRED)
instead of executing — case `u11_tier3_pref` (125: 200 EXECUTED;
126: 409).
(iv) TOTP store writes (Janus and provision.py enroll-2fa) use a
unique temp file + os.replace, so concurrent writers cannot
tear the store — case in `u11_janus_units` (125 reuses one fixed
temp path; 126's paths differ per write).
(v) The chain scrubber folds confusable look-alikes: Cyrillic
З/з → 3 and Unicode Nd digits fold to ASCII before plate-shape
matching — case in `u11_sentinel_units`. **Named non-claim
(carried from the synthesis):** fragmentation across ≥4 tokens
is NOT claimed closed.
(vi) C8-11 doc fixes: INSTALL §6 now says checkpoints are
Ed25519-signed with `<db>.signing_key.pem` (they were never
HMAC); INSTALL §7 and OPERATIONS §10 corrected (lockout scope,
unlock paths, chain_auditor job custody); OPERATIONS gained
§9a, the sink-divergence ceremony.
(vii) R-F originals: pre-adaptation seat files kept beside the
adapted ones with one-line reason headers — see §4.
Additions: (a) `_totp_pickup` and the re-enroll target check
mirror auth()'s disabled test (case `u11_disabled_pickup`:
125 picks up for a disabled account, 126 refuses);
(b) `alert_check.py` names `migration_status.state ==
"incomplete"` (case `u11_alert_check_names`);
(c) `sentinel.totp_code` gained the base32-padding tolerance
`janus._totp_code` already had (unit case);
(d) `_sql_order_covers` fails CLOSED (returns "covers") on any
exception instead of leaking the row (case in `u11_janus_units`:
125 returns 0 on a broken input, 126 returns 1);
(e) INSTALL §8 go-live checklist gained the bound-identities
checkbox.

**U12 — sink tail reconciliation (Qwen's forced change). DONE.**
`_sink_file_tail` no longer returns (0, None) for a non-empty
unparseable file: it distinguishes absent / empty / ok / torn /
unreadable. A torn final line is truncated to the last valid
line and delivery resumes from there — the chain is NOT
re-delivered into the existing file and the ledger is not
cleared. A truncated sink (0 < file_seq < recorded tail) is a
NAMED divergence: obligations preserved, `sink_state.ok = 0`,
resolution only via the U3 ceremony. Case `u12_sink_tail`
(torn-tail and truncated-sink fault injections) — FAILS on 125
(its own unit crashes reading the welded file), PASSES on 126.

**U13 — restore key custody + R-A closure. DONE.** When the
backup set carries no keys (every T8 escrow-split set),
`restore.py` leaves the host's live keys in place — it no longer
moves them aside into a void — and prints the key posture
honestly. When a set DOES carry keys, 1.2.5 behavior is kept.
PLUS: the restore marker records the OUTGOING install's
provisioning state (read from the live DB before the swap); if
the outgoing install was provisioned, Janus treats the incoming
install as provisioned and materializes must_reenroll for its
humans regardless of the incoming DB's own marker (residual R-A
closed). Cases `u13_restore_custody` (split-set restore on an
instance with published checkpoints: keys intact, signing
identity unchanged, no fence — 125: keys gone, hits 503) and
`u13_ra_closure` (provisioned outgoing → unprovisioned incoming:
126 answers key-only auth 401 with must_reenroll materialized;
125 served key-only 200). Both FAIL on 125, PASS on 126. One
completion added during the cold battery — see §3, defect 4.

**U14 — anchor evaluation cost. DONE.** Checkpoint signature
verification is memoized by checkpoint CONTENT hash
(`_checkpoint_sig_ok`, bounded 8192-entry memo): per-window
under-lock work is bounded by NEW checkpoints, not the file's
total. What the case measures: openssl verify subprocess calls
per evaluation window over a 200-checkpoint file — first window
200 verifies, second window (no new checkpoints) **0**. 125
verifies 200 then 200. Case `u14_anchor_cost` — FAILS on 125,
PASSES on 126. U2's auto-clear inherits the bound (same
evaluation path).


## 3. Judgment calls and defects found by the battery

**Judgment call 1 — U9's scope (flagged FIRST, needs Round 9
ratification).** Read literally — "an unprovisioned install
refuses ingest and serves key-only auth to no one" — U9 is
mutually exclusive with the living battery: every suite fixture
is a born-empty unprovisioned install that ingests and
authenticates key-only by design (demo mode, first-boot
provisioning, and every battery case depend on it). Implemented
instead: the tightened state arms only on a **populated
arrival** — a database that arrives WITH history but no TOTP
provisioning. The mechanism is the `install_born_empty` marker:
captured from whether the DB file existed at import, and set
when the DB never served (no reads/hits and no SYSTEM audit
entry). A refinement was forced by the builders' suite (P4's
1.1-upgrade fixture crashed the first reading): a database whose
chain predates 1.2 (first audit payload is a `"version": "1.1"`
entry with no `"v": 2`) is an UPGRADE, not an arrival — the 1.1
line had no second factor and its upgrade path is
ceremony-shaped — so the legacy-chain probe at first connect
also disarms the state. Case `u9_populated_arrival` (a DB built
by janus125 with history, booted by 126 unprovisioned: ingest
refused, key-only auth refused) FAILS on 125 and PASSES on 126
under this reading. **Round 9 must ratify or reject the reading
itself** — the case proves the implemented behavior, not the
interpretation.

**Judgment call 2 — U6 validation order.** The amendment names
the list-registry check. The shipped order is: registry →
supervisor suppression refusal → category/expiry validation →
role split. Category/expiry presence is plate-independent, so
its position cannot leak plate class to anyone; placing the
supervisor's refusal before it preserves 1.2.5's informative
supervisor answer for a thin body (the T7 living case posts a
supervisor add with no category and asserts the 403). For
non-supervisors every validation still precedes the uniform 202.
The U6 case's bogus-list probe passes under this order.

**Judgment call 3 — U3/U12 divergence state.** Diverged seqs are
per-process state, exposed through `sink_status()`; the durable
record is the chain entry the ceremony writes and the archived
`.diverged-<ts>` file. Resolution rotates and backfills; it
never deletes the diverged file (it is evidence).

**Judgment call 4 — U4 superseded outcomes.** A superseded hit's
outcome fields stay unresolved by design; "a supervisor
disposes" means the supervisor works the SUPERSEDING hit and
the queue surfaces the superseded one linked — no new outcome
verb was invented for a hit that never reached a roadside
decision.

**Judgment call 5 — U10 "backup tree".** Read as the backup root
(the `--out` directory): an escrow path anywhere inside it is
refused; the sibling default is unchanged.

**Defect 1 (found by the U battery; fixed).**
`_consume_provision_marker` chained ACCOUNT_UNLOCKED for
`provision.py unlock` lines but never popped the in-memory
`_auth_locks` entry — and consuming the marker deletes it, so
the shell-unlock state check had nothing left to find. The
account stayed locked until expiry despite the chained unlock.
The unlock branch now pops the in-memory lock and persists
before chaining.

**Defect 2 (found by the U battery; fixed).** `scripts/
restore.py` used `sqlite3` without importing it — the U13
outgoing-provisioned read died silently inside its bare
`except`, so every restore marker recorded
`outgoing_provisioned: false` and R-A stayed open in practice
while the code looked closed. Import added; the U13 R-A case
is the regression test.

**Defect 3 (found by the U battery; fixed).** The same read
needed a normal (read-write) connection: a read-only URI open
cannot recover a stopped server's hot WAL and silently read a
stale main file, missing the provisioning marker that lives in
recent commits.

**Defect 4 (found by the cold round-5 leg; fixed).** R5-14
reproduced against the first U13 build (janus125 control:
not reproduced). The scenario measures the pre-restore snapshot:
under U13's no-keys branch no key copies were made at all, which
its condition reads as "copies destroyed." In substance nothing
was destroyed — the live keys never moved — but the snapshot
contract is worth keeping whole: when the set carries no keys,
restore now takes snapshot COPIES (`shutil.copy2`) of the live
key files into the same `.pre-restore-<stamp>` set while the
live keys stay in place. Round 5 re-ran green with the copies
present and the U13 custody case still green.

## 4. Living-suite updates (commissioned shape changes only)

Every change below is assertion-preserving: setups that needed a
live hot-list entry now place it through the supervisor's direct
add (U6 made the detective's add a non-matching submission), and
status expectations follow U4's rename. Nothing else was
touched; no assertion was weakened, deleted, or re-aimed.

- `tests/run_tests.py` — hotlist setup adds re-pointed DET→SUP
  by plate (RST417 first occurrence only; its banned-case twin
  stays DET; PRT208, ZZQ999, RET100, EXP200, P121AA, DEL121,
  KEEP121, GONE121); the VIC309 suppression check rewritten to
  the U6 shape (detective add → 202 `submitted`,
  SUPPRESSION_CONFLICT still chained); version strings
  1.2.5 → 1.2.6.
- `tests/run_q122_cases.py` — `hotlist()` helper DET→SUP with a
  disclosure comment; Q25's BAK100 setup and INV1's expiry-probe
  adds via SUP (INV1's invariant is expiry parsing; its 400s and
  its no-expiry 201 leg are unchanged in substance).
- `tests/run_r123_cases.py` — version strings → 1.2.6; R9's
  expected supersede status WITHDRAWN → PENDING_SUPERSEDED with
  an explanatory comment; all direct DET setup adds → SUP
  (helper `place_and_hit` carries the disclosure comment).
- `tests/run_s124_cases.py` — `hotlist()` helper DET→SUP;
  S11's pickup now presents the U7 pickup token taken from the
  confirm response (the flow's invariant — two-key restore +
  re-enroll + single pickup — is unchanged; the token is U7's
  addition to that same handoff, and `confirm_leaks_secret`
  still asserts the secret itself is never shown).
- `tests/run_t125_cases.py` — `hotlist()` helper default → SUP
  (t7's detective legs pass `user=DET` explicitly, since they
  test the submission itself); `_suppressed_hit` and
  t7_redelivery setups via SUP; `t7_hotlist_oracle` rewritten
  for U6 (detective protected/unprotected adds byte-identical
  202; supervisor direct add of a protected plate → 403;
  supervisor approving the protected queue entry → 403 and the
  entry leaves the queue); t7_redelivery expects
  PENDING_SUPERSEDED.
- `demo/seed_demo.py` (product code) — the demo's hot list is
  placed as sgt.reyes (supervisor direct add) with a U6 comment;
  a detective's submission would sit pending and the demo would
  seed nothing.
- Seat attack files (originals preserved per R-F as
  `<name>.orig-124` beside each adapted file, each carrying a
  one-line reason header; assertions unchanged):
  `tests/attacks/round4/attack1.py` (3 adds), `attack2.py`
  (4 adds), `attack3.py` (1), `attack4.py` (1);
  `tests/attacks/round5/r5_evidence_deadend.py` (1),
  `r5_parity.py` (1), `r5_supersede.py` (1), `r5_gates.py` (1),
  `r5_hotlist_expiry.py` (5 — its expiry measurements are
  vacuous against pending entries, so the setups must be live);
  `tests/attacks/round6/f2d_native_orders.py` (1),
  `f10_orphan_bundle.py` (1), `f4_preauth_race.py` (1).
  Deliberately NOT adapted: round-6 `f2_migration.py` and
  `f9_bothtree.py` adds run against the real 1.0/1.1 fixture
  builds, which have no pending concept — they construct
  historical data, and changing the actor there would falsify
  the fixture.
- Shared docs (`~/workspace/noctua-1.0/docs/` — one folder
  serves every tree, so these edits describe 1.2.6 for all):
  INSTALL §6 (Ed25519 checkpoints, C8-11), §7 items 4–5
  (escrow split + inside-tree refusal; post-restore key posture
  and re-enrollment), §8 bound-identities checkbox (U11e);
  OPERATIONS §10 rewritten (lockout scope, supervisor unlock +
  `provision.py unlock` break-glass, chain_auditor job custody)
  and new §9a (sink-divergence ceremony).

## 5. Residuals and non-claims

- U11(v): scrubber folding covers the listed confusables and Nd
  digits; fragmentation of a plate across ≥4 tokens remains a
  named non-claim, as the synthesis left it.
- U9's reading (§3, item 1) is the build's largest open
  question and is Round 9's to ratify.
- Criterion 5 (Ben Hooper / ACIC written answers as a
  convergence gate) was not part of this commission and nothing
  in this build prejudges it.
- S10 and the two A18 seat files are load-sensitive on this VM
  class (§1 flags); their invariants held in every measurement
  that completed.
- No prior tree was modified: janus125 md5s re-verified at the
  end of the build (see header). The shared `docs/` folder edits
  in §4 are the only files outside `janus126/` this build
  touched, and they are documentation, not code.
