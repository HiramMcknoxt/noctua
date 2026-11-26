# NOCTUA 1.2.1 — Track Report

Patch release closing council round 4 (all four seats: NOT
CONVERGED on 1.2). Every item below was reproduced against 1.2
before it was fixed — most by the cloud seat's independent attack
suite (39 CONFIRMED defects at baseline), the rest by the browser
seat's runtime harness — and each item carries a fail-before-fix
test in the builders' suite (`tests/run_tests.py`, suites
`suite_p121` / `suite_p121_boots` plus updated legacy checks).

## Acceptance gates

**(a) Attack suite** —
`NOCTUA12_TREE=janus121 bash council4/attacks-cloud/noctua12-round4-attacks/run_all.sh`:

- **Zero CONFIRMED defect lines.** 31 verdicts print
  NOT REPRODUCED; A36 also verified NOT REPRODUCED by direct run.
- The one remaining CONFIRMED line is **A9b, the suite's contrast
  control**: it prints CONFIRMED precisely when Janus's startup
  anchor DOES flag a rewritten history — the healthy behavior, and
  it printed CONFIRMED against 1.2 as well. It is not a defect and
  cannot flip without breaking the anchor check.
- **A27** (negative control: OpenSSL 3 creates the private key
  0600 itself) stays NOT REPRODUCED — verified manually after its
  harness slot became unreachable (below); the key file is created
  0600 by openssl, unchanged.
- Eight verdicts print nothing because the attack harness dies
  inside its own setup — in each case the setup exercises the
  refused behavior itself, or a refusal the patch mandates:
  - **A14b / A14c** (attack1): setup publishes a rotation WITH a
    client-supplied seed and asserts 201. P9 refuses that publish
    (400), so the setup assert fails before the findings run.
    A14a (the uuid 500) prints NOT REPRODUCED.
  - **A18** (attack4): its 600k-entry instance boots with an
    env-only audit key over a hand-built unpinned chain — exactly
    the state A28 requires Janus to refuse — so the instance never
    starts. The A18 scenario is re-verified in the builders' suite
    with a deployment-shaped setup (key file beside the DB): a
    concurrent read completes in <1s while a first, uncached
    /audit/verify scans a 250k-entry chain.
  - **A28 / A29 / A30 / A27** (attack3): A28's instance start
    raises (the TOFU refusal IS the fix), which ends attack3
    before A29, A30, and A27 print. A29 and A30 are covered by
    builders' tests (marker survives a KEY_LOCKED boot; 
    NOCTUA_BACKUP_DIR honored by /health). A27 verified manually.
  - **A37** (attack5): the HOLD_DAYS=400 instance refuses to
    start — the refusal is the fix; the finding's CONFIRMED
    condition requires a running server.

**(b) Builders' suite** — `python3 tests/run_tests.py`:
**312 checks, 312 passed, 0 failed** (255 legacy checks as updated
for 1.2.1 behavior + 57 new P-item checks).

**(c) Demo** — `demo/seed_demo.py` seeds and runs clean against
1.2.1 (covered by suite_demo inside the builders' run).

## Per-item status

- **P1 Share tier strict — DONE.** Only the JSON integer `2` is
  accepted; tier 1 / 3 / `true` / `"2"` / `2.0` ⇒ 403
  SHARE_BLOCKED with the refused tier chained as a coded value.
  (Judgment call, flagged: a MISSING tier still defaults to 2 —
  the only legal value — rather than refusing; the strictness the
  finding demanded is about never running another tier's search.)
- **P2 Hotlist expiry — DONE.** `_post_hotlist` stores NULL for
  no-expiry; the sweep matches only `expires_ts IS NOT NULL AND
  expires_ts <> '' AND expires_ts < now`; migration normalizes
  legacy `''` → NULL; hotlist_sync updates + chains
  HOTLIST_EXPIRED in ONE shared transaction.
- **P3 Query-time suppression — DONE.** Every hit-disclosure path
  (/hits, Tier 3 live results, /verify, /evidence/export, share
  results) evaluates suppression live against the canonical plate;
  `hits.suppressed` is a cache only. A5 flipped.
- **P4 Migration repair — DONE.** First 1.2.1 boot normalizes
  legacy `reads.plate` / `hits.read_plate` to canonical form
  (original text preserved in `plate_raw` by the pre-existing
  backfill, which runs first) and chains MIGRATION with row
  counts. Tested against a database built by actually booting the
  repo's janus11 code. **Upgrade note:** the 1.1 deployment in
  the test uses the key-FILE shape (janus11 mints it beside the
  DB; 1.2.1 pins from it). An env-key-only 1.1 deployment must
  place the same key in the file beside the DB to upgrade — an
  unverifiable env key over an existing unpinned chain is
  refused at boot, which is the A28 fix operating as designed.
- **P5 Witness proof — DONE.** publish_witness.sh requires a git
  repo with a configured remote, drops `|| true` from commit, and
  posts the witness heartbeat ONLY after the checkpoint is proven
  on the remote (ls-remote ref equality + the checkpoint root
  read back from the remote's tree). Any failure ⇒ heartbeat
  false + exit 1. A6a/A6b flipped.
- **P6 Restore trust — DONE.** Manifest signatures verify ONLY
  against the host's signing_pub.pem (beside the live DB) or an
  explicit --pubkey/--pubkey-fingerprint — never a key inside the
  set. Host audit key configured + no host-verifiable credential
  (HMAC missing, signature unverifiable against a host key) ⇒
  refuse. Audit-key lookup checks host paths first. ALL tarballs
  are fully filter-validated BEFORE any live file moves aside —
  a refusing restore changes nothing on disk. A7/A8 flipped.
  (Deviation, flagged: the attack harness's A29 SETUP restores
  without any pin and asserts success; under P6 that restore is
  legitimate only because its manifest HMAC verifies under the
  host's env audit key — it still succeeds, and the marker fix
  itself is covered by a builders' test.)
- **P7 Compact binding — DONE.** /compact/audit-result requires
  report.agency == filing agency (400) and report.ts within 26h
  (409); the row stores the report's own ts. The share gate is
  evaluated at query time by one helper: newest checkpoint must
  exist (missing ⇒ CLOSED), latest receipt must match it, carry
  verified=1, and be ≤26h old. /compact/reinstate reads the
  latest audit row by id DESC. A3/A4 flipped.
- **P8 Key pinning mandatory — DONE.** compact.py,
  sentinel_audit.py URL mode, and rotation.py --verify (signed
  schedules) all refuse to run without an out-of-band pin.
  compact.py: --our-agency required; the receipt is signed with
  OUR key via explicit --signing-key. No path verifies against a
  key embedded in the document under verification. A23/A26
  flipped (A26 also: URL mode no longer dies on /health — a
  chain_auditor's 403 there degrades to a named warning and the
  chain checks proceed).
- **P9 Rotation — DONE.** uuid NameError fixed; the seed is
  DERIVED (SHA-256 of sorted members ‖ cycle_start ‖ current
  chain root) and a client-supplied seed is refused (400).
  Delinquency is per-agency over COMPLETED rounds only,
  direction-correct and success-only (verified receipts for
  audits OF us; ok=1 compact_audits for audits BY us); future
  rounds never count. /compact/witness requires a supervisor or
  the partner's registered auditor signature (Ed25519 over the
  attestation) and chains WITNESS_ATTEST. Minimum 2 members;
  the home agency may be a member without registering as its
  own partner. A14a/A25 flipped.
- **P10 Registry parity — DONE.** ONE breach implementation
  (`sentinel.registry_breaches` + `sentinel.hit_protected`) is
  consumed by Janus /health, sentinel_audit, and retention.py —
  CAST-normalized hold refs, either-scope holds inside their
  review window, evidence protection only for exported
  unreleased bundles, destroyed bundles checked ON DISK, orphan
  bundles and expired backup sets FAIL (not warn), and
  NOCTUA_BACKUP_DIR is honored everywhere. holds.reason and
  witness_attestations.detail are registered (class derived).
  The schema test is a FULL-COLUMN ALLOWLIST
  (PLATE_DATA_STORES ∪ NON_PLATE_COLUMNS) plus loose-file and
  folder checks; SQLite -wal/-shm/journal are declared
  file-stores. A16/A19b/A30/A35 flipped.
- **P11 One verification contract + chain hardening — DONE.**
  All chain/signature verification flows through sentinel.py
  (entry_hash / verify / verify_detached); compact.py's private
  hash copy is gone. Chain hash v2 binds kind and ts (columns
  inside the hash); verify accepts v1 and v2. Spool: torn lines
  quarantined to `<spool>.bad` with SPOOL_QUARANTINE chained —
  a chained write never fails over the spool; spool/sink appends
  take fcntl.flock; transactional appends stream only after
  commit (deferred flush, presence-checked). Anchor accept,
  partner suspend/reinstate, rotation void, and witness moved
  inside their transactions. First config load chains
  CONFIG_CHANGED with the config hash; SYSTEM carries it too
  (A13 flipped). Anchor acceptance records the accepted
  checkpoint ids (A15 flipped). sentinel_audit anchors against
  EVERY checkpoint (A9 flipped); checkpoint.py REFUSES to sign
  over a disagreement with the newest existing checkpoint
  (CHECKPOINT_REFUSED, heartbeat false) unless a two-key anchor
  acceptance already recorded that checkpoint. A10/A11 flipped.
  **Found by the new tests, fixed in 1.2.1:** Chain's lock is now
  an RLock — append() holds the lock while _note_quarantine
  re-enters append() to chain SPOOL_QUARANTINE; with a plain
  Lock, a non-transactional append after a quarantine
  self-deadlocked.
- **P12 Approver visibility — DONE.** A SUPERVISOR approver's
  /tier3/pending shows plate_fragment, case_no, why, auth_basis,
  tier, requester. Detectives see only their own requests,
  plate-free. (R17.)
- **P13 Holds, hotlist delete, misc fail-closes — DONE.**
  review_by must be a real ISO date, > today, ≤ today+HOLD_DAYS;
  HOLD_DAYS above 150 refuses to start (A37); overdue holds
  surface in /health degraded; the shared protection predicate
  caps ALL hit protection at 150 days from placement and the
  purge deletes past it regardless of paperwork — an unconfirmed
  disposition protects nothing at any age (A19/A34 flipped).
  DELETE /hotlist identifies the membership (id, or
  plate+state+list), DELETES the row, chains HOTLIST_REMOVE with
  plate_ref; no match ⇒ 404 (A24 flipped). GET /audit limit
  outside integer 1..1000 ⇒ 400 (A17 flipped). Negative
  Content-Length ⇒ 400 in janus.py and frigate_bridge.py.
  /audit/verify returns the same 60s cached detached verify as
  /health and never verifies under DBLOCK (A18 — see gate (a)
  note). Frigate redelivery with a different plate or higher
  confidence supersedes the stored read in place and chains
  READ_SUPERSEDED (A12 flipped). config_closed() is audited
  across all data endpoints, with a route-enumeration test that
  fails if a GET data route lacks it. AUTH_FAIL chaining gained
  a global per-minute cap (A20 flipped), and case/why hashes are
  keyed HMACs (A36 flipped: brute force over the case-number
  space recovers nothing).
- **P14 Docs — DONE.** COMPACT.md updated (tier strictness,
  report binding, query-time gate + missing-checkpoint closure,
  mandatory pinning, derived seed, direction-correct
  delinquency, witness signatures); module docstrings updated
  in janus.py, sentinel.py, and the touched scripts; this
  report.

## Builders'-suite changes that are part of the patch

The suite was extended, and four legacy checks were updated to
the new intended behavior (each was asserting a 1.2 behavior the
council rejected): registry version string; /audit limit (clamp
→ 400 contract); rotation publishing (client seeds removed —
republish difference now comes from the moved chain root);
publish_witness (now requires a real git repo + bare remote);
restore (the operator pin is passed explicitly, modeling the
documented flow); the anchor-tamper simulation (recomputes with
the current v2 formula — the attacker has the public code; what
they cannot fix is the published checkpoint); sentinel_audit URL
mode (now passes --pubkey, plus a no-pin refusal check).

## Remaining honest limitations

- Act 668 of 2025 is still flagged-not-settled (secondary source
  only) — routed to the city attorney; no retention logic was
  changed over it.
- A missing `tier` on /share/query defaults to 2 (see P1 note).
- The witness heartbeat remains best-effort by design: if Janus
  is unreachable, publish_witness prints the failure but the
  publish result stands on the git proof, which is the witness
  that matters.
