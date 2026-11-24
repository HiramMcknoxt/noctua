# NOCTUA Council — Round 4 Synthesis (NOCTUA 1.2)

**Seats and models (owner's protocol — best included tier, max effort,
no Fable, no credit-gated/Ultra tiers):**
- ChatGPT — GPT-6.2, High (picker observed: GPT-6.2 selected, effort
  slider High 3/3; no Ultra tier offered). Read all 20 files.
- Gemini — Neon, High (Carbon still Ultra-gated, declined). Read all
  20 files (two messages; 10-attachment cap).
- Claude (user's browser) — Opus 5.5, Effort Max. Read all 20 files;
  RAN runtime attacks (38 defects reproduced, 2 positive controls held).
- Claude (cloud) — Opus 5.5, Effort Max. Read all 20 files; RAN 41
  runtime attacks (39 defects reproduced) and delivered an independent
  attack suite (`attacks-cloud/noctua12-round4-attacks/run_all.sh`).

**Verdict: NOT CONVERGED — unanimous, for the third straight round.**
But round 4 changed the evidence standard: two seats executed the code,
and the orchestrator re-ran the cloud seat's attack suite against the
shipped tree — **39 CONFIRMED, the only NOT REPRODUCED being the
suite's own negative control.** The builders' 246/246 suite passes and
catches none of these. 1.2's architecture is not in question anymore —
every seat says so. What remains is a set of fail-open boundaries,
self-vouching trust records, and enforcement contradictions between
components that each claim the same invariant.

## Code-confirmed convergent core (verified by Vesper in code and/or
## reproduced at runtime by an independent suite)

1. **Share tier bypass.** POST /share/query accepts tier=1 (and JSON
   true) and runs a FULL historical search (janus.py:3152, 3227). The
   Tier 2 cap — the Compact's core promise — is one parameter away
   from void. (Gemini + both Claudes; runtime A2/R01.)
2. **hotlist_sync empties the hot list.** Entries stored with
   expires_ts="" are "expired" by the sweep's SQL ("" IS NOT NULL and
   "" < now), so the nightly job deactivates every non-expiring entry;
   retention then deletes the rows. /health REQUIRES the job — a green
   dashboard means an empty stolen-vehicle list. (Gemini + cloud
   Claude B-1; runtime A1/A1b.)
3. **Suppression is an ingest-time stamp, not a property of the plate.**
   /hits, Tier 3 results, /verify, and /evidence/export read the static
   hits.suppressed flag; a protection order entered after a hit does
   not hide it. (All four seats in substance; runtime A5/R02.) The
   browser seat's forced change names the fix: suppression must be
   evaluated at query time, everywhere.
4. **The 1.1→1.2 upgrade voids suppressions.** The migration copies
   plate→plate_raw without normalizing legacy rows, so canonical
   matching misses every pre-upgrade suppression, silently. (Claude
   browser R24, runtime-tested against a real 1.1 database.)
5. **The witness can vouch for itself.** publish_witness.sh exits 0
   and /health shows the witness ok when no repo is configured, and
   when git commit fails (`|| true` swallows it, push is a no-op).
   (Gemini edge case + cloud Claude B-2; runtime A6a/A6b.)
6. **Restore verifies against the backup's own keys.** restore.py
   checks the manifest signature against signing_pub.pem INSIDE the
   untrusted backup set; an attacker-signed set installs attacker's
   users and keys. Separately, a restore that REFUSES (tar-slip) has
   already replaced the live DB. (Gemini + cloud Claude; runtime
   A7/A8.)
7. **Compact trust records are replayable.** A signed audit report can
   be re-filed under a different partner and replayed forever
   (/compact/audit-result never checks report.agency or report.ts);
   receipts are never freshness-checked at query time, an unverified
   (verified=0) receipt satisfies the gate, and a missing newest
   checkpoint fails the gate OPEN. (Gemini + cloud Claude B-4;
   runtime A3/A4.)
8. **Nothing pins the partner's key.** compact.py, sentinel_audit.py
   (URL mode), and rotation.py --verify all accept the public key
   embedded in the very document being verified when no pin is passed.
   (Gemini + ChatGPT F5 in substance.)
9. **Rotation still broken at the edges.** Seed omitted → 500
   (uuid never imported, janus.py:3085 — Vesper-confirmed); the
   publishing supervisor can grind seeds to choose who audits whom
   (runtime A14c: ~3 tries average); delinquency compares adjacent
   DIFFERENT agencies and counts future rounds; POST /compact/witness
   has no role check, no signature, no chain entry. (Gemini + both
   Claudes.)
10. **Registry contradictions.** sentinel_audit --db permanently FAILS
    a healthy aged deployment (scrubbed fragments, destroyed bundles,
    held hits all misread as breaches), while janus retention_breach
    misses scope='case' holds and ignores NOCTUA_BACKUP_DIR; the
    registry itself misses holds.reason and witness_attestations.detail,
    and the schema test's plate|frag|results name regex cannot catch a
    new store (runtime A16: unregistered reads.vehicle_tag,
    ocr_cache table, and a loose file all pass). ChatGPT adds WAL/
    journal files and the witness bundle as undeclared stores.
    (All four seats in substance.)
11. **Chain fragilities.** Audit kind/ts columns sit OUTSIDE the hash
    (rewriting them verifies clean — runtime A10); one torn spool line
    makes chained writes fail and loses a stolen-plate read while
    /health stays ok (A11); Chain streams to the sink BEFORE commit,
    so a rollback leaves a phantom entry; several endpoints still
    commit before logging; an account added while Janus is stopped is
    live at boot with no CONFIG_CHANGED (A13); anchor acceptance
    re-triggers after the next checkpoint (A15); sentinel_audit
    anchors only the NEWEST checkpoint — Janus's own startup check
    catches a history rewrite the audit tool misses (A9/A9b).
12. **Blind second key.** /tier3/pending was overcorrected after round
    3: approvers now see only hashes — no fragment, case, justification,
    or auth basis — so the two-key control's second key cannot actually
    judge what it approves. (Claude browser R17.)
13. **Hold/disposition abuse.** A junk hold review_by date or an
    unconfirmed disposition keeps a hit past 150 days while /health
    stays green (Claude browser R03; Gemini flagged the unvalidated
    review_by in round 3 — still open); HOLD_DAYS itself has no
    150-day ceiling.
14. **DELETE /hotlist can no-op while reporting success** — called
    without the entry's state it answers "membership deactivated,"
    chains HOTLIST_REMOVE, and the entry stays active (runtime A24).
15. **Verification-surface fragmentation** (ChatGPT's forced change):
    chain/signature verification is implemented separately in janus,
    sentinel_audit, compact, and restore, and the copies have already
    drifted (see 11: the audit tool missing what Janus catches).
    One verification contract in sentinel.py, consumed by all.

## Forced changes — four seats, one shape

- Gemini: close every fail-open boundary and registry contradiction,
  each proven by an adversarial test that fails before the fix.
- Cloud Claude: "nothing may vouch for itself" — six binding
  conditions (restore/host keys, compact key pinning, audit-result
  agency+freshness binding, witness proof-of-publication, audit tool
  anchoring ALL checkpoints, rotation seed not publisher-chosen).
- Claude browser: suppression as a query-time property of the plate;
  hot-list removal deletes the row.
- ChatGPT: one authenticated chain-verification path in sentinel.py
  used by every consumer.
**All four ACCEPTED.** They are the same patch described four ways.

## Routed out (unchanged)

Act 668 of 2025 remains flagged-not-settled (the browser seat's
appendix confirms: secondary source only, enrolled act not checked;
150-day governmental cap reportedly unchanged). § 1804(d) sharing,
§ 1808(b) scope, derived-data status of plate_refs — Lane 2 (Ben).
Key custody, witness-repo ownership, Frigate media retention —
Commission decisions / CANT-DO.

## Disposition

1.2.1 patch build commissioned (items P1–P13 in the build brief).
Acceptance is objective and external: the cloud seat's attack suite
and the browser seat's harness must both run CLEAN against 1.2.1
(controls excluded), the builders' suite must pass including new
fail-before-fix tests for every item, and the orchestrator re-runs
all three. Round 5 then reviews the patch.
