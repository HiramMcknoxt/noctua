# Project NOCTUA — a city-owned, open-source ALPR design for Cabot, Arkansas

**Status: design and reference implementation. Nothing in this repository is deployed, and nothing here authorizes capturing a single plate.**

> ## ⚠️ DEVELOPMENT BUILDS — NOT DEPLOYMENT-READY
>
> Every version in this repository — including the newest, **1.2.8** — is a
> **development build**. None is approved for deployment, and none may be used
> to operate a live ALPR system. The multi-round hostile review process
> documented here has found real vulnerabilities in successive versions
> (including a fail-open two-factor authentication defect in 1.2.4, found by
> Security Round 1, and three blocker findings in 1.2.6, found by Round 9);
> each round's findings are published in that round's synthesis, and later
> versions exist because earlier ones were **not** good enough. The current
> version, 1.2.8, has passed its builder battery and an independent cold
> verification, and the code loop has **converged** under the project's own
> criteria 1–4 (Round 10 record and convergence addendum, in `council10/`).
> Convergence is a code-review outcome only — it certifies nothing about
> deployment readiness and lifts none of the gates below. Independently
> of code state: **no camera goes live until a non-waivable, independent
> penetration test of the deployed pilot has been completed**, the City
> Council has adopted the written policy, ACIC's terms are in place, and the
> Council separately authorizes a pilot after a public hearing. See
> [RELEASES.md](RELEASES.md) for the per-version record.

**Round 10 update (Nov 26, 2026):** Round 10 — the final code gate for
1.2.7 — closed **NOT CONVERGED**, on a single branch of one criterion
(criterion 2): an anchor-fence reason-promotion gap in 1.2.7, in which a
genuine checkpoint disagreement evaluated while the anchor fence stands for
a file-state reason is never promoted into the fence record, so a later
clean evaluation could clear the fence with the disagreement leaving no
trace. The commissioned scoped **1.2.8** micro-build fixed that branch
(and the round's remaining ceremony and hotlist items); the chair's
independent cold verification of 1.2.8 passed (full battery SUCCESS, W
battery 6/6), and by the convergence addendum to the Round 10 synthesis
the **code loop is CONVERGED under criteria 1–4 at 1.2.8**. The full
Round 10 record is in [`council10/`](council10/). Convergence is not a
deployment approval: the builds here remain **DEVELOPMENT BUILDS — NOT
DEPLOYMENT-READY**, and the deployment gates (the non-waivable
independent penetration test of the deployed pilot, the city attorney's
answers, and the policy / Commission / Council authorization gates) all
stand.

Cabot, Arkansas (pop. ~26k) currently leases 9 Flock ALPR cameras (8 Falcon + 1 Flex; $27,500 invoiced in 2026 — invoiced, not shown paid — on staggered 24-month tranches; the hardware remains Flock's). The department's own reported figures for Jan. 1 – Jun. 30, 2026: 8,040,000 plates scanned, 688 hot-list matches (8.56 per 100,000 reads), 7 stolen vehicles recovered, 19 arrests.

This repository is the working design for a possible city-owned alternative: commodity LPR cameras, open-source detection/OCR, all data on a city server, designed in the open by a Citizens Commission, and implemented only if the City Council separately authorizes it after a public hearing. NOCTUA is a codename (the little owl, *Athene noctua*); the formal documents keep their plain titles.

## NOCTUA 1.0 (Nov 24, 2026)

The production rewrite lives in [`1.0/`](1.0/): Janus 1.0 (two-key Tier 3, evidence export, cumulative statutory-report counters, dead-man heartbeats, provisioning/backup/restore tooling, Frigate bridge, verified demo dataset), the network/install/operations guides, CONTINGENCIES and CANT-DO, the failure-mode simulator, and the integration record explaining what the simulation findings changed. The v0.9 reference build below it in this repo is preserved as history.

## The development record, 1.2.3–1.2.8 (Nov 24–26, 2026)

Development continued in the open after 1.2.2. Each version folder
(`1.2.3/` … `1.2.8/`) contains that build's code (Janus, Sentinel, and the
operations scripts), its build report (`TRACK-*-REPORT.md`), and — where an
independent cold verification was run — the verification record
(`VESPER-VERIFICATION-*.md`). The hostile multi-AI council review continued
round by round; each round's brief, the individual seat reviews, and the
chair's synthesis are published in `council3/` … `council10/` and
`security-round/` (a dedicated threat-model round on 1.2.4). Every seated
round returned **NOT CONVERGED** — that is the process working as designed,
and it is why the warning above applies to every version here. Round 10,
the review of 1.2.7, closed NOT CONVERGED on a single criterion-2 branch;
the commissioned 1.2.8 micro-build addressed that branch, the chair's cold
verification passed, and the code loop converged by addendum to the
Round 10 synthesis. [RELEASES.md](RELEASES.md) indexes
every version with its battery result, verification status, and reviewing
round.

Two design documents are published as **draft specifications — not built**:
the **Prytaneum** credentialing mechanism (`credentialing/`), under which a
credentialing foundation could certify cities to run NOCTUA on 90-day timed
certificates and revoke certification for abuse, and **ARGUS v0.2**
(`argus/`), a read-only advisory LLM monitor design (no system credentials,
its output never a daemon input).

## The gates come first

Nothing in this design goes live until, in order:

1. The City Council adopts a written ALPR policy (Ark. Code § 12-12-1805(a)(3)) — a draft is in `spec/written-policy-draft.md`.
2. ACIC answers, in writing, how hot-list access works for a city-operated system — Path A (matching stays on the dispatch/ACIC side), Path B (the city server is a CJIS system, priced before any build), or Path C (approved vendors only; the pilot stops). *(Update, Nov 25, 2026: ACIC answered — a no-vendor, city-operated system can receive the hot-list file under an MOU; the file is delivered by ACIC email four times daily and there is no real-time interface. The answers rest on ACIC policy, not statute; the legal questions remain with the City Attorney.)*
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
| `council/`, `council2/` … `council10/` | The hostile multi-AI review rounds and their syntheses — disagreements preserved |
| `security-round/` | The dedicated threat-model round on NOCTUA 1.2.4 |
| `1.0/` … `1.2.8/` | The versioned builds, oldest to newest — all development builds, none deployment-ready |
| `credentialing/` | The Prytaneum credentialing-foundation spec (draft — not built) |
| `argus/` | The ARGUS v0.2 advisory-monitor spec (draft — not built) |
| `RELEASES.md` | The per-version index: battery results, verification status, reviewing round |

## The design in one paragraph

Every access goes through one front door (**Janus**): named individual accounts only, every search tied to a validated case number with a stated justification, historical searches behind a judicial-authorization gate, and the outside auditor read-only. Every allowed *and* blocked action is written to an append-only, hash-chained audit log (**Sentinel**) whose entries never contain plate text (keyed references only); the chain streams to an outside sink and is anchored by daily signed checkpoints held outside the department. Non-hit reads are deleted at 14 days — really deleted (secure-delete + vacuum), except records under legal hold. The statutory six-month report (Ark. Code § 12-12-1805) is a designed output, compiled from plate-free outcome records preserved 18 months.

## What the review found

This design was put through a hostile review by four AI systems before any of it was shown to anyone (see `council/`). Their unanimous verdict: proceed with the Commission and the gated pilot; do not authorize operational replacement yet; and do not oversell what is proven. The fixes they forced — including two defects found in this code and repaired the same day (plate text in the audit chain; deletions that weren't erased at the file layer) — are folded into spec v2 and the current deploy package. The rounds that followed (3–9 and Security Round 1) kept finding real defects in successive builds; the record is published in full so any reader can check that claim round by round.

## License and reuse

Built for public reuse by any city asking the same questions. Read the spec's source notes before quoting any figure: other cities' numbers are reported figures, not quotes, and Cabot's cost figures are qualified planning estimates, not bids.
