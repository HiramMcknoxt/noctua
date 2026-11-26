# ARGUS — NOCTUA's Watchman
## Spec v0.2 — DRAFT for council review, not built (Nov 25, 2026)

**ARGUS** — named for Argus Panoptes, the hundred-eyed watchman of
Greek myth, some of whose eyes were always awake.
Backronym, retained from v0.1 with the letters re-read for the
revised design: **A**nomaly **R**eview, **G**uarded operations,
**S**anitized research — the first two are the pilot jobs; the
third is a deferred module (see Pilot scope).

Status gate: this is a draft for council review. It is not built,
and building remains gated on Corey's explicit go after review.
It succeeds SPEC.md (v0.1), which Security Round 1 rejected
unanimously as written; v0.1 stays on file, untouched, as the
red-teamed record. The round's v0.2 direction is binding on this
draft and is quoted at `~/workspace/noctua-1.0/security-round/
SYNTHESIS.md` ("ARGUS — ruled on, unanimously negative as
written").

The one-sentence version of the revision: **v0.1 gave the LLM a
key, a toolbox, and a rollback button; v0.2 gives it a window, a
notebook, and no hands.** The LLM advises. A deterministic,
non-LLM policy daemon — human-configured, allowlist-bound —
decides and executes the small set of operational actions that
may be automated at all, and every action it takes is chained.
A human does everything else.

## What changed from v0.1 and why

Each change is keyed to a defect Security Round 1 named. The
round's verdict and defect list govern; where this draft adds
detail the round did not dictate, the addition is marked as a
drafting choice and, where it needs a decision, parked in Open
questions.

**D1 — Automatic database rollback (v0.1, Tier B step 5).**
v0.1 let an invariant failure after a deploy trigger automatic
rollback to last-known-good, on the reasoning that it "only ever
restores a state a human already approved." The round: automatic
DB-state rollback is destructive and abusable — an attacker who
can induce an invariant failure chooses the rollback timing, and
the mechanism bypasses the restore ceremony entirely.
**v0.2: there is no automatic rollback of database state, ever,
by any component specified here.** The only rollback that exists
is the one Janus already has: the chained two-key restore
ceremony, initiated and approved by humans. An invariant failure
after a deploy raises a deterministic alert (see The alert
channel) and stops there. Humans decide; humans restore.

**D2 — ARGUS held a jobs-class Janus key (v0.1, Tier A).**
v0.1 acted through Janus's API under ARGUS's own machine
identity, key-only, jobs-class. The round: a jobs-class key is
an alerting kill-switch, not least privilege — the same identity
family that can forge heartbeat state can blind the very
alerting the watchman exists to support (round finding 9).
**v0.2: ARGUS holds NO Janus credential of any kind — no key,
no token, no account.** It cannot call Janus's API at all. The
only component that acts is the policy daemon (see The policy
daemon), a deterministic non-LLM program holding its own narrow
machine identity, fenced to exactly its allowlisted actions.
The LLM never touches that identity, that code path, or any
other.

**D3 — The "sanitizer" was a scrubber, not a boundary (v0.1,
The data firewall).** v0.1's research queries passed through a
plate-pattern scrubber built on the chain's ASCII-only regex —
and the round's own finding 12 is that that regex passes
homoglyph and full-width encodings. A pattern matcher with a
known bypass is not a data boundary. **v0.2: ARGUS has no
internet path and no research function.** Research is specified
as a separable module on separate hardware (see Sanitized
research module), default OUT of pilot scope, and its boundary
is physical and network-level first; template construction and
refusal rules are the second layer, never the only one. (The
scrubber itself was fixed in Janus by commission item T9 —
NFKC normalization plus a confusables map — but v0.2 does not
rest any ARGUS boundary on it.)

**D4 — Research-result quarantine was prompt-level (v0.1).**
v0.1 declared returned web text "quarantined" by instruction to
the model. The round: a prompt-level construct enforces nothing.
**v0.2: enforcement is structural.** In the pilot architecture
there is no path by which external text can reach the advisor's
context, the daemon's inputs, or a patch draft — the research
module is a separate system whose only output is a fenced report
to a human. If a human wants a research result considered, the
human carries it in, in the open, the same as any other document.

**D5 — Same-host research proxy (v0.1, Pilot vs production).**
v0.1 piloted the research proxy as a separate process on the
ARGUS host, dual-NIC. The round: the same-host form fails the
threat model. **v0.2: if research exists at all, it is on
separate hardware.** There is no same-host option in this spec.

**D6 — ARGUS lived on the NOCTUA server (v0.1, Model and
runtime / The machine).** v0.1 ran the analyst model on the
NOCTUA server's own GPU, time-shared with the plate pipeline,
with load-shedding rules so the watchman could not starve the
watched. Corey's model decision (Nov 25, 2026) and the round's
separate-hardware direction converge: **v0.2 puts the whole
watch floor on its own host.** No GPU contention with plate
recognition exists to be managed, because the components share
no hardware. The NOCTUA server's sizing reverts to the pilot
spec's own figures; this document sizes only the watch host
(see The watch host).

**D7 — The watchman's log was outside the registry (round
direction).** The round directs that ARGUS's review log be
registered in PLATE_DATA_STORES. v0.1 kept the log with the
auditor but outside Sentinel's retention registry, so nothing
bounded or purged it. **v0.2: the review log is a registered
store with a retention class and a purge action** (see The
review log), auditable and retention-bound like everything else
in the system.

**D8 — Alert independence is now explicit architecture (round
direction).** v0.1 said ARGUS is "not the alarm"; the round
directs the positive form: **deterministic Sentinel alerts
travel on their own unfilterable channel, independent of
ARGUS.** v0.2 specifies that channel as a component with its
own delivery path (see The alert channel), so no ARGUS failure,
compromise, or misbehavior can sit between Sentinel and the
humans it alerts.

## What ARGUS is

A locally hosted LLM system on its own hardware — the watch
host — that watches NOCTUA's *outputs* and works two jobs in
the pilot, with a third specified but deferred:

1. **Anomaly review.** Reads the external Sentinel sink stream
   (the witnessed copy of the audit chain that already leaves
   the system by design) and the auditor-facing reports built
   from it: checkpoint status, retention and sink-reconciliation
   reports, Compact cross-audit status where it is chained, and
   2FA/authentication events as they appear in the chain.
   Produces flags to the auditor and operator, and a
   plain-English daily digest / weekly pattern report — the
   layer that makes an audit log somebody actually reads.
2. **Guarded operations (advice only).** Notices operational
   faults and pattern-level problems and *recommends*: to the
   humans who edit the policy daemon's rules and allowlist, and
   in its digests. The execution half of this job belongs to the
   daemon, not to ARGUS (see The policy daemon). ARGUS's
   runtime output goes to humans only; nothing ARGUS produces
   at runtime triggers any action by any machine.
3. **Sanitized research (DEFERRED — separable module, out of
   pilot scope).** Specified at Sanitized research module so
   the council can rule on it as a design, but no part of the
   pilot depends on it and the pilot builds without it.

## What ARGUS is not (hard limits, not settings)

- **Not the alarm.** Deterministic Sentinel verification (hash
  chain, watermark reconciliation, signed checkpoints) remains
  the enforcement layer, and its alerts travel on their own
  unfilterable channel, independent of ARGUS. ARGUS can
  escalate, summarize, and notice patterns. It cannot suppress,
  clear, delay, or downgrade any deterministic alert, ever.
- **Not a reader of the live database.** ARGUS reads the sink
  copy — the same witnessed export an outside auditor gets. It
  holds no Janus database credentials and no audit key. In
  v0.2 this extends further: ARGUS holds **no Janus credential
  of any kind** and has no network path to Janus's API.
- **Not an actor.** ARGUS executes nothing. It cannot restart,
  replay, re-run, restore, deploy, or configure anything. The
  policy daemon acts, within its allowlist, on its own
  deterministic rules — never on ARGUS's output.
- **Not an author of production code.** See Tier B: it drafts,
  in a shadow copy, for a human. It never deploys, and it has
  no deploy path to abuse.
- **Not a rollback mechanism.** There is no automatic rollback
  of database state, ever (see D1).
- **Not a network bridge.** The watch host receives a one-way
  export and forwards nothing anywhere. It has no internet
  route in the pilot configuration.
- **Not a cloud client.** The model runs locally, on the watch
  host, from open weights held on that host. No audit material
  — sink content, chain payloads, digests, drafts — is ever
  sent to a vendor cloud, an external API, or any off-premises
  inference service. There is no cloud-LLM path for chain
  material in this design, at any tier, as a fallback or
  otherwise.

## Architecture

Five components. Only one of them is a language model, and it
is the one with the least reach.

### The advisor (the LLM)
The Qwen-class local model (see Model and runtime). Its whole
world is: a read-only spool of sink-export segments delivered
to the watch host, the report templates it fills, and the
review log it appends to. It has no tools that act on anything
outside the watch host, no shell, no API client, no credentials.
Its outputs are flag records and digest text, written to the
review log, and delivered to humans by the deterministic
shipper below — not by the model itself.

### The policy daemon (deterministic, non-LLM)
A small, ordinary, human-reviewed program — no learned
component, no model output anywhere in its inputs. It:
- evaluates a fixed set of **deterministic rules** over the
  same exported state ARGUS reads (health/heartbeat exports,
  sink status, checkpoint schedule) — e.g., "sink backlog
  above N entries for more than T minutes," "scheduled
  checkpoint missed by more than T minutes";
- executes, for a rule that fires, only the **allowlisted
  action** bound to that rule (see Tier A);
- anchors the review log (see The review log) on a fixed
  schedule;
- delivers ARGUS's digests and its own escalation notices to
  humans through the watch host's outbound mail/notice path.
Its rule set and allowlist are files a human edits, under the
same change discipline as any other production configuration:
edited by a person, reviewed, and their hashes part of the
deployment record. The daemon holds the watch floor's only
Janus machine identity — a dedicated, narrow role created for
it, fenced to exactly the allowlisted operational actions and
the log-anchor append. It is not a jobs-class identity: it
cannot write heartbeats, cannot touch alerting state, cannot
read or write plate data, cannot authenticate as any human
role. Every action it takes through Janus's API is a chained
audit entry under that identity, attributable like anyone
else's. If the daemon's rules, inputs, or identity checks are
in any doubt, the daemon's defined behavior is to take no
action and escalate. It fails closed or it does not run.

### The alert channel (deterministic, independent)
Sentinel's deterministic alerts — chain verification failures,
watermark/checkpoint mismatches, sink divergence, health
degradations — are produced and delivered by the Janus host's
existing deterministic machinery (alert_check and the /health
degradation surface) over a delivery path that does not pass
through the watch host, the advisor, or the daemon. ARGUS
receives *copies* of alert state as part of the sink export,
after the fact, for pattern review. ARGUS cannot suppress,
clear, delay, downgrade, or acknowledge-away any alert on this
channel; it has no write path to it and no shared component
whose failure could mute it. If the watch host burned down,
this channel would not notice.

### The review log
ARGUS's flags, digests, Tier B drafts, and the daemon's action
notices are written to an append-only review log on the watch
host. Because the log can quote chain-adjacent text, it is
treated as what it is — a plate-data-adjacent store:
- It is **registered in PLATE_DATA_STORES** (sentinel.py's
  registry) with its own store entry, retention class, and
  purge action, so the retention machinery accounts for it and
  the outside auditor can verify its handling like any other
  store's.
- The policy daemon **anchors** it: on a fixed schedule the
  daemon appends a chained entry to Janus naming the review
  log's current segment hash, so the watchman's notebook is
  witnessed by the same chain structure the watchman watches.
  Tampering with the log after the fact is detectable against
  the anchored hashes.
- Readership is the auditor and the operator (see Open
  questions for the readership decision the council still owes).

### The research module (separate, deferred)
Not part of the pilot. Specified at Sanitized research module
as a separable system on its own hardware, with no connection
to the watch host except a human carrying its reports across.

### Data flow
```
Enclave (camera VLAN, Janus, Sentinel)  — unchanged, no inbound path
        │  one-way sink export (already exists by design)
        ▼
Watch host (separate hardware, no internet route in pilot)
        ├── sink spool (read-only)
        ├── advisor (LLM) ──► review log (append-only, registered)
        └── policy daemon ──► Janus API (its own fenced identity,
        │                        allowlisted actions + log anchor only)
        └── deterministic shipper ──► digests/notices to humans
Deterministic alert channel: Janus host ──► humans (never via watch host)
Research module (deferred): separate hardware, human-carried reports only
```
Watch host → enclave traffic is exactly two things: the
daemon's allowlisted API actions and its log-anchor appends,
both under the daemon's identity, both chained. Nothing else
on the watch host can open a connection into the enclave; the
host firewall is default-deny in both directions and the rule
files are part of the deployment record, as in v0.1.

## Guarded operations, in two tiers

### Tier A — operational response (daemon-executed)
The automated surface, deliberately small. A fixed allowlist of
Janus's own operational actions — the class of thing v0.1
listed: replay a sink backlog, re-run a failed checkpoint,
restart a wedged named job, re-execute retention housekeeping.
Rules:
- **Deterministic triggers only.** Each action is bound to a
  rule the daemon evaluates from exported state. The rule set
  is human-written and human-edited. ARGUS's flags and digests
  are not daemon inputs; a pattern ARGUS notices becomes a
  daemon rule only when a human writes it as one.
- **Allowlist only.** Anything not on the list does not exist
  for the daemon. The list changes by human edit, not by the
  daemon, not by ARGUS.
- **Chained and attributable.** Every daemon action is a chain
  entry under the daemon's own identity (see The policy
  daemon), including the log-anchor appends.
- **Rate-limited and self-limiting.** Each rule carries a
  cooldown and a per-day cap. Repeated failure of the same
  action disables that rule and escalates to the auditor over
  the deterministic path — the daemon stops; it does not loop.
- **Reversible where the action class allows it**, and where
  it does not (a replayed backlog is not un-replayable), the
  action's chain entry is the record and the digest reports it.
- The initial allowlist's exact contents and thresholds are a
  policy decision, parked in Open questions; this spec fixes
  the *shape* (named actions, named preconditions, caps) and
  refuses to fix the numbers by drafting fiat.

### Tier B — code bugs (advisory only: draft, prove, hand over)
When the advisor detects a probable code bug (crash signatures,
invariant violations in the exported state, anomalous error
clusters, a battery leg failing against the live tree's
version):
1. Reproduce it in a **shadow copy** of the tree, driven by
   sink-export segments and test fixtures. The shadow
   environment holds **no copy of the live database** — v0.1's
   shadow database does not survive into v0.2, because a full
   DB copy on the watch host would contradict the sink-only
   rule (see Open questions for the residual case).
2. Draft a candidate patch against the shadow copy.
3. Run the **full acceptance battery** (builders' suite + every
   attack leg + the invariant suites) against the patched
   shadow, and record the evidence.
4. Present the patch, the reproduction, and the battery
   evidence to the operator, in the review log and the digest.
   **That is the end of ARGUS's involvement.** Deployment is a
   human act, performed by humans through the ordinary change
   process, entirely outside ARGUS. Patches touching Tier 3,
   suppression, evidence, or 2FA code paths additionally
   require the two-key pattern the system itself uses, and are
   candidates for a council round at the operator's call —
   carried over from v0.1 unchanged.
5. After any human deployment, the advisor watches the exported
   invariants like it watches everything else. **An invariant
   failure raises a flag and a deterministic alert; nothing
   rolls anything back.** If humans judge a restore necessary,
   it is Janus's chained two-key restore ceremony, initiated
   and approved by humans. (This paragraph replaces v0.1's
   step 5 in full — see D1.)

An LLM autonomously rewriting a live law-enforcement data
system on its own authority is precisely the failure mode
NOCTUA exists to prevent. Tier B is designed so ARGUS can do
everything up to the line — find it, prove it, fix it on paper,
prove the fix — and a person still turns every key from there.

## Inputs, and the injection problem stated plainly

ARGUS's input is the sink export and nothing else. If a signal
is not in the export, ARGUS does not see it; extending the
export is a Janus change through the normal council process,
not an ARGUS feature. This bounds what anomaly review can
notice, and the bound is accepted on purpose: the alternative —
a credentialed, API-polling watcher — is what v0.2 removed.

Chain content is, in part, attacker-influenced text: camera
identifiers, operator free-text, error strings. That text
reaches the advisor's context. v0.1 parked this as an open
question for the round; v0.2 answers it structurally:
- A fabricated flag costs a human one look. Flags are advisory;
  nothing acts on them automatically.
- A suppressed flag is bounded by the alert channel's
  independence: the deterministic alerts a log-injection would
  most want to hide never pass through ARGUS at all.
- The advisor's outputs are data in a log, delivered by a
  deterministic shipper that treats them as text. Model output
  is never parsed as instructions by any component in this
  design — the daemon does not read the review log as input.
Residual risk, stated honestly: a poisoned sink segment can
waste reviewer attention and can bias a digest's wording. It
cannot act, cannot hide a deterministic alert, and cannot reach
the daemon. The council may still judge the digest-integrity
risk worth a mitigation (e.g., digest diffs against the
deterministic reports); that is parked in Open questions.

## Sanitized research module (separable, deferred, OUT of pilot)

Specified so the council can rule on the design; not built for
the pilot, and nothing in the pilot depends on it.

- **Separate hardware, full stop.** Its own small appliance on
  its own network segment with internet egress. It shares no
  host, no network, and no storage with the enclave or the
  watch host. There is no same-host form of this module.
- **No chain material, by construction.** The module never
  receives sink content, chain payloads, plate-shaped data, or
  case data. Research questions are built from templates —
  component, version, error class, CVE/advisory lookup — on
  the module itself, from parameters a human types or selects
  there. There is no automated feed from ARGUS to the module;
  if the advisor's digest suggests a lookup, a human re-keys
  the question on the module. Slow is the point: the air gap
  is a person.
- **Refusal rules are the second layer, not the boundary.**
  Template fields carry no free text that could hold a plate,
  a case number, or a payload fragment; any free-text field
  that exists passes pattern refusal (plate-shaped, case-shaped,
  payload-fragment), a length cap, and a query-type allowlist,
  and a tripped query is refused outright, never cleaned and
  sent. The boundary is that the data was never there; the
  refusal rules exist for the day a human pastes wrong.
- **Results are untrusted text, delivered to a human.** The
  module's only output is a report to a human reader, with
  external text fenced and labeled. Results never enter the
  advisor's context automatically, never reach the daemon
  (whose inputs are local exported state only), and never
  become patch inputs except through Tier B's ordinary path —
  a human carrying a document in, in the open.
- Whether this module is ever built, and who may task it, are
  open questions for Corey and the council.

## Model and runtime

**Model boundary (model-agnostic).** The advisor is specified
against an interface, not a weights file: it consumes bounded
sink-export segments plus a task template (triage, digest,
pattern review, Tier B drafting) and produces flag records and
report text through a local inference endpoint. Any local model
that meets the floor — instruction-following adequate to the
triage templates, context long enough for the segment size the
deployment chooses, deterministic-enough decoding at low
temperature — may sit behind that interface. Swapping the model
is a deployment act by a human, with the model file's hash
recorded in the deployment record, and (see Open questions) an
evaluation pass against a fixed test set before the swap is
trusted. No component in this design knows or cares which model
is running, and no model gets any additional reach by being
smarter.

**Reference implementation: Qwen, locally hosted.** Corey's
decision (Nov 25, 2026): the reference engine is a locally
hosted Qwen model — open weights, held on the watch host, run
on the city's own hardware. No audit material ever leaves the
building to a vendor cloud; there is no API key, no per-token
bill, and no external party whose retention policy the chain
would inherit. A cloud model, however capable, would invert
the project's premise — a system built to end third-party
custody of plate data does not hand its audit trail to a
third-party inference service.

**Runtime.** A local inference server of the llama.cpp / vLLM
class, under its own unprivileged user on the watch host,
containerized where the platform supports it, no shell access
for the model process, network reach limited to the local
inference endpoint and the local sink spool. Low-temperature
decoding for triage and flags; a separate drafting profile for
Tier B work. The model's tool list is: read the spool, write
the review log. That list is the whole of its reach.

**Sizing — candidate model classes vs. watch-host tiers.**
All figures are planning estimates, not quotes — re-price and
re-benchmark at purchase, against the actual sink volume
(~44,400 reads/day is the NOCTUA side's figure; the sink
segment rate the advisor must chew is a chain-entry rate, far
smaller).

| Tier | Model class (Qwen reference) | Hardware | What it does well |
|---|---|---|---|
| Reference | 32B-class dense at Q4/Q5, 128k context | 1× 32 GB-class GPU, 64–128 GB RAM | v0.1's analyst profile: full-segment triage at working speed, daily digest + weekly patterns, Tier B drafting on the same host |
| Modest | 14B-class dense at Q4/Q5 | 1× 16–24 GB-class GPU, 64 GB RAM | Triage and digests at production-adequate quality; Tier B drafting slower and shallower — expect more human rework per draft |
| Heavy | 32B at Q8, or 70B-class at Q4 | 1× 48 GB-class GPU, 128 GB RAM | Headroom for longer segments and a second concurrent drafting job; a capacity luxury, not a correctness requirement |
| GPU-less fallback | 7–8B-class at Q4, CPU inference | No GPU; 32–64 GB RAM, modern many-core CPU | Batch digests only — see losses below |

**What the GPU-less fallback loses, stated plainly:**
- **Latency.** Flag generation goes from near-real-time to
  batch. On CPU, a 7–8B model chews a day-segment in tens of
  minutes, not minutes; "flags" arrive with the digest, not
  ahead of it. The deterministic alert channel is unaffected —
  which is exactly why it is independent.
- **Context in practice.** Long sink windows must be chunked
  with deterministic pre-filtering (counts, error-class
  extraction) before the model sees them, so cross-segment
  pattern review — the weekly report's whole value — gets
  thinner and more dependent on the pre-filter's choices.
- **Drafting quality.** Tier B candidate patches from a small
  CPU-bound model are noticeably weaker; the battery still
  judges them, but the human should expect a lower fraction
  worth reading.
- **Nothing else.** The daemon, the alert channel, the review
  log, and the anchor are all deterministic and run the same
  on any tier. Capability degrades; the safety shape does not.
  That asymmetry is deliberate and is the reason a GPU-less
  pilot is specifiable at all.

## The watch host

A separate, ordinary machine — deliberately not the NOCTUA
server, and sized only for the watch floor (advisor + daemon +
spool + log). The NOCTUA server itself is specced by the pilot
spec; v0.1's combined-machine tables do not carry over.

| Component | Pilot (reference tier) | Notes |
|---|---|---|
| CPU | 8–16-core current-gen | Daemon and spool are light; CPU is the fallback inference path |
| GPU | 1× 32 GB class (RTX 5090 or equivalent) | Omit for the GPU-less fallback tier, accepting the losses above |
| RAM | 64–128 GB | 128 GB if CPU inference is a planned fallback mode |
| Storage | 2× 2 TB NVMe, mirrored | Sink spool retention + review log + model weights; the spool is a copy — its loss loses no original data |
| Network | 2× NICs (enclave-facing watch VLAN / management), no bridging, IP forwarding disabled | No internet route in pilot configuration; firewall default-deny both directions, rule files in the deployment record |
| Power | UPS with chained graceful shutdown, shared with or matched to the NOCTUA server's practice | A dead watchman must be visible: the daemon's absence is itself reported by the Janus side's heartbeat expectations for the anchor schedule — a missed anchor is a chained, health-visible event, not a silent gap |
| Planning estimate | **~$2,500–$4,500** with GPU; **~$1,200–$2,000** GPU-less (estimates, not quotes — re-price at purchase) | Excludes the NOCTUA server, cameras, and network gear, which the pilot spec already carries |

Physical and platform posture matches the NOCTUA server's:
locked room, TPM 2.0, Secure Boot, full-disk encryption with
an operator-held passphrase.

## Failure modes

- **Advisor down, hallucinating, or replaced by a worse
  model.** Nothing else notices operationally. Alerts are
  unaffected (independent channel), the daemon is unaffected
  (does not read advisor output), and the worst case is a
  digest a human should not have trusted — mitigated by the
  anchored log, which makes after-the-fact fabrication
  detectable, and by flags being advisory by construction.
- **Daemon down.** Automated operational response stops; the
  missed-anchor signal makes the stoppage chain-visible rather
  than silent. Janus itself is unaffected — the daemon is a
  client of it, not a component of it.
- **Daemon buggy or compromised.** The allowlist bounds the
  blast radius to named operational actions, each chained
  under its identity, each rate-limited. It holds no plate
  data access, no alerting write path, no human role. A human
  stops it by editing its rule file to empty or stopping the
  service; that stop is itself the recovery, and anything it
  did is in the chain for the auditor.
- **Watch host compromised.** The attacker gains: the sink
  copy (already the witnessed export an outside auditor
  receives), the review log, and a model. They do not gain a
  Janus credential (none exists there except the daemon's
  fenced identity — see above for its bounds), a path into the
  enclave beyond the daemon's allowlisted actions, or any
  ability to mute the deterministic alert channel, which does
  not touch this host.
- **Sink feed interrupted.** The advisor's digests say so, in
  so many words, when the feed resumes — a gap in the export
  is a finding, not a silence. Independently, Janus's own
  health surface already degrades on sink-status problems
  without ARGUS's involvement.
- **Model drift / silent swap.** The running model's file hash
  is part of the deployment record and is printed in every
  digest header. A mismatch between the digest's named model
  and the deployment record is a discrepancy a human or the
  auditor can catch without trusting the model.

## Pilot scope

**In the first deployment:**
- The watch host, at the tier Corey selects (Open questions).
- Anomaly review over the sink export: flags, daily digest,
  weekly pattern report, delivered by the deterministic
  shipper to the operator and the outside auditor.
- The policy daemon with its initial allowlist (contents
  parked as a policy decision — Open questions), log anchoring
  on schedule, and escalation-on-repeat-failure.
- The review log, registered in PLATE_DATA_STORES, anchored,
  retention-bound.
- Tier B advisory drafting in the shadow environment
  (sink-driven, no live database copy), battery evidence
  attached, human handover. Tier B is the first workload shed
  if the watch host is contended; anomaly review is the job
  the host exists for.

**Explicitly deferred or excluded:**
- The sanitized research module — out; separate hardware and a
  separate council decision if it is ever built.
- Any runtime path from advisor output to daemon action — out,
  and not a "later phase" of the pilot design; adding one is a
  new spec and a new round.
- Automatic rollback of anything — out, permanently (D1).
- Cloud inference for any chain material — out, permanently.
- ARGUS co-residency on the NOCTUA server — out (D6).
- Compact cross-audit *analysis* beyond reading the chained
  status the export already carries — the advisor reads what
  the export holds; it does not query partner systems (it
  cannot; it has no credentials and no network path).

## Open questions for Corey / the council

1. **Initial daemon allowlist and thresholds.** Which named
   actions, with what preconditions, cooldowns, and daily caps?
   This spec fixes the shape; the numbers and the list are a
   policy decision for Corey and the operator, and the pilot
   should start shorter than anyone's first instinct.
2. **Daemon identity shape.** This draft specifies a dedicated,
   narrow Janus role fenced to the allowlisted actions plus
   log anchoring. Creating it is a Janus change (interacts with
   Security Round 1's T7 identity-binding work) and needs its
   own discriminating cases. Council to confirm the role's
   exact permission set when the build is commissioned.
3. **Advice-to-action, ever?** Pilot takes the strict line:
   advisor output reaches humans only. A future design could
   queue *proposed* daemon actions for one-click human
   approval. Is that a direction Corey wants held open, or is
   the strict line the permanent one? Not needed for the pilot;
   asked now so the answer is on record before anyone builds
   toward the relaxed form.
4. **Watch-host tier.** Reference (32B-class, GPU) vs. modest
   vs. GPU-less fallback — a budget decision with the losses
   tabled above. The safety shape is identical at every tier;
   only latency, context, and drafting quality move.
5. **Research module: later, or never?** Separate hardware
   makes it specifiable; nothing makes it necessary. Corey and
   the council to decide whether it is a phase-two candidate or
   permanently cut — and if ever built, who may task it (the
   operator, the auditor, or both) and who approves its query
   templates.
6. **Review-log retention class and readership.** Which
   retention class the registered store carries (the log is
   plate-data-adjacent; the class choice is policy), and who
   reads the digest — operator, outside auditor, or both, in
   what form. The anchoring mechanism does not depend on the
   answer; the registry entry does.
7. **Model evaluation before trust.** A model swap (including
   the initial selection among Qwen-class candidates) should
   pass a fixed evaluation: recorded sink segments with known
   verdicts, scored for flag precision/recall and digest
   faithfulness. Who builds that test set, and what score is
   "trusted"? Until it exists, the advisor's flags carry an
   explicit unproven-instrument caveat in the digest header.
8. **Pen-test gate scope.** The pilot pen-test gate clause
   (Security Round 1 synthesis, non-waivable) covers the
   deployed Janus/Sentinel pilot before any camera is
   energized. Recommendation: the watch host and daemon join
   that scope before ARGUS is connected to a live deployment —
   the daemon holds a credential and an action path, however
   fenced. Corey's call whether the gate extends, and whether
   ARGUS connects only after the first pen-test report.
9. **Tier B's residual case.** This draft forbids a live
   database copy on the watch host, so some bugs — those
   reproducible only against live data shape — cannot be
   shadow-reproduced by the advisor. The fallback is a
   human-run, on-host exercise with the advisor advising from
   reports. Council to confirm that trade is accepted, or to
   specify the conditions (if any) under which a time-boxed,
   chained, human-carried data extract may cross to the watch
   host.
10. **Digest integrity against a poisoned sink.** Flags are
    advisory and alerts are independent, but a crafted sink
    segment can still bias a digest's wording. Is the residual
    risk accepted as documented, or does the council want a
    mechanical mitigation (e.g., the digest's factual claims
    cross-checked against the deterministic reports before
    delivery, with discrepancies printed rather than resolved)?

*Vesper's drafting seat, for Corey Spangler — Cabot, Arkansas.
Drafted Nov 25, 2026. Unbranded city-business document, per
standing rule. DRAFT — not built; build gated on Corey's
explicit go after council review.*

## Names in reserve
- **VIGIL** (Verifies Integrity, Generates Insights from Logs) —
  coined by the dashboard builder, Nov 25, 2026; Corey likes it
  and directed it be kept in mind for a later component, TBD.
  Candidates when the time comes: the auditor's nightly digest,
  the standalone audit verifier, or a future watch component.
  Not assigned; do not let it be lost. (Carried forward from
  v0.1 so the name is not lost in the revision.)
