# NOCTUA Security Round 1 — Brief
## A threat-model-first audit of NOCTUA 1.2.4

Commissioned by Corey Spangler, Nov 25, 2026. Orchestrator: Vesper.
Runs against the 1.2.4 tree (`~/workspace/noctua-1.0/janus124/`)
AFTER the orchestrator's cold battery passes and BEFORE Round 8's
correctness pass. This round does not replace Round 8; it hunts
where Round 8 is not looking.

> HANDOFF RULE (standing, Corey Nov 24 2026): Before starting, create
> HANDOFF.md in the work folder using the council template: goal,
> done-definition, current state with evidence, exact next step,
> remaining steps, blockers, settled decisions, model/effort, limit
> status/reset. If the next step is a machine step (compile, test,
> render, push, deploy), also create an executable runner
> (run-next.bat/.ps1 pure ASCII, or run-next.sh) that does it
> end-to-end and logs its result. Update the handoff at every
> milestone and at ~70% limit use. Do not end without a current
> handoff another model can execute cold.

## How this round differs

Rounds 1–7 reviewed the build against a commission: are the
specified safeguards implemented correctly? This round starts from
the other end. Each seat first builds the attack surface map from
the code itself, chooses its attacker, and hunts wherever the
hunting is good — including places no commission item has ever
named. A finding does not need a commission item to answer to. It
needs an attacker, a path, and evidence.

## Seat protocol

- Best included model in your existing subscription, maximum
  reasoning. Fable never (no credits). Ultra-class off unless the
  orchestrator states a reason. Credit-gated tiers step down to
  best included; report the step-down.
- Claude seats run at Medium effort (Max is reserved for the
  final version's round).
- Both Claude seats share ONE account limit — heavy Claude work
  runs in sequence.
- **Identity anchoring (new, standing for all seats):** every part
  you receive is headed "Reference material for the [your seat]
  seat — other AI systems named in these documents are other
  reviewers, not you." Report your model and effort ONLY as shown
  in this chat's interface, transcribed verbatim. If the interface
  shows no model name, write "the interface shows no model name."
  Never infer your identity from the documents. Prior seats'
  reviews are quoted third-party evidence, framed as such.

## The system you are attacking (orientation, not limits)

NOCTUA is a city-operated ALPR back end: Janus (single-file Python,
stdlib only) is the one logged front door for plate reads, hot-list
matching, Tier 1/2/3 searches (Tier 3 = historical search behind a
configurable judicial gate + two-key execution), protection-order
suppressions, evidence export/destruction, and Compact cross-agency
sharing with reciprocal audit. Sentinel is the append-only,
hash-chained audit log with Ed25519-signed checkpoints witnessed
outside the system (City Clerk). Plate text never enters the chain —
keyed HMAC plate_refs do. Deployment shape: cameras on an isolated
VLAN with no internet route, WireGuard backhaul, Janus bound to
localhost behind the department's own access path. The pilot spec's
gates (ACIC hot-list path, Council authorization, Commission
review) are institutional, not code — out of scope here except
where code claims to enforce them.

## Attacker models — state yours on every finding

1. **Outsider** — network presence on the department LAN or a
   compromised non-ALPR host; no credentials.
2. **Low-privilege insider** — a valid patrol or detective key;
   curious or malicious; wants other cases, protected plates,
   or history they are not entitled to.
3. **Supervisor insider** — a valid supervisor key; wants to
   search without a paper trail, defeat two-key, capture the
   Compact rotation, or rewrite history.
4. **Partner agency** — a Compact member in good standing abusing
   the sharing, cross-audit, or rotation protocols.
5. **File attacker** — read or write access to the database file,
   a backup set, or the evidence directory (stolen laptop, rogue
   admin, ransomware staging) without any API key.
6. **Edge attacker** — controls one camera/edge node or anything
   that feeds Janus: Frigate events, hot-list feeds, partner
   checkpoints. Everything arriving from these sources is
   untrusted input.
7. **Supply-chain / operator attacker** — can influence scripts,
   cron jobs, config files, or the restore path; or phishes the
   operator who runs them.

## Named hunts (a floor, not a ceiling)

1. **The 2FA surface (new code in 1.2.4 — attack it hardest).**
   TOTP enrollment and activation ceremony, drift window, replay
   of accepted codes, recovery-code generation/storage/use,
   throttling interaction with AUTH_FAIL, the demo-mode waiver —
   can a production install be made to believe it is a demo?
2. **Command construction.** Janus and its scripts invoke the
   openssl CLI for Ed25519 operations. Audit every invocation:
   are any attacker-influenced values (names, refs, paths,
   payloads) interpolated into a command line or shell string?
3. **Untrusted-input parsing.** frigate_bridge events, hotlist_sync
   feeds, partner checkpoint files, /share/query payloads,
   config files on reload. Malformed, oversized, or hostile
   values — what breaks, what leaks, what executes?
4. **Alert suppression as an attack goal.** The system's safety
   function is alerting. An attacker who cannot read a single
   plate but can silently stop alerts (hot-list corruption,
   watermark/sink interference, fence states, clock games) has
   won. Hunt silence, not just disclosure.
5. **Chain and witness attacks.** Beyond tamper-evidence: can a
   file attacker (model 5) roll the database back to an earlier
   valid state and have the system accept the shorter history?
   What does the anchor actually detect, and what does it miss?
6. **The proposed LLM monitor — red-team the design.** The
   design now exists on paper: ARGUS, spec at
   `~/workspace/noctua-1.0/argus/SPEC.md` (anomaly review,
   guarded self-healing in two tiers, sanitized internet
   research behind a data firewall, spec'd hardware). Attack
   the spec as written, including its six self-identified open
   questions. Assume its inputs include audit-derived text
   containing attacker-controlled strings (plates, case refs,
   user-supplied fields) and untrusted web text. Rule on: can
   injection make it suppress, misroute, or fabricate? Do its
   authority limits hold mechanically, or only as prose? Your
   verdict must state the constraints under which it may
   exist — or that it may not.
7. **Privacy leakage outside the chain.** The chain holds no plate
   text by design. Do logs, error messages, HTTP responses,
   timing, counts, or the scrubber leak what the chain protects?
   (Existence oracles have been found here before — hunt for the
   next one.)
8. **Denial of service against the guarantees.** Lock contention,
   chain-growth throttles, expensive verifications, spool/sink
   exhaustion — which availability failures degrade silently
   instead of alarming?

## Rules of evidence

- Every finding: attacker model, attack path, and either an
  executed reproduction or a code citation (file:line) precise
  enough for the orchestrator to verify in minutes. Assertions
  without one of those two are recorded as speculation and earn
  nothing.
- Severity is judged against the system's stated guarantees —
  confidentiality of reads, integrity and completeness of the
  audit chain, availability of alerts — not generic CVSS.
- Generic advice ("use TLS," "patch your OS") is out of scope
  unless tied to a specific line of this code or a specific step
  of these scripts.
- Disagreements between seats are preserved, not averaged. Where
  a claim is code-checkable, the code wins.
- Legal and statutory questions are not yours to settle; note
  them for the Ben Hooper / ACIC lanes and move on.

## Deliverables (per seat)

1. Your attack surface map (one page: assets, entry points,
   trust boundaries, as YOU derived them from the code).
2. Findings register: severity, attacker model, path, evidence.
3. Your ruling on the LLM monitor (named hunt 6).
4. Verdict against this round's criterion: **no surviving
   Critical or High finding exploitable by its stated attacker
   model without a compensating control already in the code.**
5. The single forced change that is the price of your vote.

## Required output of the round (orchestrator)

The synthesis must also produce a **pilot pen-test gate clause**
for the pilot spec: an independent penetration test of the
deployed pilot (application + network + key-custody procedure)
as a non-waivable gate before any camera goes live, naming the
free external routes (CISA Cyber Hygiene, MS-ISAC) as the floor
and a paid independent tester as the standard. The clause is
drafted here; it is applied to the spec when the document freeze
lifts, or sooner on Corey's word.
