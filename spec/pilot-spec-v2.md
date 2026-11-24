# CITY OF CABOT, ARKANSAS

# Cabot Open-Source ALPR Pilot — Design Specification

## Version 2 — revised after AI council review, November 23, 2026

## Project NOCTUA

*Codename (working title only — the formal document title above is what appears in any packet): **NOCTUA** — Athene noctua, the little owl of Athena/Minerva: a sentinel that watches one post and ignores everything it is not there for. Backronym, for packet use if wanted: **N**o **O**utsourcing, **C**ity-**T**racked, **U**nshared **A**ccess. Component names in this spec: the Front Door API is **Janus** (the Roman god of doors and thresholds — nothing passes except through him), and the outside-witness checks are the **Sentinels** (§10).*

**A city-owned, open-source automated license plate reader pilot, adapted from the Clark County, Arkansas county-owned design**

|  |  |
|---|---|
| Prepared for | The Citizens Commission on a City-Controlled ALPR System; the Mayor, the City Attorney, and the Members of the Cabot City Council |
| Sponsor draft | Corey Spangler, Council Member, Ward 1 Position 2 |
| Status | **DRAFT v2 — for Commission discussion. Not introduced, not a vendor quote, not a procurement award, and not an appropriation. Nothing in this spec authorizes a system by itself — and nothing in it authorizes capture, purchase, or deployment (see "Labeled assumptions").** |
| Date | November 23, 2026 (v1); November 23, 2026 (v2, same-day revision after the AI council review) |
| Companion documents | (1) Draft Ordinance — Third-Party ALPR Ban and Citizens Commission (Nov. 16–17, 2026); (2) Cabot City-Controlled ALPR Plan — Technical and Cost Proposal (Nov. 16, 2026, rev. Nov. 17); (3) Draft Tiered Judicial Authorization for Access to ALPR Data (Nov. 19, 2026); (4) AI Council Synthesis — NOCTUA / Cabot Open-Source ALPR Package (Nov. 23, 2026); (5) Three-Lane Inquiry Package — City-Owned ALPR Evaluation (Nov. 23, 2026); (6) Draft Written Policy — Captured Plate Data (companion draft, for City Attorney review) |
| Principal source adapted | Brayden Sanders, *Flock Alternatives: A Research Hub* — Clark County, Arkansas (GitHub: TiredofSleep/flock-alternatives, Oct. 2026): `design/architecture.md`, `design/sentinels.md`, `research/02-audit-log-models.md`, `research/04-build-path-cjis.md`, `research/07-arkansas-state-police-lpr.md`, `docs/action-plan.md`. Cited below as "Clark County design," with section names so any reader can check it. |
| No branding note | This is unbranded city business. It carries no project or campaign branding of any kind. |

*How to read the labels: **[Source: …]** = a figure or rule taken from a named record. **"Applied arithmetic"** = a verified per-unit figure multiplied by a Cabot count, inputs shown. **"Estimate / allowance"** = a planning figure procurement or the Commission must confirm or replace. **"Commission decision"** = a threshold or choice this spec proposes but the Commission may change, stating its reasons.*

---

## What changed in v2

Version 1 was reviewed on November 23, 2026 by a four-seat AI council (ChatGPT, Claude ×2, Gemini) given an identical hostile-review brief. The council's verdict was unanimous: proceed with the Citizens Commission and the gated pilot; do not authorize operational replacement; do not describe the build as production-ready. Its synthesis produced a 13-item amendment list. **All 13 amendments are folded into this version.** Nothing in v1 that the amendments do not touch has been changed; every Cabot figure is carried over unaltered. The full synthesis is companion document (4).

| # | Amendment (synthesis wording, condensed) | Where it landed in v2 |
|---|---|---|
| 1 | Adopted written policy (§ 12-12-1805(a)(3)) is a precondition to **any** capture, Stage 0 included; Stage 0 is CPD-operated with consenting vehicles only | §2 principle 4 (rewritten); §3 Stage 0 row; §14 timeline (policy-adoption step moved ahead of Stage 0); companion document (6), the draft written policy itself |
| 2 | Frigate lockdown as a design requirement — write-only sensor; no human-reachable UI/API; media retention ≤ 14 days; authenticated ingest; isolated camera VLAN; NTP discipline | §4, new "Sensor lockdown" component row and paragraph; §15 Risk 11 |
| 3 | Sentinel v2: real-time streaming to an independent sink; daily signed checkpoints including entry count; auditor recomputes independently; chain stores keyed plate references only (done in code) | §4 architecture diagram and Audit log / External witness rows; §10 "In the pilot" list; Appendix A (plate-reference fields) |
| 4 | Evidence lifecycle: legal-hold flag in Janus; evidence export with hash + chain of custody; prosecutor-approved disposition schedule replacing the flat 30-day resolved-hit delete; plate-free outcome records preserved 18 months | §4 new component row; §9 (evidence-hold row rewritten, new outcome-records row and paragraphs); §15 Risk 12 |
| 5 | Statutory report generator: report view = § 12-12-1805 categories exactly, compiled six-monthly, preserved 18 months, aggregates exempt from retention deletes; prosecutor feedback loop for prosecution outcomes | §4 Report job row; §9 outcome-records row; §13 task table |
| 6 | Case-gate hardening: justification field required; catch-all case numbers banned and auto-flagged; auditor sampling of searched plates vs. case files; case-list staleness fails closed, logged and alarmed; emergency-flag post-hoc review + frequency kill metric | §7 items 6–9; §8 Emergency row; §11 Metric 10 and kill condition K8 |
| 7 | Protection-order suppression flag built **before** any owner-disclosure feature; owner-disclosure request process defined; FOIA redaction process for the audit log preserving public verifiability via published roots | §2 principle 8; §9 disclosure paragraphs; §4 Front Door row (suppression flag) |
| 8 | ACIC/dispatch inquiry expanded: Path A real-time matching capability and latency; CJIS scope via case-list sync and via hit-detail return flow; § 12-12-1804(c) 24-hour update-duty ownership | §5 Step 1; §16 open-questions table; Appendix B questions 9–11; companion document (5), Lane 1 questions 9–10 |
| 9 | Named maintainer + deputy; on-call expectation; dead-man alarms to Clerk and auditor for retention/bridge/witness failures; Commission designs policy and receives summaries; auditing is a named paid/contracted role | §3 Users row; §12 auditor line; §13 (named people, task table, dead-man alarm paragraph) |
| 10 | NDAA §889 camera requirement; onboard storage and cloud/P2P features disabled | §4 Cameras row (warning upgraded to requirement); §6 closing note; §15 Risk 4 |
| 11 | Independent adversarial verification of the data-access boundary as a written condition in the authorization; unresolved critical bypass = no Stage 1 | §14 timeline (new gate row before Stage 1); §15 Risk 11 |
| 12 | Demo script additions: bypass attempt shown blocked/logged; on-screen disclosure that the console is not yet wired to the production API; tamper test re-run as a full-chain rewrite against the witnessed checkpoints | §10, new "What the demonstration must show — and say" subsection |
| 13 | Authorization language: a failed pilot does not default to vendor renewal; discontinuation remains an explicit option | §1 closing paragraph; §14 final row |

Two council findings were also verified against the working code and fixed on November 23, 2026, before this revision: the audit chain no longer stores plate text (keyed HMAC plate references only), and deletion is now real at the file layer (SQLite `secure_delete` plus vacuum after retention runs). Both fixes are recorded in the synthesis and reflected in §4 and Appendix A.

## Labeled assumptions

This version is written to be buildable and reviewable **before** three outside answers arrive. The assumptions are stated here, in one place, so no reader has to guess which parts of the design are settled and which are placeholders:

1. **Path A is the planning assumption.** The design assumes ACIC confirms that hot-list matching can stay on the ACIC / dispatch side and the city server is not a CJIS system (§5, Path A). That answer is **pending** — Lane 1 of the three-lane inquiry package (companion document 5) asks it, and ACIC has not answered. If the answer is Path B, the same build carries a priced CJIS compliance layer (§5, §12); if it is Path C, Stage 1 does not proceed (kill condition K1). No section of this spec should be read as claiming Path A is confirmed.
2. **The Tier 3 instrument is a configurable authorization gate, not a settled mechanism.** Arkansas law contains no ALPR court-order mechanism; in practice Tier 3 authorization likely means a probable-cause warrant, but that is **pending the City Attorney's opinion** (Lane 2, question 3). The front door is therefore specified to enforce *an* authorization instrument — entered number, uploaded authorization, two-key execution — without hard-coding which instrument it is. The November 19 draft's open questions (§8) remain pre-go-live gates.
3. **Nothing in v2 authorizes capture, purchase, or deployment.** This spec authorizes nothing by itself (see Status). Capture of any plate — including the Stage 0 lot test — additionally requires the adopted written policy (amendment 1). Purchase requires the §14 procurement step after a separate Council authorization. Deployment requires the separate Council vote the companion ordinance prescribes. Drafting, building, simulating, and reviewing under these labeled assumptions commits the City to none of those steps.

---

## 1. Purpose — what this pilot is, and what it is not

The November 16 City-Controlled ALPR Plan proved a *purchase* model on the record: buy Axis cameras outright, license recognition software (the Quincy / OdinEye route), own the data. This spec adds the route that plan listed but did not design in full: **recognition software the City does not rent at all** — open-source software, running on city hardware, with every search forced through one logged front door that someone outside the Police Department can check.

No U.S. city has put such a system into production. OpenALPR, the original open-source engine, is effectively unmaintained since Rekor acquired it in 2019 (last open release 2.5.103, March 2018). The current open stack — Frigate NVR's built-in LPR and fast-alpr — is proven in homes, parking lots, and HOAs, not in a police system. The Clark County hub is, like this spec, "research and planning, not a product." This pilot is therefore designed as a **test with kill conditions**, not as a promise.

**The pilot answers five questions, in order:**

1. **CJIS/ACIC:** Can a city-owned box match plates against hot lists without itself becoming an unmanaged CJIS system — or, if it does become one, what does compliance actually cost?
2. **Accuracy:** Can open-source recognition read Arkansas plates at Cabot road speeds, day and night, well enough to be a lead generator — measured against a hand-checked sample, not a vendor claim?
3. **Accountability:** Can every search be forced through one front door, tied to a real person and a validated case number, into a tamper-evident log that an outside witness actually verifies?
4. **Deletion:** Does data delete on schedule, automatically, and can the City *prove* nothing older than the cap survives?
5. **Maintenance:** How many staff hours does this really take, week to week — the cost every vendor comparison hides?

**A reference implementation, not a finished answer.** Software, a demonstration console, and a deploy package exist for this design (built November 2026, all synthetic data). They exist so the Commission has something concrete to inspect, amend, or reject — not to pre-decide its work. If the stack is already built, the obvious question is what the Commission is designing; the answer is: the policy, the thresholds, the acceptance criteria, and the go / no-go judgment. The Commission may amend or discard any part of the reference build, and this spec is written so that it can. *(Amendment: AI council synthesis, Gemini seat.)*

**What the pilot is not:** not an expansion (no camera beyond the locations in §3), not a replacement decision (the full-system decision stays where the companion ordinance puts it — a separate Council ordinance, after public hearing, on the Commission's June 2027 recommendations), and not a back door around that vote. If the pilot fails its gates, the purchase model in the November 16 plan remains the fallback, and the no-ALPR outcome remains on the table. **A failed pilot does not default to renewing the current vendor.** Whether Cabot has ALPR at all, and who operates it, are separate questions, and any authorization written from this spec must say so expressly: discontinuation is an explicit option at every decision point, not a failure state the system falls out of into a renewal. *(Amendment 13.)*

---

## 2. Design principles — borrowed from Clark County, tightened for Cabot

1. **One logged front door.** "All reads come through one API. There is no direct DB access for users and no national-lookup feature." [Source: Clark County design, architecture §3] Every documented ALPR abuse in the research — a DEA agent searching under a local officer's password, free-text reasons like "idk" — happened because there was a side door or an unreviewed log.
2. **The log is only real if an outsider checks it.** A hash chain nobody verifies is, in the Clark County phrase, "tamper-evident to nobody." The root hash is published on a schedule to a place the City operating the system does not control, and a named outside auditor verifies it on a short cadence. [Source: Clark County design, architecture §3; audit-log research §§ "Tamper-evident logging," "Design requirements"]
3. **A case number is validated, not typed.** Each query requires a case number **validated against a real case record** (RMS or case list). "No valid open case means no search." Free text is not a reason. [Source: Clark County design, architecture §3]
4. **Policy before capture — any capture.** The Clark County action plan's hard gate is adopted verbatim in substance: "nothing gets built until ACIC confirms how hotlist access works and the [governing body] passes the ordinance." Version 2 tightens it, on the council's legal finding: the adopted written policy required by Ark. Code § 12-12-1805(a)(3) is a precondition to **any** capture, the Stage 0 lot test included — a test that captures plates before the policy exists risks operating outside the statute's authorization and exposing any resulting evidence to exclusion. For Cabot: nothing that captures a plate — public-road or lot — operates until (a) the ACIC answer in §5 is in writing, and (b) the Council has adopted the governing policy, including the tiered judicial-authorization rules in §8. A draft policy accompanies this spec as companion document (6) so that adoption is an edit, not a start from zero. *(Amendment 1.)*
5. **Government ownership already works in Arkansas.** The Arkansas State Police own their "LPR systems, equipment, databases and data" (ASP Rule 5(d)), retain no more than 150 days, log deletions and every disclosure, and report quarterly to the Legislative Council. [Source: Clark County research 07, ASP LPR Rules 130.01.24 Ark. Code R. 002] Cabot's design copies ASP's structure and goes further where ASP is silent: ASP defines query logs but does not specify their contents or a review schedule; this spec does both.
6. **Open-source all of it.** Code, configuration (minus credentials and hot-list data), runbooks, and audit tooling are published, "so the [city] is never locked to any one maintainer." [Source: Clark County design, architecture §7] This is also the license test in §6.
7. **Begin from the limits, not the capabilities** — the charge the companion ordinance already gives the Commission. No component is procured because it *can* do something the policy does not ask for.
8. **Oversight sees records, not raw plates.** Ark. Code § 12-12-1808 restricts disclosure of captured plate data; an oversight mandate does not by itself authorize access to protected data. Commissioners and the outside auditor work from redacted records, keyed plate references, aggregates, and summaries. Raw plate data stays inside the front door, behind the case gate, for named operational users only. *(Amendment 7.)*

---

## 3. Pilot scope

| Item | Pilot spec |
|---|---|
| Stage 0 — bench / lot test | 1 camera, on City property (e.g., a city lot), City-owned and volunteer vehicles only, **operated by the Police Department** under the adopted written policy (§2 principle 4). **No public-road capture, no hot list, no enforcement use.** Runs during the Commission's work (spring 2027) to answer the accuracy question cheaply and lawfully. Department operation is specified because a test that matches nothing, run by non-law-enforcement, may not fit the statute's law-enforcement authorization — the City Attorney's answer (three-lane package, Lane 2 question 7) confirms the smallest lawful form before Stage 0 runs. *(Amendment 1.)* |
| Stage 1 — road pilot | **3 cameras**, at 3 of the 9 existing Flock locations, chosen by the Commission with the Department for (a) an entry/exit chokepoint, (b) a higher-speed site (the hard case for open-source OCR), and (c) a slow-approach site (the easy case). No new locations. No increase in citywide camera count at any point. |
| Duration | **90 days** of live operation, following the Clark County action plan's pilot length, then a public report and automatic shutdown unless the Council affirmatively extends it. [Source: Clark County action plan §5] |
| Users | Named, individually credentialed users only, designated in the governing policy. Planning assumption: the System Administrator, one named backup administrator, the Chief's designee, and the outside auditor (read-only, log-only, redacted records per §2 principle 8). No other accounts in the pilot. **Auditing is a named role** (§13): the Council designates the auditor as a paid or contracted function, not an informal volunteer expectation — the Commission designs policy and receives summaries; it is not the weekly log-review body and not the unpaid IT department. *(Amendment 9.)* |
| Data in scope | Plate reads (plate text, site, date/time, plate-crop image) at the 3 pilot sites only. Raw video is not a function of this system and is not retained. |
| Data out of scope | No regional or national lookup network. No facial recognition. No vehicle-fingerprint / make-model-color search product. No bulk export. No immigration, parking, code-enforcement, or revenue use — Act 668 of 2025 (Ark. Code §§ 12-12-1801 to -1808) already limits lawful uses; the governing policy lists the pilot's permitted uses exhaustively. |
| Sunset | Pilot authority, accounts, and hot-list access expire at day 90. Data collected is deleted on the §9 schedule regardless of what the Council later decides. |

---

## 4. Architecture — one front door, an outside witness, and a retention job

Adapted directly from Clark County design, architecture §1, with Cabot's retention and tier rules substituted:

```
[LPR cameras x3] --RTSP--> [Edge / NVR: Frigate LPR *or* fast-alpr]
                                  |  plate reads only
                                  v
                           [Read store (Postgres) — city hardware,
                            city-controlled network segment]
                                  |
                   every query goes through — no exceptions
                                  v
[Users: named officers] --MFA--> [FRONT DOOR API] --> [Audit log:
                                  |                     hash-chained,
                                  |                     append-only]
                                  |
        entries streamed as written --> [INDEPENDENT SINK outside
                                  Police Dept. / administrator control]
                     signed checkpoint, daily (root hash + entry
                     count) --> [EXTERNAL WITNESS: City Clerk/Treasurer
                                  + public repo]

[Retention job] --hard-deletes past cap, honors legal holds,
                    logs itself--> read store + audit log
[Report job]    --> monthly pilot report + final public report
                    + six-month statutory report in the exact
                    Ark. Code § 12-12-1805 categories, from plate-free
                    outcome records preserved 18 months
[Hot-list matching] --> ON THE ACIC SIDE if ACIC confirms it (§5, Path A)
```

**Components**

| Component | Spec | Notes / source |
|---|---|---|
| Cameras | Dedicated LPR/ANPR, native RTSP/ONVIF, shutter at least 1/1000s (1/2000s at night / speed), IR with focus-shift compensation, motorized varifocal; target ~100 pixels-per-foot on the plate. Two camera classes are tested head-to-head in Stage 0: (a) commodity LPR (Clark County example: Dahua/EmpireTech ITC215 class, ~$300–$450) and (b) the AXIS Q1800-LE from the November 16 plan ($1,779 MSRP). | Camera requirements and commodity price: Clark County research 04, "Cameras." Axis price: November 16 plan §3, named retailers, Nov. 2026. **NDAA §889 is a requirement in v2, not a warning (amendment 10):** pilot cameras must be NDAA §889-compliant regardless of funding source, so no later grant or funding change can disqualify the installed base; if the Clark County commodity example is not compliant, class (a) is an NDAA-compliant equivalent in the same class, priced in procurement. **Onboard storage and cloud / P2P features are disabled** on every pilot camera (see Sensor lockdown, below). |
| Recognition — candidate A | **Frigate NVR built-in LPR:** YOLOv9 plate detector + PaddleOCR; needs at least 4 GB RAM and an AVX/AVX2 CPU. Frigate's own docs warn, in substance, "if a human can't read the characters, Frigate usually can't either," and publish no accuracy numbers. | Clark County research 04, "Software stack"; design architecture §7. |
| Recognition — candidate B | **fast-alpr:** MIT license, ONNX models, swappable detector/OCR backends. | Clark County research 04; architecture §7. Cabot's November 16 plan records fast-alpr as actively versioned (v0.4.0, March 2026). |
| Bake-off rule | Stage 0 runs A and B on the *same* camera feeds and the *same* hand-checked sample (Appendix C). The Commission picks one for Stage 1 on measured read rate, not preference. The loser is documented, not quietly dropped. Paid on-prem fallback (Plate Recognizer, ~95% claimed, Docker) may be benchmarked for comparison only; adopting it converts this from an open-source pilot to the purchase model and must be reported as such. | Fallback and claim: Clark County research 04. |
| Read store | Postgres (or equivalent open-source store) on a city-owned server, on a network segment controlled by the City, encrypted at rest and in transit. No vendor cloud. No general-purpose city file share. | CJIS conditions if this store ever holds CJI: §5, Path B. |
| Sensor lockdown *(v2)* | The recognition layer (Frigate or fast-alpr host) is a **write-only sensor**, not a second front door: it writes reads to the read store through **authenticated ingest** and holds no lasting plate store of its own. Its web UI and API are **not reachable by any human account** in the production configuration (bound to localhost / management interface reachable only by the Administrator for maintenance, with that access itself logged). Its own media retention is configured to **no more than 14 days**, matched to the read retention, so the 14-day promise is true at the media layer and not only in the read store. Cameras sit on an **isolated camera VLAN** with no internet route; camera and host clocks are disciplined by NTP, because read timestamps are evidence. Camera onboard storage and cloud / P2P features are disabled (amendment 10). | Amendment 2. The v1 spec listed "Frigate LPR bridge pinning" as an integration gap; the council's finding is that an unlocked recognition layer is a design hole — an unlogged second front door with its own database, snapshots, and logins — not a version-pinning chore. |
| Front Door API | The *only* query path. Enforces: individual account + MFA; validated case number (§7); tier rules (§8); result minimization; canary stripping (§10); the **protection-order suppression flag** (§9 — a flagged plate returns nothing except as the result of a match, to anyone, including a registered-owner requester). Direct database access for users is technically disabled, not just policy-prohibited. The honest claim, stated in every public presentation: *every action mediated by the Front Door is logged* — which is why the sensor lockdown above and the adversarial verification in §14 exist to make the Front Door the only path in fact. | Clark County architecture §§1, 3; amendments 2, 7. |
| Audit log (Sentinel v2) | Hash-chained, append-only, on WORM / object-lock backup. Minimum fields at Appendix A. Retention and report jobs write their own entries. **v2 changes (amendment 3):** entries are **streamed as written to an independent sink** outside Police Department and administrator control; **signed checkpoints including the entry count are published daily** (not weekly); the outside auditor **recomputes the chain independently** rather than trusting a presented verification; and chain entries carry **keyed plate references only, never plate text** — an append-only permanent log of plate text would itself become captured plate data retained past every cap (implemented and verified in the working code, Nov. 23, 2026). | Clark County architecture §4; audit-log research §"Tamper-evident logging" (WORM + hash chain is the "small-shop-feasible" pattern); amendment 3. |
| External witness | Signed checkpoint (root hash + entry count) published **daily** during the pilot to (a) the City Clerk/Treasurer, who is outside the Police Department chain of command, and (b) a public git repository, so any resident, journalist, or defense attorney can verify the chain did not change after the fact. Publication credentials are not held solely by the system administrator; a missed publication is a dead-man alarm event (§13). | Clark County architecture §3 (witness = "clerk, public git repo"); sentinels §"Who controls what"; amendments 3, 9. |
| Retention job | Scheduled hard delete past the §9 cap; **honors legal holds** — a held record is never deleted by the job (§9); every run logs rows deleted and the oldest remaining timestamp; a run that fails, or does not run, alerts the Administrator, the auditor, and the Clerk the same day (dead-man alarm, §13). Deletion is real at the file layer (secure-delete semantics plus file rewrite), verified in the working code Nov. 23, 2026; backups follow the same retention schedule, or the promise is theater. | Clark County architecture §§1, 5; amendments 4, 9. |
| Evidence hold & export *(v2)* | A **legal-hold flag** in the Front Door, settable by the Administrator on a documented case basis, that stops the retention job for the held records; and an **evidence export** function that moves a held record (image plus read) to the Department's records / evidence system, **hashed at export with chain-of-custody documentation**, after which disposition follows the prosecutor-approved schedule in §9. | Amendment 4. |
| Report job | Generates the monthly pilot report and the day-90 public report from the log itself — counts are computed, not hand-tallied. **v2 (amendment 5):** also generates the **six-month statutory report** in the exact Ark. Code § 12-12-1805 categories (§9), from plate-free outcome records preserved 18 months and exempt from retention deletes. | Clark County architecture §§1, 6 (report contents); amendment 5. |

---

## 5. The CJIS / ACIC boundary — the decision gate that comes first

This is the single most important section. Capturing plates is not CJIS-regulated. **Crossing them against NCIC/ACIC hot lists is.** [Source: Clark County research 04, "CJIS and ACIC"]

**Step 1 — the joint ACIC call (February 2027, Commission's first task).** Through the Police Department's Terminal Agency Coordinator (TAC), the Commission asks ACIC, in writing where ACIC will give it in writing, the questions at Appendix B. The Clark County plan's framing question is adopted: *how do LPR systems in Arkansas receive hot-list data, what agreement does it take, and does a city server holding the hot list become a CJIS system?* ACIC's published contact in the Clark County plan is (501) 682-2222 — verify before use. Small Arkansas agencies usually hold **ACIC Indirect Access** (they can receive criminal-justice information but cannot run transactions directly; recipients need an FBI-assigned ORI). [Source: Clark County research 04]

**v2 — the inquiry is expanded, and already drafted (amendment 8).** Three questions the v1 list did not ask are now Appendix B questions 9–11, because two council seats independently doubted that Path A exists in practice: (9) whether CJIS scope can arrive through the records-system **case-list sync** or through **hit details flowing back** to the city server, rather than through the hot list; (10) who owns the § 12-12-1804(c) duty to update captured plate data against the lists within 24 hours when matching is off-box; and (11) whether Cabot's **dispatch/CAD can actually ingest outside reads and match them in real time**, and at what latency — if it cannot, the real choice collapses to Path B (priced) or Path C, and no further design work proceeds on the Path A assumption. The inquiries are drafted in the three-lane package (companion document 5): Lane 1 to ACIC Operations (ACIC.Operations@dps.arkansas.gov, verified Nov. 23, 2026), Lane 2 to the City Attorney, Lane 3 (dispatch capability and the Department's own 2026 audit-data analysis) held until Lanes 1–2 answer. Drafting the questions early changes no gate: the written answers still gate Stage 1 exactly as Step 2 provides.

**Step 2 — build only the version ACIC's answer permits:**

| Path | ACIC answer | What gets built | Compliance burden |
|---|---|---|---|
| **A — Preferred** | Hot-list matching can stay on the ACIC / dispatch side | City box stores plate reads + a *local* (department-created, documented) list only. NCIC/ACIC checks run through the Department's existing ACIC-connected workflow (dispatch / TAC terminal), as ASP's verify-before-a-stop rule already assumes. The pilot box is **not** a CJIS system. | Lightest lawful path. Still requires: MFA, individual accounts, audit log, training — all already in this spec. |
| **B — CJIS system** | A city server holding a hot-list extract *is* a CJIS system | Same build, hosted on a Police-Department-controlled network, plus a CJIS IT audit across the 13 policy areas: MFA, FIPS-validated encryption in transit and at rest, audit review, lockout after 5 failed attempts, fingerprint check for every administrator (and any vendor with access), CJIS security training, and an FBI Security Addendum for any vendor contract, filed with ACIC. | Priced *before* Stage 1 — see the kill condition at §11. CJIS audits recur (at least every 3 years for direct-access agencies, with action plans due within 30 days of findings). [Source: Clark County architecture §2; research 04] |
| **C — Approved vendors only** | Only state-approved vendors may receive hot-list data | **Pilot does not proceed to Stage 1.** The Commission reports Path C to the Council, asks ACIC how a system gets approved, and the open-source route pauses. Stage 0 accuracy results are still published — they remain useful for judging any vendor's claims. | No workaround. Routing hot-list data to an unapproved system to "make the pilot work" is a kill-condition violation, not ingenuity. |

No Stage 1 purchase order is issued before the City Attorney confirms, in writing, which path applies. That confirmation joins the November 16 plan's existing gating items (hosting route, OdinEye-type terms if the purchase model is later used, contract expiration dates).

---

## 6. Cameras, sites, power, and connectivity

The November 16 plan's Phase 1 site-survey discipline applies unchanged, per site, before any install: (1) mount — what the camera attaches to and who owns it (Flock's poles/mounts are Flock's; reusability is **not** assumed); (2) power — source and whether it is City-controlled, including PoE/midspan needs the camera price excludes; (3) connectivity — how reads reach the read store and the recurring price, which was the largest unpriced line in the purchase model and must not be unpriced here; (4) honest "new pole" sites, priced at the top of the allowance, not discovered mid-install.

Planning figures [Source: Clark County architecture §7; research 04]:

- Off-grid pole site (camera + edge compute + LTE modem + solar + battery): **~$800–$2,500 per site, estimate.**
- LTE / connectivity: **~$20–$50 per camera per month, estimate**, plus storage and replacements — and staff time, identified in both the Clark County hub and the November 16 plan as the real recurring cost.
- Existing powered, wired city sites should price materially below the off-grid figure; the survey, not this spec, establishes which of the 3 pilot sites is which.

Stage 0 deliberately starts on a powered city lot so the accuracy question is answered before any pole, solar, or LTE money is spent.

**Camera configuration note (amendment 10).** Whichever camera class the survey selects: onboard SD/local storage is disabled or removed, vendor cloud and P2P remote-access features are disabled, default credentials are replaced before install, and the camera is reachable only from the isolated camera VLAN (§4, Sensor lockdown). A camera that phones home is a side door with a lens.

---

## 7. Identity, case validation, and the front door in operation

1. **Individual accounts only.** No shared, generic, service, or vendor accounts for human users. Hardware-backed MFA where the front door supports it; MFA in all cases. [Source: Clark County architecture §3 — the DEA/password failure is the stated reason]
2. **Case-number validation.** The front door checks the entered case/incident number against the Department's case list / RMS before executing a search. An invalid, closed (where closure bars the search type), or missing number returns no results and writes a log entry. This replaces free-text "reasons," which the research shows degrade to "idk" / "TBD" and, in one documented case, a single vague search touching 82,413 cameras. [Source: Clark County architecture §3]
3. **Tier check.** The front door applies §8 mechanically: Tier 2 queries return current status only and cannot display history; Tier 3 functions are locked by default and unlock only on an entered judicial-authorization number with the signed authorization uploaded (two-key execution by the Administrator or a designee who is not the applicant), or on a logged emergency entry. Paper rules the software does not enforce are treated in this spec as no rules. **The Tier 3 authorization instrument is the labeled assumption in the front matter:** the front door enforces an authorization instrument; which instrument Arkansas law provides (in practice, likely a probable-cause warrant) is pending the City Attorney's opinion and must be configured before go-live. The front door never invents its own instrument.
4. **Anomaly flags, automatic.** The log system flags, for the auditor's weekly review: bulk or partial-plate sweeps, off-hours use, a single user querying many unrelated plates, any canary hit (§10), any failed-validation attempt pattern, and any missed retention or witness checkpoint. [Source: Clark County architecture §3 — "automated anomaly flags: bulk searches, off-hours use, one user with many plates"]
5. **Lockout and removal.** Five failed login attempts lock the account (CJIS pattern, §5 Path B — applied in the pilot on both paths as good practice). Accounts are disabled at role change, not at the next quarterly review (November 16 plan §9 rule, retained).
6. **Justification, not just a case number (v2, amendment 6).** Validating a case number proves a case exists; it does not prove the searched plate belongs to it. The realistic misuse the council identified at three seats unprompted is a legitimate case number used to look up a person — the ex-partner scenario. So every search requires, in addition to a validated case number, an **own-words justification** recorded with the query: what the plate is wanted for and how it connects to the case. A search with a validated case number but no justification is refused exactly like one with no case number.
7. **No catch-all case numbers.** Shared or generic case identifiers (e.g., a standing "PATROL" number) are banned. The front door maintains a deny list of generic identifiers and **auto-flags** any case number that appears across unrelated plates or users at a rate the auditor sets. A catch-all in use is an anomaly flag, not a convenience.
8. **Relevance sampling.** The outside auditor **samples searched plates against the case files** they purportedly relate to — not merely against the case list — on a monthly cadence, and reports the non-match rate (searched plates that never appear in the case file) in the public report. Sampling, not trust, is what closes the gap between "the case exists" and "this search belonged to it."
9. **Fail-closed on a stale case list.** If the case-list / RMS feed has not refreshed within its configured window, the front door **fails closed**: searches stop, the failure is logged and alarmed to the Administrator and the auditor the same day, and the only way back is an Administrator-documented refresh — not an override that becomes permanent. A system that fails open teaches its users to expect the override. The sync mechanism and refresh window are a §13 maintenance task, set with the Department's records unit before go-live.

---

## 8. Access tiers — the sponsor's tiered judicial-authorization draft, built into the software

This spec incorporates the November 19, 2026 *Tiered Judicial Authorization* draft as the pilot's access law. The Commission may adopt, amend, or reject it, stating its reasons — but the front door must enforce *some* adopted version of it, configured before go-live, not promised for later.

| Tier | Access | Rule (summary of the Nov. 19 draft) |
|---|---|---|
| **Tier 1** | Automated hot-list comparison | No prior judicial authorization. Official lists only (stolen vehicles/plates, arrest warrants, missing/endangered incl. AMBER/Silver). An alert is a lead, not proof: before a stop, visually verify plate + state, verify through dispatch or ACIC/NCIC, compare occupants to any wanted-person description (ASP Rule 6(a) pattern). Custom hot lists are gated: stolen / missing / warrant / court order, or supervisor's written approval on documented imminent-risk facts, expiring in 24 hours without judicial authorization; every entry states its facts, author, and an expiration no more than 30 days out. |
| **Tier 2** | Contemporaneous query | No prior judicial authorization. Plate directly observed in an encounter; case/incident number (or direct-observation statement) and an own-words reason recorded; system returns **current status only, no historical location data**. One plate at a time. Scanning a lot, gathering, or neighborhood for later use is prohibited. |
| **Tier 3** | Historical search | **Prior judicial authorization required** — search warrant or court order on a sworn application showing probable cause, with particularity (plate/vehicle/person, date-time range as narrow as the facts permit and never beyond the retention period or 30 days per authorization, cameras/data set). Two-key execution. Return filed within 10 days. Denials logged; no judge-shopping without disclosing the prior denial. **Reverse searches** (by place/time, to identify unknown vehicles): heightened showing, de-identified results first, identifying data only on a further authorization. |
| **Emergency** | Historical search without prior authorization | Only on specific, recorded facts of imminent threat of death/serious bodily injury (incl. kidnapping, missing/endangered), or flight/destruction risk for a felony involving death/serious bodily injury. Supervisor (or Chief/designee) approval; log entry within 4 hours; judicial notice or application within **48 hours**. If found unjustified: data quarantined, not used, deleted when the matter resolves, and counted in the public report. **v2 (amendment 6): every emergency use receives post-hoc review** — by the reviewing judge where one is engaged, and by the outside auditor in all cases — and **emergency-use frequency is a pilot metric with a kill threshold** (§11, Metric 10 and K8). Until two-key Tier 3 execution exists in practice and not just in this table, a single supervisor's flag is one person approving themselves; post-hoc review of every flag is the compensating control, because the council's shared fear is the exception becoming the everyday route. |
| **Always** | No circumvention (§8 of the Nov. 19 draft) | No asking another agency, vendor, database, or private network to do what this policy forbids Cabot to do directly, and no sharing for the purpose or effect of evading it. No prohibited purposes (personal, discriminatory, movement-record building). Violations: discipline up to termination, willful violation = access revoked; contractor violation = termination for cause. Whether evidence is suppressed is a court's question — the policy neither requires nor forbids it, and must not be represented to a court as doing either. |

Open questions flagged in the November 19 draft for the City Attorney and the judges who would actually receive applications (form — warrant vs. order; issuing court and after-hours route; prosecutor review; 48-hour period; reverse-search offense list; records/FOIA treatment) are **pre-go-live gates for Stage 1**, not footnotes. A rule that cannot be used at 2 a.m. will be bypassed at 2 a.m.

---

## 9. Retention and deletion

| Bucket | Pilot rule | Basis |
|---|---|---|
| Non-hit plate reads | **Automatic hard delete at 14 days.** | Cabot's chosen policy in the November 16 plan (following Quincy's planned 14 days), far inside the state ceiling. A pilot that cannot keep a short promise has no business asking for a longer one. |
| Verified hit preserved for an investigation | Preserved only under Ark. Code § 12-12-1804(b) (ongoing investigation), destroyed at its conclusion, **and the deletion is logged** — ASP Rule 6(e) pattern. A suspicion, a query, or a bulk hold is not an investigation. **v2 (amendment 4): preservation runs through the evidence lifecycle below — legal-hold flag, evidence export, prosecutor-approved disposition — not through a calendar.** The v1 design's flat 30-day delete for resolved hits is **removed**: a charged case can run months or years, and a timer deleting a hit 30 days after "resolved" can destroy evidence discovery requires, including exculpatory material. | November 16 plan §8; Clark County research 07; amendment 4. |
| Legal hold and evidence export *(v2)* | Any record tied to an investigation or criminal action may be placed under a **legal hold** in the Front Door, on a documented case basis. The retention job **never deletes a held record**. Evidence needed beyond the system is **exported to the Department's records / evidence system, hashed at export, with chain-of-custody documentation**; after export, the system copy is destroyed when the hold is released. Holds are released only on documented disposition (investigation concluded without charges, or criminal action concluded) with **prosecutor-approved disposition sign-off** — the disposition schedule is approved by the prosecuting attorney before Stage 1, because a developer or administrator does not decide evidence questions with a deletion script. Every hold, export, release, and destruction is a log entry. | Amendment 4; § 12-12-1804(b). |
| Plate-free outcome records *(v2)* | When a hit is resolved, the system writes an **outcome record containing no plate data**: camera site, list category, confirmed / non-correlating outcome, arrest (yes/no), prosecution (yes/no, updated through the prosecutor feedback loop in §13), and disposition dates. Outcome records are **preserved 18 months** and are **exempt from every retention delete** — they are the raw material of the § 12-12-1805 six-month statutory report, and they must survive the 14-day deletes that would otherwise shred the link between a read and its case outcome before a prosecution finishes. | Amendment 5; § 12-12-1805. |
| State ceiling (context, never the pilot's operating number) | 150 days for a governmental entity, § 12-12-1804(a)(2). The three numbers in Cabot's record — 30 days (current Flock vendor cloud), 150 days (statute / CPD-preserved), 14 days (this pilot) — govern three different buckets and must never be merged in public presentation. | November 16 plan §8, with primary sources there. |
| Audit log | Preserved at least **3 years** [bracketed floor in the Nov. 19 draft, §7(b) / §10 — Commission and City Attorney to conform to the applicable records schedule]. Log entries are never deleted by the retention job. | Nov. 19 draft. |
| Deletion proof | Weekly retention report, generated by the report job: rows deleted, oldest remaining read timestamp, exceptions. "Nothing older than cap" is a headline pilot success metric. | Clark County architecture §5. |

Arkansas's floor applies throughout: a governmental entity may not sell, trade, or exchange captured plate data (§ 12-12-1804(d)), with the statute's law-enforcement exception for data indicating evidence of an offense. This pilot goes beyond the floor by policy: **no sharing at all during the pilot** except (a) a specific, case-tied disclosure authorized in writing by the Administrator, logged, and named in the public report, or (b) a disclosure state or federal law or a court order compels, likewise logged and reported.

**Disclosure processes that must exist before they are needed (v2, amendment 7).** Section 12-12-1808 makes the registered owner a permitted recipient of their own vehicle's data — which means a resident asking "what do you have on my car?" is a lawful request the system must be able to honor, and v1 had no process for it. The governing policy (companion document 6) therefore defines, before go-live: (1) a **registered-owner request process** — written request, identity and registration verification, response through the Front Door with the request and the disclosure both logged; and (2) a **protection-order suppression flag** that must be built and tested **before** any owner-disclosure feature is enabled: when a protection order is presented for a vehicle, that vehicle's data is not disclosed to anyone — including a co-owning registered owner — except as the result of a match. The scenario is concrete: an abuser who co-owns the victim's car using the owner-disclosure right to locate them. The flag precedes the feature, in that order, or the feature does not ship.

**Public records and the audit log.** The six-month statistical report is a public record, and the audit log will be requested under the Arkansas Freedom of Information Act. The log's FOIA posture is designed, not improvised: published daily checkpoints (root hash + entry count) make the chain's integrity **publicly verifiable without disclosing log contents**; a FOIA production of log extracts uses a **redaction process** (case numbers of open investigations, officer identifiers where exempt, and any plate references — which are keyed hashes in any event, §4) confirmed by the City Attorney before go-live. Redaction protects the contents; the published roots protect the public's ability to verify nothing was rewritten. Neither is traded against the other.

---

## 10. Sentinels and canaries — what is in the pilot, and what is deliberately deferred

The Clark County design adds two controls on top of the hash chain. This spec phases them honestly instead of promising all of them at once:

**In the pilot (Stage 1, from day one):**
- **Hash-chained log + Sentinel v2 witnessing** (§4): entries streamed as written to an independent sink outside Department and administrator control; **daily** signed checkpoints (root hash + entry count) published to the Clerk and the public repo; the auditor recomputes the chain independently. Simple, proven pattern, highest value per unit of complexity — with the v1 weekly window closed, because a plain unkeyed chain with a weekly anchor leaves up to seven days an insider can rewrite and recompute before anyone outside can tell. *(Amendment 3.)*
- **Missed-checkpoint alarm.** If a scheduled witness publication or retention run does not happen, the Administrator and the outside auditor are alerted. Silence is treated as an incident, not as "probably fine." In v2 this is one instance of the general dead-man alarm rule (§13, amendment 9): retention job, recognition bridge, and witness publication each page the Clerk and the auditor when an expected event *doesn't* happen, and a missed publication is itself recorded as a public event in the next checkpoint.

**Deferred to a post-pilot phase, with reasons stated:**
- **Forward-secure sentinel agents** (per-epoch Ed25519 keys, each checkpoint committing to the next epoch's public key, prior private keys destroyed, hourly epochs, outbound-only agents, silence-as-alarm per machine). Clark County's own build order puts full sentinels first among its *post-architecture* items and the hardware data diode last; for a 3-camera, 90-day pilot, witnessed hash publication captures most of the tamper-evidence value at a fraction of the key-ceremony burden. **v2 note:** the council review moved the *witnessing* half of this design into the pilot — real-time streaming to an independent sink and daily checkpoints (§4) — because the weekly window in v1 was the chain's weakest point. What remains deferred is the forward-secure key machinery itself (per-epoch keys, key destruction, data diode), not the outside copy. If the Council authorizes a full system, the sentinel design (Clark County `design/sentinels.md`, including in-person pinning of each machine's first public key by the outside auditor, and its 3-of-5 key ceremony model in `design/ceremony-protocol.md`) is the Commission's starting text. [Source: Clark County sentinels §§A–B, "Build order"]
- **Canary records** (fake plate reads no legitimate query should ever return; any hit = a dragnet, bulk export, or exfiltration, alerted immediately). Deferred for the Clark County reason: a canary must **never be a real plate** — seeding requires confirming a non-issuable Arkansas plate format with the DFA, excluding canaries from § 12-12-1805 statistics, public reports, and any evidence export (with a test proving it), and seeding by the outside auditor, not City IT. That groundwork is a Commission task during the pilot; canaries go live only when it is done. [Source: Clark County sentinels §B, "Hard rules"]

Deferring a control is a disclosed design choice in this spec, not a silent omission. The day-90 report must state what the pilot's log could and could not detect, in plain language.

**What the demonstration must show — and say (v2, amendment 12).** The council demo is this design's public face, and the council review was blunt about its current limits: the tamper test beats a careless attacker (one entry edited, hashes not recomputed), and the console is a simulation, not the production system. Any public demonstration of the pilot design must therefore:

1. **Show a bypass attempt, not just a log edit.** The demo includes an attempt to reach plate data *around* the Front Door — through the recognition layer's interface or a direct database read — and shows it blocked or logged under the §4 sensor-lockdown configuration. A demo that only proves the software follows its own rules when used as designed answers the wrong question; the resident's question is what catches someone who refuses to use it as designed.
2. **Re-run the tamper test as a full-chain rewrite.** The attacker in the demo edits history *and recomputes the chain* — and is caught by the witnessed daily checkpoints and the independent sink, not by internal consistency. If a demonstration build cannot yet do this, the presenter says so, on the record, rather than letting the weaker test imply the stronger property.
3. **Disclose the console's status on screen.** Any demonstration console that is not wired to the production Front Door API carries that disclosure **on screen, in the demo itself** — "demonstration console: simulated data, not connected to the production system" — not in a footnote or a verbal aside. The same honesty rule applies to the match workflows shown: if hot-list matching is not yet authorized under the ACIC path in force, the demo labels match screens as simulated workflow, not Day-1 capability.

---

## 11. Success metrics and kill conditions — decided before the pilot starts

Following the Clark County action plan §5 ("must prove / how you show it"), expanded with Cabot's tier and cost questions. **Thresholds marked [Commission decision] are proposed starting points; the Commission sets the final numbers in its June 2027 report, before Stage 1 is authorized — and may not loosen them mid-pilot without a public vote of the Commission recorded in its minutes.**

**Judge the pilot on ground truth, not outcomes (v2).** The council review's arithmetic is adopted: at the Department's reported rates for January 1 – June 30, 2026 — 8,040,000 plates scanned, 688 matches, 7 stolen vehicles recovered, 19 arrests across the 9-camera system — a 3-camera, 90-day pilot projects to roughly 114 matches, about 1 recovery, and about 3 arrests. Counts that small are noise: zero recoveries would not prove failure and three would not prove equivalence. Outcome counts are reported (they are statutory-report material, §9), but **no success threshold and no kill condition in this section rests on them**. The pilot is judged on capture rate and read accuracy against ground truth, misread rate, alert latency, and uptime — the things a 90-day test can actually measure.

| # | Must prove | How it is shown | Proposed threshold |
|---|---|---|---|
| 1 | Plates read at road speed | Read-rate report against a hand-checked sample (Appendix C), reported separately for day / night and for the high-speed vs. slow site. **Plate-text accuracy and jurisdiction (state) accuracy are scored and reported separately** — a correct character string with the wrong state is not a correct read, and an uncertain jurisdiction must never silently become a confident match (v2) | ≥ 90% correct full-plate reads on the slow site and ≥ 85% on the high-speed site, with false-positive (misread-as-a-different-valid-plate) rate < 1%; jurisdiction accuracy reported alongside, threshold set by the Commission with the text threshold **[Commission decision]** |
| 2 | Every search logged, with a person and a validated case | Auditor's sample audit of the full log; count of searches without a validated case number | **Zero** unlogged or unvalidated searches. One is a kill condition, not a rounding error. |
| 3 | The log cannot be quietly edited | Daily witness checkpoints all verify; auditor's independent recomputation matches the streamed sink; one live verification demo for the Council, run by the auditor, not the Administrator, conducted to the §10 demonstration standard (full-chain rewrite attempt, bypass attempt) | 100% of daily checkpoints verify against the witness copies and the independent sink |
| 4 | No shared accounts | Account list vs. log user list, audited monthly | Zero shared / generic / dormant accounts |
| 5 | Data deletes on schedule | Weekly retention reports (§9) | Zero reads older than 14 days (outside a logged § 1804(b) hold) at any weekly check |
| 6 | Hot-list alerts work end-to-end | Count of Tier 1 alerts, verification outcome for each, and time from capture to alert | Every alert either verified through dispatch/ACIC or documented as a misread; alert latency reported, threshold set after the ACIC call **[Commission decision]** |
| 7 | Tier rules hold in practice | Tier 3 log vs. authorizations on file (monthly Administrator review + auditor spot-check, per Nov. 19 draft §10(c)); emergency searches and their 48-hour follow-ups counted | Zero Tier 3 searches without a matching authorization or a timely emergency filing |
| 8 | Maintenance is real and bounded | Administrator + backup log hours weekly (task-level, §13 table) | Sustained load reported as-is; **> 10 staff-hours/week sustained over any 4 pilot weeks is a scale-blocker** — the full-system recommendation must then price a position or a support contract, not absorb it silently **[Commission decision]** |
| 9 | Cost stays inside the envelope | Actuals vs. §12 table, reported monthly | Pilot actuals within the §12 high case; any line exceeding it is reported to the Council that month, not at day 90 |
| 10 | The emergency exception stays exceptional *(v2)* | Emergency-flag uses counted monthly; **100% receive post-hoc review** (§8); frequency reported in the monthly report | Every emergency use post-hoc reviewed; sustained frequency above the Commission's threshold — proposed starting point: more than 2 emergency uses in any rolling 30 days, or any pattern the auditor judges routine — triggers kill condition K8 **[Commission decision]** |

**Kill conditions — any one stops Stage 1 (or ends it early), and the Commission reports the stop and the reason to the Council in public session:**

- **K1. ACIC Path C** (§5): only approved vendors may receive hot-list data, and no approval path is available to this system.
- **K2. CJIS cost erasure:** Path B applies *and* the priced CJIS compliance burden (audit, hosting move, training, fingerprinting, Administrator time) pushes the pilot's honest 5-year projection at or above the November 16 purchase model's margin — i.e., the unpriced lines together approach the ~$13,600–$16,700/year break-even band that plan computed (standard case ~$15,800/year). The Commission recomputes this with pilot actuals; it does not reuse the purchase model's numbers as if they were the pilot's.
- **K3. Accuracy failure:** After site tuning documented in the log, read rates remain below Metric 1 thresholds, or the false-positive rate exceeds its threshold — because a misread is not a statistic; in March 2026 a family was stopped at gunpoint after an apparent Flock misread, which is exactly what ASP's verify-before-a-stop rule exists to prevent. [Source: Clark County research 07, "Wider Arkansas context"]
- **K4. Any unlogged access, any shared-account use, or any witness-hash mismatch that cannot be explained as a documented clerical error** — verified by the auditor, not self-certified.
- **K5. Any sharing outside §9**, any Tier 3 search without authorization, or any use for a purpose outside the governing policy's exhaustive list.
- **K6. No maintainer, no system:** the named Administrator or the named backup leaves and no fingerprint-cleared (Path B) / trained successor is designated within 30 days. A system with a bus factor of one is, in the Clark County phrase, a system that "rots when its one owner leaves." [Source: Clark County research 04, "The real risk: maintenance"]
- **K7. Vendor-lock creep:** any component adopted mid-pilot whose license, format, or terms would prevent the City from exporting its own reads and log in open formats, or from replacing that component — reported by the Administrator or auditor. Open-source licenses are checked before adoption (e.g., Frigate/fast-alpr stack licenses, YOLO's AGPL-3.0-or-commercial terms where applicable), not assumed.
- **K8. The exception became the rule (v2):** emergency-flag use exceeds the Metric 10 threshold, or post-hoc review finds a pattern of emergency uses that were routine investigative convenience rather than imminent-threat facts. Either finding stops Tier 3 / emergency functionality pending Commission and Council review — a bypass that becomes the everyday path has repealed the tier system without a vote.

---

## 12. Pilot budget — estimates, labelled, with the unknowns named

**Basis and honesty note.** No figure below is a quote to Cabot. Camera and site figures are the Clark County hub's October 2026 estimates and the November 16 plan's sourced Axis figure, applied to a 3-camera pilot. The November 16 purchase model's qualified 5-year estimate ($53,829–$69,579 for 9 cameras, Axis + OdinEye, *provided* connectivity, CJIS hosting, PoE power, and administration stay below ~$15,800/year in the standard case) is a **different model** and is not restated here as this pilot's cost. This pilot exists in part to price the lines that model could not.

| Line | Low case | High case | Basis |
|---|---|---|---|
| Cameras ×3 | $900 | $5,337 | Low: commodity LPR at ~$300/camera [Clark County research 04]. High: 3 × $1,779 AXIS Q1800-LE MSRP [Nov. 16 plan §3]. Stage 0 tests both classes; Stage 1 may mix them by site, so the actual will likely land between. |
| Edge / server hardware | $1,500 | $3,500 | **Estimate / allowance.** One city-owned server / edge box meeting Frigate's floor (≥4 GB RAM, AVX/AVX2 CPU) with storage for 14 days of reads + plate crops at 3 sites and 3 years of audit log. Procurement prices the actual specification; storage sizing is a Commission technical task (read volume at Cabot sites is not yet measured — Flock-volume figures from other systems must not be imported as Cabot facts). |
| Installation ×3 sites | $450 | $5,700 | **Allowance.** The November 16 plan's installation schedule applied to 3 sites: 3 × $150 (existing infrastructure) to 3 × $1,900 (new pole with solar), standard case 3 × $650 = $1,950. It is Flock's published cooperative schedule used as an allowance for non-Flock hardware, to be replaced by the §6 site survey. Off-grid sites may instead price inside the Clark County ~$800–$2,500/site all-in estimate — do not double-count both; the survey picks one basis per site. |
| Recognition software licenses | $0 | $0 | Open-source stack. $0 is a *license* figure only — see Administrator time below. Any paid fallback converts the model (§4, bake-off rule). |
| Connectivity, pilot period (~4 months incl. Stage 0) | $240 | $600 | **Estimate.** $20–$50/camera/month [Clark County research 04] × 3 cameras × 4 months, where a site is not already wired. Wired city sites price lower; the survey establishes it. |
| **Pilot hardware + install + connectivity subtotal** | **~$3,090** | **~$15,137** | Sum of the lines above. Standard-install, Axis-camera midpoint is roughly $9,000–$10,000. |
| Administrator + backup time | *Not $0 — recorded as hours* | *Not $0 — recorded as hours* | No new hire is proposed for the pilot. Time is logged weekly against the §13 task table and reported in hours and in loaded-cost terms in the day-90 report, so the full-system decision prices labour from Cabot actuals for the first time. |
| CJIS compliance (Path B only) | *Unpriced — gate, §5* | *Unpriced — gate, §5* | Audit, hosting, training, and fingerprinting costs are obtained after the ACIC call and **before** Stage 1 authorization. Path A carries no such line beyond training time. |
| Outside auditor | *Priced at designation — see note* | — | **v2 (amendment 9): auditing is a named, paid or contracted role**, designated by the Council outside the Police Department chain of command (cf. Nov. 19 draft §10(c), annual independent audit). The v1 assumption of an unpaid citizen auditor is removed: weekly verification, monthly sampling, and independent chain recomputation are work, and a control that depends on unpaid goodwill is a control designed to lapse. The Council prices the role (part-time contract or stipended designation) as part of the Stage 1 authorization; the amount is an appropriation decision, stated openly, and is not hidden inside another line. |
| Contingency | — | — | No percentage contingency is invented here. The known contingency in Cabot's existing record — a $4,500 Flock termination-for-convenience fee ($500 × 9 units, Agreement §6.2) — belongs to the *contract-exit* decision, not to this pilot, and must not be double-counted into pilot costs. [Source: Nov. 16 plan §3] |

**Comparison, for scale only (applied arithmetic):** 3 cameras on Cabot's current Flock terms pro-rate to ~$9,167/year ($27,500 invoiced in 2026 for 9 units ÷ 9 × 3 — *invoiced, not proven paid; staggered tranches, not a single annual bill*, per the November 16 plan §1 precision limits). The pilot's entire hardware subtotal is therefore on the order of **four months to twenty months of what 3 leased cameras cost** — and at the end of the pilot the City owns the hardware either way. That comparison does not include staff time or any Path B costs, and must always be quoted with that sentence attached.

---

## 13. Staffing, maintenance, and the runbook — the real cost, made visible

The Clark County hub and the November 16 plan agree on the finding: none of the switch reports collected mentioned a new hire, administration was absorbed by existing personnel where government infrastructure carried hosting — **and** staff time is still the real recurring cost. This pilot does not promise "no new hire" and does not cost labour at $0. It measures it.

| Recurring task | Owner | Pilot cadence |
|---|---|---|
| User accounts, role changes, account review | System Administrator | On change + monthly pilot review (quarterly in a full system) |
| Case-list / RMS validation feed health | Administrator, with Department records | Weekly check, logged |
| Hot-list source checks; custom-list documentation audit | Administrator, with the Department | Weekly |
| Audit-log review; anomaly-flag disposition | Administrator (weekly) **and** Outside Auditor (daily checkpoint verification, monthly sample audit incl. searched-plate-vs-case-file relevance sampling, §7 item 8) | Daily / weekly / monthly |
| Statutory outcome tracking | Administrator, with the prosecuting attorney's office | Prosecution outcomes for hit records updated as cases conclude; feeds the § 12-12-1805 six-month report (§9) |
| Tier 3 authorization file vs. log reconciliation | Administrator | Monthly, per Nov. 19 draft §10(c) |
| Camera health, failure triage, replacement logistics | Administrator, with installer / supplier support priced in procurement | On failure + weekly health report |
| Software / firmware updates on city components | Administrator; backup observes at least one update cycle | As released, staged: Stage 0 feed first, never all sites at once untested |
| Retention-job and witness-publication verification | Auditor (independent of Administrator) | Daily checkpoint; weekly summary |
| Public-records response for system records; monthly + day-90 reports | Administrator, with City Clerk/Treasurer | Monthly |
| Accuracy sampling (Appendix C) | Commission designee + auditor | Stage 0: weekly; Stage 1: monthly |

**Named people, before go-live:** (1) System Administrator, by name, in the governing policy; (2) a **named backup** who has completed the same training (and, on Path B, the same fingerprint check) and has run at least one update and one log review under observation; (3) Outside Auditor, designated by the Council, outside the Police Department chain of command, as a paid or contracted role (§12); (4) Department TAC as ACIC liaison. A pilot with only item (1) filled does not start (kill condition K6). **On-call expectation (v2, amendment 9):** the Administrator and backup carry a stated on-call rotation for pilot incidents (camera outage, ingest failure, retention or witness alarm), with the rotation and its compensation treatment written into the governing policy — a system nobody is on call for is a system whose failures are discovered by residents. **The Commission's lane, stated once more:** the Commission designs the policy, sets the thresholds, and receives summaries and redacted reports; it does not patch servers, review raw logs, or hold credentials. Conflating the design body with the operating staff is how volunteer commissions become unpaid IT departments and quietly stop meeting.

**Dead-man alarms (v2, amendment 9).** Three pilot processes fail silently by default — the retention job, the recognition (Frigate/fast-alpr) bridge, and the witness publication — so each carries a **dead-man alarm**: an expected event that does not occur by its deadline pages the System Administrator, the Outside Auditor, **and the City Clerk**. A missed witness publication is additionally recorded as an event in the next successful checkpoint, so the gap is part of the public record rather than a private embarrassment. Silence is an incident (§10); this paragraph names whose phone it rings on.

**Runbook requirement.** Before Stage 1, the Administrator delivers a written runbook — install, update, backup/restore, account on/off-boarding, retention failure, witness failure, camera replacement, incident disclosure — sufficient for the backup, or a successor, to run the system without the author. The runbook is part of the published open-source repository (credentials and hot-list data excepted). "Don't expand past the pilot until someone besides you can keep it running" is adopted as a scale gate. [Source: Clark County action plan §6]

---

## 14. Timeline — Commission first, pilot second, full decision last

All dates are planning targets tied to the companion ordinance's sequence (Commission convenes first week of February 2027, written recommendations June 2027, implementation target December 1, 2027 only if the Council separately authorizes after public hearing). If the written contract-expiration confirmation the companion ordinance directs moves the full-system target, this timeline moves with it by Council resolution — it does not silently detach.

| When | Step | Gate |
|---|---|---|
| Feb. 2027, wk. 1 | Commission convenes; adopts this spec (as amended) as a working text | — |
| Feb. 2027 | **Joint ACIC call** via Department TAC (Appendix B); City Attorney begins CJIS/path review | Answers documented and sent to the Commission in writing |
| Feb.–Mar. 2027 | Hosting route identified **by name, verified, and priced** (city server vs. any Arkansas CJIS-compliant host) — the November 16 plan's gating item, carried over | No named, priced hosting route = no Stage 1 recommendation |
| Feb.–Mar. 2027 | **Governing policy adopted** (moved ahead of Stage 0 in v2, amendment 1): policy drafted from companion document (6), incorporating §8 tiers; City Attorney + judicial-officer questions from the Nov. 19 draft put to the judges who would receive applications; Council adopts the policy | **No adopted policy, no capture of any kind — Stage 0 included** |
| Mar.–Apr. 2027 | Stage 0 bench/lot test: 1 camera, CPD-operated, consenting vehicles only, both recognition candidates, both camera classes, Appendix C protocol | Accuracy results published to the Commission, pass or fail |
| May–June 2027 | **Independent adversarial verification** of the complete data-access boundary (amendment 11): a technically qualified reviewer who did not build the system attempts to access, export, alter, and retain plate data outside the Front Door — administrator access, recognition layer, backups, ingest bridge — and to circumvent the witness mechanism. Written report to the Commission and Council | **Any unresolved critical bypass blocks Stage 1 authorization.** The report classifies each finding: prevented / independently detectable / accepted risk |
| June 2027 | Commission's written recommendations to the Council, **including a pilot go / no-go recommendation with the final §11 thresholds** | Commission report is public |
| June–July 2027 | Council public hearing; **separate vote** authorizing (or declining) the Stage 1 road pilot, its 3 sites, its budget, and its 90-day sunset | No hearing + vote, no pilot. Commission work alone authorizes nothing. |
| July 2027 | Procurement (quotes against §12), site surveys (§6), runbook, accounts, training, fingerprint checks if Path B | §13 named-people checklist complete |
| Aug.–Oct. 2027 | **Stage 1: 90-day live pilot** at 3 sites; daily witness checkpoints; monthly reports to the Council in public session | Kill conditions §11 live throughout |
| Nov. 2027 | Day-90 public report: every §11 metric, all failures and misreads, actual hours, actual costs, sentinel/canary readiness statement (§10) | Report filed with City Clerk/Treasurer and published |
| Nov.–Dec. 2027 | Council decision on a full city-controlled system (open-source, purchase model, hybrid, **or none — discontinuation is an express option, and a failed or completed pilot does not default to renewing the current vendor**, amendment 13), in time for the December 1, 2027 target **if** that is the decision | Separate ordinance + appropriation, as the companion ordinance requires |

---

## 15. Risks and mitigations

| # | Risk | Mitigation in this spec |
|---|---|---|
| 1 | **Accuracy at speed / at night.** Open-source OCR is "good for driveways and slow approaches, marginal at highway speed" on current evidence; no vendor-style accuracy guarantee exists. [Clark County research 04, verdict] | Two-stage testing; site-class thresholds (§11 Metric 1); camera shutter/IR/varifocal spec (§4); verify-before-a-stop on every alert (§8 Tier 1). Failure is a kill condition, not a public-relations problem. |
| 2 | **Maintenance rot / bus factor of one.** "As few as 13% of large government IT projects succeed"; ~80% of federal IT spend is legacy maintenance. A one-person system rots when that person leaves. [Clark County research 04] | Named backup, runbook, open-source publication, hours measurement, scale gate (§13), kill condition K6. |
| 3 | **Log that nobody reviews.** California's mandated ALPR logs got "little to no auditing"; CJIS audits run on a 3-year cycle — detection measured in years. [Clark County audit-log research] | Daily witnessed checkpoints with independent auditor recomputation, weekly auditor review, monthly sample audit incl. relevance sampling (§7), anomaly flags (§7), dead-man alarms (§13). Review is a named person's dated task, not an aspiration. |
| 4 | **NDAA §889.** Hikvision/Dahua-class cameras are barred for federal / federally funded purchases. | **v2 (amendment 10): compliance is required for the pilot regardless of funding source** — camera class (a) is an NDAA-compliant equivalent if the Clark County commodity example is not compliant, priced in procurement; onboard storage and cloud/P2P features disabled (§§4, 6). [Clark County research 04] |
| 5 | **Key custody defeats the hash chain.** Whoever holds the signing key can rewrite and re-sign. | Witness copies held by the Clerk and a public repo (§4); Sentinel v2 streaming to an independent sink plus daily checkpoints shrink the rewrite window from a week to a day and put a copy outside the key-holder's reach (§§4, 10); in a full system, the Clark County sentinel/key-ceremony design (in-person pinning by the auditor; split custody) is the starting text (§10). Pilot limitation disclosed in the day-90 report. |
| 6 | **Function creep.** A working pilot invites new uses (parking, code enforcement, school zones) one quiet request at a time. | Permitted uses are exhaustive in the governing policy; any new use is a new public Council decision. Sharing and circumvention bans (§§8–9) have no administrative waiver. |
| 7 | **Public-records / litigation exposure.** Reads, logs, and reports will be requested and, where the law requires, produced. A system designed assuming secrecy will fail in daylight. | Design assumes publication: aggregate reports are generated from the log itself; target-identifying details of pending investigations are handled as the Nov. 19 draft §10 provides (de-identified public reporting), with FOIA treatment confirmed by the City Attorney before go-live. |
| 8 | **Evidence challenges.** Defence counsel will attack an open-source system's accuracy and log integrity in any case a pilot read touches. | Hand-checked accuracy record (Appendix C), witnessed hash chain, verify-before-stop documentation, and ASP-style verification create the record a court will ask for. The pilot makes no claim that a read is proof — it is a lead (§8). |
| 9 | **Alert fatigue from sentinel/witness alarms** on flaky LTE sites (a Clark County warning). | Per-site alert thresholds; every alert and its disposition logged, so an auditor who starts ignoring alarms leaves a record of doing so. [Clark County sentinels, "How each piece fails"] |
| 10 | **Cost creep in the unpriced lines** — the exact failure the November 16 plan disclosed for the purchase model. | §12 names them, §5 gates Path B pricing before authorization, kill condition K2 recomputes break-even with pilot actuals. |
| 11 | **Accountability proven at the application layer only (v2).** The v1 design logged everything that passed through the Front Door — and nothing that went around it: the recognition layer's own UI, database, and snapshots; direct database or filesystem access; backups. An insider's realistic misuse is a *read*, which a hash chain does not detect at all. | Sensor lockdown (§4) makes the Front Door the only lasting store; authenticated ingest; isolated camera VLAN; backups on the same retention schedule; and **independent adversarial verification as a binding pre-Stage-1 condition** (§14, amendment 11) — the proposal's distinguishing claim is demonstrably accountable surveillance, and if that cannot be established independently, the trust problem has been transferred from a vendor to city personnel, not solved. |
| 12 | **Evidence spoliation by timer (v2).** A flat retention/delete schedule destroys records a live investigation, prosecution, appeal, or *Brady* duty requires the City to keep. | Legal-hold flag, hashed evidence export with chain of custody, prosecutor-approved disposition schedule (§9, amendment 4); the retention job never deletes a held record. |
| 13 | **Exception normalization (v2).** Tier 3's authorization instrument is untested in Arkansas practice; if judges decline to sign or the workflow fails at 2 a.m., urgent queries funnel through the supervisor emergency flag until the exception *is* the system. | Post-hoc review of every emergency use, frequency metric with a kill threshold (§§8, 11, K8); the instrument question is a pre-go-live gate (§8), and the two-key workflow is demonstrated in Stage 0 conditions before Stage 1 relies on it. |

---

## 16. Open questions — assigned, not left floating

| Question | Owner | Needed by |
|---|---|---|
| Which CJIS path (A / B / C) applies, and on what ACIC agreement? | City Attorney, via Dept. TAC, from ACIC | Mar. 2027 — gates everything |
| Can dispatch/CAD ingest reads from an outside city system and match in real time — and at what end-to-end latency? (Path A realism, v2) | Department dispatch / CAD supervision, via TAC — three-lane package, Lane 3 (held until Lanes 1–2 answer) | Before the Stage 1 design is frozen; a "no" collapses the choice to Path B (priced) or C |
| Does CJIS scope arise through the case-list sync or the hit-detail return flow, rather than the hot list? (v2) | ACIC — three-lane package, Lane 1 question 9; Appendix B question 9 | With the path answer |
| Who owns the § 12-12-1804(c) 24-hour update duty when matching is off the city server? (v2) | ACIC / City Attorney — Lane 1 question 10; Appendix B question 10 | With the path answer |
| Is there an Arkansas CJIS-compliant hosting route available to Cabot, by name and price — or is it a city server? | City Attorney + Administrator-designee | Mar. 2027 |
| Judicial-authorization open questions (form, issuing court, after-hours, prosecutor review, 48 hours, reverse-search list, records treatment) | City Attorney, with the receiving judges | May 2027 — gates Stage 1 |
| Non-issuable Arkansas plate format for future canaries — DFA confirmation | Outside Auditor-designee, via City Attorney | During pilot; gates canaries only |
| Exact Flock expiration / non-renewal dates per order form (companion ordinance §4 direction) | Mayor + City Attorney | Feb. 2027 — sets the Dec. 1 target's firmness |
| Storage sizing from measured Cabot read volume at pilot sites | Administrator, from Stage 0/1 actuals | Day-90 report |
| Who supplies ASP's cameras/software, and do ASP's quarterly Legislative Council reports include query counts and sharing recipients? (FOIA if needed) | Commission research task | June 2027 report — a model, or a gap, for Cabot's reporting |
| Insurance / risk-pool position on a self-hosted law-enforcement system | City Attorney / Clerk-Treasurer with the City's insurer | Before Stage 1 appropriation |

---

## Appendix A — Audit log: minimum fields

From Clark County architecture §4, with Cabot's tier fields added (marked †) and v2 fields added (marked ‡):

`seq · timestamp_utc · user_id (individual) · auth_method · case_number · case_validated (bool) · ‡justification (own-words, required — §7 item 6) · query_type (†tier) · query_params (‡plate_ref — a keyed HMAC reference, never raw plate text; partial / description searches recorded by type and length) · result_count · requesting_agency · shared_with (if any) · legal_basis (warrant / court order / hotlist / emergency† / none) · †authorization_number + issuing officer (Tier 3) · †canary_hit (bool) · ‡legal_hold_set / released (with case basis) · ‡evidence_export (hash + custody reference) · prev_hash · entry_hash`

**Why no plate text (v2):** the chain is append-only and effectively permanent; plate text in it would be captured plate data retained forever, past the 150-day statutory ceiling and every retention promise in §9. Keyed references keep entries correlatable by key holders and useless to anyone else. Implemented and verified in the working code, November 23, 2026.

Retention and deletion runs also write entries: `job_id · rows_deleted · oldest_remaining_ts · ‡holds_honored (count of held records skipped)`.
Witness publications write entries: `witness_target · root_hash_published · ‡entry_count · verified_by · verification_date · ‡missed_checkpoint (bool, for a gap being closed)`.

## Appendix B — The ACIC call: questions to ask, in order

Adapted from Clark County research 05 (call-prep) and action plan §3, for Cabot's TAC to put jointly with a Commission designee:

1. How do LPR systems in Arkansas receive NCIC/ACIC hot-list data today? What agreement, ORI status, and approvals does it take?
2. Does a city server that *stores plate reads only* — with hot-list matching done through our existing dispatch/TAC workflow — stay outside CJIS system status? (Path A confirmation)
3. If the city server holds a hot-list *extract*, does it become a CJIS system? Which of the 13 CJIS policy areas then apply, and what does the IT audit process and timeline look like for a city of Cabot's size?
4. What fingerprint, training, and Security Addendum requirements apply to (a) the System Administrator, (b) a backup administrator, (c) an outside citizen auditor with log-only access, (d) any contractor with maintenance access?
5. How does the Arkansas State Police system receive its hot lists — and could ASP-side matching ever be available to a municipal system, so the city box never holds CJI?
6. Are there state-approved-vendor requirements for ALPR systems receiving hot-list data? If so, how does a system obtain approval? (Path C test)
7. What audit cadence will ACIC apply to Cabot under each path, and what corrective-action timelines follow a finding?
8. Who at ACIC is our named contact for the pilot, and will ACIC put the answers to these questions in writing?
9. *(v2)* Can CJIS scope arise from data flows other than the hot list itself — specifically, (a) syncing a records-system open-case list to the city server so searches can be validated against real case numbers, or (b) hit details (which list matched, and why) flowing back from dispatch/ACIC to the city server after a match?
10. *(v2)* Ark. Code § 12-12-1804(c) requires captured plate data to be updated against the lists within 24 hours where updates are available. When matching happens off the city server (on the dispatch/ACIC side), who owns that update duty — the Department, ACIC, or the operator of the city server?
11. *(v2)* Can Cabot's dispatch/CAD ingest plate reads from an outside city-operated system and match them against hot lists in real time? Through what interface, and at what end-to-end latency from camera read to alert reaching an officer? (Put jointly to ACIC and, in Lane 3 of the three-lane package, to the Department — Path A stands or falls on this answer.)

## Appendix C — Hand-checked accuracy protocol (Stage 0 and Stage 1)

Vendor and library accuracy claims are not evidence. The pilot measures its own:

1. **Sample.** For each measurement period, a human reviewer hand-reads a random sample of at least 500 vehicle passes per site class (or all passes, if fewer), from the camera's own plate crops plus a ground-truth view, *before* seeing the system's reads.
2. **Score.** Per pass: correct full-plate read / partial read / missed plate / misread (system returned a different, plausible plate). Misreads are reported separately from misses — a miss wastes time; a misread can stop an innocent person. **Plate-text accuracy and jurisdiction (state) accuracy are scored as separate rates (v2)** — the ground truth records the issuing state from the plate itself, and a read with correct characters but the wrong or guessed state is scored as a jurisdiction error, not a correct read. Conditions (day / night / rain / glare) are recorded per pass so the rates can be split by condition as well as by site.
3. **Split.** Results are reported by site, by day/night, by condition, and by candidate (Stage 0 bake-off), never only as a blended average that hides a failing site.
4. **Publish.** The sample sheets (plate values redacted in the public version; unredacted sample retained by the auditor under the governing policy), the counts, and the computed rates go into the Commission's record and the day-90 report.
5. **No tuning on the test.** Camera or model changes made to improve a score are logged, and the sample is re-drawn after any change. A score earned on a sample the system was tuned against is not reported as a measurement.

## Appendix D — Sources

- Sanders, B., *Flock Alternatives: A Research Hub* (Clark County, Arkansas), GitHub `TiredofSleep/flock-alternatives`, Oct. 2026 — README; `design/architecture.md`; `design/sentinels.md`; `research/02-audit-log-models.md`; `research/04-build-path-cjis.md`; `research/07-arkansas-state-police-lpr.md`; `docs/action-plan.md`. Status, in its own words: "research and planning, not a product."
- Cabot City-Controlled ALPR Plan — Technical and Cost Proposal, Nov. 16, 2026 (rev. Nov. 17, Hostile QA Round 2) — Cabot invoice figures ($27,500 invoiced in 2026 for 9 units; staggered tranches; invoiced ≠ paid), Axis Q1800-LE MSRP $1,779, installation allowance schedule, 14-day retention proposal, break-even band for unpriced lines (~$13,600–$16,700/yr; standard case ~$15,800/yr), disclosed unknowns.
- Draft Ordinance — Third-Party ALPR Ban and Citizens Commission, Nov. 16–17, 2026 — Commission composition and charge, Feb./June/Dec. 1, 2027 sequence, separate-authorization rule, contract-date confirmation direction.
- Draft Tiered Judicial Authorization for Access to ALPR Data, Nov. 19, 2026 — §§1–13 and appendices, summarized at §8 of this spec.
- AI Council Synthesis — NOCTUA / Cabot Open-Source ALPR Package, Nov. 23, 2026 — four-seat hostile review (ChatGPT, Claude ×2, Gemini) of the v1 spec, the demonstration console, and the deploy package; the 13-item amendment list folded into this version, the preserved disagreements, and the two code findings verified and fixed the same day (plate text in the audit chain; file-layer deletion).
- Three-Lane Inquiry Package — City-Owned ALPR Evaluation, Nov. 23, 2026 — Lane 1 (ACIC / Arkansas State Police, 10 questions), Lane 2 (City Attorney, 7 opinion questions), Lane 3 (Police Department / dispatch, held until Lanes 1–2 answer). Drafts only; nothing in that package had been sent as of this version.
- Ark. Code §§ 12-12-1801 to -1808 (Act 668 of 2025, as cited in the Clark County legal reference and the November 16 plan) — 150-day governmental ceiling (§ 1804(a)(2)), ongoing-investigation exception (§ 1804(b)), no sale/trade/exchange by a governmental entity (§ 1804(d)), semiannual statistics (§ 1805). *Verify against the official code before filing or quoting in an ordinance.*
- Arkansas State Police License Plate Reader Rules, 130.01.24 Ark. Code R. 002, as digested in Clark County research 07 — ownership (Rule 5(d)), retention and logged deletion (Rules 6(d)–(e)), dissemination log (Rules 6(b)–(c)), verify-before-stop (Rule 6(a)), quarterly Legislative Council reporting (Rule 5(e)).

---

*End of draft spec, version 2. Prepared for Commission discussion — not introduced, not filed, and not a statement of current City policy or of current law. All statutory references to be verified by the City Attorney against the official code before any use in an ordinance. Nothing in this version authorizes capture, purchase, or deployment (see "Labeled assumptions").*
