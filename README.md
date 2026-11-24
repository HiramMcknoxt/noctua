# Project NOCTUA — a city-owned, open-source ALPR design for Cabot, Arkansas

**Status: design and reference implementation. Nothing in this repository is deployed, and nothing here authorizes capturing a single plate.**

Cabot, Arkansas (pop. ~26k) currently leases 9 Flock ALPR cameras (8 Falcon + 1 Flex; $27,500 invoiced in 2026 — invoiced, not shown paid — on staggered 24-month tranches; the hardware remains Flock's). The department's own reported figures for Jan. 1 – Jun. 30, 2026: 8,040,000 plates scanned, 688 hot-list matches (8.56 per 100,000 reads), 7 stolen vehicles recovered, 19 arrests.

This repository is the working design for a possible city-owned alternative: commodity LPR cameras, open-source detection/OCR, all data on a city server, designed in the open by a Citizens Commission, and implemented only if the City Council separately authorizes it after a public hearing. NOCTUA is a codename (the little owl, *Athene noctua*); the formal documents keep their plain titles.

## NOCTUA 1.0 (Nov 24, 2026)

The production rewrite lives in [`1.0/`](1.0/): Janus 1.0 (two-key Tier 3, evidence export, cumulative statutory-report counters, dead-man heartbeats, provisioning/backup/restore tooling, Frigate bridge, verified demo dataset), the network/install/operations guides, CONTINGENCIES and CANT-DO, the failure-mode simulator, and the integration record explaining what the simulation findings changed. The v0.9 reference build below it in this repo is preserved as history.

## The gates come first

Nothing in this design goes live until, in order:

1. The City Council adopts a written ALPR policy (Ark. Code § 12-12-1805(a)(3)) — a draft is in `spec/written-policy-draft.md`.
2. ACIC answers, in writing, how hot-list access works for a city-operated system — Path A (matching stays on the dispatch/ACIC side), Path B (the city server is a CJIS system, priced before any build), or Path C (approved vendors only; the pilot stops).
3. The Citizens Commission (7 volunteers) reports, and the Council votes to authorize a limited pilot after a public hearing, with an automatic sunset.

The design is built on **labeled assumptions**: Path A is the planning assumption; the historical-search authorization is a configurable gate pending the City Attorney's opinion. An answer that changes a path changes settings and prices, not the architecture.

## What's here

| Path | Contents |
|---|---|
| `index.html` | Public transparency dashboard (simulation, locked to Cabot's real match frequency) |
| `cpd-console.html` | Demonstration operations console — simulates its backend; the production console is this interface wired to the Janus API |
| `spec/` | Pilot spec v1, pilot spec v2 (current), and the draft written policy |
| `deploy/` | The deploy package: Janus (the front-door service), Sentinel (the witnessed audit chain), retention job, Frigate configuration, runbook |
| `sim/` | The auditable Python simulator core, its report, and the council demo script |
| `council/` | The hostile multi-AI review of this design (four seats) and the synthesis — disagreements preserved |

## The design in one paragraph

Every access goes through one front door (**Janus**): named individual accounts only, every search tied to a validated case number with a stated justification, historical searches behind a judicial-authorization gate, and the outside auditor read-only. Every allowed *and* blocked action is written to an append-only, hash-chained audit log (**Sentinel**) whose entries never contain plate text (keyed references only); the chain streams to an outside sink and is anchored by daily signed checkpoints held outside the department. Non-hit reads are deleted at 14 days — really deleted (secure-delete + vacuum), except records under legal hold. The statutory six-month report (Ark. Code § 12-12-1805) is a designed output, compiled from plate-free outcome records preserved 18 months.

## What the review found

This design was put through a hostile review by four AI systems before any of it was shown to anyone (see `council/`). Their unanimous verdict: proceed with the Commission and the gated pilot; do not authorize operational replacement yet; and do not oversell what is proven. The fixes they forced — including two defects found in this code and repaired the same day (plate text in the audit chain; deletions that weren't erased at the file layer) — are folded into spec v2 and the current deploy package.

## License and reuse

Built for public reuse by any city asking the same questions. Read the spec's source notes before quoting any figure: other cities' numbers are reported figures, not quotes, and Cabot's cost figures are qualified planning estimates, not bids.
