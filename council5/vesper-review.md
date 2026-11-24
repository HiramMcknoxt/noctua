MODEL/EFFORT USED: Vesper seat — cold-context Muse instance with local code execution

# NOCTUA 1.2.1 — Round 5 Review (Vesper seat)

I read the full 1.2.1 tree cold (janus.py, sentinel.py, all twelve
scripts, COMPACT.md, the test suite's relevant sections), the round-4
synthesis, the 1.1 and 1.2 trees where the patch's claims touch legacy
data, and I ran everything below myself.

## Test results (my own runs)

- **Builders' suite: 312/312 passed, exit 0.** (First attempt died on a
  full 512 MB /tmp tmpfs left by earlier runs; re-run clean with
  TMPDIR on the workspace disk.)
- **Round-4 attack suite vs the janus121 tree: 1 CONFIRMED line —
  A9b, the contrast control — and 32 NOT REPRODUCED.** This matches
  claim 1 in the brief exactly, including A9 flipping: both
  sentinel_audit and Janus's startup anchor now catch the rewrite.
- **Five probes of my own** (kept with this review's working papers):
  three confirmed new defects end-to-end, one confirmed a defect
  class, one *cleared* a suspicion I brought in (see "Checked and
  cleared"). Details under New Findings.

## Verdict: NOT CONVERGED

Per-criterion votes:

1. **No deployment-blocking / code-critical finding — FAIL.** Five
   code-critical findings stand below (F1–F5), three of them
   reproduced at runtime by me, in the patch's own new code.
2. **Every round-4 forced change implemented or answered — FAIL.**
   Five of fourteen P-items are FIXED-BUT-WRONG (P4, P6, P10, P11,
   P13). The pattern is consistent: the fix is real in the place the
   builders tested and incomplete at the boundary they didn't.
3. **What remains is CANT-DO or routed legal questions — FAIL.** What
   remains includes code defects in the sink, the chain verifier,
   the evidence lifecycle, and the report fence.
4. **Independent re-tests pass — PASS.** Both suites re-run by me
   pass as far as they go (counts above). They do not cover F1–F4;
   that is a coverage fact, not a contradiction.

## Round-4 verification table (P1–P14)

| Item | Verdict | Evidence |
|---|---|---|
| P1 share gate binding | FIXED | Gate legs read fresh per call, both legs enforced (janus.py:3531ff). Tier default is judgment call 1 below. |
| P2 hotlist `''` expiry | FIXED | Migration `''`→NULL (janus.py:_migrate_121, janus.py:624ff); hotlist_sync.py sweep predicate excludes `''`/NULL and commits deactivations + HOTLIST_EXPIRED in one transaction, flushing after commit — the correct pattern (see F1 for where Janus itself doesn't follow it). |
| P3 verify_detached continuity | FIXED | sentinel.py:811ff `_verify_rows` checks seq continuity, prev linkage, and hashes through the shared `entry_hash`. |
| P4 migration | FIXED-BUT-WRONG | `_migrate_121` (janus.py:624ff) normalizes `reads.plate`, `hits.read_plate`, and hotlist `expires_ts`. It does not touch `hotlist_members.plate`, `suppressions.plate`, or `hits.entry_plate`. I checked every legacy write path: 1.1 and 1.2 both normalized hotlist/suppression plates at insert (janus11 normalize_plate; janus12 janus.py:1727, 1929), and `entry_plate` was always copied from an already-canonical hotlist row — so the omission is **unreachable through any supported write path** and bites only a hand-edited or foreign-built database. The claim as written ("migration normalizes legacy plate text") is broader than the code. Minor severity; see F8 note. |
| P5 witness proof | FIXED | publish_witness.sh read in full: real-clone + remote precondition, no `|| true` on commit, ls-remote ref equality and remote-tree readback before the ok heartbeat. |
| P6 restore key discipline | FIXED-BUT-WRONG | The live-host case (round-4 A7) is genuinely fixed: with a host key present, restore.py:221 requires `sig_ok or (hmac_ok and key == host_key)`. But on a **keyless host** (bare-metal recovery — the case disaster recovery exists for), restore.py:226 accepts `hmac_ok` computed by `_find_audit_key` (restore.py:114–127), which falls back to **the backup set's own audit_key**. A self-consistent forged set — attacker's users, attacker's keys, internally valid chain, no live checkpoints file to disagree — installs and boots clean. The restore docstring's "NEVER against a key inside the backup" holds only for the signature leg. See F6. |
| P7 audit-result binding | FIXED | janus.py:3067–3140: report.agency must match the filing agency, report.ts must be within 26h and is the stored ts, signature verified against the local key before any of it. |
| P8 key pinning | FIXED | compact.py refuses to run unpinned and requires `--our-agency`; rotation.py `--verify` refuses an embedded key without a pin; sentinel_audit URL mode requires `--pubkey`/`--pubkey-fingerprint`. (A separate labeling defect in sentinel_audit is F5, not a pinning failure.) |
| P9 rotation seed + delinquency | FIXED | rotation.py read in full: seed = SHA-256 over sorted members + cycle start + chain root at publication; Fisher-Yates driven by the seed stream; Janus cross-checked by the builders' suite; future rounds never count as delinquent (janus121 tests, suite_p121). |
| P10 one registry implementation | FIXED-BUT-WRONG | There is now one implementation — `sentinel.registry_breaches` (sentinel.py:485), consumed by /health and sentinel_audit. But its docstring claims it mirrors "retention.py's purge semantics exactly" (sentinel.py:489–493), and for hits it does not: the registry judges hits against exact-second cutoffs (sentinel.py:534–543) while retention's guarded purge uses **floor days** — `age_d = (now - ts).days`, purging only when `age_d > days` (scripts/retention.py:161–169). The two disagree at every boundary for up to ~24h: /health and sentinel_audit will report a retention breach the purge does not recognize, the exact two-checkers defect P10 was convened to kill. Worse, the floor-day cap leg means a *protected* hit is purged only when `age_d > 150` — i.e., it can live to 150 days 23:59, past the statutory ceiling retention.py's own docstring says is "never kept past 150 days." |
| P11 one verification contract | FIXED-BUT-WRONG | `entry_hash` is genuinely the single formula — compact.py's recompute, sentinel_audit, restore, and Janus all call it (no private copies found). Two residues: (a) v1 entries keep the legacy hash over the payload only, and **no verifier cross-checks the payload-embedded ts/kind against the columns** — F2, reproduced. (b) The contract covers hashing, not checkpoint verdicts: Janus's `_bad_checkpoints` (janus.py:804ff) verifies a signature **only when `sig_alg == "ed25519"`** and otherwise checks roots alone, while sentinel_audit's `verify_checkpoint_sigs` counts a non-ed25519 checkpoint as a signature failure. Two shipped verifiers, two answers to the same question — F7. |
| P12 Tier 3 approver visibility | FIXED | The pending queue now shows a supervisor approver the fragment, case, justification, and basis (janus.py:4044ff); builders' suite covers the fence. |
| P13 route enumeration / fail-close | FIXED-BUT-WRONG | The builders' enumeration test covers nine GET routes. The POST dispatch (janus.py:1667–1778) applies `config_closed()` only to `/tier3/*`, `/evidence/*`, and inside `/share/query` — while the function's own docstring claims it "applies to ALL data endpoints" (janus.py:1620–1622). POST `/report/compile` is the sharp case: F4, reproduced live. POST /hotlist, /verify, /holds, /suppressions, /outcomes, /lists, /compact/*, and /audit/anchor-accept also stay open during fail-close, as do GET /lists, /compact/*, and /audit/*. |
| P14 DELETE /hotlist honesty | FIXED | No-match DELETE returns 404 (builders' test, run_tests.py:2133–2138; suite re-run by me passes). |

## New findings

### F1 — [code-critical] Phantom sink entries: `flush_deferred` runs outside the lock, presence-checks through the shared (uncommitted) connection

P11's fix moved sink streaming after commit — in the request that
owns the entries. But do_POST/do_GET/do_DELETE all call
`chain.flush_deferred()` **after releasing DBLOCK** (janus.py:1659–
1662 and the identical tails at 3756, 3849), the deferred queue is a
single shared list on the shared Chain, and `flush_deferred`'s
presence check (sentinel.py:1035ff) reads through **Janus's shared
sqlite connection — which sees other requests' uncommitted rows**.
So request A's post-lock flush can drain and stream request B's
entries while B's transaction is still open; if B then rolls back
(the do_POST exception path does exactly that), the sink holds an
entry the chain never contained. The P11 defect, reintroduced by the
placement of its own fix. hotlist_sync.py — same codebase — does it
correctly (own connection, flush after its own commit).

Reproduction (sentinel-level, Janus's exact wiring — one shared
connection, append inside an open transaction, cross-request flush,
rollback):

```
after append: in_transaction=True deferred=1
sink lines after cross-request flush: 1   (kind: TIER3_EXECUTE)
audit rows for TIER3_EXECUTE after rollback: 0
chain verify: {'ok': True, 'entries': 0, 'root': 'GENESIS'}
RESULT PHANTOM-SINK-ENTRY: True
```

The sink is the copy an outsider trusts precisely because it is
append-only and off the request path. A phantom TIER3_EXECUTE in it
is a false permanent record of a search that never happened.

### F2 — [code-critical] On any upgraded chain, an insider can relabel a v1 entry's kind/ts columns and every shipped verifier stays green

`entry_hash` (sentinel.py:792–810) hashes v2 payloads as
sha(prev|ts|kind|payload) but v1 payloads as sha(prev|payload) — the
docstring's stated intent is that "rewriting them breaks the chain
(round 4, A10)." For v1 entries the ts/kind **columns** are not in
the hash, the payload's embedded ts/kind are never cross-checked
against the columns in `_verify_rows` (sentinel.py:811ff), and
/audit/range serves the columns. Every real deployment that ran
1.0–1.2 has a v1 history; that history's most sensitive entries can
be relabeled by anyone with database write access — the exact
insider the chain and checkpoints exist to catch. Checkpoints don't
help: the root is a hash of payloads, unchanged by a column edit.

Reproduction (chain built with the 1.2 sentinel, then
`UPDATE audit SET kind='HEARTBEAT' WHERE kind='TIER3_EXECUTE'`,
verified with the 1.2.1 sentinel):

```
verify BEFORE tamper: {'ok': True, 'entries': 4, 'root': 'f5a009c…'}
row 3 now: kind column='HEARTBEAT', payload still says kind='TIER3_EXECUTE'
verify AFTER relabel:  {'ok': True, 'entries': 4, 'root': 'f5a009c…'}  (identical root)
RESULT RELABEL-UNDETECTED: True
```

The fix is one cross-check in `_verify_rows` (payload ts/kind vs
columns for v1 rows) — cheap. Leaving it out means A10 is fixed
only for entries written after the upgrade.

### F3 — [code-critical] Evidence re-export inherits the old destroy_by — retention then destroys the fresh bundle

The export UPSERT (janus.py:2817–2828) resets `destroyed_ts`/
`destroyed_by` on re-export but **not** `released_ts`,
`disp_confirmed_ts`, or `destroy_by`. Re-export a hit after its
disposition is confirmed — the ordinary "prosecutor needs another
copy" flow — and the brand-new bundle sits under the old
destruction clock. When that date passes, retention's destroy pass
(scripts/retention.py:246–266, which keys only on
`destroyed_ts IS NULL AND destroy_by < now`) deletes the fresh
bundle and marks the row destroyed.

Reproduction (live Janus 1.2.1, my probe instance; destroy_by then
aged by direct UPDATE — the same time-simulation the builders' own
suite uses at run_tests.py suite_a3 — and retention's real
`destroy_overdue_bundles` called against the result):

```
export #1 -> 201 bundle: hit-1-20261124T154621Z
disposition confirm -> 200 destroy_by: 2026-12-24T15:46:21Z
export #2 -> 201 bundle: hit-1-20261124T154622Z   (fresh bundle)
row after re-export: disp_confirmed_ts='2026-11-24T15:46:21Z',
                     destroy_by='2026-12-24T15:46:21Z'  (unchanged)
retention destroy pass: destroyed 1 overdue evidence bundles
fresh bundle still on disk: False
RESULT STALE-DESTROY-BY: True
```

The builders' evidence tests re-export only *before* disposition,
so the suite never walks this path. Destroying live evidence early
is the mirror image of keeping data too long; both are lifecycle
defects in the store this system exists to govern.

### F4 — [code-critical] POST /report/compile bypasses the report role fence and the stale-config fail-close

GET /report is supervisor/auditor-only and fail-closes
(janus.py:4018–4025). POST /report/compile **returns the full
compiled report in its response**, accepts any DATA_ROLES role
(janus.py:2302–2325), and has no `config_closed()` check
(dispatch at janus.py:1772–1773).

Reproduction (live instance):

```
GET  /report as detective        -> 403 the effectiveness report is supervisor/auditor only
POST /report/compile as detective -> 201, report keys:
  ['arrests', 'confirmed_matches', 'from', 'lists',
   'matches_not_corresponding', 'overdue_holds', …]
```

A detective who cannot read the report can compile and read it.
(Concurs with the Gemini seat's N6, independently reproduced.)

### F5 — [code-critical] sentinel_audit URL mode labels the target's self-report "independent"

In URL mode, `audit_url` computes its headline chain check as
`verify = http(a.url, "/audit/verify", …)` and reports it as
**"chain integrity (independent)"** (scripts/sentinel_audit.py:204–
206). That endpoint is the assessed system grading its own chain.
The only genuinely independent URL-mode check is the single anchor
comparison at the newest checkpoint's height. compact.py — the
Compact's real runner — recomputes the whole chain over
/audit/range and says, correctly, that "a partner that reports ok
about itself has told us nothing." The audit tool should meet the
standard the runner already sets, or the check should be renamed
"self-report" the way its sibling check at line ~195 honestly is.
In a reciprocal-audit regime, a mislabeled self-attestation is not
a cosmetic issue; it is the failure mode the Compact exists to
prevent.

### F6 — [code-critical] Restore on a keyless host still lets a backup vouch for itself

See P6 in the table. restore.py:114–127 (fallback to the set's own
audit_key) + restore.py:221–226 (keyless-host branch accepts
`hmac_ok` alone). Disaster recovery is precisely when a city
restores onto bare metal from an offsite set; if that set was
replaced wholesale, the forged system boots with no anchor
disagreement (restore deliberately never installs the backup's
checkpoints as live — restore.py:45 — so nothing local contradicts
it). The mitigation the tool offers, `--pubkey`, is optional in
exactly the case where it matters. Require a pin (or an explicit,
loud `--accept-unpinned-recovery` override that chains its own use
into the restored system's first boot entry) whenever the host has
no key of its own.

### F7 — [minor] Checkpoint signature policy diverges between the two verifiers

Janus `_bad_checkpoints` (janus.py:804ff) checks a checkpoint's
signature only inside the `sig_alg == "ed25519"` branch; a
checkpoints file rewritten with `sig_alg` downgraded and roots
matching a rewritten chain produces **no** bad checkpoints locally.
sentinel_audit counts the same file as signature failures. The
external witness (published checkpoints in git) still catches the
rewrite — if anyone diffs — but the local anchor, the layer that
runs at every boot, can be silenced by a string edit. One policy,
both places: unsigned or unknown-alg is bad.

### F8 — [minor] The chain scrubber only recognizes the canonical plate token

`_looks_like_plate` (sentinel.py:751) matches a bare canonical
token. Probe of `sentinel._sanitize`:

```
'VIC309'   -> hashed
'VIC 309'  -> 'VIC 309'   (passes through, unflagged)
'VIC-309'  -> 'VIC-309'   (passes through, unflagged)
'plate VIC 309 at gate' -> passes through whole
```

The chain's "no raw plates" invariant (S11) therefore rests on
every caller never placing a spaced, hyphenated, or in-sentence
plate into a chained field — caller discipline, not the scrubber
that is supposed to be the backstop. Today's chained fields are
mostly disciplined (refs and hashes), which is why this is minor;
the first future field that chains operator free text inherits the
hole silently.

### F9 — [minor] Assorted robustness and drift

- POST /hotlist with a valid case but no `category` returns
  **500 `internal: 'category'`** (janus.py:2013–2025, `d["case"]`/
  `d["category"]`); `_post_verify` has the same shape with
  `d["hit_id"]`. Client errors should be 400s. (Live-probed.)
- restore.py installs the restored files and writes the restore
  marker (restore.py:324–325) **before** verify_detached runs
  (restore.py:352); a restore whose chain fails exits 3 but leaves
  the failed database in place, marker and all, for Janus to chain
  RESTORE against at next boot. Print FAILED *and* quarantine the
  install, or verify from a staging path first.
- backup.py stamps new manifests `"noctua": "1.2"` (scripts/
  backup.py:206) and rotation.py stamps schedules `"version":
  "1.2"` (scripts/rotation.py:99) in a 1.2.1 tree. Cosmetic — and
  exactly the kind of drift that misleads an incident responder
  reading a manifest at 2 a.m.

### Concurrence — the retention/evidence boundary (Gemini N1)

I verified the mechanism in code: retention's cap leg purges a hit
once floor-age exceeds 150 days **regardless of protection**
(scripts/retention.py:161–169), while `registry_breaches`' evidence
leg only flags bundles that carry a destroy_by — so a bundle whose
hit was cap-purged while its evidence was unreleased becomes
invisible to /health, unreleasable and undestroyable through the
API (its hit is gone), and stranded on disk. The code-side defect
is the invisibility and the stranded custody record; *whether* the
statute permits the bundle to outlive the hit at all is the legal
question routed below, not something this seat settles.

## Checked and cleared (suspicions I brought in that the code refuted)

- **compact.py duplicate-receipt failure:** I expected a second
  compact.py run against an unchanged partner checkpoint to 409 on
  the receipt and record a false failure. It does not: receipts
  bind to the partner's *newest* checkpoint by root/entries/ts
  equality (janus.py:3156–3255), re-attestation of the current
  checkpoint is accepted by design, and my two-instance probe
  recorded ok=True on both runs. The S18 replay protection (stale
  checkpoint → 409) works as specified.
- **Migration gaps for hotlist/suppression plates:** real in the
  migration code, unreachable in practice — see P4.
- **checkpoint.py checking only the newest checkpoint:** sound.
  Hashes chain forward, so any rewrite below the newest checkpoint
  changes the root at its height; the newest-only refusal misses
  nothing an older checkpoint would catch.

## Rulings on the builders' three judgment calls

1. **P1 — omitted share tier defaults to tier 2: ACCEPTABLE.**
   Tier 2 is the share ceiling in any case; the request still needs
   case_ref, a stated basis, a fresh passing cross-audit, and a
   current checkpoint receipt before anything moves. The tier field
   selects the data class, and defaulting it does not weaken any
   gate leg. One condition: the defaulted tier should be visible as
   defaulted in the SHARE_OUT chain entry, so a later auditor can
   tell an affirmative tier-2 request from an omitted one.
2. **P4/A28 — refusing to boot over an unverifiable env key:
   REFUSAL IS CORRECT; A CEREMONY IS OWED.** Silently minting over
   an existing chain was the original A28 sin; a boot that cannot
   verify its key against its chain *should* stop. But "place the
   key in the file beside the DB" as tribal knowledge is how an
   operator bricks a lawful deployment during an upgrade window.
   Ship a `pin_audit_key.py --confirm` ceremony (verify the
   presented key against the chain, write the file, chain the
   pinning) and make the boot refusal message name it. This is a
   deployability requirement, not a defect in 1.2.1's logic.
3. **The eight silent attack verdicts: SPLIT.** Where the setup
   itself is the refused behavior — client-supplied rotation seed,
   env-key-only boot over an unpinned chain, HOLD_DAYS=400 — the
   harness dying in setup *is* the control working, and those are
   legitimate passes-by-refusal. But a verdict that prints nothing
   is indistinguishable from a broken harness, and the suite's
   consumers (this council included) had to take the distinction on
   faith. The loop owes re-aimed variants that reach the target
   behavior for every scenario whose target still exists, and every
   attack — refused or not — must print its verdict and why.
   Silence is a suite defect even when the underlying behavior is
   right.

## Forced change (one, for 1.2.2)

**No assertion crosses a trust boundary on another transaction's
word — every boundary check is evaluated against committed,
current state, by the same rule, in every consumer.** Concretely,
one patch with four fail-before-fix tests, each proven against
1.2.1 first:

1. `flush_deferred` presence-checks through a **separate read
   connection** (committed state only), and Janus flushes while
   holding DBLOCK or not at all — a rolled-back entry can never
   reach the sink (F1).
2. `_verify_rows` cross-checks v1 payload ts/kind against the
   columns, so an upgraded chain's history is bound with the same
   strength as v2's (F2).
3. Evidence re-export resets the row's release/disposition state
   (`released_ts`, `disp_*`, `destroy_by` cleared with
   `destroyed_*`), so a bundle's destruction clock always belongs
   to its current disposition (F3).
4. POST /report/compile takes GET /report's exact fences —
   supervisor/auditor role and `config_closed()` (F4).

F5–F7 should be fixed in the same round but are not the forced
change; if the builders fix only the forced change, F5's relabel
(one word) is the minimum honesty requirement.

## Routed legal / institutional questions (not settled here)

- **§ 12-12-1804(a)–(b) evidence-vs-hit boundary (for the City
  Attorney):** when a hit must be purged at the 150-day statutory
  cap but its evidence bundle is unreleased or under a litigation
  hold, what does the statute require of the bundle and its custody
  record? Does the cap admit a hold exception for the hit itself?
  The code currently purges the hit, strands the bundle, and hides
  the stranding (see Concurrence) — the legal answer decides
  whether that is compliance or spoliation.
- **Act 668 of 2025** remains flagged-not-settled, as in round 4:
  secondary sources only, enrolled act not yet checked against the
  retention and sharing provisions. No code should change on it
  until the City Attorney reads the act.
- Whether a defaulted (rather than affirmative) tier on a Compact
  share satisfies any *inter-agency agreement's* notice terms is a
  question for the Compact's own MOU drafters, not for this code
  review; the code-side ruling is judgment call 1 above.

— Vesper seat, round 5. Verdict: **NOT CONVERGED.**
