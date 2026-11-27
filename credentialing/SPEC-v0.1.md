# The Prytaneum — Credentialing for SURNIA

## Spec v0.1 — DRAFT for council review, not built (Nov 25, 2026)

**Prytaneum** — the public hearth of a Greek city, where the
sacred fire burned continuously under the city's care. When a
city founded a colony, the colonists carried fire from the
mother city's prytaneum to light the new city's hearth: the
flame was the same fire, and carrying it was the act that made
the new city a city. The Prytaneum is the foundation that keeps
that fire for SURNIA — it certifies the cities that run the
system, carries the system to new cities (the golden image
travels on the Prytaneum drive), and can, under published rules
and with due process, let a city's fire go out. This document
is the combined charter skeleton and technical mechanism spec
for that foundation.

Status gate: this is a draft for council review. It is not
built, and building remains gated on SURNIA code convergence
and Corey's explicit go after review. The design decisions in
§2 are Corey's, directed Nov 25, 2026, and are not open for
relitigation by reviewers; the numbers marked **[charter
parameter]** are recommendations for the charter to set, and
the governance questions in §13 are Corey's to answer. Nothing
in this spec authorizes any code change to Janus or Sentinel.

The one-sentence version: **a city runs SURNIA under a signed,
time-boxed credential from the foundation; the credential is
verified entirely offline, renewed quarterly by an affirmative
act of the foundation, and revocable only by multiple signers
after published notice and a grace period — and no state of
the credential, including the foundation's own death, can ever
lock a city out of its own archive.**

Background documents this spec builds on and does not restate:
the Data-Sharing Compact (`janus127/COMPACT.md` — the
reciprocal cross-audit network the credential interlocks with),
the installation guide (`docs/INSTALL.md`, especially §6 on
keys and §8 on the go-live checklist), and the 1.2.7 ceremony
design (Council Round 9 synthesis §4, item V4 — the ceremony
state the credential is presented inside).

---

## 1. What the Prytaneum is, and is not

**It is** a credentialing foundation. It publishes a set of
operating rules for running SURNIA. A city that adopts the
rules signs the license agreement and receives a credential: a
signed, time-limited statement by the foundation that this
install, bound to this signing key, is certified. The genuine
build checks the credential locally and continuously. The
foundation renews credentials on a quarterly cadence, and it
can revoke a credential — for abuse of the technology or
breach of the published rules — through a proceeding whose
steps are fixed in advance and encoded in the mechanism itself.

**It is not** a vendor. It holds no city's data, operates no
city's system, and has no remote access to any install. There
is no phone-home in this design: no install contacts the
foundation to ask permission to run, and the foundation cannot
reach into a running system. Every check in this spec is a
local verification of a signed artifact the city already holds
— the same posture as the Compact's checkpoints and the ACIC
hot-list file, both of which SURNIA already verifies offline.

**It is not** a kill switch. Revocation is slow on purpose:
notice, a response window, a threshold-signed decision, a
grace period, and daily warnings before anything stops — and
what stops is new capture, never access to what a city already
lawfully collected (§7).

**It is not** a guarantee the software can enforce against a
determined adversary. The source is open. §10 says plainly
what a fork can and cannot do, and where the real teeth are.

---

## 2. Settled design decisions

These are directed and fixed for this draft. Reviewers attack
the mechanism's execution of them, not the decisions
themselves.

1. **Timed certificates.** Operation requires a signed
   credential with a fixed term. The term is a foundation-set
   parameter; the default is **90 days** (quarterly). No valid
   unexpired credential, no new captures. Verification is
   fully offline.
2. **Renewal is an affirmative foundation act.** A renewal
   officer of the foundation authenticates with two factors
   before countersigning. The city presents its current
   credential and its own admin attestation. Renewal is never
   automatic and never silent.
3. **Revocation by threshold.** Revocation takes effect
   through a signed revocation list, distributed out-of-band
   like the ACIC hot-list file. Entries are valid only with
   signatures from multiple foundation signers meeting a
   threshold. No individual — officer, signer, or chair — can
   revoke a city alone.
4. **Due process is encoded, not promised.** Published
   notice, a grace period before capture-stop, daily operator
   warnings inside every window, and credential status
   surfaced in `/health` and on the public dashboard.
   Uncertified operation on the genuine build is publicly
   visible; it is never silently possible.
5. **The archive is never hostage.** Lapse or revocation
   stops new capture after grace. The audit chain, evidence,
   search under existing legal process, and exports remain
   available forever (§7's table is normative).
6. **The credential lives inside the existing ceremony.** It
   is presented and verified during the provisioning ceremony
   (the 1.2.7 ceremony state). A golden-image install boots to
   ceremony and cannot leave it for production use without a
   valid credential.
7. **The Compact interlocks.** Cross-audit handshakes require
   a valid credential from both peers. A lapsed, revoked, or
   forked instance drops out of the mutual-audit network
   automatically (§9).
8. **The foundation's death is a designed state, not a
   catastrophe.** If renewals become impossible through the
   foundation's own fault — dissolution, defunding, key loss —
   installs enter an ORPHANED state and keep operating under
   their last credential, publicly flagged, until a successor
   is chartered or the charter's wind-down executes (§8).
9. **The fork analysis is stated in the open** (§10).

---

## 3. Objects and roles

### 3.1 Objects

- **Credential.** A signed document issued by the foundation
  to one install. Fields, at spec level: format version;
  credential ID; agency (city) identifier; the install's
  Ed25519 signing-key fingerprint (the binding — the same key
  whose public half Compact partners pin); credential sequence
  number (monotonic per install; a renewal supersedes by
  sequence); issued-at; not-before; expires-at; term class
  (`standard` or `probationary`, §5.4); issuer key ID;
  foundation signature. The credential contains no plate data
  and no personal data beyond the agency identifier.
- **Revocation list.** A signed document: format version; list
  sequence number (monotonic); issued-at; entries, each naming
  a credential ID (or an install signing-key fingerprint,
  where a whole binding is revoked), the entry's effective
  date, and a reason code; the threshold signature block
  (§6.2). Lists are append-only in effect: a correction is a
  new list with a higher sequence, never an edit to a
  published list.
- **Foundation key set.** Two tiers (§8.3): a root key set,
  held offline by the threshold signers, which certifies
  operational keys; and an operational issuance key, used by
  renewal officers for issuance and renewal countersignatures.
  Installs pin the foundation's root-certified key set the
  same way Compact tooling pins partner keys — no artifact is
  ever verified against a key carried inside the artifact
  itself.
- **Golden image / Prytaneum drive.** The signed install
  image. It contains no credential and no city keys; it boots
  to ceremony (§4).

### 3.2 Roles

- **Foundation** — the credentialing body (§11 sketches its
  composition). Acts through officers and signers below.
- **Renewal officer** — a foundation officer who processes
  renewals. Authenticates with two factors to the foundation's
  signing tooling before any countersignature (§5.2).
- **Revocation signer** — one of the charter-named holders of
  a revocation signing key. Revocation requires a threshold
  of them (§6.2).
- **City administrator** — the install's System Administrator
  (INSTALL §8 names this role per city). Presents credentials,
  files renewal requests and attestations, receives notices.
- **City auditor** — the install's outside-auditor role as in
  INSTALL §6/§8. Read-only; sees credential state like every
  other chained fact.

---

## 4. Issuance and the ceremony

### 4.1 First issuance

1. The city adopts the published rules and executes the
   license agreement (a legal act, outside the software; §10.3
   explains why the agreement is load-bearing).
2. The city installs from the golden image and provisions its
   install in the ordinary way: keys generated beside the
   database, humans enrolled. The install is in the ceremony
   state (1.2.7, V4): ingest, safety writes, provisioning,
   auth admin, and health are open; the human disclosure
   surface is refused for key-only accounts.
3. The city administrator presents the install's signing-key
   fingerprint and agency identifier to the foundation,
   out-of-band, through the channel the charter specifies.
4. The foundation verifies the agreement is executed, issues
   credential sequence 1 bound to that fingerprint, signed
   with the operational issuance key.
5. The administrator presents the credential to the install
   during the ceremony (`provision.py` gains a present-
   credential step; §14). The install verifies the signature
   against its pinned foundation key set, checks the binding
   fingerprint against its own signing key, and chains
   `CREDENTIAL_PRESENTED` with the credential ID, sequence,
   and expiry — never the credential's full text.
6. Ceremony exit to production now requires **both** existing
   conditions (every human enrolled ACTIVE, per INSTALL §8)
   **and** a valid credential on file. An install that is
   provisioned but uncredentialed remains in ceremony posture
   for production purposes: bench and lab work proceed exactly
   as 1.2.7 specifies; production capture does not begin.

### 4.2 The continuing condition

Holding a valid credential is not a one-time ceremony event;
it is a continuing state the install evaluates at boot and on
a daily periodic check (the stale case-list feed is the
existing precedent for a periodic fail-closed check). The
evaluated state is one of:

| State | Meaning |
|---|---|
| `valid` | Credential present, signature good, unexpired, not listed |
| `expiring` | `valid`, inside the renewal window (§5.1) |
| `grace` | Expired or revoked, inside the applicable grace period (§§5.5, 6.4) |
| `lapsed` | Expired, grace exhausted, no revocation — capture stopped |
| `revoked` | On the freshest revocation list held, grace exhausted — capture stopped |
| `orphaned` | §8: foundation fault makes renewal impossible — capture continues, flagged |
| `uncertified` | No credential on file (pre-issuance, or a fork that stripped it) |

The state, the credential ID, its expiry, the freshest
revocation list sequence held, and the list's age are reported
in `/health` alongside the existing `totp.state` block, and
every state transition is chained. A state the public
dashboard shows is a state the city cannot quietly edit: the
dashboard reads the same chained facts the auditor does.

### 4.3 Lab mode

`SURNIA_LAB=1` is unaffected. Lab installs carry no credential,
make no production captures, and are refused on a provisioned
install under the existing 1.2.7 rule. The credential gate
binds production posture only.

---

## 5. Renewal

### 5.1 The renewal window

The renewal window opens **30 days** before expiry
**[charter parameter]** and closes at expiry. Inside the
window, `/health` reports `expiring`, the operator console
shows the days remaining, and the install chains a daily
`CREDENTIAL_EXPIRING` warning entry. A renewal completed
inside the window takes its term from the **previous
credential's expiry**, not from the signing date — renewing
early never shortens or drifts the cadence, and a city is
never punished for renewing on day one of the window.

### 5.2 The renewal flow, end to end

1. **Request.** The city administrator generates a renewal
   request from the install: the current credential ID and
   sequence, the install's signing-key fingerprint, and a
   fresh attestation (§5.3), signed with the install's signing
   key. The request is chained locally
   (`CREDENTIAL_RENEWAL_REQUESTED`) before it leaves the box —
   this chain entry matters later (§8.2).
2. **Delivery.** The request reaches the foundation
   out-of-band (the charter names the channel; email to a
   published foundation address is the expected default, as
   with the ACIC correspondence). Delivery is the city's
   responsibility; the foundation acknowledges receipt
   out-of-band.
3. **Officer authentication.** A renewal officer opens the
   foundation's signing tooling and authenticates with **two
   factors** — the officer's individual credential plus a
   second factor — before the tooling will produce a
   countersignature. An unauthenticated session cannot sign.
   Officer authentication events are logged on the foundation
   side; the charter sets the foundation's own log-retention
   rule.
4. **Review.** The officer confirms: the agreement is in good
   standing; no revocation proceeding is open against the
   city (or §5.4 applies); the attestation is present and
   signed by the bound key; the requested binding fingerprint
   matches the credential on file (a mismatch is a rebind,
   §12.4, not a renewal).
5. **Countersignature.** The officer countersigns the new
   credential (next sequence, term per §5.1) with the
   operational issuance key.
6. **Presentation.** The city administrator presents the new
   credential to the install exactly as in §4.1 step 5. The
   install verifies signature, binding, and sequence (a
   credential with a sequence not greater than the one on
   file is refused and chained as an anomaly), stores it, and
   chains `CREDENTIAL_RENEWED`.

### 5.3 The city's attestation

Renewal carries an admin attestation, signed with the
install's signing key, that to the administrator's knowledge:
the published rules are being followed; retention is
configured within the charter ceiling; no undisclosed
third-party sharing has occurred; incidents required to be
disclosed have been disclosed. The attestation is a signed
statement by a named office, not a checkbox — a false
attestation is itself a revocation trigger (§11.3), which is
what gives the quarterly ritual its evidentiary weight.

### 5.4 Renewal during a proceeding or incident

Renewal is not a rubber stamp, and a proceeding is not a
starvation weapon. If a revocation proceeding is open, or a
critical audit failure is unresolved, the foundation has
exactly two moves, both published to the city:

- **Probationary renewal**: a credential of a shorter term
  (**30 days** recommended **[charter parameter]**, term class
  `probationary`, shown as such in `/health` and on the
  dashboard), renewable again on the same basis while the
  proceeding runs; or
- **Hold with reasons**: a written hold naming the proceeding
  and the specific deficiency. A hold does not stop capture by
  itself — the city's current credential runs to its expiry,
  and the §6 process, not the renewal desk, is the only road
  to capture-stop.

What the foundation may not do is simply not answer. An
unanswered, properly filed renewal request is the factual
predicate of the orphaned state (§8.2), and the city's chained
request is the proof it was filed.

### 5.5 Lapse

If the window closes with no renewal: the credential expires,
the install enters `grace` for **14 days** **[charter
parameter]** with daily chained warnings
(`CREDENTIAL_GRACE`), and a renewal presented inside grace is
still accepted (its term runs from the expired credential's
expiry, so grace is not a cadence loophole). At grace
exhaustion the state becomes `lapsed`: capture stops (§7),
and reinstatement is a fresh issuance proceeding under §4,
which the charter may streamline for short lapses.

---

## 6. Revocation

### 6.1 What revocation is

Revocation is the foundation's formal act, after a proceeding
under §11.3, declaring a city's certification withdrawn. It is
distinct from lapse (the city's own omission) and from
suspension inside the Compact (a peer's act protecting its own
data, immediate and unilateral by design — see COMPACT.md;
the Compact's suspension is not a foundation act and this spec
does not change it).

### 6.2 Threshold signature

A revocation list entry is valid only if signed by a
threshold of revocation signers. **Recommendation: 3-of-5**
— five charter-named signers, any three concurring — with a
floor of 2-of-3 for a founding board too small to seat five
**[charter parameter: signer count and threshold]**. The
signers' public keys are part of the foundation key set
installs pin. A list whose threshold is not met is not a
revocation list; installs refuse it, chain the refusal, and
report it in `/health` — a malformed or under-signed list is
treated as an attack indicator, not an administrative error
to be waved through.

### 6.3 The list: form and distribution

- Published **at least weekly and on every change**
  **[charter parameter: cadence]**, even if the change set is
  empty (a heartbeat list: sequence increments, so installs
  can distinguish "no revocations" from "no news").
- Distributed out-of-band by the same pattern as the ACIC
  hot-list file: delivered to a named address at each member
  city and posted at a published location; Compact peers also
  relay the freshest list they hold during cross-audit
  (§9.2), so the list travels on more than one road.
- Each install records the freshest list it has verified
  (highest sequence with a valid threshold signature) and
  chains `REVOCATION_LIST_APPLIED` with the sequence and the
  count of entries naming it (zero included).
- **Absence of the list is never evidence of revocation.**
  Only a signed entry revokes. A list older than **35 days**
  **[charter parameter]** raises `revocation_list_stale` in
  `/health` and on the dashboard — a distribution failure is
  visible, but it stops nothing by itself (§12.2 gives the
  reasoning: the quarterly term is the bound on this failure
  mode, because non-renewal is revocation's certain path).

### 6.4 Effect and timing

A revocation entry carries an effective date set by the
proceeding. The install that finds itself named enters
`grace` on the later of (a) the entry's effective date and
(b) the date the install first holds the list containing it —
a city is never retroactively in breach of a list it could
not have seen. Grace runs **30 days** **[charter parameter]**
from that date, with daily chained warnings and dashboard
display of the reason code. At grace exhaustion the state
becomes `revoked` and capture stops (§7). An appeal under
§11.4 does not automatically stay the clock; the charter
states whether a timely appeal stays capture-stop pending
decision (open question Q4).

### 6.5 Errata

A revocation entered in error is corrected by a new list, at
a higher sequence, whose entry is signed at the same
threshold and names the erroneous entry it withdraws. Both
lists remain in the published record. There is no silent edit
path: the foundation's list history is append-only in public,
the same discipline the Sentinel chain imposes in private.

---

## 7. What stops, and what never stops

Normative. "Stops" means: at capture-stop (lapse or revocation
grace exhausted). Inside grace, nothing has stopped yet —
warnings are the whole of it.

| Surface | At capture-stop | Why |
|---|---|---|
| Plate ingest (`POST /reads`, the Frigate bridge) | **Stops** — refused, refusal chained | This is the capture the credential authorizes |
| New hot-list entries and operational intake of new surveillance data | **Stops** | Intake of new surveillance data is capture by another door |
| Compact share queries, both directions | **Stops** (the interlock already closed it, §9) | Uncertified data does not move, and peers' data does not move to it |
| Tier 3 and all search **of existing data under existing legal process** (warrant / court order on file) | **Never stops** | A court order addressed to records a city lawfully holds is not the foundation's to frustrate |
| Audit chain: append, verification, checkpoints, sink | **Never stops** | The chain is the record of everything, including the capture-stop itself; checkpoints keep publishing so the stop is witnessed |
| Evidence: holds, exports, chain-of-custody production | **Never stops** | Court obligations and pending prosecutions outlive any credential |
| Protection-order suppressions: application and honoring | **Never stops** | Suppression is a safety duty owed to identified people; it does not lapse with a certificate |
| Retention and scheduled deletion | **Never stops** | A lapsed city must keep deleting on schedule; stopping retention would make it *more* non-compliant, and turn the archive into the shadow copy the 14-day promise forbids |
| Backups and restore | **Never stops** | Custody of existing records |
| `/health`, the public dashboard feed | **Never stops** | The stop itself must remain publicly visible |
| Legal holds and disclosure duties (§ 12-12-1808 owner requests and the like) | **Never stops** | Statutory duties run to the city, not to the credential |

The principle the table encodes: **the credential governs
the creation of new surveillance data and the movement of
data between agencies. It does not govern, and can never be
allowed to govern, a city's custody of what it already holds
under law.** A mechanism that could brick evidence, suppress a
protection order, or halt a court-ordered search would be a
greater abuse than the ones it exists to police.

---

## 8. The foundation-death escape

This section is a first-class requirement of the mechanism,
not a contingency footnote. A credentialing system that bricks
every member city when its foundation is defunded, dissolved,
or simply loses its keys has reproduced, at the center, the
exact single-point-of-control failure SURNIA exists to remove
from the edge. The foundation must be **unable** to take the
cities down with it — by accident, by insolvency, or by
capture.

### 8.1 The orphaned state

An install enters `orphaned` when renewal has become
impossible **through the foundation's fault**. Any one of
these triggers is sufficient:

1. The credential has expired, the orphan threshold —
   **45 days** past expiry **[charter parameter]** — has
   passed, and the install's chain shows at least one properly
   filed renewal request inside the renewal window that was
   never answered (no countersignature, no probationary
   renewal, no §5.4 hold with reasons). Silence is the
   foundation's fault by definition here: §5.4 enumerates the
   only answers the foundation may give, and all of them are
   answers.
2. The foundation publishes a signed incapacity or
   dissolution notice (signed at the revocation threshold —
   the foundation's death certificate is a threshold act).
3. A threshold-signed notice announces loss of the operational
   issuance key with no successor key certified within the
   charter's succession window (§8.3).

A revocation entry naming the install, in any list the
install holds, defeats the orphan claim absolutely: a city
cannot orphan its way out of a revocation. The orphan
determination is made **locally**, from chained facts and
signed artifacts the install already holds — it requires no
message from the foundation, which is the point: the escape
must work precisely when the foundation cannot send messages.

### 8.2 Orphan behavior

- Capture **continues** under the last credential held.
- `/health` reports `orphaned`, the dashboard displays
  ORPHANED prominently, and the install chains
  `CREDENTIAL_ORPHANED` with the trigger it relied on. The
  state is a public flag, not a quiet pass: a city operating
  orphaned is visibly uncredentialed-but-operating, and its
  council owns that fact in daylight.
- Everything in §7's "never stops" column is unchanged (it
  never stops anyway).
- Compact peers see the orphan flag in the credential-status
  attestation (§9.1) and treat the peer under the Compact
  agreement's own rule for orphaned members — this spec's
  recommendation is that orphaned peers remain share-eligible
  while flagged, since their chains are still being audited
  and the fault is not theirs; the decision belongs to the
  Compact agreement (open question Q9).
- The orphan state ends when (a) a successor foundation,
  chartered under §8.4, certifies its key set and issues a
  renewal — the install returns to the ordinary cadence; or
  (b) the charter's wind-down clause executes (§8.4).

### 8.3 Foundation keys: compromise and succession

Two tiers, deliberately separated so that no single key's
loss is fatal and no single key's theft is sufficient:

- **Root key set.** Held offline by the revocation signers;
  used only to certify and decertify operational keys and to
  sign foundation-level notices (incapacity, key rotation,
  succession). Root actions are threshold acts.
- **Operational issuance key.** Held in the renewal officers'
  signing tooling; signs credentials and renewals. It is
  certified by the root set, and installs accept a credential
  only if its issuer key chains to a root certification they
  hold.

Compromise handling:

- **Operational key compromised**: the root set publishes a
  threshold-signed rotation notice decertifying the old key
  and certifying its successor. Credentials already issued
  under the compromised key **remain valid until their own
  expiry** unless individually named on a revocation list —
  a key incident must not mass-brick the membership on
  suspicion alone. Renewals proceed under the successor key.
  Installs accept the rotation only from the root set they
  pinned; a rotation notice signed by the compromised
  operational key itself proves nothing and is refused.
- **A signer's key compromised**: the remaining signers,
  meeting threshold without the compromised key, publish a
  list re-keying the signer set (the compromised key's
  signatures cease to count). If the remaining signers cannot
  meet threshold without it, that is a charter crisis handled
  under §8.4's succession path, and installs' orphan trigger
  §8.1(3) is the backstop.
- **Root set lost** (not stolen — destroyed): indistinguishable
  from foundation death from an install's viewpoint, and
  handled by the same escape. This is deliberate: the design
  does not ask installs to adjudicate the foundation's
  internal disasters, only to survive them.

Key succession in the ordinary course (officer departure,
signer rotation) is a root-certified re-keying published the
same way, on the charter's schedule rather than in a crisis.

### 8.4 Succession and wind-down

The charter, at founding, must name its succession path
before the first credential is issued; a foundation that
cannot say who succeeds it is not ready to certify anyone.
The shape this spec requires (the named parties are Corey's
to choose, open question Q7):

- A **designated successor** (an organization, or a rule for
  constituting one — e.g., a member-city assembly), recorded
  in the charter and in a threshold-signed succession
  instrument held by a named escrow holder outside the
  foundation's own officers.
- On succession, the successor generates its own root key
  set and publishes a succession certificate signed under the
  succession instrument. Installs accept the successor's key
  set **only** via that certificate — never via an unsigned
  announcement, and never via the successor's own assertion.
- If no successor is certified within the wind-down window —
  **12 months** from the first orphan trigger date
  **[charter parameter]** — the wind-down clause executes:
  orphaned installs transition on a published schedule to
  archival posture (§7's never-stop column, permanently;
  capture stops at the window's end, with the same daily
  warnings as any grace). Wind-down is slow, announced, and
  dated years in advance by the mechanism itself. What the
  escape forbids is only the sudden brick: the unannounced,
  undated stop that a dead foundation would otherwise
  inflict on cities that did nothing wrong.

---

## 9. The Compact interlock

### 9.1 Credential status in the handshake

The Compact's gate (COMPACT.md) already refuses a share query
when any leg is missing and chains the refusal as
`SHARE_BLOCKED` naming the missing leg. The credential adds
one more leg, of the same kind:

- Each install's checkpoint publication carries a
  **credential-status block**: credential ID, state (§4.2),
  expiry, and the freshest revocation-list sequence the
  install holds — signed as part of the checkpoint, so the
  status a peer reads is the status the install has chained,
  not a claim made in the handshake itself.
- Before answering a share query, the answering install
  evaluates the **requesting peer's** credential state from
  the peer's latest checkpoint: `valid` or `expiring` passes;
  `grace` fails the leg (a peer in grace is a peer whose own
  capture is about to stop; new data movement waits for its
  renewal); `lapsed`, `revoked`, `uncertified`, or an absent
  credential block fails the leg. `orphaned` is evaluated
  under §8.2's Compact rule.
- The answering install also requires **its own** credential
  to be in a passing state to answer at all: data does not
  flow out of an uncertified install either. The interlock
  binds in both directions, as the Compact's audit gate
  already does.
- A failed credential leg is refused as `SHARE_BLOCKED`
  naming the leg (`credential`), chained like every other
  refusal. There is no override switch, as there is none for
  the audit legs.

### 9.2 List relay and fork exclusion

During cross-audit, each side offers the freshest revocation
list it holds; the side with the older list takes the newer
one (after verifying its threshold signature) and chains
`REVOCATION_LIST_APPLIED`. The list therefore propagates
through the audit network even if direct delivery to one city
fails.

A forked instance — one whose credential check has been
stripped — cannot present a credential block signed by a key
the foundation certified, because the block rides inside a
checkpoint signed by the install's own key and the credential
itself is foundation-signed; the fork can omit the block but
cannot forge it. Omission fails the leg. A fork therefore
drops out of the mutual-audit network automatically, without
the foundation or any peer taking an action — the network
simply stops being able to verify it, which under the
Compact's rule (no cross-audit, no data) is exclusion.

---

## 10. The fork analysis — stated in the open

### 10.1 What a fork is, here

The SURNIA source is public. A city whose credential is
revoked can download the source, delete the credential check,
and run the result. Nothing in this spec pretends otherwise,
and any version of this mechanism that did pretend otherwise
would be lying to the cities it certifies. This section is
the honest accounting of what that fork costs the city that
makes it — because the mechanism's real design target is not
making evasion impossible, but making evasion **visible,
attributable, and expensive in exactly the currencies the
city cared about when it sought certification**.

### 10.2 What the fork loses

- **The certification mark.** The mark is a trademark, not a
  code path. A forked install displaying it is committing
  trademark infringement in public, on a public dashboard —
  the one claim in this section that needs no one's
  cooperation to enforce.
- **The Compact.** §9.2: a fork cannot forge a credential
  block, so it cannot pass the credential leg, so no member
  will answer its queries or accept its audits. The fork is
  out of the mutual-audit network the day it forks, and every
  member can see that it is out.
- **Signed builds and updates.** The golden image and update
  packages are foundation-signed and hash-verifiable. A fork
  maintains itself: every future security fix, every battery,
  every council round is theirs to reproduce alone. The
  entire verification apparatus that makes SURNIA credible —
  the rounds, the cold re-runs, the signed releases — is a
  service of the genuine line.
- **ARGUS.** The watchman ships to credentialed installs
  through the same signed channel (see the ARGUS spec). A
  fork runs unwatched by anything but itself.
- **The public record of good standing.** The dashboard and
  the checkpoint stream are how a city *proves* to its own
  citizens that its system is accountable. A fork's
  checkpoints stop attesting a credential state anyone
  recognizes. The absence is itself the announcement.

### 10.3 Where the teeth actually are

- **The license agreement.** Certification is conditioned on
  a signed agreement: operate the genuine build, honor the
  published rules, submit to the proceeding process. Running
  a fork after revocation is a breach of a contract the city
  signed in a council vote — actionable in ordinary courts,
  by an ordinary plaintiff, without any technology.
- **The certification trademark**, as above.
- **The public record.** Every step — proceeding, notice,
  revocation, the fork's disappearance from the Compact — is
  published. A council that votes to fork its police
  surveillance system to evade an accountability revocation
  does so on the record, in daylight, in front of its own
  voters and every neighboring council. The mechanism's
  deepest enforcement is that it makes the evasion a *story
  with documents*.

### 10.4 The threat model, plainly

This mechanism governs participants acting in the open:
cities that sought certification because being seen to comply
is worth something to them. A city determined from the outset
to surveil without accountability was never going to run
accountable software, with or without a credentialing
foundation — it would run a vendor's closed system, or a
fork, and no mechanism in this document could have stopped
it. The foundation exists so that the cities acting in good
faith can prove it, the cities drifting can be corrected
quarterly instead of catastrophically, and the city that
crosses the line loses the proof, the network, and the mark —
publicly. That is the actual threat model, and the mechanism
is sized to it.

---

## 11. Governance skeleton

The politics are Corey's; this section fixes only the shape
the mechanism needs the politics to fill. Every item here is
a placeholder with a job to do, not a decision smuggled in as
structure.

### 11.1 Composition (roles, not names)

- **Board of governors** — sets the published rules and the
  charter parameters; owns the charter and its amendments.
  Recommended constituencies **[for the charter to settle]**:
  municipal representatives from member cities; a
  civil-liberties / privacy seat; a law-enforcement
  practitioner seat; a technical auditor seat; a public
  member seat.
- **Renewal officers** — process issuance and renewal under
  §5; individually authenticated, 2FA-gated; no renewal
  officer may process a renewal for a city they are employed
  by or govern.
- **Revocation signers** — hold the revocation keys; the
  threshold set of §6.2. Drawn so that no single constituency
  holds a threshold alone.
- **Inspector / evidence function** — gathers the record for
  proceedings: Compact cross-audit results, witness
  attestations, published-report compliance, incident
  disclosures. The inspector presents evidence; the inspector
  does not sign revocations.
- **Appeals panel** — members who took no part in the
  proceeding under appeal (§11.4).

### 11.2 The published rules (categories)

Cities agree, in the license agreement, to operate under
published rules in at least these categories. The rules' text
is the charter's; the categories are what the credential
mechanism and the renewal attestation (§5.3) reference:

- **Retention ceiling** — captured data retained no longer
  than the charter cap (which itself sits at or below the
  state statutory ceiling); the attestation names the
  configured value.
- **Judicial authorization for historical search** — Tier 3
  searches only under the configured judicial instruments;
  no informal historical lookups, by anyone, ever.
- **Suppression handling** — protection-order suppressions
  applied within the charter's service window, honored across
  every surface including shares.
- **Audit publication** — checkpoints published on schedule;
  the statutory statistical reports produced and public on
  the charter's cadence; delinquency is itself a rules breach
  (the Compact already flags it; the foundation's rules give
  the flag a consequence).
- **No undisclosed sharing** — data moves only through the
  Compact gate or under legal process; no side channels, no
  vendor back doors, no sale, ever.
- **Identity and enrollment hygiene** — named users, no
  shared accounts, 2FA enrollment complete (the INSTALL §8
  conditions, restated as continuing duties).
- **Incident disclosure** — breaches, misdirected shares, and
  suppression failures disclosed to the foundation and the
  city's own auditor on the charter's clock.

### 11.3 Proceedings: triggers and steps

**Evidence that can open a proceeding** (the inspector brings
at least one, documented): a failed or delinquent Compact
cross-audit of record; adverse witness attestations across a
rotation cycle; a court finding against the city's operation;
a verified public report (the mechanism does not act on
rumor — verification is the inspector's first task); a missed
statistical publication; retention or suppression breach
evidenced in the city's own chain; a false renewal
attestation (§5.3).

**Steps**, each published to the city and, at decision, to
the membership:

1. Notice of proceeding, naming the rule and the evidence.
2. City response window (**30 days** recommended
   **[charter parameter]**).
3. Hearing before the board (the city appears; the inspector
   presents; the record is written).
4. Decision: dismiss, remediate on a stated schedule (with
   probationary renewals under §5.4 as the enforcement
   posture), or revoke.
5. Revocation, if decided, is executed by threshold
   signature into the next revocation list, with the §6.4
   grace running from the city's actual receipt.
6. Publication: the decision, the reason code, and the vote
   count (not individual signers' votes, unless the charter
   says otherwise) enter the foundation's public record.

### 11.4 Appeal

One level of appeal, to the appeals panel, filed within
**30 days** of the decision **[charter parameter]**, decided
on the written record plus one hearing, within a charter-set
period. Grounds: procedural defect, evidence error, or
sanction disproportion. The panel may affirm, remand, or
reverse; a reversal is executed by errata list under §6.5.
Whether a timely appeal stays capture-stop pending decision
is open question Q4 — the mechanism supports either answer;
the charter must pick one before the first credential issues.

---

## 12. Failure modes

### 12.1 Clock skew against expiry

The mechanism is time-based and verification is offline, so
an install's clock is part of its trusted base — a clock
rolled back extends a credential on paper. Defenses, in
order of strength:

- **Effective-time rule.** Expiry and grace are evaluated
  against *effective time*: the **maximum** of the local
  clock and the newest timestamp the install has itself
  verified inside a signed artifact (its own checkpoints, a
  peer's checkpoint, a revocation list's issued-at). Rolling
  the local clock back cannot move effective time backward
  past evidence the install has already chained. Rolling it
  forward only harms the operator.
- **Skew flag.** If the local clock disagrees with effective
  time by more than **1 hour** **[charter parameter]**, or
  runs behind the freshest verified artifact at all,
  `/health` reports `clock_untrusted: true` and the dashboard
  shows it. NTP discipline is already an INSTALL §2
  requirement; this makes its failure visible rather than
  silent.
- Checkpoint timestamps the install *issues* are also
  chained, so a city that runs its clock backward to fake
  freshness leaves the evidence in its own chain, in order,
  for its Compact auditors to find.

### 12.2 The city that never receives the revocation list

Covered structurally in §6.3: absence never revokes, peers
relay, and the failure is bounded by the term — a revoked
city cut off from every channel still holds only a 90-day
credential, and non-renewal closes the road the list could
not reach. The residual is stated honestly: within one term,
a fully isolated revoked city can operate until expiry. The
quarterly term is what makes that residual acceptable; a
longer term would not be. (This is a load-bearing argument
for Corey's quarterly cadence, recorded so a future charter
amendment to lengthen terms prices it.)

### 12.3 Renewal during an active incident

Two directions, both specced in place: a *city* incident
(open proceeding, unresolved critical audit failure) routes
to §5.4 — probationary renewal or a hold with reasons, never
silence, never an administrative capture-stop. A *foundation*
incident (issuance-key compromise) freezes renewals under the
affected key only; §8.3 rotation restores the desk, and
credentials in force are untouched by the freeze. If an
incident spans a city's expiry, the city is in §5.5 grace,
not in breach, and a renewal issued under the successor key
inside grace cures it retroactively to the cadence (§5.5).

### 12.4 Server migration and rebind

The credential binds to the install's signing key, not to
hardware. Migration that preserves the key — the ordinary
backup/restore path, whose key escrow is split from the
backup set under INSTALL §7 — preserves the credential
untouched; the restored install presents the same fingerprint
and the credential verifies as before. Migration that loses
the key is a **rebind**: the foundation verifies the city's
identity out-of-band, issues a new credential (sequence
continues) bound to the new fingerprint, and publishes a
revocation entry naming the **old fingerprint's binding**
(reason code `rebind`, effective immediately — this is the
one entry class whose grace is zero, because it is the city
itself asking). Until the rebind completes, the new install
sits in ceremony: the failure is inconvenient, not fatal,
which is the correct price for making key loss unforgeable
into a credential transfer.

### 12.5 Erroneous revocation

§6.5's errata procedure, plus the structural mitigations:
threshold signature (three officers must err together),
notice and response before decision, grace after it, and an
appeal. An erroneous entry discovered inside grace is
withdrawn by errata list before capture ever stops; the
published record shows both the error and its correction,
which is the foundation's credibility working as intended
rather than being spent.

### 12.6 Foundation outage short of death

A foundation that is merely down — tooling broken, officers
unavailable, a bad quarter — is §8's concern only when the
§8.1 triggers ripen. Before that: renewal windows are 30
days wide precisely so a fortnight's outage is an
inconvenience; grace adds 14 more. The mechanism's time
constants are chosen so that ordinary institutional failure
is absorbed by the windows, and only sustained, unanswered
silence — 45 days past expiry with a filed request on chain —
escalates to the orphan state. A foundation that finds that
threshold uncomfortable is invited to answer its mail.

---

## 13. Open questions for Corey and the council

Politics and judgment calls this draft deliberately does not
make. Each needs an answer before the charter is final; none
blocks council review of the mechanism.

- **Q1 — Grace numbers.** Lapse grace 14 days, revocation
  grace 30 days, response window 30 days: right as charter
  defaults, or should any of them breathe more?
- **Q2 — Probationary renewal.** Does it exist at all? The
  alternative is binary (renew, or proceed toward
  revocation), which is cleaner and harsher. §5.4 assumes it
  exists.
- **Q3 — Emergency revocation.** Is there any abuse so active
  (a city selling data *now*) that grace should shrink — and
  if so, what shrinks: the grace, or only Compact access
  (which peers can already suspend unilaterally, today,
  under the existing Compact)?
- **Q4 — Appeal stay.** Does a timely appeal stay
  capture-stop pending decision? (§11.4.)
- **Q5 — The never-stop line.** §7 keeps Tier 3 search under
  existing legal process available forever, even to a revoked
  city. Confirm that line holds in every circumstance the
  council can imagine, or name the exception now.
- **Q6 — Foundation legal form.** Nonprofit corporation,
  interlocal agreement, fiscally sponsored project? The
  mechanism is form-agnostic; signer custody, fee handling,
  and the succession instrument are not.
- **Q7 — Succession designation.** Who is the designated
  successor at founding, and who holds the succession
  instrument in escrow? (§8.4 requires both before the first
  credential.)
- **Q8 — Funding.** Does certification cost member cities a
  fee? A foundation that can be defunded is a foundation
  whose death the mechanism must survive (§8 does) — but the
  charter should say whether fees exist, because §8 is a
  backstop, not a business model.
- **Q9 — Orphaned peers in the Compact.** §8.2 recommends
  share-eligible-while-flagged. The Compact agreement, not
  this spec, decides.
- **Q10 — Build-version floor.** Should the foundation be
  able to set a minimum genuine-build version for credential
  validity (refusing renewal to installs running a build with
  a known critical defect)? Powerful and dangerous in the
  same direction as revocation itself; if yes, it needs its
  own proceeding shape.
- **Q11 — The public registry.** One foundation-run registry
  page listing every city's credential state, or only each
  city's own dashboard? The mechanism feeds either; the
  politics of a single public list are Corey's call.
- **Q12 — Bootstrap.** Who certifies the first city, under
  what interim board, before the charter's full composition
  is seated? Every foundation has a first day; the spec's
  mechanisms all assume the board exists.

---

## 14. What a build would touch

Scoping only — the surfaces a future build must change, in
Janus/Sentinel terms, so the council can size it. No code is
designed here.

- **Credential store (Janus).** A credential file held beside
  the database, in the same custody class as the signing key
  (0600, included in backup manifests by hash as keys are,
  never inside the backup set). Registered in the data-store
  inventory so retention and restore treat it deliberately,
  not accidentally.
- **Verification (Janus).** Signature/binding/expiry/list
  evaluation at boot and on the daily periodic check, sharing
  the fail-closed pattern of the case-list feed and the
  ceremony fence. Effective-time computation (§12.1) from
  already-verified artifacts.
- **Health and dashboard (Janus).** A `credential` block in
  `/health` beside the `totp` block: state, credential ID,
  expiry, days remaining, freshest list sequence and age,
  `clock_untrusted`. The public dashboard renders the same
  block; ORPHANED and `probationary` are first-class display
  states.
- **Ceremony (provision.py).** A present-credential step
  (verify, bind, chain) and the §4.1 exit condition joining
  the existing enrollment condition. Chained event types:
  `CREDENTIAL_PRESENTED`, `CREDENTIAL_RENEWED`,
  `CREDENTIAL_EXPIRING`, `CREDENTIAL_GRACE`,
  `CREDENTIAL_LAPSED`, `CREDENTIAL_ORPHANED`,
  `REVOCATION_LIST_APPLIED`, `REVOCATION_EFFECTIVE` — the
  exact vocabulary is the build's to settle.
- **Ingest gate (Janus).** Capture-stop applied at the ingest
  path and the operational-intake paths of §7's table, with
  chained refusals; the never-stop column is enforced by
  *not* gating those paths, and the battery must prove both
  halves — including that retention, suppression, evidence,
  and legal-process search run untouched in `lapsed` and
  `revoked` states.
- **Checkpoints (Sentinel).** The credential-status block
  (§9.1) added to the signed checkpoint payload — the one
  Sentinel-adjacent change, so peers and ARGUS read status
  from the witnessed stream rather than from a new channel.
- **Compact (compact.py + the share gate).** The credential
  leg in the gate (`SHARE_BLOCKED` naming `credential`), the
  status evaluation from peer checkpoints, and list relay in
  the audit flow.
- **Foundation-side tooling (new, separate).** The officers'
  signing tool: issuance and renewal countersignature behind
  officer 2FA, revocation-list assembly collecting threshold
  signatures, root-certification operations. This tool does
  **not** ship to cities and holds the only copies of
  foundation operational keys.
- **ARGUS (no change to its posture).** ARGUS reads
  credential state from the sink stream like every other
  fact; it gets no credential-related privilege. Its digests
  will surface expiring and orphaned installs as a matter of
  course.
- **Tests.** Discriminating cases per state transition in
  the house style: lapse → grace → stop; revocation inside
  and outside grace; orphan trigger with and without a filed
  request; under-signed list refused; clock-rollback defeated
  by effective time; rebind; and the §7 never-stop proofs.

Explicitly out of build scope: the license agreement's legal
text, the trademark registration, the foundation's internal
operations, and the charter itself. The build implements the
mechanism; the charter is a legal instrument this spec only
skeletons.

---

## Appendix — charter parameters at a glance

All values are recommendations for the charter to set; the
mechanism takes them as configuration of the foundation, not
constants of the code.

| Parameter | Recommended | § |
|---|---|---|
| Credential term | 90 days | 2, 5.1 |
| Renewal window opens | 30 days before expiry | 5.1 |
| Probationary renewal term | 30 days | 5.4 |
| Lapse grace | 14 days | 5.5 |
| Revocation grace | 30 days from effective receipt | 6.4 |
| Revocation threshold | 3-of-5 (floor 2-of-3) | 6.2 |
| Revocation list cadence | Weekly and on change | 6.3 |
| Stale-list signal | 35 days | 6.3 |
| Proceeding response window | 30 days | 11.3 |
| Appeal filing window | 30 days | 11.4 |
| Orphan threshold | 45 days past expiry, filed request unanswered | 8.1 |
| Wind-down window | 12 months from first orphan trigger | 8.4 |
| Clock-skew tolerance | 1 hour | 12.1 |

---

## Amendment 1 — hardware second factors (Corey, Nov 27, 2026)

The operator second factor as built is TOTP: the rotating code an
authenticator app generates (2FA-SCOPE, Nov 24, 2026 — Google
Authenticator, Authy, 1Password). This amendment admits hardware
tokens as an enrollment factor of equal standing, so a department
can issue a physical object instead of relying on a personal phone.

1. **FIDO2 / WebAuthn security keys — the preferred hard token.**
   Phishing-resistant, no shared secret to extract, no battery or
   clock to drift. A supervisor's key is a physical object the
   department issues, inventories, and takes back — which fits the
   two-key ceremony model literally: the key that turns is a key.
2. **Programmable hardware TOTP tokens — the alternate.** Seeded
   display tokens ride the existing TOTP verification path and the
   `totp` state block unchanged. Their limits are recorded, not
   discovered later: a shared secret exists, clocks drift, and they
   carry no phishing resistance. Use where WebAuthn is impractical,
   not as the default.

Rules: an operator may enroll an authenticator app, a FIDO2 key,
or both; sign-in, releases, and ceremony acts accept any enrolled
factor. Factor enrollment and revocation run through the same
credential state machine as every other credential in this spec,
and `/health` surfaces a `webauthn` block beside the existing
`totp` block. Losing a hard token is a revocation event under §6,
nothing more. The §7 never-stop table is unchanged: a lost or
unavailable token never blocks Tier 3 under existing legal
process, suppressions, retention/deletion, evidence, or exports.

Status: spec decision of record. Implementation is pilot-phase
work, alongside the 1.2.9 hardening tranche; the converged 1.2.8
code is authenticator-TOTP only, and this amendment does not
reopen convergence.

*End of SPEC-v0.1.*
