# The NOCTUA Data-Sharing Compact

*How agencies share license-plate data with each other — and the price of admission.*

*This document describes the Compact as implemented in NOCTUA 1.2.
Where earlier versions differed, 1.2 is what the code does.*

---

## The principle

The Compact grows out of a simple rule, stated in the Data-Sharing
Compact draft this design is anchored in: **shared security, access,
and reciprocal audit standards are the price of participation.** An
agency that wants to query another agency's plate data must first
let that agency audit its books — and must keep letting it, on a
schedule neither side controls.

Data sharing between police agencies usually runs on trust and
memoranda. This one runs on verification:

> **No cross-audit, no data — in both directions, enforced by the
> software, not by trust.**

## Keys: two kinds, two jobs (1.2)

1.2 separates the two secrets earlier versions conflated:

- The **audit key** is an HMAC secret. It keys the plate references
  (`pref:` hashes) and **never leaves the box** — it is not a
  credential a partner can hold, because anyone holding it could
  dictionary-attack the plate space offline.
- The **signing key** is an **Ed25519 keypair** generated beside the
  database (private key 0600). Checkpoints, audit reports, rotation
  schedules, and Compact receipts are signed with it. The **public
  key is exportable** and is what a partner registers at enrollment;
  its SHA-256 fingerprint is stored with the partner record
  (`audit_key_fingerprint`). Everything a partner must verify is
  verified against that public key — never against the audit key.

## How it works

Every member agency runs a system that keeps a tamper-evident audit
chain (in NOCTUA: the Sentinel chain inside Janus) and publishes
**signed checkpoints** of that chain — a dated statement of the
chain's root hash and entry count, Ed25519-signed so it cannot be
quietly rewritten later.

Before Agency A may query Agency B's data, **all** of these must
hold, each of them fresh:

1. **A has audited B — and B's books say so, lately.** A's auditor
   (`scripts/compact.py`, running with the read-only `chain_auditor`
   credential described below) independently recomputes B's chain
   from the last `(seq, hash)` A stored for B, verifies B's newest
   checkpoint signature against B's registered public key, and only
   then posts a **signed audit report** to A's own Janus
   (`POST /compact/audit-result`). The endpoint verifies the
   report's Ed25519 signature and records the report's hash — a bare
   boolean is never accepted.
2. **B's gate reads the LATEST audit row.** When B later evaluates
   A's share query, it reads the most recent audit result B holds
   for A (filed by B's own auditor, symmetrically): it must be a
   pass **and** no more than 26 hours old. **Any newer failing audit
   closes the gate immediately** — a pass from yesterday does not
   survive a failure from this morning.
3. **A holds a receipt for B's NEWEST checkpoint.** After a passing
   audit, A's tool posts a **checkpoint receipt** to B attesting to
   the checkpoint it verified. The receipt must name B's newest
   checkpoint exactly (root and entry count equal to the latest) and
   carry A's Ed25519 signature over `(root, entries, checkpoint_ts,
   agency)`, verified against A's registered public key. Freshness
   is measured from the checkpoint's own timestamp (≤ 26 hours). A
   receipt for an older checkpoint — replayed after B has published
   a newer one — is refused.

When A then sends B a share query, B's software checks all the
legs — A is an active (not suspended) partner, the latest-audit leg,
and the receipt leg. If any leg is missing, the query is refused
with `SHARE_BLOCKED` naming the missing leg, and the refusal itself
is written into B's audit chain. There is no override switch.

A successful share query runs under the **same rules as a local
search**, with three share-specific limits:

- **Tier 2 only.** Shares are capped at the contemporaneous tier —
  a `tier` above 2 is refused. Historical (Tier 3) data never moves
  through the Compact.
- **The partner's references are required and stay theirs.** The
  query must carry a non-empty `case_ref`, a `why`, and the
  partner's `basis_type`. The `case_ref` is the *partner's* case
  reference — it is never validated against the answering agency's
  case list (one agency cannot validate another's cases; the audit
  is what vouches for the partner's gatekeeping) — but the catch-all
  ban still applies: a `PATROL`/`TEST`-style reference is refused
  here as everywhere. The `why` text is stored in the answering
  agency's database only; the chain carries `why_hash`, never the
  text.
- **Rate limit.** 60 queries per partner per rolling hour. Tripping
  it returns 429 and chains `SHARE_RATE_LIMIT`.

Suppressed plates (for example, plates under a protection order)
are excluded identically, the Tier 2 window applies identically,
results are shaped identically, and the stale-configuration
fail-closed check applies to shares as to every data endpoint. The
share is chained on the answering side as `SHARE_OUT` with the
plate reference (a keyed hash, never plate text), the case and
justification hashes, and the result count.

## The chain_auditor credential

Cross-audits run under a dedicated role, `chain_auditor`, that can
read **only** the five things an audit needs — `GET /audit`,
`/audit/root`, `/audit/verify`, `/audit/range`, and
`/compact/checkpoint` — and is barred from hits, the hotlist,
stats, reports, Tier 3, and search. The credential a partner holds
against your system can verify your chain end to end and cannot
touch your data. (`scripts/provision.py` issues the role.)

## What a member agency must run

- A system that keeps a **hash-chained, append-only audit log** of
  every plate query and its justification — NOCTUA, or any system
  that can meet the same interface.
- **Ed25519-signed checkpoints** of that chain, published at least
  daily, that other members can fetch and verify.
- An **auditor endpoint** a partner's `chain_auditor` can use
  read-only: chain root, chain verification, chain entries by range
  (so a partner can recompute your chain, not just trust your
  verify endpoint), and your newest checkpoint.
- A **receipt endpoint** where a partner records its signed
  attestation of your checkpoint.
- The **sharing gate** itself: refuse queries when either audit leg
  is stale or failed, and chain the refusal.
- **Backups that include the evidence bundles** (each bundle 0600),
  under a backup manifest signed with the agency's Ed25519 key — a
  member's chain of custody must survive a restore, and an unsigned
  manifest is refused at restore time.

An agency whose system cannot do these things cannot be a member.
That is not a judgment about the agency; it is the mechanism. The
audit is the admission ticket.

## Suspension

A supervisor at any member agency may suspend a partner immediately
(`POST /compact/suspend`). Suspension blocks all sharing with that
partner on the next query — no grace period, no cached permission.
Reinstatement (`POST /compact/reinstate`) is also a supervisor act,
and **requires a fresh passing audit (≤ 26 hours) on file** — a
partner is not reinstated on the strength of the record it fell
behind on. Both acts are written into the audit chain. Suspension
is the response to a failed audit, a missed audit, or a loss of
confidence; the Compact does not require the suspending agency to
prove anything to anyone before protecting its own data.

## Audit rotation — the anti-capture mechanism

The daily checkpoint gate above proves each member's chain is intact
*today*. The rotation governs the deeper, periodic audit duty — and
it exists because fixed audit pairs go cozy. Two agencies that audit
only each other, forever, eventually stop auditing.

- **Activation.** At **2 members** the pairing is static — each
  audits the other — and the schedule says so plainly. Below 2 there
  is nothing to rotate. Rotation proper starts at 3.
- **The seed actually deals the cards (1.2).** A cycle's schedule is
  a deterministic permutation of the member list derived from a
  published seed: SHA-256 of the seed drives a Fisher-Yates shuffle
  of the slots (the algorithm is documented on `build_schedule` in
  the code). Identical inputs reproduce the schedule byte-identically;
  a different seed — or a different cycle start — deals a different
  order. In each round, one member audits the next member in the
  permuted order, cyclically, so over a full cycle of *n* rounds
  **every member audits exactly once and is audited exactly once**,
  and nobody audits themselves.
- **Validation at publication.** Members are deduplicated and must
  all be registered, non-suspended partners; the cycle start must be
  a real calendar date; the period must be 7–120 days (default 90).
  The published schedule is Ed25519-signed. **A new publication
  cannot replace a cycle that is still active** — voiding one takes
  two keys (a supervisor requests, the auditor confirms) and chains
  `ROTATION_VOID`.
- **Joins and leaves** take effect at the **next cycle**. A published
  cycle never reshuffles mid-cycle.
- **Duty and delinquency.** Duty is tracked from the records
  themselves, in each round's window: audits **of** us are the
  signed checkpoint receipts a member filed; audits **by** us are
  our signed audit results. Each round also carries a **witness
  duty**: a member posts its checkpoint-verification attestation for
  the round (`POST /compact/witness`), and
  `GET /compact/rotation/status` shows, per round, who filed what —
  receipts, audits, and the witness attestation. A member that owed
  an assignment in **2 consecutive rounds and filed in neither** is
  flagged delinquent in that output. The flag is all the code does —
  consequences for delinquency belong to the Compact agreement, not
  the software.
- **What rotation does not change:** the daily 26-hour reciprocity
  gate on share queries. Rotation governs who owes whom a deep audit
  each period; the daily gate governs whether any data moves today.

## What the Compact does not do

It does not make another agency's data *yours*. A share query returns
what the answering agency's rules allow, shaped the way its own
officers would see it. It does not pool data, mirror databases, or
create a shared watchlist. And it does not certify that a member's
*policies* are wise — only that its audit chain is intact, its
checkpoints are genuine, and its queries left the same paper trail
yours do. Judgment about a partner's practices remains a human,
political decision — which is why suspension is one supervisor's
signature, not a committee vote.
