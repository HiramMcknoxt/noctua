# The NOCTUA Data-Sharing Compact

*How agencies share license-plate data with each other — and the price of admission.*

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

## How it works

Every member agency runs a system that keeps a tamper-evident audit
chain (in NOCTUA: the Sentinel chain inside Janus) and publishes
**signed checkpoints** of that chain — a dated statement of the
chain's root hash and entry count, HMAC-signed so it cannot be
quietly rewritten later.

Before Agency A may query Agency B's data, **both** of these must be
fresh (within 26 hours):

1. **A has audited B.** A's audit tool fetched B's latest published
   checkpoint and B's current chain root, verified B's chain end to
   end, and confirmed the chain's hash at the checkpoint's entry
   count matches the checkpoint B published. A records the result on
   its own books (`CROSS_AUDIT_OK`), and posts a **checkpoint
   receipt** to B attesting to the checkpoint it verified.
2. **B has audited A** — the same thing in the other direction,
   leaving B's `CROSS_AUDIT_OK` on B's books and B's receipt on A's.

When A then sends B a share query, B's software checks all three
legs — A is an active member, B holds a fresh `CROSS_AUDIT_OK` for A,
and B holds A's fresh receipt for B's own checkpoint. If any leg is
missing, the query is refused with `SHARE_BLOCKED` naming the missing
leg, and the refusal itself is written into B's audit chain. There is
no override switch.

A successful share query runs under the **same rules as a local
search**: the requesting agency's case reference and justification
are recorded as the partner's references; suppressed plates (for
example, plates under a protection order) are excluded identically;
the Tier 2 contemporaneous window applies identically; results are
shaped identically. The share is chained on the answering side as
`SHARE_OUT` with the plate reference (a keyed hash, never plate text)
and the result count.

## What a member agency must run

- A system that keeps a **hash-chained, append-only audit log** of
  every plate query and its justification — NOCTUA, or any system
  that can meet the same interface.
- **Signed checkpoints** of that chain, published at least daily,
  that other members can fetch and verify.
- An **auditor endpoint** a partner can use read-only: chain root,
  chain verification, and individual chain entries (so a partner can
  confirm the hash at a checkpoint's entry count).
- A **receipt endpoint** where a partner records its attestation of
  your checkpoint.
- The **sharing gate** itself: refuse queries when either audit leg
  is stale, and chain the refusal.

An agency whose system cannot do these things cannot be a member.
That is not a judgment about the agency; it is the mechanism. The
audit is the admission ticket.

## Suspension

A supervisor at any member agency may suspend a partner immediately
(`POST /compact/suspend`). Suspension blocks all sharing with that
partner on the next query — no grace period, no cached permission.
Reinstatement is also a supervisor act, and both are written into the
audit chain. Suspension is the response to a failed audit, a missed
audit, or a loss of confidence; the Compact does not require the
suspending agency to prove anything to anyone before protecting its
own data.

## Audit rotation — the anti-capture mechanism

The daily checkpoint gate above proves each member's chain is intact
*today*. The rotation governs the deeper, periodic audit duty — and
it exists because fixed audit pairs go cozy. Two agencies that audit
only each other, forever, eventually stop auditing.

- **Activation.** Rotation is active only at **3 or more members**.
  At 2 members the pairing is static — each audits the other — and
  the schedule output says so plainly. Below 2 there is nothing to
  rotate.
- **Deterministic, not rigged.** A cycle's schedule is a pure
  function of a published seed: SHA-256 of the cycle start date plus
  the sorted member list. Anyone with the member list recomputes the
  identical schedule. Janus refuses to record a published schedule
  that does not recompute from the seed (`ROTATION_REJECTED`).
- **The cycle.** Members are arranged by the circle method: over one
  full cycle (base rounds plus a mirrored half with orientations
  flipped), **every member audits every other member exactly once**,
  and no round ever contains a mutual pair (A auditing B while B
  audits A in the same round). One round is one audit period —
  default 90 days (`COMPACT_ROTATION_PERIOD_DAYS`).
- **The bye is a job.** With an odd number of members, one member
  sits out each round. That member is the round's **witness**: their
  duty is to verify that every member published its checkpoints that
  period. The witness is named in the schedule.
- **Joins and leaves** take effect at the **next cycle**. A published
  cycle never reshuffles mid-cycle.
- **Duty and delinquency.** Completing a rotation duty means filing a
  passing cross-audit (`CROSS_AUDIT_OK`) for your assigned agency
  within the period. `GET /compact/rotation/status` shows the current
  cycle, each assignment, and who has filed. A member missing **two
  consecutive** duties is flagged `rotation_delinquent` in that
  output. The flag is all the code does — consequences for
  delinquency belong to the Compact agreement, not the software.
- **What rotation does not change:** the daily 26-hour reciprocity
  gate on share queries. Rotation governs who owes whom a deep audit
  each quarter; the daily gate governs whether any data moves today.

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
