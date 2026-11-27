# The NOCTUA Data-Sharing Compact

*How agencies share license-plate data with each other — and the price of admission.*

*This document describes the Compact as implemented in NOCTUA 1.2.8.
Where earlier versions differed, 1.2.8 is what the code does.*

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
   boolean is never accepted. **The report is bound to its subject
   and its moment (1.2.1, P7):** the report's own `agency` field
   must equal the agency it is filed under, its own `ts` must be
   within 26 hours, and the recorded row stores the REPORT's
   timestamp — a signed report from last year cannot be re-filed as
   today's audit, nor re-filed under a different partner's name.
2. **B's gate reads the LATEST audit — by the report's own
   clock.** When B later evaluates A's share query, it reads the
   audit result B holds for A with the newest REPORT timestamp
   (filed by B's own auditor, symmetrically): it must be a pass
   **and** no more than 26 hours old. **Any newer failing audit
   closes the gate immediately** — a pass from yesterday does not
   survive a failure from this morning. 1.2.2 (Q21): "latest" is
   the report's timestamp, not the order reports happened to be
   FILED in — 1.2.1 read the last-filed row, so re-filing an old
   signed pass after a newer failure reopened the gate. Re-filing
   is now refused outright (a duplicate report hash, or a report
   older than the newest on file, is a 409), and the auditor's
   tool itself fails a partner checkpoint older than 26 hours and
   advances its high-water mark to the live verified chain height,
   so a rewrite above the last checkpoint is visible at the next
   audit.
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
legs **at query time** — A is an active (not suspended) partner,
the latest-audit leg, and the receipt leg — against the state as
it stands at that moment, including that **B's newest checkpoint
exists at all: if there is no checkpoint, the gate is CLOSED**
(1.2.1, P7; 1.2 evaluated the receipt leg against no checkpoint
and let the gate stand open). If any leg is missing, the query is
refused with `SHARE_BLOCKED` naming the missing leg, and the
refusal itself is written into B's audit chain. There is no
override switch.

**Key pinning is mandatory in the tooling (1.2.1, P8).**
`compact.py` refuses to run without `--partner-pubkey` or
`--partner-fingerprint`; `sentinel_audit.py` URL mode and
`rotation.py --verify` (for a signed schedule) refuse likewise. No
code path verifies a signature against a key embedded in the very
document being verified — a checkpoint that carries its own key
proves nothing. `--our-agency` is required (a receipt is signed
under OUR identity, never defaulted to the partner's name), and
the receipt is signed with OUR signing key, named explicitly via
`--signing-key` — never with any partner credential.

A successful share query runs under the **same rules as a local
search**, with three share-specific limits:

- **Tier 2 only — exactly, and only as the integer 2 (1.2.1, P1).**
  Shares are capped at the contemporaneous tier. The ONLY accepted
  `tier` is the JSON integer `2`: tier 1, tier 3, `true`, `"2"`, and
  `2.0` are all refused as `SHARE_BLOCKED` with the refused tier
  chained as a coded value. (1.2's loose comparison let tier 1 —
  and JSON `true`, which Python reads as 1 — run a FULL historical
  search.) Historical (Tier 3) data never moves through the Compact.
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
- **The seed deals the cards — and nobody can pick it (1.2.2,
  Q23).** 1.2.1 derived the seed from public facts (members ‖
  cycle_start ‖ chain root) and called it unchosen; round 5
  showed the publisher still chose cycle_start and could move the
  root with an ordinary read, so the pairing remained grindable.
  1.2.2 publishes by **commit-reveal**: a supervisor opens the
  cycle (`POST /compact/rotation/commit`), every member commits
  the SHA-256 of a secret nonce, then every member reveals its
  nonce, and only then can the cycle publish
  (`POST /compact/rotation`). The seed is SHA-256 over the sorted
  members, the cycle start, and **the revealed nonces** — no
  party, the publisher included, can predict or bias it without
  breaking a commitment that is already on the chain. The cycle
  start is also fixed by rule: the first cycle may not be
  backdated, and every later cycle starts the day the previous
  one ends. The published document carries the nonces, the seed,
  the cycle start, the period, and the chain root, and its
  Ed25519 signature covers all of them; any partner can recompute
  the seed and the schedule from the document alone
  (`scripts/rotation.py --verify`). One builder
  (`sentinel.rotation_schedule`) produces the rounds for both
  Janus and the verifier. In each round, one member audits the
  next member in the permuted order, cyclically, so over a full
  cycle of *n* rounds **every member audits exactly once and is
  audited exactly once**, and nobody audits themselves. A cycle
  needs at least 2 members; the home agency may be a member
  without registering as its own partner.
- **Validation at publication.** Members are deduplicated and must
  all be registered, non-suspended partners; the cycle start must be
  a real calendar date; the period must be 7–120 days (default 90).
  The published schedule is Ed25519-signed. **A new publication
  cannot replace a cycle that is still active** — voiding one takes
  two keys (a supervisor requests, the auditor confirms) and chains
  `ROTATION_VOID`.
- **Joins and leaves** take effect at the **next cycle**. A published
  cycle never reshuffles mid-cycle.
- **Duty and delinquency (1.2.1, P9).** Duty is tracked from the
  records themselves, in each round's window, **direction-correct
  and success-only**: audits **of** us are the auditor's VERIFIED
  checkpoint receipts (`compact_receipts`); audits **by** us are
  our **ok=1** audit results against the audited agency
  (`compact_audits`). 1.2 counted both tables against the auditor
  regardless of direction or outcome — a failed audit "filed", and
  a receipt about someone else counted. Delinquency is per agency
  across **COMPLETED rounds only** (round end before today): a
  member that owed a filing in a completed round and filed in none
  of its completed rounds is flagged delinquent in
  `GET /compact/rotation/status`. **Future rounds never count** —
  1.2 listed a not-yet-started cycle's members as delinquent on
  publication day. Each round also carries a **witness duty**: a
  member posts its checkpoint-verification attestation for the
  round (`POST /compact/witness`). An attestation is accepted only
  for an agency that is a **member of the named cycle**, only
  from a **supervisor of the home agency attesting for the home
  agency**, or from the partner's **registered auditor
  identity** — an Ed25519 signature over the attestation, verified
  against the public key registered for the agency the attestation
  is about — and every accepted attestation chains
  `WITNESS_ATTEST`. (1.2.1 still let a local supervisor attest for
  an arbitrary partner by name; 1.2.2 closed that — round 5,
  ChatGPT F3.) (1.2 let ANY authenticated role, including the
  ingest service account, attest for another agency, unsigned and
  unchained.) The delinquency flag is all the code does —
  consequences belong to the Compact agreement, not the software.
- **Who the witness is (1.2.4, S5):** each round's designated
  witness is a member who is neither that round's auditor nor its
  audited agency. With three members that is the remaining member;
  with four or more, designation rotates deterministically among
  the eligible members by round number, and rotation status counts
  that member's filings — split into **positive** and **adverse**
  attestations, so a witness reporting a failed verification is
  never counted as a pass. **Two-member compacts have no third
  party:** the round's auditor attests its own audit, and rotation
  status labels that round `witness_self_attestation: true`. The
  independent-witness guarantee activates at **n≥3**; at n=2 the
  Compact's check on an audit is the reciprocal audit itself, and
  the status output says so rather than dressing a self-attestation
  as an independent one.
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
