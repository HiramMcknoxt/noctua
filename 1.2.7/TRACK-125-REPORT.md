# TRACK-125-REPORT — NOCTUA 1.2.5 (Janus + Sentinel)

Builder: Vesper's builder subagent, Nov 25, 2026.
Source tree: `janus124/` copied byte-identical to `janus125/`
(baseline md5s in `scratch/janus124-baseline-md5.txt`, re-verified
unchanged at the end of the build — see §5). No git operations, no
pushes. Commission: `security-round/SYNTHESIS.md` items T1–T9,
per-claim detail in `security-round/VERIFICATION-NOTES.md`.

## 1. Battery results (final code, no edits after the cold run began)

| Leg | Result | Evidence |
|---|---|---|
| builders' suite | **335/335 PASS** | cold-run log `scratch/battery-20261125-135439.log` |
| round-4 wrapper | **PASS** — 41 verdicts, only A9b CONFIRMED (contrast control) | cold-run log; also `scratch/logs/r4-raw4.log` |
| round-5 suite | **PASS** | cold-run log |
| round-6 harness | **PASS** — every verdict PROPERTY HOLDS / not reproduced | cold-run log; also `scratch/logs/r6-raw3.log` |
| Q battery + invariants | **35/35 PASS** | cold-run log; also `scratch/logs/q-raw2.log` |
| R battery | **20/20 PASS** | cold-run log; also `scratch/logs/r-raw2.log` |
| load envelope | **PASS** — completeness holds to 6 burners | `scratch/logs/load-raw2.log` |
| S battery | **25/25 PASS** | `scratch/logs/s-raw4.log` |
| T battery (new) | **20/20 PASS**, every case discriminating | `scratch/logs/t-raw3.log` |

**Honest flag — the single-process `./run-next.sh` exit-0 could not
be obtained in this environment.** The full battery takes ~50
minutes on this 1.5-CPU VM; the runtime reaps long-lived process
trees at ~26–30 minutes. Attempt 1 (foreground, `scratch/
battery-20261125-120909.log`) was SIGTERM'd during the R leg with
builders PASS and round5 PASS recorded. Attempt 2 (detached
setsid/nohup, `scratch/battery-20261125-135439.log`) recorded
builders, round4, round5, round6, Q+invariants, and R all PASS
before the runner was reaped during the load leg. The remaining
three legs (load, S, T) were then run cold with the runner's exact
commands on **unchanged code** and all passed (logs above).
`run-next.sh` itself is correct and complete; on an environment
without the process-lifetime cap it runs end-to-end. I did not
shorten or split the battery to manufacture an exit 0.

## 2. Per-item dispositions

**T1 — fail-closed authentication state. DONE.**
Provisioned-marker design: a DB meta marker (`totp_provisioned`)
records that an install has ever been provisioned. Provisioning
state (no marker, empty store) is the sanctioned fresh-install
ceremony state — human key-only auth works, /health is red and
names the state. Once provisioned: missing store, corrupt store,
unenrolled human, malformed entry, and must_reenroll are all
authentication **failures** (401), never waivers, never 500s;
the refusal reasons chain (2FA_NOT_ENROLLED / AUTH_STATE,
throttled, keyed username hash). Restore onto a provisioned
install materializes must_reenroll placeholders for every human
the store does not carry and chains TOTP_REENROLL_REQUIRED.
chain_auditor tooling: `sentinel.totp_code/totp_counter_now`
(RFC 6238) added to sentinel.py; `scripts/compact.py` and
`scripts/sentinel_audit.py` accept `NOCTUA_TOTP_SECRET` and retry
once on the next 30 s step after a 401.
Discriminating cases: T1-unenrolled, T1-missing-store,
T1-corrupt-store, T1-restore-without-store, T1-chain-auditor-
totp-tooling (sentinel_audit URL mode completes against a
provisioned install: 5 ok checks incl. independent recompute).

**T2 — throttling + the §10 lockout + cap-proof evidence. DONE.**
Per-account failure counting persisted in DB meta; 5 consecutive
failures lock the account for 900 s (ACCOUNT_LOCKED chained);
even correct credentials refuse while locked; supervisor-only
POST /auth/unlock chains ACCOUNT_UNLOCKED; success resets the
counter. Per-target failure totals increment on EVERY failure
(before the chain cap is consulted) and surface in /health
(`auth_fail.fail_totals`, `cap_suppressed_total`,
`locked_accounts`), with a chained aggregate when a capped
minute rolls. The AUTH_FAIL username hash is now HMAC-keyed
(`user_hash`).
Cases: T2-five-failure-lockout, T2-cap-proof-failure-evidence
(33-failure spray: totals survive, suppressed = 8, bare-sha key
absent, HMAC key present).

**T3 — anchor fence + witness consumption + sink divergence.
DONE.**
On a recorded or live-detected anchor mismatch, data endpoints
refuse 503; safety writes (/reads, suppressions, holds) proceed
with a chained ANCHOR_FENCE_WRITE; the recovery surface (health,
chain reads, heartbeats, anchor-accept, 2FA/auth admin) stays
open. /health consumes the witness state: newest published
checkpoint's (entries, root, ts) + `matches_chain`.
Sink leg (Claude F6, verified real in the 1.2.4 code): below-tail
delivery candidates were marked delivered on faith, so appends
after a chain rollback (reused seqs, different hashes) vanished
from the mirror silently. `Chain._deliver_locked` now verifies
below-tail candidates against the sink file's own record at that
seq (`_sink_seq_hashes`); a mismatch is a named divergence, the
obligation stands, and sink_status reports the error.
Case: T3-anchor-fence-and-sink-divergence (restore-style
snapshot rollback — a row delete cannot reuse AUTOINCREMENT
seqs; the case swaps an earlier DB snapshot back in, as a real
restore does).

**T4 — health fail-closed sweep. DONE.**
Unknown ≠ healthy: a sink whose status cannot be determined is
`sink_status_unknown` and not ok; a no-sink install names
`sink_posture: "checkpoints_only"` and is not ok; DEMO_MODE is a
named degradation (`degraded.demo_mode`) and never reports ok;
T1 states (provisioning / store missing or corrupt / unenrolled
/ malformed / must_reenroll) each hold health down by name;
`config_status()` per-file entries carry DeepSeek F9's
`guard_error`. `scripts/alert_check.py` names each new reason.
Case: T4-health-fail-closed-sweep. **Absence-proof for the
sink-status-exception branch:** it is a three-line exception
handler around `sink_status()`; no public-API input makes
`sink_status()` raise (a directory as the sink path is handled
gracefully by the delivery error path instead), so the branch
is covered by code inspection, not a case.

**T5 — strict signature verification. DONE.**
janus `_bad_checkpoints` no longer conditions verification on
the declared `sig_alg`: every checkpoint needs a verifiable
Ed25519 signature by our key; absent/unknown alg, wrong types,
or malformed keys are bad checkpoints, each evaluated in a
try/except. (sentinel_audit's `verify_checkpoint_sigs` and
rotation.py were already strict; untouched.)
Case: T5-strict-checkpoint-signatures (sig stripped, root and
entries intact → 1.2.4 accepts, 1.2.5 fences).

**T6 — defensive checkpoint parsing. DONE.**
`sentinel.pubkey_fingerprint` returns None on any malformed
input instead of raising. janus `_load_checkpoints` parses
line-by-line and returns (checkpoints, error, malformed_count);
non-JSON/non-dict lines are counted malformed and excluded;
malformed content produces the named anchor reason
`checkpoints_malformed` (fail-closed, fenced, repairable — it
is not an acceptable disagreement); `_startup_anchor_check`
converts any evaluation exception into a recorded mismatch.
Cases: T6 (a) null / non-dict / malformed-PEM lines — 1.2.4
**crashes at boot** (AttributeError in `_bad_checkpoints`),
1.2.5 boots and names the problem; (b) truncated line — 1.2.4
lumps it into `checkpoints_unreadable`, 1.2.5 names
`checkpoints_malformed`.

**T7 — identity binding + oracle shaping + redelivery. DONE,
with one reconciliation (flagged in §3).**
User records may declare `cameras` (ingest) / `jobs` (jobs);
a bound identity presenting another camera/job is refused 403
and the refusal chains (INGEST_REJECTED / HEARTBEAT_REJECTED).
Unbound legacy identities keep working and are named in /health
(`ingest_unbound`, `jobs_unbound`). /verify oracle: suppressed
hit + non-supervisor now returns the byte-identical 409
"hit not found or already decided" as a non-pending hit (the
chain BLOCKED entry keeps the real reason). /hotlist oracle:
protected plate + non-supervisor returns 404 "plate not found";
the supervisor keeps the informative 403, and probing still
chains SUPPRESSION_CONFLICT.
Cases: T7-camera-binding, T7-heartbeat-binding,
T7-verify-oracle-shaped, T7-hotlist-oracle-shaped,
T7-redelivery-cannot-withdraw.

**T8 — provisioning + backup custody. DONE.**
provision.py enroll-2fa is two-key in the shell: when any other
account holds an ACTIVE enrollment, `--confirm-by` + the
confirmer's own credential (TOTP code, counter consumed — or a
recovery code, hash-matched and burned) is required; confirmer
≠ target and must be ACTIVE; `--force` overwrites obey the same
rule. Bootstrap/recovery exception: with NO active enrollment
anywhere, enrollment proceeds unconfirmed, printed loudly.
Every enroll-2fa mutation chains PROVISION_2FA via a marker
file janus consumes (a shell process appending directly would
miss the sink ledger). Re-enrollment: the auditor's confirm
creates the pending enrollment and returns **no secret**; the
holder collects it once via POST /auth/2fa/pickup with their
own key — the pickup generates the new secret, recovery codes,
and a **rotated API key** (rotation happens before the pickup
is consumed; a second pickup is 409; pickup refuses while the
account is T2-locked). Backup: key material (audit_key,
signing_key.pem, signing_pub.pem) no longer enters the set —
it lands in a separate escrow directory
(`$NOCTUA_KEY_ESCROW_DIR/key-escrow-<stamp>/`, default a sibling
of the backup root) with its own signed manifest; the set's
manifest records escrow hashes only; restore.py's fingerprint
pinning also seeks the material at the escrow location (the pin
remains the trust root). CLOUD.md's false "encrypted backup"
sentence and backup.py's docstring were corrected to describe
the split. openssl is pinned via `sentinel.OPENSSL`
(`NOCTUA_OPENSSL` env or `shutil.which`); the PATH residual is
documented in docs/CANT-DO.md.
Cases: T8-provision-two-key, T8-backup-key-escrow-split; the
pickup flow is covered end-to-end by the reworked S-battery
case S11-restore-reenroll-two-key.

**T9 — scrubber Unicode + F3 stored reads. DONE.**
`sentinel._contains_plate` now also checks the NFKC-folded,
confusables-mapped form of each token (Cyrillic/Greek
look-alikes → Latin); detection only — `normalize_plate` and
plate_ref are unchanged, so no stored ref moves. F3: the SQL
suppression legs (`_SUPPRESSED_SQL`, `_SUPPRESSED_HIT_SQL`) now
test a registered `noctua_order_covers(ref, order_plate,
order_state, plate)` function that delegates to the same
`_order_covers` predicate as the Python leg, so plate-less
legacy-ref orders suppress stored rows on search/Tier-3/hits
exactly as they do at ingest.
Cases: T9-homoglyph-scrubber (Cyrillic + full-width + ASCII
control), T9-stored-reads-legacy-order.

## 3. Judgment calls (for Vesper's reconciliation)

1. **T1 provisioned-marker + provisioning ceremony state.** The
   commission requires fail-closed auth and the batteries
   require unenrolled harnesses to work; the marker design is
   the reconciliation (fresh install = named ceremony state;
   once provisioned, never a waiver again). chain_auditor stays
   a TOTP-capable HUMAN role with tooling support rather than a
   redesigned machine identity.
2. **T1 restore-flip refinement (build-phase).** The flip fires
   only when the install was provisioned (marker in the restored
   DB or a non-empty live store). A never-provisioned install
   restoring a backup stays in its ceremony state instead of
   acquiring must_reenroll placeholders for accounts that were
   never enrolled. Evidence: round-4 attack3 and round-6 f10
   restore never-enrolled instances and read the chain to verify
   the RESTORE; the unrefined flip broke both on a state change
   no seat asked for. The downgrade case T1 targets (provisioned
   install, store lost) still flips — covered by
   T1-restore-without-store and S11-restore-reenroll-two-key.
   Residual: a provisioned install whose store is deleted AND
   which then restores a pre-provisioning backup is
   indistinguishable from a never-provisioned install; no rule
   separates them.
3. **T7 vs R9 reconciliation.** Literal T7 (no redelivery
   withdrawal, ever) and R9 (a later different-plate correction
   withdraws the PENDING hit) are jointly impossible — R9 is a
   ratified battery case. Implemented: a different-plate
   delivery takes currency only on a STRICT (phase, confidence)
   out-rank (R9's 0.96 > 0.95 still corrects); an equal-rank
   plate change is chained READ_PLATE_CHANGE_REFUSED and
   withdraws nothing (kills the F8 shape). The refused delivery
   is NOT stored as a reads version: a stored row would enter
   the currency ranking (arrival tie-break) and become current
   by the back door — found by the T7 case during the build.
   READ_SUPERSEDED now names the withdrawn hit ids.
4. **T7 binding posture.** The enforced invariant is "a bound
   identity cannot cross". Legacy unbound identities
   (ingest.local/jobs.local, on which every battery depends)
   keep working and are named degradations in /health rather
   than silently trusted. Making unbound identities refuse
   would be a deployment decision for the pilot, not a default
   I chose unilaterally.
5. **T8 pickup is key-only by design.** The holder's current
   API key alone authorizes the one-time pickup (the account
   may be must_reenroll or locked out of TOTP — that is the
   point of the ceremony). Tradeoff: a stolen key + a live
   pending re-enrollment can collect the new secret — mitigated
   by one-time semantics, the T2 lockout refusing pickup, and
   TOTP_PICKUP + KEY_ROTATED chaining. Flagged for the council.
6. **T8 backup = split, not script-side encryption** (the
   commission's allowed alternative), with restore.py taught
   the escrow location for fingerprint pinning.
7. **REGISTRY_VERSION bumped to "1.2.5".** The registry table
   itself is unchanged, but its enforcement semantics changed
   (suppression predicate, scrubber normalization, sink
   handling), and the codebase convention is one registry
   version per release; R15's honesty sweep exists to keep the
   version claims consistent. The builders' suite's literal
   assertion was updated to match.
8. **Seat-scenario adaptations (2 files, assertion-preserving).**
   Two frozen seat scenarios reached for key material inside
   the backup set — the exact custody T8 abolished — and
   crashed before printing any verdict:
   `tests/attacks/round4/attack2.py` (A8 now takes the host
   signing key from the escrow directory; the tar-slip refusal
   assertion is unchanged) and
   `tests/attacks/round6/f11_restore_trust.py` (the two
   `os.remove` calls are existence-guarded; the self-vouching
   refusal assertion is unchanged). Without these, both suites
   report harness failures no verdict table can express. The
   diffs are small, commented in place, and revertible if the
   council prefers the legs red.

## 4. Living-suite updates (disclosed, all assertion-preserving)

- **Builders' suite** (`tests/run_tests.py`): the health-ok
  check now asserts the degraded shape by name on Instance A
  plus ok:true on a new fully-provisioned + sink mini-instance
  H; alert_check-on-A asserts exit 1 naming PROVISIONING +
  checkpoints; hotlist oracle check 403→404; two
  detective-verify oracle checks 403→409; the backup/restore
  suite asserts the escrow split (keys absent from the set,
  escrow manifest contents, pinned pub from escrow, tar-slip
  re-sign with the host key); two HTTP chain reads on
  restore-marker boots re-pointed to direct sqlite reads
  (restored humans are must_reenroll by design); registry
  version literals → "1.2.5".
- **S battery**: S2/S3 verify-shape expectations 403→409 (T7);
  S11-totp-lifecycle enrolls SUP2 with DET's recovery-code
  confirmation (T8 two-key), reads health as the jobs identity,
  and takes the acknowledgment from the enrolled SUP2; S11-
  restore-reenroll reworked to the 1.2.5 ceremony (shell
  recovery → endpoint request/confirm → pickup with key
  rotation, confirmer never sees the secret); S7-destroy
  environment repair (see §5).
- **R battery**: R1×2 and R2 verify-refusal shapes 403→409
  (T7); R15 version expectations → 1.2.5.
- **rotation.py**: version gates extended to "1.2.5" and its
  own document version bumped (a 1.2.5 schedule otherwise fell
  into the pre-1.2.2 legacy verify path — found by Q23).
- **Shared docs** (live outside the per-tree layout, edited
  minimally): `docs/CLOUD.md` backup sentence made true;
  `docs/CANT-DO.md` gained the openssl PATH residual.

## 5. Honest flags

- **Bugs found in my own build during testing** (fixed, with
  the catches credited): `_consume_restore_marker` ran before
  `roles_of` was defined — a swallowed NameError meant the
  must_reenroll flip never fired (caught by the S battery);
  one `_load_checkpoints` call site missed in the 3-tuple
  conversion (caught by the builders' suite as share/compact
  500s); the first T7 refusal draft stored the refused version
  and let it win currency by arrival (caught by the T battery).
- **S7-destroy environment repair:** the case's premise (chmod
  0o500 makes a bundle undeletable) does not hold for a
  root-run server on this overlay filesystem's upper layer —
  identical code passes in the older tree's directory and fails
  in a fresh one. The case now swaps the bundle path for a
  symlink (rmtree refuses on any filesystem); the asserted
  invariant (record-first ordering under removal failure) is
  unchanged. Verified mechanism, not a code difference.
- **T4 sink-status-unknown branch** has no discriminating case
  (absence-proof in §2, T4).
- **T3's sink-divergence leg** asserts an invariant whose guard
  partly predates 1.2.5 (the at-tail mismatch block is S1-era);
  the case discriminates via the fence, and the below-tail
  faith-delivery hole it also closes was verified present in
  the 1.2.4 code by reading `_deliver_locked`.
- **/hotlist residual oracle:** after shaping, a caller who can
  add unprotected plates can still distinguish 201 (added) from
  404 (protected-or-unknown) for plates they probe — inherent
  to any add endpoint. The unique protected-plate signal is
  gone and probing chains; recorded here rather than claimed
  closed.
- **Performance note (not a failure):** S12 measured appends at
  ~17–19/s on 1.2.5 vs ~45–52/s on 1.2.3 in this VM (sink
  verification work per append); the load envelope's
  completeness property holds to 6 burners on both trees.
- **Prior trees:** janus124 janus.py/sentinel.py md5-verified
  identical to the copy-time baseline; no prior-tree code file
  was edited (script mtimes in janus124 predate this session;
  the only writes there were test-scratch residue from running
  janus124's own S7 case during diagnosis). The two seat-file
  adaptations in §3.8 are inside janus125's copies only.
