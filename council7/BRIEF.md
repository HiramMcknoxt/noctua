# NOCTUA Council — Round 7 Brief: Review of 1.2.3

You are a seat on the NOCTUA council. NOCTUA is a city-owned,
open-source automated license plate reader (ALPR) system design for
Cabot, Arkansas: cameras feed a single gated API ("Janus"), every
action lands in a hash-chained, externally witnessed audit log (the
"Sentinel" chain), plate data purges on a short clock, protection
orders make a plate invisible, and a multi-city Compact lets member
agencies share and audit each other reciprocally. Arkansas law
(Ark. Code §§ 12-12-1801 to -1808) caps ALPR retention at 150 days;
the Cabot design purges ordinary reads at 14.

Round 6 reviewed 1.2.2 and closed NOT CONVERGED — unanimously among
valid seats. Its synthesis (in your docs attachment) commissioned
1.2.3 as items R1–R15; two late seat findings and one commissioned
feature were added during the build: R16 (a held hit's underlying
reads inherit the hit's protection — DeepSeek), the Qwen residuals
(append-race sink shape; destroyed-on-paper evidence bundles;
_strict_id overflow), and a DEMO-ONLY presenter account,
`imperator`, which must be impossible outside a demo-flagged config
(Janus must refuse to start if it appears anywhere else). 2FA is
explicitly OUT of scope for this build — it is scoped separately
(2FA-SCOPE.md, in your docs) as the next round's headline; do not
fail 1.2.3 for its absence, though you may note the gap.

## Your attachments (byte-identical to the 1.2.3 tree)
- janus.py and sentinel.py individually
- scripts-combined.txt — every operator script
- docs-combined.txt — the Round 6 synthesis (the commission), the
  builder's design decisions, TRACK-123-REPORT.md, 2FA-SCOPE.md
- tests-combined.txt — the builders' suite, the Q battery +
  invariants, the R battery, the load envelope

## The acceptance standard you are judging against
Round 6 replaced "test counts" with verified invariant satisfaction:
every R item carries a discriminating case that FAILS on 1.2.2 and
PASSES on 1.2.3, exercised against real multi-step lifecycles (real
predecessor-tree upgrades, two consecutive Compact audits, a full
rotation ceremony including an abort, a lost-key restore, the pin
ceremony on databases written by the real 1.1 code). A test that
observes zero of the thing it names is a failed test, not a pass.
The orchestrator has re-run every leg cold — builders' suite,
round-4 attacks, round-5 seat-1 suite, the round-6 seat-2 harness,
Q battery + invariants, R battery, load envelope — and will report
her numbers alongside this brief's distribution; dispute them if
your own runs disagree.

## Named probes (attack these specifically)
1. **The rebuilt Q16 sink case.** Round 6's Q16 was vacuous (it set
   an env var nothing reads). It has been rebuilt on the real sink
   with fault injection. Break it again if you can: sink down,
   forced rollbacks, concurrent bursts — phantoms, duplicates, or
   dropped committed entries all count. A third phantom shape was
   claimed by the Qwen seat (append() re-reading transaction state
   unlocked, racing a handler's rollback): is that shape
   structurally impossible in 1.2.3, or merely untested?
2. **Protection orders as records (R1).** Two overlapping orders on
   one vehicle — native, migrated from real 1.1 data, and mixed.
   Release one; the other must still protect. Migration must
   preserve every order as its own record with its own court
   reference.
3. **The rotation ceremony (R6).** Commit phase freezes at first
   reveal; authorship is the partner's own Ed25519 signature; a
   supervisor transports but never authors; a stuck ceremony is
   clearable. Grind it, replay it, strand it.
4. **The pin ceremony (R3) on a quiet install.** A 1.1 database
   whose only keyed refs come from Tier 3 fragments: does
   verify-don't-proxy find the key, and does the boot-refusal
   message name a remedy that actually works?
5. **The imperator guard.** Construct any path by which the demo
   presenter account — or the demo flag itself — exists or takes
   effect in a non-demo installation.

## Judgment calls put to the seats
(a) The R6 witness rule as built: an attestation counts only from
    the round's designated attester (the bye member, or the round's
    auditor at n=2). Sound, or does it strand small compacts?
(b) The R12 fence: a stale case feed closes data reads but lets
    safety writes (ingest, protection-order placement/release)
    proceed with a chained warning. Right line, or should stale
    mean stopped?
(c) Qwen's claim that restore's atomicity is over-broad (validation
    covers tar slips, not I/O failure mid-swap): narrow the claim,
    or demand the fail-injection test before convergence?

## Rules of the seat
- State your model and effort exactly as your interface shows them.
- A finding counts when you reproduce it (executed code) or cite it
  to file and line in a way the orchestrator can verify in minutes.
  Say plainly which of your claims are code-read only.
- Verdict per convergence criterion (1) no surviving
  deployment-blocking or code-critical finding; (2) every prior
  forced change implemented or answered in writing; (3) what
  remains is documented CANT-DO limitations or legal questions
  routed to the City Attorney / ACIC — not code defects;
  (4) the orchestrator's re-tests pass. Then an overall verdict:
  CONVERGED or NOT CONVERGED, and the single forced change that is
  the price of your vote if it is not.
- HANDOFF PROTOCOL (standing, all council work): before starting
  long work, create HANDOFF.md in your working area stating your
  seat, model, the build under review, and your plan; keep it
  current at every milestone. If your work product is delivered as a
  file, the handoff travels with it. A seat that runs out of room
  without a current handoff has failed the task.
